"""run_npu_ort.py — MobileNetV2 on the Hexagon NPU via ONNX Runtime + QNN EP.

This is the runnable counterpart to the IQ-9075 retrospective findings. Unlike
the older samples (which shell out to ``qnn-net-run``), this uses the ONNX
Runtime QNN Execution Provider directly through :mod:`quad_mcp_client.ort_qnn`,
demonstrating the guard rails the retrospective asked for:

  * verifies ``QNNExecutionProvider`` is actually active (no silent CPU fallback)
  * treats the first inference as HTP-compile warmup, excluded from timing
  * reports the per-layer NPU vs CPU split
  * compares against a CPU baseline so the model-size crossover is visible

Run (native ARM64 Python 3.10-3.12 with onnxruntime-qnn):

    .venv\\Scripts\\python.exe run_npu_ort.py --model mobilenetv2_qdq.onnx --image photo.jpg
    .venv\\Scripts\\python.exe run_npu_ort.py --model mobilenetv2_qdq.onnx --split

Use a REAL photo (e.g. a dog) for correctness checks — a synthetic placeholder
image produces misleading top-k predictions (retrospective §5).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running straight from the samples dir without installing the package.
_SRC = Path(__file__).resolve().parents[2] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402

from quad_mcp_client import ort_qnn  # noqa: E402


def _preprocess(image_path: str | None, shape: tuple[int, int, int, int]) -> np.ndarray:
    """Load + preprocess an image to NCHW float32, or synthesize one."""
    n, c, h, w = shape
    if image_path is None:
        print("[warn] no --image given; using a synthetic input. Top-k predictions "
              "will be meaningless — pass a real photo for correctness checks.")
        return np.random.rand(n, c, h, w).astype(np.float32)

    from PIL import Image

    img = Image.open(image_path).convert("RGB").resize((w, h))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    # ImageNet normalization, NHWC -> NCHW.
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))[np.newaxis, ...]
    return np.ascontiguousarray(arr, dtype=np.float32)


def _bench(session, feeds, runs: int) -> list[float]:
    """Time ``runs`` inferences (warmup already excluded). Returns per-run ms."""
    output_names = [o.name for o in session.get_outputs()]
    times: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        session.run(output_names, feeds)
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


def _summary(times: list[float]) -> str:
    arr = np.array(times)
    return (f"mean {arr.mean():.2f} ms | p50 {np.percentile(arr, 50):.2f} | "
            f"p95 {np.percentile(arr, 95):.2f} | {1000.0 / arr.mean():.0f} FPS")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="Path to a (QDQ INT8) ONNX model")
    ap.add_argument("--image", help="Path to a real input photo (recommended)")
    ap.add_argument("--runs", type=int, default=20, help="Timed inference count")
    ap.add_argument("--cache-dir", help="Persistent HTP context cache directory")
    ap.add_argument("--split", action="store_true", help="Print per-layer NPU/CPU split")
    ap.add_argument("--allow-fallback", action="store_true",
                    help="Permit CPU fallback instead of failing when NPU is inactive")
    args = ap.parse_args()

    if not ort_qnn.native_arm64_python():
        print("[warn] This interpreter is not native ARM64. onnxruntime-qnn wheels "
              "are win-arm64 only and will fail to load NPU support here.")

    # 1. Create the NPU session (verifies QNNExecutionProvider is active).
    try:
        sess = ort_qnn.create_npu_session(
            args.model, allow_fallback=args.allow_fallback, cache_dir=args.cache_dir
        )
    except ort_qnn.NPUFallbackError as e:
        print(f"[error] {e}")
        return 2
    print(f"[ok] Active execution provider: {sess.get_providers()[0]}")

    # 2. Build input + warmup (first-run HTP compile, excluded from timing).
    in_meta = sess.get_inputs()[0]
    shape = tuple(d if isinstance(d, int) and d > 0 else s
                  for d, s in zip(in_meta.shape, (1, 3, 224, 224), strict=False))
    inp = _preprocess(args.image, shape)  # type: ignore[arg-type]
    feeds = {in_meta.name: inp}
    ort_qnn.warmup(sess, feeds, n=1)

    # 3. Benchmark NPU.
    npu_times = _bench(sess, feeds, args.runs)
    print(f"[NPU] {_summary(npu_times)}")

    # 4. CPU baseline (small models often win on CPU — retrospective §8/issue 10).
    import onnxruntime as ort
    cpu_sess = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])
    ort_qnn.warmup(cpu_sess, feeds, n=1)
    cpu_times = _bench(cpu_sess, feeds, args.runs)
    print(f"[CPU] {_summary(cpu_times)}")

    npu_mean = float(np.mean(npu_times))
    cpu_mean = float(np.mean(cpu_times))
    winner = "NPU" if npu_mean < cpu_mean else "CPU"
    print(f"[compare] winner: {winner} "
          f"(NPU {npu_mean:.2f} ms vs CPU {cpu_mean:.2f} ms). "
          f"Small models (<~100M params) may not beat CPU on the NPU — this is "
          f"expected, not a misconfiguration.")

    # 5. Optional per-layer NPU/CPU split.
    if args.split:
        split = ort_qnn.provider_split(args.model, feeds, cache_dir=args.cache_dir)
        s = split["summary"]
        print("\n=== NPU vs CPU Layer Split ===")
        print(f"  Total ops : {s['total_nodes']}")
        print(f"  On NPU    : {s['on_npu']} ({s['npu_percent']}%)")
        print(f"  On CPU    : {s['on_cpu']} ({s['cpu_percent']}%)")
        if "note" in split:
            print(f"  note: {split['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
