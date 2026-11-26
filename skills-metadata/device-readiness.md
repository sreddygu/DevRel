---
name: device-readiness
description: "Check, without changing the device, whether a publicly available Qualcomm development board is ready for a documented project workflow: reachable over SSH or USB, identified, running a supported OS image, with the required runtime and tools present."
---

# Hardware Target Readiness Check

Check, without changing the device, whether a publicly available Qualcomm development board is ready for a documented project workflow: reachable over SSH or USB, identified, running a supported OS image, with the required runtime and tools present.

## Catalog

- **Level:** Academy shared skill
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `device`, `readiness`, `validation`, `open-source`, `release`, `shared-skills`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs6490-rb3gen2-core-kit`, `qcs6490-rb3gen2-vision-kit`, `qcs6490-rb3gen2-vision-lite-kit`, `qcs6490-rubikpi3-kit`, `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; host OS `linux`, `windows`, `macos`
- **References:** [Delivery models](../skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](../docs/skills-hub-compatibility-values.md)
- **Hub triggers:** `suggest-install` after `get_active_device`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/device-readiness/SKILL.md)

## Use Cases

- Is my dev board ready to run this sample?
- Check that my IQ-9075 EVK is reachable and running a supported OS image before I deploy
- What is missing on my RB3 Gen 2 for this workflow?
- Compare my board's OS image and runtime version against the project's compatibility table
- Write a dated readiness record I can link from my validation evidence
- Validate my hardware target before I publish the demo
- Can I claim this sample works on my board, or only on my PC?
