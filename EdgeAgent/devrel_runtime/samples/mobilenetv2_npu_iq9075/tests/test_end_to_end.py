"""End-to-end tests: one full run on a small fixture, host-side (CPU only,
no board needed -- exercises the same code path deploy/inference.py runs
on-device) plus a real on-target smoke test gated on board reachability."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_run_cpu_end_to_end(fixture_model: Path):
    """Runs inference.run_cpu() directly against the real ONNX model with a
    random input -- this is exactly what deploy/inference.py does on-device
    for the CPU backend, just executed on the host instead."""
    import inference  # type: ignore[import-not-found]

    inp = inference.load_input(None)
    result = inference.run_cpu(str(fixture_model), inp, iterations=3, warmup=1)
    assert result["ok"] is True
    assert result["backend"] == "cpu"
    assert result["avg_ms"] > 0
    assert result["fps"] > 0
    assert result["logits"].shape == (1000,)


def test_run_inference_cpu_only_end_to_end(fixture_model: Path, fixture_labels: Path):
    import inference  # type: ignore[import-not-found]

    labels = inference.load_labels(str(fixture_labels))
    result = inference.run_inference(
        str(fixture_model), None, iterations=3, warmup=1, k=5, labels=labels, try_npu_gpu=False,
    )
    assert "cpu" in result["backends"]
    assert result["backends"]["cpu"]["ok"] is True
    assert "npu" not in result["backends"]
    assert "gpu" not in result["backends"]
    assert len(result["top_k"]) == 5
    for p in result["top_k"]:
        assert 0.0 <= p["prob"] <= 1.0


def test_run_inference_with_npu_gpu_attempt_never_crashes(fixture_model: Path):
    """The key contract this app makes: attempting NPU/GPU on a machine
    without onnxruntime_qnn installed (true for a plain CI/dev host) must
    degrade to a reported reason, never raise or hang."""
    import inference  # type: ignore[import-not-found]

    result = inference.run_inference(
        str(fixture_model), None, iterations=1, warmup=0, k=1, try_npu_gpu=True,
    )
    assert result["backends"]["cpu"]["ok"] is True
    for backend in ("npu", "gpu"):
        entry = result["backends"][backend]
        if not entry["ok"]:
            assert "error" in entry and entry["error"]


@pytest.mark.timeout(30)
def test_on_target_smoke(fixture_model: Path, fixture_image: Path, fixture_labels: Path, tmp_path: Path):
    """Real on-target smoke test -- skipped automatically if adb or the
    IQ-9075 board isn't reachable, so this test suite still passes cleanly
    on a plain CPU/CI machine with no board attached (per the app-builder
    convention: 'Skip on-target tests when board is unreachable')."""
    adb = shutil.which("adb") or shutil.which("adb.exe")
    if adb is None:
        pytest.skip("adb not on PATH -- skipping on-target smoke test")

    devices = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10)
    serials = [
        line.split("\t")[0]
        for line in devices.stdout.splitlines()[1:]
        if line.strip() and "\tdevice" in line
    ]
    if not serials:
        pytest.skip("no adb device attached -- skipping on-target smoke test")

    sample_dir = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [
            sys.executable, str(sample_dir / "run_iq9075.py"),
            "--transport", "adb",
            "--serial", serials[0],
            "--model", str(fixture_model),
            "--image", str(fixture_image),
            "--labels", str(fixture_labels),
            "--iterations", "3",
            "--warmup", "1",
            "--cpu-only",  # keep the on-target smoke fast; NPU/GPU attempt is exercised by unit tests
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=sample_dir,
        timeout=25,
    )
    assert proc.returncode == 0, proc.stderr
    assert "cpu" in proc.stdout
