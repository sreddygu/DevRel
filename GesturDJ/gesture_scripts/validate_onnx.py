"""Validate an exported gesture ONNX model on the machine that will run it. Read-only.

Three checks, each reported separately:
  parity   ONNX Runtime logits vs the PyTorch checkpoint (needs torch; skip with --no_parity on a target that has none)
  accuracy held-out accuracy using the SAME split as train_gesture_pytorch.py (same seed, test_size, shuffle)
  latency  single-sample end-to-end time (preprocess + inference), p50/p95/max in ms, against --budget_ms

    python validate_onnx.py --data_dir DATASET_ROOT --output_dir outputs --out onnx-validation.json
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

from gesture_io import iter_dataset, load_labels
from gesture_preprocess import GesturePreprocessConfig, preprocess_series


def heldout_indices(n: int, seed: int, test_size: float) -> np.ndarray:
    """Mirror of the split in train_gesture_pytorch.py."""
    idx = np.arange(n)
    np.random.default_rng(seed).shuffle(idx)
    test_n = max(1, int(round(test_size * n)))
    return idx[:test_n]


def main() -> int:
    p = argparse.ArgumentParser(description="Validate an exported gesture ONNX model: parity, held-out accuracy, latency.")
    p.add_argument("--data_dir", required=True)
    p.add_argument("--output_dir", default="outputs", help="Folder with gesture_model.onnx/.pt, gesture_config.json, gesture_labels.json")
    p.add_argument("--seed", type=int, default=0, help="Must match training.")
    p.add_argument("--test_size", type=float, default=0.2, help="Must match training.")
    p.add_argument("--budget_ms", type=float, default=50.0, help="Latency budget for recognition alone (inside the 200 ms gesture-to-sound budget).")
    p.add_argument("--runs", type=int, default=300)
    p.add_argument("--parity_tol", type=float, default=1e-3, help="Max abs logit difference allowed.")
    p.add_argument("--no_parity", action="store_true", help="Skip the PyTorch comparison (target without torch).")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    out = Path(args.output_dir)
    import onnxruntime as ort

    labels = load_labels(out / "gesture_labels.json")
    cfg_raw = json.loads((out / "gesture_config.json").read_text(encoding="utf-8"))
    cfg = GesturePreprocessConfig(resample_len=int(cfg_raw["resample_len"]),
                                  mean=tuple(float(x) for x in cfg_raw["mean"]), std=tuple(float(x) for x in cfg_raw["std"]))
    samples = iter_dataset(args.data_dir)
    label_to_id = {l: i for i, l in enumerate(sorted({s.label for s in samples}))}
    if sorted(label_to_id) != list(labels):
        raise SystemExit(f"labels differ: dataset {sorted(label_to_id)} vs model {labels}")

    sess = ort.InferenceSession((out / "gesture_model.onnx").as_posix(), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    xs = np.stack([preprocess_series(s.series, cfg) for s in samples]).astype(np.float32)
    ys = np.array([label_to_id[s.label] for s in samples])

    result: dict = {"platform": f"{platform.system()} {platform.machine()}", "python": platform.python_version(),
                    "onnxruntime": ort.__version__, "samples": len(samples)}

    # accuracy on the held-out split
    test_idx = heldout_indices(len(samples), args.seed, args.test_size)
    logits = sess.run(None, {inp: xs[test_idx]})[0]
    acc = float((logits.argmax(1) == ys[test_idx]).mean())
    result["accuracy"] = {"heldout_samples": int(len(test_idx)), "accuracy": round(acc, 4)}

    # parity with the PyTorch checkpoint
    if args.no_parity:
        result["parity"] = {"skipped": True}
    else:
        import torch
        from gesture_pytorch_model import GestureConvNet
        ckpt = torch.load(out / "gesture_model.pt", map_location="cpu")
        model = GestureConvNet(num_classes=len(labels))
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        with torch.no_grad():
            ref = model(torch.from_numpy(xs)).numpy()
        full = sess.run(None, {inp: xs})[0]
        diff = float(np.abs(full - ref).max())
        result["parity"] = {"max_abs_logit_diff": diff, "tolerance": args.parity_tol, "ok": diff <= args.parity_tol,
                            "argmax_agreement": float((full.argmax(1) == ref.argmax(1)).mean())}

    # single-sample latency, including preprocessing, as it would run live
    series = [s.series for s in samples[: min(50, len(samples))]]
    for s in series[:10]:
        sess.run(None, {inp: preprocess_series(s, cfg)[np.newaxis].astype(np.float32)})
    times = []
    for i in range(args.runs):
        t0 = time.perf_counter()
        sess.run(None, {inp: preprocess_series(series[i % len(series)], cfg)[np.newaxis].astype(np.float32)})
        times.append((time.perf_counter() - t0) * 1000)
    t = np.array(times)
    result["latency_ms"] = {"p50": round(float(np.percentile(t, 50)), 3), "p95": round(float(np.percentile(t, 95)), 3),
                            "max": round(float(t.max()), 3), "budget": args.budget_ms, "ok": bool(np.percentile(t, 95) <= args.budget_ms),
                            "runs": args.runs}

    ok = result["latency_ms"]["ok"] and (result["parity"].get("ok", True))
    result["ok"] = bool(ok)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
