"""
Convert mobilenetv2.onnx to INT8 QNN context binary via the QUAD MCP server.

Usage
-----
    python convert_int8.py [--model PATH] [--calibration DIR] [--server URL]

Defaults
    --model        mobilenetv2.onnx        (download instructions below)
    --calibration  calibration/            (optional but recommended)
    --server       stdio                   (local QUAD server via subprocess)

Download the ONNX model
-----------------------
    # ONNX Model Zoo release (opset 12)
    curl -L -o mobilenetv2.onnx \
        https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx

Calibration data (optional but strongly recommended for INT8 accuracy)
-----------------------------------------------------------------------
    mkdir calibration
    # Copy 100–500 representative JPEG/PNG images into calibration/
    # QUAD will preprocess them automatically using the image_format_notes
    # derived from the model's input layout (NCHW, RGB, mean-subtracted).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert mobilenetv2.onnx to INT8 via QUAD.")
    p.add_argument("--model", default="mobilenetv2.onnx",
                   help="Path to the source ONNX model (default: mobilenetv2.onnx)")
    p.add_argument("--calibration", default=None,
                   help="Directory of calibration images (optional, improves INT8 accuracy)")
    p.add_argument("--output-dir", default="output",
                   help="Directory to write the converted artefacts (default: output/)")
    p.add_argument("--server", default="stdio",
                   help=(
                       "QUAD server address. "
                       "'stdio' (default) spawns a local server subprocess. "
                       "Pass an HTTP/SSE URL for a remote server, e.g. http://localhost:8080/sse"
                   ))
    p.add_argument("--target-sdk", default="qnn",
                   choices=["qnn", "snpe", "qairt"],
                   help="Target Qualcomm SDK (default: qnn — best for Windows Snapdragon X Elite)")
    return p.parse_args()


def _check_model(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        print(f"[error] Model not found: {p}")
        print()
        print("Download it with:")
        print(
            "  curl -L -o mobilenetv2.onnx "
            "https://github.com/onnx/models/raw/main/validated/vision/classification/"
            "mobilenet/model/mobilenetv2-12.onnx"
        )
        sys.exit(1)
    return p


def _format_table(result: dict) -> str:
    """Render the conversion result as a simple table."""
    rows = [
        ("Original size",   result.get("original_size_mb", "?"), "MB"),
        ("Output size",     result.get("output_size_mb", "?"),   "MB"),
        ("Compression",     result.get("compression_ratio", "?"), "×"),
        ("Quantization",    result.get("quantization", "?"),      ""),
        ("Supported ops",   result.get("supported_ops_pct", "?"), "%"),
        ("Conversion time", result.get("conversion_time_s", "?"), "s"),
        ("Target SDK",      result.get("target_sdk", "?"),        ""),
        ("Output path",     result.get("output_path", "?"),       ""),
    ]
    width = max(len(r[0]) for r in rows) + 2
    lines = []
    for label, value, unit in rows:
        lines.append(f"  {label:<{width}} {value} {unit}".rstrip())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main conversion coroutine
# ---------------------------------------------------------------------------

async def convert(args: argparse.Namespace) -> None:
    try:
        from fastmcp import Client  # type: ignore[import-untyped]
    except ImportError:
        print("[error] fastmcp is not installed. Run:  pip install fastmcp")
        sys.exit(1)

    model_path = _check_model(args.model)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Build tool arguments
    # -----------------------------------------------------------------------
    tool_args: dict = {
        "source_format":     "onnx",
        "model_path":        str(model_path.resolve()),
        "target_sdk":        args.target_sdk,
        "quantization":      "int8",
        # MobileNetV2 from ONNX Model Zoo uses PyTorch convention: NCHW, RGB
        "input_layout":      "nchw",
        "channel_order":     "rgb",
        # Bind the symbolic batch dimension to 1
        "input_dimensions":  {"input": "1,3,224,224"},
        # ImageNet mean / std for MobileNetV2
        "mean_values":       [123.675, 116.28, 103.53],
        "std_values":        [58.395,  57.12,  57.375],
        "output_dir":        str(output_dir.resolve()),
    }
    if args.calibration:
        cal = Path(args.calibration)
        if not cal.is_dir():
            print(f"[warn] Calibration directory not found: {cal} — skipping calibration data.")
        else:
            tool_args["calibration_data"] = str(cal.resolve())

    # -----------------------------------------------------------------------
    # Connect to QUAD server and call convert_model
    # -----------------------------------------------------------------------
    if args.server == "stdio":
        server_target = "python -m quad.mcp.server"
    else:
        server_target = args.server

    print(f"Connecting to QUAD server ({server_target!r}) …")
    print(f"  Model       : {model_path}")
    print("  Quantization: INT8")
    print(f"  Target SDK  : {args.target_sdk}")
    if args.calibration:
        print(f"  Calibration : {args.calibration}")
    print()

    async with Client(server_target) as client:
        print("Connected. Starting conversion …")
        response = await client.call_tool("convert_model", tool_args)

    # -----------------------------------------------------------------------
    # Parse and display result
    # -----------------------------------------------------------------------
    # fastmcp returns a list of content items; the first text item is JSON.
    raw = response[0].text if response else "{}"
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        result = {"raw": raw}

    if result.get("status") == "error":
        print(f"[error] Conversion failed: {result.get('message', raw)}")
        sys.exit(1)

    print("Conversion complete!\n")
    print(_format_table(result))
    print()

    # Surface image format guidance — critical for correct preprocessing at inference time
    notes = result.get("image_format_notes")
    if notes:
        print("Image format guidance (needed for test_target.py):")
        if isinstance(notes, list):
            for note in notes:
                print(f"  • {note}")
        else:
            print(f"  {notes}")
        print()

    # Warn about unsupported ops that will fall back to CPU
    unsupported = result.get("unsupported_ops", [])
    if unsupported:
        print(f"[warn] {len(unsupported)} op(s) not supported on NPU — will fall back to CPU:")
        for op in unsupported:
            print(f"  • {op}")
        print()

    output_path = result.get("output_path", str(output_dir))
    print("Next steps:")
    print(f"  1. Profile on NPU   :  quad-profile {output_path}")
    print(f"  2. Test on target   :  python test_target.py --model {output_path}")
    print("  3. Orchestrate      :  quad-orchestrate (allocate across CPU/GPU/NPU)")


def main() -> None:
    args = _parse_args()
    asyncio.run(convert(args))


if __name__ == "__main__":
    main()
