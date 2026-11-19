"""ADB transport for boards that expose Android Debug Bridge.

Used as an alternative to SSH when the board exposes ADB. The
``adb`` binary is from the Android SDK platform-tools.
"""

from __future__ import annotations

import shutil
import subprocess
import time as _time
from dataclasses import dataclass


@dataclass
class ADBTarget:
    serial: str = ""  # blank -> let adb auto-pick the only device


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _check_adb() -> str:
    exe = shutil.which("adb")
    if exe is None:
        raise RuntimeError("'adb' not on PATH. Install Android SDK platform-tools.")
    return exe


def adb_shell(target: ADBTarget, cmd: str, *, timeout_s: int = 30) -> CommandResult:
    adb = _check_adb()
    full = [adb]
    if target.serial:
        full += ["-s", target.serial]
    full += ["shell", cmd]
    start = _time.perf_counter()
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", f"adb shell timeout after {timeout_s}s", (_time.perf_counter() - start) * 1000)
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=(_time.perf_counter() - start) * 1000,
    )


def adb_push(target: ADBTarget, src, dst: str, *, timeout_s: int = 120) -> CommandResult:
    """Push a local file to the device via ``adb push``."""
    adb = _check_adb()
    full = [adb]
    if target.serial:
        full += ["-s", target.serial]
    full += ["push", str(src), dst]
    start = _time.perf_counter()
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", f"adb push timeout after {timeout_s}s", (_time.perf_counter() - start) * 1000)
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        elapsed_ms=(_time.perf_counter() - start) * 1000,
    )
