"""Tests for adb orchestration: find_adb / list_devices / require_one_device.

All adb invocations are mocked via monkeypatch -- no device required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class _FakeProc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _patch_adb_run(monkeypatch, stdout: str = "", returncode: int = 0):
    """Replace subprocess.run inside run_target_cpu with a fake."""
    import run_target_cpu  # type: ignore[import-not-found]

    calls: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        calls.append(list(cmd))
        return _FakeProc(stdout=stdout, returncode=returncode)

    monkeypatch.setattr(run_target_cpu.subprocess, "run", fake_run)
    return calls


def test_find_adb_uses_path(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(run_target_cpu.shutil, "which", lambda name: "/fake/adb.exe")
    assert run_target_cpu.find_adb() == "/fake/adb.exe"


def test_find_adb_falls_back_to_winget(monkeypatch, tmp_path: Path):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(run_target_cpu.shutil, "which", lambda name: None)
    fake_local = tmp_path / "AppData" / "Local"
    fake_winget = (
        fake_local
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "platform-tools"
        / "adb.exe"
    )
    fake_winget.parent.mkdir(parents=True, exist_ok=True)
    fake_winget.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))
    assert run_target_cpu.find_adb() == str(fake_winget)


def test_find_adb_raises_when_missing(monkeypatch, tmp_path: Path):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(run_target_cpu.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(run_target_cpu.AdbError, match="not found"):
        run_target_cpu.find_adb()


def test_list_devices_parses_serials(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    _patch_adb_run(
        monkeypatch,
        stdout=(
            "List of devices attached\n"
            "3169246211\tdevice\n"
            "emu-5554\tdevice\n"
        ),
    )
    devs = run_target_cpu.list_devices("adb")
    assert devs == ["3169246211", "emu-5554"]


def test_list_devices_skips_unauthorized(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    _patch_adb_run(
        monkeypatch,
        stdout=(
            "List of devices attached\n"
            "abc123\tunauthorized\n"
            "xyz999\tdevice\n"
        ),
    )
    assert run_target_cpu.list_devices("adb") == ["xyz999"]


def test_list_devices_empty(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    _patch_adb_run(monkeypatch, stdout="List of devices attached\n\n")
    assert run_target_cpu.list_devices("adb") == []


def test_require_one_device_happy(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(
        run_target_cpu, "list_devices", lambda _adb: ["serial1"]
    )
    assert run_target_cpu.require_one_device("adb") == "serial1"


def test_require_one_device_none(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(run_target_cpu, "list_devices", lambda _adb: [])
    with pytest.raises(run_target_cpu.AdbError, match="No adb devices"):
        run_target_cpu.require_one_device("adb")


def test_require_one_device_multiple(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    monkeypatch.setattr(
        run_target_cpu, "list_devices", lambda _adb: ["a", "b"]
    )
    with pytest.raises(run_target_cpu.AdbError, match="Multiple devices"):
        run_target_cpu.require_one_device("adb")


def test_adb_propagates_failure(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    def fake_run(cmd, *a, **kw):
        return _FakeProc(stdout="", stderr="boom", returncode=99)

    monkeypatch.setattr(run_target_cpu.subprocess, "run", fake_run)
    with pytest.raises(run_target_cpu.AdbError, match="boom"):
        run_target_cpu.adb("adb", "shell", "ls")


def test_run_remote_parses_json(monkeypatch):
    import run_target_cpu  # type: ignore[import-not-found]

    expected = {
        "avg_ms": 65.6,
        "p50_ms": 65.6,
        "p99_ms": 88.9,
        "fps": 14.2,
        "iterations": 10,
        "warmup": 3,
        "model": "/data/local/tmp/quad/models/mobilenetv2.onnx",
        "input": "/data/local/tmp/quad/inputs/mobilenetv2_input.npy",
        "top_k": [{"class_id": 281, "prob": 0.5, "label": "tabby"}],
    }
    fake_stdout = (
        "[W:onnxruntime] some warning\n" + json.dumps(expected) + "\n"
    )
    _patch_adb_run(monkeypatch, stdout=fake_stdout)
    result = run_target_cpu.run_remote(
        "adb", iterations=10, warmup=3, top_k=5
    )
    assert result["avg_ms"] == pytest.approx(65.6)
    assert result["top_k"][0]["label"] == "tabby"


def test_main_errors_when_files_missing(monkeypatch, tmp_path: Path, capsys):
    import run_target_cpu  # type: ignore[import-not-found]

    rc = run_target_cpu.main(
        [
            "--model",
            str(tmp_path / "nope.onnx"),
            "--image",
            str(tmp_path / "nope.jpg"),
            "--labels",
            str(tmp_path / "nope.txt"),
            "--script",
            str(tmp_path / "nope.py"),
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "model not found" in err
