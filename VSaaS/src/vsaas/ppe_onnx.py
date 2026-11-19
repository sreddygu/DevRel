"""
ONNX-based PPE checker for VSaaS.

This expects a PPE-trained detector model exported to ONNX (YOLOv8-style output).
You provide the model and labels.

Environment:
- VSAAS_PPE_ONNX_PATH   Path to PPE ONNX model
- VSAAS_PPE_LABELS      Comma-separated label list for class indices (e.g. "person,helmet,vest,...")
- VSAAS_PPE_REQUIRED    Comma-separated required PPE items (default: "helmet")
- VSAAS_PPE_IOU         Minimum IOU of PPE item box with person box (default: 0.10)

Notes:
- This module is optional; it requires `pip install -r requirements.txt`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .edge_vision import Detection, iou
from .yolo_onnx import YoloV8OnnxConfig, YoloV8OnnxDetector


def _parse_labels(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


@dataclass(frozen=True)
class PpeResult:
    violation: bool
    missing: list[str]


class OnnxPpeChecker:
    """Run a PPE detector and check required items per person detection."""

    def __init__(self) -> None:
        model_path = os.environ.get("VSAAS_PPE_ONNX_PATH", "").strip()
        if not model_path:
            raise SystemExit("VSAAS_PPE_ONNX_PATH is required for VSAAS_PPE_CHECKER=onnx_ppe")

        labels_s = os.environ.get("VSAAS_PPE_LABELS", "").strip()
        if not labels_s:
            raise SystemExit("VSAAS_PPE_LABELS is required for VSAAS_PPE_CHECKER=onnx_ppe (comma-separated labels)")
        labels = _parse_labels(labels_s)

        self._required = _parse_labels(os.environ.get("VSAAS_PPE_REQUIRED", "helmet"))
        self._iou = float(os.environ.get("VSAAS_PPE_IOU", "0.10"))

        self._det = YoloV8OnnxDetector(YoloV8OnnxConfig(path=model_path, labels=labels))

    def check(self, person: Detection, frame_path: str) -> dict[str, Any]:
        dets = self._det.detect(frame_path)

        present: set[str] = set()
        for d in dets:
            if d.label in self._required and iou(d.bbox, person.bbox) >= self._iou:
                present.add(d.label)

        missing = [r for r in self._required if r not in present]
        return {"violation": bool(missing), "missing": missing, "present": sorted(present)}
