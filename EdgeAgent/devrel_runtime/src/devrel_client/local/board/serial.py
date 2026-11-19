"""Serial / UART helpers for early-boot logs and bootloader interaction.

Read-only operations only; flashing is left to the user via documented
``fastboot`` / ``screen`` invocations. We won't take a pyserial dep.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class SerialResult:
    available: bool
    detail: str


def detect_serial_tool() -> SerialResult:
    """Identify which serial console tool is available on the host."""
    for tool in ("screen", "minicom", "putty"):
        if shutil.which(tool):
            return SerialResult(True, f"{tool} on PATH")
    if shutil.which("powershell"):
        # On Windows, [System.IO.Ports.SerialPort] is always available.
        return SerialResult(True, "powershell System.IO.Ports.SerialPort")
    return SerialResult(False, "no screen/minicom/putty/powershell found")


def serial_help() -> str:
    return (
        "Open a UART console with one of:\n"
        "  Linux/macOS:  screen /dev/ttyUSB0 115200\n"
        "  Windows:      putty -serial COM3 -sercfg 115200\n"
        "Use Ctrl-A k (screen) or right-click->Close (putty) to exit."
    )
