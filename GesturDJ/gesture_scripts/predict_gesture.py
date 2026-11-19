from __future__ import annotations

import argparse

import joblib

from gesture_features import extract_features
from gesture_io import load_labels, load_series


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict a label for a single gesture file.")
    parser.add_argument("--model", required=True, help="Path to gesture_model.joblib")
    parser.add_argument("--labels", required=True, help="Path to gesture_labels.json")
    parser.add_argument("--input", required=True, help="CSV or NPY file to classify")
    parser.add_argument("--resample_len", type=int, default=128, help="Resample length (must match training).")
    args = parser.parse_args()

    model = joblib.load(args.model)
    labels = load_labels(args.labels)

    series = load_series(args.input)
    feats = extract_features(series, resample_len=args.resample_len).reshape(1, -1)
    pred = int(model.predict(feats)[0])
    print(labels[pred])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

