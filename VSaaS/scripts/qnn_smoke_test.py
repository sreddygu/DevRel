from __future__ import annotations

import json
import os
import sys

from vsaas.qnn_yolov8 import QnnYoloV8Config, QnnYoloV8Detector


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 scripts/qnn_smoke_test.py /path/to/frame.jpg", file=sys.stderr)
        return 2

    frame_path = argv[1]
    cfg = QnnYoloV8Config(
        backend=os.environ.get("VSAAS_QNN_BACKEND", "/lib/libQnnHtp.so").strip(),
        model_so=os.environ.get("VSAAS_QNN_MODEL_SO", "").strip() or None,
        dlc_path=os.environ.get("VSAAS_QNN_DLC_PATH", "").strip() or None,
        retrieve_context=os.environ.get("VSAAS_QNN_RETRIEVE_CONTEXT", "").strip() or None,
        input_name=os.environ.get("VSAAS_QNN_INPUT_NAME", "images").strip(),
        input_size=int(os.environ.get("VSAAS_QNN_INPUT_SIZE", "640")),
    )
    det = QnnYoloV8Detector(cfg)
    dets = det.detect(frame_path)
    out = [
        {"label": d.label, "score": round(float(d.score), 4), "bbox": [d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2]}
        for d in sorted(dets, key=lambda d: d.score, reverse=True)[:20]
    ]
    print(json.dumps({"count": len(dets), "top": out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
