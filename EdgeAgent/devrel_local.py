"""Dependency-free local probes for developer bring-up and onboarding."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def ensure_local_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("model URL must use http or https")
    if parsed.hostname not in LOCAL_HOSTS:
        raise ValueError(
            f"DevRel agent requires a local LLM endpoint; got host {parsed.hostname!r}. "
            "Use 127.0.0.1, localhost, or an SSH tunnel bound to loopback."
        )
    return url.rstrip("/")


def _run(command: list[str], timeout_s: float = 8.0) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _powershell(expression: str) -> str:
    executable = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not executable:
        return ""
    return _run([executable, "-NoProfile", "-Command", expression])


def _linux_value(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _memory_bytes() -> int | None:
    if os.name == "nt":
        raw = _powershell("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
        return int(raw) if raw.isdigit() else None
    meminfo = _linux_value("/proc/meminfo")
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) * 1024
    return None


def _cpu_name() -> str:
    if os.name == "nt":
        return _powershell(
            "Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name"
        ) or platform.processor()
    cpuinfo = _linux_value("/proc/cpuinfo")
    for prefix in ("model name", "Hardware", "Processor", "chip name"):
        for line in cpuinfo.splitlines():
            if line.lower().startswith(prefix.lower() + "\t") or line.lower().startswith(prefix.lower() + " "):
                return line.split(":", 1)[-1].strip()
    return platform.processor()


def _gpu_names() -> list[str]:
    if os.name == "nt":
        raw = _powershell(
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
        )
        return [line.strip() for line in raw.splitlines() if line.strip()]
    names: list[str] = []
    for path in Path("/sys/class/drm").glob("card*/device/uevent"):
        text = _linux_value(str(path))
        for line in text.splitlines():
            if line.startswith("DRIVER="):
                names.append(line.split("=", 1)[1])
    return sorted(set(names))


def _soc_strings() -> list[str]:
    values = [
        _linux_value("/sys/devices/soc0/family"),
        _linux_value("/sys/devices/soc0/machine"),
        _linux_value("/sys/devices/soc0/soc_id"),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
        os.environ.get("PROCESSOR_ARCHITECTURE", ""),
    ]
    return [value for value in values if value]


def detect_hardware() -> dict[str, Any]:
    cpu = _cpu_name()
    soc_strings = _soc_strings()
    searchable = " ".join([cpu, platform.processor(), *soc_strings]).lower()
    markers = ("qualcomm", "snapdragon", "qcs", "x1e", "sc8280", "oryon")
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python_architecture": platform.architecture()[0],
        "python_version": platform.python_version(),
        "cpu": cpu or "unknown",
        "cpu_count": os.cpu_count(),
        "memory_bytes": _memory_bytes(),
        "gpu": _gpu_names(),
        "soc_strings": soc_strings,
        "qualcomm_detected": any(marker in searchable for marker in markers),
    }


def _check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


def _package_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def local_doctor(real_mode: bool = False) -> list[dict[str, str]]:
    hardware = detect_hardware()
    checks: list[dict[str, str]] = []

    version = sys.version_info
    supported_python = (3, 10) <= (version.major, version.minor) <= (3, 12)
    checks.append(
        _check(
            "Python version",
            "pass" if supported_python else "warn",
            f"Python {platform.python_version()} ({platform.machine()}); common Qualcomm NPU wheels target Python 3.10-3.12.",
        )
    )

    checks.append(
        _check(
            "Qualcomm hardware",
            "pass" if hardware["qualcomm_detected"] else "warn",
            f"CPU={hardware['cpu']}; machine={hardware['machine']}",
        )
    )

    sdk_vars = {
        name: os.environ.get(name, "")
        for name in ("QAIRT_HOME", "QNN_SDK_ROOT", "SNPE_ROOT")
    }
    configured = {name: value for name, value in sdk_vars.items() if value}
    invalid = {name: value for name, value in configured.items() if not Path(value).is_dir()}
    if invalid:
        checks.append(_check("Qualcomm SDK paths", "fail", f"Configured paths do not exist: {sorted(invalid)}"))
    elif configured:
        checks.append(_check("Qualcomm SDK paths", "pass", f"Configured: {sorted(configured)}"))
    else:
        checks.append(_check("Qualcomm SDK paths", "fail" if real_mode else "warn", "No QAIRT_HOME, QNN_SDK_ROOT, or SNPE_ROOT is configured."))

    tools = {
        name: shutil.which(name)
        for name in ("qnn-net-run", "qnn-platform-validator", "adb", "ssh", "cmake", "git")
    }
    qnn_tools = [name for name in ("qnn-net-run", "qnn-platform-validator") if tools[name]]
    checks.append(
        _check(
            "QNN command-line tools",
            "pass" if qnn_tools else "fail" if real_mode else "warn",
            f"Found: {qnn_tools or 'none'}",
        )
    )
    checks.append(
        _check(
            "Device transports",
            "pass" if tools["adb"] or tools["ssh"] else "warn",
            f"adb={'yes' if tools['adb'] else 'no'}, ssh={'yes' if tools['ssh'] else 'no'}",
        )
    )

    adsp = os.environ.get("ADSP_LIBRARY_PATH", "")
    checks.append(
        _check(
            "DSP library path",
            "pass" if adsp else "fail" if real_mode else "warn",
            "ADSP_LIBRARY_PATH is set." if adsp else "ADSP_LIBRARY_PATH is not set.",
        )
    )

    packages = {
        name: _package_available(name)
        for name in ("onnxruntime", "torch", "executorch", "qai_hub", "qai_hub_models")
    }
    checks.append(
        _check(
            "AI runtime packages",
            "pass" if any(packages.values()) else "warn",
            json.dumps(packages, sort_keys=True),
        )
    )

    if packages["onnxruntime"]:
        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            has_qnn = "QNNExecutionProvider" in providers
            checks.append(
                _check(
                    "ONNX Runtime QNN provider",
                    "pass" if has_qnn else "warn",
                    f"Providers: {providers}",
                )
            )
        except Exception as exc:  # noqa: BLE001 - diagnostic must not crash
            checks.append(_check("ONNX Runtime import", "fail", f"Import failed: {type(exc).__name__}: {exc}"))

    return checks


def model_server_health(base_url: str, timeout_s: float = 5.0) -> dict[str, Any]:
    base = ensure_local_url(base_url)
    request = urllib.request.Request(base + "/v1/models", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "status": "blocked",
            "base_url": base,
            "error": f"{type(exc).__name__}: {exc}",
        }
    models = payload.get("data", []) if isinstance(payload, dict) else []
    names = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    return {"status": "pass", "base_url": base, "models": names}
