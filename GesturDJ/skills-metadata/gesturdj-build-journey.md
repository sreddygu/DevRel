---
name: gesturdj-build-journey
description: "Guide a developer through GesturDJ, a gesture-controlled music project, from no setup to a motion-gesture recognizer that is trained, exported to ONNX and validated on the machine that will run it (a PC or a Qualcomm Dragonwing IQ-8275 (IQ8) board), with a gesture-to-music mapping designed."
---

# GesturDJ Gesture-to-Music Build Guide

Guide a developer through GesturDJ, a gesture-controlled music project, from no setup to a motion-gesture recognizer that is trained, exported to ONNX and validated on the machine that will run it (a PC or a Qualcomm Dragonwing IQ-8275 (IQ8) board), with a gesture-to-music mapping designed.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `build`, `journey`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesturdj-build-journey/SKILL.md)

## Use Cases

- Walk me through building GesturDJ from scratch
- Train, export and validate a gesture model for my board
- Which GesturDJ step should I do next, and what evidence proves the last one worked?
- Rerun the GesturDJ build steps after I changed the dataset
- Where did my GesturDJ build fail and why?
- Design a gesture-to-music mapping for left, right and circle gestures
- Check that my PC and board are ready before I start the GesturDJ build
