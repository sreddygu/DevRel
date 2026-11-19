"""macOS hardware probe via sysctl. Returns a 'non-Snapdragon' shaped result."""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any


def _sysctl(name: str) -> str:
    try:
        r = subprocess.run(
            ["sysctl", "-n", name],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def probe() -> dict[str, Any]:
    chipset = _sysctl("machdep.cpu.brand_string") or "unknown"
    cores_str = _sysctl("hw.ncpu")
    mem_str = _sysctl("hw.memsize")
    freq_str = _sysctl("hw.cpufrequency")  # often empty on Apple Silicon

    try:
        cores = int(cores_str) if cores_str else 0
    except ValueError:
        cores = 0
    try:
        ram_gb = round(int(mem_str) / (1024**3), 1) if mem_str else 0.0
    except ValueError:
        ram_gb = 0.0
    try:
        freq_ghz = round(int(freq_str) / 1e9, 3) if freq_str else 0.0
    except ValueError:
        freq_ghz = 0.0

    try:
        storage_gb = round(shutil.disk_usage("/").total / (1024**3), 1)
    except OSError:
        storage_gb = 0.0

    mac_ver = platform.mac_ver()[0]
    os_version = f"macOS {mac_ver}" if mac_ver else "macOS"

    return {
        "chipset": chipset,
        "cpu_cores": cores,
        "cpu_arch": platform.machine() or "unknown",
        "cpu_freq_ghz": freq_ghz,
        "ram_gb": ram_gb,
        "storage_gb": storage_gb,
        "os_version": os_version,
    }
