"""NumPy-only gesture preprocessing. Safe to import on a target that has no PyTorch (for example the Arduino Ventuno Q,
where `import torch` can crash with an illegal instruction). The ONNX inference scripts must import from here, never
from gesture_pytorch_model.py."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def resample_to_length(x: np.ndarray, target_len: int) -> np.ndarray:
    """
    Resample a (T,3) series to (target_len,3) using linear interpolation.
    Matches the scikit-learn pipeline's behavior closely, but returns the
    resampled series (not a feature vector).
    """
    if target_len <= 1:
        raise ValueError("target_len must be >= 2")
    if x.ndim != 2 or x.shape[1] != 3:
        raise ValueError(f"expected shape (T,3), got {x.shape}")

    t = x.shape[0]
    if t < 2:
        x = np.concatenate([x, x], axis=0)
        t = 2

    src = np.linspace(0.0, 1.0, num=t, dtype=np.float64)
    dst = np.linspace(0.0, 1.0, num=target_len, dtype=np.float64)
    out = np.empty((target_len, 3), dtype=np.float64)
    for ch in range(3):
        out[:, ch] = np.interp(dst, src, x[:, ch].astype(np.float64, copy=False))
    return out.astype(np.float32, copy=False)


@dataclass(frozen=True)
class GesturePreprocessConfig:
    resample_len: int = 128
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)
    std: tuple[float, float, float] = (1.0, 1.0, 1.0)
    eps: float = 1e-6


def preprocess_series(series: np.ndarray, cfg: GesturePreprocessConfig) -> np.ndarray:
    x = resample_to_length(series, cfg.resample_len)  # (T,3)
    mean = np.asarray(cfg.mean, dtype=np.float32).reshape(1, 3)
    std = np.asarray(cfg.std, dtype=np.float32).reshape(1, 3)
    x = (x - mean) / (std + float(cfg.eps))
    # model expects [C,T]
    return x.T.astype(np.float32, copy=False)


def softmax_np(logits: np.ndarray) -> np.ndarray:
    logits = logits.astype(np.float32, copy=False)
    logits = logits - float(np.max(logits))
    ex = np.exp(logits)
    return ex / float(np.sum(ex) + 1e-12)
