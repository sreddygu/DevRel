---
name: aura-agent-orchestration
description: "Prepare AURA, an on-device physical-AI agent (camera, microphone, memory and local LLM) for Arduino VENTUNO Q and Qualcomm IQ8, and pick the smallest milestone to run, without starting device services by default."
version: 0.1.0
---

# AURA Agent Orchestration

Prepare the AURA runtime and select the smallest required milestone without
starting device services or changing hardware state by default.

1. Work from `AURA` with Python 3.10 or later.
2. Install the base and development dependencies only after approval:
   `python -m pip install -e ".[dev]"`.
3. Run `pytest -q` and `aura config`; record versions, selected configuration,
   failures, and unavailable optional components.
4. Add only the required milestone extra (`vision`, `speech`, `memory`,
   `agent`, or `dashboard`) after approval.
5. Record the selected reasoning mode and whether it is host-local, target-local,
   or trusted-host hybrid. Mark any unobserved target facts as `unknown`.

Starting a server, opening a sensor, connecting to a device, or installing
optional components is outside the non-destructive default and requires explicit
approval.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Dragonwing IQ-8275 EVK (`qcs8275-iq-8275-evk-pro`) |
| Target OS | Qualcomm Linux (`qli-2.0`, `qualcomm-linux-proprietary`) |
| Host OS | Any |
| Requirements | Arduino VENTUNO Q or Qualcomm IQ8 (QCS8275); Python 3.10+; optional Genie endpoint (QAIRT 2.47) on a trusted Snapdragon host |

References: [AURA README](https://github.com/sreddygu/DevRel/blob/main/AURA/README.md), [IQ8 deployment](https://github.com/sreddygu/DevRel/blob/main/AURA/docs/IQ8_DEPLOYMENT.md), [NPU setup](https://github.com/sreddygu/DevRel/blob/main/AURA/docs/NPU_SETUP.md).

## Example prompts

- Set up the AURA on-device agent on my IQ8 board
- Which AURA milestone should I build first: vision, speech, memory or agent?
- Install only the AURA vision extra and run the tests
- Show my AURA configuration and tell me which optional components are missing
- Should AURA reason on the board, on my PC, or in hybrid mode with a trusted host?
- Prepare AURA for my Arduino VENTUNO Q without opening the camera or microphone
- Record which AURA settings I observed on the device and which are still unknown

<!-- skills-hub:end -->
