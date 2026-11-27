from __future__ import annotations

"""
Train a wakeword KWS model (PyTorch) and optionally export to ONNX.

What it produces (defaults under ./output/)
-------------------------------------------
- `pytorch_kws_model.pt`        (PyTorch checkpoint used by export)
- `pytorch_kws_labels.json`     (label order used by training + inference)
- `pytorch_kws_model.onnx`      (optional; with --export-onnx)
- `pytorch_kws_config.json`     (optional; with --export-onnx)

Dataset expectation
-------------------
This script expects a Speech Commands-like folder containing:
- `<keyword>/` wav files (positive class)
- other word folders (used to form `_unknown_`), and/or you can point to a subset
- `_background_noise_/` wav files (used to synthesize `_silence_`)
- `validation_list.txt` and `testing_list.txt` (official split files)

Timing info
-----------
The script prints wall-clock timing for:
- total training duration
- per-epoch duration (plus a simple ETA based on average epoch time)
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset


@dataclass(frozen=True)
class FeatCfg:
    sample_rate: int = 16000
    clip_seconds: float = 1.0
    n_fft: int = 512
    hop_length: int = 160
    n_mels: int = 40
    fmin: int = 20
    fmax: int = 7600
    log_eps: float = 1e-6
    stft_impl: str = "loop"  # "loop" (default) or "vectorized"

    @property
    def clip_samples(self) -> int:
        return int(round(self.sample_rate * self.clip_seconds))


class DepthwiseSeparableConv2d(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, *, kernel_size: int = 3, stride: int = 1, padding: int = 1):
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_ch,
            in_ch,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            groups=in_ch,
            bias=False,
        )
        self.pointwise = nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        return F.relu(x, inplace=True)


class KWSDscnn(nn.Module):
    def __init__(self, num_classes: int):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )
        self.blocks = nn.Sequential(
            DepthwiseSeparableConv2d(64, 64),
            nn.MaxPool2d(kernel_size=2),
            DepthwiseSeparableConv2d(64, 128),
            nn.MaxPool2d(kernel_size=2),
            DepthwiseSeparableConv2d(128, 128),
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.blocks(x)
        return self.head(x)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train KWS wakeword model and export artifacts for ONNX streaming demo.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--speech-commands-dir",
        type=Path,
        default=Path(os.environ.get("SPEECH_COMMANDS_DIR", "speech_commands_v0.02_min")),
        help="Root folder containing Speech Commands v0.02 (or a subset).",
    )
    p.add_argument("--keyword", default="hey_dragon", help="Keyword label (folder name) to detect.")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--out-dir", type=Path, default=Path("output"))
    p.add_argument("--model-path", type=Path, default=Path("output/pytorch_kws_model.pt"))
    p.add_argument("--labels-path", type=Path, default=Path("output/pytorch_kws_labels.json"))
    p.add_argument("--export-onnx", action="store_true", help="Also run export_pytorch_to_onnx.py after training.")
    p.add_argument("--onnx-path", type=Path, default=Path("output/pytorch_kws_model.onnx"))
    p.add_argument("--config-path", type=Path, default=Path("output/pytorch_kws_config.json"))
    p.add_argument("--opset", type=int, default=17, help="ONNX opset for export (only with --export-onnx).")

    p.add_argument(
        "--unknown-max-words",
        type=int,
        default=30,
        help="Max distinct non-keyword words to include for the _unknown_ class.",
    )
    p.add_argument(
        "--unknown-per-word",
        type=int,
        default=60,
        help="Max clips per non-keyword word to include for the _unknown_ class (per split).",
    )
    p.add_argument(
        "--silence-count",
        type=int,
        default=400,
        help="Synthetic silence/noise clips per split (mix of background_noise + near-silence).",
    )
    p.add_argument("--noise-prob", type=float, default=0.8, help="Probability of mixing background noise.")
    p.add_argument("--noise-min-snr", type=float, default=0.0, help="Min SNR for noise mix (dB).")
    p.add_argument("--noise-max-snr", type=float, default=20.0, help="Max SNR for noise mix (dB).")
    p.add_argument("--gain-prob", type=float, default=0.7, help="Probability of applying random gain.")
    p.add_argument("--time-shift-ms", type=int, default=100, help="Max time shift in ms.")

    # Feature extraction knobs (trade accuracy vs. speed; important for UNOQ CPU training)
    p.add_argument("--sample-rate", type=int, default=16000, help="Feature sample rate (resampled if needed).")
    p.add_argument("--clip-seconds", type=float, default=1.0, help="Clip duration in seconds.")
    p.add_argument("--n-fft", type=int, default=512, help="STFT FFT size.")
    p.add_argument("--hop-length", type=int, default=160, help="STFT hop length in samples.")
    p.add_argument("--n-mels", type=int, default=40, help="Number of mel bins.")
    p.add_argument("--fmin", type=int, default=20, help="Mel filterbank min frequency (Hz).")
    p.add_argument("--fmax", type=int, default=7600, help="Mel filterbank max frequency (Hz).")
    p.add_argument(
        "--stft-impl",
        default="loop",
        choices=("loop", "vectorized"),
        help="STFT implementation. 'loop' is most compatible; 'vectorized' may be faster on some systems.",
    )
    return p.parse_args()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_dt(dt: datetime) -> str:
    # ISO-like but compact; always UTC to avoid confusion across machines.
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_td(seconds: float) -> str:
    return str(timedelta(seconds=int(round(seconds))))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _read_lines(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _split_sets(sc_root: Path) -> tuple[set[str], set[str]]:
    val_list = set(_read_lines(sc_root / "validation_list.txt"))
    test_list = set(_read_lines(sc_root / "testing_list.txt"))
    return val_list, test_list


def _load_wav_mono_16bit(path: Path) -> tuple[np.ndarray, int]:
    import wave

    with wave.open(str(path), "rb") as wf:
        sr = int(wf.getframerate())
        n_ch = int(wf.getnchannels())
        sampwidth = int(wf.getsampwidth())
        n_frames = int(wf.getnframes())
        raw = wf.readframes(n_frames)
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM WAV, got sampwidth={sampwidth} for {path}")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_ch > 1:
        x = x.reshape(-1, n_ch).mean(axis=1)
    return x, sr


def _resample_linear(x: np.ndarray, *, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    n_out = int(round(len(x) * sr_out / sr_in))
    if n_out <= 1:
        return np.zeros((0,), dtype=np.float32)
    x_old = np.linspace(0.0, 1.0, num=len(x), endpoint=False, dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False, dtype=np.float32)
    return np.interp(x_new, x_old, x).astype(np.float32, copy=False)


def _clip_or_pad(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    return np.pad(x, (0, n - len(x)), mode="constant")


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64) + 1e-12))


def _mix_noise(clean: np.ndarray, noise: np.ndarray, *, snr_db: float) -> np.ndarray:
    clean_rms = _rms(clean)
    noise_rms = _rms(noise)
    if noise_rms <= 0.0:
        return clean
    desired_noise_rms = clean_rms / (10 ** (snr_db / 20.0))
    scale = desired_noise_rms / noise_rms
    y = clean + noise * scale
    return np.clip(y, -1.0, 1.0).astype(np.float32, copy=False)


def _time_shift(x: np.ndarray, *, max_shift: int) -> np.ndarray:
    if max_shift <= 0:
        return x
    shift = random.randint(-max_shift, max_shift)
    if shift == 0:
        return x
    if shift > 0:
        return np.pad(x, (shift, 0), mode="constant")[: len(x)]
    return np.pad(x, (0, -shift), mode="constant")[-shift:]


def _random_gain(x: np.ndarray) -> np.ndarray:
    # +/- ~6 dB
    g = 10 ** (random.uniform(-6.0, 6.0) / 20.0)
    return np.clip(x * g, -1.0, 1.0).astype(np.float32, copy=False)


def _list_word_dirs(sc_root: Path) -> list[Path]:
    return [p for p in sc_root.iterdir() if p.is_dir() and not p.name.startswith("_")]


def _all_wavs(word_dir: Path) -> list[Path]:
    return sorted(word_dir.glob("*.wav"))


def _split_of(rel_posix: str, *, val_list: set[str], test_list: set[str]) -> str:
    if rel_posix in val_list:
        return "val"
    if rel_posix in test_list:
        return "test"
    return "train"


@dataclass(frozen=True)
class Example:
    path: Path
    label: str
    split: str


def _collect_examples(
    *,
    sc_root: Path,
    keyword: str,
    unknown_max_words: int,
    unknown_per_word: int,
    include_silence: bool,
    silence_count: int,
    rng: np.random.Generator,
) -> tuple[list[Example], list[str]]:
    val_list, test_list = _split_sets(sc_root)

    def rel_under_root(p: Path) -> str:
        return p.relative_to(sc_root).as_posix()

    all_labels = sorted([p.name for p in _list_word_dirs(sc_root)])
    if keyword not in all_labels:
        raise ValueError(f"Keyword folder not found under dataset root: {keyword!r}")

    target_words = [keyword]
    UNKNOWN_LABEL = "_unknown_"
    SILENCE_LABEL = "_silence_"

    examples: list[Example] = []

    # Targets
    # Use recursive discovery to be resilient to accidental nesting like:
    #   speech_commands/.../hey_dragon/hey_dragon_0001.wav
    #   speech_commands/.../hey_dragon/hey_dragon/hey_dragon_0002.wav
    for p in sorted(_all_wavs(sc_root / keyword)):
        rel = rel_under_root(p)
        examples.append(Example(path=p, label=keyword, split=_split_of(rel, val_list=val_list, test_list=test_list)))

    # Unknown = sample from other word dirs (balanced roughly to keyword counts per split).
    #
    # IMPORTANT: If your dataset root only contains the keyword folder (e.g. a tiny subset),
    # then there are no "unknown" word folders to sample from. Training without unknown
    # examples will usually produce a trigger-happy model (high false positives on random
    # speech). In that case you should either:
    #   - Point --speech-commands-dir at a dataset containing additional word folders, or
    #   - Build a minimal subset that includes a few negative word folders (recommended).
    unknown_labels = [l for l in all_labels if l not in target_words]
    if unknown_max_words is not None and int(unknown_max_words) <= 0:
        unknown_labels = []
    if unknown_max_words is not None and len(unknown_labels) > int(unknown_max_words):
        unknown_labels = list(rng.choice(unknown_labels, size=int(unknown_max_words), replace=False))

    unknown_files_by_split: dict[str, list[Path]] = {"train": [], "val": [], "test": []}
    for lab in sorted(unknown_labels):
        files = _all_wavs(sc_root / lab)
        if unknown_per_word is not None and len(files) > int(unknown_per_word):
            idx = rng.choice(len(files), size=int(unknown_per_word), replace=False)
            files = [files[i] for i in idx]
        for p in files:
            rel = rel_under_root(p)
            unknown_files_by_split[_split_of(rel, val_list=val_list, test_list=test_list)].append(p)

    target_counts_by_split = {
        "train": sum(1 for e in examples if e.split == "train"),
        "val": sum(1 for e in examples if e.split == "val"),
        "test": sum(1 for e in examples if e.split == "test"),
    }

    have_unknown = any(len(v) > 0 for v in unknown_files_by_split.values())
    if have_unknown:
        for split, files in unknown_files_by_split.items():
            files = sorted(files)
            keep = min(len(files), int(target_counts_by_split[split]))
            if keep <= 0:
                continue
            idx = rng.choice(len(files), size=keep, replace=False)
            for p in (files[i] for i in idx):
                examples.append(Example(path=p, label=UNKNOWN_LABEL, split=split))

    # Silence from background noise (if present)
    if include_silence:
        noise_dir = sc_root / "_background_noise_"
        noise_files = sorted(noise_dir.glob("*.wav")) if noise_dir.exists() else []
        if noise_files:
            for split in ("train", "val", "test"):
                for _ in range(int(silence_count)):
                    p = noise_files[int(rng.integers(0, len(noise_files)))]
                    examples.append(Example(path=p, label=SILENCE_LABEL, split=split))

    if include_silence:
        label_order = [SILENCE_LABEL, keyword, UNKNOWN_LABEL] if have_unknown else [SILENCE_LABEL, keyword]
    else:
        label_order = [keyword, UNKNOWN_LABEL] if have_unknown else [keyword]
    return examples, label_order


def _mel_filterbank(*, sr: int, n_fft: int, n_mels: int, fmin: float, fmax: float) -> np.ndarray:
    # Match librosa defaults: htk=False, norm="slaney".
    def hz_to_mel_slaney(f: np.ndarray) -> np.ndarray:
        f_sp = 200.0 / 3
        min_log_hz = 1000.0
        min_log_mel = min_log_hz / f_sp
        logstep = np.log(6.4) / 27.0

        m = f / f_sp
        idx = f >= min_log_hz
        m[idx] = min_log_mel + np.log(f[idx] / min_log_hz) / logstep
        return m

    def mel_to_hz_slaney(m: np.ndarray) -> np.ndarray:
        f_sp = 200.0 / 3
        min_log_hz = 1000.0
        min_log_mel = min_log_hz / f_sp
        logstep = np.log(6.4) / 27.0

        f = f_sp * m
        idx = m >= min_log_mel
        f[idx] = min_log_hz * np.exp(logstep * (m[idx] - min_log_mel))
        return f

    n_freqs = 1 + n_fft // 2
    fft_freqs = np.linspace(0.0, float(sr) / 2.0, n_freqs, dtype=np.float64)

    m_min = float(hz_to_mel_slaney(np.array([fmin], dtype=np.float64))[0])
    m_max = float(hz_to_mel_slaney(np.array([fmax], dtype=np.float64))[0])
    m_pts = np.linspace(m_min, m_max, n_mels + 2, dtype=np.float64)
    f_pts = mel_to_hz_slaney(m_pts)

    fdiff = np.diff(f_pts)
    ramps = f_pts[:, None] - fft_freqs[None, :]

    weights = np.zeros((n_mels, n_freqs), dtype=np.float64)
    for i in range(n_mels):
        lower = -ramps[i] / fdiff[i]
        upper = ramps[i + 2] / fdiff[i + 1]
        weights[i] = np.maximum(0.0, np.minimum(lower, upper))

    enorm = 2.0 / (f_pts[2 : n_mels + 2] - f_pts[:n_mels])
    weights *= enorm[:, None]
    return weights.astype(np.float32)


def _stft_power(y: np.ndarray, *, n_fft: int, hop_length: int, impl: str) -> np.ndarray:
    pad = n_fft // 2
    y = np.pad(y, (pad, pad), mode="reflect")
    if y.shape[0] < n_fft:
        y = np.pad(y, (0, n_fft - y.shape[0]), mode="constant")

    window = np.hanning(n_fft).astype(np.float32)

    if impl == "vectorized":
        try:
            from numpy.lib.stride_tricks import sliding_window_view

            frames = sliding_window_view(y.astype(np.float32), n_fft)[::hop_length]
            frames = frames * window[None, :]
            spec = np.fft.rfft(frames, axis=1)
            power = (np.abs(spec) ** 2).astype(np.float32)
            return power.T  # (n_freqs, n_frames)
        except Exception:
            impl = "loop"

    n_frames = 1 + (y.shape[0] - n_fft) // hop_length
    n_freqs = 1 + n_fft // 2
    out = np.empty((n_freqs, n_frames), dtype=np.float32)
    for i in range(n_frames):
        start = i * hop_length
        frame = y[start : start + n_fft] * window
        spec = np.fft.rfft(frame.astype(np.float32))
        out[:, i] = (np.abs(spec) ** 2).astype(np.float32)
    return out


def _log_mel(y: np.ndarray, *, cfg: FeatCfg, mel_fb: np.ndarray) -> np.ndarray:
    power = _stft_power(y.astype(np.float32), n_fft=cfg.n_fft, hop_length=cfg.hop_length, impl=cfg.stft_impl)
    mel = mel_fb @ power
    log_mel = np.log(np.maximum(mel, cfg.log_eps))
    # Per-clip standardization. The notebook and kws_keyword_beep_onnx.py apply the same step at
    # inference, so a model trained here must see identical features or it will not trigger there.
    log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-6)
    return log_mel.astype(np.float32, copy=False)


class KwsDataset(Dataset):
    def __init__(
        self,
        *,
        examples: list[Example],
        label_to_idx: dict[str, int],
        cfg: FeatCfg,
        mel_fb: np.ndarray,
        split: str,
        rng: np.random.Generator,
        noise_files: list[Path],
        noise_prob: float,
        noise_min_snr: float,
        noise_max_snr: float,
        gain_prob: float,
        time_shift_ms: int,
    ):
        self.examples = [e for e in examples if e.split == split]
        self.label_to_idx = label_to_idx
        self.cfg = cfg
        self.mel_fb = mel_fb
        self.split = split
        self.rng = rng
        self.noise_files = noise_files
        self.noise_prob = float(noise_prob)
        self.noise_min_snr = float(noise_min_snr)
        self.noise_max_snr = float(noise_max_snr)
        self.gain_prob = float(gain_prob)
        self.time_shift = int(round((time_shift_ms / 1000.0) * cfg.sample_rate))

    def __len__(self) -> int:
        return len(self.examples)

    def _load_clip(self, path: Path, *, is_silence: bool) -> np.ndarray:
        y, sr = _load_wav_mono_16bit(path)
        y = _resample_linear(y, sr_in=sr, sr_out=self.cfg.sample_rate)

        if is_silence and len(y) > self.cfg.clip_samples:
            start = int(self.rng.integers(0, len(y) - self.cfg.clip_samples + 1))
            y = y[start : start + self.cfg.clip_samples]

        y = _clip_or_pad(y, self.cfg.clip_samples)

        if self.time_shift > 0:
            y = _time_shift(y, max_shift=self.time_shift)

        # Mix noise
        if self.noise_files and random.random() < self.noise_prob:
            noise_path = self.noise_files[int(self.rng.integers(0, len(self.noise_files)))]
            n, sr_n = _load_wav_mono_16bit(noise_path)
            n = _resample_linear(n, sr_in=sr_n, sr_out=self.cfg.sample_rate)
            if len(n) >= self.cfg.clip_samples:
                start = int(self.rng.integers(0, len(n) - self.cfg.clip_samples + 1))
                n = n[start : start + self.cfg.clip_samples]
            n = _clip_or_pad(n, self.cfg.clip_samples)
            snr = random.uniform(self.noise_min_snr, self.noise_max_snr)
            y = _mix_noise(y, n, snr_db=snr)

        # Random gain
        if random.random() < self.gain_prob:
            y = _random_gain(y)

        return y.astype(np.float32, copy=False)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        e = self.examples[idx]
        is_silence = e.label == "_silence_"
        y = self._load_clip(e.path, is_silence=is_silence)
        feat = _log_mel(y, cfg=self.cfg, mel_fb=self.mel_fb)
        x = torch.from_numpy(feat[None, :, :])  # (1, n_mels, n_frames)
        y_idx = torch.tensor(int(self.label_to_idx[e.label]), dtype=torch.long)
        return x, y_idx


def _train_epoch(model: nn.Module, loader: DataLoader, *, device: str, opt: torch.optim.Optimizer) -> float:
    model.train()
    total = 0.0
    n = 0
    for xb, yb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        opt.zero_grad(set_to_none=True)
        logits = model(xb)
        loss = F.cross_entropy(logits, yb)
        loss.backward()
        opt.step()
        total += float(loss.item()) * int(xb.shape[0])
        n += int(xb.shape[0])
    return total / max(1, n)


@torch.no_grad()
def _eval_acc(model: nn.Module, loader: DataLoader, *, device: str) -> float:
    model.eval()
    correct = 0
    total = 0
    for xb, yb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        logits = model(xb)
        preds = logits.argmax(dim=1)
        correct += int((preds == yb).sum().item())
        total += int(yb.shape[0])
    return correct / max(1, total)


def main() -> None:
    args = parse_args()
    set_seed(int(args.seed))

    t0 = time.perf_counter()
    start = _now_utc()
    print(f"start={_fmt_dt(start)}")

    sc_root = Path(args.speech_commands_dir)
    if not sc_root.exists():
        raise FileNotFoundError(f"Speech Commands dir not found: {sc_root.resolve()}")

    rng = np.random.default_rng(int(args.seed))
    examples, label_order = _collect_examples(
        sc_root=sc_root,
        keyword=str(args.keyword),
        unknown_max_words=int(args.unknown_max_words),
        unknown_per_word=int(args.unknown_per_word),
        include_silence=True,
        silence_count=int(args.silence_count),
        rng=rng,
    )

    label_to_idx = {lab: i for i, lab in enumerate(label_order)}

    cfg = FeatCfg(
        sample_rate=int(args.sample_rate),
        clip_seconds=float(args.clip_seconds),
        n_fft=int(args.n_fft),
        hop_length=int(args.hop_length),
        n_mels=int(args.n_mels),
        fmin=int(args.fmin),
        fmax=int(args.fmax),
        stft_impl=str(args.stft_impl),
    )
    mel_fb = _mel_filterbank(
        sr=cfg.sample_rate,
        n_fft=cfg.n_fft,
        n_mels=cfg.n_mels,
        fmin=cfg.fmin,
        fmax=cfg.fmax,
    )

    noise_dir = sc_root / "_background_noise_"
    noise_files = sorted(noise_dir.glob("*.wav")) if noise_dir.exists() else []

    train_ds = KwsDataset(
        examples=examples,
        label_to_idx=label_to_idx,
        cfg=cfg,
        mel_fb=mel_fb,
        split="train",
        rng=rng,
        noise_files=noise_files,
        noise_prob=float(args.noise_prob),
        noise_min_snr=float(args.noise_min_snr),
        noise_max_snr=float(args.noise_max_snr),
        gain_prob=float(args.gain_prob),
        time_shift_ms=int(args.time_shift_ms),
    )
    val_ds = KwsDataset(
        examples=examples,
        label_to_idx=label_to_idx,
        cfg=cfg,
        mel_fb=mel_fb,
        split="val",
        rng=rng,
        noise_files=noise_files,
        noise_prob=0.0,
        noise_min_snr=float(args.noise_min_snr),
        noise_max_snr=float(args.noise_max_snr),
        gain_prob=0.0,
        time_shift_ms=0,
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=int(args.batch_size),
        shuffle=True,
        num_workers=int(args.num_workers),
        pin_memory=False,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=int(args.batch_size),
        shuffle=False,
        num_workers=int(args.num_workers),
        pin_memory=False,
    )

    model = KWSDscnn(num_classes=len(label_order)).to(str(args.device))
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr))

    print(f"labels={label_order}")
    print(f"train_examples={len(train_ds)} val_examples={len(val_ds)}")

    best_acc = -1.0
    best_state: dict[str, torch.Tensor] | None = None
    epoch_times: list[float] = []
    for epoch in range(int(args.epochs)):
        e0 = time.perf_counter()
        loss = _train_epoch(model, train_loader, device=str(args.device), opt=opt)
        acc = _eval_acc(model, val_loader, device=str(args.device))
        e_dt = time.perf_counter() - e0
        epoch_times.append(float(e_dt))

        avg = float(sum(epoch_times) / len(epoch_times))
        remaining = max(0, int(args.epochs) - (epoch + 1))
        eta_s = remaining * avg
        print(
            f"epoch={epoch+1}/{int(args.epochs)} "
            f"loss={loss:.4f} val_acc={acc:.4f} "
            f"epoch_time={_fmt_td(e_dt)} eta={_fmt_td(eta_s)}"
        )
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ckpt = {
        "model_type": "KWSDscnn",
        "state_dict": model.cpu().state_dict(),
        "sample_rate": cfg.sample_rate,
        "clip_samples": cfg.clip_samples,
        "n_fft": cfg.n_fft,
        "hop_length": cfg.hop_length,
        "n_mels": cfg.n_mels,
        "fmin": cfg.fmin,
        "fmax": cfg.fmax,
    }

    model_path = Path(args.model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(ckpt, model_path)

    labels_path = Path(args.labels_path)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.write_text(json.dumps(label_order, indent=2), encoding="utf-8")

    print("wrote", model_path)
    print("wrote", labels_path)

    if bool(args.export_onnx):
        # Avoid importing subprocess/sys at module import time on minimal systems.
        import subprocess
        import sys

        export_py = Path(__file__).resolve().parent / "export_pytorch_to_onnx.py"
        cmd = [
            sys.executable,
            str(export_py),
            "--pt",
            str(model_path),
            "--labels",
            str(labels_path),
            "--onnx",
            str(Path(args.onnx_path)),
            "--config",
            str(Path(args.config_path)),
            "--opset",
            str(int(args.opset)),
        ]
        subprocess.run(cmd, check=True)

    end = _now_utc()
    total = time.perf_counter() - t0
    print(f"end={_fmt_dt(end)} total_time={_fmt_td(total)}")


if __name__ == "__main__":
    main()
