#!/usr/bin/env python3
"""
Export the KWSDscnn ONNX and then run the SNPE converter.
"""

import argparse
import os
import subprocess
from pathlib import Path

import torch

from train_wakeword import KWSDscnn


def export_onnx(onnx_path: Path, num_classes: int = 3) -> None:
    model = KWSDscnn(num_classes=num_classes)
    model.eval()
    dummy = torch.zeros(1, 1, 40, 101)
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        opset_version=17,
        input_names=["x"],
        output_names=["logits"],
        dynamic_axes={"x": {0: "batch"}},
        keep_initializers_as_inputs=True,
    )
    print("exported ONNX:", onnx_path)


def run_converter(qa_path: Path, onnx_path: Path, dlc_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(qa_path / "lib" / "python")
    env["PATH"] = (
        f"{qa_path / 'bin' / 'x86_64-windows-msvc'};"
        f"{qa_path / 'lib' / 'x86_64-windows-msvc'};"
        + env.get("PATH", "")
    )
    cmd = [
        str(qa_path / "bin" / "x86_64-windows-msvc" / "snpe-onnx-to-dlc"),
        "--input_network",
        str(onnx_path),
        "-o",
        str(dlc_path),
    ]
    subprocess.run(cmd, check=True, env=env)
    print("converter finished:", dlc_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--qa",
        required=True,
        help="Path to qairt/2.46.0.260424",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Relative path where ONNX/DLC live",
    )
    parser.add_argument(
        "--onnx-name",
        default="pytorch_kws_model_clean.onnx",
        help="Name for the exported ONNX",
    )
    parser.add_argument(
        "--dlc-name",
        default="pytorch_kws_model.dlc",
        help="Name for the resulting DLC",
    )
    args = parser.parse_args()

    out_dir = Path.cwd() / args.output_dir
    onnx_path = out_dir / args.onnx_name
    dlc_path = out_dir / args.dlc_name
    qa_path = Path(args.qa)

    export_onnx(onnx_path)
    run_converter(qa_path, onnx_path, dlc_path)


if __name__ == "__main__":
    main()