"""
ONNX-based YOLO detector helpers for VSaaS.

This enables "real" edge object detection without requiring a full QNN pipeline.
It is designed to be dependency-optional:

Install extra deps (same file as core requirements):
  pip install -r requirements.txt

Environment:
- VSAAS_YOLO_ONNX_PATH   Path to YOLOv8 ONNX file (default: models/yolov8n.onnx)
- VSAAS_DET_CONF         Confidence threshold (default: 0.25)
- VSAAS_DET_NMS_IOU      NMS IOU threshold (default: 0.45)
- VSAAS_DET_MAX          Max detections returned (default: 100)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .edge_vision import Detection
from .yolo_postprocess import yolo_v8_rows_to_detections


def _require_edge_deps() -> tuple[object, object, object]:
    try:
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit("Missing dependency 'numpy'. Install edge deps: pip install -r requirements.txt") from e
    try:
        import onnxruntime as ort  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "Missing dependency 'onnxruntime'. Install edge deps: pip install -r requirements.txt"
        ) from e
    try:
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit("Missing dependency 'Pillow'. Install edge deps: pip install -r requirements.txt") from e
    return np, ort, Image


COCO80 = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]


@dataclass(frozen=True)
class YoloV8OnnxConfig:
    path: str
    labels: list[str] | None = None
    input_size: int = 640  # typical YOLOv8 export


class YoloV8OnnxDetector:
    """YOLOv8 ONNX detector for COCO-style models (e.g., yolov8n.onnx)."""

    def __init__(self, cfg: YoloV8OnnxConfig) -> None:
        np, ort, _ = _require_edge_deps()
        self._np = np
        self._ort = ort
        self._cfg = cfg
        self._labels = cfg.labels or COCO80

        if not os.path.exists(cfg.path):
            raise SystemExit(f"YOLO ONNX model not found: {cfg.path} (set VSAAS_YOLO_ONNX_PATH)")

        providers = ["CPUExecutionProvider"]
        self._session = ort.InferenceSession(cfg.path, providers=providers)
        self._input_name = self._session.get_inputs()[0].name

    def detect(self, frame_path: str) -> list[Detection]:
        np, _, Image = _require_edge_deps()

        img = Image.open(frame_path).convert("RGB")
        s = int(self._cfg.input_size)

        resized = img.resize((s, s))
        x = np.asarray(resized).astype("float32") / 255.0
        x = x.transpose(2, 0, 1)[None, ...]  # NCHW

        out = self._session.run(None, {self._input_name: x})[0]
        out = np.asarray(out)

        # Ultralytics YOLOv8 export is typically (1, 84, 8400) => transpose to (8400, 84)
        if out.ndim == 3 and out.shape[0] == 1:
            out = out[0]
        if out.ndim == 2 and out.shape[0] in (84, 85) and out.shape[1] > out.shape[0]:
            out = out.transpose(1, 0)
        if out.ndim != 2 or out.shape[1] < 6:
            return []

        return yolo_v8_rows_to_detections(out, input_size=s, labels=self._labels)
