---
name: baseline-evidence-collection
description: "Collect read-only evidence over SSH about a Qualcomm Linux (QLI) device (OS, hardware, services) as the baseline for a readiness assessment."
---

# Qualcomm Linux Device Baseline Collection

Collect read-only evidence over SSH about a Qualcomm Linux (QLI) device (OS, hardware, services) as the baseline for a readiness assessment.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `baseline`, `evidence`, `collection`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/baseline-evidence-collection/SKILL.md)

## Use Cases

- Collect baseline information from my IQ9 over SSH
- Capture the state of my device before I change anything
- Gather evidence for a readiness assessment
- What is installed on my QLI device?
