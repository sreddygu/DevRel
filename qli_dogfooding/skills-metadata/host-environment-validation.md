---
name: host-environment-validation
description: "Verify that your PC has the tools a selected Qualcomm Linux (QLI) workflow needs, such as SSH, adb and Python, before you start."
---

# Host Tools Check for Qualcomm Linux Workflows

Verify that your PC has the tools a selected Qualcomm Linux (QLI) workflow needs, such as SSH, adb and Python, before you start.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `host`, `environment`, `validation`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/host-environment-validation/SKILL.md)

## Use Cases

- Does my PC have what I need to work with my IQ9?
- Check that SSH and adb are installed
- Verify my host before running the readiness assessment
- Which tools are missing on my host?
