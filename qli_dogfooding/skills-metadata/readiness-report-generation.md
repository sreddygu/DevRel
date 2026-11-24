---
name: readiness-report-generation
description: "Generate a matching readiness summary, workbook and report for a Qualcomm Linux (QLI) device from verified evidence."
---

# Qualcomm Linux Readiness Report Generation

Generate a matching readiness summary, workbook and report for a Qualcomm Linux (QLI) device from verified evidence.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `2.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `readiness`, `report`, `generation`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/readiness-report-generation/SKILL.md)

## Use Cases

- Create the readiness report for my IQ8
- Generate the workbook from the evidence I collected
- Produce a summary I can share with my team
- Update the report after I re-ran the checks
