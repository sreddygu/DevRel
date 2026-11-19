"""Local QUAD diagnostic suite.

Replicates the 10 highest-ROI checks from
``QUAD/src/quad/cli/doctor.py`` (commit 2485044) with no quad-agent
imports. Server-only checks (AdapterFactory init, ``quad.runtime``,
AIMET/AI Hub Models adapter ``.doctor()``, QHAS prerequisites) are
deliberately not in this list -- run the MCP doctor for those.

Each check returns ``{"name": str, "status": "pass"|"warn"|"fail",
"message": str}`` matching the server's ``CheckResult`` shape so the
formatter can render either source identically.

``real_mode=True`` mirrors the server's escalation: SDK env vars,
SDK tools, DSP env, and DLC compatibility warnings escalate to fail
with a "[real-mode strict] " prefix.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import sys
import sysconfig
from collections.abc import Callable
from pathlib import Path

CheckResult = dict[str, str]
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_REAL_MODE_ESCALATE = {
    "SDK env vars",
    "SDK tools in PATH",
    "DSP env (ADSP_LIBRARY_PATH)",
    "DLC compatibility (>=1.16)",
    "onnxruntime package conflict",
    "Active venv for NPU",
}


def _r(name: str, status: str, message: str) -> CheckResult:
    return {"name": name, "status": status, "message": message}


def _parse_version(s: str) -> tuple[int, int, int] | None:
    m = _VERSION_RE.search(s or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# ─── Individual checks (private) ─────────────────────────────────────


def _check_python_version() -> CheckResult:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    # onnxruntime-qnn / onnxruntime-genai wheels exist only for 3.10–3.12.
    # 3.14 (a perfectly normal "latest Python" install) fails with a cryptic
    # wheel error that never says which version is needed — so say it here.
    if v < (3, 10):
        return _r(
            "Python version",
            "fail",
            f"Python {ver} — need Python 3.10 to 3.12 (NPU wheels require it).",
        )
    if (v.major, v.minor) >= (3, 14):
        return _r(
            "Python version",
            "fail",
            f"Python {v.major}.{v.minor} is not supported — please use Python 3.10 to 3.12. "
            f"The onnxruntime-qnn NPU wheels are not built for 3.13+, so NPU support will "
            f"fail to install with a cryptic wheel error.",
        )
    if (v.major, v.minor) == (3, 13):
        return _r(
            "Python version",
            "warn",
            f"Python {ver} — onnxruntime-qnn wheels target 3.10–3.12. Prefer 3.12 for NPU work.",
        )
    return _r("Python version", "pass", f"Python {ver} (3.10–3.12, NPU-wheel compatible)")


def _check_quad_client_package() -> CheckResult:
    try:
        import quad_mcp_client  # type: ignore
    except ImportError as e:
        return _r("quad-mcp-client package", "fail", f"import quad_mcp_client failed: {e}")
    version = getattr(quad_mcp_client, "__version__", "unknown")
    return _r("quad-mcp-client package", "pass", f"version {version}")


def _check_sdk_env_vars() -> CheckResult:
    candidates = [
        ("QAIRT_SDK_ROOT", os.environ.get("QAIRT_SDK_ROOT", "")),
        ("QNN_SDK_ROOT", os.environ.get("QNN_SDK_ROOT", "")),
        ("SNPE_ROOT", os.environ.get("SNPE_ROOT", "")),
    ]
    set_vars = [(k, v) for k, v in candidates if v.strip()]
    if not set_vars:
        return _r("SDK env vars", "warn", "None of QAIRT_SDK_ROOT/QNN_SDK_ROOT/SNPE_ROOT are set.")
    for name, val in set_vars:
        if not Path(val).exists():
            return _r("SDK env vars", "warn", f"{name}={val} does not exist on disk.")
    names = ", ".join(n for n, _ in set_vars)
    return _r("SDK env vars", "pass", f"{names} set and pointing at existing directories.")


def _check_sdk_tools_on_path() -> CheckResult:
    required = ["qairt-converter", "snpe-net-run"]
    missing = [t for t in required if shutil.which(t) is None]
    sdk_root = (
        os.environ.get("QAIRT_SDK_ROOT")
        or os.environ.get("QNN_SDK_ROOT")
        or os.environ.get("SNPE_ROOT")
        or ""
    )
    if missing and sdk_root:
        # On Windows, QAIRT bin tools are extensionless scripts. Try the SDK bin dir directly.
        bin_root = Path(sdk_root) / "bin"
        if bin_root.is_dir():
            for sub in bin_root.iterdir():
                if not sub.is_dir():
                    continue
                missing = [t for t in missing if not (sub / t).exists() and not (sub / f"{t}.exe").exists()]
    if not missing:
        return _r("SDK tools in PATH", "pass", "qairt-converter, snpe-net-run reachable.")
    return _r(
        "SDK tools in PATH",
        "warn",
        f"Missing on PATH: {', '.join(missing)}. Source activate.ps1/activate.sh or set QAIRT_SDK_ROOT.",
    )


def _check_dsp_env() -> CheckResult:
    val = os.environ.get("ADSP_LIBRARY_PATH", "").strip()
    if not val:
        return _r(
            "DSP env (ADSP_LIBRARY_PATH)",
            "warn",
            "ADSP_LIBRARY_PATH not set. Required for DSP/HTP runtime on device.",
        )
    sep = ";" if sys.platform == "win32" else ":"
    bad = [p for p in val.split(sep) if p and not Path(p).exists()]
    if bad:
        return _r(
            "DSP env (ADSP_LIBRARY_PATH)",
            "warn",
            f"Some entries do not exist: {', '.join(bad[:3])}",
        )
    return _r("DSP env (ADSP_LIBRARY_PATH)", "pass", f"set ({len(val.split(sep))} entries).")


def _check_android_tools() -> CheckResult:
    adb = shutil.which("adb")
    ndk = os.environ.get("ANDROID_NDK_ROOT", "").strip()
    if not adb and not ndk:
        return _r("Android tools", "warn", "adb not on PATH and ANDROID_NDK_ROOT not set (only matters for Android targets).")
    parts = []
    if adb:
        parts.append(f"adb={adb}")
    if ndk:
        parts.append(f"ANDROID_NDK_ROOT={ndk}")
    return _r("Android tools", "pass", "; ".join(parts))


def _check_dlc_compat() -> CheckResult:
    sdk = (
        os.environ.get("QAIRT_SDK_ROOT")
        or os.environ.get("SNPE_ROOT")
        or os.environ.get("QNN_SDK_ROOT")
        or ""
    )
    if not sdk:
        return _r("DLC compatibility (>=1.16)", "warn", "No SDK env var set; skipping version check.")
    ver = _parse_version(sdk)
    if ver is None:
        return _r("DLC compatibility (>=1.16)", "warn", f"Could not parse version from {sdk}.")
    if ver >= (1, 16, 0):
        return _r("DLC compatibility (>=1.16)", "pass", f"SDK {ver[0]}.{ver[1]}.{ver[2]} supports modern DLC features.")
    return _r("DLC compatibility (>=1.16)", "warn", f"SDK {ver[0]}.{ver[1]}.{ver[2]} is older than 1.16; some DLC features unavailable.")


def _check_wer_support() -> CheckResult:
    sdk = (
        os.environ.get("QAIRT_SDK_ROOT")
        or os.environ.get("SNPE_ROOT")
        or os.environ.get("QNN_SDK_ROOT")
        or ""
    )
    if not sdk:
        return _r("WER support (>=2.28)", "warn", "No SDK env var set.")
    ver = _parse_version(sdk)
    if ver is None:
        return _r("WER support (>=2.28)", "warn", f"Could not parse version from {sdk}.")
    if ver >= (2, 28, 0):
        return _r("WER support (>=2.28)", "pass", f"SDK {ver[0]}.{ver[1]}.{ver[2]} supports Windows Error Reporting.")
    return _r("WER support (>=2.28)", "warn", f"SDK {ver[0]}.{ver[1]}.{ver[2]} -- WER unsupported (Windows-only feature).")


def _check_psutil() -> CheckResult:
    try:
        import psutil  # type: ignore  # noqa: F401
    except ImportError:
        return _r("psutil for profiling", "warn", "psutil not installed -- live RSS/CPU sampling disabled. pip install psutil if needed.")
    return _r("psutil for profiling", "pass", "available.")


def _check_python_arch_vs_os() -> CheckResult:
    machine = platform.uname().machine
    py_plat = sysconfig.get_platform()
    py_is_x64 = "amd64" in py_plat.lower() or "x86_64" in py_plat.lower()

    # Determine the true host arch. PROCESSOR_ARCHITEW6432 is the standard
    # signal but isn't always set; on Windows fall back to the WMI probe
    # that hardware.py uses (it reports the chip arch, not the interpreter's view).
    host_arch = os.environ.get("PROCESSOR_ARCHITEW6432", "").upper()
    if not host_arch and sys.platform == "win32":
        try:
            from ._platform import windows as windows_probe
            chip_arch = (windows_probe.probe().get("cpu_arch") or "").upper()
            if "ARM64" in chip_arch:
                host_arch = "ARM64"
        except Exception:  # noqa: BLE001
            pass
    if not host_arch:
        host_arch = machine.upper()

    if "ARM64" in host_arch and py_is_x64:
        return _r(
            "Python arch vs OS",
            "warn",
            f"x86_64 Python ({py_plat}) running under Prism on ARM64 Windows. NPU wheels "
            f"(onnxruntime-qnn) are win-arm64 only and will NOT load here — install native "
            f"ARM64 Python for any NPU work.",
        )
    if "AMD64" in host_arch and "arm" in py_plat.lower():
        return _r(
            "Python arch vs OS",
            "warn",
            f"ARM Python ({py_plat}) on amd64 OS -- unusual combination.",
        )
    return _r("Python arch vs OS", "pass", f"host={host_arch.lower()}, python={py_plat}")


def _installed_distributions() -> set[str]:
    """Return the set of installed distribution names (lower-cased).

    Uses importlib.metadata so it reflects the ACTIVE interpreter's
    environment — the only place a pip file-conflict can actually occur.
    """
    from importlib import metadata

    names: set[str] = set()
    for dist in metadata.distributions():
        name = (dist.metadata["Name"] if dist.metadata else None) or ""
        if name:
            names.add(name.lower())
    return names


def _check_onnxruntime_conflict() -> CheckResult:
    """Detect onnxruntime + onnxruntime-qnn installed together.

    Both packages write ``onnxruntime/capi/onnxruntime.dll`` to the SAME
    location; whichever installs last silently overwrites the other, destroying
    NPU support with no error. pip cannot detect this file conflict, so we check
    for both distributions explicitly (issue 2).
    """
    installed = _installed_distributions()
    has_base = "onnxruntime" in installed
    has_qnn = "onnxruntime-qnn" in installed
    if has_base and has_qnn:
        return _r(
            "onnxruntime package conflict",
            "fail",
            "Both onnxruntime and onnxruntime-qnn are installed — they overwrite each "
            "other's onnxruntime.dll and NPU support silently breaks. Fix: "
            "pip uninstall onnxruntime  (keep only onnxruntime-qnn).",
        )
    if has_qnn:
        return _r("onnxruntime package conflict", "pass",
                  "onnxruntime-qnn present, plain onnxruntime absent (correct for NPU).")
    if has_base:
        return _r("onnxruntime package conflict", "warn",
                  "Only plain onnxruntime present — CPU only. Install onnxruntime-qnn "
                  "(and NOT onnxruntime) for NPU support.")
    return _r("onnxruntime package conflict", "warn",
              "Neither onnxruntime nor onnxruntime-qnn installed in this environment.")


def _check_active_venv_for_npu() -> CheckResult:
    """Warn when NPU code would run in the wrong environment.

    NPU inference needs a native-ARM64 interpreter with onnxruntime-qnn
    importable. This check catches the common "ran it from the wrong venv"
    trap where onnxruntime-qnn simply isn't present in the active interpreter
    (issue 4). It does not import onnxruntime (heavy / may abort) — it only
    inspects installed distributions + interpreter arch.
    """
    installed = _installed_distributions()
    if "onnxruntime-qnn" not in installed:
        return _r(
            "Active venv for NPU",
            "warn",
            "onnxruntime-qnn is not installed in the ACTIVE interpreter "
            f"({sys.executable}). NPU code must run from the native-ARM64 venv that "
            "has onnxruntime-qnn (e.g. .venv-arm64), not the general tooling venv.",
        )
    py_plat = sysconfig.get_platform().lower()
    if "arm" not in py_plat and "aarch64" not in py_plat:
        return _r(
            "Active venv for NPU",
            "warn",
            f"onnxruntime-qnn is present but the interpreter is {py_plat} (not ARM64). "
            "The QNN wheels are win-arm64 only — run NPU code from a native-ARM64 venv.",
        )
    return _r("Active venv for NPU", "pass",
              "Active interpreter is ARM64 with onnxruntime-qnn — correct for NPU.")


def _check_model_access_token() -> CheckResult:
    """Check that a model-access credential is set, documenting the aliases.

    ANTHROPIC_API_KEY ≈ ANTHROPIC_AUTH_TOKEN ≈ QGENIE_API_KEY are the SAME
    credential in this deployment (Claude is routed via QGenie). Claude Code
    fails confusingly when none is set (issue IQ9-2).
    """
    aliases = ("QGENIE_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    present = [a for a in aliases if os.environ.get(a, "").strip()]
    if present:
        return _r("Model access token", "pass",
                  f"Set via {', '.join(present)} (these aliases are equivalent).")
    return _r(
        "Model access token",
        "warn",
        "None of QGENIE_API_KEY / ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN is set — "
        "these are the SAME credential (Claude is routed via QGenie). Claude Code needs "
        "one of them, and it must be set in the SAME shell that launches Claude Code "
        "(the VS Code GUI does not inherit shell env vars).",
    )


def _check_ca_bundle_env() -> CheckResult:
    """Flag a stale REQUESTS_CA_BUNDLE / SSL_CERT_FILE pointing at a missing file.

    On corporate networks these env vars are often exported pointing at a CA
    bundle that no longer exists, so every HTTPS download dies with
    'Could not find a suitable TLS CA certificate bundle' /
    CERTIFICATE_VERIFY_FAILED (IQ9 issues 24 / 47).
    """
    from pathlib import Path

    problems = []
    for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE", "QUAD_CA_BUNDLE"):
        val = os.environ.get(var, "").strip()
        if val and not Path(val).expanduser().exists():
            problems.append(f"{var}={val}")
    if problems:
        return _r(
            "TLS CA bundle env vars",
            "fail",
            "CA bundle env var points at a missing file: " + "; ".join(problems) +
            ". This breaks HTTPS model/asset downloads. Unset it or point it at a "
            "real corporate CA .pem (or `pip install truststore`).",
        )
    return _r("TLS CA bundle env vars", "pass",
              "No stale REQUESTS_CA_BUNDLE / SSL_CERT_FILE / QUAD_CA_BUNDLE detected.")


# ─── Public API ─────────────────────────────────────────────────────


_CHECKS: tuple[Callable[[], CheckResult], ...] = (
    _check_python_version,
    _check_quad_client_package,
    _check_sdk_env_vars,
    _check_sdk_tools_on_path,
    _check_dsp_env,
    _check_android_tools,
    _check_dlc_compat,
    _check_wer_support,
    _check_psutil,
    _check_python_arch_vs_os,
    _check_onnxruntime_conflict,
    _check_active_venv_for_npu,
    _check_ca_bundle_env,
    _check_model_access_token,
)


def run_doctor(real_mode: bool = False) -> list[CheckResult]:
    """Run the full local check suite and return a list of CheckResult dicts."""
    results: list[CheckResult] = []
    for check in _CHECKS:
        try:
            result = check()
        except Exception as e:  # defensive -- a check should never crash the suite
            result = _r(getattr(check, "__name__", "?"), "fail", f"check raised: {e!r}")
        if real_mode and result["status"] == "warn" and result["name"] in _REAL_MODE_ESCALATE:
            result = _r(result["name"], "fail", "[real-mode strict] " + result["message"])
        results.append(result)
    return results


def has_failures(results: list[CheckResult]) -> bool:
    return any(r["status"] == "fail" for r in results)
