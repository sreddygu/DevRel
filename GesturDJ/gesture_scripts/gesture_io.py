from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class GestureSample:
    label: str
    series: np.ndarray  # (T,3) float32
    path: Path


def _load_csv(path: Path) -> np.ndarray:
    # Try a header-aware load first; fall back to plain numeric.
    try:
        data = np.genfromtxt(path, delimiter=",", names=True, dtype=np.float64)
        if data.dtype.names is None:
            raise ValueError("no header")
        names = [n.lower() for n in data.dtype.names]
        preferred = [
            ("ax", "ay", "az"),
            ("x", "y", "z"),
        ]
        for cols in preferred:
            if all(c in names for c in cols):
                stacked = np.stack([data[c] for c in cols], axis=1)
                return stacked
        # otherwise take first 3 numeric columns
        stacked = np.stack([data[n] for n in data.dtype.names[:3]], axis=1)
        return stacked
    except Exception:
        raw = np.loadtxt(path, delimiter=",", dtype=np.float64)
        if raw.ndim == 1:
            raw = raw.reshape(-1, 1)
        if raw.shape[1] < 3:
            raise ValueError(f"{path} has {raw.shape[1]} columns; need >= 3")
        return raw[:, :3]


def load_series(path: str | Path) -> np.ndarray:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        series = _load_csv(path)
    elif path.suffix.lower() == ".npy":
        series = np.load(path)
    else:
        raise ValueError(f"unsupported input file type: {path.suffix}")

    series = np.asarray(series, dtype=np.float32)
    if series.ndim != 2:
        raise ValueError(f"expected 2D array, got shape {series.shape} from {path}")
    if series.shape[1] != 3:
        if series.shape[0] == 3:
            series = series.T
        else:
            series = series[:, :3]
    return series


def iter_dataset(data_dir: str | Path) -> list[GestureSample]:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(data_dir)
    if not data_dir.is_dir():
        raise NotADirectoryError(data_dir)

    samples: list[GestureSample] = []
    for label_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()]):
        label = label_dir.name
        for path in sorted(label_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in {".csv", ".npy"}:
                continue
            series = load_series(path)
            samples.append(GestureSample(label=label, series=series, path=path))
    if not samples:
        raise ValueError(f"no gesture samples found under {data_dir}")
    return samples


def save_labels(labels: list[str], path: str | Path) -> None:
    path = Path(path)
    path.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")


def load_labels(path: str | Path) -> list[str]:
    path = Path(path)
    labels = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise ValueError(f"invalid labels file: {path}")
    return labels

