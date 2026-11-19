"""Read-only host discovery for GesturDJ. Writes the `host` part of device-profile.json.

Observes only; installs nothing. Anything not observed is reported as "unknown".
Run it with the same Python you will use for the project, so the import checks are truthful.

    python discover_host.py --out device-profile.json
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

PACKAGES = ("numpy", "sklearn", "joblib", "torch", "onnx", "onnxruntime")
AUDIO_PLAYERS = ("paplay", "pw-play", "aplay", "gst-play-1.0", "ffplay")


def native_machine() -> str:
    """Real CPU architecture of the machine (not of the Python interpreter)."""
    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE            # declare types: a 64-bit handle is truncated otherwise
            k32.IsWow64Process2.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT)]
            process_machine, native = wintypes.USHORT(), wintypes.USHORT()
            ok = k32.IsWow64Process2(k32.GetCurrentProcess(), ctypes.byref(process_machine), ctypes.byref(native))
            names = {0x8664: "AMD64", 0xAA64: "ARM64", 0x014C: "x86"}
            if ok and native.value in names:
                return names[native.value]
        except Exception:
            pass
    return platform.machine()


def package_versions() -> dict[str, str]:
    out = {}
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
            out[name] = getattr(mod, "__version__", "present")
        except Exception:
            out[name] = "missing"
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only host discovery for GesturDJ.")
    p.add_argument("--out", type=Path, default=None, help="Write the profile JSON here (default: print only).")
    p.add_argument("--path", type=Path, default=Path.cwd(), help="Folder whose free disk space is reported.")
    args = p.parse_args()

    # Windows on ARM can run x64 Python under emulation, and then Python and the environment both claim AMD64.
    # Ask Windows for the real machine type (IsWow64Process2); elsewhere platform.machine() is the machine.
    os_arch = native_machine()
    free_gb = round(shutil.disk_usage(args.path).free / 2**30, 1)
    players = [p_ for p_ in AUDIO_PLAYERS if shutil.which(p_)]
    pkgs = package_versions()

    profile = {
        "host": {
            "os": f"{platform.system()} {platform.release()}",
            "os_arch": os_arch,
            "python": platform.python_version(),
            "python_arch": platform.machine(),
            "python_executable": sys.executable,
            "free_disk_gb": free_gb,
            "packages": pkgs,
            "audio_players_on_path": players,
            "camera": "unknown",
            "audio_sink": "unknown",
        },
        "unknown": ["camera", "audio_sink", "recognizer_board", "generator"],
    }
    profile["host"]["onnxruntime"] = "present" if pkgs["onnxruntime"] != "missing" else "missing"

    notes = []
    if os_arch.upper() in ("ARM64", "AARCH64") and platform.machine().upper() not in ("ARM64", "AARCH64"):
        notes.append(f"Python is {platform.machine()} on an {os_arch} machine: running under emulation; expect slower training and different wheels.")
    missing = [k for k, v in pkgs.items() if v == "missing"]
    if missing:
        notes.append("missing packages: " + ", ".join(missing))
    profile["notes"] = notes

    text = json.dumps(profile, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
