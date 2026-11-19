"""Vendored copy of chipset compute capabilities.

Source: ``QUAD/src/quad/compiler/capabilities.py`` (commit 2485044 at sync time).
Drift policy: re-sync this file when QUAD bumps its capabilities table.
The contract test in ``tests/test_local/test_capabilities.py`` will fail
loudly if a downstream consumer expects a chipset entry that's not here.

We only carry the four fields actually used by the client-light tier
(chipset name, NPU/GPU model strings, TOPS/TFLOPS). The full
``ComputeCapability`` dataclass with VTCM size, HVX width, supported
dtypes, etc. lives only on the server because it's only needed by the
compiler/runtime layers.
"""

from __future__ import annotations

from typing import TypedDict


class ChipsetCapability(TypedDict):
    chipset: str
    gpu_model: str
    gpu_tflops: float
    npu_model: str
    npu_tops: float


# Frozen literal — last sync from QUAD@2485044.
_CAPABILITIES: dict[str, ChipsetCapability] = {
    "snapdragon-x-elite": {
        "chipset": "Snapdragon X Elite",
        "gpu_model": "Adreno X1-85",
        "gpu_tflops": 4.6,
        "npu_model": "Hexagon NPU (v73)",
        "npu_tops": 45.0,
    },
    "snapdragon-8-elite": {
        "chipset": "Snapdragon 8 Elite",
        "gpu_model": "Adreno 830",
        "gpu_tflops": 5.0,
        "npu_model": "Hexagon NPU (v73)",
        "npu_tops": 48.0,
    },
    "snapdragon-8-gen-3": {
        "chipset": "Snapdragon 8 Gen 3",
        "gpu_model": "Adreno 750",
        "gpu_tflops": 3.8,
        "npu_model": "Hexagon NPU (v69)",
        "npu_tops": 36.0,
    },
    "qcs2210": {
        "chipset": "QCS2210",
        "gpu_model": "Adreno 504",
        "gpu_tflops": 0.4,
        "npu_model": "Hexagon DSP (v66)",
        "npu_tops": 1.0,
    },
    "qcs9075": {
        # Dragonwing IQ-9075 EVK — HTP v73, Adreno 663 (retrospective validated).
        "chipset": "QCS9075",
        "gpu_model": "Adreno 663",
        "gpu_tflops": 1.0,
        "npu_model": "Hexagon NPU (v73)",
        "npu_tops": 20.0,
    },
    "qcs6490": {
        # Rubio Pi / RB3 Gen 2 — HTP v69, Adreno 643 (per .claude/skills/quad-unoq
        # SKILL.md's Arduino Portenta Q reference row, same SoC/board family).
        "chipset": "QCS6490",
        "gpu_model": "Adreno 643",
        "gpu_tflops": 1.5,
        "npu_model": "Hexagon NPU (v69)",
        "npu_tops": 12.0,
    },
    "qcs8250": {
        # Robotics RB5 — HTP v68, 15 TOPS per quad-app-builder SKILL.md's target
        # table. GPU spec not documented anywhere in this repo -- 0.0/unconfirmed
        # rather than a fabricated number; update once measured.
        "chipset": "QCS8250",
        "gpu_model": "unconfirmed",
        "gpu_tflops": 0.0,
        "npu_model": "Hexagon NPU (v68)",
        "npu_tops": 15.0,
    },
}


# Substring aliases -> canonical capability key. The Windows WMI CPU ``Name``
# (and Linux /proc SoC strings) rarely contain the marketing name verbatim
# (e.g. "Snapdragon(R) X 12-core X1E80100" has no "snapdragon x elite"
# substring), so a plain name match returns None and gpu/npu come back
# "unknown" (IQ9 issue 22). Map the SoC part-numbers / common variants that
# DO appear in probe strings to the right entry.
_ALIASES: dict[str, str] = {
    "x1e80100": "snapdragon-x-elite",
    "x1e78100": "snapdragon-x-elite",
    "x1e00100": "snapdragon-x-elite",
    "x1e-80-100": "snapdragon-x-elite",
    "snapdragon x elite": "snapdragon-x-elite",
    "snapdragon(r) x": "snapdragon-x-elite",
    "snapdragon x plus": "snapdragon-x-elite",
    "oryon": "snapdragon-x-elite",
    "sm8750": "snapdragon-8-elite",
    "snapdragon 8 elite": "snapdragon-8-elite",
    "sm8650": "snapdragon-8-gen-3",
    "snapdragon 8 gen 3": "snapdragon-8-gen-3",
    "qcs2210": "qcs2210",
    "qcs9075": "qcs9075",
    "qcs9100": "qcs9075",
    "iq-9075": "qcs9075",
    "iq9075": "qcs9075",
    "qcs6490": "qcs6490",
    "rubio-pi": "qcs6490",
    "rubiopi": "qcs6490",
    "rb3 gen 2": "qcs6490",
    "qcs8250": "qcs8250",
    "rb5": "qcs8250",
}


def _normalize(s: str) -> str:
    """Strip trademark glyphs, vendor parens, and excess whitespace."""
    import re

    # Drop ( ... ) groups -- "(R)", "(TM)", "(Compute, Windows)", etc.
    s = re.sub(r"\([^)]*\)", " ", s)
    # Collapse hyphens-with-spaces and runs of whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def lookup_for_chipset(chipset: str | None) -> ChipsetCapability | None:
    """Find the capability entry whose chipset substring matches the given string.

    Matching order: (1) canonical chipset name substring, (2) SoC part-number /
    variant aliases. The alias pass is what makes a raw WMI/`/proc` CPU string
    resolve to real GPU/NPU specs instead of "unknown".
    """
    if not chipset:
        return None
    needle = _normalize(chipset)
    for cap in _CAPABILITIES.values():
        if _normalize(cap["chipset"]) in needle:
            return cap
    # Alias pass — match part-numbers / codenames the probe strings actually carry.
    raw = (chipset or "").lower()
    for alias, key in _ALIASES.items():
        if alias in needle or alias in raw:
            return _CAPABILITIES.get(key)
    return None


def known_chipsets() -> list[str]:
    return [cap["chipset"] for cap in _CAPABILITIES.values()]
