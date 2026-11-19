"""Windows hardware probe via a single batched PowerShell call.

PowerShell startup is ~300 ms per invocation, so we make ONE call that
returns JSON for both ``Win32_Processor`` and ``Win32_ComputerSystem``.
Total probe time is typically 400-600 ms.
"""

from __future__ import annotations

import json
import platform
import subprocess
from typing import Any

_PS_QUERY = r"""
$cs = Get-CimInstance Win32_ComputerSystem |
    Select-Object -Property TotalPhysicalMemory
$cpu = Get-CimInstance Win32_Processor |
    Select-Object -Property Name,NumberOfCores,MaxClockSpeed,Architecture
$osq = Get-CimInstance Win32_OperatingSystem |
    Select-Object -Property Caption,Version
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'" |
    Select-Object -Property Size
@{ cpu = $cpu; cs = $cs; os = $osq; disk = $disk } | ConvertTo-Json -Depth 4 -Compress
"""


def _run_powershell() -> dict[str, Any] | None:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_QUERY],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _arch_label(arch_code: int | None) -> str:
    # Win32_Processor.Architecture: 0=x86, 5=ARM, 9=x64, 12=ARM64
    return {0: "x86", 5: "ARM", 9: "AMD64/x64", 12: "ARM64"}.get(arch_code or -1, platform.machine())


def probe() -> dict[str, Any]:
    data = _run_powershell()
    if data is None:
        # Fallback to stdlib
        import shutil

        try:
            storage = round(shutil.disk_usage("C:\\").total / (1024**3), 1)
        except OSError:
            storage = 0.0
        return {
            "chipset": platform.processor() or "unknown",
            "cpu_cores": 0,
            "cpu_arch": platform.machine() or "unknown",
            "cpu_freq_ghz": 0.0,
            "ram_gb": 0.0,
            "storage_gb": storage,
            "os_version": f"Windows {platform.release()}" if platform.release() else "Windows",
        }

    cpu = data.get("cpu") or {}
    if isinstance(cpu, list):
        cpu = cpu[0] if cpu else {}
    cs = data.get("cs") or {}
    if isinstance(cs, list):
        cs = cs[0] if cs else {}
    osq = data.get("os") or {}
    if isinstance(osq, list):
        osq = osq[0] if osq else {}
    disk = data.get("disk") or {}
    if isinstance(disk, list):
        disk = disk[0] if disk else {}

    name = (cpu.get("Name") or "").strip() or "unknown"
    cores = int(cpu.get("NumberOfCores") or 0)
    mhz = int(cpu.get("MaxClockSpeed") or 0)
    arch = _arch_label(cpu.get("Architecture"))
    total_bytes = int(cs.get("TotalPhysicalMemory") or 0)
    disk_bytes = int(disk.get("Size") or 0)
    os_caption = (osq.get("Caption") or "").strip()

    return {
        "chipset": name,
        "cpu_cores": cores,
        "cpu_arch": arch,
        "cpu_freq_ghz": round(mhz / 1000.0, 3) if mhz else 0.0,
        "ram_gb": round(total_bytes / (1024**3), 1) if total_bytes else 0.0,
        "storage_gb": round(disk_bytes / (1024**3), 1) if disk_bytes else 0.0,
        "os_version": os_caption or (f"Windows {platform.release()}" if platform.release() else "Windows"),
    }
