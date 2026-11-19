"""Check a gesture dataset before training. Read-only.

Reports per-label counts and series lengths, and flags problems a trainer will not tell you about
(too few samples, imbalance, non-finite values, flat series). Exit code 1 if there is an ERROR.

    python check_dataset.py --data_dir DATASET_ROOT [--out dataset-report.json]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from gesture_io import iter_dataset

MIN_PER_LABEL_ERROR = 5
MIN_PER_LABEL_WARN = 20
IMBALANCE_WARN = 3.0


def main() -> int:
    p = argparse.ArgumentParser(description="Check a gesture dataset (label subfolders of CSV/NPY).")
    p.add_argument("--data_dir", required=True)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    samples = iter_dataset(args.data_dir)
    by_label: dict[str, list] = defaultdict(list)
    for s in samples:
        by_label[s.label].append(s)

    errors: list[str] = []
    warnings: list[str] = []
    labels = {}
    for label, items in sorted(by_label.items()):
        lens = np.array([s.series.shape[0] for s in items])
        bad_finite = [str(s.path) for s in items if not np.isfinite(s.series).all()]
        flat = [str(s.path) for s in items if float(np.std(s.series)) < 1e-6]
        labels[label] = {
            "count": len(items),
            "length_min": int(lens.min()), "length_median": int(np.median(lens)), "length_max": int(lens.max()),
            "non_finite_files": len(bad_finite), "flat_files": len(flat),
        }
        if bad_finite:
            errors.append(f"{label}: {len(bad_finite)} file(s) contain NaN/inf, e.g. {bad_finite[0]}")
        if flat:
            warnings.append(f"{label}: {len(flat)} file(s) are flat (no motion), e.g. {flat[0]}")
        if len(items) < MIN_PER_LABEL_ERROR:
            errors.append(f"{label}: only {len(items)} samples (need at least {MIN_PER_LABEL_ERROR} to split and train)")
        elif len(items) < MIN_PER_LABEL_WARN:
            warnings.append(f"{label}: only {len(items)} samples; held-out accuracy will be noisy (aim for {MIN_PER_LABEL_WARN}+)")
        if lens.min() < 16:
            warnings.append(f"{label}: shortest series has {int(lens.min())} points; very short gestures resample poorly")

    if len(labels) < 2:
        errors.append(f"need at least 2 labels, found {len(labels)}")
    counts = [v["count"] for v in labels.values()]
    if counts and max(counts) / max(1, min(counts)) > IMBALANCE_WARN:
        warnings.append(f"class imbalance: largest/smallest = {max(counts)}/{min(counts)}")

    report = {"data_dir": str(Path(args.data_dir).resolve()), "total_samples": len(samples),
              "labels": labels, "errors": errors, "warnings": warnings, "ok": not errors}
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
