---
name: on-device-action-validation
description: "Check the AURA agent's action policy and safety limits before it is allowed to perform an approved action on a device."
---

# AURA Device Action Safety Check

Check the AURA agent's action policy and safety limits before it is allowed to perform an approved action on a device.

## Catalog

- **Level:** Project skill for AURA
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `aura`, `edge-ai`, `device`, `action`, `validation`, `ai-agent`, `physical-ai`, `on-device-ai`, `iq8`, `ventuno-q`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Arduino VENTUNO Q or Qualcomm IQ8 (QCS8275); Python 3.10+; optional Genie endpoint (QAIRT 2.47) on a trusted Snapdragon host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/on-device-action-validation/SKILL.md)

## Use Cases

- Verify AURA cannot take an action outside its allowed list
- Test the safety limits before I let AURA control a device
- Dry-run an AURA action and show which policy approves it
- Which AURA actions need my explicit approval?
