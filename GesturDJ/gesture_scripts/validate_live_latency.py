"""Validate the live path's latency budget over many gestures: recognizer + mix + player start + audio buffer.

Replays recorded sensor windows N times with debounce and cooldown disabled (so every gesture changes the sound),
and reports p50/p95/max per stage and for the estimated gesture-to-sound time against the budget.
The audio buffer is the value you pass (see probe_audio_output.py for what the board adds). Exit 1 if p95 is over budget.

    python validate_live_latency.py --model_dir outputs --clips clips --windows DATA_DIR --runs 200 --buffer_ms 40 --out live-latency.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from gesture_io import load_labels, load_series
from gesture_preprocess import GesturePreprocessConfig, preprocess_series, softmax_np
from live_mixer import Mixer, build_player
from warm_output import WarmOutput


def pct(xs: list[float], q: float) -> float:
    return float(np.percentile(xs, q))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model_dir", default="outputs")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--windows", required=True, help="Dataset root: DATA/<label>/sample_*.csv")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--buffer_ms", type=int, default=40)
    ap.add_argument("--budget_ms", type=float, default=200.0)
    ap.add_argument("--player", default="aplay", help="aplay, paplay, pw-play, or warm (one pw-cat stream kept open)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import onnxruntime as ort

    out = Path(a.model_dir)
    labels = load_labels(out / "gesture_labels.json")
    c = json.loads((out / "gesture_config.json").read_text(encoding="utf-8"))
    cfg = GesturePreprocessConfig(resample_len=int(c["resample_len"]), mean=tuple(c["mean"]), std=tuple(c["std"]))
    sess = ort.InferenceSession((out / "gesture_model.onnx").as_posix(), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    files = sorted(Path(a.windows).glob("*/*.csv"))
    series = [load_series(str(f)) for f in files]
    actions = {"left": "previous_clip", "right": "next_clip", "circle": "toggle_filter"}
    warm = None
    if a.player == "warm":
        warm = WarmOutput(48000, 20)
        time.sleep(2.0)
        mixer = Mixer(Path(a.clips), [], warm)
    else:
        mixer = Mixer(Path(a.clips), build_player(a.player, a.buffer_ms * 1000))

    sess.run(None, {inp: (preprocess_series(series[0], cfg)[np.newaxis]).astype(np.float32)})   # warm-up, not counted
    inf, mix, tot = [], [], []
    for n in range(a.runs):
        s = series[n % len(series)]
        t0 = time.perf_counter()
        x = preprocess_series(s, cfg)[np.newaxis, :, :]
        probs = softmax_np(sess.run(None, {inp: x.astype(np.float32)})[0][0])
        t1 = time.perf_counter()
        mixer.apply(actions.get(labels[int(np.argmax(probs))], "next_clip"))
        t2 = time.perf_counter()
        inf.append((t1 - t0) * 1000)
        mix.append((t2 - t1) * 1000)
        tot.append((t2 - t0) * 1000 + a.buffer_ms)
        time.sleep(0.02)                                           # give the previous player process time to be replaced
    mixer.stop()
    if warm:
        warm.close()

    def stage(xs: list[float]) -> dict:
        return {"p50": round(float(np.median(xs)), 2), "p95": round(pct(xs, 95), 2), "max": round(max(xs), 2)}

    res = {
        "runs": a.runs, "windows": len(series), "player": a.player, "buffer_ms": a.buffer_ms, "budget_ms": a.budget_ms,
        "inference_ms": stage(inf), "mix_ms": stage(mix), "gesture_to_sound_estimate_ms": stage(tot),
        "ok": pct(tot, 95) <= a.budget_ms,
        "note": "estimate = inference + mix + player start + configured buffer; not measured at a speaker; no real gestures",
    }
    print(json.dumps(res, indent=2))
    if a.out:
        a.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
