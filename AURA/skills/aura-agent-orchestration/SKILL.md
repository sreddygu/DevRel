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
