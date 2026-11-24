---
name: developer-readiness-assessment
description: "Assess whether a Qualcomm Linux (QLI) board is ready for development across device lifecycle, connectivity, media, storage, AI, debugging and deployment, and produce a workbook and report."
---

# Qualcomm Linux Developer Readiness Assessment

Assess whether a Qualcomm Linux (QLI) board is ready for development across device lifecycle, connectivity, media, storage, AI, debugging and deployment, and produce a workbook and report.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `developer`, `readiness`, `assessment`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/developer-readiness-assessment/SKILL.md)

## Use Cases

- Assess whether my IQ8 is ready for development
- Run a full readiness assessment on my IQ9 board
- Rerun only the connectivity checks
- Compare two readiness runs and produce a report
