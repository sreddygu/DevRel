"""Host-side orchestrator: run MobileNetV2 inference on the Dragonwing
IQ-9075 EVK (QCS9075), over either adb (USB) or SSH (Wi-Fi/Ethernet).

Pipeline
--------
  1. Preprocess the test image on host (PIL is not on the board)
  2. Push model + .npy input + labels + deploy/inference.py to the board's
     workspace via individual file transfers (`adb push` or `scp`)
  3. Run deploy/inference.py on-device (`adb shell python3 ...` or `ssh ... python3 ...`)
  4. Print parsed JSON result: CPU (real numbers), NPU/GPU via the
     onnxruntime_qnn plugin EP (attempted, documented blocker if it
     fails), and optionally a genuine NPU pass via a pre-compiled QNN
     context binary through qnn-net-run (see --qnn-context-bin)

Two transports, one board, two verified histories
--------------------------------------------------
This board was originally bring-up'd over **adb** (USB-C, the only
Windows-reachable interface on the factory QLI 1.6 image -- DIAG/QDSS
have no Windows driver). After a reflash to **QLI 2.0**, the board was
reconnected over **Wi-Fi + SSH** instead -- a materially different
environment (writable rootfs, internet access, pip, newer QAIRT). Both
transports are real and supported here; `--transport` picks one
(default `ssh`, since that's how this board is reachable post-reflash --
pass `--transport adb` if you're back on a QLI-1.6-era image over USB).

Why this doesn't hand-roll a directory-tree push: `adb push` of a
*directory* on this board's (QLI 1.6) adb client is known to crash
silently (`libc++abi: ... std::bad_alloc`, exit 0, zero files
transferred -- see docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md).
This script never pushes a directory over either transport -- only
individual files (model, .npy, labels, script), one push call each. For
anything that genuinely needs a directory tree (e.g. installing
onnxruntime itself on a QLI-1.6-era image, done once as a one-time
on-device setup step -- see README.md), tar it first and extract with
`tar` on the device instead of `push -r`.

`scripts/board_profile.py`'s `python_path_extra` convention (an
on-device PYTHONPATH entry for a manually-installed onnxruntime, since
a QLI-1.6-era /usr is read-only and there's no pip/ensurepip there) is
reused directly via --python-path-extra below, so this app and
`board_profile.py` agree on where onnxruntime lives on a QLI-1.6-era
board. On a QLI 2.0 board (writable rootfs + internet), `pip3 install
onnxruntime onnxruntime-qnn` works directly and --python-path-extra ""
is the right choice.

NPU/GPU status (verified live, not assumed -- see
docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md for the full
history and caveats):
  - onnxruntime_qnn plugin-EP path (what --model alone exercises):
    still blocked on QLI 2.0 too -- onnxruntime's Linux device-discovery
    code doesn't recognize this board's Hexagon NPU exposure
    (/dev/fastrpc-*, not a DRM GPU node with a `vendor` file). Same root
    cause, unaffected by the QAIRT version bump.
  - qnn-net-run + pre-compiled context-binary path (--qnn-context-bin):
    WORKS on QLI 2.0 (QAIRT 2.47.0) -- the QAIRT compiler-version wall
    that rejected AI-Hub-compiled binaries on the original QLI 1.6 image
    (QAIRT 2.38.0, AI Hub compiles for >=2.45) no longer applies now
    that the board's own QAIRT is >=2.45. Verified live: 2.5-2.7ms mean
    latency over 50 inferences on Hexagon HTP v73, using the exact
    context binary that was previously rejected on the QLI 1.6 image.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from quad_mcp_client.local.board.ssh import SSHTarget  # noqa: E402
from quad_mcp_client.local.board.ssh import push_file as ssh_push_file
from quad_mcp_client.local.board.ssh import run_remote as ssh_run_remote

DEFAULT_MODEL = HERE / "mobilenetv2.onnx"
DEFAULT_IMAGE = HERE / "test_input.jpg"
DEFAULT_LABELS = HERE / "imagenet_classes.txt"
DEFAULT_DEPLOY_SCRIPT = HERE / "deploy" / "inference.py"
HOST_NPY = HERE / "output" / "mobilenetv2_input.npy"
HOST_NHWC_RAW = HERE / "output" / "mobilenetv2_input_nhwc.raw"

REMOTE_WORKSPACE = "/data/local/tmp/quad/"
REMOTE_MODEL = f"{REMOTE_WORKSPACE}models/mobilenetv2.onnx"
REMOTE_INPUT = f"{REMOTE_WORKSPACE}inputs/mobilenetv2_input.npy"
REMOTE_NHWC_RAW = f"{REMOTE_WORKSPACE}inputs/mobilenetv2_input_nhwc.raw"
REMOTE_LABELS = f"{REMOTE_WORKSPACE}labels/imagenet_classes.txt"
REMOTE_SCRIPT = f"{REMOTE_WORKSPACE}apps/mobilenetv2_iq9075/inference.py"

IMAGENET_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
IMAGENET_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)


class BoardError(RuntimeError):
    pass


# ─────────────────────────────────────────────────────────────────────────
# Transport abstraction -- adb (USB) or ssh (Wi-Fi/Ethernet), one board
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class BoardTarget:
    transport: str  # "adb" | "ssh"
    adb_path: str | None = None
    serial: str | None = None
    ssh: SSHTarget | None = None


def find_adb() -> str:
    """Locate adb.exe -- prefer PATH, fall back to the winget install dir."""
    on_path = shutil.which("adb") or shutil.which("adb.exe")
    if on_path:
        return on_path
    import os

    winget = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "platform-tools"
        / "adb.exe"
    )
    if winget.exists():
        return str(winget)
    raise BoardError(
        "adb not found. Install with: winget install Google.PlatformTools"
    )


def _adb(adb_path: str, *args: str) -> str:
    import os

    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    env["MSYS2_ARG_CONV_EXCL"] = "*"
    proc = subprocess.run(
        [adb_path, *args], capture_output=True, text=True, env=env, check=False
    )
    if proc.returncode != 0:
        raise BoardError(
            f"adb {' '.join(args)} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def list_devices(adb_path: str) -> list[str]:
    out = _adb(adb_path, "devices")
    serials: list[str] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def resolve_serial(adb_path: str, requested: str | None) -> str:
    if requested and requested != "auto":
        return requested
    devs = list_devices(adb_path)
    if not devs:
        raise BoardError("No adb devices attached. Plug in the IQ-9075 and confirm `adb devices` lists it.")
    if len(devs) > 1:
        raise BoardError(f"Multiple devices attached ({devs}); pass --serial to pick one.")
    return devs[0]


def resolve_target(args: argparse.Namespace) -> BoardTarget:
    if args.transport == "adb":
        adb_path = find_adb()
        serial = resolve_serial(adb_path, args.serial)
        return BoardTarget(transport="adb", adb_path=adb_path, serial=serial)

    if args.transport == "ssh":
        if not args.host:
            raise BoardError("--transport ssh requires --host <ip-or-hostname>")
        key = Path(args.key) if args.key else None
        target = SSHTarget(host=args.host, user=args.user, port=args.port, key=key)
        return BoardTarget(transport="ssh", ssh=target)

    raise BoardError(f"unknown transport {args.transport!r} (expected 'adb' or 'ssh')")


def shell(target: BoardTarget, cmd: str, *, timeout_s: int = 60) -> str:
    if target.transport == "adb":
        return _adb(target.adb_path, "-s", target.serial, "shell", cmd)
    result = ssh_run_remote(target.ssh, cmd, timeout_s=timeout_s)
    if not result.ok:
        raise BoardError(f"ssh command failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def push(target: BoardTarget, src: Path, dst: str) -> None:
    if target.transport == "adb":
        _adb(target.adb_path, "-s", target.serial, "push", str(src), dst)
        return
    result = ssh_push_file(target.ssh, src, dst)
    if not result.ok:
        raise BoardError(f"scp push failed (exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}")


def describe(target: BoardTarget) -> str:
    if target.transport == "adb":
        return f"adb device: {target.serial}"
    return f"ssh target: {target.ssh.user}@{target.ssh.host}:{target.ssh.port}"


def preprocess_image(image_path: Path, npy_out: Path, nhwc_raw_out: Path | None = None) -> tuple[tuple, np.dtype]:
    """Load JPEG/PNG, resize 224. Saves two formats:
    - NCHW float32 ImageNet-normalized .npy (for the CPU/onnxruntime_qnn paths)
    - NHWC float32 [0,1]-range raw tensor (for --qnn-context-bin, matching the
      AI-Hub-exported context binary's declared input contract, see
      export_assets/mobilenet_v2_iq9075_qnn/mobilenet_v2-qnn_context_binary-float-qualcomm_qcs9075/metadata.json)
    """
    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr_uint8 = np.array(img, dtype=np.float32)

    arr = (arr_uint8 - IMAGENET_MEAN) / IMAGENET_STD
    arr = arr.transpose(2, 0, 1)
    arr = np.expand_dims(arr, axis=0)
    npy_out.parent.mkdir(parents=True, exist_ok=True)
    np.save(npy_out, arr)

    if nhwc_raw_out is not None:
        nhwc = (arr_uint8 / 255.0)[np.newaxis, ...].astype(np.float32)
        nhwc_raw_out.parent.mkdir(parents=True, exist_ok=True)
        nhwc.tofile(nhwc_raw_out)

    return arr.shape, arr.dtype


def push_artifacts(
    target: BoardTarget, *, model: Path, npy: Path, labels: Path, script: Path,
    nhwc_raw: Path | None = None, qnn_context_bin: Path | None = None,
) -> None:
    dirs = f"{REMOTE_WORKSPACE}models {REMOTE_WORKSPACE}inputs {REMOTE_WORKSPACE}labels {REMOTE_WORKSPACE}apps/mobilenetv2_iq9075"
    shell(target, f"mkdir -p {dirs}")
    push(target, model, REMOTE_MODEL)
    push(target, npy, REMOTE_INPUT)
    push(target, labels, REMOTE_LABELS)
    push(target, script, REMOTE_SCRIPT)
    if nhwc_raw is not None:
        push(target, nhwc_raw, REMOTE_NHWC_RAW)
    if qnn_context_bin is not None:
        remote_bin = f"{REMOTE_WORKSPACE}models/{qnn_context_bin.name}"
        push(target, qnn_context_bin, remote_bin)


def run_remote(
    target: BoardTarget, *, iterations: int, warmup: int, top_k: int, cpu_only: bool,
    python_path_extra: str, qnn_context_bin: Path | None, qnn_backend_lib: str,
) -> dict:
    py_prefix = f"PYTHONPATH={python_path_extra} " if python_path_extra else ""
    qnn_args = ""
    if qnn_context_bin is not None:
        remote_bin = f"{REMOTE_WORKSPACE}models/{qnn_context_bin.name}"
        qnn_args = (
            f"--qnn-context-bin {remote_bin} "
            f"--qnn-backend-lib {qnn_backend_lib} "
            f"--qnn-raw-input {REMOTE_NHWC_RAW} "
        )
    cmd = (
        f"{py_prefix}python3 {REMOTE_SCRIPT} "
        f"--model {REMOTE_MODEL} "
        f"--input {REMOTE_INPUT} "
        f"--labels {REMOTE_LABELS} "
        f"--iterations {iterations} "
        f"--warmup {warmup} "
        f"--top-k {top_k} "
        f"{'--cpu-only ' if cpu_only else ''}"
        f"{qnn_args}"
        f"--json"
    )
    out = shell(target, cmd, timeout_s=120)
    json_text = _extract_json(out)
    if json_text is None:
        raise BoardError(f"could not find JSON in remote output:\n{out}")
    return json.loads(json_text)


def _extract_json(text: str) -> str | None:
    """Pull the last {...} block out of mixed stdout (ORT prints warnings)."""
    depth = 0
    start = -1
    last_block: str | None = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                last_block = text[start : i + 1]
    return last_block


def print_result(result: dict) -> None:
    print()
    print("IQ-9075 on-target benchmark (CPU real; NPU/GPU attempted)")
    print("-" * 60)
    print(f"  model       {result['model']}")
    print(f"  iterations  {result['iterations']} (warmup {result['warmup']})")
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
            print("  status      : NOT AVAILABLE (known, documented limitation -- not a crash)")
            print(f"  reason      : {r.get('error', 'unknown')}")
        print()
    if result.get("top_k"):
        print(f"  top-{len(result['top_k'])} predictions (from CPU backend):")
        for rank, p in enumerate(result["top_k"], 1):
            print(
                f"    {rank}. {p['label']:<30} "
                f"{p['prob']*100:5.1f}%  (class {p['class_id']})"
            )
    print()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run MobileNetV2 on the Dragonwing IQ-9075 EVK over adb (USB) or ssh (Wi-Fi/Ethernet)."
    )
    p.add_argument("--transport", choices=["adb", "ssh"], default="ssh", help="Transport to reach the board (default: ssh)")
    p.add_argument("--serial", default="auto", help="[adb] device serial, or 'auto' for the single attached device")
    p.add_argument("--host", default=None, help="[ssh] board hostname or IP")
    p.add_argument("--user", default="root", help="[ssh] login user (default: root)")
    p.add_argument("--port", type=int, default=22, help="[ssh] port (default: 22)")
    p.add_argument("--key", default=None, help="[ssh] path to a private key (default: use ssh-agent/default keys)")
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    p.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    p.add_argument("--script", type=Path, default=DEFAULT_DEPLOY_SCRIPT)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--python-path-extra",
        default="",
        help="On-device PYTHONPATH entry for a manually-installed onnxruntime -- "
        "needed on a QLI-1.6-era image (/usr read-only, no pip; try "
        "/data/local/tmp/quad/pylibs). Leave empty (default) on a QLI 2.0+ "
        "image where `pip3 install onnxruntime onnxruntime-qnn` was used instead.",
    )
    p.add_argument("--cpu-only", action="store_true", help="Skip the NPU/GPU attempt entirely")
    p.add_argument(
        "--qnn-context-bin",
        type=Path,
        default=None,
        help="Path to a pre-compiled QNN context binary (.bin) on the HOST -- "
        "when supplied, pushes it to the board and attempts a genuine NPU "
        "pass via qnn-net-run (works when the board's on-device QAIRT "
        "version is >= the version this binary was compiled for -- check "
        "with `qnn-net-run --version` on-device; see "
        "docs/debugging/8. NPU_Profiling_MobileNetV2_IQ9075.md)",
    )
    p.add_argument(
        "--qnn-backend-lib",
        default="/usr/lib/libQnnHtp.so",
        help="On-device QNN backend library path for --qnn-context-bin (default: HTP/NPU)",
    )
    p.add_argument(
        "--skip-push",
        action="store_true",
        help="Reuse artifacts already pushed to the board's workspace",
    )
    p.add_argument("--json", action="store_true", help="Emit raw JSON result instead of a formatted table")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    for path, label in [
        (args.model, "model"),
        (args.image, "image"),
        (args.labels, "labels"),
        (args.script, "deploy script"),
    ]:
        if not path.exists():
            print(f"[error] {label} not found: {path}", file=sys.stderr)
            return 2
    if args.qnn_context_bin is not None and not args.qnn_context_bin.exists():
        print(f"[error] qnn context binary not found: {args.qnn_context_bin}", file=sys.stderr)
        return 2

    try:
        target = resolve_target(args)
        print(describe(target))

        if not args.skip_push:
            print("preprocessing image on host ...")
            shape, dtype = preprocess_image(args.image, HOST_NPY, HOST_NHWC_RAW)
            print(f"  -> {HOST_NPY}  shape={shape}  dtype={dtype}")
            if args.qnn_context_bin is not None:
                print(f"  -> {HOST_NHWC_RAW}  (NHWC [0,1] raw, for --qnn-context-bin)")
            print("pushing artifacts to the board's workspace ...")
            push_artifacts(
                target,
                model=args.model, npy=HOST_NPY, labels=args.labels, script=args.script,
                nhwc_raw=HOST_NHWC_RAW if args.qnn_context_bin is not None else None,
                qnn_context_bin=args.qnn_context_bin,
            )

        print(
            f"running inference on board "
            f"({args.iterations} iterations, warmup {args.warmup}) ..."
        )
        result = run_remote(
            target,
            iterations=args.iterations, warmup=args.warmup, top_k=args.top_k,
            cpu_only=args.cpu_only, python_path_extra=args.python_path_extra,
            qnn_context_bin=args.qnn_context_bin, qnn_backend_lib=args.qnn_backend_lib,
        )
    except BoardError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
