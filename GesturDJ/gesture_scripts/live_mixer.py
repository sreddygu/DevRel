"""Minimal live mixer for GesturDJ: gesture window -> ONNX recognizer -> mix action -> player process.

Replays recorded sensor windows as if a sensor had just finished each gesture, applies the
mix map (min_confidence, debounce, cooldown), switches the playing clip, and times each stage.
Nothing here measures sound at the speaker: the last stage is "player process started", and the
audio buffer is the buffer-time passed to the player (reported separately).

    python live_mixer.py --model_dir outputs --mix_map mix_map.json --clips clips \
        --events left.csv right.csv circle.csv --report live-mixer-report.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from gesture_io import load_labels, load_series
from gesture_preprocess import GesturePreprocessConfig, preprocess_series, softmax_np
from warm_output import WarmOutput, load_pcm


def build_player(name: str, buffer_us: int) -> list[str]:
    """Player command with a small buffer so it fits the latency budget."""
    if name == "aplay":
        return ["aplay", "-q", f"--buffer-time={buffer_us}", f"--period-time={buffer_us // 4}"]
    if name == "pw-play":
        return ["pw-play", f"--latency={buffer_us // 1000}ms"]
    return [name]


class Mixer:
    def __init__(self, clips_dir: Path, player_cmd: list[str], output=None):
        self.clips = sorted(p for p in clips_dir.glob("clip_*.wav") if not p.stem.endswith("_filtered"))
        self.dir = clips_dir
        self.player = player_cmd
        self.i = 0
        self.filtered = False
        self.proc: subprocess.Popen | None = None
        self.output = output                           # a WarmOutput: one stream kept open instead of a player per gesture
        self.pcm = {p: load_pcm(str(p), output.rate) for p in sorted(clips_dir.glob("clip_*.wav"))} if output else {}

    def current(self) -> Path:
        p = self.clips[self.i]
        f = self.dir / f"{p.stem}_filtered.wav"
        return f if self.filtered and f.exists() else p

    def play(self) -> None:
        if self.output:
            self.output.play(self.pcm[self.current()])
            return
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = subprocess.Popen(self.player + [str(self.current())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply(self, action: str) -> str:
        if action == "next_clip":
            self.i = (self.i + 1) % len(self.clips)
        elif action == "previous_clip":
            self.i = (self.i - 1) % len(self.clips)
        elif action == "toggle_filter":
            self.filtered = not self.filtered
        else:
            return "unknown_action"
        self.play()
        return self.current().name

    def stop(self) -> None:
        if self.output:
            self.output.stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model_dir", default="outputs")
    p.add_argument("--mix_map", required=True)
    p.add_argument("--clips", required=True, help="Folder with clip_*.wav (and optional clip_*_filtered.wav)")
    p.add_argument("--events", nargs="+", required=True, help="Sensor windows (CSV/NPY), replayed in order")
    p.add_argument("--gap_ms", type=int, default=900, help="Pause between events")
    p.add_argument("--gap_override", nargs="*", default=[], help="index=ms overrides, e.g. 4=200 (event 4 follows 200 ms after event 3)")
    p.add_argument("--player", default="aplay", help="aplay, paplay, pw-play, or warm (one pw-cat stream kept open)")
    p.add_argument("--buffer_ms", type=int, default=40, help="Player audio buffer in ms (counted in the budget)")
    p.add_argument("--report", type=Path, default=None)
    a = p.parse_args()

    import onnxruntime as ort

    out = Path(a.model_dir)
    labels = load_labels(out / "gesture_labels.json")
    c = json.loads((out / "gesture_config.json").read_text(encoding="utf-8"))
    cfg = GesturePreprocessConfig(resample_len=int(c["resample_len"]), mean=tuple(c["mean"]), std=tuple(c["std"]))
    sess = ort.InferenceSession((out / "gesture_model.onnx").as_posix(), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    mix = json.loads(Path(a.mix_map).read_text(encoding="utf-8"))
    budget = float(mix["latency_budget_ms"])
    if a.player == "warm":
        warm = WarmOutput(48000, 20)
        time.sleep(2.0)                               # let the stream connect
        mixer = Mixer(Path(a.clips), [], warm)
    else:
        warm = None
        if not shutil.which(a.player):
            raise SystemExit(f"player not found: {a.player}")
        mixer = Mixer(Path(a.clips), build_player(a.player, a.buffer_ms * 1000))
    overrides = dict(kv.split("=") for kv in a.gap_override)

    warmup = preprocess_series(load_series(a.events[0]), cfg)[np.newaxis]
    sess.run(None, {inp: warmup.astype(np.float32)})  # warm-up: not counted

    last_action_t: dict[str, float] = {}
    last_seen_t: dict[str, float] = {}
    rows = []
    for n, ev in enumerate(a.events):
        time.sleep(int(overrides.get(str(n), a.gap_ms)) / 1000.0 if n else 0)
        series = load_series(ev)                      # the sensor window, already complete
        t0 = time.perf_counter()                      # gesture window ended
        x = preprocess_series(series, cfg)[np.newaxis, :, :]
        logits = sess.run(None, {inp: x.astype(np.float32)})[0][0]
        probs = softmax_np(logits)
        t1 = time.perf_counter()
        k = int(np.argmax(probs))
        label, conf = labels[k], float(probs[k])
        rule = mix["gestures"].get(label)
        now = time.monotonic()
        row = {"event": Path(ev).name, "label": label, "confidence": round(conf, 3), "inference_ms": round((t1 - t0) * 1000, 3)}
        if rule is None:
            row["result"] = "unmapped"
        elif conf < rule["min_confidence"]:
            row["result"] = "below_min_confidence"
        elif (now - last_seen_t.get(label, -1e9)) * 1000 < rule["debounce_ms"]:
            row["result"] = "debounced"
        elif (now - last_action_t.get(label, -1e9)) * 1000 < rule["cooldown_ms"]:
            row["result"] = "cooldown"
        else:
            t2 = time.perf_counter()
            clip = mixer.apply(rule["action"])
            t3 = time.perf_counter()
            last_action_t[label] = now
            total = (t3 - t0) * 1000 + a.buffer_ms
            row.update(result="applied", action=rule["action"], clip=clip, mix_ms=round((t3 - t2) * 1000, 3),
                       buffer_ms=a.buffer_ms, gesture_to_sound_estimate_ms=round(total, 2), within_budget=total <= budget)
        last_seen_t[label] = now
        rows.append(row)
        print(json.dumps(row))
    time.sleep(0.3)
    mixer.stop()
    if warm:
        warm.close()
    applied = [r for r in rows if r["result"] == "applied"]
    summary = {"budget_ms": budget, "events": len(rows), "applied": len(applied),
               "worst_estimate_ms": max((r["gesture_to_sound_estimate_ms"] for r in applied), default=None),
               "all_within_budget": all(r["within_budget"] for r in applied) if applied else None,
               "note": "estimate = inference + mix + player start + configured audio buffer; not measured at the speaker"}
    print(json.dumps(summary))
    if a.report:
        a.report.write_text(json.dumps({"summary": summary, "events": rows}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
