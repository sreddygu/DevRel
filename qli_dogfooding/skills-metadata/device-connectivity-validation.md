---
name: device-connectivity-validation
description: "Check TCP reachability of a Qualcomm Linux (QLI) device at a host and port you supply, without changing network configuration."
---

# Qualcomm Linux Device Connectivity Check

Check TCP reachability of a Qualcomm Linux (QLI) device at a host and port you supply, without changing network configuration.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `2.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `device`, `connectivity`, `validation`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** `suggest-install` after `validate_ssh_connection`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-connectivity-validation/SKILL.md)

## Use Cases

- Can I reach my board over SSH?
- Check that port 22 is open on 192.168.1.50
- Why can't my PC connect to my IQ9?
- Validate network access to my device before I deploy
