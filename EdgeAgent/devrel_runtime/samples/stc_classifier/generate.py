"""Render the STC (Smart Traffic Classifier) NWAIOS app from DevRel templates.

Calls DevRel's `generate_code` MCP operation with parameters tuned for
the 5-class 1D-CNN packet classifier on `aarch64-openwrt-linux`.
Writes the rendered modular scaffold under ./app/.

Customize the constants below and re-run to retarget. The same call
is what the `devrel-codegen` skill makes when invoked via Claude Code.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running from devrelAgent/samples/stc_classifier/ even without
# `pip install` -- find DevRel's source tree next to devrelAgent.
HERE = Path(__file__).resolve()
for parent in HERE.parents:
    candidate = parent.parent / "DevRel" / "src"
    if (candidate / "devrel" / "__init__.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from devrel.core.operations.generate_code import generate_code  # noqa: E402

# -- Customize these --------------------------------------------------------

MODEL_PATH = "/host/stc_classifier.bin"
"""Source model path. Mock mode does not actually read this file.
The stem ('stc_classifier') becomes the IPK package name and lcmd handle."""

APP_NAME = "stc_classifier"
"""Mirrors Path(MODEL_PATH).stem -- kept here for clarity."""

TARGET_ARCH = "aarch64-openwrt-linux"
"""aarch64-openwrt-linux | aarch64-prpl-linux | aarch64-rdk-linux | arm-openwrt-linux."""

RUNTIME = "npu"
"""npu (default; -> NWAIOS NSP) | cpu | gpu (-> CPU fallback) | auto."""

SCAFFOLD = "modular"
"""minimal (6-file) | modular (17-file -- full production layout with
turnkey, debugging, cloud_services, oci_config, Dockerfile)."""


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
        (app_dir / name).write_text(content, encoding="utf-8")

    print(f"Wrote {len(out['source_files'])} files to {app_dir}/")
    print()
    print("Next:")
    print("  python build_model.py                                    # synth ONNX")
    print(f"  devrel gwapps build --source {app_dir} --target {TARGET_ARCH} --dry-run")
    print(f"  devrel gwapps deploy {app_dir}/{APP_NAME}.ipk              # mock LCM")
    print()
    print("Files:")
    for name in sorted(out["source_files"].keys()):
        print(f"  {app_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
