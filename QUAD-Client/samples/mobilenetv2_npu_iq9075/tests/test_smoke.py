"""Smoke tests: imports + --help work, no crashes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_inference_module_imports():
    import inference  # type: ignore[import-not-found]

    assert hasattr(inference, "run_inference")
    assert hasattr(inference, "run_cpu")
    assert hasattr(inference, "attempt_qnn")
    assert hasattr(inference, "softmax")
    assert hasattr(inference, "topk")


def test_orchestrator_module_imports():
    import run_iq9075  # type: ignore[import-not-found]

    assert hasattr(run_iq9075, "main")
    assert hasattr(run_iq9075, "preprocess_image")
    assert hasattr(run_iq9075, "find_adb")
    assert hasattr(run_iq9075, "resolve_serial")


def test_inference_help_runs():
    sample_dir = Path(__file__).resolve().parents[1]
    script = sample_dir / "deploy" / "inference.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=sample_dir,
    )
    assert proc.returncode == 0
    assert "MobileNetV2" in proc.stdout


def test_orchestrator_help_runs():
    sample_dir = Path(__file__).resolve().parents[1]
    script = sample_dir / "run_iq9075.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=sample_dir,
    )
    assert proc.returncode == 0
    assert "IQ-9075" in proc.stdout
