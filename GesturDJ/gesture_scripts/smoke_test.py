from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from train_gesture import main as train_main


def _write_csv(path: Path, series: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "ax,ay,az\n"
    lines = ["{:.6f},{:.6f},{:.6f}\n".format(*row) for row in series]
    path.write_text(header + "".join(lines), encoding="utf-8")


def _make_series(kind: str, length: int, rng: np.random.Generator) -> np.ndarray:
    t = np.linspace(0, 1, num=length, dtype=np.float32)
    noise = 0.05 * rng.standard_normal((length, 3), dtype=np.float32)
    if kind == "left":
        base = np.stack([-np.sin(2 * np.pi * t), np.zeros_like(t), np.cos(2 * np.pi * t)], axis=1)
    elif kind == "right":
        base = np.stack([np.sin(2 * np.pi * t), np.zeros_like(t), np.cos(2 * np.pi * t)], axis=1)
    else:
        base = np.stack([np.cos(4 * np.pi * t), np.sin(4 * np.pi * t), np.zeros_like(t)], axis=1)
    return base.astype(np.float32) + noise


def main() -> int:
    rng = np.random.default_rng(0)
    tmp = Path(tempfile.mkdtemp(prefix="gesture_smoke_"))
    try:
        data = tmp / "data"
        for label in ["left", "right", "circle"]:
            for i in range(10):
                series = _make_series(label, length=int(rng.integers(60, 160)), rng=rng)
                _write_csv(data / label / f"sample_{i:04d}.csv", series)

        out = tmp / "out"
        argv = [
            "train_gesture.py",
            "--data_dir",
            str(data),
            "--output_dir",
            str(out),
            "--test_size",
            "0.2",
            "--seed",
            "0",
        ]

        # emulate CLI
        import sys

        old_argv = sys.argv
        sys.argv = argv
        try:
            rc = train_main()
        finally:
            sys.argv = old_argv

        assert (out / "gesture_model.joblib").exists()
        assert (out / "gesture_labels.json").exists()
        print("Smoke test OK")
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

