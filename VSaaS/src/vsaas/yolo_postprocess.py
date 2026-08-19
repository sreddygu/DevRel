from __future__ import annotations

import math
import os

from .edge_vision import BBox, Detection, iou


def nms(dets: list[Detection], iou_thresh: float, max_det: int) -> list[Detection]:
    dets = sorted(dets, key=lambda d: d.score, reverse=True)
    kept: list[Detection] = []
    for d in dets:
        if len(kept) >= max_det:
            break
        if all(iou(d.bbox, k.bbox) < iou_thresh for k in kept):
            kept.append(d)
    return kept


def yolo_v8_rows_to_detections(
    rows,
    *,
    input_size: int,
    labels: list[str],
    conf_default: float = 0.25,
    nms_iou_default: float = 0.45,
    max_det_default: int = 100,
) -> list[Detection]:
    """
    Convert YOLOv8-style rows (each row: [x,y,w,h, cls0,cls1,...]) to normalized detections.

    `rows` must be an iterable of 1D sequences (list/tuple/numpy row).
    """

    conf_th = float(os.environ.get("VSAAS_DET_CONF", str(conf_default)))
    nms_iou = float(os.environ.get("VSAAS_DET_NMS_IOU", str(nms_iou_default)))
    max_det = int(os.environ.get("VSAAS_DET_MAX", str(max_det_default)))

    s = float(input_size)
    dets: list[Detection] = []
    for row in rows:
        if len(row) < 6:
            continue
        x_c, y_c, bw, bh = [float(v) for v in row[:4]]
        if not (math.isfinite(x_c) and math.isfinite(y_c) and math.isfinite(bw) and math.isfinite(bh)):
            continue
        cls_scores = row[4:]
        # avoid numpy dependency here; assume cls_scores is indexable
        cls_id = max(range(len(cls_scores)), key=lambda i: float(cls_scores[i]))
        score = float(cls_scores[cls_id])
        if not math.isfinite(score):
            continue
        if score < conf_th:
            continue
        label = labels[cls_id] if 0 <= cls_id < len(labels) else f"class_{cls_id}"

        x1 = x_c - bw / 2.0
        y1 = y_c - bh / 2.0
        x2 = x_c + bw / 2.0
        y2 = y_c + bh / 2.0
        if not (math.isfinite(x1) and math.isfinite(y1) and math.isfinite(x2) and math.isfinite(y2)):
            continue

        nx1, ny1, nx2, ny2 = x1 / s, y1 / s, x2 / s, y2 / s
        nx1, ny1 = max(0.0, min(1.0, nx1)), max(0.0, min(1.0, ny1))
        nx2, ny2 = max(0.0, min(1.0, nx2)), max(0.0, min(1.0, ny2))
        dets.append(Detection(label=label, score=score, bbox=BBox(nx1, ny1, nx2, ny2)))

    return nms(dets, iou_thresh=nms_iou, max_det=max_det)
