"""Pytest fixtures shared across the STC test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the sample's top-level scripts importable from tests/
SAMPLE_ROOT = Path(__file__).resolve().parent.parent
if str(SAMPLE_ROOT) not in sys.path:
    sys.path.insert(0, str(SAMPLE_ROOT))


@pytest.fixture(scope="session")
def sample_root() -> Path:
    return SAMPLE_ROOT


@pytest.fixture(scope="session")
def app_dir(sample_root: Path) -> Path:
    return sample_root / "app"


@pytest.fixture(scope="session")
def onnx_path(sample_root: Path) -> Path:
    p = sample_root / "stc_1dcnn.onnx"
    if not p.is_file():
        pytest.skip(
            f"{p} missing -- run `.venv/Scripts/python.exe build_model.py` first"
        )
    return p
