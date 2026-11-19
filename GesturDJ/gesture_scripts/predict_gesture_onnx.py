from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from gesture_io import load_labels, load_series
from gesture_preprocess import GesturePreprocessConfig, preprocess_series, softmax_np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Predict a gesture label using ONNX Runtime (no PyTorch required).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output_dir", default="outputs", help="Folder containing ONNX + config + labels.")
    p.add_argument("--input", required=True, help="CSV or NPY file to classify")
    p.add_argument("--topk", type=int, default=3, help="Print top-k predictions.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.output_dir)

    onnx_path = out / "gesture_model.onnx"
    cfg_path = out / "gesture_config.json"
    labels_path = out / "gesture_labels.json"

    if not onnx_path.exists():
        raise FileNotFoundError(f"Missing ONNX file: {onnx_path.resolve()}")
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config file: {cfg_path.resolve()}")
    if not labels_path.exists():
        raise FileNotFoundError(f"Missing labels file: {labels_path.resolve()}")

    try:
        import onnxruntime as ort  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(f"Missing dependency: onnxruntime ({e})")

    labels = load_labels(labels_path)
    cfg_raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg = GesturePreprocessConfig(
        resample_len=int(cfg_raw["resample_len"]),
        mean=tuple(float(x) for x in cfg_raw["mean"]),
        std=tuple(float(x) for x in cfg_raw["std"]),
    )

    series = load_series(args.input)
    x = preprocess_series(series, cfg)[np.newaxis, :, :]  # [1,3,T]

    sess = ort.InferenceSession(onnx_path.as_posix(), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    logits = sess.run(None, {input_name: x.astype(np.float32)})[0][0]
    probs = softmax_np(logits)

    topk = int(args.topk)
    topk = max(1, min(topk, probs.shape[0]))
    idxs = np.argsort(-probs)[:topk]
    for i in idxs:
        print(f"{labels[int(i)]}\t{float(probs[int(i)]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

