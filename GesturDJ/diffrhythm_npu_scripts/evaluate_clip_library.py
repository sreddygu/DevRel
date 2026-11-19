"""Objective checks for generated clips before they join the live mixer's library. numpy and wave only.

For each .wav: duration, sample rate, channels, loudness (RMS dBFS), peak, clipped fraction, silent fraction,
DC offset, NaN-free, and how much the start and end loudness differ (a loop seam). Then library-level checks:
all clips share a sample rate, and loudness is within --max_spread_db of each other (so switching clips does not jump).

These catch a broken or unusable clip. They do not tell you whether it sounds good: listen to it.

    python evaluate_clip_library.py CLIP.wav [CLIP.wav ...] [--out clip-library-report.json]
Exit code 1 if any clip or the library fails a check.
"""

import argparse
import json
import sys
import wave

import numpy as np

CHECKS = {"min_seconds": 20.0, "max_clipped": 0.001, "max_silent": 0.30, "max_dc": 0.01, "max_seam_db": 6.0}


def load(path):
    with wave.open(path) as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        sys.exit(f"{path}: only 16-bit PCM is supported (got {8 * width}-bit)")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return x.reshape(-1, ch).mean(axis=1), sr, ch


def dbfs(v):
    return float(20 * np.log10(max(v, 1e-9)))


def evaluate(path):
    x, sr, ch = load(path)
    rms = float(np.sqrt(np.mean(x ** 2)))
    win = int(0.05 * sr)
    frames = x[: len(x) // win * win].reshape(-1, win)
    frame_db = 20 * np.log10(np.maximum(np.sqrt((frames ** 2).mean(axis=1)), 1e-9))
    two = int(2 * sr)
    seam = abs(dbfs(float(np.sqrt(np.mean(x[:two] ** 2)))) - dbfs(float(np.sqrt(np.mean(x[-two:] ** 2)))))
    r = {
        "file": path.replace("\\", "/").split("/")[-1], "seconds": round(len(x) / sr, 2), "sample_rate": sr, "channels": ch,
        "rms_dbfs": round(dbfs(rms), 1), "peak": round(float(np.abs(x).max()), 3),
        "clipped_fraction": round(float((np.abs(x) >= 0.9999).mean()), 5),
        "silent_fraction": round(float((frame_db < -50).mean()), 3),
        "dc_offset": round(float(abs(x.mean())), 5), "finite": bool(np.isfinite(x).all()),
        "start_end_seam_db": round(seam, 1),
    }
    fails = []
    if r["seconds"] < CHECKS["min_seconds"]: fails.append("too short")
    if not r["finite"]: fails.append("NaN or inf")
    if r["clipped_fraction"] > CHECKS["max_clipped"]: fails.append("clipping")
    if r["silent_fraction"] > CHECKS["max_silent"]: fails.append("mostly silent")
    if r["dc_offset"] > CHECKS["max_dc"]: fails.append("DC offset")
    r["loop_seam"] = "smooth" if seam <= CHECKS["max_seam_db"] else "audible jump if looped"   # informational, not a failure
    r["fails"] = fails
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("clips", nargs="+")
    p.add_argument("--max_spread_db", type=float, default=8.0, help="Allowed loudness spread across the library")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    rows = [evaluate(c) for c in a.clips]
    lib_fails = []
    if len({r["sample_rate"] for r in rows}) > 1: lib_fails.append("clips differ in sample rate")
    spread = max(r["rms_dbfs"] for r in rows) - min(r["rms_dbfs"] for r in rows)
    if spread > a.max_spread_db: lib_fails.append(f"loudness spread {spread:.1f} dB over {a.max_spread_db} dB")
    res = {"checks": CHECKS, "clips": rows, "loudness_spread_db": round(spread, 1), "library_fails": lib_fails,
           "ok": not lib_fails and not any(r["fails"] for r in rows),
           "note": "objective checks only; whether a clip sounds good needs a listener"}
    for r in rows:
        print(f"{r['file']:70s} {r['seconds']:6.1f}s rms {r['rms_dbfs']:6.1f} dBFS peak {r['peak']:.2f} silent {r['silent_fraction']:.2f} seam {r['start_end_seam_db']:4.1f} dB  {'FAIL ' + ', '.join(r['fails']) if r['fails'] else 'ok'}")
    print(f"loudness spread {spread:.1f} dB; library: {'FAIL ' + '; '.join(lib_fails) if lib_fails else 'ok'}")
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(res, indent=2) + "\n")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
