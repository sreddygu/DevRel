"""Unit tests for the STC pre/post pipeline.

Exercises the math the C code performs (softmax, argmax, normalization)
in Python so we can test it without a cross-compiler. The C code in
tensor_io.c is the source of truth -- these tests verify our Python
shadow implementations agree with the C code's contract on the same
inputs (e.g. identical input bytes produce a known output distribution).
"""

from __future__ import annotations

import math

import numpy as np
import pytest


def softmax_py(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax matching tensor_io.c::softmax."""
    m = float(np.max(x))
    e = np.exp(x - m)
    s = float(np.sum(e))
    if s <= 0.0:
        s = 1.0
    return e / s


def stc_input_synth(seq: int, n: int = 64) -> np.ndarray:
    """Mirror prepare_inputs() in tensor_io.c.

    For sequence ``seq``, byte j = (seq * 131 + j * 17 + 7) & 0xFF;
    normalized to [0, 1] by dividing by 255.0.
    """
    bytes_ = np.array(
        [(seq * 131 + j * 17 + 7) & 0xFF for j in range(n)],
        dtype=np.float32,
    )
    return bytes_ / 255.0


def test_softmax_sums_to_one():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    p = softmax_py(x)
    assert math.isclose(float(np.sum(p)), 1.0, rel_tol=1e-6)


def test_softmax_all_zero_is_uniform():
    x = np.zeros(5, dtype=np.float32)
    p = softmax_py(x)
    assert np.allclose(p, np.full(5, 0.2), atol=1e-6)


def test_softmax_argmax_preserved():
    x = np.array([1.0, 5.0, 2.0, 3.0, 0.5], dtype=np.float32)
    p = softmax_py(x)
    assert int(np.argmax(p)) == 1


def test_softmax_negative_input_handled():
    x = np.array([-100.0, -50.0, 0.0, -25.0, -75.0], dtype=np.float32)
    p = softmax_py(x)
    # All probability concentrates on the maximum (index 2 = 0.0).
    assert int(np.argmax(p)) == 2
    assert p[2] > 0.99


def test_input_synth_normalized():
    """All synthesized bytes must land in [0, 1] after normalization."""
    for seq in range(0, 100):
        v = stc_input_synth(seq)
        assert v.shape == (64,)
        assert np.min(v) >= 0.0
        assert np.max(v) <= 1.0


def test_input_synth_distinct_per_seq():
    """Successive packets must produce different inputs."""
    a = stc_input_synth(0)
    b = stc_input_synth(1)
    assert not np.allclose(a, b)


def test_input_synth_deterministic():
    """Same seq number must produce byte-identical output."""
    assert np.array_equal(stc_input_synth(42), stc_input_synth(42))


def test_class_label_set_matches_service_json(sample_root):
    import json

    service = json.loads(
        (sample_root / "app" / "service.json").read_text()
    )
    expected = ["video", "voip", "web", "iot", "bulk"]
    assert service["metadata"]["class_labels"] == expected


@pytest.mark.parametrize(
    "logits,expected_label",
    [
        ([5.0, 0.1, 0.1, 0.1, 0.1], 0),  # video
        ([0.1, 5.0, 0.1, 0.1, 0.1], 1),  # voip
        ([0.1, 0.1, 5.0, 0.1, 0.1], 2),  # web
        ([0.1, 0.1, 0.1, 5.0, 0.1], 3),  # iot
        ([0.1, 0.1, 0.1, 0.1, 5.0], 4),  # bulk
    ],
)
def test_argmax_picks_correct_class(logits, expected_label):
    p = softmax_py(np.array(logits, dtype=np.float32))
    assert int(np.argmax(p)) == expected_label
    assert p[expected_label] > 0.95
