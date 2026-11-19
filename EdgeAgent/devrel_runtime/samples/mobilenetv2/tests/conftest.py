"""Pytest config: add the sample dir to sys.path so tests can import modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = SAMPLE_DIR / "deploy"

for p in (SAMPLE_DIR, DEPLOY_DIR):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture
def sample_dir() -> Path:
    return SAMPLE_DIR


@pytest.fixture
def fixture_image(sample_dir: Path) -> Path:
    img = sample_dir / "test_input.jpg"
    if not img.exists():
        pytest.skip(f"missing fixture image: {img}")
    return img


@pytest.fixture
def fixture_labels(sample_dir: Path) -> Path:
    labels = sample_dir / "imagenet_classes.txt"
    if not labels.exists():
        pytest.skip(f"missing fixture labels: {labels}")
    return labels


@pytest.fixture
def fixture_model(sample_dir: Path) -> Path:
    m = sample_dir / "mobilenetv2.onnx"
    if not m.exists():
        pytest.skip(f"missing fixture model: {m}")
    return m
