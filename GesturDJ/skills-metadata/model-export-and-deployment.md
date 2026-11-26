---
name: model-export-and-deployment
description: "Export a trained PyTorch gesture model to a single-file ONNX model that a board without PyTorch (such as the Qualcomm Dragonwing IQ-8275 (IQ8) or Arduino VENTUNO Q) can load, prove its outputs match the original, and package and copy it to the device."
---

# Gesture Model ONNX Export and Packaging

Export a trained PyTorch gesture model to a single-file ONNX model that a board without PyTorch (such as the Qualcomm Dragonwing IQ-8275 (IQ8) or Arduino VENTUNO Q) can load, prove its outputs match the original, and package and copy it to the device.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.2.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `model`, `export`, `deployment`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/model-export-and-deployment/SKILL.md)

## Use Cases

- Export my gesture model to ONNX for the IQ8 board
- Check that the ONNX output matches the PyTorch model
- Package the model so a board without PyTorch can run it
- Copy the exported model and its preprocessing script to my device
- Why is my exported ONNX model split into several files?
- Export my gesture model for the Arduino VENTUNO Q
