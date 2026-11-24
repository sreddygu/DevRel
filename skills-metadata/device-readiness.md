---
name: device-readiness
description: "Check whether a publicly available Qualcomm development board is ready for a documented project workflow: reachable, identified, correct OS image and required tools present."
---

# Hardware Target Readiness Check

Check whether a publicly available Qualcomm development board is ready for a documented project workflow: reachable, identified, correct OS image and required tools present.

## Catalog

- **Level:** Academy shared skill
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `device`, `readiness`, `validation`, `open-source`, `release`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Hub triggers:** `suggest-install` after `get_active_device`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-readiness/SKILL.md)

## Use Cases

- Is my dev board ready to run this sample?
- Check that my board is reachable and running a supported OS image before I deploy
- What is missing on my device for this workflow?
- Validate my hardware target before I publish the demo
