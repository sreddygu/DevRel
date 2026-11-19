"""Phase 4 (IQ-9075 retrospective): board config portability + backend/artifact lock.

- configure_template must not be UNO Q-only; it renders per-board specs
  (issues IQ9-8/22).
- A compiled HTP .bin cannot run on the GPU/CPU backend (issue IQ9-35).
"""

from __future__ import annotations

import pytest

from devrel_client import qnn_utils
from devrel_client.local.board import commands as ops


class TestConfigureTemplateBoards:
    def test_default_is_unoq(self):
        toml = ops.configure_template(host="h").details["toml"]
        assert 'board = "arduino-unoq"' in toml
        assert 'soc = "qcs2210"' in toml
        assert 'hexagon = "v66"' in toml

    def test_iq9075_profile(self):
        r = ops.configure_template(host="10.0.0.9", board="iq9075")
        toml = r.details["toml"]
        assert 'board = "iq9075"' in toml
        assert 'soc = "qcs9075"' in toml
        assert 'hexagon = "v73"' in toml
        assert 'preferred_runtime = "htp"' in toml
        assert r.details["board"] == "iq9075"

    def test_unknown_board_falls_back_with_note(self):
        r = ops.configure_template(host="h", board="totally-unknown")
        toml = r.details["toml"]
        assert "unknown board" in toml
        assert 'soc = "qcs2210"' in toml  # UNO Q fallback

    def test_custom_port_rendered(self):
        toml = ops.configure_template(host="h", port=2222).details["toml"]
        assert "port = 2222" in toml


class TestBackendArtifactLock:
    def test_htp_bin_on_gpu_rejected(self):
        with pytest.raises(ValueError, match="backend-locked"):
            qnn_utils.validate_backend_artifact("model.bin", "gpu")

    def test_htp_bin_on_cpu_rejected(self):
        with pytest.raises(ValueError, match="backend-locked"):
            qnn_utils.validate_backend_artifact("model.bin", "cpu")

    def test_htp_bin_on_htp_ok(self):
        qnn_utils.validate_backend_artifact("model.bin", "htp")  # no raise

    def test_dlc_on_gpu_ok(self):
        qnn_utils.validate_backend_artifact("model.dlc", "gpu")  # no raise
