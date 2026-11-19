"""Drift canary: detect_hardware()'s envelope must match the server's
DeviceProfile keys. If DevRel adds a *required* field, this test fails so we know
to re-vendor.

The server's DeviceProfile also carries OPTIONAL fields (board_id,
recommended_sdk, and the canonical SoC-registry facts: soc_sku, htp_arch,
dsp_abi, sdk_abi_band, min_qairt_version, firmware_band, memory_tier,
thermal_envelope, supports_int4, aihub_slug). Those are populated by the
*server's* registry-enriched hardware_detect and flow through the SDK
(discovery_source="server"); the client-light static probe does not synthesize
them, so they are intentionally NOT in the required local envelope.
"""

from __future__ import annotations

from devrel_client.local import detect_hardware, envelope_keys

# The REQUIRED core keys — always present in a local probe. Hardcoded from
# DevRel/src/devrel/models/device.py (the non-optional fields).
EXPECTED_KEYS = frozenset({
    "chipset",
    "platform",
    "cpu_cores",
    "cpu_arch",
    "cpu_freq_ghz",
    "gpu_model",
    "gpu_tflops",
    "npu_model",
    "npu_tops",
    "ram_gb",
    "sdk_path",
    "sdk_version",
    "available_runtimes",
    "gpu_backend_available",
})

# Optional server fields the client tolerates but does not require locally.
OPTIONAL_SERVER_KEYS = frozenset({
    "board_id", "recommended_sdk", "soc_sku", "htp_arch", "dsp_abi",
    "sdk_abi_band", "min_qairt_version", "firmware_band", "memory_tier",
    "thermal_envelope", "supports_int4", "aihub_slug",
    "storage_gb", "os_version",
})


def test_envelope_includes_all_device_profile_keys() -> None:
    profile = detect_hardware(sdk_probe=False, enrich=False)
    missing = EXPECTED_KEYS - profile.keys()
    assert not missing, f"missing keys: {sorted(missing)}"


def test_local_probe_tags_provenance() -> None:
    """A local static probe must label itself, not masquerade as authoritative."""
    profile = detect_hardware(sdk_probe=False, enrich=False)
    assert profile["discovery_source"] == "client-local-static"
    assert "host_os" in profile  # real OS recorded even if platform is coerced


def test_enriched_envelope_adds_ui_and_tips() -> None:
    profile = detect_hardware(sdk_probe=False, enrich=True)
    assert "ui" in profile and isinstance(profile["ui"], str)
    assert "tips" in profile and isinstance(profile["tips"], list)


def test_envelope_keys_module_level_matches() -> None:
    """The published envelope_keys() tuple is the single source of truth."""
    assert set(envelope_keys()) == EXPECTED_KEYS


def test_types_match_schema() -> None:
    profile = detect_hardware(sdk_probe=False, enrich=False)
    assert isinstance(profile["chipset"], str)
    assert isinstance(profile["cpu_cores"], int) and profile["cpu_cores"] >= 1
    assert isinstance(profile["cpu_freq_ghz"], float) and profile["cpu_freq_ghz"] > 0
    assert isinstance(profile["ram_gb"], float) and profile["ram_gb"] > 0
    assert isinstance(profile["available_runtimes"], list)
    assert isinstance(profile["gpu_backend_available"], bool)
    assert profile["sdk_path"] is None or isinstance(profile["sdk_path"], str)
