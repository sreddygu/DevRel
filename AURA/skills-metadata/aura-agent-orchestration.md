---
name: aura-agent-orchestration
description: "Prepare AURA, an on-device physical-AI agent (camera, microphone, memory and local LLM) for Arduino VENTUNO Q and Qualcomm IQ8, and pick the smallest milestone to run, without starting device services by default."
---

# AURA Runtime Setup and Milestone Selection

Prepare AURA, an on-device physical-AI agent (camera, microphone, memory and local LLM) for Arduino VENTUNO Q and Qualcomm IQ8, and pick the smallest milestone to run, without starting device services by default.

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
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/aura-agent-orchestration/SKILL.md)

## Use Cases

- Set up the AURA on-device agent on my IQ8 board
- Which AURA milestone should I build first: vision, speech, memory or agent?
- Install only the AURA vision extra and run the tests
- Show my AURA configuration and what optional components are missing
