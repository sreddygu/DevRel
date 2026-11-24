---
name: qli-readiness-agent
description: "Coordinates the Qualcomm Linux (QLI) readiness skills: picks approved skills, explains the plan, asks approval before consequential steps, validates results and recovers from failures."
---

# Qualcomm Linux Readiness Assistant

Coordinates the Qualcomm Linux (QLI) readiness skills: picks approved skills, explains the plan, asks approval before consequential steps, validates results and recovers from failures.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `qli`, `readiness`, `agent`, `qli-linux`, `qualcomm-linux`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/qli-readiness-agent/SKILL.md)

## Use Cases

- Check whether my QLI device is ready for development
- Plan a readiness run and let me approve each step
- Recover from a failed readiness check
- Run the smallest set of checks to confirm my board works
