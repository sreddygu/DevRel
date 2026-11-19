"""Phase 4 (IQ-9075 retrospective): ONNX Runtime version capture in detect.

ORT version drives a 2.4x latency swing on identical hardware (retrospective
PDF §2.2 / issue IQ9-17), so detect_hardware records it. IQ9-19: a
python_path_extra hook lets ORT installed off the default path be found.
"""

from __future__ import annotations

import sys
import types

from devrel_client.local import hardware


class TestOrtInfo:
    def test_reports_none_when_absent(self, monkeypatch):
        # Ensure onnxruntime import fails.
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        info = hardware._ort_info()
        assert info["ort_version"] is None
        assert info["ort_providers"] == []

    def test_reports_version_and_providers(self, monkeypatch):
        fake = types.ModuleType("onnxruntime")
        fake.__version__ = "1.27.0"
        fake.get_available_providers = lambda: ["QNNExecutionProvider", "CPUExecutionProvider"]
        monkeypatch.setitem(sys.modules, "onnxruntime", fake)
        info = hardware._ort_info()
        assert info["ort_version"] == "1.27.0"
        assert "QNNExecutionProvider" in info["ort_providers"]

    def test_python_path_extra_is_added(self, monkeypatch, tmp_path):
        added = str(tmp_path / "custom_site")
        fake = types.ModuleType("onnxruntime")
        fake.__version__ = "1.24.4"
        fake.get_available_providers = lambda: ["CPUExecutionProvider"]
        monkeypatch.setitem(sys.modules, "onnxruntime", fake)
        hardware._ort_info(python_path_extra=[added])
        assert added in sys.path

    def test_detect_hardware_includes_ort_keys(self, monkeypatch):
        fake = types.ModuleType("onnxruntime")
        fake.__version__ = "1.27.0"
        fake.get_available_providers = lambda: ["CPUExecutionProvider"]
        monkeypatch.setitem(sys.modules, "onnxruntime", fake)
        profile = hardware.detect_hardware(sdk_probe=False, enrich=False)
        assert profile["ort_version"] == "1.27.0"
        assert "ort_providers" in profile
