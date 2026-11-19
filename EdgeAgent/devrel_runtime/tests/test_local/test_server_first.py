"""Tests for server-first hardware discovery (detect_hardware_server_first)."""

from __future__ import annotations

import pytest

from devrel_client.local import hardware


class TestServerFirst:
    def test_prefers_server_when_reachable(self, monkeypatch) -> None:
        server_profile = {
            "chipset": "Snapdragon 8 Elite SM8750",
            "soc_sku": "SM8750",
            "htp_arch": "v79",
            "aihub_slug": "qualcomm-snapdragon-8-elite",
        }
        monkeypatch.setattr(hardware, "_query_server", lambda platform: dict(server_profile))
        out = hardware.detect_hardware_server_first("android", enrich=False)
        assert out["discovery_source"] == "server"
        assert out["soc_sku"] == "SM8750"
        assert out["htp_arch"] == "v79"

    def test_falls_back_to_local_when_server_errors(self, monkeypatch) -> None:
        def _boom(platform):  # noqa: ANN001
            raise ConnectionError("server down")

        monkeypatch.setattr(hardware, "_query_server", _boom)
        out = hardware.detect_hardware_server_first(
            "android", enrich=False, sdk_probe=False
        )
        assert out["discovery_source"] == "client-local-static"

    def test_no_fallback_raises_when_required(self, monkeypatch) -> None:
        def _boom(platform):  # noqa: ANN001
            raise ConnectionError("server down")

        monkeypatch.setattr(hardware, "_query_server", _boom)
        with pytest.raises(RuntimeError):
            hardware.detect_hardware_server_first(
                "android", allow_local_fallback=False, sdk_probe=False
            )

    def test_macos_host_not_relabeled_as_linux(self, monkeypatch) -> None:
        """A macOS dev box probing locally records host_os=macos, not a silent
        claim that it *is* Linux."""
        monkeypatch.setattr(hardware, "_detect_platform", lambda: "macos")
        # macos probe returns minimal fields; force it deterministic
        monkeypatch.setattr(
            hardware, "_probe_for_platform",
            lambda plat: {"chipset": "Apple M3", "cpu_cores": 8, "cpu_arch": "arm64",
                          "cpu_freq_ghz": 3.0, "ram_gb": 16.0},
        )
        out = hardware.detect_hardware(platform="macos", enrich=False, sdk_probe=False)
        assert out["host_os"] == "macos"
        # platform is still coerced to linux for envelope-compat, but host_os is honest
        assert out["discovery_source"] == "client-local-static"
