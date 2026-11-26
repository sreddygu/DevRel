---
name: gesture-dataset-preparation
description: "Choose and prepare a labelled accelerometer (motion) dataset for gesture recognition, whether synthetic, the public uWave set or your own capture, check its quality and class balance, and split it into train and held-out sets before training."
---

# Gesture Dataset Preparation

Choose and prepare a labelled accelerometer (motion) dataset for gesture recognition, whether synthetic, the public uWave set or your own capture, check its quality and class balance, and split it into train and held-out sets before training.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.2.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `gesture`, `dataset`, `preparation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesture-dataset-preparation/SKILL.md)

## Use Cases

- Prepare a synthetic accelerometer dataset for left, right and circle gestures
- Check my gesture recordings for class imbalance, flat series and bad samples
- Split my motion data into train and held-out sets
- Which gesture dataset should I start with?
- Is my dataset good enough to train on, or do I need more samples per label?
- Download the public uWave gesture dataset after showing me its license
- Generate dataset-report.json and explain the warnings
