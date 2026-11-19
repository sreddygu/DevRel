"""Host-side adb orchestrator: run MobileNetV2 inference on Arduino UNO Q.

Pipeline
--------
  1. Discover adb (PATH or winget install dir)
  2. Verify exactly one device is attached
  3. Preprocess the test image on host (PIL is not on the board)
  4. Push model + .npy input + labels + deploy/inference.py to /data/local/tmp/quad/
  5. Run inference over `adb shell python3 ...`
  6. Print parsed JSON result with a human-friendly latency + top-K table

Why CPU-only: the Arduino UNO Q (QCM2290 / QRB2210) has no /dev/fastrpc
compute path -- the running adsp remoteproc serves audio (q6asm), not
inference. SNPE 2.45 returns QNN_COMMON_ERROR_PLATFORM_NOT_SUPPORTED on
this SoC, and the Adreno GPU is exposed only via Mesa rusticl, which the
SNPE GPU backend does not support. ONNX Runtime CPU is the working path
on this board.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = HERE / "mobilenetv2.onnx"
DEFAULT_IMAGE = HERE / "test_input.jpg"
DEFAULT_LABELS = HERE / "imagenet_classes.txt"
DEFAULT_DEPLOY_SCRIPT = HERE / "deploy" / "inference.py"
HOST_NPY = HERE / "output" / "mobilenetv2_input.npy"

REMOTE_ROOT = "/data/local/tmp/quad"
REMOTE_MODEL = f"{REMOTE_ROOT}/models/mobilenetv2.onnx"
REMOTE_INPUT = f"{REMOTE_ROOT}/inputs/mobilenetv2_input.npy"
REMOTE_LABELS = f"{REMOTE_ROOT}/labels/imagenet_classes.txt"
REMOTE_SCRIPT = f"{REMOTE_ROOT}/apps/mobilenetv2/inference.py"

IMAGENET_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
IMAGENET_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)


@dataclass
class AdbError(RuntimeError):
    message: str

    def __str__(self) -> str:
        return self.message


def find_adb() -> str:
    """Locate adb.exe -- prefer PATH, fall back to winget install dir."""
    on_path = shutil.which("adb") or shutil.which("adb.exe")
    if on_path:
        return on_path
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
    raise AdbError(
        "adb not found. Install with: winget install Google.PlatformTools"
    )


def adb(adb_path: str, *args: str, capture: bool = True) -> str:
    """Run adb. Path-mangling is disabled (MSYS_NO_PATHCONV=1)."""
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    env["MSYS2_ARG_CONV_EXCL"] = "*"
    cmd = [adb_path, *args]
    proc = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise AdbError(
            f"adb {' '.join(args)} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def list_devices(adb_path: str) -> list[str]:
    out = adb(adb_path, "devices")
    serials: list[str] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def require_one_device(adb_path: str) -> str:
    devs = list_devices(adb_path)
    if not devs:
        raise AdbError(
            "No adb devices attached. Plug in the UNO Q and authorize."
        )
    if len(devs) > 1:
        raise AdbError(
            f"Multiple devices attached ({devs}); set ANDROID_SERIAL to pick one."
        )
    return devs[0]


def preprocess_image(image_path: Path, npy_out: Path) -> tuple[int, int]:
    """Load JPEG/PNG, resize 224, ImageNet-normalize, save NCHW float32 .npy."""
    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
    arr = arr.transpose(2, 0, 1)
    arr = np.expand_dims(arr, axis=0)
    npy_out.parent.mkdir(parents=True, exist_ok=True)
    np.save(npy_out, arr)
    return arr.shape, arr.dtype


def push_artifacts(
    adb_path: str,
    *,
    model: Path,
    npy: Path,
    labels: Path,
    script: Path,
) -> None:
    adb(
        adb_path,
        "shell",
        f"mkdir -p {REMOTE_ROOT}/models {REMOTE_ROOT}/inputs "
        f"{REMOTE_ROOT}/labels {REMOTE_ROOT}/apps/mobilenetv2",
    )
    adb(adb_path, "push", str(model), REMOTE_MODEL)
    adb(adb_path, "push", str(npy), REMOTE_INPUT)
    adb(adb_path, "push", str(labels), REMOTE_LABELS)
    adb(adb_path, "push", str(script), REMOTE_SCRIPT)


def run_remote(
    adb_path: str, *, iterations: int, warmup: int, top_k: int
) -> dict:
    cmd = (
        f"python3 {REMOTE_SCRIPT} "
        f"--model {REMOTE_MODEL} "
        f"--input {REMOTE_INPUT} "
        f"--labels {REMOTE_LABELS} "
        f"--iterations {iterations} "
        f"--warmup {warmup} "
        f"--top-k {top_k} "
        f"--json"
    )
    out = adb(adb_path, "shell", cmd)
    json_text = _extract_json(out)
    if json_text is None:
        raise AdbError(f"could not find JSON in remote output:\n{out}")
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
    print("UNO Q on-target benchmark (CPU / ONNX Runtime)")
    print("-" * 50)
    print(f"  model       {result['model']}")
    print(f"  iterations  {result['iterations']} (warmup {result['warmup']})")
    print()
    print(f"  avg latency  {result['avg_ms']:6.1f} ms")
    print(f"  P50 latency  {result['p50_ms']:6.1f} ms")
    print(f"  P99 latency  {result['p99_ms']:6.1f} ms")
    print(f"  throughput   {result['fps']:6.1f} fps")
    if result.get("top_k"):
        print()
        print(f"  top-{len(result['top_k'])} predictions:")
        for rank, p in enumerate(result["top_k"], 1):
            print(
                f"    {rank}. {p['label']:<30} "
                f"{p['prob']*100:5.1f}%  (class {p['class_id']})"
            )
    print()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run MobileNetV2 on Arduino UNO Q over USB (adb)."
    )
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    p.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    p.add_argument("--script", type=Path, default=DEFAULT_DEPLOY_SCRIPT)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--skip-push",
        action="store_true",
        help="Reuse artifacts already on /data/local/tmp/quad/",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON result instead of formatted table",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # The ImageNet-1k labels are a public dataset artifact, not committed to
    # this repo (open-source review) — fetch on demand from PyTorch Hub when
    # the default path is used and the file is absent.
    if args.labels == DEFAULT_LABELS and not args.labels.exists():
        import urllib.request

        url = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
        print(f"labels not present; downloading from {url} ...")
        try:
            urllib.request.urlretrieve(url, args.labels)
        except Exception as exc:  # noqa: BLE001 - surface a clear next step
            print(
                f"[error] could not download labels: {exc}\n"
                f"        fetch manually: curl -L -o {args.labels} {url}",
                file=sys.stderr,
            )
            return 2

    for path, label in [
        (args.model, "model"),
        (args.image, "image"),
        (args.labels, "labels"),
        (args.script, "deploy script"),
    ]:
        if not path.exists():
            print(f"[error] {label} not found: {path}", file=sys.stderr)
            return 2

    try:
        adb_path = find_adb()
        serial = require_one_device(adb_path)
        print(f"adb device: {serial}")

        if not args.skip_push:
            print("preprocessing image on host ...")
            shape, dtype = preprocess_image(args.image, HOST_NPY)
            print(f"  -> {HOST_NPY}  shape={shape}  dtype={dtype}")
            print("pushing artifacts to /data/local/tmp/quad/ ...")
            push_artifacts(
                adb_path,
                model=args.model,
                npy=HOST_NPY,
                labels=args.labels,
                script=args.script,
            )

        print(
            f"running inference on board "
            f"({args.iterations} iterations, warmup {args.warmup}) ..."
        )
        result = run_remote(
            adb_path,
            iterations=args.iterations,
            warmup=args.warmup,
            top_k=args.top_k,
        )
    except AdbError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
