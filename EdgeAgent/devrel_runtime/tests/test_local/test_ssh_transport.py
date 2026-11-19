"""Phase 4 (IQ-9075 retrospective): SSH/SCP transport-layer fixes.

Covers the silent scp port bug (-P vs -p), non-UTF-8 decode safety,
unreachable-host messaging, and the pre-flight disk-space check — all without
touching a real board (subprocess.run is stubbed).
"""

from __future__ import annotations

from devrel_client.local.board import ssh
from devrel_client.local.board.ssh import SSHTarget


def _target() -> SSHTarget:
    return SSHTarget(host="board.local", user="root", port=2222)


class TestPortFlag:
    def test_ssh_uses_lowercase_p(self):
        args = _target().base_args()
        assert "-p" in args and "-P" not in args
        assert args[args.index("-p") + 1] == "2222"

    def test_scp_uses_uppercase_p(self):
        args = _target().base_args(is_scp=True)
        assert "-P" in args and "-p" not in args
        assert args[args.index("-P") + 1] == "2222"


class TestRunRemoteDecoding:
    def test_non_utf8_output_does_not_crash(self, monkeypatch):
        class _R:
            returncode = 0
            stdout = "ok�"  # already-replaced byte
            stderr = ""

        monkeypatch.setattr(ssh.shutil, "which", lambda _n: "/usr/bin/ssh")
        captured = {}

        def _run(cmd, **kw):
            captured.update(kw)
            return _R()

        monkeypatch.setattr(ssh.subprocess, "run", _run)
        result = ssh.run_remote(_target(), "echo hi")
        assert result.ok
        # errors='replace' must be requested so non-UTF-8 bytes never crash.
        assert captured.get("errors") == "replace"
        assert captured.get("encoding") == "utf-8"


class TestUnreachableHost:
    def test_exit_255_becomes_clear_message(self, monkeypatch):
        class _R:
            returncode = 255
            stdout = ""
            stderr = "ssh: connect to host board.local port 2222: No route to host"

        monkeypatch.setattr(ssh.shutil, "which", lambda _n: "/usr/bin/ssh")
        monkeypatch.setattr(ssh.subprocess, "run", lambda cmd, **kw: _R())
        result = ssh.run_remote(_target(), "uptime")
        assert not result.ok
        assert "unreachable" in result.stderr.lower()
        assert "board.local:2222" in result.stderr


class TestPushFilePreflightSpace:
    def test_blocks_when_insufficient_space(self, monkeypatch, tmp_path):
        src = tmp_path / "model.bin"
        src.write_bytes(b"x" * 10_000_000)  # 10 MB

        monkeypatch.setattr(ssh.shutil, "which", lambda _n: "/usr/bin/scp")

        # df reports only 1000 KB (~1 MB) available — not enough for 10 MB.
        def _fake_run_remote(target, cmd, **kw):
            return ssh.CommandResult(
                returncode=0,
                stdout="rootfs 100000 90000 1000 90% /data",
                stderr="",
                elapsed_ms=1.0,
            )

        monkeypatch.setattr(ssh, "run_remote", _fake_run_remote)
        # scp must NOT be invoked when space check fails.
        monkeypatch.setattr(ssh.subprocess, "run", lambda *a, **k: pytest_fail())

        result = ssh.push_file(_target(), src, "/data/model.bin")
        assert result.returncode == 28  # ENOSPC
        assert "Not enough space" in result.stderr

    def test_proceeds_when_space_ok(self, monkeypatch, tmp_path):
        src = tmp_path / "model.bin"
        src.write_bytes(b"x" * 1000)  # 1 KB

        monkeypatch.setattr(ssh.shutil, "which", lambda _n: "/usr/bin/scp")
        monkeypatch.setattr(
            ssh, "run_remote",
            lambda t, c, **k: ssh.CommandResult(0, "rootfs 100000 100 99000 1% /data", "", 1.0),
        )

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        called = {"scp": False}

        def _run(cmd, **kw):
            called["scp"] = True
            # scp must use uppercase -P.
            assert "-P" in cmd
            return _R()

        monkeypatch.setattr(ssh.subprocess, "run", _run)
        result = ssh.push_file(_target(), src, "/data/model.bin")
        assert result.ok
        assert called["scp"] is True


def pytest_fail():  # helper: scp should never be reached in the ENOSPC test
    raise AssertionError("scp should not run when pre-flight space check fails")
