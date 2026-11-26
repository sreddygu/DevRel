---
name: gesture-model-training-and-evaluation
description: "Train a motion-gesture classifier (scikit-learn baseline or PyTorch), read the held-out result honestly, spot overfitting or an unrealistically easy dataset, and decide whether the model is good enough to export."
---

# Gesture Model Training and Evaluation

Train a motion-gesture classifier (scikit-learn baseline or PyTorch), read the held-out result honestly, spot overfitting or an unrealistically easy dataset, and decide whether the model is good enough to export.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.2.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `gesture`, `model`, `training`, `evaluation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesture-model-training-and-evaluation/SKILL.md)

## Use Cases

- Train a gesture classifier on my accelerometer data
- Is my model's held-out accuracy good enough or is it overfitting?
- Compare the scikit-learn baseline with a PyTorch model on the same split
- Show the confusion matrix for my gesture model
- My accuracy is 100%. Is that real or is my dataset too easy?
- Decide whether this model is ready to export to ONNX
