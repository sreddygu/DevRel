from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def _write_csv(path: Path, series: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ax", "ay", "az"])
        w.writerows(series.tolist())


def _make_series(kind: str, length: int, rng: np.random.Generator) -> np.ndarray:
    t = np.linspace(0, 1, num=length, dtype=np.float32)
    noise = 0.05 * rng.standard_normal((length, 3), dtype=np.float32)
    if kind == "left":
        base = np.stack([-np.sin(2 * np.pi * t), np.zeros_like(t), np.cos(2 * np.pi * t)], axis=1)
    elif kind == "right":
        base = np.stack([np.sin(2 * np.pi * t), np.zeros_like(t), np.cos(2 * np.pi * t)], axis=1)
    elif kind == "circle":
        base = np.stack([np.cos(4 * np.pi * t), np.sin(4 * np.pi * t), np.zeros_like(t)], axis=1)
    else:
        base = rng.standard_normal((length, 3), dtype=np.float32)
    return base.astype(np.float32) + noise


def main() -> int:
    p = argparse.ArgumentParser(description="Create a local synthetic gesture dataset (CSV per sample).")
    p.add_argument("--data_dir", default="gesture_data/synthetic", help="Output dataset directory.")
    p.add_argument("--labels", nargs="+", default=["left", "right", "circle"], help="Label names.")
    p.add_argument("--samples_per_label", type=int, default=50)
    p.add_argument("--min_len", type=int, default=60)
    p.add_argument("--max_len", type=int, default=160)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    project_root = Path(__file__).resolve().parent
    out_dir = (project_root / args.data_dir).resolve()

    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty data_dir: {out_dir}")

    rng = np.random.default_rng(args.seed)
    for label in args.labels:
        for i in range(args.samples_per_label):
            length = int(rng.integers(args.min_len, args.max_len + 1))
            series = _make_series(label, length=length, rng=rng)
            _write_csv(out_dir / label / f"sample_{i:05d}.csv", series)

    print(f"Wrote synthetic dataset to: {out_dir}")
    print("Next:")
    print(f"  python train_gesture.py --data_dir {out_dir} --output_dir outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
