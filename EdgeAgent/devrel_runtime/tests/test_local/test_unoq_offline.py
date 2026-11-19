"""UNO Q board-ops tests using a fake SSH shim.

We monkeypatch ``shutil.which`` to point at a small Python script that
echoes deterministic stdout, so the SSH wrapper exercises end-to-end
command construction + result parsing without needing a live board.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from devrel_client.local.board import commands as ops
from devrel_client.local.board.ssh import SSHTarget


@pytest.fixture
def fake_ssh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a fake ssh on PATH that echoes its remote command back as stdout."""
    script = tmp_path / ("ssh.bat" if sys.platform == "win32" else "ssh")
    if sys.platform == "win32":
        # Windows .bat: echo the last argument (the remote command) verbatim.
        script.write_text("@echo off\r\necho FAKE-SSH-OK\r\nexit /B 0\r\n", encoding="utf-8")
    else:
        script.write_text("#!/usr/bin/env bash\necho FAKE-SSH-OK\nexit 0\n")
        st = os.stat(script)
        os.chmod(script, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    return script


def _target() -> SSHTarget:
    return SSHTarget(host="fake.local", user="root")


def test_status_returns_bundle_result(fake_ssh: Path) -> None:
    r = ops.status(_target())
    assert r.op == "status"
    assert r.ok is True  # fake-ssh returns 0 for every probe
    assert "alive" in r.details and "uname" in r.details
    assert "FAKE-SSH-OK" in r.details["alive"]["stdout"]


def test_debug_returns_diagnostic_bundle(fake_ssh: Path) -> None:
    r = ops.debug(_target())
    assert r.op == "debug"
    assert "dsp_state" in r.details
    assert "snpe_version" in r.details
    assert "kernel_errors" in r.details


def test_logs_passes_since_window(fake_ssh: Path) -> None:
    r = ops.logs(_target(), since_minutes=15)
    assert r.op == "logs"
    assert "dmesg_tail" in r.details
    assert "journal_recent" in r.details


def test_app_lifecycle_validates_action(fake_ssh: Path) -> None:
    r = ops.app_lifecycle(_target(), action="invalid", app_name="x")
    assert r.ok is False
    assert "must be one of" in r.summary


def test_run_command_dispatches_known_op(fake_ssh: Path) -> None:
    r = ops.run_command("status", _target())
    assert r.op == "status"
    assert r.ok is True


def test_run_command_unknown_op_fails() -> None:
    r = ops.run_command("nonexistent")
    assert r.ok is False
    assert "unknown command" in r.summary


def test_configure_template_includes_host_in_toml() -> None:
    r = ops.configure_template(host="10.0.0.5", user="pi")
    assert r.ok
    assert "host = \"10.0.0.5\"" in r.details["toml"]
    assert "user = \"pi\"" in r.details["toml"]
