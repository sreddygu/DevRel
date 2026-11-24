---
name: live-mixer-and-latency-validation
description: "Replay many gestures through the recognizer, mix map and audio player and check the estimated gesture-to-sound delay against a 200 ms budget."
---

# Live Mixer Latency Validation

Replay many gestures through the recognizer, mix map and audio player and check the estimated gesture-to-sound delay against a 200 ms budget.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `live`, `mixer`, `latency`, `validation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/live-mixer-and-latency-validation/SKILL.md)

## Use Cases

- Does my gesture-to-sound latency stay within 200 ms?
- Replay 100 gestures and report p50 and p95 latency
- Compare spawning a player per gesture with a warm output stream
- Find which stage of the live path uses the most latency
