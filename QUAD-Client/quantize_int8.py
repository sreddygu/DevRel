"""
Quantize mobilenetv2-12.onnx to INT8 QDQ format for Hexagon HTP.
Uses onnxruntime.quantization with static quantization + QDQ format.
Random calibration data is used here — for production use real images.
"""
import numpy as np
from onnxruntime.quantization import (
    CalibrationDataReader,
    QuantFormat,
    QuantType,
    quantize_static,
)

INPUT_MODEL  = "mobilenetv2-12.onnx"
OUTPUT_MODEL = "mobilenetv2-12-int8-qdq.onnx"
INPUT_NAME   = "input"
INPUT_SHAPE  = (1, 3, 224, 224)
N_CALIB      = 20


class RandomCalibReader(CalibrationDataReader):
    def __init__(self):
        self._data = [
            {INPUT_NAME: np.random.randn(*INPUT_SHAPE).astype(np.float32)}
            for _ in range(N_CALIB)
        ]
        self._idx = 0

    def get_next(self):
        if self._idx >= len(self._data):
            return None
        item = self._data[self._idx]
        self._idx += 1
        return item


print(f"Quantizing {INPUT_MODEL} -> {OUTPUT_MODEL}")
print(f"Calibration: {N_CALIB} random samples (replace with real images for production)")

quantize_static(
    INPUT_MODEL,
    OUTPUT_MODEL,
    RandomCalibReader(),
    quant_format=QuantFormat.QDQ,      # Hexagon HTP requires QDQ, not ConvInteger
    activation_type=QuantType.QInt8,
    weight_type=QuantType.QInt8,
)

import os

size_mb = os.path.getsize(OUTPUT_MODEL) / 1024 / 1024
print(f"Done. Output size: {size_mb:.1f} MB  (input was 13.3 MB)")
