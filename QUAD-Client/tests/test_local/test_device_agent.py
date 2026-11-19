"""Tests for the client-side profiling agent (device_agent.execute_plan, #32).

Uses a fake transport (stub run_remote/push_file / adb) so no real board is
needed. Asserts the executor pushes the right files, runs the plan's steps in
order, collects raw outputs, and captures failures instead of raising.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quad_mcp_client.local import device_agent
from quad_mcp_client.local.board.ssh import CommandResult


def _ok(stdout="", stderr="", rc=0):
    return CommandResult(returncode=rc, stdout=stdout, stderr=stderr, elapsed_ms=1.0)


class _Recorder:
    def __init__(self, run_map=None, run_default=None, push_result=None):
        self.run_map = run_map or {}
        self.run_default = run_default or _ok("")
        self.push_result = push_result or _ok("")
        self.runs: list[str] = []
        self.pushes: list[tuple[str, str]] = []

    def run(self, transport, target, shell, *, timeout_s):
        self.runs.append(shell)
        for needle, resp in self.run_map.items():
            if needle in shell:
                return resp
        return self.run_default

    def push(self, transport, target, src, dst, *, timeout_s):
        self.pushes.append((str(src), dst))
        return self.push_result


@pytest.fixture
def model(tmp_path) -> Path:
    p = tmp_path / "ctx.bin"
    p.write_bytes(b"MODEL" * 20)
    return p


def _plan_bin(workspace="/data/local/tmp/quad"):
    return {
        "plan_id": "bin-1",
        "kind": "bin",
        "workspace": workspace,
        "remote_model": f"{workspace}/models/ctx.bin",
        "runtime_label": "npu",
        "strategy": "cli:qnn-net-run",
        "parse": "snpe_net_run",
        "files": [{"role": "model", "remote_path": f"{workspace}/models/ctx.bin", "source_hint": "ctx.bin", "content": ""}],
        "steps": [{"id": "run", "label": "qnn-net-run", "shell": "qnn-net-run --retrieve_context …", "timeout_s": 65}],
        "unsupported_reason": "",
    }


def _plan_onnx(workspace="/data/local/tmp/quad"):
    return {
        "plan_id": "onnx-1", "kind": "onnx", "workspace": workspace,
        "remote_model": f"{workspace}/models/m.onnx", "runtime_label": "unknown",
        "strategy": "python-ort", "parse": "python_ort",
        "files": [
            {"role": "model", "remote_path": f"{workspace}/models/m.onnx", "source_hint": "m.onnx", "content": ""},
            {"role": "bench_script", "remote_path": f"{workspace}/quad_bench.py", "source_hint": "", "content": "import onnxruntime\nprint('bench')\n"},
        ],
        "steps": [{"id": "bench", "label": "python-ort", "shell": "python3 quad_bench.py …", "timeout_s": 95}],
        "unsupported_reason": "",
    }


class TestExecutePlan:
    def test_bin_pushes_model_and_runs_step(self, monkeypatch, model):
        rec = _Recorder(run_map={"qnn-net-run": _ok("Total Inference Time: 2.41 ms")})
        monkeypatch.setattr(device_agent, "_run", rec.run)
        monkeypatch.setattr(device_agent, "_push", rec.push)

        out = device_agent.execute_plan(_plan_bin(), model_path=model, transport="ssh", target=object())

        assert out["error"] == ""
        # model pushed to the plan's remote path
        assert any(dst.endswith("/models/ctx.bin") for _, dst in rec.pushes)
        # the step ran and its raw output was captured
        assert len(out["step_outputs"]) == 1
        assert out["step_outputs"][0]["id"] == "run"
        assert "2.41 ms" in out["step_outputs"][0]["stdout"]
        # device_info was probed
        assert "arch" in out["device_info"] or out["device_info"] == {}

    def test_onnx_pushes_model_and_bench_script(self, monkeypatch, tmp_path):
        m = tmp_path / "m.onnx"
        m.write_bytes(b"onnx" * 20)
        rec = _Recorder(run_map={"quad_bench.py": _ok('{"ok": true, "mean_ms": 40.0}')})
        monkeypatch.setattr(device_agent, "_run", rec.run)
        monkeypatch.setattr(device_agent, "_push", rec.push)

        out = device_agent.execute_plan(_plan_onnx(), model_path=m, transport="ssh", target=object())

        assert out["error"] == ""
        dests = [dst for _, dst in rec.pushes]
        # both the model and the generated bench script were pushed
        assert any(d.endswith("/models/m.onnx") for d in dests)
        assert any(d.endswith("quad_bench.py") for d in dests)
        assert out["step_outputs"][0]["id"] == "bench"

    def test_missing_model_errors(self, monkeypatch, tmp_path):
        rec = _Recorder()
        monkeypatch.setattr(device_agent, "_run", rec.run)
        monkeypatch.setattr(device_agent, "_push", rec.push)
        out = device_agent.execute_plan(
            _plan_bin(), model_path=tmp_path / "nope.bin", transport="ssh", target=object()
        )
        assert "model not found" in out["error"]
        assert rec.pushes == []

    def test_push_failure_is_captured(self, monkeypatch, model):
        rec = _Recorder(push_result=_ok(stderr="No space left on device", rc=1))
        monkeypatch.setattr(device_agent, "_run", rec.run)
        monkeypatch.setattr(device_agent, "_push", rec.push)
        out = device_agent.execute_plan(_plan_bin(), model_path=model, transport="ssh", target=object())
        assert "push failed" in out["error"]
        # never ran the step after a failed push
        assert out["step_outputs"] == []

    def test_adb_transport_dispatch(self, monkeypatch, model):
        seen = {}

        def fake_run(transport, target, shell, *, timeout_s):
            seen["transport"] = transport
            return _ok("Total Inference Time: 3.0 ms")

        def fake_push(transport, target, src, dst, *, timeout_s):
            return _ok("")

        monkeypatch.setattr(device_agent, "_run", fake_run)
        monkeypatch.setattr(device_agent, "_push", fake_push)
        out = device_agent.execute_plan(_plan_bin(), model_path=model, transport="adb", target="SERIAL", probe_device=False)
        assert seen["transport"] == "adb"
        assert out["step_outputs"][0]["stdout"].endswith("3.0 ms")
