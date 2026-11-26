"""Tiny always-on context classifier: windowed motion + heart-rate features.

Pure stdlib arithmetic so it runs on a microcontroller-class budget; this is the
"low-power model" that decides whether the large model should wake.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .sensors import Sample

MOTION_STD_WALK = 0.12   # std of acceleration magnitude (g) above which the wearer is moving
MOTION_STD_RUN = 0.55
HR_ANOMALY_STILL = 110   # bpm while still
HR_ANOMALY_ANY = 175


def features(window: Sequence[Sample]) -> dict:
    # Plain arithmetic: the Qualcomm Linux image's trimmed Python has no ``statistics``.
    mags = [math.sqrt(s.ax**2 + s.ay**2 + s.az**2) for s in window]
    mean = sum(mags) / len(mags)
    return {
        "motion_std": math.sqrt(sum((m - mean) ** 2 for m in mags) / len(mags)),
        "hr_mean": sum(s.hr for s in window) / len(window),
    }


def classify(window: Sequence[Sample]) -> tuple[str, dict]:
    """Return ``(state, features)`` with state in resting/walking/running/anomaly."""
    f = features(window)
    still = f["motion_std"] < MOTION_STD_WALK
    if (still and f["hr_mean"] > HR_ANOMALY_STILL) or f["hr_mean"] > HR_ANOMALY_ANY:
        return "anomaly", f
    if f["motion_std"] >= MOTION_STD_RUN:
        return "running", f
    return ("resting" if still else "walking"), f
