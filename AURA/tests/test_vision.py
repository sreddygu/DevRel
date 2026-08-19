# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Milestone 1 (Vision) tests.

These run on the base install: the ONNX Runtime session is faked, so the
detector's preprocess → decode → NMS → Events path is exercised without the
``vision`` extra or a real model file. numpy is a base dependency.
"""

from __future__ import annotations

import numpy as np
import pytest

from aura.core.events import Event
from aura.vision.detector import COCO80, Detection, Detector, decode_yolov8


def _yolo_output(rows: list[list[float]]) -> np.ndarray:
    """Build a fake Ultralytics-shaped output ``(1, 84, N)`` from rows of len 84."""
    arr = np.array(rows, dtype="float32")  # (N, 84)
    return arr.transpose(1, 0)[None, ...]  # (1, 84, N)


def _row(cx, cy, w, h, cls_id, score) -> list[float]:
    row = [cx, cy, w, h] + [0.0] * 80
    row[4 + cls_id] = score
    return row


def test_decode_yolov8_picks_class_and_scales() -> None:
    # one "person" (class 0) box at center, high score, in 640-space
    out = _yolo_output([_row(320, 320, 100, 200, 0, 0.9)])
    dets = decode_yolov8(out, input_size=640, labels=COCO80, conf_threshold=0.35)
    assert len(dets) == 1
    d = dets[0]
    assert d.label == "person"
    assert d.confidence == pytest.approx(0.9)
    # box centered: (270,220)-(370,420) in model space, scale 1.0
    assert d.box == (270, 220, 370, 420)


def test_decode_yolov8_conf_threshold_filters() -> None:
    out = _yolo_output([_row(320, 320, 50, 50, 16, 0.10)])  # dog, low score
    dets = decode_yolov8(out, input_size=640, labels=COCO80, conf_threshold=0.35)
    assert dets == []


def test_decode_yolov8_nms_dedupes_overlap() -> None:
    # two near-identical person boxes → NMS keeps the higher-scoring one
    out = _yolo_output([
        _row(320, 320, 100, 100, 0, 0.9),
        _row(322, 321, 100, 100, 0, 0.6),
    ])
    dets = decode_yolov8(out, input_size=640, labels=COCO80, conf_threshold=0.35)
    assert len(dets) == 1
    assert dets[0].confidence == pytest.approx(0.9)


class _FakeSession:
    """Stand-in for onnxruntime.InferenceSession."""

    def __init__(self, output: np.ndarray) -> None:
        self._output = output

    def get_inputs(self):
        class _I:
            name = "images"
        return [_I()]

    def run(self, _outputs, _feeds):
        return [self._output]


def test_detector_detect_with_fake_session() -> None:
    out = _yolo_output([_row(320, 320, 100, 200, 0, 0.95)])
    det = Detector("unused.onnx", conf_threshold=0.35, input_size=640)
    det._session = _FakeSession(out)
    det._input_name = "images"

    frame = np.zeros((480, 640, 3), dtype="uint8")
    dets = det.detect(frame)
    assert [d.label for d in dets] == ["person"]


def test_describe_variants() -> None:
    det = Detector("unused.onnx")
    assert det.describe([]) == "Nothing is in view"
    one = [Detection("dog", 0.9, (0, 0, 1, 1))]
    assert det.describe(one) == "A dog is in view"
    apple = [Detection("apple", 0.9, (0, 0, 1, 1))]
    assert det.describe(apple) == "An apple is in view"
    two_people = [Detection("person", 0.9, (0, 0, 1, 1)),
                  Detection("person", 0.8, (2, 2, 3, 3))]
    assert det.describe(two_people) == "2 people are in view"
    mixed = [Detection("person", 0.9, (0, 0, 1, 1)),
             Detection("dog", 0.8, (2, 2, 3, 3))]
    assert det.describe(mixed) == "A person and a dog are in view"


def test_to_events_bridges_to_contract() -> None:
    det = Detector("unused.onnx")
    dets = [Detection("backpack", 0.812, (10, 20, 30, 40))]
    events = det.to_events(dets, location="study room")
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, Event)
    assert ev.event == "backpack detected"
    assert ev.type == "detection"
    assert ev.entities == ["backpack"]
    assert ev.confidence == 0.812
    assert ev.location == "study room"
    assert ev.source == "vision"
    assert ev.attributes["box"] == [10, 20, 30, 40]
