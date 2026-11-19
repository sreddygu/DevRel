"""Linux hardware probe via /proc."""

from __future__ import annotations

import platform
import re
import shutil
from pathlib import Path
from typing import Any


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_cpuinfo(text: str) -> dict[str, Any]:
    chipset = ""
    cores = 0
    freq_mhz = 0.0
    arch = platform.machine() or "unknown"

    # processor count: number of "processor :" lines
    cores = sum(1 for line in text.splitlines() if line.startswith("processor"))

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Hardware: line on Snapdragon/Arduino UNO Q boards
        if line.startswith("Hardware") and not chipset:
            _, _, val = line.partition(":")
            chipset = val.strip()
        elif line.startswith("model name") and not chipset:
            _, _, val = line.partition(":")
            chipset = val.strip()
        elif line.startswith("cpu MHz") and freq_mhz == 0.0:
            _, _, val = line.partition(":")
            try:
                freq_mhz = float(val.strip())
            except ValueError:
                pass

    return {
        "chipset": chipset or "unknown",
        "cpu_cores": cores,
        "cpu_arch": arch,
        "cpu_freq_ghz": round(freq_mhz / 1000.0, 3) if freq_mhz else 0.0,
    }


def _parse_meminfo(text: str) -> float:
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE)
    if not m:
        return 0.0
    kb = int(m.group(1))
    return round(kb / (1024**2), 1)


def _os_version() -> str:
    """PRETTY_NAME from /etc/os-release, else a generic 'Linux <release>'."""
    text = _read("/etc/os-release")
    m = re.search(r'^PRETTY_NAME\s*=\s*"?([^"\n]+)', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return f"Linux {platform.release()}" if platform.release() else "Linux"


def _storage_gb() -> float:
    try:
        return round(shutil.disk_usage("/").total / (1024**3), 1)
    except OSError:
        return 0.0


def probe() -> dict[str, Any]:
    cpu = _parse_cpuinfo(_read("/proc/cpuinfo"))
    ram_gb = _parse_meminfo(_read("/proc/meminfo"))
    cpu["ram_gb"] = ram_gb
    cpu["storage_gb"] = _storage_gb()
    cpu["os_version"] = _os_version()
    return cpu
