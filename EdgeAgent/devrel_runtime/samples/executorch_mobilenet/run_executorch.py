"""
run_executorch.py — PyTorch → ExecuTorch .pte → profile → runner code, via DevRel.

End-to-end demonstration of DevRel's ExecuTorch integration. Spawns the DevRel MCP
server as a subprocess (no server to start) and walks the full lifecycle:

  1. hardware_detect   — what chipset / NPU are we targeting?
  2. convert_model     — PyTorch → ExecuTorch .pte (target_sdk="executorch")
                         with the QNN-HTP delegate; shows the delegate
                         partition map (delegated vs CPU-fallback ops)
  3. profile_workload  — per-op ETDump-style profile of the .pte
  4. orchestrate_workload — CPU/GPU/NPU allocation the partition implies
  5. generate_code     — emit an ExecuTorch runner (python or cpp)

Runs in **mock mode** by default, so it works on any machine with no torch,
no NPU, and no QNN SDK — the whole pipeline is exercised end to end and a real
stub `.pte` is written to disk. Pass `--real` on a build-capable Snapdragon host
(3.10–3.13 + torch + executorch + QAIRT) to drive the real export.

Usage
-----
    # one-time
    ./run.ps1                      # or: pip install -r requirements.txt

    # mock end-to-end (any host)
    .venv/Scripts/python.exe run_executorch.py

    # choose the delegate backend + quantization
    .venv/Scripts/python.exe run_executorch.py --runtime xnnpack --quantization fp32

    # real export on a build-capable Snapdragon host
    .venv/Scripts/python.exe run_executorch.py --real --platform android
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows consoles (cp1252 can't render the box chars).
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = HERE / "mobilenet_v2.pt"


# ── tiny PyTorch model fixture ────────────────────────────────────────────────


def ensure_model(model_path: Path) -> Path:
    """Make sure a PyTorch model file exists at model_path.

    If `torch` is available, save a real (tiny) MobileNetV2-shaped module so a
    --real run has something genuine to export. Otherwise write a placeholder
    blob — mock-mode convert only needs the file to exist + sizes from it.
    """
    if model_path.exists():
        return model_path
    try:
        import torch
        import torchvision  # type: ignore[import-untyped]

        model = torchvision.models.mobilenet_v2(weights=None)
        model.eval()
        torch.save(model, model_path)
        print(f"[setup] saved a real MobileNetV2 module → {model_path.name}")
    except Exception:
        model_path.write_bytes(b"\x80\x02DevRel-placeholder-pytorch-model" + b"\0" * 4096)
        print(f"[setup] torch not available — wrote a placeholder {model_path.name} "
              "(fine for mock mode)")
    return model_path


# ── MCP plumbing ──────────────────────────────────────────────────────────────


def _server_env(adapter_mode: str) -> dict[str, str]:
    env = dict(os.environ)
    env["DevRel_ADAPTER_MODE"] = adapter_mode
    # The FastMCP banner goes to stdout and corrupts the stdio JSONRPC channel.
    env["FASTMCP_SHOW_SERVER_BANNER"] = "false"
    return env


async def _call(client: Any, tool: str, args: dict) -> dict:
    response = await client.call_tool(tool, args)
    if response.structured_content:
        return response.structured_content
    raw = next((b.text for b in response.content if hasattr(b, "text")), "{}")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        return {"raw": raw}


async def run_pipeline(args: argparse.Namespace) -> int:
    try:
        from fastmcp import Client
        from fastmcp.client.transports.stdio import StdioTransport
    except ImportError:
        print("[error] fastmcp not installed. Run:  pip install fastmcp")
        return 1

    model_path = ensure_model(Path(args.model))
    python_exe = sys.executable
    adapter_mode = "real" if args.real else "mock"

    transport = StdioTransport(
        command=python_exe,
        args=["-m", "devrel.mcp.server"],
        env=_server_env(adapter_mode),
        keep_alive=False,
    )

    print("=" * 70)
    print(f"DevRel × ExecuTorch  —  {adapter_mode.upper()} mode")
    print(f"  model={model_path.name}  platform={args.platform}  "
          f"runtime={args.runtime}  quant={args.quantization}")
    print("=" * 70)

    async with Client(transport) as client:
        # 1. hardware_detect
        hw = await _call(client, "hardware_detect", {"platform": args.platform})
        print(f"\n[1/5] hardware_detect → {hw.get('chipset', '?')}  "
              f"NPU={hw.get('npu_model', '?')} ({hw.get('npu_tops', '?')} TOPS)")

        # 2. convert_model → .pte
        conv = await _call(client, "convert_model", {
            "source_format": "pytorch",
            "model_path": str(model_path),
            "target_sdk": "executorch",
            "quantization": args.quantization,
            "runtime": args.runtime,
        })
        if "output_path" not in conv:
            print(f"\n[error] convert_model failed: {json.dumps(conv, indent=2)[:800]}")
            return 1
        pte = conv["output_path"]
        delegated = conv.get("delegated_op_count")
        fallback = conv.get("fallback_op_count")
        print(f"\n[2/5] convert_model → {Path(pte).name}")
        print(f"        size: {conv.get('original_size_mb')} MB → {conv.get('model_size_mb')} MB "
              f"({conv.get('quantization_applied')})")
        if delegated is not None:
            total = delegated + (fallback or 0)
            print(f"        delegate partition: {delegated}/{total} ops on "
                  f"{args.runtime}, {fallback} on CPU fallback")
            if conv.get("fallback_ops"):
                print(f"        fallback ops: {', '.join(conv['fallback_ops'])}")
        for note in conv.get("conversion_notes", [])[:3]:
            print(f"        • {note}")

        # 3. profile_workload (.pte)
        prof = await _call(client, "profile_workload", {
            "model_path": pte,
            "platform": args.platform,
            "runtime": "npu" if args.runtime.startswith("qnn") else "cpu",
            "duration_s": 5,
            "profiling_level": "detailed",
        })
        lat = prof.get("latency", {})
        print(f"\n[3/5] profile_workload → mean {lat.get('mean_ms')} ms  "
              f"({prof.get('throughput_fps')} fps, {prof.get('power_mw')} mW)  "
              f"on {prof.get('runtime_used')}")
        print(f"        per-op layers profiled: {len(prof.get('layers', []))}  "
              f"(source: {prof.get('measurement_notes', {}).get('source', 'n/a')})")

        # 4. orchestrate_workload
        alloc = await _call(client, "orchestrate_workload", {
            "model_path": pte,
            "power_mode": args.power_mode,
        })
        print(f"\n[4/5] orchestrate_workload ({args.power_mode}) → "
              f"NPU {alloc.get('npu_utilization_pct')}%  "
              f"GPU {alloc.get('gpu_utilization_pct')}%  "
              f"CPU {alloc.get('cpu_utilization_pct')}%")
        print(f"        projected: {alloc.get('projected_latency_ms')} ms, "
              f"{alloc.get('projected_power_mw')} mW")

        # 5. generate_code
        gen = await _call(client, "generate_code", {
            "platform": args.platform,
            "sdk": "executorch",
            "language": args.language,
            "model_path": pte,
            "runtime": "npu" if args.runtime.startswith("qnn") else "cpu",
        })
        files = gen.get("source_files", {})
        print(f"\n[5/5] generate_code ({args.language}) → {len(files)} file(s)")
        out_dir = HERE / "generated"
        out_dir.mkdir(exist_ok=True)
        for name, content in files.items():
            (out_dir / name).write_text(content, encoding="utf-8")
            print(f"        • {name}  ({len(content.splitlines())} lines)  → generated/{name}")

    print("\n" + "=" * 70)
    print("Done. The .pte and generated runner are on disk.")
    if adapter_mode == "mock":
        print("This was a MOCK run — re-run with --real on a build-capable Snapdragon")
        print("host (3.10–3.13 + torch + executorch + QAIRT) for a genuine export.")
    print("=" * 70)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="DevRel × ExecuTorch end-to-end sample")
    ap.add_argument("--model", default=str(DEFAULT_MODEL), help="PyTorch model path (.pt)")
    ap.add_argument("--platform", default="android",
                    choices=["windows", "linux", "android", "gateway", "robotics"])
    ap.add_argument("--runtime", default="qnn-htp",
                    choices=["qnn-htp", "qnn-gpu", "xnnpack", "vulkan", "arm"],
                    help="ExecuTorch delegate backend")
    ap.add_argument("--quantization", default="int8", choices=["fp32", "int8", "fp16"])
    ap.add_argument("--language", default="python", choices=["python", "cpp"])
    ap.add_argument("--power-mode", default="performance",
                    choices=["performance", "balanced", "efficiency"])
    ap.add_argument("--real", action="store_true",
                    help="drive the real export (needs a build-capable host)")
    args = ap.parse_args()

    rc = asyncio.run(run_pipeline(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
