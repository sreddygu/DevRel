"""CLI tests for `devrel-agent profile-device` model-source resolution (#33).

Covers the three ways a model reaches the board — local, --model-from-server,
--convert — plus validation, using a fake DevRelClient (no server) and a fake
device_agent.execute_plan (no board).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devrel_client.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class _FakeClient:
    """Async-context-manager stand-in for DevRelClient."""

    def __init__(self, *, download_to: Path | None = None, convert_local: Path | None = None):
        self._download_to = download_to
        self._convert_local = convert_local
        self.calls: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def download_artifact(self, url, dest_dir, *, filename=None, expected_sha256=None):
        self.calls.append(("download_artifact", url, expected_sha256))
        p = self._download_to or (Path(dest_dir) / "fetched.bin")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"FETCHED")
        return p

    async def convert_model(self, **kwargs):
        self.calls.append(("convert_model", kwargs))
        local = self._convert_local
        if local is not None:
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(b"CONVERTED")
            return {"local_path": str(local), "decisions": [{"choice": "int8 quantize"}], "warnings": []}
        return {"local_path": None, "warnings": ["cloud-only artifact; nothing to download"]}

    async def call_tool_dict(self, name, args):
        self.calls.append(("call_tool_dict", name))
        if name == "profile_device_plan":
            return {"plan_id": "p1", "kind": "bin", "workspace": "/w",
                    "remote_model": "/w/models/m.bin", "runtime_label": "npu",
                    "strategy": "cli:qnn-net-run", "parse": "snpe_net_run",
                    "files": [{"role": "model", "remote_path": "/w/models/m.bin", "content": ""}],
                    "steps": [{"id": "run", "label": "qnn-net-run", "shell": "qnn-net-run …", "timeout_s": 65}],
                    "unsupported_reason": ""}
        # profile_device_report
        return {"devices": [{"ok": True, "runtime_used": "npu"}], "comparison": {}, "recommendations": [],
                "report_md": "# Profiling report\n## Summary\nok"}


def _patch(monkeypatch, client):
    # The command does `from .client import create_client` at call time, so the
    # name resolves from the client module — patch it there.
    from devrel_client import client as client_mod
    monkeypatch.setattr(client_mod, "create_client", lambda **kw: client)

    def _fake_exec(plan, *, model_path, transport, target, probe_device=True):
        return {"step_outputs": [{"id": "run", "returncode": 0, "stdout": "Total Inference Time: 2.4 ms", "stderr": ""}],
                "device_info": {"arch": "aarch64"}, "log": [], "error": ""}

    # device_agent is imported inside the command as `from .local import device_agent`,
    # so patching the module attribute is what the command sees.
    from devrel_client.local import device_agent
    monkeypatch.setattr(device_agent, "execute_plan", _fake_exec)


class TestModelSources:
    def test_from_server_downloads_then_profiles(self, runner, monkeypatch, tmp_path):
        client = _FakeClient()
        _patch(monkeypatch, client)
        r = runner.invoke(app, [
            "profile-device", "--model-from-server", "/bundles/x/download?d=1&h=2",
            "--sha256", "abc", "--transport", "ssh", "--host", "root@board",
        ])
        assert r.exit_code == 0, r.output
        assert any(c[0] == "download_artifact" and c[2] == "abc" for c in client.calls)
        assert "Profiling report" in r.output

    def test_convert_then_profiles(self, runner, monkeypatch, tmp_path):
        conv_local = tmp_path / "out.bin"
        client = _FakeClient(convert_local=conv_local)
        _patch(monkeypatch, client)
        src = tmp_path / "src.onnx"
        src.write_bytes(b"ONNX")
        r = runner.invoke(app, [
            "profile-device", "--convert", "--model", str(src),
            "--source-format", "onnx", "--target-sdk", "qnn", "--quantization", "int8",
            "--transport", "ssh", "--host", "root@board", "--keep",
        ])
        assert r.exit_code == 0, r.output
        conv = next((c for c in client.calls if c[0] == "convert_model"), None)
        assert conv is not None
        assert conv[1]["quantization"] == "int8" and conv[1]["target_sdk"] == "qnn"
        assert conv[1]["upload"] == str(src)
        assert "converted (qnn/int8)" in r.output

    def test_convert_no_local_path_errors(self, runner, monkeypatch, tmp_path):
        client = _FakeClient(convert_local=None)  # convert returns no local_path
        _patch(monkeypatch, client)
        src = tmp_path / "src.onnx"
        src.write_bytes(b"ONNX")
        r = runner.invoke(app, [
            "profile-device", "--convert", "--model", str(src),
            "--transport", "ssh", "--host", "root@board",
        ])
        assert r.exit_code == 1
        assert "no local artifact" in r.output


class TestValidation:
    def test_no_source_errors(self, runner):
        r = runner.invoke(app, ["profile-device", "--transport", "ssh", "--host", "root@board"])
        assert r.exit_code == 2
        assert "exactly one model source" in r.output

    def test_two_sources_errors(self, runner, tmp_path):
        m = tmp_path / "m.bin"
        m.write_bytes(b"X")
        r = runner.invoke(app, [
            "profile-device", "--model", str(m), "--model-from-server", "/bundles/x/download",
            "--transport", "ssh", "--host", "root@board",
        ])
        assert r.exit_code == 2
        assert "exactly one model source" in r.output

    def test_ssh_requires_host(self, runner, tmp_path):
        m = tmp_path / "m.bin"
        m.write_bytes(b"X")
        r = runner.invoke(app, ["profile-device", "--model", str(m), "--transport", "ssh"])
        assert r.exit_code == 2
        assert "requires --host" in r.output

    def test_missing_local_model(self, runner):
        r = runner.invoke(app, [
            "profile-device", "--model", "/no/such.bin", "--transport", "ssh", "--host", "root@board",
        ])
        assert r.exit_code == 2
        assert "not found on this machine" in r.output
