from __future__ import annotations

import numpy as np


def _resample_to_length(x: np.ndarray, target_len: int) -> np.ndarray:
    if target_len <= 1:
        raise ValueError("target_len must be >= 2")
    if x.ndim != 2:
        raise ValueError("expected shape (T, C)")
    t, c = x.shape
    if t < 2:
        # pad to at least 2 for interpolation
        x = np.concatenate([x, x], axis=0)
        t = 2
    src = np.linspace(0.0, 1.0, num=t, dtype=np.float64)
    dst = np.linspace(0.0, 1.0, num=target_len, dtype=np.float64)
    out = np.empty((target_len, c), dtype=np.float64)
    for ch in range(c):
        out[:, ch] = np.interp(dst, src, x[:, ch].astype(np.float64, copy=False))
    return out


def extract_features(
    series: np.ndarray,
    *,
    resample_len: int = 128,
) -> np.ndarray:
    """
    Convert a variable-length (T,3) time-series into a fixed-length feature vector.
    """
    if series.ndim != 2 or series.shape[1] != 3:
        raise ValueError(f"expected series shape (T,3), got {series.shape}")

    x = _resample_to_length(series, resample_len)

    # Time-domain stats (per-axis)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    minv = x.min(axis=0)
    maxv = x.max(axis=0)
    ptp = maxv - minv
    rms = np.sqrt(np.mean(x * x, axis=0))

    # First-difference stats (captures motion dynamics)
    dx = np.diff(x, axis=0)
    d_mean = dx.mean(axis=0)
    d_std = dx.std(axis=0)
    d_rms = np.sqrt(np.mean(dx * dx, axis=0))

    # Frequency-domain energy (per-axis, coarse bands)
    fft = np.fft.rfft(x, axis=0)
    mag = np.abs(fft)  # (F,3)
    mag = mag[1:, :]  # drop DC
    if mag.shape[0] == 0:
        mag = np.zeros((1, 3), dtype=np.float64)
    power = mag * mag
    total = power.sum(axis=0) + 1e-12

    # 4 equal-width bands over available bins
    bands = np.array_split(power, 4, axis=0)
    band_energy = np.stack([b.sum(axis=0) / total for b in bands], axis=0).reshape(-1)

    feats = np.concatenate(
        [
            mean,
            std,
            minv,
            maxv,
            ptp,
            rms,
            d_mean,
            d_std,
            d_rms,
            band_energy,
        ],
        axis=0,
    ).astype(np.float32, copy=False)
    return feats


def features_dim(*, resample_len: int = 128) -> int:
    # Keep in sync with extract_features() concatenation above.
    # 9 blocks of per-axis stats + 4 bands * 3 axes
    return (9 * 3) + (4 * 3)

