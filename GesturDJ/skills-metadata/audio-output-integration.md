---
name: audio-output-integration
description: "Find a board's audio output device and available players (aplay, paplay, pw-play), measure how much delay each one adds, and pick the setting a live music path should use, for example on a Qualcomm Dragonwing IQ-8275 (IQ8) board."
---

# Board Audio Output Latency Check

Find a board's audio output device and available players (aplay, paplay, pw-play), measure how much delay each one adds, and pick the setting a live music path should use, for example on a Qualcomm Dragonwing IQ-8275 (IQ8) board.

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
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/audio-output-integration/SKILL.md)

## Use Cases

- Which audio player should GesturDJ use on my IQ8 board?
- Why is there a delay before sound plays on my board?
- Measure aplay, paplay and pw-play latency on this device
- Is audio output working on the board?
- List the audio sinks my board exposes and which one is the default
- Pick the lowest-latency way to play generated music on my device
