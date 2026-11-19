"""MobileNetV2 inference on Arduino UNO Q (QCM2290) via ONNX Runtime CPU.

Runs on-device. Preprocessing happens on the host (PIL is not on the
board); this script consumes a pre-built float32 NCHW .npy tensor and
prints latency stats plus top-K predictions.

Falls back to a random input when --input is omitted, useful for
end-to-end smoke testing without needing a real image transferred.

Why CPU only on this board: QCM2290 / QRB2210 lacks a /dev/fastrpc
compute path (the running adsp remoteproc is the audio DSP) and the
Adreno GPU is exposed only via Mesa rusticl, not the Qualcomm OpenCL
driver SNPE expects. SNPE 2.45 returns
QNN_COMMON_ERROR_PLATFORM_NOT_SUPPORTED for every backend on this SKU.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

INPUT_SHAPE = (1, 3, 224, 224)


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


def run_inference(
    model_path: str,
    input_path: str | None,
    *,
    iterations: int = 10,
    warmup: int = 3,
    k: int = 5,
    labels: list[str] | None = None,
) -> dict:
    sess = ort.InferenceSession(
        model_path, providers=["CPUExecutionProvider"]
    )
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name

    inp = load_input(input_path)

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

    avg = sum(latencies) / len(latencies)
    p50 = percentile(latencies, 50)
    p99 = percentile(latencies, 99)
    fps = 1000.0 / avg if avg > 0 else 0.0

    predictions = topk(last_logits, k) if last_logits is not None else []
    labels = labels or []
    named = [
        (idx, prob, labels[idx] if 0 <= idx < len(labels) else f"class_{idx}")
        for idx, prob in predictions
    ]

    return {
        "model": model_path,
        "input": input_path or "<random>",
        "iterations": iterations,
        "warmup": warmup,
        "avg_ms": avg,
        "p50_ms": p50,
        "p99_ms": p99,
        "fps": fps,
        "top_k": [
            {"class_id": i, "prob": p, "label": n} for (i, p, n) in named
        ],
    }


def _print_human(result: dict) -> None:
    print(f"Model       : {result['model']}")
    print(f"Input       : {result['input']}")
    print(
        f"Iterations  : {result['iterations']} "
        f"(warmup {result['warmup']})"
    )
    print()
    print("Latency:")
    print(f"  avg : {result['avg_ms']:6.1f} ms")
    print(f"  P50 : {result['p50_ms']:6.1f} ms")
    print(f"  P99 : {result['p99_ms']:6.1f} ms")
    print(f"  fps : {result['fps']:6.1f}")
    print()
    if result["top_k"]:
        print(f"Top-{len(result['top_k'])} predictions:")
        for rank, p in enumerate(result["top_k"], 1):
            print(
                f"  {rank}. {p['label']:<30} {p['prob']*100:5.1f}% "
                f"(class {p['class_id']})"
            )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MobileNetV2 ONNX Runtime CPU inference on UNO Q."
    )
    p.add_argument(
        "--model",
        default="/data/local/tmp/quad/models/mobilenetv2.onnx",
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
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
