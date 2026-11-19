"""Smoke-test the vendored markdown formatters."""

from __future__ import annotations

from devrel_client.local.render import format_device, format_doctor, tips_for


def test_format_device_contains_chipset_and_runtimes() -> None:
    fixture = {
        "chipset": "Snapdragon X Elite",
        "platform": "windows",
        "cpu_cores": 12,
        "cpu_arch": "Oryon ARM64",
        "cpu_freq_ghz": 4.012,
        "gpu_model": "Adreno X1-85",
        "gpu_tflops": 4.6,
        "npu_model": "Hexagon NPU",
        "npu_tops": 45.0,
        "ram_gb": 31.6,
        "sdk_path": "/opt/qairt/2.45",
        "sdk_version": "2.45.0",
        "available_runtimes": ["cpu", "gpu", "npu"],
    }
    out = format_device(fixture)
    assert "Snapdragon X Elite" in out
    assert "31.6" in out
    assert "TFLOPS" in out
    assert "TOPS" in out
    assert "cpu, gpu, npu" in out


def test_format_doctor_summarises_pass_warn_fail() -> None:
    checks = [
        {"name": "A", "status": "pass", "message": "ok"},
        {"name": "B", "status": "warn", "message": "soft"},
        {"name": "C", "status": "fail", "message": "boom"},
    ]
    out = format_doctor(checks)
    assert "1 passed" in out
    assert "1 warnings" in out
    assert "1 errors" in out
    # Status icons rendered (ASCII variants in the vendored copy).
    assert "[OK]" in out
    assert "[FAIL]" in out


def test_tips_for_detect_returns_two() -> None:
    tips = tips_for("detect", n=2)
    assert len(tips) == 2
    assert all(isinstance(t, str) and t for t in tips)
    assert tips_for("convert", n=2) == []
