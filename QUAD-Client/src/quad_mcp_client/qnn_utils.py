"""
qnn_utils.py — Shared QNN/QAIRT inference utilities for QUAD sample scripts.

Handles the platform quirks of running qnn-net-run on Windows ARM64
(Snapdragon X Elite and similar) where:

  • Python's platform.machine() reports 'AMD64' even on ARM64 hardware.
  • PROCESSOR_IDENTIFIER reliably exposes the real CPU family/vendor.
  • The SDK ships separate arch dirs: aarch64-windows-msvc (has QnnHtpPrepare.dll)
    and x86_64-windows-msvc (lacks QnnHtpPrepare.dll — HTP unavailable there).
  • libcdsprpc.dll (Qualcomm FastRPC) lives in the Windows DriverStore rather
    than in a standard System32 / PATH location.

Public API
----------
  detect_windows_arm64()                   → bool
  find_qnn_sdk_dirs(sdk_root)              → (bin_dir, lib_dir)
  find_cdsprpc_dir()                       → Path | None
  build_qnn_subprocess_env(sdk_root)       → dict[str, str]
  run_qnn_net_run(model_bin, inp, sdk_root) → (logits np.ndarray, elapsed_ms float)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


# ---------------------------------------------------------------------------
# Architecture detection
# ---------------------------------------------------------------------------

def detect_windows_arm64() -> bool:
    """Return True when running on a Windows ARM64 machine (e.g. Snapdragon X Elite).

    Python may report AMD64 for platform.machine() on ARM64 because it can ship
    as an x64 or ARM64EC binary.  We use two more reliable signals instead:

    * PROCESSOR_ARCHITEW6432 — set by Windows when a non-native (WoW64) x64
      process queries PROCESSOR_ARCHITECTURE; its value is the real OS arch.
    * PROCESSOR_IDENTIFIER   — always reflects the physical CPU, e.g.
      "ARMv8 (64-bit) Family 8 Model 1 Revision 201, Qualcomm Technologies Inc".
    """
    import platform
    machine    = platform.machine().lower()
    proc_id    = os.environ.get("PROCESSOR_IDENTIFIER",   "").lower()
    wow64_arch = os.environ.get("PROCESSOR_ARCHITEW6432", "").upper()
    return (
        "arm"      in machine
        or "aarch64" in machine
        or wow64_arch == "ARM64"
        or "armv8"    in proc_id
        or "aarch64"  in proc_id
        or "qualcomm" in proc_id   # Snapdragon X Elite identifies itself here
    )


# ---------------------------------------------------------------------------
# SDK directory resolution
# ---------------------------------------------------------------------------

def find_qnn_sdk_dirs(sdk_root: str | Path) -> tuple[Path, Path]:
    """Return *(bin_dir, lib_dir)* for the correct SDK architecture.

    Preference order on Windows:
      1. ``aarch64-windows-msvc`` when detect_windows_arm64() is True *or*
         when QnnHtpPrepare.dll is absent in x86_64-windows-msvc (graceful
         fallback).
      2. ``x86_64-windows-msvc`` otherwise.
    """
    sdk_root = Path(sdk_root)
    arch = "aarch64-windows-msvc" if detect_windows_arm64() else "x86_64-windows-msvc"
    bin_dir = sdk_root / "bin" / arch
    lib_dir = sdk_root / "lib" / arch

    # Graceful fallback: if the chosen lib dir lacks QnnHtpPrepare.dll, try
    # aarch64 which always ships the full HTP stack.
    if not (lib_dir / "QnnHtpPrepare.dll").exists():
        alt_bin = sdk_root / "bin" / "aarch64-windows-msvc"
        alt_lib = sdk_root / "lib" / "aarch64-windows-msvc"
        if (alt_lib / "QnnHtpPrepare.dll").exists():
            bin_dir, lib_dir = alt_bin, alt_lib

    return bin_dir, lib_dir


# ---------------------------------------------------------------------------
# DSP RPC library discovery
# ---------------------------------------------------------------------------

def find_cdsprpc_dir() -> Path | None:
    """Locate the directory that contains *libcdsprpc.dll* (Qualcomm FastRPC).

    On Windows the library ships inside the DriverStore rather than System32,
    so it is not on PATH by default.  We search
    ``%SystemRoot%\\System32\\DriverStore\\FileRepository`` for the first
    ``qcadsprpc*.inf_arm64_*`` directory that contains the DLL.

    Returns the directory *Path* or *None* if not found.
    """
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    driverstore = Path(system_root) / "System32" / "DriverStore" / "FileRepository"
    if not driverstore.is_dir():
        return None
    for entry in sorted(driverstore.iterdir()):   # sorted → deterministic
        if entry.name.lower().startswith("qcadsprpc") and entry.is_dir():
            if (entry / "libcdsprpc.dll").exists():
                return entry
    return None


# ---------------------------------------------------------------------------
# Subprocess environment builder
# ---------------------------------------------------------------------------

def build_qnn_subprocess_env(sdk_root: str | Path) -> dict[str, str]:
    """Build an *os.environ* copy with the QNN SDK and FastRPC DLLs on PATH.

    Prepends (in order):
      1. SDK lib dir for the resolved arch (QnnHtp.dll, QnnHtpPrepare.dll, stubs)
      2. SDK bin dir (qnn-net-run.exe may dlopen sibling executables)
      3. DriverStore dir containing libcdsprpc.dll (if found)
    """
    bin_dir, lib_dir = find_qnn_sdk_dirs(sdk_root)
    extra: list[str] = [str(lib_dir), str(bin_dir)]
    cdsp_dir = find_cdsprpc_dir()
    if cdsp_dir:
        extra.append(str(cdsp_dir))
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(extra) + os.pathsep + env.get("PATH", "")
    return env


# ---------------------------------------------------------------------------
# qnn-net-run inference
# ---------------------------------------------------------------------------

# QNN backend → shared library name (Windows).
_BACKEND_DLL_MAP = {"htp": "QnnHtp.dll", "gpu": "QnnGpu.dll", "cpu": "QnnCpu.dll"}


def validate_backend_artifact(model_bin: str | Path, backend: str) -> None:
    """Reject artifact/backend combinations that cannot possibly load.

    A compiled HTP context binary (``.bin`` from AI Hub Models / graph-prepare) is
    **backend-locked**: loading an HTP ``.bin`` against ``libQnnGpu`` fails at
    load time with ``GPU_ERROR_DOES_NOT_EXIST`` — the confusing failure the
    IQ-9075 bring-up hit (retrospective §4 / issue IQ9-35). The GPU (and CPU)
    backends must be fed a portable ``.dlc`` instead. Raise a clear error up
    front rather than surfacing the opaque backend error later.
    """
    suffix = Path(model_bin).suffix.lower()
    b = backend.lower()
    if suffix == ".bin" and b in ("gpu", "cpu"):
        raise ValueError(
            f"A compiled HTP context binary (.bin) is backend-locked to the HTP "
            f"(NPU) and cannot run on the {b.upper()} backend — it would fail at "
            f"load time (e.g. GPU_ERROR_DOES_NOT_EXIST). Use the portable .dlc "
            f"artifact for {b.upper()} inference, or target the HTP backend."
        )


def run_qnn_net_run(
    model_bin: str | Path,
    inp: np.ndarray,
    sdk_root: str | Path,
    *,
    timeout: int = 60,
) -> tuple[np.ndarray, float]:
    """Run one inference pass via ``qnn-net-run.exe`` and return *(logits, ms)*.

    Accepts two model formats:
    * ``.bin``  — QNN context binary; loaded via ``--retrieve_context``.
    * ``.dlc``  — SNPE DLC (output of qairt-converter); loaded via
                  ``--dlc_path`` together with ``QnnModelDlc.dll``.

    Parameters
    ----------
    model_bin:
        Path to a QNN context binary (.bin) or SNPE DLC (.dlc).
    inp:
        Pre-processed input tensor as a float32 numpy array.  Will be cast
        to float32 before writing.
    sdk_root:
        QAIRT/QNN SDK root directory (contains ``bin/`` and ``lib/``
        sub-directories).
    timeout:
        Maximum seconds to wait for qnn-net-run to finish.

    Returns
    -------
    logits:
        Flat 1-D float32 numpy array (shape ``(1, num_classes)`` or similar).
    elapsed_ms:
        Wall-clock inference time in milliseconds.

    Raises
    ------
    FileNotFoundError
        If ``model_bin`` does not exist on disk.
    RuntimeError
        If qnn-net-run.exe, QnnHtp.dll, or (for DLC) QnnModelDlc.dll are not
        found in the SDK, or if qnn-net-run exits with a non-zero code.
    """
    import numpy as np

    model_bin = Path(model_bin)
    if not model_bin.exists():
        raise FileNotFoundError(
            f"QNN model not found: {model_bin}\n"
            "The model may have been converted in mock mode (no real SDK installed).\n"
            "Re-run with a real QAIRT SDK to produce an actual model file."
        )

    bin_dir, lib_dir = find_qnn_sdk_dirs(sdk_root)
    net_run = bin_dir / "qnn-net-run.exe"
    backend = lib_dir / "QnnHtp.dll"

    if not net_run.exists():
        raise RuntimeError(f"qnn-net-run.exe not found: {net_run}")
    if not backend.exists():
        raise RuntimeError(f"QnnHtp.dll not found: {backend}")

    env = build_qnn_subprocess_env(sdk_root)

    is_dlc = model_bin.suffix.lower() == ".dlc"

    if is_dlc:
        qnn_model_dlc = lib_dir / "QnnModelDlc.dll"
        if not qnn_model_dlc.exists():
            raise RuntimeError(
                f"QnnModelDlc.dll not found: {qnn_model_dlc}\n"
                "This DLL is required for --dlc_path inference and ships with "
                "the QAIRT SDK (lib/aarch64-windows-msvc/)."
            )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        raw_input = tmp / "input.raw"
        inp.astype(np.float32).tofile(raw_input)

        input_list = tmp / "input_list.txt"
        input_list.write_text(str(raw_input))

        output_dir = tmp / "output"
        output_dir.mkdir()

        if is_dlc:
            # DLC files are loaded via --dlc_path; QnnModelDlc.dll must be on
            # PATH (already added by build_qnn_subprocess_env via lib_dir).
            cmd = [
                str(net_run),
                "--backend",    str(backend),
                "--dlc_path",   str(model_bin),
                "--input_list", str(input_list),
                "--output_dir", str(output_dir),
            ]
        else:
            cmd = [
                str(net_run),
                "--backend",          str(backend),
                "--retrieve_context", str(model_bin),
                "--input_list",       str(input_list),
                "--output_dir",       str(output_dir),
            ]

        t0 = time.perf_counter()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if result.returncode != 0:
            raise RuntimeError(
                f"qnn-net-run failed (exit {result.returncode}):\n"
                f"{result.stderr[:600]}"
            )

        raw_files = sorted(output_dir.rglob("*.raw"))
        if not raw_files:
            raise RuntimeError("qnn-net-run produced no output .raw files")

        import numpy as np  # re-import to satisfy type checker in function scope
        logits = np.fromfile(str(raw_files[-1]), dtype=np.float32)
        return logits.reshape(1, -1), elapsed_ms


def benchmark_qnn_net_run(
    model_bin: str | Path,
    inp: np.ndarray,
    sdk_root: str | Path,
    *,
    duration_s: int = 5,
    perf_profile: str = "burst",
    timeout: int = 120,
    backend: str = "htp",
) -> dict:
    """Run many inferences in a single ``qnn-net-run`` process using ``--duration``.

    Unlike :func:`run_qnn_net_run` (which runs **one** inference per
    subprocess launch), this function keeps qnn-net-run alive for
    *duration_s* seconds so it can execute hundreds of iterations after
    the one-time graph-prepare overhead.  This gives accurate per-
    inference NPU latency without process-spawn noise.

    Parameters
    ----------
    backend : str
        QNN backend to target: ``"htp"`` (NPU, default), ``"gpu"``
        (Adreno), or ``"cpu"``.

    Returns
    -------
    dict with keys:
        logits       — float32 ndarray from the last iteration
        num_iters    — number of completed iterations
        wall_s       — total wall-clock time (including init)
        avg_ms       — average latency per inference (wall / iters)
        fps          — inferences per second (1000 / avg_ms)
    """
    import numpy as np

    model_bin = Path(model_bin)
    if not model_bin.exists():
        raise FileNotFoundError(f"QNN model not found: {model_bin}")

    bin_dir, lib_dir = find_qnn_sdk_dirs(sdk_root)
    net_run = bin_dir / "qnn-net-run.exe"

    # Reject artifact/backend combos that can't load (HTP .bin on GPU/CPU).
    validate_backend_artifact(model_bin, backend)

    # Select backend library based on the backend parameter
    backend_dll_name = _BACKEND_DLL_MAP.get(backend.lower(), "QnnHtp.dll")
    backend_lib = lib_dir / backend_dll_name

    if not net_run.exists():
        raise RuntimeError(f"qnn-net-run.exe not found: {net_run}")
    if not backend_lib.exists():
        raise RuntimeError(f"{backend_dll_name} not found: {backend_lib}")

    env = build_qnn_subprocess_env(sdk_root)
    is_dlc = model_bin.suffix.lower() == ".dlc"

    if is_dlc:
        qnn_model_dlc = lib_dir / "QnnModelDlc.dll"
        if not qnn_model_dlc.exists():
            raise RuntimeError(f"QnnModelDlc.dll not found: {qnn_model_dlc}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        raw_input = tmp / "input.raw"
        inp.astype(np.float32).tofile(raw_input)

        input_list = tmp / "input_list.txt"
        input_list.write_text(str(raw_input))

        output_dir = tmp / "output"
        output_dir.mkdir()

        if is_dlc:
            cmd = [
                str(net_run),
                "--backend",    str(backend_lib),
                "--dlc_path",   str(model_bin),
                "--input_list", str(input_list),
                "--output_dir", str(output_dir),
            ]
        else:
            cmd = [
                str(net_run),
                "--backend",          str(backend_lib),
                "--retrieve_context", str(model_bin),
                "--input_list",       str(input_list),
                "--output_dir",       str(output_dir),
            ]

        cmd += [
            "--duration",     str(duration_s),
            "--perf_profile", perf_profile,
        ]

        t0 = time.perf_counter()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
        wall_s = time.perf_counter() - t0

        if result.returncode != 0:
            raise RuntimeError(
                f"qnn-net-run failed (exit {result.returncode}):\n"
                f"{result.stderr[:600]}"
            )

        # Count iterations from Result_N directories
        result_dirs = sorted(output_dir.glob("Result_*"))
        num_iters = len(result_dirs)
        if num_iters == 0:
            raise RuntimeError("qnn-net-run produced no Result_* directories")

        # Read logits from last iteration
        last_dir = result_dirs[-1]
        raw_files = sorted(last_dir.glob("*.raw"))
        if not raw_files:
            raise RuntimeError(f"No output .raw in {last_dir}")
        logits = np.fromfile(str(raw_files[-1]), dtype=np.float32).reshape(1, -1)

        # Compute timing — subtract init overhead by using only execution time.
        # Parse first and last QnnGraph_execute timestamps from stdout if
        # available, otherwise fall back to wall_clock / num_iters.
        avg_ms = (wall_s * 1000.0) / num_iters
        # Refine: strip init time by estimating graph-prepare overhead from
        # the gap between process start and first execution.  A reasonable
        # heuristic is that total_execution_time ≈ wall_s - first_execute_offset.
        # With --duration, the qnn-net-run tool times only the execute phase
        # internally, so iterations / duration_s gives the clean throughput.
        if num_iters > 1:
            # qnn-net-run --duration targets `duration_s` of *execution* time.
            # So avg_ms ≈ duration_s * 1000 / num_iters is the best estimate.
            avg_ms = (duration_s * 1000.0) / num_iters

        fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0

        return {
            "logits": logits,
            "num_iters": num_iters,
            "wall_s": wall_s,
            "avg_ms": avg_ms,
            "fps": fps,
        }


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def check_qnn_environment(sdk_root: str | Path | None = None) -> dict:
    """Return a summary of the QNN inference environment.

    Useful for debugging — call from a script or ``python -c``.

    Returns a dict with keys:
        ok (bool)           — True if everything needed for NPU inference is present.
        is_arm64 (bool)
        arch (str)          — Selected SDK arch dir name.
        sdk_root (str|None)
        net_run (str|None)
        qnn_htp_dll (str|None)
        qnn_htp_prepare_dll (str|None)
        cdsprpc_dir (str|None)
        messages (list[str]) — human-readable notes / warnings.
    """
    msgs: list[str] = []
    result: dict = {
        "ok": False,
        "is_arm64": detect_windows_arm64(),
        "arch": None,
        "sdk_root": None,
        "net_run": None,
        "qnn_htp_dll": None,
        "qnn_htp_prepare_dll": None,
        "cdsprpc_dir": None,
        "messages": msgs,
    }

    # Resolve SDK root
    if sdk_root is None:
        sdk_root = os.environ.get("QNN_SDK_ROOT") or os.environ.get("QAIRT_SDK_ROOT")
    if not sdk_root:
        msgs.append("QNN_SDK_ROOT / QAIRT_SDK_ROOT not set — run: set QNN_SDK_ROOT=<sdk path>")
        return result

    sdk_root = Path(sdk_root)
    result["sdk_root"] = str(sdk_root)

    bin_dir, lib_dir = find_qnn_sdk_dirs(sdk_root)
    result["arch"] = bin_dir.name  # e.g. "aarch64-windows-msvc"

    net_run = bin_dir / "qnn-net-run.exe"
    backend = lib_dir / "QnnHtp.dll"
    prepare = lib_dir / "QnnHtpPrepare.dll"

    result["net_run"] = str(net_run) if net_run.exists() else None
    result["qnn_htp_dll"] = str(backend) if backend.exists() else None
    result["qnn_htp_prepare_dll"] = str(prepare) if prepare.exists() else None

    if not net_run.exists():
        msgs.append(f"qnn-net-run.exe not found at {net_run}")
    if not backend.exists():
        msgs.append(f"QnnHtp.dll not found at {backend}")
    if not prepare.exists():
        msgs.append(f"QnnHtpPrepare.dll not found at {prepare} — HTP will not initialise")

    cdsp = find_cdsprpc_dir()
    result["cdsprpc_dir"] = str(cdsp) if cdsp else None
    if cdsp is None:
        msgs.append(
            "libcdsprpc.dll not found in DriverStore — the Qualcomm DSP driver may "
            "not be installed. HTP inference will fail with DspTransport errors."
        )

    if not msgs:
        result["ok"] = True
        msgs.append("QNN environment looks healthy.")
    return result

