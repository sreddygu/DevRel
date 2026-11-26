---
name: aura-agent-orchestration
description: "Set up AURA (Autonomous Understanding and Responsive Agents), a privacy-first on-device AI agent that sees, listens, remembers and acts, on an Arduino VENTUNO Q or a Qualcomm Dragonwing IQ-8275 (IQ8) board, and choose the smallest milestone (vision, speech, memory or agent) to build first. Does not start device services or touch hardware unless you approve."
---

# AURA On-Device Agent Setup

Set up AURA (Autonomous Understanding and Responsive Agents), a privacy-first on-device AI agent that sees, listens, remembers and acts, on an Arduino VENTUNO Q or a Qualcomm Dragonwing IQ-8275 (IQ8) board, and choose the smallest milestone (vision, speech, memory or agent) to build first. Does not start device services or touch hardware unless you approve.

## Catalog

- **Level:** Project skill for AURA
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `aura`, `edge-ai`, `agent`, `orchestration`, `ai-agent`, `physical-ai`, `on-device-ai`, `iq8`, `ventuno-q`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Arduino VENTUNO Q or Qualcomm IQ8 (QCS8275); Python 3.10+; optional Genie endpoint (QAIRT 2.47) on a trusted Snapdragon host
- **References:** [AURA README](../README.md), [IQ8 deployment](../docs/IQ8_DEPLOYMENT.md), [NPU setup](../docs/NPU_SETUP.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/aura-agent-orchestration/SKILL.md)

## Use Cases

- Set up the AURA on-device agent on my IQ8 board
- Which AURA milestone should I build first: vision, speech, memory or agent?
- Install only the AURA vision extra and run the tests
- Show my AURA configuration and tell me which optional components are missing
- Should AURA reason on the board, on my PC, or in hybrid mode with a trusted host?
- Prepare AURA for my Arduino VENTUNO Q without opening the camera or microphone
- Record which AURA settings I observed on the device and which are still unknown
