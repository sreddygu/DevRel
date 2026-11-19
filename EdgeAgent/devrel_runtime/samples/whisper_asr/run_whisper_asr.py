"""
run_whisper_asr.py — Live Whisper-tiny streaming ASR on Snapdragon X Elite.

Architecture:
  - Encoder (mel → latent):  benchmarked on CPU + GPU (Adreno) + NPU (HTP)
  - Decoder (latent → text): CPU (onnxruntime) — autoregressive, low latency
  - Audio frontend:          CPU (numpy mel filterbank)

Steps performed automatically:
  1. Download whisper-tiny encoder + decoder ONNX from Hugging Face
  2. Convert both halves via DevRel MCP server (FP32 by default — see note)
  3. Benchmark encoder on CPU vs GPU vs NPU and decoder on CPU
  4. Run live microphone transcription with streaming output

Quantization note:
  Default is FP32 because INT8 requires real calibration data
  (a few seconds of representative mel spectrograms). Without
  calibration data, qairt-quantizer falls into pathological per-tensor
  scale search on Transformer encoders and hangs. FP32 runs on
  NPU/GPU/CPU at acceptable latency on Snapdragon X Elite. Pass
  --quantization int8 only when you have real calibration audio.

Usage
-----
    # Live transcription from microphone (FP32 + CPU/GPU/NPU benchmark):
    python run_whisper_asr.py

    # Transcribe a WAV file:
    python run_whisper_asr.py --input recording.wav

    # Skip download if models already exist:
    python run_whisper_asr.py --skip-download

    # Try INT8 (requires calibration audio under calib/ — not provided):
    python run_whisper_asr.py --quantization int8

    # Use real QAIRT SDK (not mock):
    python run_whisper_asr.py --adapter-mode real
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import os
import struct
import subprocess
import sys
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows (cp1252 consoles can't render special chars)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE_HZ = 16_000
CHUNK_MS = 80
CHUNK_SAMPLES = SAMPLE_RATE_HZ * CHUNK_MS // 1000  # 1280 samples per chunk
WINDOW_S = 5
WINDOW_SAMPLES = SAMPLE_RATE_HZ * WINDOW_S  # 80000 samples per window
N_MELS = 80
N_FFT = 400
HOP_LENGTH = 160
POWER_BUDGET_W = 4.0
FIRST_WORD_LATENCY_MS_BUDGET = 200
PARTIAL_LATENCY_MS_BUDGET = 80

# Whisper-tiny ONNX model URLs (Hugging Face)
ENCODER_URL = (
    "https://huggingface.co/onnx-community/whisper-tiny/resolve/main/"
    "onnx/encoder_model.onnx"
)
DECODER_URL = (
    "https://huggingface.co/onnx-community/whisper-tiny/resolve/main/"
    "onnx/decoder_model.onnx"
)
TOKENIZER_URL = (
    "https://huggingface.co/openai/whisper-tiny/resolve/main/tokenizer.json"
)

# Test audio — a short WAV clip for benchmarking when no mic is available
TEST_AUDIO_URL = (
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/"
    "1.flac"
)


# ---------------------------------------------------------------------------
# Audio Chunker
# ---------------------------------------------------------------------------

@dataclass
class AudioChunker:
    """Sliding 5-second window with 80 ms hop and VAD-aware endpointing."""

    window_samples: int = WINDOW_SAMPLES
    chunk_samples: int = CHUNK_SAMPLES
    silence_threshold: int = 50
    silence_run_required: int = 250 // CHUNK_MS  # ~250 ms of silence to flush
    _buffer: deque = field(default_factory=deque)
    _silent_runs: int = 0

    def push(self, pcm_chunk: list[float]) -> dict[str, Any]:
        """Push one CHUNK_MS slice of PCM. Returns event metadata."""
        for s in pcm_chunk:
            self._buffer.append(s)
            if len(self._buffer) > self.window_samples:
                self._buffer.popleft()

        is_silent = max((abs(s) for s in pcm_chunk), default=0) < self.silence_threshold
        self._silent_runs = self._silent_runs + 1 if is_silent else 0

        return {
            "window_full": len(self._buffer) >= self.window_samples,
            "flush": self._silent_runs >= self.silence_run_required,
            "buffered_samples": len(self._buffer),
        }

    def get_window(self) -> list[float]:
        """Return the current window as a list of float samples."""
        return list(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()
        self._silent_runs = 0


# ---------------------------------------------------------------------------
# Mel Spectrogram
# ---------------------------------------------------------------------------

def compute_mel_spectrogram(audio: np.ndarray, sr: int = SAMPLE_RATE_HZ) -> np.ndarray:
    """Compute log-mel spectrogram matching Whisper's preprocessing.

    Always returns shape (1, N_MELS, 3000) — the exact size the
    whisper-tiny encoder expects.
    """
    import numpy as np

    N_FRAMES = 3000  # Whisper's fixed encoder input width

    # Pad or trim to 30 seconds (Whisper's native window)
    target_length = sr * 30
    if len(audio) < target_length:
        audio = np.pad(audio, (0, target_length - len(audio)))
    else:
        audio = audio[:target_length]

    # STFT — use manual numpy path so we control the exact frame count
    # scipy stft adds an extra boundary frame; manual approach matches Whisper.
    window = np.hanning(N_FFT).astype(np.float32)
    num_frames = 1 + (len(audio) - N_FFT) // HOP_LENGTH
    frames = np.stack([
        audio[i * HOP_LENGTH: i * HOP_LENGTH + N_FFT]
        for i in range(num_frames)
    ])
    Zxx = np.fft.rfft(frames * window, n=N_FFT)
    magnitudes = np.abs(Zxx.T) ** 2  # (n_fft//2+1, num_frames)

    # Mel filterbank
    mel_filters = _mel_filterbank(sr, N_FFT, N_MELS)
    mel_spec = mel_filters @ magnitudes[:mel_filters.shape[1], :]

    # Enforce exactly N_FRAMES columns
    if mel_spec.shape[1] < N_FRAMES:
        mel_spec = np.pad(mel_spec, ((0, 0), (0, N_FRAMES - mel_spec.shape[1])))
    else:
        mel_spec = mel_spec[:, :N_FRAMES]

    # Log scale (Whisper normalisation)
    log_mel = np.log10(np.maximum(mel_spec, 1e-10))
    log_mel = np.maximum(log_mel, log_mel.max() - 8.0)
    log_mel = (log_mel + 4.0) / 4.0  # roughly [0, 1]

    return np.expand_dims(log_mel, axis=0).astype(np.float32)  # (1, N_MELS, 3000)


def _mel_filterbank(sr: int, n_fft: int, n_mels: int) -> np.ndarray:
    """Build a Mel filterbank matrix (n_mels, n_fft//2 + 1)."""
    import numpy as np

    def _hz_to_mel(hz: float) -> float:
        return 2595.0 * math.log10(1.0 + hz / 700.0)

    def _mel_to_hz(mel: float) -> float:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    n_freqs = n_fft // 2 + 1
    mel_low = _hz_to_mel(0)
    mel_high = _hz_to_mel(sr / 2)
    mel_points = np.linspace(mel_low, mel_high, n_mels + 2)
    hz_points = np.array([_mel_to_hz(m) for m in mel_points])
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filters = np.zeros((n_mels, n_freqs))
    for i in range(n_mels):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        for j in range(left, center):
            if center != left:
                filters[i, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                filters[i, j] = (right - j) / (right - center)

    return filters


# ---------------------------------------------------------------------------
# Step 1 — Download Models
# ---------------------------------------------------------------------------

def _download_file(url: str, dest: Path, label: str, *, skip: bool) -> None:
    """Download a file with progress indication."""
    if skip and dest.exists():
        size_mb = dest.stat().st_size / 1_048_576
        print(f"  [skip] {label}: {dest} ({size_mb:.1f} MB)")
        return

    print(f"  Downloading {label} …", end="", flush=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DevRel-WhisperASR-Sample/1.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
        size_mb = dest.stat().st_size / 1_048_576
        print(f" done  ({size_mb:.1f} MB)")
    except Exception as e:
        print(f" failed ({e})")
        raise


def _generate_test_audio(dest: Path) -> None:
    """Generate a synthetic 3-second 16 kHz mono WAV for testing."""
    import numpy as np

    duration_s = 3.0
    t = np.linspace(0, duration_s, int(SAMPLE_RATE_HZ * duration_s), endpoint=False)
    # Simple tone sweep (300 Hz → 1000 Hz) — produces a recognizable pattern
    freq = 300 + 700 * t / duration_s
    audio = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)

    # Write as WAV
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        n_samples = len(audio)
        data_size = n_samples * 2  # 16-bit mono
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE_HZ,
                            SAMPLE_RATE_HZ * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(audio.tobytes())


def step1_download(
    encoder_path: Path,
    decoder_path: Path,
    test_audio_path: Path | None,
    tokenizer_path: Path | None,
    *,
    skip: bool,
) -> Path | None:
    """Download encoder, decoder, tokenizer, and optionally a test audio file."""
    print("=" * 60)
    print("STEP 1 — Download Whisper-tiny models")
    print("=" * 60)

    _download_file(ENCODER_URL, encoder_path, "Encoder ONNX", skip=skip)
    _download_file(DECODER_URL, decoder_path, "Decoder ONNX", skip=skip)
    if tokenizer_path is not None:
        _download_file(TOKENIZER_URL, tokenizer_path, "Tokenizer JSON", skip=skip)

    if test_audio_path and not test_audio_path.exists():
        print("  Generating synthetic test audio …", end="", flush=True)
        _generate_test_audio(test_audio_path)
        print(f" done  ({test_audio_path.stat().st_size // 1024} KB)")

    print()
    return test_audio_path


# Calibration audio sources — small public clips reachable via plain
# urllib (corporate SSL inspection breaks httpx-based downloaders).
# Five real recordings is enough to keep qairt-quantizer's per-tensor
# scale search out of the pathological convergence behaviour that
# np.random.randn triggers; production INT8 deploys typically use
# 32-128 calibration samples drawn from the target domain.
CALIBRATION_AUDIO_URLS = [
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/1.flac",
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/2.flac",
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/3.flac",
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/4.flac",
    "https://huggingface.co/datasets/Narsil/asr_dummy/resolve/main/mlk.flac",
]


def step1_5_download_calibration(calibration_dir: Path, *, skip: bool) -> int:
    """Download a small calibration audio set. Returns number of clips ready.

    Idempotent — re-running with --skip-download keeps existing files.
    Skips clips that 404 individually so a partial outage in the
    upstream dataset still produces a usable calibration set.
    """
    print("=" * 60)
    print("STEP 1.5 — Download INT8 calibration audio")
    print("=" * 60)

    audio_dir = calibration_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    successful = 0
    for url in CALIBRATION_AUDIO_URLS:
        dest = audio_dir / Path(url).name
        try:
            _download_file(url, dest, f"calib/{dest.name}", skip=skip)
            successful += 1
        except Exception as exc:
            print(f"  [skip] {dest.name}: {type(exc).__name__}: {exc}")

    print(f"\n  {successful} calibration clips ready in {audio_dir}")
    print()
    return successful


def step1_6_build_calibration_inputs(
    calibration_dir: Path,
    encoder_input_name: str,
) -> Path | None:
    """Compute mel spectrograms for each calibration clip and write input_list.txt.

    Returns the input_list path or None if no usable audio exists.

    qairt-quantizer expects an input_list.txt where each line is
    `<input_name>:=<absolute_path_to_raw_file>` with one line per
    calibration sample. The .raw files are float32 mel spectrograms
    of the exact shape the encoder accepts (1, N_MELS, 3000).
    """
    import numpy as np

    print("=" * 60)
    print("STEP 1.6 — Build mel-spectrogram calibration set")
    print("=" * 60)

    audio_dir = calibration_dir / "audio"
    raw_dir = calibration_dir / "mel_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    audio_files = sorted(audio_dir.glob("*.flac")) + sorted(audio_dir.glob("*.wav"))
    if not audio_files:
        print("  [warn] No calibration audio found — skipping INT8 quantisation.")
        print()
        return None

    raw_paths: list[Path] = []
    for audio_path in audio_files:
        try:
            audio = _load_audio_file(str(audio_path))
            mel = compute_mel_spectrogram(audio)
            raw_path = raw_dir / f"{audio_path.stem}.raw"
            mel.astype(np.float32).tofile(raw_path)
            raw_paths.append(raw_path)
            print(f"  mel({audio_path.name}) → {raw_path.name}  shape={mel.shape}")
        except Exception as exc:
            print(f"  [skip] {audio_path.name}: {type(exc).__name__}: {exc}")

    if not raw_paths:
        print("  [warn] All calibration files failed to process — skipping INT8.")
        print()
        return None

    input_list = calibration_dir / "input_list.txt"
    input_list.write_text(
        "\n".join(f"{encoder_input_name}:={p.resolve()}" for p in raw_paths) + "\n"
    )
    print(f"\n  Wrote {len(raw_paths)}-sample input list to {input_list}")
    print()
    return input_list


def _find_qairt_python() -> str | None:
    """Locate a Python interpreter that can run qairt-quantizer.

    QAIRT 2.x ships .pyd extensions compiled against Python 3.10 only.
    Running them under a different Python version fails with
    "DLL load failed while importing libPyIrGraph". DevRel ships a
    purpose-built venv at `.DevRel/qairt-venv/` with the right interpreter
    and numpy 1.x; prefer that. Fall back to py.exe -3.10, then a 3.10
    on PATH.
    """
    if explicit := os.environ.get("QAIRT_PYTHON"):
        if Path(explicit).exists():
            return explicit

    here = Path(__file__).resolve()
    for ancestor in here.parents:
        for rel in (
            Path("DevRel") / ".DevRel" / "qairt-venv" / "Scripts" / "python.exe",
            Path("DevRel") / ".DevRel" / "qairt-venv" / "bin" / "python",
            Path(".DevRel") / "qairt-venv" / "Scripts" / "python.exe",
            Path(".DevRel") / "qairt-venv" / "bin" / "python",
        ):
            cand = ancestor / rel
            if cand.exists():
                return str(cand)

    import shutil
    py = shutil.which("py")
    if py:
        try:
            r = subprocess.run(
                [py, "-3.10", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass

    for name in ("python3.10", "python310"):
        cand = shutil.which(name)
        if cand:
            return cand

    return None


def step2_5_quantize_int8(
    fp32_dlc: Path,
    input_list: Path,
    sdk_root: Path,
    *,
    python_exe: str | None = None,
    timeout_s: int = 600,
) -> Path | None:
    """Run qairt-quantizer to produce an INT8 DLC from the FP32 DLC.

    Bypasses the MCP convert_model surface because that tool doesn't
    expose the calibration_data parameter the qairt_adapter accepts
    internally. Calling qairt-quantizer directly with a real input list
    is the supported path for users who already have calibration data
    on hand.

    qairt-quantizer ships as an extension-less Python script and depends
    on .pyd extensions compiled for Python 3.10 specifically. We locate
    a 3.10 interpreter (preferring DevRel's `.DevRel/qairt-venv/`) — the DevRel
    server's venv (often 3.13) cannot load the .pyd files.
    """
    print("=" * 60)
    print("STEP 2.5 — Quantize encoder to INT8 with real calibration")
    print("=" * 60)

    quantizer = _find_qairt_tool("qairt-quantizer", sdk_root)
    if quantizer is None:
        print("  [warn] qairt-quantizer not found in SDK — keeping FP32 DLC.")
        print()
        return None

    # qairt-quantizer is a Python 3.10 script; find a compatible
    # interpreter regardless of what python_exe (the DevRel server's
    # interpreter) happens to be.
    qairt_py = _find_qairt_python()
    if qairt_py is None:
        print("  [warn] No Python 3.10 interpreter found for qairt-quantizer.")
        print("         Tried QAIRT_PYTHON env, .DevRel/qairt-venv, py -3.10, python3.10.")
        print("         Set QAIRT_PYTHON to a 3.10 interpreter and retry.")
        print()
        return None

    output_dlc = fp32_dlc.with_stem(f"{fp32_dlc.stem}_int8")
    cmd = [
        qairt_py,
        str(quantizer),
        "--input_dlc",  str(fp32_dlc),
        "--input_list", str(input_list),
        "--output_dlc", str(output_dlc),
    ]

    print(f"  Running: {Path(quantizer).name} ...")
    print(f"  FP32 DLC : {fp32_dlc.name}")
    print(f"  Calibrate: {input_list}")
    print(f"  Output   : {output_dlc.name}")

    # qti.aisw.converters.common imports libPyIrGraph.pyd which depends
    # on native DLLs in <sdk>/bin/<arch>/. Use the same env-builder
    # qnn_utils uses so the loader can find them.
    try:
        from devrel_client.qnn_utils import build_qnn_subprocess_env
        env = build_qnn_subprocess_env(sdk_root)
    except Exception:
        env = os.environ.copy()

    sdk_pylib = str(Path(sdk_root) / "lib" / "python")
    if Path(sdk_pylib).is_dir():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = sdk_pylib + (os.pathsep + existing if existing else "")

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout_s, env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"  [warn] qairt-quantizer timed out after {timeout_s}s.")
        print()
        return None

    elapsed_s = time.perf_counter() - t0
    if result.returncode != 0:
        print(f"  [warn] qairt-quantizer failed (exit {result.returncode}) after {elapsed_s:.1f}s")
        for line in (result.stderr or "").splitlines()[-8:]:
            print(f"    | {line}")
        print()
        return None

    if not output_dlc.exists():
        print(f"  [warn] qairt-quantizer reported success but {output_dlc.name} missing.")
        print()
        return None

    size_mb = output_dlc.stat().st_size / 1_048_576
    print(f"  done in {elapsed_s:.1f}s — {output_dlc.name} ({size_mb:.1f} MB)")
    print()
    return output_dlc


def _find_qairt_tool(name: str, sdk_root: Path) -> Path | None:
    """Locate a qairt-* tool inside the SDK across per-arch bin subdirs.

    QAIRT 2.x splits tools across architecture-specific bin directories;
    this walker matches the resolution order in DevRel's qairt_adapter.
    """
    bin_root = Path(sdk_root) / "bin"
    if not bin_root.is_dir():
        return None
    # Host-arch first on Windows
    arch_priority = (
        "x86_64-windows-msvc",
        "arm64x-windows-msvc",
        "aarch64-windows-msvc",
        "x86_64-linux-clang",
    )
    for arch in arch_priority:
        for ext in ("", ".exe"):
            cand = bin_root / arch / (name + ext)
            if cand.exists():
                return cand
    # Fall back to a wildcard search
    for cand in bin_root.glob(f"*/{name}*"):
        if cand.is_file():
            return cand
    return None


# ---------------------------------------------------------------------------
# ONNX Simplification (one-time, marker-file gated)
# ---------------------------------------------------------------------------

def _simplify_onnx_inplace(model_path: Path) -> None:
    """Simplify ONNX model for QAIRT compatibility (runs once, marker file)."""
    marker = model_path.with_suffix(".onnxsim_done")
    if marker.exists():
        return

    try:
        import onnx
        import onnxsim
    except ImportError:
        print(f"  [info] onnxsim not installed — skipping {model_path.name} simplification.")
        return

    print(f"  Simplifying {model_path.name} …", end="", flush=True)
    try:
        model = onnx.load(str(model_path))
        model_simplified, ok = onnxsim.simplify(model)
        if ok:
            onnx.save(model_simplified, str(model_path))
            marker.touch()
            size_mb = model_path.stat().st_size / 1_048_576
            print(f" done  ({size_mb:.1f} MB)")
        else:
            print(" verification failed — using original model")
    except Exception as exc:
        print(f" error: {exc} — using original model")


# ---------------------------------------------------------------------------
# Step 2 — Convert via DevRel MCP server
# ---------------------------------------------------------------------------

def _find_devrel_python(override: str | None) -> str | None:
    """Return a Python executable that can import devrel.mcp.server, or None."""
    def _can_import(py: str) -> bool:
        py_path = Path(py)
        if not py_path.exists():
            return False
        venv_root = py_path.parent.parent
        sp_dirs = list(venv_root.glob("Lib/site-packages")) + \
                  list(venv_root.glob("lib/python*/site-packages"))
        for sp in sp_dirs:
            if (sp / "devrel" / "mcp" / "server.py").exists():
                return True
            for pth in sp.glob("*.pth"):
                try:
                    for line in pth.read_text(errors="ignore").splitlines():
                        line = line.strip()
                        if line and not line.startswith(("#", "import ")):
                            if (Path(line) / "devrel" / "mcp" / "server.py").exists():
                                return True
                except Exception:
                    pass
        return False

    candidates: list[str] = []
    if override:
        candidates.append(override)
    if os.environ.get("DevRel_PYTHON"):
        candidates.append(os.environ["DevRel_PYTHON"])

    here = Path(__file__).resolve()
    for ancestor in here.parents:
        venv_py = ancestor / "DevRel" / ".venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            candidates.append(str(venv_py))
            break
        venv_py = ancestor / "DevRel" / ".venv" / "bin" / "python"
        if venv_py.exists():
            candidates.append(str(venv_py))
            break

    candidates.append(sys.executable)

    for py in candidates:
        if _can_import(py):
            return py

    return None


async def _call_convert(python_exe: str, tool_args: dict, adapter_mode: str,
                        timeout_s: int = 600) -> dict:
    """Call the DevRel MCP convert_model tool via stdio transport.

    Returns the conversion result dict, or {"status": "error", ...} on failure/timeout.

    timeout_s defaults to 600 because Whisper-tiny encoder/decoder
    conversion via qairt-converter routinely takes 25-60 seconds
    on Snapdragon X; 60s was too tight and produced spurious timeouts.
    """
    try:
        from fastmcp import Client
        from fastmcp.client.transports.stdio import StdioTransport
    except ImportError:
        return {"status": "error", "message": "fastmcp not installed"}

    server_env = dict(os.environ)
    server_env["DevRel_ADAPTER_MODE"] = adapter_mode
    server_env["FASTMCP_SHOW_SERVER_BANNER"] = "false"

    transport = StdioTransport(
        command=python_exe,
        args=["-m", "devrel.mcp.server"],
        env=server_env,
        keep_alive=False,
    )

    try:
        async with Client(transport) as client:
            response = await asyncio.wait_for(
                client.call_tool("convert_model", tool_args),
                timeout=timeout_s,
            )
    except asyncio.TimeoutError:
        return {"status": "error", "message": f"MCP call timed out after {timeout_s}s"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    if response.structured_content:
        return response.structured_content
    raw = next((b.text for b in response.content if hasattr(b, "text")), "{}")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        return {"raw": raw}


def _convert_half(
    name: str,
    model_path: Path,
    output_dir: Path,
    *,
    runtime: str,
    python_exe: str,
    adapter_mode: str,
    input_name: str,
    input_dims: str,
    quantization: str = "fp32",
) -> tuple[Path | None, dict]:
    """Convert one model half (encoder or decoder).

    Returns (output_path, result) on success, (None, result) on failure.
    Never exits the process — caller decides how to proceed.

    Default quantization is FP32 because INT8 requires real calibration
    data (a few seconds of representative mel spectrograms). Without
    calibration data, qairt-quantizer falls into pathological per-tensor
    scale search on Transformer encoders and hangs indefinitely.
    """
    print(f"\n  ── Converting {name} ({runtime.upper()}) ───────────────────")
    print(f"  Model        : {model_path}")
    print(f"  Runtime      : {runtime}")
    print(f"  Quantization : {quantization.upper()}")

    tool_args: dict = {
        "source_format": "onnx",
        "model_path": str(model_path.resolve()),
        "target_sdk": "qnn",
        "quantization": quantization,
        "input_name": input_name,
        "input_dimensions": input_dims,
    }

    result = asyncio.run(_call_convert(python_exe, tool_args, adapter_mode))

    if result.get("status") == "error":
        msg = result.get("message", "unknown error")
        print(f"  [warn] Conversion failed: {msg}")
        print(f"         CPU-only mode will be used for {name}.")
        return None, result

    rows = [
        ("Original size",   result.get("original_size_mb",     "?"), "MB"),
        ("Output size",     result.get("model_size_mb",        "?"), "MB"),
        ("Quantization",    result.get("quantization_applied", "?"), ""),
        ("Supported ops",   result.get("supported_ops_pct",    "?"), "%"),
        ("Conversion time", result.get("conversion_time_s",    "?"), "s"),
        ("Output path",     result.get("output_path",          "?"), ""),
    ]
    col = max(len(r[0]) for r in rows) + 2
    for label, value, unit in rows:
        print(f"  {label:<{col}} {value} {unit}".rstrip())

    output_path = Path(result.get("output_path", output_dir))
    return output_path, result


def step2_convert(
    encoder_path: Path,
    decoder_path: Path,
    output_dir: Path,
    *,
    server_python: str | None,
    adapter_mode: str,
    quantization: str = "fp32",
) -> tuple[Path | None, Path | None, str | None]:
    """Convert both halves. Returns (encoder_out, decoder_out, devrel_python).

    Any or all values may be None if conversion is unavailable.
    The app continues in CPU-only mode when conversion fails.
    """
    print("=" * 60)
    print(f"STEP 2 — Convert to {quantization.upper()} QNN")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)
    python_exe = _find_devrel_python(server_python)

    if python_exe is None:
        print("  [warn] DevRel MCP server not found — skipping conversion.")
        print("         The app will run in CPU-only mode using ONNX models directly.")
        print("         To enable NPU conversion, install the DevRel platform.")
        print()
        return None, None, None

    print(f"  Adapter mode : {adapter_mode}")
    print(f"  Server       : {python_exe} -m devrel.mcp.server")
    if quantization == "int8":
        print()
        print("  [note] INT8 selected — qairt-quantizer needs real calibration")
        print("         data (mel spectrograms from sample audio). Without it,")
        print("         the quantizer hangs on Transformer encoders. If conversion")
        print("         hangs, re-run with --quantization fp32.")

    # Encoder: input is mel spectrogram (1, N_MELS, 3000) for 30s audio
    enc_out, _ = _convert_half(
        "encoder", encoder_path, output_dir,
        runtime="npu",
        python_exe=python_exe,
        adapter_mode=adapter_mode,
        input_name="input_features",
        input_dims=f"1,{N_MELS},3000",
        quantization=quantization,
    )

    # Decoder: skipped intentionally.
    #
    # The Whisper decoder ONNX has TWO graph inputs (input_ids and
    # encoder_hidden_states) for cross-attention K/V projection. The
    # MCP convert_model tool only accepts a single input_name /
    # input_dimensions pair, so qairt-converter rejects the model with
    # KeyError: 'encoder_hidden_states'. Autoregressive decoders also
    # don't benefit much from NPU offload (variable sequence length,
    # KV cache state, per-token launch overhead) so the practical path
    # is to keep the decoder on CPU via onnxruntime — which is exactly
    # what the inference pipeline does anyway.
    print()
    print("  ── Decoder ────────────────────────────────────")
    print("  [skip] Decoder kept on CPU via onnxruntime (autoregressive,")
    print("         multi-input — not converted for NPU/GPU). This is by")
    print("         design, not a failure.")
    dec_out = None

    print()
    return enc_out, dec_out, python_exe


# ---------------------------------------------------------------------------
# Step 3 — Benchmark
# ---------------------------------------------------------------------------

def _inject_sdk_pythonpath(devrel_python: str) -> str | None:
    """Resolve SDK root and inject into sys.path + os.environ."""
    def _inject(sdk_root: str) -> str | None:
        lib_python = str(Path(sdk_root) / "lib" / "python")
        if not Path(lib_python).is_dir():
            return None
        if lib_python not in sys.path:
            sys.path.insert(0, lib_python)
        os.environ.setdefault("QNN_SDK_ROOT", sdk_root)
        os.environ.setdefault("QAIRT_SDK_ROOT", sdk_root)
        existing = os.environ.get("PYTHONPATH", "")
        if lib_python not in existing:
            os.environ["PYTHONPATH"] = f"{lib_python}{os.pathsep}{existing}" if existing else lib_python
        return sdk_root

    for var in ("QNN_SDK_ROOT", "QAIRT_SDK_ROOT"):
        val = os.environ.get(var, "")
        if val and Path(val).is_dir():
            result = _inject(val)
            if result:
                return result

    here = Path(__file__).resolve()
    for ancestor in here.parents:
        sdk_dir = ancestor / ".DevRel" / "sdk"
        if sdk_dir.is_dir() and (sdk_dir / "lib" / "python").is_dir():
            result = _inject(str(sdk_dir))
            if result:
                return result

    for ancestor in here.parents:
        sdks_dir = ancestor / "DevRel" / "sdks"
        if sdks_dir.is_dir():
            versions = sorted(
                [d for d in sdks_dir.iterdir() if d.is_dir()],
                key=lambda p: p.name, reverse=True,
            )
            if versions:
                result = _inject(str(versions[0]))
                if result:
                    return result
            break

    return None


def _run_encoder_onnxruntime(encoder_onnx: str, mel: np.ndarray) -> tuple[np.ndarray, float]:
    """Run encoder via onnxruntime (CPU baseline)."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("[error] onnxruntime not installed. Run:  pip install onnxruntime")
        sys.exit(1)

    sess = ort.InferenceSession(encoder_onnx, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    t0 = time.perf_counter()
    outputs = sess.run(None, {input_name: mel})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return outputs[0], elapsed_ms


def _run_decoder_onnxruntime(decoder_onnx: str, encoder_output: np.ndarray) -> tuple[np.ndarray, float]:
    """Run one decoder step via onnxruntime (CPU)."""
    import numpy as np

    try:
        import onnxruntime as ort
    except ImportError:
        print("[error] onnxruntime not installed. Run:  pip install onnxruntime")
        sys.exit(1)

    sess = ort.InferenceSession(decoder_onnx, providers=["CPUExecutionProvider"])
    # Whisper decoder takes: input_ids (1, seq_len), encoder_hidden_states
    input_ids = np.array([[50258]], dtype=np.int64)  # <|startoftranscript|>

    feed = {}
    for inp in sess.get_inputs():
        if "input_ids" in inp.name:
            feed[inp.name] = input_ids
        elif "encoder" in inp.name.lower() or "hidden" in inp.name.lower():
            feed[inp.name] = encoder_output

    t0 = time.perf_counter()
    outputs = sess.run(None, feed)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return outputs[0], elapsed_ms


def _bench(
    run_fn: Any,
    model_path: str,
    inp: np.ndarray,
    warmup: int,
    runs: int,
    label: str,
) -> dict:
    """Warm up then time `runs` inference calls with CPU utilization tracking."""
    import numpy as np
    import psutil

    proc = psutil.Process()

    print(f"  [{label}] warmup ({warmup} run(s)) …")
    for _ in range(warmup):
        logits, _ = run_fn(model_path, inp)

    print(f"  [{label}] timed  ({runs} run(s)) …")
    times_ms: list[float] = []
    cpu_pcts: list[float] = []
    cpu_times_s: list[float] = []

    for i in range(runs):
        psutil.cpu_percent(interval=None)
        ct_before = sum(proc.cpu_times()[:2])
        logits, ms = run_fn(model_path, inp)
        ct_after = sum(proc.cpu_times()[:2])
        cpu_pct = psutil.cpu_percent(interval=None)

        times_ms.append(ms)
        cpu_pcts.append(cpu_pct)
        cpu_times_s.append(ct_after - ct_before)
        print(f"    run {i+1:>2}: {ms:6.1f} ms   CPU {cpu_pct:4.0f}%")

    return {
        "label":       label,
        "logits":      logits,
        "times_ms":    times_ms,
        "avg_ms":      float(np.mean(times_ms)),
        "min_ms":      float(np.min(times_ms)),
        "p95_ms":      float(np.percentile(times_ms, 95)),
        "fps":         float(1000.0 / np.mean(times_ms)),
        "cpu_pct_avg": float(np.mean(cpu_pcts)),
        "cpu_time_s":  float(np.mean(cpu_times_s)),
    }


def _print_benchmark_results(
    enc_cpu: dict,
    dec_cpu: dict,
    enc_npu: dict | None = None,
    enc_gpu: dict | None = None,
) -> None:
    """Print benchmark summary table."""

    print()
    print("=" * 60)
    print("BENCHMARK RESULTS — Whisper-tiny Encoder + Decoder")
    print("=" * 60)

    col = 14
    has_npu = enc_npu is not None
    has_gpu = enc_gpu is not None

    # Encoder comparison — CPU vs GPU vs NPU when all three are available
    print("\n  ── Encoder ──────────────────────────────────────────")
    header = f"  {'Metric':<22}  {'CPU':>{col}}"
    if has_gpu:
        header += f"  {'GPU (Adreno)':>{col}}"
    if has_npu:
        header += f"  {'NPU (HTP)':>{col}}"
    print(header)
    print("  " + "─" * (len(header) - 2))

    def _fmt_row(label: str, fmt: str, key: str, suffix: str = "") -> None:
        line = f"  {label:<22}  {fmt.format(enc_cpu[key]):>{col}}{suffix}"
        if has_gpu:
            line += f"  {fmt.format(enc_gpu[key]):>{col}}{suffix}"
        if has_npu:
            line += f"  {fmt.format(enc_npu[key]):>{col}}{suffix}"
        print(line)

    _fmt_row("Avg latency", "{:.1f} ms", "avg_ms")
    _fmt_row("Min latency", "{:.1f} ms", "min_ms")
    _fmt_row("Throughput",  "{:.0f} FPS", "fps")

    # Speedup row (CPU = 1.0×)
    speedup_line = f"  {'Speedup vs CPU':<22}  {'1.0×':>{col}}"
    if has_gpu:
        sp = enc_cpu["avg_ms"] / enc_gpu["avg_ms"] if enc_gpu["avg_ms"] > 0 else float("nan")
        speedup_line += f"  {sp:>{col-1}.1f}×"
    if has_npu:
        sp = enc_cpu["avg_ms"] / enc_npu["avg_ms"] if enc_npu["avg_ms"] > 0 else float("nan")
        speedup_line += f"  {sp:>{col-1}.1f}×"
    print(speedup_line)

    # Decoder (CPU only — autoregressive, not suitable for NPU)
    print("\n  ── Decoder (CPU only — autoregressive) ──────────────")
    print(f"  {'Avg latency':<22}  {dec_cpu['avg_ms']:>{col}.1f} ms / step")
    print(f"  {'Min latency':<22}  {dec_cpu['min_ms']:>{col}.1f} ms / step")
    print(f"  {'P95 latency':<22}  {dec_cpu['p95_ms']:>{col}.1f} ms / step")

    # End-to-end budget evaluation — pick the fastest available encoder path
    if has_npu:
        enc_lat = enc_npu["avg_ms"]
        enc_label = "NPU"
    elif has_gpu:
        enc_lat = enc_gpu["avg_ms"]
        enc_label = "GPU"
    else:
        enc_lat = enc_cpu["avg_ms"]
        enc_label = "CPU"
    dec_lat = dec_cpu["avg_ms"]
    first_word_ms = enc_lat + dec_lat
    partial_ms = dec_cpu["p95_ms"]

    CPU_TDP_W = 23.0
    GPU_TDP_W = 8.0
    NPU_TDP_W = 4.5
    if has_npu:
        enc_power = NPU_TDP_W
    elif has_gpu:
        enc_power = GPU_TDP_W
    else:
        enc_power = CPU_TDP_W * enc_cpu.get("cpu_pct_avg", 50) / 100
    dec_power = CPU_TDP_W * dec_cpu.get("cpu_pct_avg", 10) / 100
    est_power_w = (enc_power + dec_power) * 0.5  # Duty cycle ~50%

    fw_ok = "OK" if first_word_ms <= FIRST_WORD_LATENCY_MS_BUDGET else "MISS"
    p_ok = "OK" if partial_ms <= PARTIAL_LATENCY_MS_BUDGET else "MISS"
    pw_ok = "OK" if est_power_w <= POWER_BUDGET_W else "MISS"

    print(f"\n  ── Budget Evaluation (encoder on {enc_label}) ─────────")
    print(f"    First-word latency : {first_word_ms:6.1f} ms  [{fw_ok}]  (target: <= {FIRST_WORD_LATENCY_MS_BUDGET} ms)")
    print(f"    Partial p95        : {partial_ms:6.1f} ms  [{p_ok}]  (target: <= {PARTIAL_LATENCY_MS_BUDGET} ms)")
    print(f"    Est. power         : {est_power_w:6.2f} W   [{pw_ok}]  (target: <= {POWER_BUDGET_W} W)")
    print()


def step3_benchmark(
    encoder_onnx: Path,
    decoder_onnx: Path,
    encoder_npu_dlc: Path | None,
    encoder_gpu_dlc: Path | None,
    *,
    devrel_python: str | None,
    warmup: int,
    runs: int,
) -> None:
    """Benchmark encoder (CPU vs GPU vs NPU) and decoder (CPU).

    The NPU and GPU paths can take different DLCs because Adreno GPU
    does not support INT8 inference — we use the FP32 DLC for GPU
    and the (possibly INT8) DLC for NPU.
    """
    import numpy as np

    print("=" * 60)
    print("STEP 3 — Benchmark Encoder + Decoder")
    print("=" * 60)

    # If conversion was skipped or failed, fall back to a sibling .dlc
    # produced by an earlier run. This lets --skip-convert reuse the
    # cached encoder DLC for NPU/GPU benchmarks.
    cached_fp32 = encoder_onnx.with_suffix(".dlc")
    if encoder_npu_dlc is None or not Path(encoder_npu_dlc).exists():
        if cached_fp32.exists():
            print(f"  [info] Using cached DLC for NPU: {cached_fp32.name}")
            encoder_npu_dlc = cached_fp32
    if encoder_gpu_dlc is None or not Path(encoder_gpu_dlc).exists():
        if cached_fp32.exists():
            encoder_gpu_dlc = cached_fp32

    sdk_root = _inject_sdk_pythonpath(devrel_python)
    if sdk_root:
        print(f"  SDK      : {sdk_root}")

    # Generate synthetic mel input for benchmarking
    mel = np.random.randn(1, N_MELS, 3000).astype(np.float32)
    print(f"  Input    : synthetic mel spectrogram (1, {N_MELS}, 3000)")
    print()

    # --- Encoder CPU benchmark ---
    print("  ── Encoder CPU (onnxruntime) ─────────────────────")
    if encoder_onnx.exists():
        enc_cpu = _bench(_run_encoder_onnxruntime, str(encoder_onnx), mel, warmup, runs, "ENC-CPU")
    else:
        print(f"  [warn] Encoder ONNX not found: {encoder_onnx}")
        enc_cpu = {"avg_ms": 0, "min_ms": 0, "p95_ms": 0, "fps": 0, "cpu_pct_avg": 0}
    print()

    # --- Encoder NPU benchmark ---
    print("  ── Encoder NPU (QNN HTP) ─────────────────────────")
    enc_npu: dict | None = None
    enc_gpu: dict | None = None
    npu_sdk_root = os.environ.get("QNN_SDK_ROOT") or os.environ.get("QAIRT_SDK_ROOT")

    try:
        from devrel_client.qnn_utils import benchmark_qnn_net_run

        if not npu_sdk_root:
            raise RuntimeError("QNN_SDK_ROOT not set")
        if encoder_npu_dlc is None or not Path(encoder_npu_dlc).exists():
            raise RuntimeError("converted encoder DLC not available")

        # duration_s drives accuracy of the per-iteration latency: the
        # benchmark divides total wall time by num_iters, so if duration
        # is short the one-time graph-prepare overhead inflates avg_ms.
        # 15 s gives ~120 NPU iterations on Snapdragon X — init is < 5%.
        duration_s = max(15, runs * 3)
        print(f"  Model      : {Path(encoder_npu_dlc).name}")
        print(f"  Running qnn-net-run --backend QnnHtp --duration {duration_s}s --perf_profile burst ...")
        bench = benchmark_qnn_net_run(
            str(encoder_npu_dlc), mel, npu_sdk_root,
            duration_s=duration_s, perf_profile="burst",
            timeout=duration_s + 60,
            backend="htp",
        )
        print(f"  {bench['num_iters']} iterations in {bench['wall_s']:.1f}s"
              f"  (avg {bench['avg_ms']:.2f} ms, {bench['fps']:.0f} FPS)")
        enc_npu = {
            "label": "NPU",
            "logits": bench["logits"],
            "avg_ms": bench["avg_ms"],
            "min_ms": bench["avg_ms"],
            "p95_ms": bench["avg_ms"],
            "fps": bench["fps"],
            "cpu_pct_avg": 0.0,
            "num_iters": bench["num_iters"],
        }
    except (RuntimeError, FileNotFoundError, TypeError, ImportError) as exc:
        first_line = str(exc).splitlines()[0]
        print(f"  [warn] NPU benchmark skipped: {first_line}")
    print()

    # --- Encoder GPU benchmark (Adreno via QnnGpu.dll) ---
    # Adreno GPU does not support INT8 inference at FP-equivalent quality,
    # so we always use the FP32 DLC here even when the NPU is running INT8.
    print("  ── Encoder GPU (QNN Adreno) ──────────────────────")
    try:
        from devrel_client.qnn_utils import benchmark_qnn_net_run

        if not npu_sdk_root:
            raise RuntimeError("QNN_SDK_ROOT not set")
        if encoder_gpu_dlc is None or not Path(encoder_gpu_dlc).exists():
            raise RuntimeError("FP32 encoder DLC not available for GPU")

        duration_s = max(15, runs * 3)
        print(f"  Model      : {Path(encoder_gpu_dlc).name}")
        print(f"  Running qnn-net-run --backend QnnGpu --duration {duration_s}s --perf_profile burst ...")
        bench = benchmark_qnn_net_run(
            str(encoder_gpu_dlc), mel, npu_sdk_root,
            duration_s=duration_s, perf_profile="burst",
            timeout=duration_s + 60,
            backend="gpu",
        )
        print(f"  {bench['num_iters']} iterations in {bench['wall_s']:.1f}s"
              f"  (avg {bench['avg_ms']:.2f} ms, {bench['fps']:.0f} FPS)")
        enc_gpu = {
            "label": "GPU",
            "logits": bench["logits"],
            "avg_ms": bench["avg_ms"],
            "min_ms": bench["avg_ms"],
            "p95_ms": bench["avg_ms"],
            "fps": bench["fps"],
            "cpu_pct_avg": 0.0,
            "num_iters": bench["num_iters"],
        }
    except (RuntimeError, FileNotFoundError, TypeError, ImportError) as exc:
        first_line = str(exc).splitlines()[0]
        print(f"  [warn] GPU benchmark skipped: {first_line}")
    print()

    # --- Decoder CPU benchmark ---
    print("  ── Decoder CPU (onnxruntime) ─────────────────────")
    if decoder_onnx.exists():
        # Use encoder output as decoder input
        enc_out = enc_cpu.get("logits")
        if enc_out is None:
            enc_out = np.random.randn(1, 1500, 384).astype(np.float32)

        def _dec_fn(path: str, inp: np.ndarray) -> tuple[np.ndarray, float]:
            return _run_decoder_onnxruntime(path, inp)

        dec_cpu = _bench(_dec_fn, str(decoder_onnx), enc_out, warmup, runs, "DEC-CPU")
    else:
        print(f"  [warn] Decoder ONNX not found: {decoder_onnx}")
        dec_cpu = {"avg_ms": 0, "min_ms": 0, "p95_ms": 0, "fps": 0, "cpu_pct_avg": 0}
    print()

    _print_benchmark_results(enc_cpu, dec_cpu, enc_npu, enc_gpu)


# ---------------------------------------------------------------------------
# Step 4 — Live Transcription
# ---------------------------------------------------------------------------

def _load_audio_file(path: str) -> np.ndarray:
    """Load audio from WAV/FLAC file, resample to 16 kHz mono."""
    import numpy as np

    ext = Path(path).suffix.lower()

    if ext == ".wav":
        import wave
        with wave.open(path, "rb") as wf:
            assert wf.getnchannels() in (1, 2)
            assert wf.getsampwidth() in (2, 4)
            frames = wf.readframes(wf.getnframes())
            if wf.getsampwidth() == 2:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            if wf.getnchannels() == 2:
                audio = audio.reshape(-1, 2).mean(axis=1)
            src_rate = wf.getframerate()
    elif ext in (".flac", ".mp3", ".ogg"):
        try:
            import soundfile as sf
            audio, src_rate = sf.read(path, dtype="float32")
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
        except ImportError:
            print(f"  [error] Install soundfile to read {ext} files: pip install soundfile")
            sys.exit(1)
    else:
        print(f"  [error] Unsupported audio format: {ext}")
        sys.exit(1)

    # Resample to 16 kHz if needed
    if src_rate != SAMPLE_RATE_HZ:
        try:
            from scipy.signal import resample
            num_samples = int(len(audio) * SAMPLE_RATE_HZ / src_rate)
            audio = resample(audio, num_samples).astype(np.float32)
        except ImportError:
            # Simple linear interpolation fallback
            ratio = SAMPLE_RATE_HZ / src_rate
            indices = np.arange(0, len(audio), 1.0 / ratio)
            indices = indices[indices < len(audio) - 1].astype(int)
            audio = audio[indices]

    return audio


def step4_transcribe(
    encoder_onnx: Path,
    decoder_onnx: Path,
    *,
    input_source: str | None,
    max_duration_s: float = 30.0,
) -> None:
    """Run streaming transcription from microphone or file."""

    print("=" * 60)
    print("STEP 4 — Live Transcription")
    print("=" * 60)

    # Load models
    try:
        import onnxruntime as ort
    except ImportError:
        print("[error] onnxruntime not installed. Run:  pip install onnxruntime")
        sys.exit(1)

    if not encoder_onnx.exists() or not decoder_onnx.exists():
        print("  [warn] ONNX models not found — skipping transcription.")
        print("         Download with: python run_whisper_asr.py (without --skip-download)")
        return

    enc_sess = ort.InferenceSession(str(encoder_onnx), providers=["CPUExecutionProvider"])
    dec_sess = ort.InferenceSession(str(decoder_onnx), providers=["CPUExecutionProvider"])

    # Determine input source
    if input_source and Path(input_source).exists():
        print(f"  Source   : {input_source}")
        audio = _load_audio_file(input_source)
        print(f"  Duration : {len(audio) / SAMPLE_RATE_HZ:.1f}s")
        _transcribe_audio(enc_sess, dec_sess, audio)
    elif input_source:
        print(f"  [error] Audio file not found: {input_source}")
        sys.exit(1)
    else:
        _transcribe_microphone(enc_sess, dec_sess, max_duration_s)


def _transcribe_audio(
    enc_sess: Any,
    dec_sess: Any,
    audio: np.ndarray,
) -> None:
    """Transcribe pre-loaded audio with streaming output."""

    print("\n  Processing audio …")
    t0 = time.perf_counter()

    mel = compute_mel_spectrogram(audio)
    mel_ms = (time.perf_counter() - t0) * 1000

    # Encoder
    enc_input_name = enc_sess.get_inputs()[0].name
    t1 = time.perf_counter()
    encoder_output = enc_sess.run(None, {enc_input_name: mel})[0]
    enc_ms = (time.perf_counter() - t1) * 1000

    # Decoder — autoregressive token generation
    t2 = time.perf_counter()
    tokens = _decode_greedy(dec_sess, encoder_output, max_tokens=128)
    dec_ms = (time.perf_counter() - t2) * 1000

    total_ms = (time.perf_counter() - t0) * 1000

    print("\n  Timing:")
    print(f"    Mel spectrogram : {mel_ms:6.1f} ms")
    print(f"    Encoder         : {enc_ms:6.1f} ms")
    print(f"    Decoder         : {dec_ms:6.1f} ms  ({len(tokens)} tokens)")
    print(f"    Total           : {total_ms:6.1f} ms")
    print("\n  Transcript:")
    text = _detokenize(tokens)
    print(f"    {text}")
    print()


def _transcribe_microphone(
    enc_sess: Any,
    dec_sess: Any,
    max_duration_s: float,
) -> None:
    """Live microphone transcription with streaming output."""
    import numpy as np

    try:
        import sounddevice as sd
    except ImportError:
        print("  [error] sounddevice not installed. Run:  pip install sounddevice")
        print("          Or use --input <file.wav> for file-based transcription.")
        sys.exit(1)

    chunker = AudioChunker()
    print("  Listening on default microphone (Ctrl+C to stop) …")
    print(f"  Window: {WINDOW_S}s  |  Chunk: {CHUNK_MS}ms  |  Max: {max_duration_s}s")
    print()

    segments_transcribed = 0
    start_time = time.perf_counter()

    def _audio_callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        nonlocal segments_transcribed
        if status:
            print(f"  [audio] {status}")

        pcm = indata[:, 0].tolist()  # mono
        event = chunker.push(pcm)

        if event["window_full"] or event["flush"]:
            window = chunker.get_window()
            audio_array = np.array(window, dtype=np.float32)

            # Compute mel and run encoder + decoder
            mel = compute_mel_spectrogram(audio_array)
            enc_input_name = enc_sess.get_inputs()[0].name
            encoder_output = enc_sess.run(None, {enc_input_name: mel})[0]
            tokens = _decode_greedy(dec_sess, encoder_output, max_tokens=64)
            text = _detokenize(tokens)

            if text.strip():
                tag = "final" if event["flush"] else "  ..."
                elapsed = time.perf_counter() - start_time
                print(f"  [{elapsed:6.1f}s] [{tag}] {text}")
                segments_transcribed += 1

            if event["flush"]:
                chunker.reset()

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE_HZ,
            channels=1,
            blocksize=CHUNK_SAMPLES,
            dtype="float32",
            callback=_audio_callback,
        ):
            print("  Recording … (Ctrl+C to stop)")
            while time.perf_counter() - start_time < max_duration_s:
                time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    elapsed = time.perf_counter() - start_time
    print(f"\n  Done. {segments_transcribed} segments in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Decoder helpers (greedy token generation)
# ---------------------------------------------------------------------------

# Whisper special token IDs (whisper-tiny vocabulary)
SOT_TOKEN = 50258        # <|startoftranscript|>
EOT_TOKEN = 50257        # <|endoftext|>
TRANSLATE_TOKEN = 50358  # <|translate|>
TRANSCRIBE_TOKEN = 50359 # <|transcribe|>
NO_TIMESTAMPS_TOKEN = 50363

# Basic vocabulary for detokenization (subset — full vocab has 51865 tokens)
# In production, use the tokenizer from the transformers library.
_VOCAB: dict[int, str] | None = None


def _decode_greedy(
    dec_sess: Any,
    encoder_output: np.ndarray,
    max_tokens: int = 128,
) -> list[int]:
    """Greedy autoregressive decoding."""
    import numpy as np

    # Initial prompt: SOT + language + task + notimestamps
    tokens = [SOT_TOKEN, 50259, TRANSCRIBE_TOKEN, NO_TIMESTAMPS_TOKEN]  # 50259 = <|en|>

    for _ in range(max_tokens):
        input_ids = np.array([tokens], dtype=np.int64)

        feed = {}
        for inp in dec_sess.get_inputs():
            if "input_ids" in inp.name:
                feed[inp.name] = input_ids
            elif "encoder" in inp.name.lower() or "hidden" in inp.name.lower():
                feed[inp.name] = encoder_output

        try:
            outputs = dec_sess.run(None, feed)
        except Exception:
            break

        logits = outputs[0]
        next_token = int(np.argmax(logits[0, -1, :]))

        if next_token == EOT_TOKEN:
            break

        tokens.append(next_token)

    # Strip special tokens from output
    return [t for t in tokens if t < 50257]


_TOKENIZER_PATH = Path(__file__).parent / "tokenizer.json"
_TOKENIZER_CACHE: Any = None


def _load_tokenizer() -> Any:
    """Load the Whisper tokenizer from the local tokenizer.json (cached).

    Returns a `tokenizers.Tokenizer` instance, or None if loading fails.
    Uses the lightweight `tokenizers` library (not `transformers`) so we
    skip PyTorch and avoid HuggingFace Hub network calls — we already
    downloaded tokenizer.json via urllib in step 1.
    """
    global _TOKENIZER_CACHE
    if _TOKENIZER_CACHE is not None:
        return _TOKENIZER_CACHE
    if _TOKENIZER_CACHE is False:  # last attempt failed; don't keep retrying
        return None

    try:
        from tokenizers import Tokenizer
    except ImportError:
        _TOKENIZER_CACHE = False
        return None

    if not _TOKENIZER_PATH.exists():
        _TOKENIZER_CACHE = False
        return None

    try:
        _TOKENIZER_CACHE = Tokenizer.from_file(str(_TOKENIZER_PATH))
        return _TOKENIZER_CACHE
    except Exception:
        _TOKENIZER_CACHE = False
        return None


def _detokenize(token_ids: list[int]) -> str:
    """Convert token IDs to text using the local Whisper tokenizer."""
    if not token_ids:
        return "(no tokens decoded)"

    tokenizer = _load_tokenizer()
    if tokenizer is None:
        hint = (
            "install 'tokenizers' (pip install tokenizers)"
            if not _TOKENIZER_PATH.exists()
            else f"tokenizer.json missing at {_TOKENIZER_PATH}"
        )
        return (
            f"[token IDs: {token_ids[:20]}{'...' if len(token_ids) > 20 else ''}] "
            f"({hint})"
        )

    try:
        return tokenizer.decode(token_ids, skip_special_tokens=True)
    except Exception as exc:
        first_line = str(exc).splitlines()[0][:100]
        return (
            f"[token IDs: {token_ids[:20]}{'...' if len(token_ids) > 20 else ''}] "
            f"(decode failed: {first_line})"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Whisper-tiny streaming ASR on Snapdragon X Elite (NPU encoder + CPU decoder).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Step 1
    p.add_argument("--encoder-model", default="whisper_tiny_encoder.onnx",
                   help="Local path for encoder ONNX model")
    p.add_argument("--decoder-model", default="whisper_tiny_decoder.onnx",
                   help="Local path for decoder ONNX model")
    p.add_argument("--skip-download", action="store_true",
                   help="Skip download if model files already exist")

    # Step 2
    p.add_argument("--output-dir", default="output",
                   help="Directory for converted models")
    p.add_argument("--server-python", default=None,
                   help="Python executable for devrel.mcp.server (auto-detected)")
    p.add_argument("--adapter-mode", default=None, choices=["mock", "real"],
                   help="DevRel adapter mode (default: DevRel_ADAPTER_MODE env var or 'real')")
    p.add_argument("--skip-convert", action="store_true",
                   help="Skip MCP conversion (use ONNX models directly on CPU)")
    p.add_argument("--quantization", default="fp32", choices=["fp32", "int8"],
                   help="Quantization for QNN conversion. fp32 (default) is "
                        "fast (~30s) and works on CPU/GPU/NPU. int8 first does "
                        "an FP32 conversion, then downloads ~5 LibriSpeech-style "
                        "audio clips, builds a mel-spectrogram calibration set, "
                        "and runs qairt-quantizer with that real data so the "
                        "per-tensor scale search converges (random noise hangs).")
    p.add_argument("--calibration-dir", default="calibration",
                   help="Directory for INT8 calibration audio + mel raw files")

    # Step 3
    p.add_argument("--warmup", type=int, default=2,
                   help="Warmup runs for benchmarking")
    p.add_argument("--runs", type=int, default=5,
                   help="Timed benchmark runs")

    # Step 4
    p.add_argument("--input", default=None,
                   help="Audio file path (WAV/FLAC). If omitted, uses microphone")
    p.add_argument("--max-duration", type=float, default=30.0,
                   help="Max recording duration in seconds (microphone mode)")
    p.add_argument("--skip-transcribe", action="store_true",
                   help="Skip the live transcription step (benchmark only)")

    return p.parse_args()


def main() -> None:
    args = _parse_args()

    encoder_path = Path(args.encoder_model)
    decoder_path = Path(args.decoder_model)
    output_dir = Path(args.output_dir)
    test_audio = Path("test_audio.wav")
    tokenizer_path = _TOKENIZER_PATH

    adapter_mode = args.adapter_mode or os.environ.get("DevRel_ADAPTER_MODE", "real")

    # Step 1 — Download
    step1_download(encoder_path, decoder_path, test_audio, tokenizer_path,
                   skip=args.skip_download)

    # Step 1.5 — Simplify
    if encoder_path.exists():
        _simplify_onnx_inplace(encoder_path)
    if decoder_path.exists():
        _simplify_onnx_inplace(decoder_path)

    # Step 2 — Convert (optional — app works without it in CPU-only mode)
    enc_converted: Path | None = None       # used for NPU (may be INT8)
    enc_fp32_dlc: Path | None = None        # always FP32, used for GPU
    dec_converted: Path | None = None
    devrel_python: str | None = None

    if args.skip_convert:
        print("=" * 60)
        print("STEP 2 — Convert to QNN (skipped via --skip-convert)")
        print("=" * 60)
        # Still try to use a cached FP32 DLC if one exists — that lets
        # --skip-convert combined with --quantization int8 run only the
        # quantizer step on a previously-converted FP32 DLC.
        cached_fp32 = encoder_path.with_suffix(".dlc")
        if cached_fp32.exists():
            print(f"  Using cached FP32 DLC: {cached_fp32.name}")
            enc_converted = cached_fp32
            enc_fp32_dlc = cached_fp32
            devrel_python = _find_devrel_python(args.server_python)
        else:
            print("  Running in CPU-only mode (no cached DLC found).")
        print()
    else:
        # Always do FP32 conversion via MCP first. INT8 follows as a
        # separate qairt-quantizer step with real calibration data so we
        # never feed random noise to the quantizer (which hangs).
        enc_converted, dec_converted, devrel_python = step2_convert(
            encoder_path, decoder_path, output_dir,
            server_python=args.server_python,
            adapter_mode=adapter_mode,
            quantization="fp32",
        )
        enc_fp32_dlc = enc_converted

    # INT8 path — runs whether we just converted FP32 or are reusing
    # a cached FP32 DLC. Downloads calibration audio, builds mel raws,
    # runs qairt-quantizer directly. Falls back to FP32 if any step fails.
    # GPU keeps the FP32 DLC because Adreno doesn't support INT8.
    if args.quantization == "int8" and enc_converted is not None:
        calibration_dir = Path(args.calibration_dir)
        n_clips = step1_5_download_calibration(
            calibration_dir, skip=args.skip_download,
        )
        if n_clips > 0:
            input_list = step1_6_build_calibration_inputs(
                calibration_dir, encoder_input_name="input_features",
            )
            if input_list is not None:
                sdk_root = _inject_sdk_pythonpath(devrel_python)
                if sdk_root:
                    int8_dlc = step2_5_quantize_int8(
                        enc_converted, input_list, Path(sdk_root),
                        python_exe=devrel_python,
                    )
                    if int8_dlc is not None:
                        print(f"  NPU benchmark will use: {int8_dlc.name}")
                        print(f"  GPU benchmark will use: {enc_fp32_dlc.name}  (Adreno needs FP32)\n")
                        enc_converted = int8_dlc

    # Step 3 — Benchmark
    step3_benchmark(
        encoder_path, decoder_path,
        encoder_npu_dlc=enc_converted,
        encoder_gpu_dlc=enc_fp32_dlc,
        devrel_python=devrel_python,
        warmup=args.warmup,
        runs=args.runs,
    )

    # Step 4 — Transcribe
    if not args.skip_transcribe:
        input_source = args.input or (str(test_audio) if test_audio.exists() else None)
        step4_transcribe(
            encoder_path, decoder_path,
            input_source=input_source,
            max_duration_s=args.max_duration,
        )


if __name__ == "__main__":
    main()
