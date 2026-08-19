from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .edge_vision import Detection
from .yolo_onnx import COCO80
from .yolo_postprocess import yolo_v8_rows_to_detections


def _require_edge_deps() -> tuple[object, object]:
    try:
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit("Missing dependency 'numpy'. Install edge deps: pip install -r requirements.txt") from e
    try:
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise SystemExit("Missing dependency 'Pillow'. Install edge deps: pip install -r requirements.txt") from e
    return np, Image


@dataclass(frozen=True)
class QnnYoloV8Config:
    # Exactly one of these must be provided:
    model_so: str | None = None  # passed to `qnn-net-run --model`
    dlc_path: str | None = None  # passed to `qnn-net-run --dlc_path`
    retrieve_context: str | None = None  # passed to `qnn-net-run --retrieve_context`

    backend: str = "/lib/libQnnHtp.so"  # HTP/NPU backend on IQ8
    input_name: str = "images"
    input_size: int = 640
    labels: list[str] | None = None


class QnnYoloV8Detector:
    """
    YOLOv8 detector that shells out to `qnn-net-run` (QNN / HTP).

    This is intentionally simple for demo workflows. It assumes the QNN-exported model
    emits a YOLOv8-style raw output compatible with the same post-processing used for ONNX.

    Required env/config depends on the exported artifacts:
    - `VSAAS_QNN_MODEL_SO` or `VSAAS_QNN_DLC_PATH` or `VSAAS_QNN_RETRIEVE_CONTEXT`
    - `VSAAS_QNN_INPUT_NAME` (default: images)
    - Optional overrides:
      - `VSAAS_QNN_OUTPUT_NAME` (pick which output .raw to parse)
      - `VSAAS_QNN_OUTPUT_DTYPE` (default: float32)
    """

    def __init__(self, cfg: QnnYoloV8Config) -> None:
        if not (cfg.model_so or cfg.dlc_path or cfg.retrieve_context):
            raise SystemExit(
                "QNN detector requires one of: VSAAS_QNN_MODEL_SO, VSAAS_QNN_DLC_PATH, VSAAS_QNN_RETRIEVE_CONTEXT"
            )
        self._cfg = cfg
        self._labels = cfg.labels or COCO80

    def detect(self, frame_path: str) -> list[Detection]:
        np, Image = _require_edge_deps()

        s = int(self._cfg.input_size)
        img = Image.open(frame_path).convert("RGB").resize((s, s))
        x = np.asarray(img).astype("float32") / 255.0
        x = x.transpose(2, 0, 1)[None, ...]  # NCHW

        with tempfile.TemporaryDirectory(prefix="vsaas_qnn_") as td:
            tdir = Path(td)
            input_raw = tdir / "input.raw"
            input_list = tdir / "input_list.txt"
            out_dir = tdir / "out"

            x.astype("float32").tofile(input_raw)
            input_list.write_text(f"{self._cfg.input_name}:={input_raw}\n", encoding="utf-8")

            cmd: list[str] = [
                "qnn-net-run",
                "--backend",
                self._cfg.backend,
                "--input_list",
                str(input_list),
                "--output_dir",
                str(out_dir),
            ]
            if self._cfg.retrieve_context:
                cmd += ["--retrieve_context", self._cfg.retrieve_context]
            elif self._cfg.dlc_path:
                cmd += ["--dlc_path", self._cfg.dlc_path]
            else:
                cmd += ["--model", self._cfg.model_so or ""]

            # Keep logs quiet unless explicitly requested.
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode != 0:
                hint = proc.stderr.strip().splitlines()[-20:]
                raise RuntimeError("qnn-net-run failed:\n" + "\n".join(hint))

            raw_files = list(out_dir.rglob("*.raw"))
            if not raw_files:
                return []

            desired = os.environ.get("VSAAS_QNN_OUTPUT_NAME", "").strip()
            out_raw: Path
            if desired:
                matches = [p for p in raw_files if p.stem == desired or p.name == desired]
                out_raw = matches[0] if matches else raw_files[0]
            else:
                out_raw = raw_files[0]

            dtype_s = os.environ.get("VSAAS_QNN_OUTPUT_DTYPE", "float32").strip().lower()
            dtype = {"float32": np.float32, "fp32": np.float32, "float": np.float32}.get(dtype_s, np.float32)

            arr = np.fromfile(out_raw, dtype=dtype)
            # Try to infer YOLOv8 row width (84 or 85 typical).
            row_w = None
            for w in (84, 85):
                if arr.size % w == 0:
                    row_w = w
                    break
            if row_w is None:
                # As a fallback, allow explicit shape like "8400,84" or "84,8400".
                shape_s = os.environ.get("VSAAS_QNN_YOLO_SHAPE", "").strip()
                if not shape_s:
                    return []
                parts = [int(p) for p in shape_s.split(",") if p.strip()]
                if len(parts) != 2:
                    return []
                out = arr.reshape(parts)
            else:
                out = arr.reshape(-1, row_w)

            # If transposed (84,8400), transpose to (8400,84).
            if out.shape[0] in (84, 85) and out.shape[1] > out.shape[0]:
                out = out.transpose(1, 0)

            if out.shape[1] < 6:
                return []

            return yolo_v8_rows_to_detections(out, input_size=s, labels=self._labels)
