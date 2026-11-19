"""Local hardware probe.

Returns a dict matching the server-side ``DeviceProfile.model_dump()``
envelope so any caller can use it interchangeably with what the MCP
``hardware_detect`` tool returns.

Field provenance:
  * platform/CPU/RAM   -> per-OS module under ``_platform/``
  * gpu_*, npu_*       -> ``capabilities.lookup_for_chipset()`` (vendored 4-entry table)
  * sdk_path/version   -> ``sdk_scan.find_sdk()`` (env -> sibling -> vendor defaults)
  * available_runtimes -> derived from chipset match + optional ``qnn-platform-validator`` probe
  * gpu_backend_available -> SDK probe only; defaults to False without it
  * ui / tips          -> ``render`` (when ``enrich=True``)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

from . import capabilities, render, sdk_scan
from ._platform import linux as linux_probe
from ._platform import macos as macos_probe
from ._platform import windows as windows_probe

# Order matches the DeviceProfile model. Keep in sync with the contract test.
_ENVELOPE_KEYS: tuple[str, ...] = (
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
)


def _detect_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    return "linux"  # treat unknown unix-likes as linux


def _probe_for_platform(plat: str) -> dict[str, Any]:
    if plat == "windows":
        return windows_probe.probe()
    if plat == "macos":
        return macos_probe.probe()
    return linux_probe.probe()


def _run_validator() -> dict[str, Any] | None:
    """Best-effort `qnn-platform-validator --backend all` probe.

    Returns ``{available_runtimes: [...], gpu_backend_available: bool}`` or
    ``None`` when the validator isn't on PATH or fails.
    """
    exe = shutil.which("qnn-platform-validator")
    if exe is None:
        return None
    try:
        result = subprocess.run(
            [exe, "--backend", "all"],
            capture_output=True,
            text=True,
            timeout=20.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    out = (result.stdout or "") + "\n" + (result.stderr or "")
    runtimes: list[str] = []
    if "CPU" in out and "PASS" in out.split("CPU", 1)[1][:200].upper():
        runtimes.append("cpu")
    elif "cpu" in out.lower():
        runtimes.append("cpu")
    if "GPU" in out and "PASS" in out:
        runtimes.append("gpu")
    if "HTP" in out or "DSP" in out:
        runtimes.append("npu")
    # Dedupe while preserving order
    seen: set[str] = set()
    runtimes = [r for r in runtimes if r in {"cpu", "gpu", "npu"} and not (r in seen or seen.add(r))]
    return {
        "available_runtimes": runtimes or ["cpu"],
        "gpu_backend_available": "gpu" in runtimes,
    }


def _ort_info(python_path_extra: list[str] | None = None) -> dict[str, Any]:
    """Best-effort ONNX Runtime version + available providers.

    ORT version matters enormously for profiling comparisons (1.22.1 = 67 FPS
    vs 1.27.0 = 163 FPS on identical hardware — IQ-9075 retrospective PDF §2.2 /
    issue IQ9-17). Capturing it makes benchmark numbers reproducible and
    comparable. ``python_path_extra`` lets a caller add non-standard install
    locations so ORT isn't reported MISSING when it's installed off the default
    path (issue IQ9-19).

    Returns ``{ort_version, ort_providers}`` — version is ``None`` when ORT
    isn't importable in the active interpreter.
    """
    if python_path_extra:
        for p in python_path_extra:
            if p and p not in sys.path:
                sys.path.insert(0, p)
    try:
        import onnxruntime as ort  # noqa: PLC0415
    except ImportError:
        return {"ort_version": None, "ort_providers": []}
    try:
        providers = list(ort.get_available_providers())
    except Exception:  # noqa: BLE001 - never let a probe crash detection
        providers = []
    return {"ort_version": getattr(ort, "__version__", None), "ort_providers": providers}


def detect_hardware(
    platform: str | None = None,
    *,
    enrich: bool = True,
    sdk_probe: bool = True,
    python_path_extra: list[str] | None = None,
) -> dict[str, Any]:
    """Local hardware probe; returns a DeviceProfile-shaped dict.

    Args:
        platform: override OS detection (``windows``/``linux``/``macos``/``android``).
            ``android`` is accepted for envelope compatibility but probed as linux.
        enrich: when True, attach ``ui`` (markdown) and ``tips`` (list[str]) keys.
        sdk_probe: when True, run ``qnn-platform-validator`` if on PATH to populate
            ``available_runtimes`` / ``gpu_backend_available``. Skip when the
            caller wants a pure-python answer.
        python_path_extra: extra sys.path entries for the ONNX Runtime probe, so
            ORT installed off the default path is still detected (issue IQ9-19).
    """
    plat = platform or _detect_platform()
    raw = _probe_for_platform("linux" if plat == "android" else plat)

    chipset = raw.get("chipset") or "unknown"
    cap = capabilities.lookup_for_chipset(chipset)

    sdk_path, sdk_version = sdk_scan.find_sdk()

    # Runtime list: validator probe wins; otherwise infer from chipset match.
    validator_result = _run_validator() if sdk_probe else None
    if validator_result is not None:
        available_runtimes = validator_result["available_runtimes"]
        gpu_backend_available = validator_result["gpu_backend_available"]
    else:
        available_runtimes = ["cpu"]
        if cap is not None:
            available_runtimes.append("npu")
        gpu_backend_available = False

    profile: dict[str, Any] = {
        "chipset": chipset,
        "platform": plat if plat in {"windows", "linux", "android"} else "linux",
        "cpu_cores": int(raw.get("cpu_cores") or 0),
        "cpu_arch": raw.get("cpu_arch") or "unknown",
        "cpu_freq_ghz": float(raw.get("cpu_freq_ghz") or 0.0),
        "gpu_model": (cap or {}).get("gpu_model", "unknown"),
        "gpu_tflops": float((cap or {}).get("gpu_tflops", 0.0)),
        "npu_model": (cap or {}).get("npu_model", "unknown"),
        "npu_tops": float((cap or {}).get("npu_tops", 0.0)),
        "ram_gb": float(raw.get("ram_gb") or 0.0),
        "storage_gb": (float(raw["storage_gb"]) if raw.get("storage_gb") else None),
        "os_version": raw.get("os_version") or None,
        "sdk_path": sdk_path,
        "sdk_version": sdk_version,
        "available_runtimes": available_runtimes,
        "gpu_backend_available": gpu_backend_available,
        # Provenance: this is a LOCAL client-side probe from a static, vendored
        # capability table — not the authoritative server detection. The
        # server's hardware_detect (registry-enriched) is the source of truth;
        # see detect_hardware_server_first(). host_os records the real OS even
        # when platform is coerced (e.g. a macOS dev box probing a Linux target
        # envelope) so we never silently claim macOS *is* Linux.
        "discovery_source": "client-local-static",
        "host_os": plat,
    }

    # ONNX Runtime version + providers — captured so profiling/benchmark output
    # is reproducible and comparable across ORT versions (issue IQ9-17). Extra
    # keys (not part of the strict DeviceProfile envelope).
    profile.update(_ort_info(python_path_extra))

    # Defensive: if cpu_cores is 0 (probe failed), bump to 1 so callers that
    # do `cores * something` don't divide-by-zero. The probe-failure signal
    # is the chipset == "unknown" -- not the cores count.
    if profile["cpu_cores"] == 0:
        profile["cpu_cores"] = 1
    if profile["cpu_freq_ghz"] == 0.0:
        profile["cpu_freq_ghz"] = 0.001  # bare minimum to satisfy gt=0 in DeviceProfile
    if profile["ram_gb"] == 0.0:
        profile["ram_gb"] = 0.1

    if enrich:
        profile["ui"] = render.format_device(profile)
        profile["tips"] = render.tips_for("detect", n=2)

    return profile


def envelope_keys() -> tuple[str, ...]:
    """Public access to the ordered DeviceProfile key tuple. Used by tests."""
    return _ENVELOPE_KEYS


def detect_hardware_server_first(
    platform: str | None = None,
    *,
    enrich: bool = True,
    sdk_probe: bool = True,
    allow_local_fallback: bool = True,
) -> dict[str, Any]:
    """Prefer the SERVER's authoritative hardware_detect; fall back to local.

    The client-side static table (``capabilities.py``) is a small, drifting
    mirror that cannot scale to Qualcomm's SoC matrix. The server's
    ``hardware_detect`` is registry-enriched (canonical SoC SKU, HTP arch,
    AI Hub Models slug, INT4 support, …) and is the source of truth. This queries it
    over whatever transport the environment resolves (``DevRel_MCP_URL`` /
    ``.claude/settings.json`` / a local spawn), tagging the result
    ``discovery_source="server"``.

    On any connection/tool error it degrades to the local static probe (tagged
    ``client-local-static``) when ``allow_local_fallback`` — so an offline dev
    box still gets an answer, but the provenance is always explicit. Set
    ``allow_local_fallback=False`` to require the authoritative answer.
    """
    server_platform = platform if platform in {"windows", "linux", "android", "gateway", "robotics"} else None
    if server_platform is not None:
        try:
            profile = _query_server(server_platform)
            if profile is not None:
                profile["discovery_source"] = "server"
                if enrich:
                    profile.setdefault("ui", render.format_device(profile))
                    profile.setdefault("tips", render.tips_for("detect", n=2))
                return profile
        except Exception as exc:  # noqa: BLE001 - server unreachable / tool error
            if not allow_local_fallback:
                raise RuntimeError(
                    "Server hardware_detect was required (allow_local_fallback="
                    f"False) but failed: {exc}"
                ) from exc

    if not allow_local_fallback and server_platform is not None:
        raise RuntimeError(
            "Server hardware_detect was required (allow_local_fallback=False) "
            "but the DevRel MCP server was unreachable."
        )
    return detect_hardware(platform=platform, enrich=enrich, sdk_probe=sdk_probe)


def _query_server(platform: str) -> dict[str, Any] | None:
    """Call the server's hardware_detect via the DevRelClient SDK (sync wrapper)."""
    import asyncio

    from devrel_client import create_client

    async def _run() -> dict[str, Any]:
        async with create_client() as client:
            return await client.hardware_detect(platform=platform)  # type: ignore[arg-type]

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # Already inside an event loop (rare for the CLI) — use a fresh loop.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
