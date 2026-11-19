"""Probe the board's audio output: which sink and players exist, and how much time each player adds.

Plays a 100 ms clip through each available player at the default and at a small buffer, N times, and reports the
wall time minus the clip length (player start-up plus buffer drain). That overhead is an upper-bound proxy for the
"audio buffer" stage of the live path. It is not an acoustic measurement: it cannot tell whether a speaker is attached.

    python probe_audio_output.py --runs 5 --out audio-output-probe.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path

CLIP_S = 0.1


def median(xs: list[float]) -> float:
    """Own median: the `statistics` module is missing from some board Python builds."""
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def make_clip(path: Path, sr: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack("<h", 0) * int(sr * CLIP_S))     # silence: audible output is not needed


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception as e:                                          # noqa: BLE001 - report, never fail the probe
        return f"unavailable ({e})"


def variants() -> list[tuple[str, list[str]]]:
    v: list[tuple[str, list[str]]] = []
    if shutil.which("aplay"):
        v += [("aplay default buffer", ["aplay", "-q"]), ("aplay 40 ms buffer", ["aplay", "-q", "--buffer-time=40000", "--period-time=10000"])]
    if shutil.which("paplay"):
        v += [("paplay default", ["paplay"]), ("paplay 40 ms", ["paplay", "--latency-msec=40"])]
    if shutil.which("pw-play"):
        v += [("pw-play default", ["pw-play"]), ("pw-play 40 ms", ["pw-play", "--latency=40ms"])]
    return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    clip = Path(tempfile.mkdtemp()) / "probe.wav"
    make_clip(clip)
    result: dict = {
        "sinks": sh(["aplay", "-l"]).splitlines()[:6] if shutil.which("aplay") else [],
        "players_on_path": [p for p in ("aplay", "paplay", "pw-play", "gst-play-1.0", "ffplay") if shutil.which(p)],
        "clip_ms": int(CLIP_S * 1000),
        "runs": a.runs,
        "variants": [],
    }
    for name, base in variants():
        over, rcs = [], []
        for _ in range(a.runs):
            t0 = time.perf_counter()
            r = subprocess.run(base + [str(clip)], capture_output=True, timeout=20)
            over.append((time.perf_counter() - t0 - CLIP_S) * 1000)
            rcs.append(r.returncode)
        result["variants"].append({
            "variant": name, "exit_codes": sorted(set(rcs)),
            "overhead_ms_median": round(median(over), 1), "overhead_ms_max": round(max(over), 1),
        })
        print(f"{name:24s} exit {sorted(set(rcs))} overhead median {median(over):6.1f} ms  max {max(over):6.1f} ms")
    ok = [v for v in result["variants"] if v["exit_codes"] == [0]]
    result["best_variant"] = min(ok, key=lambda v: v["overhead_ms_median"])["variant"] if ok else None
    result["note"] = "overhead = wall time minus clip length; includes player start-up and buffer drain; not measured at a speaker"
    print("best:", result["best_variant"])
    if a.out:
        a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
