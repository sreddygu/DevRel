"""Issue 23 test: benchmark the pre-downloaded HTP .bin from a NATIVE arm64 venv."""
from pathlib import Path

import run_mobilenetv2 as r

HERE = Path(__file__).resolve().parent
BIN = HERE / "quad_artifacts" / "mobilenetv2.bin"
IMG = HERE / "test_input.jpg"
LABELS = HERE / "imagenet_classes.txt"
if not LABELS.exists():
    r._download(r.LABELS_URL, LABELS)

r.step3_test(
    BIN, str(IMG), LABELS,
    quad_python=r.sys.executable,
    sdk="qnn", warmup=3, runs=10, top_k=5,
)
