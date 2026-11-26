---
name: device-readiness
description: Establish whether a publicly obtainable hardware target is ready for a project’s documented workflow without changing device state. Use before installing a runtime, deploying a model, recording sensors, or claiming device support.
version: 1.0.0
---

# Device Readiness

1. Confirm that the developer owns or controls the device and has a public
   setup path. Record device model, OS/image version, host connection method,
   runtime version, and available storage.
2. Run only read-only discovery and project-documented smoke checks by default.
3. Compare the observed environment with the project compatibility declaration.
   Name mismatches and unsupported targets; do not silently substitute another
   device’s result.
4. Require explicit approval before device package installation, model copying,
   camera or microphone access, sensor recording, flashing, or network changes.
5. Write a dated, redacted readiness record and link it from validation evidence.

On a failed check, stop and report the failed condition and recovery path. Never
claim device support solely because a host-side workflow completed.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Dragonwing RB3 Gen 2 Core Kit (`qcs6490-rb3gen2-core-kit`), Dragonwing RB3 Gen 2 Vision Kit (`qcs6490-rb3gen2-vision-kit`), Dragonwing RB3 Gen 2 Lite Vision Kit (`qcs6490-rb3gen2-vision-lite-kit`), RUBIK Pi 3 Development Board (`qcs6490-rubikpi3-kit`), Dragonwing IQ-8275 EVK (`qcs8275-iq-8275-evk-pro`), Dragonwing IQ-9075 EVK (`qcs9075-iq-9075-evk`) |
| Target OS | No target OS constraint declared |
| Host OS | Linux (or WSL), Windows, macOS |

References: [Delivery models](https://github.com/sreddygu/DevRel/blob/main/skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](https://github.com/sreddygu/DevRel/blob/main/docs/skills-hub-compatibility-values.md).

## Example prompts

- Is my dev board ready to run this sample?
- Check that my IQ-9075 EVK is reachable and running a supported OS image before I deploy
- What is missing on my RB3 Gen 2 for this workflow?
- Compare my board's OS image and runtime version against the project's compatibility table
- Write a dated readiness record I can link from my validation evidence
- Validate my hardware target before I publish the demo
- Can I claim this sample works on my board, or only on my PC?

<!-- skills-hub:end -->
