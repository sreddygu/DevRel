"""Smoke tests -- imports, scaffold structure, ONNX validity."""

from __future__ import annotations

from pathlib import Path

import onnx


def test_build_model_imports():
    import build_model  # noqa: F401


def test_generate_imports():
    import generate  # noqa: F401


def test_onnx_is_valid(onnx_path: Path):
    model = onnx.load(str(onnx_path))
    onnx.checker.check_model(model)


def test_onnx_has_expected_io_shape(onnx_path: Path):
    model = onnx.load(str(onnx_path))
    inputs = list(model.graph.input)
    outputs = list(model.graph.output)
    assert len(inputs) == 1, "STC model must have a single input tensor"
    assert len(outputs) == 1, "STC model must have a single output tensor"

    in_dims = [d.dim_value for d in inputs[0].type.tensor_type.shape.dim]
    out_dims = [d.dim_value for d in outputs[0].type.tensor_type.shape.dim]
    assert in_dims == [1, 1, 64], f"input shape mismatch: {in_dims}"
    assert out_dims == [1, 5], f"output shape mismatch: {out_dims}"


def test_app_scaffold_files_exist(app_dir: Path):
    expected = {
        "main.c",
        "tensor_io.c",
        "turnkey.c",
        "turnkey.h",
        "model_inferencing.c",
        "model_inferencing.h",
        "debugging.c",
        "debugging.h",
        "cloud_services.c",
        "cloud_services.h",
        "CMakeLists.txt",
        "service.json",
        "ipk_control",
        "Dockerfile",
        "oci_config.json",
        "build_containers.sh",
        "README.md",
    }
    actual = {p.name for p in app_dir.iterdir()}
    missing = expected - actual
    assert not missing, f"scaffold is missing files: {missing}"


def test_service_json_has_stc_license(app_dir: Path):
    import json

    service = json.loads((app_dir / "service.json").read_text())
    assert service["name"] == "stc_classifier"
    assert "smart_traffic_classifier" in service["license_features"]
    labels = service.get("metadata", {}).get("class_labels", [])
    assert labels == ["video", "voip", "web", "iot", "bulk"]


def test_tensor_io_uses_stc_class_names(app_dir: Path):
    """tensor_io.c must define the 5 STC class labels in order."""
    src = (app_dir / "tensor_io.c").read_text()
    for cls in ("video", "voip", "web", "iot", "bulk"):
        assert f'"{cls}"' in src, f"tensor_io.c missing class name '{cls}'"


def test_turnkey_writes_to_syslog(app_dir: Path):
    """turnkey.c must use openlog/syslog/closelog -- not stderr."""
    src = (app_dir / "turnkey.c").read_text()
    assert "openlog(" in src
    assert "syslog(" in src
    assert "closelog(" in src
