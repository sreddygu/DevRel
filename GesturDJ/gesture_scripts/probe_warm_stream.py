"""Compare a warm output stream (kept open, fed in real time) with a player started per gesture, through PipeWire.

Both write a click into a temporary null sink. A recorder on that sink's monitor timestamps when the click arrives, so the
result is the software path from "decide to play" to "samples at the sink": the player or writer, PipeWire's buffering and
the graph. It does not include the audio hardware queue (measure that with probe_hw_latency.py, 52.7 ms on the IQ8) or the
speaker. The recorder reads 10 ms chunks, so each figure includes up to 10 ms of capture granularity.

    python3 probe_warm_stream.py --trials 30 --hw_queue_ms 52.7 --out warm-stream.json        (on the board)

The null sink exists only while this script runs. Set PROBE_RATE to change the stream rate (default 48000).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from warm_output import WarmOutput

RATE = int(os.environ.get("PROBE_RATE", "48000"))     # 48000 matches the sound server graph and avoids resampling
CHUNK = RATE // 100                                    # 10 ms in frames
SINK = "gdj_probe_null"
THRESH = 4000                                          # the click peaks at ~16000; the idle sink is silent


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def stats(xs: list[float]) -> dict:
    return {"p50": round(pct(xs, 50), 1), "p95": round(pct(xs, 95), 1), "max": round(max(xs), 1), "n": len(xs)}


def click_pcm(ms: int = 40) -> bytes:
    n = RATE * ms // 1000
    return b"".join(struct.pack("<h", int(16000 * math.sin(2 * math.pi * 1000 * i / RATE))) for i in range(n))


class Recorder:
    """Reads the sink's monitor in 10 ms chunks and stamps each chunk's arrival time."""

    def __init__(self):
        cmd = ["pw-cat", "-r", "--raw", "--target", SINK, "-P", "stream.capture.sink=true", "--rate", str(RATE), "--channels", "1",
               "--format", "s16", "--latency", "10ms", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.events: list[tuple[float, int]] = []
        self.stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self.stop:
            b = self.p.stdout.read(CHUNK * 2)
            if not b:
                break
            t = time.perf_counter()
            a = struct.unpack("<%dh" % (len(b) // 2), b[: len(b) // 2 * 2])
            self.events.append((t, max(abs(x) for x in a) if a else 0))

    def first_click_after(self, t0: float, timeout: float = 1.5):
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            for t, peak in list(self.events):
                if t >= t0 and peak > THRESH:
                    return t
            time.sleep(0.002)
        return None

    def close(self):
        self.stop = True
        self.p.terminate()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--stream_latency_ms", type=int, default=20, help="pw-cat latency of the streams")
    ap.add_argument("--hw_queue_ms", type=float, default=0.0, help="hardware queue to add (from probe_hw_latency.py)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    # temporary null sink: lives while this pw-cli process stays open
    cli = subprocess.Popen(["pw-cli"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    cli.stdin.write("create-node adapter { factory.name=support.null-audio-sink node.name=%s media.class=Audio/Sink "
                    "audio.position=MONO object.linger=false }\n" % SINK)
    cli.stdin.flush()
    time.sleep(1.0)

    rec = Recorder()
    time.sleep(0.5)
    click = click_pcm()
    warm = WarmOutput(RATE, a.stream_latency_ms, SINK)
    time.sleep(2.5)
    warm_ms, miss_w = [], 0
    for _ in range(a.trials):
        time.sleep(0.45)
        t0 = time.perf_counter()
        warm.play(click)
        t = rec.first_click_after(t0)
        if t is None:
            miss_w += 1
        else:
            warm_ms.append((t - t0) * 1000)
        time.sleep(0.15)
    warm.close()

    clip = Path(tempfile.mkdtemp()) / "click.wav"
    with wave.open(str(clip), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(click)
    cold_ms, miss_c = [], 0
    for _ in range(a.trials):
        time.sleep(0.5)
        t0 = time.perf_counter()
        p = subprocess.Popen(["pw-play", "--target", SINK, "--latency", f"{a.stream_latency_ms}ms", str(clip)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t = rec.first_click_after(t0)
        p.wait()
        if t is None:
            miss_c += 1
        else:
            cold_ms.append((t - t0) * 1000)
    rec.close()
    cli.stdin.close()
    cli.terminate()

    res = {"trials": a.trials, "rate": RATE, "stream_latency_ms": a.stream_latency_ms, "hw_queue_ms": a.hw_queue_ms,
           "missed": {"warm": miss_w, "per_gesture_player": miss_c},
           "note": "software path to a null sink, via a recorder with 10 ms chunks; excludes the hardware queue (added below if given) and the speaker; not acoustic"}
    if warm_ms:
        res["warm_stream_ms"] = stats(warm_ms)
        res["warm_stream_plus_hw_ms"] = stats([x + a.hw_queue_ms for x in warm_ms])
    if cold_ms:
        res["per_gesture_player_ms"] = stats(cold_ms)
        res["per_gesture_player_plus_hw_ms"] = stats([x + a.hw_queue_ms for x in cold_ms])
    print(json.dumps(res, indent=2))
    if a.out:
        a.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    return 0 if warm_ms else 1


if __name__ == "__main__":
    raise SystemExit(main())
