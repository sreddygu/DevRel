---
name: vision-model-validation
description: "Validate an ONNX or QNN object detector (for example YOLOv8) used by VSaaS and record results labelled by backend and target."
---

# Edge Vision Model Validation

Validate an ONNX or QNN object detector (for example YOLOv8) used by VSaaS and record results labelled by backend and target.

## Catalog

- **Level:** Project skill for VSaaS
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `vsaas`, `edge-ai`, `vision`, `model`, `validation`, `video-analytics`, `computer-vision`, `yolov8`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`
- **Requirements:** Python 3.12 and Linux (Ubuntu 24.04); ONNX Runtime or QNN YOLOv8 DLC for real perception
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/vision-model-validation/SKILL.md)

## Use Cases

- Validate my YOLOv8 ONNX detector
- Run the QNN YOLOv8 DLC on my IQ8 and record the result
- Compare ONNX CPU and QNN results on the same video
- Which backend and target produced this detection result?
