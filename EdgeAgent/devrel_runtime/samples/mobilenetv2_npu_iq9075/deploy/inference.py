"""MobileNetV2 inference on the Dragonwing IQ-9075 EVK (QCS9075).

Runs on-device. Preprocessing happens on the host (PIL is not shipped
on the board's minimal Yocto image); this script consumes a pre-built
float32 NCHW .npy tensor and prints latency stats plus top-K predictions.

Falls back to a random input when --input is omitted, useful for
end-to-end smoke testing without needing a real image transferred.

Runtime selection is a live probe, never an assertion (per the DevRel
app-builder convention): this script actually tries CPU, then attempts
NPU (Hexagon HTP v73) and GPU (Adreno) via the onnxruntime-qnn plugin EP,
plus (optionally) a genuine NPU run via a pre-compiled QNN context
binary through `qnn-net-run` -- and reports exactly what happened for
each. See docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md for the
full writeup and verified latency numbers.

**Board history matters here -- two independent blockers, one now lifted:**

  1. QAIRT compiler-version wall (LIFTED after a board reflash to QLI 2.0,
     2026-07). AI Hub's cloud compiler only targets QAIRT >=2.45; the
     board originally shipped QAIRT 2.38.0, which rejected every
     AI-Hub-compiled artifact ("Using newer context binary on old SDK").
     After reflashing, the board runs QAIRT 2.47.0 -- an existing
     AI-Hub-compiled context binary (QAIRT 2.45.0) now loads and executes
     correctly via `qnn-net-run` (verified live: 3.18ms mean over 50
     inferences on Hexagon HTP v73). This is the `--qnn-context-bin` /
     `attempt_qnn_context_binary()` path below.
  2. Broken Linux GPU/NPU device discovery in onnxruntime (STILL PRESENT,
     re-verified on the QLI 2.0 image with onnxruntime 1.27.0 +
     onnxruntime_qnn 2.3.0). onnxruntime's Linux device-discovery code
     expects a DRM GPU node with a `vendor` file; this board's `card0` is
     the *display* controller, not a GPU, and the Hexagon NPU is exposed
     via /dev/fastrpc-* misc nodes instead -- a convention onnxruntime's
     discovery code doesn't recognize. `get_ep_devices()` still never
     surfaces an NPU/GPU device, so the `attempt_qnn()` (plugin-EP) path
     below still reports its documented blocker. **This is a different
     code path from #1** -- fixing the QAIRT version did not fix this.

Neither of these is a bug in this script or in this board -- they are
external, structural facts, verified live rather than assumed. This
script surfaces the true state of each path independently rather than
conflating "NPU works at all" with "the onnxruntime-qnn plugin EP path
works".

Why the CPU number varies: this script prints the on-device
onnxruntime.__version__ alongside every result. A verified finding from
this board specifically: onnxruntime 1.22.1 measured 14.85 ms mean for
this exact model, while onnxruntime 1.24.2 measured 6.14 ms mean --
a 2.4x difference from the ORT version alone, on the same hardware.
Always read the reported onnxruntime version together with the latency
number; never compare latencies across onnxruntime versions as if
they were the same benchmark.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

INPUT_SHAPE = (1, 3, 224, 224)
_qnn_registered = False


def load_input(path: str | None) -> np.ndarray:
    if path is None:
        return np.random.randn(*INPUT_SHAPE).astype(np.float32)
    arr = np.load(path)
    if arr.shape != INPUT_SHAPE:
        raise ValueError(
            f"input shape {arr.shape} != expected {INPUT_SHAPE}; "
            "run host preprocessing first"
        )
    return arr.astype(np.float32, copy=False)


def load_labels(path: str | None) -> list[str]:
    if path is None or not Path(path).exists():
        return []
    return Path(path).read_text(encoding="utf-8").splitlines()


def softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max()
    e = np.exp(x)
    return e / e.sum()


def topk(logits: np.ndarray, k: int) -> list[tuple[int, float]]:
    flat = logits.flatten()
    probs = softmax(flat)
    idx = np.argsort(probs)[::-1][:k]
    return [(int(i), float(probs[i])) for i in idx]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def _bench(sess: ort.InferenceSession, inp: np.ndarray, *, iterations: int, warmup: int) -> tuple[list[float], np.ndarray]:
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name
    for _ in range(warmup):
        sess.run([out_name], {in_name: inp})
    latencies: list[float] = []
    last_logits: np.ndarray | None = None
    for _ in range(iterations):
        t0 = time.perf_counter()
        outputs = sess.run([out_name], {in_name: inp})
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        last_logits = outputs[0][0]
    return latencies, last_logits


def run_cpu(model_path: str, inp: np.ndarray, *, iterations: int, warmup: int) -> dict:
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    latencies, last_logits = _bench(sess, inp, iterations=iterations, warmup=warmup)
    return {
        "ok": True,
        "backend": "cpu",
        "onnxruntime_version": ort.__version__,
        "avg_ms": sum(latencies) / len(latencies),
        "p50_ms": percentile(latencies, 50),
        "p99_ms": percentile(latencies, 99),
        "fps": 1000.0 / (sum(latencies) / len(latencies)),
        "logits": last_logits,
    }


def attempt_qnn(model_path: str, inp: np.ndarray, backend: str, *, iterations: int, warmup: int) -> dict:
    """Attempt NPU (backend='htp') or GPU (backend='gpu') via the
    onnxruntime-qnn plugin EP. Per this module's docstring, this is
    EXPECTED to fail on this board today -- report the exact reason,
    do not fabricate a number, do not silently report "unavailable"."""
    result = {"ok": False, "backend": backend}
    try:
        import onnxruntime_qnn as q
    except ImportError:
        result["error"] = (
            "onnxruntime_qnn is not installed on-device. This is expected if "
            "the manual install step (see README.md 'On-device setup') was "
            "skipped -- CPU-only is still a fully valid run for this board."
        )
        return result

    try:
        lib_path = q.get_library_path()
        # register_execution_provider_library() raises if called twice for
        # the same EP name -- NPU and GPU attempts share one process, so
        # only register once (module-level flag, mirrors the same fix
        # applied to scripts/board_profile.py's profile_local.py logic).
        global _qnn_registered
        if not _qnn_registered:
            ort.register_execution_provider_library("QNNExecutionProvider", lib_path)
            _qnn_registered = True
        devices = ort.get_ep_devices()
        type_suffix = {"htp": "NPU", "gpu": "GPU"}[backend]
        matches = [
            d for d in devices
            if d.ep_name == "QNNExecutionProvider" and str(d.device.type).endswith(type_suffix)
        ]
        if not matches:
            result["error"] = (
                f"QNNExecutionProvider registered, but no device of type {type_suffix} "
                "was found in onnxruntime.get_ep_devices(). This is the documented, "
                "structural blocker for this board: onnxruntime's Linux hardware-device "
                "discovery expects a DRM GPU node with a 'vendor' file; this board's "
                "card0 is the display controller (msm_dpu), not a GPU, and the Hexagon "
                "NPU is exposed via /dev/fastrpc-* instead -- a convention onnxruntime's "
                "discovery code does not recognize. See NPU_GPU_INVESTIGATION_IQ9075.md "
                "section 4.2 for the full root-cause writeup. This is NOT a bug in this "
                "script or an installation mistake."
            )
            result["ep_devices_seen"] = [f"{d.ep_name}:{d.device.type}" for d in devices]
            return result

        so = ort.SessionOptions()
        so.add_provider_for_devices(matches, {})
        sess = ort.InferenceSession(model_path, sess_options=so)
        latencies, last_logits = _bench(sess, inp, iterations=iterations, warmup=warmup)
        result.update({
            "ok": True,
            "onnxruntime_version": ort.__version__,
            "providers_active": sess.get_providers(),
            "avg_ms": sum(latencies) / len(latencies),
            "p50_ms": percentile(latencies, 50),
            "p99_ms": percentile(latencies, 99),
            "fps": 1000.0 / (sum(latencies) / len(latencies)),
            "logits": last_logits,
        })
        return result
    except Exception as e:
        result["error"] = f"unexpected error attempting {backend} EP: {e}"
        return result


def _run(cmd: list[str], *, timeout_s: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, errors="replace")


def _parse_profile_viewer(text: str) -> dict[str, float]:
    """Extract avg/min/max NetRun latency (us) and IPS from
    `qnn-profile-viewer`'s stdout. Returns {} if the expected sections
    aren't found -- caller must treat that as a parse failure, not zero."""
    out: dict[str, float] = {}
    ips = re.search(r"NetRun IPS.*?:\s*([\d.]+)\s*inf/sec", text, re.DOTALL)
    if ips:
        out["fps"] = float(ips.group(1))
    for label, key in (("Average", "avg_us"), ("Min", "min_us"), ("Max", "max_us")):
        m = re.search(rf"Execute Stats \({label}\):.*?NetRun:\s*(\d+)\s*us", text, re.DOTALL)
        if m:
            out[key] = float(m.group(1))
    return out


def attempt_qnn_context_binary(
    context_bin: str,
    backend_lib: str,
    raw_input_path: str,
    *,
    iterations: int,
    warmup: int,
) -> dict:
    """Run a genuine NPU (or GPU) pass through `qnn-net-run` against a
    pre-compiled QNN context binary -- a completely different code path
    from `attempt_qnn()` above (which goes through the onnxruntime-qnn
    plugin EP and is still blocked, see module docstring point #2).

    This path is only reachable at all because the board's on-device
    QAIRT version now covers the compiled binary's target version (see
    module docstring point #1, "LIFTED"). If `context_bin` is omitted by
    the caller, this function is simply not invoked -- an untried path
    is reported as such (`ok: False`, no `error`), never silently
    fabricated as a result.

    The context binary expects NHWC float32, [0,1]-range input (per its
    AI-Hub-exported metadata.json), NOT the NCHW ImageNet-normalized
    tensor the CPU/onnxruntime paths use -- `raw_input_path` must already
    be in that format (produced on the host, see run_iq9075.py).
    """
    result = {"ok": False, "backend": "qnn-net-run"}
    if not Path(context_bin).exists():
        result["error"] = f"context binary not found on-device: {context_bin}"
        return result
    if not Path(backend_lib).exists():
        result["error"] = f"backend library not found on-device: {backend_lib}"
        return result
    if not Path(raw_input_path).exists():
        result["error"] = f"NHWC raw input not found on-device: {raw_input_path}"
        return result

    with tempfile.TemporaryDirectory(prefix="qnn_run_") as tmp:
        tmp_dir = Path(tmp)
        input_list = tmp_dir / "input_list.txt"
        input_list.write_text(f"image_tensor:={raw_input_path}\n", encoding="utf-8")
        output_dir = tmp_dir / "output"

        cmd = [
            "qnn-net-run",
            "--retrieve_context", context_bin,
            "--backend", backend_lib,
            "--input_list", str(input_list),
            "--output_dir", str(output_dir),
            "--num_inferences", str(max(iterations, 1)),
            "--perf_profile", "burst",
            "--profiling_level", "client",
        ]
        try:
            proc = _run(cmd, timeout_s=120)
        except FileNotFoundError:
            result["error"] = "qnn-net-run not found on PATH -- expected at /usr/bin/qnn-net-run on this board"
            return result
        except subprocess.TimeoutExpired:
            result["error"] = "qnn-net-run timed out after 120s"
            return result
        if proc.returncode != 0:
            result["error"] = (
                f"qnn-net-run exited {proc.returncode}: "
                f"{(proc.stderr or proc.stdout).strip()[-500:]}"
            )
            return result

        log_files = sorted(output_dir.glob("qnn-profiling-data*.log"))
        if not log_files:
            result["error"] = f"qnn-net-run reported success but produced no profiling log:\n{proc.stdout[-500:]}"
            return result

        try:
            viewer = _run(["qnn-profile-viewer", "--input_log", str(log_files[0])], timeout_s=30)
        except FileNotFoundError:
            result["error"] = "qnn-profile-viewer not found on PATH -- cannot parse latency from the raw log"
            return result
        stats = _parse_profile_viewer(viewer.stdout)
        if "avg_us" not in stats:
            result["error"] = f"could not parse qnn-profile-viewer output:\n{viewer.stdout[-500:]}"
            return result

        result_files = sorted(output_dir.glob("Result_*/class_logits.raw"))
        logits = np.fromfile(result_files[-1], dtype=np.float32) if result_files else None

        result.update({
            "ok": True,
            "qnn_sdk_version": _qnn_sdk_version(),
            "context_binary": context_bin,
            "avg_ms": stats["avg_us"] / 1000.0,
            "min_ms": stats.get("min_us", 0.0) / 1000.0,
            "max_ms": stats.get("max_us", 0.0) / 1000.0,
            "fps": stats.get("fps", 1000.0 / (stats["avg_us"] / 1000.0)),
        })
        if logits is not None:
            result["logits"] = logits
        return result


def _qnn_sdk_version() -> str:
    try:
        proc = _run(["qnn-net-run", "--version"], timeout_s=10)
        combined = proc.stdout + "\n" + proc.stderr  # "QNN SDK v..." is printed to stderr, not stdout
        m = re.search(r"QNN SDK v([\d.]+\S*)", combined)
        return m.group(1) if m else (combined.strip() or "unknown")
    except Exception:
        return "unknown"


def run_inference(
    model_path: str,
    input_path: str | None,
    *,
    iterations: int = 10,
    warmup: int = 3,
    k: int = 5,
    labels: list[str] | None = None,
    try_npu_gpu: bool = True,
    qnn_context_bin: str | None = None,
    qnn_backend_lib: str | None = None,
    qnn_raw_input: str | None = None,
) -> dict:
    inp = load_input(input_path)
    labels = labels or []

    cpu_result = run_cpu(model_path, inp, iterations=iterations, warmup=warmup)
    results = {"cpu": cpu_result}

    if try_npu_gpu:
        results["npu"] = attempt_qnn(model_path, inp, "htp", iterations=iterations, warmup=warmup)
        results["gpu"] = attempt_qnn(model_path, inp, "gpu", iterations=iterations, warmup=warmup)

    if qnn_context_bin:
        # Independent, proven-working path (see module docstring point #1) --
        # only attempted when the caller explicitly supplies a context binary
        # + backend lib + matching raw input. Reported under a distinct key
        # so it's never confused with the still-blocked onnxruntime_qnn
        # plugin-EP "npu" entry above.
        results["npu_context_binary"] = attempt_qnn_context_binary(
            qnn_context_bin,
            qnn_backend_lib or "/usr/lib/libQnnHtp.so",
            qnn_raw_input or "",
            iterations=iterations,
            warmup=warmup,
        )

    # Top-K predictions come from whichever backend succeeded first (CPU is
    # always attempted and always succeeds if the model loads at all).
    predictions = topk(cpu_result["logits"], k)
    named = [
        (idx, prob, labels[idx] if 0 <= idx < len(labels) else f"class_{idx}")
        for idx, prob in predictions
    ]

    out = {
        "model": model_path,
        "input": input_path or "<random>",
        "iterations": iterations,
        "warmup": warmup,
        "backends": {},
        "top_k": [{"class_id": i, "prob": p, "label": n} for (i, p, n) in named],
    }
    for name, r in results.items():
        entry = {k2: v for k2, v in r.items() if k2 != "logits"}
        out["backends"][name] = entry
    return out


def _print_human(result: dict) -> None:
    print(f"Model       : {result['model']}")
    print(f"Input       : {result['input']}")
    print(
        f"Iterations  : {result['iterations']} "
        f"(warmup {result['warmup']})"
    )
    print()
    for name, r in result["backends"].items():
        print(f"[{name.upper()}]")
        if r.get("ok"):
            if "onnxruntime_version" in r:
                print(f"  onnxruntime : {r['onnxruntime_version']}")
            if "qnn_sdk_version" in r:
                print(f"  QNN SDK     : {r['qnn_sdk_version']}")
            print(f"  avg latency : {r['avg_ms']:6.2f} ms")
            if "p50_ms" in r:
                print(f"  P50 latency : {r['p50_ms']:6.2f} ms")
            if "p99_ms" in r:
                print(f"  P99 latency : {r['p99_ms']:6.2f} ms")
            if "min_ms" in r:
                print(f"  min/max     : {r['min_ms']:6.2f} / {r['max_ms']:6.2f} ms")
            print(f"  throughput  : {r['fps']:6.1f} fps")
        else:
            print("  status      : NOT AVAILABLE (this is a known, documented limitation, not a crash)")
            print(f"  reason      : {r.get('error', 'unknown')}")
        print()
    if result["top_k"]:
        print(f"Top-{len(result['top_k'])} predictions (from CPU backend):")
        for rank, p in enumerate(result["top_k"], 1):
            print(
                f"  {rank}. {p['label']:<30} {p['prob']*100:5.1f}% "
                f"(class {p['class_id']})"
            )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MobileNetV2 CPU/NPU/GPU inference attempt on Dragonwing IQ-9075 EVK."
    )
    p.add_argument(
        "--model",
        default="/data/local/tmp/devrel/models/mobilenetv2.onnx",
        help="Path to mobilenetv2.onnx",
    )
    p.add_argument(
        "--input",
        default=None,
        help="Pre-built float32 NCHW .npy file (1,3,224,224). "
        "Random input if omitted.",
    )
    p.add_argument(
        "--labels",
        default=None,
        help="Path to imagenet_classes.txt for named predictions",
    )
    p.add_argument(
        "--iterations", type=int, default=10, help="Timed iterations"
    )
    p.add_argument("--warmup", type=int, default=3, help="Warmup runs")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--cpu-only",
        action="store_true",
        help="Skip the NPU/GPU attempt entirely (faster, if you already "
        "know they're unavailable on this board)",
    )
    p.add_argument(
        "--qnn-context-bin",
        default=None,
        help="Path to a pre-compiled QNN context binary (.bin) on-device -- "
        "when supplied, attempts a genuine NPU pass via qnn-net-run "
        "(a different, independently-working code path from the "
        "onnxruntime_qnn plugin EP attempt above; requires --qnn-raw-input "
        "in the matching NHWC [0,1] format, see run_iq9075.py)",
    )
    p.add_argument(
        "--qnn-backend-lib",
        default="/usr/lib/libQnnHtp.so",
        help="QNN backend library to load for --qnn-context-bin (default: HTP/NPU)",
    )
    p.add_argument(
        "--qnn-raw-input",
        default=None,
        help="Path to a raw NHWC float32 [0,1]-range tensor on-device, "
        "required alongside --qnn-context-bin",
    )
    p.add_argument(
        "--json", action="store_true", help="Emit JSON instead of human format"
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not Path(args.model).exists():
        print(f"[error] model not found: {args.model}", file=sys.stderr)
        return 2
    labels = load_labels(args.labels)
    result = run_inference(
        args.model,
        args.input,
        iterations=args.iterations,
        warmup=args.warmup,
        k=args.top_k,
        labels=labels,
        try_npu_gpu=not args.cpu_only,
        qnn_context_bin=args.qnn_context_bin,
        qnn_backend_lib=args.qnn_backend_lib,
        qnn_raw_input=args.qnn_raw_input,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
