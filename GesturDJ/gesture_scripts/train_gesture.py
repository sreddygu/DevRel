from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from gesture_features import extract_features, features_dim
from gesture_io import iter_dataset, save_labels


def _build_model() -> object:
    return make_pipeline(
        StandardScaler(),
        SVC(kernel="rbf", gamma="scale", C=10.0),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a gesture recognition baseline (scikit-learn).")
    parser.add_argument("--data_dir", required=True, help="Dataset root directory (label subfolders).")
    parser.add_argument("--output_dir", required=True, help="Where to write artifacts.")
    parser.add_argument("--resample_len", type=int, default=128, help="Resample each series to this length.")
    parser.add_argument("--test_size", type=float, default=0.2, help="Held-out split fraction.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    args = parser.parse_args()

    samples = iter_dataset(args.data_dir)
    labels = sorted({s.label for s in samples})
    label_to_id = {l: i for i, l in enumerate(labels)}

    x = np.stack([extract_features(s.series, resample_len=args.resample_len) for s in samples], axis=0)
    y = np.array([label_to_id[s.label] for s in samples], dtype=np.int64)

    expected_dim = features_dim(resample_len=args.resample_len)
    if x.shape[1] != expected_dim:
        raise RuntimeError(f"feature dim mismatch: got {x.shape[1]}, expected {expected_dim}")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=y if len(labels) > 1 else None,
    )

    model = _build_model()
    model.fit(x_train, y_train)

    pred = model.predict(x_test)
    acc = accuracy_score(y_test, pred)
    print(f"Accuracy: {acc:.4f}")
    print(classification_report(y_test, pred, target_names=labels, zero_division=0))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, out_dir / "gesture_model.joblib")
    save_labels(labels, out_dir / "gesture_labels.json")
    print(f"Wrote: {out_dir / 'gesture_model.joblib'}")
    print(f"Wrote: {out_dir / 'gesture_labels.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

