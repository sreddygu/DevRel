"""Unit tests for the pure-function pieces of inference.py and run_iq9075.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def test_softmax_sums_to_one():
    import inference  # type: ignore[import-not-found]

    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    p = inference.softmax(x)
    assert pytest.approx(p.sum(), abs=1e-6) == 1.0
    assert (p >= 0).all()


def test_softmax_handles_large_values():
    import inference  # type: ignore[import-not-found]

    x = np.array([1000.0, 1001.0, 1002.0], dtype=np.float32)
    p = inference.softmax(x)
    assert np.isfinite(p).all()
    assert pytest.approx(p.sum(), abs=1e-6) == 1.0


def test_topk_returns_descending_order():
    import inference  # type: ignore[import-not-found]

    logits = np.array([0.1, 5.0, 2.0, 9.0, 1.0], dtype=np.float32)
    out = inference.topk(logits, k=3)
    assert len(out) == 3
    assert [i for i, _ in out] == [3, 1, 2]
    probs = [p for _, p in out]
    assert probs == sorted(probs, reverse=True)


def test_topk_clamps_to_length():
    import inference  # type: ignore[import-not-found]

    logits = np.array([0.5, 1.0], dtype=np.float32)
    out = inference.topk(logits, k=10)
    assert len(out) == 2


def test_percentile_basic():
    import inference  # type: ignore[import-not-found]

    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert inference.percentile(values, 50) == 30.0
    assert inference.percentile(values, 0) == 10.0
    assert inference.percentile(values, 100) == 50.0


def test_percentile_empty():
    import inference  # type: ignore[import-not-found]

    assert inference.percentile([], 50) == 0.0


def test_load_input_random_when_none():
    import inference  # type: ignore[import-not-found]

    arr = inference.load_input(None)
    assert arr.shape == (1, 3, 224, 224)
    assert arr.dtype == np.float32


def test_load_input_from_npy(tmp_path: Path):
    import inference  # type: ignore[import-not-found]

    npy = tmp_path / "in.npy"
    expected = np.zeros((1, 3, 224, 224), dtype=np.float32)
    np.save(npy, expected)
    loaded = inference.load_input(str(npy))
    assert loaded.shape == expected.shape
    assert loaded.dtype == np.float32


def test_load_input_rejects_wrong_shape(tmp_path: Path):
    import inference  # type: ignore[import-not-found]

    npy = tmp_path / "bad.npy"
    np.save(npy, np.zeros((1, 224, 224, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="input shape"):
        inference.load_input(str(npy))


def test_load_labels_returns_lines(tmp_path: Path):
    import inference  # type: ignore[import-not-found]

    p = tmp_path / "labels.txt"
    p.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    labels = inference.load_labels(str(p))
    assert labels == ["alpha", "beta", "gamma"]


def test_load_labels_returns_empty_when_missing(tmp_path: Path):
    import inference  # type: ignore[import-not-found]

    assert inference.load_labels(None) == []
    assert inference.load_labels(str(tmp_path / "nope.txt")) == []


def test_attempt_qnn_reports_reason_when_ep_missing(monkeypatch):
    """The core "honest degradation" behavior: if onnxruntime_qnn isn't
    installed at all, attempt_qnn must return ok=False with a specific,
    actionable error -- never raise, never silently claim success."""
    import inference  # type: ignore[import-not-found]

    result = inference.attempt_qnn("does-not-matter.onnx", np.zeros((1, 3, 224, 224), dtype=np.float32), "htp", iterations=1, warmup=0)
    assert result["ok"] is False
    assert result["backend"] == "htp"
    assert "error" in result


def test_preprocess_image_produces_nchw(fixture_image: Path, tmp_path: Path):
    import run_iq9075  # type: ignore[import-not-found]

    npy_out = tmp_path / "in.npy"
    shape, dtype = run_iq9075.preprocess_image(fixture_image, npy_out)
    assert shape == (1, 3, 224, 224)
    assert dtype == np.float32
    assert npy_out.exists()
    arr = np.load(npy_out)
    assert arr.shape == (1, 3, 224, 224)
    # ImageNet normalized values are typically in roughly [-3, 3]
    assert -10.0 < float(arr.min()) < 0.0
    assert 0.0 < float(arr.max()) < 10.0


def test_extract_json_from_mixed_output():
    import run_iq9075  # type: ignore[import-not-found]

    text = (
        "[W:onnxruntime] some warning line\n"
        '{"avg_ms": 65.6, "p50_ms": 65.6}\n'
        "trailing noise"
    )
    out = run_iq9075._extract_json(text)
    assert out is not None
    assert "avg_ms" in out


def test_extract_json_picks_last_block():
    import run_iq9075  # type: ignore[import-not-found]

    text = '{"a": 1} noise {"b": 2, "nested": {"x": 3}}'
    out = run_iq9075._extract_json(text)
    assert out == '{"b": 2, "nested": {"x": 3}}'


def test_extract_json_returns_none_when_absent():
    import run_iq9075  # type: ignore[import-not-found]

    assert run_iq9075._extract_json("no json here") is None


def test_list_devices_parses_serials(monkeypatch):
    import run_iq9075  # type: ignore[import-not-found]

    class _FakeProc:
        def __init__(self, stdout):
            self.stdout, self.stderr, self.returncode = stdout, "", 0

    def fake_run(cmd, *a, **kw):
        return _FakeProc("List of devices attached\nbdcd1f51\tdevice\nemu-5554\tdevice\n")

    monkeypatch.setattr(run_iq9075.subprocess, "run", fake_run)
    assert run_iq9075.list_devices("adb") == ["bdcd1f51", "emu-5554"]


def test_resolve_serial_requires_single_device(monkeypatch):
    import run_iq9075  # type: ignore[import-not-found]

    monkeypatch.setattr(run_iq9075, "list_devices", lambda _adb: [])
    with pytest.raises(run_iq9075.BoardError, match="No adb devices"):
        run_iq9075.resolve_serial("adb", "auto")


def test_resolve_serial_passthrough_when_explicit():
    import run_iq9075  # type: ignore[import-not-found]

    assert run_iq9075.resolve_serial("adb", "bdcd1f51") == "bdcd1f51"
