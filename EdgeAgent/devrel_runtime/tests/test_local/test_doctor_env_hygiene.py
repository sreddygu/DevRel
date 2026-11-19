"""Phase 3 (IQ-9075 retrospective): client doctor env/venv hygiene checks.

Covers the new checks that catch the setup traps developers hit on the
IQ-9075 bring-up: Python 3.14 (no NPU wheels), the onnxruntime /
onnxruntime-qnn file-overwrite conflict, running NPU code from the wrong venv,
and the ANTHROPIC/QGENIE token aliases (issues 1, 2, 4, IQ9-2).
"""

from __future__ import annotations

from devrel_client.local import doctor


def _ver(major, minor, micro=0):
    """A stand-in for sys.version_info that supports tuple compare + attrs."""
    from collections import namedtuple

    VI = namedtuple("VI", "major minor micro releaselevel serial")
    return VI(major, minor, micro, "final", 0)


class TestPythonVersionBounds:
    def test_314_fails(self, monkeypatch):
        monkeypatch.setattr(doctor.sys, "version_info", _ver(3, 14, 0))
        r = doctor._check_python_version()
        assert r["status"] == "fail"
        assert "3.10 to 3.12" in r["message"]

    def test_312_passes(self, monkeypatch):
        monkeypatch.setattr(doctor.sys, "version_info", _ver(3, 12, 1))
        assert doctor._check_python_version()["status"] == "pass"

    def test_313_warns(self, monkeypatch):
        monkeypatch.setattr(doctor.sys, "version_info", _ver(3, 13, 0))
        assert doctor._check_python_version()["status"] == "warn"

    def test_39_fails(self, monkeypatch):
        monkeypatch.setattr(doctor.sys, "version_info", _ver(3, 9, 0))
        assert doctor._check_python_version()["status"] == "fail"


class TestOnnxruntimeConflict:
    def test_both_installed_fails(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions",
                            lambda: {"onnxruntime", "onnxruntime-qnn", "numpy"})
        r = doctor._check_onnxruntime_conflict()
        assert r["status"] == "fail"
        assert "pip uninstall onnxruntime" in r["message"]

    def test_only_qnn_passes(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions",
                            lambda: {"onnxruntime-qnn"})
        assert doctor._check_onnxruntime_conflict()["status"] == "pass"

    def test_only_base_warns(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions",
                            lambda: {"onnxruntime"})
        assert doctor._check_onnxruntime_conflict()["status"] == "warn"


class TestActiveVenvForNpu:
    def test_missing_qnn_warns(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions", lambda: {"numpy"})
        r = doctor._check_active_venv_for_npu()
        assert r["status"] == "warn"
        assert "onnxruntime-qnn" in r["message"]

    def test_qnn_on_x86_warns(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions", lambda: {"onnxruntime-qnn"})
        monkeypatch.setattr(doctor.sysconfig, "get_platform", lambda: "win-amd64")
        assert doctor._check_active_venv_for_npu()["status"] == "warn"

    def test_qnn_on_arm64_passes(self, monkeypatch):
        monkeypatch.setattr(doctor, "_installed_distributions", lambda: {"onnxruntime-qnn"})
        monkeypatch.setattr(doctor.sysconfig, "get_platform", lambda: "win-arm64")
        assert doctor._check_active_venv_for_npu()["status"] == "pass"


class TestModelAccessToken:
    def test_qgenie_key_passes(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("QGENIE_API_KEY", "x")
        assert doctor._check_model_access_token()["status"] == "pass"

    def test_none_set_warns(self, monkeypatch):
        for k in ("QGENIE_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            monkeypatch.delenv(k, raising=False)
        r = doctor._check_model_access_token()
        assert r["status"] == "warn"
        assert "same credential" in r["message"].lower()
