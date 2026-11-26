---
name: on-device-gesture-validation
description: "On the machine that will run the gesture recognizer (for example a Qualcomm Dragonwing IQ-8275 (IQ8) board), check that the exported ONNX model matches the original, keeps its accuracy on held-out data and runs fast enough, and record the result."
---

# On-Device Gesture Model Validation

On the machine that will run the gesture recognizer (for example a Qualcomm Dragonwing IQ-8275 (IQ8) board), check that the exported ONNX model matches the original, keeps its accuracy on held-out data and runs fast enough, and record the result.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.2.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `device`, `gesture`, `validation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/on-device-gesture-validation/SKILL.md)

## Use Cases

- Validate my exported gesture model on the IQ8 board
- Measure inference latency of the gesture model on the device
- Does the on-device model give the same predictions as on my PC?
- Run the held-out accuracy check on the board
- Is my gesture model fast enough for live use?
- Write the on-device validation record for my gesture model
