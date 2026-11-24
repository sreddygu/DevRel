---
name: device-and-host-discovery
description: "Read-only discovery of your PC and target board for GesturDJ (a gesture-controlled DJ demo): what hardware is present and where each stage (sensing, recognition, music generation) will run."
---

# GesturDJ Device and Host Discovery

Read-only discovery of your PC and target board for GesturDJ (a gesture-controlled DJ demo): what hardware is present and where each stage (sensing, recognition, music generation) will run.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `device`, `host`, `discovery`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** `suggest-install` after `get_active_device`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-and-host-discovery/SKILL.md)

## Use Cases

- Find out what hardware I have for the GesturDJ demo
- Detect my IQ8 board, its sensors and audio devices
- Where should the gesture recognizer and music model run on my setup?
- Is my host ready to run GesturDJ?
