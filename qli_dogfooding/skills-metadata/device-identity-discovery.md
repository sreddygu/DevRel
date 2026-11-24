---
name: device-identity-discovery
description: "Identify a connected Qualcomm Linux (QLI) device (board, SoC, image and OS version) before choosing device-specific work."
---

# Qualcomm Linux Device Identification

Identify a connected Qualcomm Linux (QLI) device (board, SoC, image and OS version) before choosing device-specific work.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `device`, `identity`, `discovery`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** `suggest-install` after `get_active_device`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-identity-discovery/SKILL.md)

## Use Cases

- Identify the board I just connected
- Which SoC and image is my device running?
- Is this an IQ8 or an IQ9?
- Confirm the device matches what I asked for before I continue
