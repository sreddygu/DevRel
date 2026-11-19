"""
Run INT8 MobileNetV2 inference on Snapdragon X Elite (Windows AI PC).

This script tests a converted QNN context binary (.bin) or SNPE DLC (.dlc)
on the local device using the QNN SDK's Python bindings.

Prerequisites
-------------
1. QNN / QAIRT SDK installed (tested with QAIRT 2.x):
       C:\\Qualcomm\\AIStack\\QAIRT\\<version>\\

2. SDK Python bindings on sys.path:
       set QNN_SDK_ROOT=C:\\Qualcomm\\AIStack\\QAIRT\\<version>
       set PYTHONPATH=%QNN_SDK_ROOT%\\lib\\python;%PYTHONPATH%

3. Converted model file produced by convert_int8.py:
       output\\mobilenetv2_int8.bin   (QNN context binary)
       — or —
       output\\mobilenetv2_int8.dlc   (SNPE DLC)

4. A test image (JPEG / PNG, any size — script resizes to 224×224).

5. ImageNet class labels (optional, for human-readable top-5 output):
       curl -L -o imagenet_classes.txt \\
           https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt

Usage
-----
    python test_target.py --model output/mobilenetv2_int8.bin --image cat.jpg

For SNPE DLC:
    python test_target.py --model output/mobilenetv2_int8.dlc --image cat.jpg --sdk snpe
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess(image_path: str, *, mean: list[float], std: list[float]) -> np.ndarray:
    """Load, resize, normalise, and return a (1, 3, 224, 224) float32 array (NCHW)."""
    import numpy as np
    from PIL import Image  # type: ignore[import-untyped]

    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32)          # (224, 224, 3)  NHWC
    arr = (arr - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
    arr = arr.transpose(2, 0, 1)                   # (3, 224, 224)  NCHW
    arr = np.expand_dims(arr, axis=0)              # (1, 3, 224, 224)
    return arr


# ---------------------------------------------------------------------------
# QNN inference (context binary .bin via libQnnHtp.so / QnnHtp.dll)
# ---------------------------------------------------------------------------

def run_qnn(model_path: str, input_data: np.ndarray) -> np.ndarray:
    """
    Run inference using QNN SDK Python bindings (qnn_wrapper_api).

    The QNN SDK ships a thin Python wrapper for executing context binaries.
    It is located at:
        $QNN_SDK_ROOT/lib/python/qnn_wrapper_api/

    QNN requires NHWC input when the graph was compiled with
    --input_layout NHWC.  MobileNetV2 from the ONNX Model Zoo is NCHW —
    DevRel records the required transpose in image_format_notes.
    Transpose here before passing to the runtime.
    """

    try:
        from qnn_wrapper_api import QnnBackend, QnnContext  # type: ignore[import-untyped]
    except ImportError:
        _qnn_import_error()

    # QNN HTP (NPU) backend on Snapdragon X Elite
    backend = QnnBackend.HTP

    print("  Backend  : QNN HTP (Hexagon NPU)")
    print(f"  Model    : {model_path}")

    ctx = QnnContext(model_path, backend=backend)
    ctx.load()

    # MobileNetV2 ONNX is NCHW; QNN compiled from NCHW ONNX expects NCHW input.
    # If DevRel inserted an NHWC transpose during conversion, swap here.
    # Check the image_format_notes output of convert_int8.py.
    inp = input_data  # shape: (1, 3, 224, 224)

    t0 = time.perf_counter()
    outputs = ctx.execute({"input": inp})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print(f"  Latency  : {elapsed_ms:.1f} ms  (first-inference — includes HTP init overhead)")
    ctx.unload()

    # output shape: (1, 1000)
    return outputs["output"], elapsed_ms


# ---------------------------------------------------------------------------
# SNPE inference (.dlc)
# ---------------------------------------------------------------------------

def run_snpe(model_path: str, input_data: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Run inference using the SNPE Python bindings (snpe-python-utils).

    The SNPE SDK ships Python utilities at:
        $SNPE_ROOT/lib/python/

    SNPE requires NHWC input; transpose from NCHW before running.
    """

    try:
        from snpe import snpe_utils  # type: ignore[import-untyped]
    except ImportError:
        _snpe_import_error()

    # Transpose NCHW → NHWC for SNPE
    inp_nhwc = input_data.transpose(0, 2, 3, 1)   # (1, 224, 224, 3)

    print("  Backend  : SNPE DSP (Hexagon NPU)")
    print(f"  Model    : {model_path}")

    runner = snpe_utils.SNPERunner(model_path, runtime="dsp")
    runner.load()

    t0 = time.perf_counter()
    outputs = runner.execute({"input_1:0": inp_nhwc})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print(f"  Latency  : {elapsed_ms:.1f} ms")
    runner.unload()

    return outputs["MobilenetV2/Predictions/Reshape_1:0"], elapsed_ms


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def topk(logits: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
    import numpy as np
    scores = logits.flatten()
    # Apply softmax
    scores = scores - scores.max()
    exp = np.exp(scores)
    probs = exp / exp.sum()
    indices = np.argsort(probs)[::-1][:k]
    return [(int(i), float(probs[i])) for i in indices]


def load_labels(path: str | None) -> dict[int, str]:
    if path is None or not Path(path).exists():
        return {}
    lines = Path(path).read_text().splitlines()
    return {i: line.strip() for i, line in enumerate(lines)}


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

def _qnn_import_error() -> None:
    print("[error] QNN Python bindings not found.")
    print()
    print("  1. Install QAIRT SDK:")
    print("       https://qpm.qualcomm.com  →  AI Stack → QAIRT")
    print()
    print("  2. Add bindings to PYTHONPATH (PowerShell):")
    print("       $env:QNN_SDK_ROOT = 'C:\\Qualcomm\\AIStack\\QAIRT\\<version>'")
    print("       $env:PYTHONPATH   = \"$env:QNN_SDK_ROOT\\lib\\python;$env:PYTHONPATH\"")
    print()
    print("  3. Verify:  python -c \"from qnn_wrapper_api import QnnContext\"")
    sys.exit(1)


def _snpe_import_error() -> None:
    print("[error] SNPE Python bindings not found.")
    print()
    print("  1. Install SNPE SDK:")
    print("       https://qpm.qualcomm.com  →  AI Stack → SNPE")
    print()
    print("  2. Add bindings to PYTHONPATH (PowerShell):")
    print("       $env:SNPE_ROOT   = 'C:\\Qualcomm\\AIStack\\SNPE\\<version>'")
    print("       $env:PYTHONPATH  = \"$env:SNPE_ROOT\\lib\\python;$env:PYTHONPATH\"")
    print()
    print("  3. Verify:  python -c \"from snpe import snpe_utils\"")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Test INT8 MobileNetV2 on Snapdragon X Elite (QNN or SNPE)."
    )
    p.add_argument("--model", required=True,
                   help="Path to the converted model (.bin for QNN, .dlc for SNPE)")
    p.add_argument("--image", required=True,
                   help="Path to a test image (JPEG / PNG)")
    p.add_argument("--sdk", default="auto", choices=["auto", "qnn", "snpe"],
                   help="Which SDK to use. 'auto' picks by file extension (default: auto)")
    p.add_argument("--labels", default="imagenet_classes.txt",
                   help="Path to ImageNet class label file (optional)")
    p.add_argument("--top-k", type=int, default=5,
                   help="Number of top predictions to display (default: 5)")
    # ImageNet mean / std matching what convert_int8.py used
    p.add_argument("--mean", nargs=3, type=float, default=[123.675, 116.28, 103.53],
                   metavar=("R", "G", "B"),
                   help="Per-channel mean for normalisation (default: ImageNet)")
    p.add_argument("--std",  nargs=3, type=float, default=[58.395, 57.12, 57.375],
                   metavar=("R", "G", "B"),
                   help="Per-channel std for normalisation (default: ImageNet)")
    p.add_argument("--warmup", type=int, default=3,
                   help="Number of warmup runs before measuring latency (default: 3)")
    p.add_argument("--runs", type=int, default=10,
                   help="Number of timed inference runs for average latency (default: 10)")
    return p.parse_args()


def main() -> None:
    import numpy as np

    args = _parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"[error] Model file not found: {model_path}")
        print("  Run convert_int8.py first to generate the model.")
        sys.exit(1)

    if not Path(args.image).exists():
        print(f"[error] Image not found: {args.image}")
        sys.exit(1)

    # Auto-detect SDK from extension
    sdk = args.sdk
    if sdk == "auto":
        sdk = "snpe" if model_path.suffix.lower() == ".dlc" else "qnn"

    print("MobileNetV2 INT8 — target inference test")
    print(f"  Image    : {args.image}")
    print(f"  SDK      : {sdk.upper()}")
    print()

    # Preprocess
    inp = preprocess(args.image, mean=args.mean, std=args.std)

    # Warmup + timed runs
    print(f"Warmup ({args.warmup} run(s)) …")
    for _ in range(args.warmup):
        if sdk == "qnn":
            logits, _ = run_qnn(str(model_path), inp)
        else:
            logits, _ = run_snpe(str(model_path), inp)

    print(f"\nTimed run ({args.runs} iteration(s)) …")
    times: list[float] = []
    for i in range(args.runs):
        if sdk == "qnn":
            logits, ms = run_qnn(str(model_path), inp)
        else:
            logits, ms = run_snpe(str(model_path), inp)
        times.append(ms)
        print(f"  run {i+1:>2}: {ms:.1f} ms")

    avg_ms   = float(np.mean(times))
    p95_ms   = float(np.percentile(times, 95))
    min_ms   = float(np.min(times))

    print()
    print(f"Latency summary ({args.runs} runs):")
    print(f"  Average : {avg_ms:.1f} ms  ({1000/avg_ms:.0f} FPS)")
    print(f"  Min     : {min_ms:.1f} ms")
    print(f"  P95     : {p95_ms:.1f} ms")
    print()

    # Top-K predictions
    predictions = topk(logits, k=args.top_k)
    labels = load_labels(args.labels)

    print(f"Top-{args.top_k} predictions:")
    for rank, (class_id, prob) in enumerate(predictions, 1):
        label = labels.get(class_id, f"class_{class_id}")
        print(f"  {rank}. {label:<30} {prob*100:5.1f}%")


if __name__ == "__main__":
    main()
