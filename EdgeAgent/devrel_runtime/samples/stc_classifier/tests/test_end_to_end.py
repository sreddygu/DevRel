"""End-to-end tests: ONNX -> mock convert -> codegen -> dry-run IPK build.

Each step is exercised against DevRel's mock adapters; no real cross-
compiler or gateway is required.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest


def _devrel_available():
    try:
        from devrel.core.operations.generate_code import generate_code  # noqa: F401
        from devrel.core.operations.profile_workload import profile_workload  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _devrel_available(),
    reason="DevRel core not installed in this venv (run.ps1 should install it editable)",
)


def test_generate_code_produces_modular_scaffold(tmp_path, sample_root):
    """generate_code with scaffold='modular' must emit the 17-file tree."""
    from devrel.core.operations.generate_code import generate_code

    out = asyncio.run(generate_code(
        platform="gateway",
        sdk="nwaios",
        language="c",
        model_path="/host/stc_classifier.bin",
        runtime="npu",
        target_arch="aarch64-openwrt-linux",
        scaffold="modular",
    ))
    assert "source_files" in out
    files = out["source_files"]
    assert len(files) >= 15, f"modular scaffold should emit >=15 files, got {len(files)}"
    for required in (
        "main.c",
        "tensor_io.c",
        "turnkey.c",
        "model_inferencing.c",
        "service.json",
        "ipk_control",
        "CMakeLists.txt",
    ):
        assert required in files, f"missing {required} from codegen output"


def test_service_json_compute_engine_is_set(app_dir):
    service = json.loads((app_dir / "service.json").read_text())
    assert service["nwaios"]["compute_engine"] in ("aim_htp", "nsp", "cpu")
    assert service["nwaios"]["model_path"].startswith("/var/run/nwaios/")


def test_profile_workload_mock_returns_nwaios_shape(sample_root):
    """Mock profile_workload(platform=gateway, runtime=npu) returns NWAIOS shape.

    With no real app running on a gateway, the mock NWAIOS profiler
    returns a structurally-correct report with zeros and a
    ``measurement_notes`` indicator. We check the shape, not the
    numeric values.
    """
    from devrel.adapters.factory import AdapterFactory
    from devrel.config import load_config
    from devrel.core.operations.profile_workload import profile_workload

    factory = AdapterFactory(load_config())
    report = asyncio.run(profile_workload(
        model_path="/var/run/nwaios/stc_classifier/m.bin",
        platform="gateway",
        runtime="npu",
        duration_s=2,
        factory=factory,
    ))
    assert "latency" in report
    latency = report["latency"]
    for key in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"):
        assert key in latency, f"latency missing {key}"
    assert "throughput_fps" in report
    # Mock without a running app returns zeros + measurement_notes; that
    # is correct behavior, not a failure mode.


def test_gwapps_dry_run_build(tmp_path, sample_root):
    """``GwappsBuilder.configure_cmd()`` must produce a sane cmake plan."""
    from devrel.build.gwapps import BuildConfig, GwappsBuilder

    # SDK lives in the sibling DevRel/ checkout under sdks/gwapps/<ver>/.
    # Auto-discovery walks up from devrelAgent and stops at devrelAgent's
    # pyproject.toml -- the SDK isn't reachable from there. Pin it.
    sdk_candidates = sorted(
        (sample_root.parent.parent.parent / "DevRel" / "sdks" / "gwapps").glob(
            "*-from-source-*"
        )
    )
    if not sdk_candidates:
        pytest.skip("gwapps SDK not vendored under DevRel/sdks/gwapps/")
    sdk_root = sdk_candidates[-1]

    config = BuildConfig(
        source_dir=sample_root / "app",
        target_arch="aarch64-openwrt-linux",
        build_dir=tmp_path / "build",
        sdk_root=sdk_root,
    )
    builder = GwappsBuilder(config)
    builder.validate_inputs()
    cmd = builder.configure_cmd()
    assert cmd[0] == "cmake"
    joined = " ".join(cmd)
    assert "GWAPPS_TARGET_ARCH=aarch64-openwrt-linux" in joined
    assert str(sample_root / "app") in joined


def test_gwapps_mock_deploy(tmp_path, sample_root):
    """Mock LCM deploy: GATEWAY_HOST unset -> MockLCMAdapter, returns running."""
    from devrel.device.manager import DeviceManager

    os.environ.pop("GATEWAY_HOST", None)

    fake_ipk = tmp_path / "stc_classifier.ipk"
    fake_ipk.write_bytes(b"FAKE_IPK_BYTES_FOR_MOCK_DEPLOY_TEST")

    mgr = DeviceManager()
    result = mgr.deploy(fake_ipk)
    assert result.ok, f"deploy failed: {result.error}; log={result.log}"
    assert result.app_record is not None
    # MockLCMAdapter places the app in 'running' state by default after
    # install + start (start=True is the default).
