---
name: gesture-event-contract
description: "The single event format that every gesture sensor (accelerometer or camera pose) must emit so that the recognizer, mixer and music path work with either."
---

# Gesture Event Format

The single event format that every gesture sensor (accelerometer or camera pose) must emit so that the recognizer, mixer and music path work with either.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `gesture`, `event`, `contract`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesture-event-contract/SKILL.md)

## Use Cases

- Define the event my gesture sensor must emit
- Add a camera gesture source without changing the mixer
- Check a gesture event against the GesturDJ event format
- What fields does a gesture event need?
