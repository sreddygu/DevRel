"""SSE smoke test — exercise all 6 DevRel MCP tools against a remote server.

Run:
    python tools/sse_smoke_test.py http://HOST:8000/mcp <TOKEN>
"""

from __future__ import annotations

import asyncio
import json
import sys

from devrel_client.client import create_client


def _show(name: str, payload: object) -> None:
    print(f"\n=== {name} ===")
    if isinstance(payload, dict):
        # Print a compact digest so we don't flood the terminal.
        keys = list(payload.keys())
        print(f"  keys: {keys}")
        for k in ("chipset", "gpu", "npu", "runtime_used", "runtimes",
                  "matched_chipset", "verdict", "device", "ok", "error",
                  "output_path", "status"):
            if k in payload:
                print(f"  {k}: {json.dumps(payload[k])[:200]}")
    else:
        print(f"  {str(payload)[:300]}")


async def main(url: str, token: str) -> int:
    async with create_client(url=url, token=token) as client:
        # 1. hardware_detect — exercises the qairt GPU-parse fix path.
        try:
            hw = await client.hardware_detect("linux")
            _show("hardware_detect(linux)", hw)
        except Exception as e:
            print(f"\n=== hardware_detect FAILED: {e!r}")

        # 2. aihub_select search — exercises verdict_rank + compat slug fixes.
        try:
            sel = await client.aihub_select(action="search", query="llama")
            _show("aihub_select(search llama)", sel)
        except Exception as e:
            print(f"\n=== aihub_select FAILED: {e!r}")

        # 3. aihub_select compat for a Dragonwing IQ-9075 — must NOT fabricate
        #    a qualcomm-qcs9075 slug (the fix).
        try:
            compat = await client.aihub_select(
                action="compat", model_id="llama_v3_2_3b", platform="linux"
            )
            _show("aihub_select(compat iq9075)", compat)
        except Exception as e:
            print(f"\n=== aihub_select compat FAILED: {e!r}")

        # 4. convert_model — mock/real convert.
        try:
            conv = await client.convert_model(
                source_format="onnx",
                model_path="models/mobilenetv2.onnx",
                quantization="int8",
            )
            _show("convert_model", conv)
        except Exception as e:
            print(f"\n=== convert_model FAILED: {e!r}")

        # 5. profile_workload.
        try:
            prof = await client.profile_workload(
                model_path="models/mobilenetv2.dlc", profiling_level="detailed"
            )
            _show("profile_workload", prof)
        except Exception as e:
            print(f"\n=== profile_workload FAILED: {e!r}")

        # 6. generate_code.
        try:
            gen = await client.generate_code(
                platform="windows", language="cpp", model_path="models/mobilenetv2.dlc"
            )
            _show("generate_code", gen)
        except Exception as e:
            print(f"\n=== generate_code FAILED: {e!r}")

    print("\n[done] SSE smoke test complete.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: sse_smoke_test.py <sse-url> <token>")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1], sys.argv[2])))
