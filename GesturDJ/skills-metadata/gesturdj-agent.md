---
name: gesturdj-agent
description: "Coordinates the GesturDJ gesture-to-music skills: understands your request, picks the smallest safe path, keeps the live path within its latency budget, asks approval before consequential steps and recovers from failures."
---

# GesturDJ Assistant

Coordinates the GesturDJ gesture-to-music skills: understands your request, picks the smallest safe path, keeps the live path within its latency budget, asks approval before consequential steps and recovers from failures.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `agent`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesturdj-agent/SKILL.md)

## Use Cases

- Build a gesture-controlled DJ on my IQ8 board
- Check whether my gesture recognizer is ready for the board
- Run the GesturDJ pipeline and stop at the first failed check
- What should I do next in the GesturDJ build?
