---
name: gesture-model-training-and-evaluation
description: "Train a gesture recognizer (scikit-learn baseline or PyTorch), read the held-out result honestly and decide whether it is good enough to export."
---

# Gesture Model Training and Evaluation

Train a gesture recognizer (scikit-learn baseline or PyTorch), read the held-out result honestly and decide whether it is good enough to export.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.2.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `gesture`, `model`, `training`, `evaluation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesture-model-training-and-evaluation/SKILL.md)

## Use Cases

- Train a gesture classifier on my accelerometer data
- Is my model's held-out accuracy good enough or just overfitting?
- Compare the scikit-learn baseline with a PyTorch model
- Show the confusion matrix for my gesture model
