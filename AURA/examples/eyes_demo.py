# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 1 (Eyes) demo — frame → YOLO detection → Event JSON.

Runs the YOLOv8 ONNX detector over an image (or webcam frame), prints a
human-readable scene description, and dumps the detection Events as JSON —
the same Events that flow into AURA's memory store.

    # an image or a directory of images (no camera needed):
    python examples/eyes_demo.py path/to/image.jpg
    # a webcam (index 0), one frame:
    python examples/eyes_demo.py 0

Needs the ``vision`` extra (``pip install -e ".[vision]"``) and a YOLOv8 ONNX
model. Set AURA_YOLO_MODEL / AURA_CAMERA (see .env.example); the model path
defaults to ``./models/yolov8n.onnx``.
"""

from __future__ import annotations

import sys

from aura.config import load_settings
from aura.core.pipeline import AuraPipeline
from aura.vision.camera import Camera
from aura.vision.detector import Detector


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    settings = load_settings()
    source = argv[0] if argv else settings.camera

    detector = Detector(settings.yolo_model).load()
    pipe = AuraPipeline(detector=detector)

    with Camera(source, max_frames=1) as cam:
        frame = cam.read()
    if frame is None:
        print(f"No frame from source {source!r}", file=sys.stderr)
        return 1

    detections = detector.detect(frame)
    print("== Scene ==")
    print(detector.describe(detections), "\n")

    print("== Events ==")
    for ev in pipe.perceive(frame, location="demo"):
        print(ev.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
