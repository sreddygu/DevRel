from __future__ import annotations

"""
Streaming Keyword Spotting (keyword -> beep) using ONNX Runtime (no PyTorch required).

Use this on devices where `import torch` fails (e.g., `Illegal instruction` on some arm64 images).

Required files (default in `output/`)
------------------------------------
- `pytorch_kws_model.onnx`
- `pytorch_kws_config.json`
- `pytorch_kws_labels.json`

Install (Debian recommended via venv)
------------------------------------
    sudo apt-get update
    sudo apt-get install -y python3-venv portaudio19-dev alsa-utils
    python3 -m venv ~/kws-venv
    ~/kws-venv/bin/pip install numpy librosa sounddevice onnxruntime

Run
---
    # Note: `--mic` is a sounddevice/PortAudio selector (device index like `0`/`2`,
    # or a substring match like "USB Camera"). It is NOT an ALSA `plughw:*` string.
    #
    # On some devices (including some USB mics), the hardware cannot capture at the
    # model sample-rate (often 16 kHz). In that case, capture at a supported rate
    # (e.g. 24000) and resample internally via `--mic-sample-rate`.
    ~/kws-venv/bin/python kws_keyword_beep_onnx.py --output-dir ~/output --keyword yes --mic 0 --mic-sample-rate 24000 --spk default
"""

import argparse
import json
import queue
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class KwsConfig:
    model_type: str
    sample_rate: int
    clip_samples: int
    n_fft: int
    hop_length: int
    n_mels: int
    fmin: int
    fmax: int
    n_frames: int
    log_eps: float = 1e-6


MIC_DEVICE = "default"
SPK_DEVICE = "default"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Streaming KWS (ONNX Runtime): detect a keyword and beep.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output-dir", default="output", help="Folder containing ONNX + config + labels.")
    p.add_argument("--keyword", default="yes", help="Keyword to detect (must exist in labels).")
    p.add_argument("--threshold", type=float, default=0.75, help="Probability threshold for detection.")
    p.add_argument("--stable-n", type=int, default=3, help="Number of consecutive hits required.")
    p.add_argument("--cooldown-steps", type=int, default=12, help="Cooldown iterations after a detection.")
    p.add_argument("--exit-on-detect", action="store_true", help="Exit after the first detection + beep.")
    p.add_argument(
        "--print-any-detect",
        action="store_true",
        help="Print stable detections for any label (useful for debugging).",
    )
    p.add_argument(
        "--mic",
        default=MIC_DEVICE,
        help='Input device (sounddevice/PortAudio). Example: "0" or "USB Camera".',
    )
    p.add_argument(
        "--mic-sample-rate",
        type=int,
        default=None,
        help="Mic capture sample rate (e.g. 24000). Defaults to the model sample rate.",
    )
    p.add_argument(
        "--keyword-top-delta",
        type=float,
        default=0.05,
        help="Allow triggering when the keyword probability is within this delta of the top label probability.",
    )
    p.add_argument(
        "--require-keyword-top",
        action="store_true",
        help="Only trigger when the keyword is the top (argmax) label.",
    )
    p.add_argument(
        "--print-keyword-prob",
        action="store_true",
        help="Print the keyword probability periodically (useful for picking a threshold).",
    )
    p.add_argument(
        "--spk",
        default=SPK_DEVICE,
        help="Output device for beep (ALSA `speaker-test -D`). Example: plughw:1,3 or default.",
    )
    p.add_argument("--list-labels", action="store_true", help="Print labels and exit.")
    return p.parse_args()


def softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    ex = np.exp(x)
    return ex / np.sum(ex)


def beep(spk_device: str) -> None:
    try:
        subprocess.run(
            ["speaker-test", "-D", spk_device, "-t", "sine", "-f", "1000", "-l", "1", "-p", "200"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
    except Exception:
        pass


def _hz_to_mel_slaney(f: np.ndarray) -> np.ndarray:
    f_sp = 200.0 / 3
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0

    m = f / f_sp
    idx = f >= min_log_hz
    m[idx] = min_log_mel + np.log(f[idx] / min_log_hz) / logstep
    return m


def _mel_to_hz_slaney(m: np.ndarray) -> np.ndarray:
    f_sp = 200.0 / 3
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0

    f = f_sp * m
    idx = m >= min_log_mel
    f[idx] = min_log_hz * np.exp(logstep * (m[idx] - min_log_mel))
    return f


def _mel_filterbank(*, sr: int, n_fft: int, n_mels: int, fmin: float, fmax: float) -> np.ndarray:
    # Match librosa defaults: htk=False, norm="slaney".
    n_freqs = 1 + n_fft // 2
    fft_freqs = np.linspace(0.0, float(sr) / 2.0, n_freqs, dtype=np.float64)

    m_min = float(_hz_to_mel_slaney(np.array([fmin], dtype=np.float64))[0])
    m_max = float(_hz_to_mel_slaney(np.array([fmax], dtype=np.float64))[0])
    m_pts = np.linspace(m_min, m_max, n_mels + 2, dtype=np.float64)
    f_pts = _mel_to_hz_slaney(m_pts)

    fdiff = np.diff(f_pts)
    ramps = f_pts[:, None] - fft_freqs[None, :]

    weights = np.zeros((n_mels, n_freqs), dtype=np.float64)
    for i in range(n_mels):
        lower = -ramps[i] / fdiff[i]
        upper = ramps[i + 2] / fdiff[i + 1]
        weights[i] = np.maximum(0.0, np.minimum(lower, upper))

    # Slaney-style normalization: make each filter integrate to constant.
    enorm = 2.0 / (f_pts[2 : n_mels + 2] - f_pts[:n_mels])
    weights *= enorm[:, None]

    return weights.astype(np.float32)


def _stft_power(y: np.ndarray, *, n_fft: int, hop_length: int) -> np.ndarray:
    pad = n_fft // 2
    y = np.pad(y, (pad, pad), mode="reflect")
    if y.shape[0] < n_fft:
        y = np.pad(y, (0, n_fft - y.shape[0]), mode="constant")

    n_frames = 1 + (y.shape[0] - n_fft) // hop_length
    window = np.hanning(n_fft).astype(np.float32)

    n_freqs = 1 + n_fft // 2
    out = np.empty((n_freqs, n_frames), dtype=np.float32)

    for i in range(n_frames):
        start = i * hop_length
        frame = y[start : start + n_fft]
        frame = frame * window
        spec = np.fft.rfft(frame, n=n_fft)
        out[:, i] = (np.abs(spec).astype(np.float32)) ** 2

    return out


def main() -> None:
    args = parse_args()
    out = Path(args.output_dir)

    onnx_path = out / "pytorch_kws_model.onnx"
    cfg_path = out / "pytorch_kws_config.json"
    labels_path = out / "pytorch_kws_labels.json"

    if not labels_path.exists():
        raise FileNotFoundError(f"Missing labels file: {labels_path.resolve()}")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if args.list_labels:
        print("\n".join(str(x) for x in labels))
        return

    def _norm_label(s: object) -> str:
        return str(s).strip().casefold()

    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config file: {cfg_path.resolve()}")
    if not onnx_path.exists():
        raise FileNotFoundError(f"Missing ONNX file: {onnx_path.resolve()}")

    keyword_norm = _norm_label(args.keyword)
    norm_to_labels: dict[str, list[str]] = {}
    for lbl in labels:
        norm_to_labels.setdefault(_norm_label(lbl), []).append(str(lbl))

    keyword_matches = norm_to_labels.get(keyword_norm, [])
    if not keyword_matches:
        raise ValueError(
            f"--keyword {args.keyword!r} not in labels (case-insensitive); use --list-labels."
        )
    if len(keyword_matches) > 1:
        raise ValueError(
            f"--keyword {args.keyword!r} is ambiguous (matches {keyword_matches}); pass an exact label."
        )
    keyword_label = keyword_matches[0]
    keyword_idx = labels.index(keyword_label)

    try:
        import sounddevice as sd  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(f"Missing dependency: sounddevice ({e})")

    try:
        import onnxruntime as ort  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(f"Missing dependency: onnxruntime ({e})")

    cfg_raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg = KwsConfig(**cfg_raw)
    model_sr = int(cfg.sample_rate)
    mic_sr = int(args.mic_sample_rate) if args.mic_sample_rate else model_sr

    mel_fb = _mel_filterbank(
        sr=cfg.sample_rate,
        n_fft=cfg.n_fft,
        n_mels=cfg.n_mels,
        fmin=float(cfg.fmin),
        fmax=float(cfg.fmax),
    )

    sess = ort.InferenceSession(
        onnx_path.as_posix(),
        providers=["CPUExecutionProvider"],
    )
    input_name = sess.get_inputs()[0].name

    audio_q: queue.Queue[np.ndarray] = queue.Queue()
    ring = np.zeros(cfg.clip_samples, dtype=np.float32)

    last_top_label: str | None = None
    top_stable_count = 0
    kw_stable_count = 0
    cooldown = 0
    step = 0

    def log_mel(y: np.ndarray) -> np.ndarray:
        power = _stft_power(y.astype(np.float32), n_fft=cfg.n_fft, hop_length=cfg.hop_length)
        mel = (mel_fb @ power).astype(np.float32)  # [n_mels, n_frames]
        if mel.shape[1] != int(cfg.n_frames):
            # Keep runtime robust to minor framing differences.
            if mel.shape[1] > int(cfg.n_frames):
                mel = mel[:, : int(cfg.n_frames)]
            else:
                mel = np.pad(mel, ((0, 0), (0, int(cfg.n_frames) - mel.shape[1])), mode="constant")

        log_mel = np.log(mel + float(cfg.log_eps))
        log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-6)
        # [1, 1, n_mels, n_frames]
        return log_mel[np.newaxis, np.newaxis, :, :]

    def callback(indata, frames, time_info, status):
        chunk = indata[:, 0].astype(np.float32, copy=True)
        if mic_sr != model_sr:
            n_out = int(round(len(chunk) * model_sr / mic_sr))
            if n_out >= 1:
                x_old = np.linspace(0.0, 1.0, num=len(chunk), endpoint=False, dtype=np.float32)
                x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False, dtype=np.float32)
                chunk = np.interp(x_new, x_old, chunk).astype(np.float32, copy=False)
        audio_q.put(chunk)

    print(f"Listening on mic={args.mic} for {keyword_label!r}... Ctrl+C to stop")

    blocksize = int(round(1600 * mic_sr / model_sr))

    mic: int | str
    mic = int(args.mic) if str(args.mic).strip().isdigit() else str(args.mic)

    with sd.InputStream(
        device=mic,
        samplerate=mic_sr,
        channels=1,
        dtype="float32",
        callback=callback,
        blocksize=blocksize,
    ):
        while True:
            chunk = audio_q.get()
            n = len(chunk)
            ring = np.roll(ring, -n)
            ring[-n:] = chunk
            step += 1

            if cooldown > 0:
                cooldown -= 1
                continue

            x = log_mel(ring)
            logits = sess.run(None, {input_name: x})[0][0]
            probs = softmax(logits.astype(np.float32))

            top_idx = int(np.argmax(probs))
            top_label = str(labels[top_idx])
            top_p = float(probs[top_idx])

            p_kw = float(probs[int(keyword_idx)])
            if bool(args.print_keyword_prob) and step % 10 == 0:
                print(f"KW_PROB: {keyword_label} (p={p_kw:.2f}) top={top_label} (p={top_p:.2f})")

            # Debug printing: show stable top-label detections (argmax), optionally.
            if top_p >= float(args.threshold):
                if top_label == last_top_label:
                    top_stable_count += 1
                else:
                    last_top_label, top_stable_count = top_label, 1

                if bool(args.print_any_detect) and top_stable_count == int(args.stable_n):
                    print(f"DETECTED: {top_label} (p={top_p:.2f})")
            else:
                last_top_label, top_stable_count = None, 0

            # Keyword detection: trigger based on the keyword's probability, not argmax.
            allow_delta = 0.0 if bool(args.require_keyword_top) else float(args.keyword_top_delta)
            keyword_ok = (top_idx == int(keyword_idx)) or ((top_p - p_kw) <= allow_delta)

            if p_kw >= float(args.threshold) and keyword_ok:
                kw_stable_count += 1
                if kw_stable_count == int(args.stable_n):
                    print(f"DETECTED KEYWORD: {keyword_label} (p={p_kw:.2f})")
                    beep(str(args.spk))
                    if bool(args.exit_on_detect):
                        return
                    cooldown = int(args.cooldown_steps)
            else:
                kw_stable_count = 0


if __name__ == "__main__":
    main()
