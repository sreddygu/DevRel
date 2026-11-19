#!/usr/bin/env python3
"""Run the DevRel client bundled with this standalone EdgeAgent project."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = ROOT / "devrel_runtime"
RUNTIME_SRC = RUNTIME_ROOT / "src"


def _require_runtime() -> None:
    package_dir = RUNTIME_SRC / "devrel_client"
    if not package_dir.is_dir():
        raise SystemExit(
            f"Bundled DevRel runtime is missing: {package_dir}\n"
            "Restore devrel_runtime/ before running this command."
        )

    missing = [name for name in ("typer", "httpx") if importlib.util.find_spec(name) is None]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing DevRel runtime dependencies: {names}.\n"
            "Run: powershell -ExecutionPolicy Bypass -File .\\setup_devrel_runtime.ps1"
        )


def main() -> None:
    sys.path.insert(0, str(RUNTIME_SRC))
    _require_runtime()
    from devrel_client.cli import cli

    cli()


if __name__ == "__main__":
    main()
