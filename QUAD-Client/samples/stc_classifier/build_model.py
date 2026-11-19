"""Synthesize a tiny 1D-CNN ONNX model for the Smart Traffic Classifier.

Input  : 64 packet-header bytes (float32, normalized)  shape=[1, 1, 64]
Output : 5-class logits (video / voip / web / iot / bulk) shape=[1, 5]

Mock-mode QUAD doesn't read this file -- it's emitted so the convert
+ codegen artifacts have a real ONNX next to them, and so the host
test suite can sanity-check the graph with onnx.checker.

The graph uses:
  Conv (1->8, kernel=3) -> Relu -> Conv (8->16, kernel=3) -> Relu
  -> GlobalAveragePool -> MatMul (16->5) -> output

All weights are deterministic (np.random with a fixed seed) so the
regenerated file is byte-stable across runs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

SEED = 17
NUM_CLASSES = 5
INPUT_LEN = 64

OUT_PATH = Path(__file__).resolve().parent / "stc_1dcnn.onnx"


def _const(name: str, array: np.ndarray) -> onnx.TensorProto:
    return numpy_helper.from_array(array.astype(np.float32), name=name)


def build() -> onnx.ModelProto:
    rng = np.random.default_rng(SEED)

    # Layer 1: Conv1d(1 -> 8, k=3, pad=1)
    w1 = rng.standard_normal((8, 1, 3)) * 0.2
    b1 = np.zeros((8,))

    # Layer 2: Conv1d(8 -> 16, k=3, pad=1)
    w2 = rng.standard_normal((16, 8, 3)) * 0.2
    b2 = np.zeros((16,))

    # Classifier: MatMul (16 -> 5)
    wfc = rng.standard_normal((16, NUM_CLASSES)) * 0.1

    initializers = [
        _const("w1", w1), _const("b1", b1),
        _const("w2", w2), _const("b2", b2),
        _const("wfc", wfc),
    ]

    nodes = [
        helper.make_node(
            "Conv", ["input", "w1", "b1"], ["c1"],
            kernel_shape=[3], pads=[1, 1], strides=[1],
        ),
        helper.make_node("Relu", ["c1"], ["r1"]),
        helper.make_node(
            "Conv", ["r1", "w2", "b2"], ["c2"],
            kernel_shape=[3], pads=[1, 1], strides=[1],
        ),
        helper.make_node("Relu", ["c2"], ["r2"]),
        # GlobalAveragePool collapses sequence dim: [1,16,L] -> [1,16,1]
        helper.make_node("GlobalAveragePool", ["r2"], ["pooled"]),
        # Squeeze last dim: [1,16,1] -> [1,16]
        helper.make_node(
            "Squeeze", ["pooled"], ["features"],
            axes=[2],
        ),
        helper.make_node("MatMul", ["features", "wfc"], ["logits"]),
    ]

    graph = helper.make_graph(
        nodes,
        name="stc_1dcnn",
        inputs=[
            helper.make_tensor_value_info(
                "input", TensorProto.FLOAT, [1, 1, INPUT_LEN]
            ),
        ],
        outputs=[
            helper.make_tensor_value_info(
                "logits", TensorProto.FLOAT, [1, NUM_CLASSES]
            ),
        ],
        initializer=initializers,
    )

    opset = helper.make_opsetid("", 11)
    model = helper.make_model(graph, opset_imports=[opset])
    model.ir_version = 7
    model.producer_name = "stc_classifier.build_model"
    onnx.checker.check_model(model)
    return model


def main() -> int:
    model = build()
    OUT_PATH.write_bytes(model.SerializeToString())
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Wrote {OUT_PATH.name} ({size_kb:.1f} KB)")
    print(f"  input  : {[1, 1, INPUT_LEN]} float32 (normalized header bytes)")
    print(f"  output : {[1, NUM_CLASSES]} float32 (5-class logits)")
    print("  classes: video, voip, web, iot, bulk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
