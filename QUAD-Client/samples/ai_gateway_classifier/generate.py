"""Render the AI Gateway classifier starter app.

Calls QUAD's `generate_code` MCP operation with parameters tuned for
MobileNetV2 INT8 on an `aarch64-openwrt-linux` gateway. Writes the
six rendered files under ./app/.

Customize the constants below and re-run to retarget. The same call
is what the `quad-codegen` skill makes when invoked via Claude Code.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running this script from QUAD-Client/samples/ai_gateway_classifier/
# even if the QUAD package isn't pip-installed — find the QUAD source tree
# next to the QUAD-Client repo and prepend it to sys.path.
HERE = Path(__file__).resolve()
for parent in HERE.parents:
    candidate = parent.parent / "QUAD" / "src"
    if (candidate / "quad" / "__init__.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from quad.core.operations.generate_code import generate_code  # noqa: E402

# ── Customize these ────────────────────────────────────────────────────────

MODEL_PATH = "/host/mobilenetv2.bin"
"""Source model path. Mock mode doesn't actually read this file."""

TARGET_ARCH = "aarch64-openwrt-linux"
"""One of: aarch64-openwrt-linux | aarch64-prpl-linux | aarch64-rdk-linux | arm-openwrt-linux."""

RUNTIME = "npu"
"""npu (default; → NWAIOS NSP) | cpu | gpu (→ CPU fallback) | auto."""

SCAFFOLD = "minimal"
"""minimal (default; 6-file output) | modular (10-file output mirroring the
fault-detection reference — adds model_inferencing.c/h, Dockerfile, and
oci_config.json). Switch to "modular" when you outgrow the simple layout."""


def main() -> int:
    out = asyncio.run(generate_code(
        platform="gateway",
        sdk="nwaios",
        language="c",
        model_path=MODEL_PATH,
        runtime=RUNTIME,
        target_arch=TARGET_ARCH,
        scaffold=SCAFFOLD,
    ))
    app_dir = HERE.parent / "app"
    app_dir.mkdir(exist_ok=True)
    for name, content in out["source_files"].items():
        (app_dir / name).write_text(content)

    print(f"Wrote {len(out['source_files'])} files to {app_dir}/")
    print("\nNext:")
    print(f"  quad gwapps build --source {app_dir} --target {TARGET_ARCH} --dry-run")
    print("\nWhat's in:")
    for name in sorted(out["source_files"].keys()):
        print(f"  {app_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
