r"""GPU inference sample — generate and profile Adreno GPU code via QUAD.

Usage:
    .venv\Scripts\python.exe gpu_inference.py [--model MODEL_PATH]

Demonstrates the typed QuadClient SDK:
  1. hardware_detect → confirm GPU backend availability
  2. convert_model   → convert ONNX to QNN format
  3. profile_workload with runtime="gpu"
  4. generate_code with runtime="gpu" → libQnnGpu backend
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure quad_mcp_client is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from quad_mcp_client import create_client  # noqa: E402


async def main(model_path: str) -> None:
    async with create_client() as client:
        # Step 1: Detect hardware — confirm GPU backend is available
        print("=" * 60)
        print("Step 1: Detecting hardware...")
        profile = await client.hardware_detect(platform="windows")

        gpu_model = profile.get("gpu_model", "unknown")
        gpu_available = profile.get("gpu_backend_available", False)
        print(f"  GPU: {gpu_model}")
        print(f"  GPU backend available: {gpu_available}")

        if not gpu_available:
            print("  WARNING: GPU backend not detected — results will use mock mode")

        # Step 2: Convert model to QNN format
        print("\n" + "=" * 60)
        print("Step 2: Converting model to QNN...")
        convert_result = await client.convert_model(
            source_format="onnx",
            model_path=model_path,
            target_sdk="qnn",
            quantization="fp32",
        )
        output_path = convert_result.get("output_path", model_path)
        print(f"  Converted: {output_path}")
        print(f"  Supported ops: {convert_result.get('supported_ops_pct', 0)}%")

        # Step 3: Profile on GPU
        print("\n" + "=" * 60)
        print("Step 3: Profiling on GPU...")
        prof_result = await client.profile_workload(
            model_path=output_path,
            platform="windows",
            runtime="gpu",
            duration_s=5,
        )
        latency = prof_result.get("latency", {})
        print(f"  Latency (mean): {latency.get('mean_ms', 0):.2f} ms")
        print(f"  Power: {prof_result.get('power_mw', 0):.0f} mW")
        util = prof_result.get("utilization", {})
        print(f"  GPU utilization: {util.get('gpu', 0):.0f}%")

        # Step 4: Generate GPU inference code
        print("\n" + "=" * 60)
        print("Step 4: Generating GPU inference code (C++)...")
        codegen_result = await client.generate_code(
            platform="windows",
            sdk="qnn",
            language="cpp",
            model_path=output_path,
            runtime="gpu",
        )
        source_files = codegen_result.get("source_files", {})
        for fname, content in source_files.items():
            print(f"\n  --- {fname} ({len(content.splitlines())} lines) ---")
            # Show the backend_lib line to confirm GPU backend
            for line in content.splitlines():
                if "backend_lib" in line or "libQnnGpu" in line:
                    print(f"  >> {line.strip()}")
                    break

        print("\n" + "=" * 60)
        print("Done! GPU inference code generated successfully.")
        print("Build instructions:", codegen_result.get("build_instructions", ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QUAD GPU inference sample")
    parser.add_argument(
        "--model",
        default=str(Path(__file__).parent.parent / "mobilenetv2" / "mobilenetv2.onnx"),
        help="Path to ONNX model (default: mobilenetv2.onnx)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.model))
