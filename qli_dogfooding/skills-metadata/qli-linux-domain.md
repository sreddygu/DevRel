---
name: qli-linux-domain
description: "Context document that states which devices and platforms the Qualcomm Linux (QLI) skills support (IQ8, IQ9 and equivalent Linux targets) and the safety and evidence rules they follow."
---

# Qualcomm Linux Support Scope

Context document that states which devices and platforms the Qualcomm Linux (QLI) skills support (IQ8, IQ9 and equivalent Linux targets) and the safety and evidence rules they follow.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `2.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `qli`, `linux`, `domain`, `qli-linux`, `qualcomm-linux`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/qli-linux-domain/SKILL.md)

## Use Cases

- Which devices do the QLI skills support?
- What evidence counts as a completed QLI check?
- Check the support scope before I run a device workflow
- What safety rules apply to QLI device skills?
