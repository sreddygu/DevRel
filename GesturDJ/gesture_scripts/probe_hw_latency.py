"""Driver-level start latency of the audio output: the closest software-only view of "when does sound start".

Each run starts a player on a cold device (the PCM is closed) and polls the ALSA PCM status in /proc/asound until the
device reaches RUNNING, i.e. the hardware has started consuming samples. At that moment the status also reports `delay`,
the frames already queued ahead of the converter, so

    first_sound_estimate = time to RUNNING + delay / sample rate

This is not an acoustic measurement: it cannot see whether a speaker is attached or how long the speaker takes. It does
include the player's start-up, the sound server, the device open and prepare, and the hardware queue. A warm device (a
stream already open) skips everything except the queue; that floor is reported as `warm_floor_ms` from the queue alone.

    python probe_hw_latency.py --runs 8 --out hw-latency.json          (run on the board; Linux, ALSA)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path


def median(xs: list[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def make_clip(path: Path, seconds: float, sr: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<h", 0) * int(sr * seconds))


def read(path: str) -> str:
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--card", default="0")
    ap.add_argument("--pcm", default="0p")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    base = f"/proc/asound/card{a.card}/pcm{a.pcm}/sub0"
    if not read(base + "/status"):
        raise SystemExit(f"no PCM status at {base}/status: not an ALSA board, or wrong --card/--pcm")

    clip = Path(tempfile.mkdtemp()) / "silence.wav"
    make_clip(clip, 1.5)
    players = [(n, c) for n, c in (("pw-play", ["pw-play"]), ("paplay", ["paplay"]), ("aplay (default device)", ["aplay", "-q"])) if shutil.which(c[0])]
    result: dict = {"pcm": base, "runs": a.runs, "players": []}
    for name, cmd in players:
        run_ms, queue_ms, total_ms, failed, not_cold = [], [], [], 0, 0
        for _ in range(a.runs):
            t_end = time.perf_counter() + 20                     # wait for a cold device (the sound server closes an idle one)
            while "closed" not in read(base + "/status") and time.perf_counter() < t_end:
                time.sleep(0.05)
            if "closed" not in read(base + "/status"):
                not_cold += 1                                    # a warm device would read ~0 ms to RUNNING: do not mix it in
                continue
            p = subprocess.Popen(cmd + [str(clip)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            t0 = time.perf_counter()
            hit = None
            while time.perf_counter() - t0 < 1.2:
                s = read(base + "/status")
                if "state: RUNNING" in s:
                    hit = (time.perf_counter() - t0) * 1000
                    m = re.search(r"delay\s*:\s*(\d+)", s)
                    frames = int(m.group(1)) if m else 0
                    rate = re.search(r"rate:\s*(\d+)", read(base + "/hw_params"))
                    hz = int(rate.group(1)) if rate else 48000
                    q = frames / hz * 1000
                    break
                time.sleep(0.002)
            p.wait()
            if hit is None:
                failed += 1
                continue
            run_ms.append(hit)
            queue_ms.append(q)
            total_ms.append(hit + q)
        entry = {"player": name, "cold_runs": len(total_ms), "failed_runs": failed, "skipped_device_not_cold": not_cold}
        if total_ms:
            entry.update(
                time_to_running_ms={"median": round(median(run_ms), 1), "max": round(max(run_ms), 1)},
                hardware_queue_ms={"median": round(median(queue_ms), 1), "max": round(max(queue_ms), 1)},
                first_sound_estimate_ms={"median": round(median(total_ms), 1), "max": round(max(total_ms), 1)},
            )
            print(f"{name:24s} to RUNNING {median(run_ms):6.1f} ms + queue {median(queue_ms):5.1f} ms = {median(total_ms):6.1f} ms median, max {max(total_ms):6.1f}")
        else:
            print(f"{name:24s} never reached RUNNING in {a.runs} runs")
        result["players"].append(entry)
    ok = [p for p in result["players"] if "first_sound_estimate_ms" in p]
    if ok:
        result["warm_floor_ms"] = round(min(p["hardware_queue_ms"]["median"] for p in ok), 1)
        result["best_cold_player"] = min(ok, key=lambda p: p["first_sound_estimate_ms"]["median"])["player"]
    result["note"] = "driver-level: includes player start-up, sound server, device open and the hardware queue; excludes the speaker and the air; not acoustic"
    if a.out:
        a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
