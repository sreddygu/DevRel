"""Deterministic simulated wearable sensors (IMU + heart rate).

Stands in for a watch/band on the IQ8 proxy: no hardware sensors are read, so the
loop is reproducible. Each scenario is a list of ``(state, seconds)`` segments.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass

# (motion amplitude in g, step frequency in Hz, mean heart rate in bpm)
PROFILES = {
    "resting": (0.01, 0.0, 66),
    "walking": (0.35, 1.9, 92),
    "running": (1.30, 2.8, 150),
    "anomaly": (0.01, 0.0, 128),  # high heart rate while physically still
}

DEFAULT_SCENARIO = [("resting", 20), ("walking", 20), ("running", 10), ("resting", 15), ("anomaly", 6), ("resting", 10)]


@dataclass(frozen=True)
class Sample:
    t: float  # seconds since start
    ax: float
    ay: float
    az: float  # g; includes gravity on z
    hr: float  # bpm


def simulate(scenario=None, *, hz: int = 25, seed: int = 7) -> Iterator[Sample]:
    rng = random.Random(seed)
    t = 0.0
    for state, seconds in scenario or DEFAULT_SCENARIO:
        amp, freq, hr = PROFILES[state]
        for _ in range(int(seconds * hz)):
            phase = 2 * math.pi * freq * t
            yield Sample(
                t=round(t, 4),
                ax=amp * math.sin(phase) + rng.gauss(0, 0.005),
                ay=0.5 * amp * math.cos(phase) + rng.gauss(0, 0.005),
                az=1.0 + amp * math.sin(2 * phase) + rng.gauss(0, 0.005),
                hr=hr + rng.gauss(0, 1.5),
            )
            t += 1 / hz
