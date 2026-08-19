"""
Minimal edge-vision utilities for VSaaS (no heavy deps).

Goal: support an "edge-first" VSaaS demo where most intelligence happens on the device:
- Object/person detection (pluggable detector)
- Simple multi-object tracking (IOU-based)
- Zone analytics: intrusion (restricted zone entry) + dwell (time in zone)
- PPE checks (pluggable PPE checker)

The default detector is a deterministic mock so the project runs end-to-end
without model dependencies. For real detection, you can use:
- ONNX YOLOv8 (CPU) via `VSAAS_DETECTOR=onnx_yolov8`
- QNN YOLOv8 (HTP/NPU) via `VSAAS_DETECTOR=qnn_yolov8` (requires QNN-exported artifacts)
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in pixel coordinates (or normalized coords depending on upstream)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def clamp(self) -> "BBox":
        x1 = min(self.x1, self.x2)
        x2 = max(self.x1, self.x2)
        y1 = min(self.y1, self.y2)
        y2 = max(self.y1, self.y2)
        return BBox(x1=x1, y1=y1, x2=x2, y2=y2)

    def area(self) -> float:
        b = self.clamp()
        return max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)

    def center(self) -> tuple[float, float]:
        b = self.clamp()
        return ((b.x1 + b.x2) / 2.0, (b.y1 + b.y2) / 2.0)


def iou(a: BBox, b: BBox) -> float:
    a = a.clamp()
    b = b.clamp()
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    denom = a.area() + b.area() - inter
    if denom <= 0:
        return 0.0
    return inter / denom


@dataclass(frozen=True)
class Detection:
    label: str  # e.g. "person", "helmet", "vest"
    score: float
    bbox: BBox  # normalized [0..1] coords used by this pipeline


@dataclass
class Track:
    track_id: int
    label: str
    bbox: BBox
    last_ts_ms: int
    first_ts_ms: int

    def center(self) -> tuple[float, float]:
        return self.bbox.center()


class SimpleTracker:
    """Very small IOU tracker.

    This is good enough for a demo: it stabilizes object IDs across frames so we
    can compute zone entry and dwell time. For production, swap to ByteTrack,
    DeepSORT, etc.
    """

    def __init__(self, iou_threshold: float = 0.3, max_age_ms: int = 4000) -> None:
        self._iou_threshold = float(iou_threshold)
        self._max_age_ms = int(max_age_ms)
        self._next_id = 1
        self._tracks: dict[int, Track] = {}

    def update(self, detections: list[Detection], ts_ms: int) -> list[Track]:
        # Greedy matching by highest IOU.
        unmatched_det = set(range(len(detections)))
        updated: dict[int, Track] = {}

        existing = list(self._tracks.values())
        # Drop stale tracks before matching.
        existing = [t for t in existing if ts_ms - t.last_ts_ms <= self._max_age_ms]

        pairs: list[tuple[float, int, int]] = []
        for ti, t in enumerate(existing):
            for di, d in enumerate(detections):
                if t.label != d.label:
                    continue
                pairs.append((iou(t.bbox, d.bbox), ti, di))
        pairs.sort(reverse=True, key=lambda x: x[0])

        matched_tracks: set[int] = set()
        for score, ti, di in pairs:
            if score < self._iou_threshold:
                break
            if di not in unmatched_det:
                continue
            track = existing[ti]
            if track.track_id in matched_tracks:
                continue
            unmatched_det.remove(di)
            matched_tracks.add(track.track_id)
            updated[track.track_id] = Track(
                track_id=track.track_id,
                label=track.label,
                bbox=detections[di].bbox,
                last_ts_ms=ts_ms,
                first_ts_ms=track.first_ts_ms,
            )

        # Start new tracks for remaining detections.
        for di in sorted(unmatched_det):
            d = detections[di]
            tid = self._next_id
            self._next_id += 1
            updated[tid] = Track(
                track_id=tid,
                label=d.label,
                bbox=d.bbox,
                last_ts_ms=ts_ms,
                first_ts_ms=ts_ms,
            )

        self._tracks = updated
        return list(self._tracks.values())


@dataclass(frozen=True)
class Zone:
    """A polygonal region-of-interest."""

    zone_id: str
    kind: str  # "restricted" (intrusion) or "dwell"
    points: list[tuple[float, float]]  # [(x,y), ...] in normalized [0..1] coords
    dwell_threshold_sec: float = 10.0

    def contains_norm_point(self, p: tuple[float, float]) -> bool:
        # Ray casting algorithm; expects polygon points in normalized coords.
        x, y = p
        inside = False
        n = len(self.points)
        if n < 3:
            return False
        for i in range(n):
            x1, y1 = self.points[i]
            x2, y2 = self.points[(i + 1) % n]
            intersects = (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            if intersects:
                inside = not inside
        return inside


def load_zones_from_env() -> list[Zone]:
    """Load zones from `VSAAS_ZONES_JSON` or `VSAAS_ZONES_INLINE_JSON`."""

    inline = os.environ.get("VSAAS_ZONES_INLINE_JSON", "").strip()
    path = os.environ.get("VSAAS_ZONES_JSON", "").strip()

    raw: Any
    if inline:
        raw = json.loads(inline)
    elif path:
        raw = json.loads(open(path, "r", encoding="utf-8").read())
    else:
        return []

    zones: list[Zone] = []
    for z in raw.get("zones", []):
        zones.append(
            Zone(
                zone_id=str(z["zone_id"]),
                kind=str(z.get("kind", "restricted")),
                points=[(float(x), float(y)) for x, y in z["points"]],
                dwell_threshold_sec=float(z.get("dwell_threshold_sec", 10.0)),
            )
        )
    return zones


class Detector:
    """Detector interface."""

    def detect(self, frame_path: str) -> list[Detection]:  # pragma: no cover
        raise NotImplementedError


class MockDetector(Detector):
    """Mock detector for end-to-end demos without model dependencies.

    Behavior:
    - If `VSAAS_MOCK_DETECTIONS_JSON` is set, it should be a JSON array of detections:
      [{"label":"person","score":0.9,"bbox":[0.2,0.2,0.6,0.9]}, ...] in normalized coords.
    - Otherwise, emits a single "person" detection with a slowly moving bbox so
      zone/dwell logic can trigger.
    """

    def __init__(self) -> None:
        self._t0 = time.time()

    def detect(self, frame_path: str) -> list[Detection]:
        raw = os.environ.get("VSAAS_MOCK_DETECTIONS_JSON", "").strip()
        if raw:
            arr = json.loads(raw)
            out: list[Detection] = []
            for d in arr:
                x1, y1, x2, y2 = d["bbox"]
                out.append(
                    Detection(
                        label=str(d["label"]),
                        score=float(d.get("score", 0.9)),
                        bbox=BBox(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2)),
                    )
                )
            return out

        # Create a deterministic motion pattern.
        t = time.time() - self._t0
        x = 0.2 + 0.15 * math.sin(t / 3.0)
        y = 0.2 + 0.05 * math.cos(t / 5.0)
        return [
            Detection(
                label="person",
                score=0.85,
                bbox=BBox(x1=x, y1=y, x2=x + 0.25, y2=y + 0.55),
            )
        ]


class PpeChecker:
    """PPE checker interface."""

    def check(self, person: Detection, frame_path: str) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError


class MockPpeChecker(PpeChecker):
    """Mock PPE checker.

    - `VSAAS_MOCK_PPE_VIOLATION=1` forces a violation.
    """

    def check(self, person: Detection, frame_path: str) -> dict[str, Any]:
        violation = os.environ.get("VSAAS_MOCK_PPE_VIOLATION", "").strip().lower() in {"1", "true", "yes"}
        return {"violation": bool(violation), "missing": ["helmet"] if violation else []}


def choose_detector() -> Detector:
    kind = os.environ.get("VSAAS_DETECTOR", "mock").strip().lower()
    if kind == "mock":
        return MockDetector()
    if kind in {"onnx_yolov8", "onnx-yolov8", "yolov8_onnx"}:
        from .yolo_onnx import YoloV8OnnxConfig, YoloV8OnnxDetector

        model_path = os.environ.get("VSAAS_YOLO_ONNX_PATH", "models/yolov8n.onnx").strip()
        return YoloV8OnnxDetector(YoloV8OnnxConfig(path=model_path))
    if kind in {"qnn_yolov8", "qnn-yolov8", "yolov8_qnn"}:
        from .qnn_yolov8 import QnnYoloV8Config, QnnYoloV8Detector

        return QnnYoloV8Detector(
            QnnYoloV8Config(
                backend=os.environ.get("VSAAS_QNN_BACKEND", "/lib/libQnnHtp.so").strip(),
                model_so=os.environ.get("VSAAS_QNN_MODEL_SO", "").strip() or None,
                dlc_path=os.environ.get("VSAAS_QNN_DLC_PATH", "").strip() or None,
                retrieve_context=os.environ.get("VSAAS_QNN_RETRIEVE_CONTEXT", "").strip() or None,
                input_name=os.environ.get("VSAAS_QNN_INPUT_NAME", "images").strip(),
                input_size=int(os.environ.get("VSAAS_QNN_INPUT_SIZE", "640")),
            )
        )
    raise SystemExit(f"Unknown VSAAS_DETECTOR={kind!r} (supported: mock, onnx_yolov8, qnn_yolov8)")


def choose_ppe_checker() -> PpeChecker:
    kind = os.environ.get("VSAAS_PPE_CHECKER", "mock").strip().lower()
    if kind == "mock":
        return MockPpeChecker()
    if kind in {"onnx_ppe", "onnx-ppe"}:
        from .ppe_onnx import OnnxPpeChecker

        return OnnxPpeChecker()
    raise SystemExit(f"Unknown VSAAS_PPE_CHECKER={kind!r} (supported: mock, onnx_ppe)")


def norm_to_pixel_bbox(b: BBox, width: int, height: int) -> BBox:
    """Convert normalized bbox (0..1) -> pixel bbox using a known frame size."""

    return BBox(
        x1=float(b.x1) * width,
        y1=float(b.y1) * height,
        x2=float(b.x2) * width,
        y2=float(b.y2) * height,
    )
