---
name: music-model-npu-deployment
description: "Check that a Qualcomm Dragonwing IQ-8275 (IQ8) board is ready to run the ACE-Step (DiffRhythm-based) music transformer on its Hexagon NPU: Qualcomm Linux image, NPU firmware state, runtime libraries for the HTP v75 target, compiled model graphs and no stale server. Read-only by default."
---

# Music Model NPU Readiness Check (IQ8)

Check that a Qualcomm Dragonwing IQ-8275 (IQ8) board is ready to run the ACE-Step (DiffRhythm-based) music transformer on its Hexagon NPU: Qualcomm Linux image, NPU firmware state, runtime libraries for the HTP v75 target, compiled model graphs and no stale server. Read-only by default.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `music`, `model`, `npu`, `deployment`, `gesture-recognition`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **References:** [GesturDJ README](../README.md), [IQ8 SSH runbook](../ACE-Step/IQ8_SSH_RUNBOOK.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/music-model-npu-deployment/SKILL.md)

## Use Cases

- Is my IQ8 board ready to run the ACE-Step music model on its NPU?
- Check NPU firmware and runtime libraries before I deploy the music model
- Why do the NPU graphs fail to load on my board?
- Run the preflight checks for ACE-Step on the IQ8 NPU
- Check dmesg for external aborts since the last boot
- Is another music-model server still running on the NPU?
- Walk me through the six chained batches the ACE-Step model needs
