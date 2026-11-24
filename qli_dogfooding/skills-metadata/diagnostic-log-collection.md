---
name: diagnostic-log-collection
description: "Collect bounded logs and diagnostics from a Qualcomm Linux (QLI) device after a failed workflow, without changing device state."
---

# Qualcomm Linux Diagnostic Log Collection

Collect bounded logs and diagnostics from a Qualcomm Linux (QLI) device after a failed workflow, without changing device state.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `diagnostic`, `log`, `collection`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/diagnostic-log-collection/SKILL.md)

## Use Cases

- Collect logs from my board after the model run failed
- Gather diagnostics I can attach to a bug report
- What does the kernel log say about the NPU?
- Capture system state after a crash
