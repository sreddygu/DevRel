"""Bench helper that calls step3_test directly with an already-built DLC.

Bypasses the SDK 2.41 qairt-converter Add_15 shape-inference bug.
"""
from pathlib import Path

import run_mobilenetv2 as r

HERE = Path(__file__).resolve().parent
DLC = HERE / "output" / "mobilenetv2.dlc"
IMG = HERE / "test_input.jpg"
LABELS = HERE / "imagenet_classes.txt"

# The ImageNet-1k labels are a public dataset artifact, not committed to this
# repo (open-source review) — fetch on demand from PyTorch Hub if absent.
if not LABELS.exists():
    r._download(r.LABELS_URL, LABELS)

devrel_python = r._find_devrel_python(None)

r.step3_test(
    DLC,
    str(IMG),
    LABELS,
    devrel_python=devrel_python,
    sdk="qnn",
    warmup=3,
    runs=10,
    top_k=5,
)
