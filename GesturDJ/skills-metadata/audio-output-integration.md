---
name: audio-output-integration
description: "Find a board's audio sink and players, measure how much delay each player adds, and pick the setting a live music path should use."
---

# Board Audio Output Latency Check

Find a board's audio sink and players, measure how much delay each player adds, and pick the setting a live music path should use.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `audio`, `output`, `integration`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/audio-output-integration/SKILL.md)

## Use Cases

- Which audio player should GesturDJ use on my IQ8 board?
- Why is there a delay before sound plays on my board?
- Measure aplay, paplay and pw-play latency on this device
- Is audio output working on the board?
