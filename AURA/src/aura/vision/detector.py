# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""YOLO (ONNX) object detector → scene description → Events (Milestone 1).

Runs a YOLO model via ONNX Runtime (CPU EP on the VENTUNO Q, or the Hexagon
NPU EP later) over a frame, and turns detections into
:class:`aura.core.events.Event` records like::

    {"timestamp": "10:24", "event": "Person entered room", "type": "detection",
     "entities": ["person"], "confidence": 0.91, "source": "vision"}

``onnxruntime`` / ``numpy`` / ``PIL`` are imported lazily inside :meth:`load`
and :meth:`detect` so this module imports without the ``vision`` extra. The
box-decode + NMS postprocess is self-contained (stdlib + numpy) so AURA does
not depend on any sibling project.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from aura.core.events import Event

# COCO-80 class names — the label set of stock YOLOv8 (yolov8n.onnx / .dlc).
COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


@dataclass
class Detection:
    """One detected object in a frame (pixel-space box)."""

    label: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection-over-union of two ``(x1, y1, x2, y2)`` boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(dets: list[Detection], iou_thresh: float, max_det: int) -> list[Detection]:
    """Greedy non-maximum suppression, highest-confidence first."""
    kept: list[Detection] = []
    for d in sorted(dets, key=lambda x: x.confidence, reverse=True):
        if len(kept) >= max_det:
            break
        fbox = tuple(float(v) for v in d.box)
        if all(_iou(fbox, tuple(float(v) for v in k.box)) < iou_thresh for k in kept):
            kept.append(d)
    return kept


def decode_yolov8(
    out: Any,
    *,
    input_size: int,
    labels: list[str],
    conf_threshold: float,
    nms_iou: float = 0.45,
    max_det: int = 100,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> list[Detection]:
    """Turn a raw YOLOv8 output tensor into pixel-space :class:`Detection`\\ s.

    Handles the usual Ultralytics export shape ``(1, 84, 8400)`` (transposed to
    rows of ``[cx, cy, w, h, cls0..cls79]``). Boxes are in the model's
    ``input_size`` space; ``scale_x/scale_y`` map them back to the original
    frame. Pure numpy + stdlib.
    """
    import numpy as np  # noqa: PLC0415 — lazy: keeps base install importable

    arr = np.asarray(out)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    # Orient to rows-of-attributes. Ultralytics exports (4+num_classes, anchors),
    # e.g. (84, 8400); we want (anchors, 84). The attribute axis length is
    # 4 + len(labels); whichever axis matches that is the attribute axis.
    n_attr = 4 + len(labels)
    if arr.ndim == 2 and arr.shape[0] == n_attr and arr.shape[1] != n_attr:
        arr = arr.transpose(1, 0)
    if arr.ndim != 2 or arr.shape[1] < 5:
        return []

    dets: list[Detection] = []
    for row in arr:
        cx, cy, bw, bh = (float(v) for v in row[:4])
        cls_scores = row[4:]
        cls_id = int(np.argmax(cls_scores))
        score = float(cls_scores[cls_id])
        if not math.isfinite(score) or score < conf_threshold:
            continue
        label = labels[cls_id] if 0 <= cls_id < len(labels) else f"class_{cls_id}"
        x1 = (cx - bw / 2.0) * scale_x
        y1 = (cy - bh / 2.0) * scale_y
        x2 = (cx + bw / 2.0) * scale_x
        y2 = (cy + bh / 2.0) * scale_y
        dets.append(
            Detection(label=label, confidence=score,
                      box=(int(x1), int(y1), int(x2), int(y2)))
        )
    return _nms(dets, iou_thresh=nms_iou, max_det=max_det)


class Detector:
    """YOLO ONNX detector.

    Args:
        model_path: Path to a YOLO ``.onnx`` model.
        conf_threshold: Minimum confidence to keep a detection.
        input_size: Square model input dimension (YOLOv8 default 640).
        labels: Class-name list (defaults to :data:`COCO80`).
        providers: ONNX Runtime execution providers; defaults to CPU. Pass e.g.
            ``["QNNExecutionProvider"]`` to target the Hexagon NPU.
    """

    def __init__(
        self,
        model_path: str,
        *,
        conf_threshold: float = 0.35,
        input_size: int = 640,
        labels: list[str] | None = None,
        providers: list[str] | None = None,
    ) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.input_size = input_size
        self.labels = labels or COCO80
        self.providers = providers or ["CPUExecutionProvider"]
        self._session: Any = None
        self._input_name: str | None = None

    def load(self) -> Detector:
        """Create the ONNX Runtime inference session (lazy-imports onnxruntime)."""
        import onnxruntime as ort  # noqa: PLC0415 — lazy heavy import

        self._session = ort.InferenceSession(self.model_path, providers=self.providers)
        self._input_name = self._session.get_inputs()[0].name
        return self

    def _preprocess(self, frame: Any) -> tuple[Any, float, float]:
        """Frame (HWC BGR/RGB ``np.ndarray`` or PIL image) → NCHW float tensor.

        Returns the tensor plus the x/y scale factors from model space back to
        the original frame, so decoded boxes land in original pixel coords.
        """
        import numpy as np  # noqa: PLC0415

        s = self.input_size
        arr = np.asarray(frame)
        if arr.ndim == 2:  # grayscale → 3-channel
            arr = np.stack([arr] * 3, axis=-1)
        h, w = arr.shape[:2]
        # Nearest-neighbour resize to SxS without pulling in cv2/PIL here.
        ys = (np.linspace(0, h - 1, s)).astype(np.int64)
        xs = (np.linspace(0, w - 1, s)).astype(np.int64)
        resized = arr[ys][:, xs]
        x = resized.astype("float32") / 255.0
        x = x.transpose(2, 0, 1)[None, ...]  # NCHW
        return x, w / s, h / s

    def detect(self, frame: Any) -> list[Detection]:
        """Run inference on one frame and return kept detections."""
        if self._session is None:
            self.load()
        x, scale_x, scale_y = self._preprocess(frame)
        out = self._session.run(None, {self._input_name: x})[0]
        return decode_yolov8(
            out,
            input_size=self.input_size,
            labels=self.labels,
            conf_threshold=self.conf_threshold,
            scale_x=scale_x,
            scale_y=scale_y,
        )

    def describe(self, detections: list[Detection]) -> str:
        """Summarize detections into a human-readable scene description.

        e.g. ``[person, dog]`` → ``"A person and a dog are in view"``;
        ``[person, person]`` → ``"2 people are in view"``.
        """
        if not detections:
            return "Nothing is in view"

        counts: dict[str, int] = {}
        for d in detections:
            counts[d.label] = counts.get(d.label, 0) + 1

        parts: list[str] = []
        for label, n in counts.items():
            if n == 1:
                article = "an" if label[:1].lower() in "aeiou" else "a"
                parts.append(f"{article} {label}")
            else:
                parts.append(f"{n} {_plural(label)}")

        if len(parts) == 1:
            phrase = parts[0]
        else:
            phrase = ", ".join(parts[:-1]) + f" and {parts[-1]}"
        verb = "is" if len(detections) == 1 else "are"
        return f"{phrase[0].upper()}{phrase[1:]} {verb} in view"

    def to_events(self, detections: list[Detection], *, location: str | None = None) -> list[Event]:
        """Convert detections into Events for the memory store.

        This bit needs no model, so it's implemented: it's the bridge from the
        vision domain into the shared :class:`Event` contract.
        """
        return [
            Event(
                event=f"{d.label} detected",
                type="detection",
                entities=[d.label],
                confidence=round(float(d.confidence), 3),
                location=location,
                source="vision",
                attributes={"box": list(d.box)},
            )
            for d in detections
        ]


def _plural(label: str) -> str:
    """Small English pluralizer for scene descriptions (``person`` → ``people``)."""
    irregular = {"person": "people", "mouse": "mice"}
    if label in irregular:
        return irregular[label]
    if label.endswith(("s", "x", "z", "ch", "sh")):
        return label + "es"
    if label.endswith("y") and label[-2:-1] not in "aeiou":
        return label[:-1] + "ies"
    return label + "s"
