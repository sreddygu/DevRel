"""Unit tests for the onnxruntime-qnn NPU helper (devrel_client.ort_qnn).

These stub ``onnxruntime`` entirely so the QNN EP behaviour — no silent CPU
fallback, provider verification, per-layer split parsing, warmup, and the
double-registration guard — is covered without any real NPU or the win-arm64
wheels. Mirrors the IQ-9075 retrospective fixes (issues 8, 9, 11, 12, 21, 32).
"""

from __future__ import annotations

import json
import sys
import types

import pytest

np = pytest.importorskip("numpy")  # samples-extra dep; skip cleanly if absent

from devrel_client import ort_qnn  # noqa: E402

# ─── Fake onnxruntime ────────────────────────────────────────────────────────


class _FakeSession:
    def __init__(self, active_providers, *, inputs=None, outputs=None):
        self._providers = list(active_providers)
        self._inputs = inputs or [types.SimpleNamespace(name="input", shape=[1, 3, 4, 4])]
        self._outputs = outputs or [types.SimpleNamespace(name="output")]
        self.run_calls = 0
        self._profile_path = None

    def get_providers(self):
        return self._providers

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs

    def run(self, output_names, feeds):
        self.run_calls += 1
        return [np.zeros((1, 1000), dtype=np.float32)]

    def end_profiling(self):
        return self._profile_path or ""


def _make_fake_ort(*, available, active, profile_path=None, capture=None):
    """Build a fake onnxruntime module.

    available: providers get_available_providers() returns.
    active: providers the created session reports (first = active).
    """
    mod = types.ModuleType("onnxruntime")

    class SessionOptions:
        def __init__(self):
            self.enable_profiling = False

    def InferenceSession(path, sess_options=None, providers=None):  # noqa: N802
        if capture is not None:
            capture["providers"] = providers
            capture["path"] = path
        sess = _FakeSession(active)
        sess._profile_path = profile_path
        return sess

    mod.get_available_providers = lambda: list(available)
    mod.SessionOptions = SessionOptions
    mod.InferenceSession = InferenceSession
    return mod


@pytest.fixture(autouse=True)
def _reset_guard():
    ort_qnn.reset_registration_guard()
    yield
    ort_qnn.reset_registration_guard()


@pytest.fixture
def fake_ort(monkeypatch):
    def _install(**kwargs):
        mod = _make_fake_ort(**kwargs)
        monkeypatch.setitem(sys.modules, "onnxruntime", mod)
        return mod

    return _install


# ─── create_npu_session ──────────────────────────────────────────────────────


class TestCreateNpuSession:
    def test_npu_active_returns_session(self, fake_ort):
        fake_ort(available=["QNNExecutionProvider", "CPUExecutionProvider"],
                 active=["QNNExecutionProvider", "CPUExecutionProvider"])
        sess = ort_qnn.create_npu_session("m.onnx")
        assert sess.get_providers()[0] == "QNNExecutionProvider"

    def test_silent_fallback_raises(self, fake_ort):
        # QNN available but the session fell back to CPU (init failed) —
        # must raise instead of silently running on CPU.
        fake_ort(available=["QNNExecutionProvider", "CPUExecutionProvider"],
                 active=["CPUExecutionProvider"])
        with pytest.raises(ort_qnn.NPUFallbackError) as exc:
            ort_qnn.create_npu_session("m.onnx")
        assert exc.value.active_provider == "CPUExecutionProvider"

    def test_fallback_allowed_when_opted_in(self, fake_ort):
        fake_ort(available=["QNNExecutionProvider", "CPUExecutionProvider"],
                 active=["CPUExecutionProvider"])
        sess = ort_qnn.create_npu_session("m.onnx", allow_fallback=True)
        assert sess.get_providers()[0] == "CPUExecutionProvider"

    def test_missing_qnn_ep_raises_clear_error(self, fake_ort):
        # Plain onnxruntime installed → no QNN EP at all.
        fake_ort(available=["CPUExecutionProvider"], active=["CPUExecutionProvider"])
        with pytest.raises(RuntimeError, match="onnxruntime-qnn"):
            ort_qnn.create_npu_session("m.onnx")

    def test_provider_list_order_and_backend_path(self, fake_ort):
        capture: dict = {}
        fake_ort(available=["QNNExecutionProvider", "CPUExecutionProvider"],
                 active=["QNNExecutionProvider"], capture=capture)
        ort_qnn.create_npu_session("m.onnx")
        providers = capture["providers"]
        assert providers[0][0] == "QNNExecutionProvider"
        assert "backend_path" in providers[0][1]
        assert providers[-1] == "CPUExecutionProvider"

    def test_cache_dir_enables_context(self, fake_ort, tmp_path):
        capture: dict = {}
        fake_ort(available=["QNNExecutionProvider"], active=["QNNExecutionProvider"],
                 capture=capture)
        ort_qnn.create_npu_session("m.onnx", cache_dir=tmp_path)
        opts = capture["providers"][0][1]
        assert opts.get("ep.context_enable") == "1"
        assert "qnn_context.onnx" in opts.get("ep.context_file_path", "")


# ─── assert_npu_active ───────────────────────────────────────────────────────


class TestAssertNpuActive:
    def test_passes_when_npu_first(self):
        sess = _FakeSession(["QNNExecutionProvider", "CPUExecutionProvider"])
        ort_qnn.assert_npu_active(sess)  # no raise

    def test_raises_when_cpu_first(self):
        sess = _FakeSession(["CPUExecutionProvider"])
        with pytest.raises(ort_qnn.NPUFallbackError):
            ort_qnn.assert_npu_active(sess)


# ─── warmup ──────────────────────────────────────────────────────────────────


class TestWarmup:
    def test_runs_n_times(self, capsys):
        sess = _FakeSession(["QNNExecutionProvider"])
        ort_qnn.warmup(sess, {"input": np.zeros((1, 3, 4, 4), np.float32)}, n=3)
        assert sess.run_calls == 3
        out = capsys.readouterr().out
        assert "excluded from timing" in out


# ─── double-registration guard ───────────────────────────────────────────────


class TestRegistrationGuard:
    def test_guard_flips_after_session(self, fake_ort):
        assert ort_qnn.is_double_registered() is False
        fake_ort(available=["QNNExecutionProvider"], active=["QNNExecutionProvider"])
        ort_qnn.create_npu_session("m.onnx")
        assert ort_qnn.is_double_registered() is True


# ─── provider_split ──────────────────────────────────────────────────────────


class TestProviderSplit:
    def test_parses_profiling_json(self, fake_ort, tmp_path):
        events = [
            {"cat": "Node", "name": "Conv_0", "args": {"node_name": "Conv_0", "provider": "QNNExecutionProvider"}},
            {"cat": "Node", "name": "Conv_2", "args": {"node_name": "Conv_2", "provider": "QNNExecutionProvider"}},
            {"cat": "Node", "name": "Softmax_3", "args": {"node_name": "Softmax_3", "provider": "CPUExecutionProvider"}},
        ]
        prof = tmp_path / "prof.json"
        prof.write_text(json.dumps(events))
        fake_ort(available=["QNNExecutionProvider", "CPUExecutionProvider"],
                 active=["QNNExecutionProvider"], profile_path=str(prof))

        result = ort_qnn.provider_split("m.onnx")
        assert result["Conv_0"] == "QNNExecutionProvider"
        assert result["Softmax_3"] == "CPUExecutionProvider"
        s = result["summary"]
        assert s["total_nodes"] == 3
        assert s["on_npu"] == 2
        assert s["on_cpu"] == 1
        assert s["npu_percent"] == pytest.approx(66.7, abs=0.1)

    def test_graceful_when_no_provider_info(self, fake_ort, tmp_path):
        prof = tmp_path / "empty.json"
        prof.write_text(json.dumps([{"cat": "Node", "name": "x", "args": {}}]))
        fake_ort(available=["QNNExecutionProvider"], active=["QNNExecutionProvider"],
                 profile_path=str(prof))
        result = ort_qnn.provider_split("m.onnx")
        assert result["summary"]["total_nodes"] == 0
        assert "note" in result
