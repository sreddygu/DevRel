from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

from gesture_pytorch_model import GestureConvNet


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export the PyTorch gesture checkpoint (.pt) to ONNX (plus config/labels for ONNX Runtime).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--pt", type=Path, default=Path("outputs/gesture_model.pt"), help="Input .pt checkpoint path.")
    p.add_argument("--labels", type=Path, default=Path("outputs/gesture_labels.json"), help="Labels JSON path.")
    p.add_argument("--config", type=Path, default=Path("outputs/gesture_config.json"), help="Config JSON path.")
    p.add_argument("--onnx", type=Path, default=Path("outputs/gesture_model.onnx"), help="Output ONNX path.")
    p.add_argument("--opset", type=int, default=17, help="ONNX opset version.")
    return p.parse_args()


def main() -> None:
    # Newer PyTorch prints non-ASCII symbols while exporting; a redirected Windows console (cp1252) would crash on them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    if not args.pt.exists():
        raise FileNotFoundError(f"Missing: {args.pt.resolve()}")
    if not args.labels.exists():
        raise FileNotFoundError(f"Missing: {args.labels.resolve()}")
    if not args.config.exists():
        raise FileNotFoundError(f"Missing: {args.config.resolve()}")

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    num_classes = len(labels)

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    resample_len = int(cfg["resample_len"])

    ckpt = torch.load(args.pt, map_location="cpu")
    model_type = str(ckpt.get("model_type", "GestureConvNet"))
    if model_type != "GestureConvNet":
        raise ValueError(f"Unsupported model_type: {model_type}")

    model = GestureConvNet(num_classes=num_classes)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    args.onnx.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 3, resample_len, dtype=torch.float32)

    torch.onnx.export(
        model,
        dummy,
        args.onnx.as_posix(),
        input_names=["x"],
        output_names=["logits"],
        opset_version=int(args.opset),
        dynamic_axes={"x": {0: "batch"}, "logits": {0: "batch"}},
    )

    # Newer PyTorch writes the weights to a separate "<name>.onnx.data" file. Copying only the .onnx to a board then
    # fails at load time, so embed the weights (the model is small) and remove the side file.
    import onnx

    onnx.save_model(onnx.load(args.onnx.as_posix()), args.onnx.as_posix(), save_as_external_data=False)
    side_file = args.onnx.with_name(args.onnx.name + ".data")
    if side_file.exists():
        side_file.unlink()

    print("wrote", args.onnx)
    print("using labels", args.labels)
    print("using config", args.config)


if __name__ == "__main__":
    main()

