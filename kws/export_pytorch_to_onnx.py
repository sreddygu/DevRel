from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True)
class ExportConfig:
    model_type: str
    sample_rate: int
    clip_samples: int
    n_fft: int
    hop_length: int
    n_mels: int
    fmin: int
    fmax: int
    # librosa uses center=True by default, which yields frames ~= 1 + clip_samples / hop_length
    n_frames: int


class KWSConvNet(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
        )
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        return self.classifier(x)


class DepthwiseSeparableConv2d(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, *, kernel_size: int = 3, stride: int = 1, padding: int = 1):
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_ch,
            in_ch,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            groups=in_ch,
            bias=False,
        )
        self.pointwise = nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        return F.relu(x, inplace=True)


class KWSDscnn(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )
        self.blocks = nn.Sequential(
            DepthwiseSeparableConv2d(64, 64),
            nn.MaxPool2d(kernel_size=2),
            DepthwiseSeparableConv2d(64, 128),
            nn.MaxPool2d(kernel_size=2),
            DepthwiseSeparableConv2d(128, 128),
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.blocks(x)
        return self.head(x)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export the notebook's PyTorch KWS checkpoint (.pt) to ONNX + a small JSON config.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--pt", type=Path, default=Path("output/pytorch_kws_model.pt"), help="Input .pt checkpoint path.")
    p.add_argument(
        "--labels",
        type=Path,
        default=Path("output/pytorch_kws_labels.json"),
        help="Labels JSON path (used only to infer num_classes).",
    )
    p.add_argument("--onnx", type=Path, default=Path("output/pytorch_kws_model.onnx"), help="Output ONNX path.")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("output/pytorch_kws_config.json"),
        help="Output config JSON path (feature/model metadata for non-torch runtimes).",
    )
    p.add_argument("--opset", type=int, default=17, help="ONNX opset version.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.pt.exists():
        raise FileNotFoundError(f"Missing: {args.pt.resolve()}")
    if not args.labels.exists():
        raise FileNotFoundError(f"Missing: {args.labels.resolve()}")

    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    num_classes = len(labels)

    ckpt = torch.load(args.pt, map_location="cpu")
    model_type = str(ckpt.get("model_type", "KWSDscnn"))

    if model_type == "KWSConvNet":
        model: nn.Module = KWSConvNet(num_classes)
    elif model_type == "KWSDscnn":
        model = KWSDscnn(num_classes)
    else:
        raise ValueError(f"Unknown model_type in checkpoint: {model_type}")

    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    hop_length = int(ckpt["hop_length"])
    clip_samples = int(ckpt["clip_samples"])
    n_mels = int(ckpt["n_mels"])
    # With librosa center=True (default), frames ~= 1 + clip_samples / hop_length.
    n_frames = 1 + (clip_samples // hop_length)

    cfg = ExportConfig(
        model_type=model_type,
        sample_rate=int(ckpt["sample_rate"]),
        clip_samples=clip_samples,
        n_fft=int(ckpt["n_fft"]),
        hop_length=hop_length,
        n_mels=n_mels,
        fmin=int(ckpt["fmin"]),
        fmax=int(ckpt["fmax"]),
        n_frames=n_frames,
    )

    args.onnx.parent.mkdir(parents=True, exist_ok=True)
    args.config.parent.mkdir(parents=True, exist_ok=True)

    dummy = torch.randn(1, 1, n_mels, n_frames, dtype=torch.float32)

    torch.onnx.export(
        model,
        dummy,
        args.onnx.as_posix(),
        input_names=["x"],
        output_names=["logits"],
        opset_version=int(args.opset),
        dynamo=False,
        dynamic_axes={"x": {0: "batch"}, "logits": {0: "batch"}},
    )

    args.config.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")

    print("wrote", args.onnx)
    print("wrote", args.config)


if __name__ == "__main__":
    main()
