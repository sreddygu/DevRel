---
name: multimodal-event-pipeline
description: "Validate how the AURA on-device agent turns camera and microphone input into events and stores them in memory, with evidence that avoids saving raw images or audio."
---

# AURA Camera and Microphone Event Validation

Validate how the AURA on-device agent turns camera and microphone input into events and stores them in memory, with evidence that avoids saving raw images or audio.

## Catalog

- **Level:** Project skill for AURA
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `aura`, `edge-ai`, `multimodal`, `event`, `pipeline`, `ai-agent`, `physical-ai`, `on-device-ai`, `iq8`, `ventuno-q`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Arduino VENTUNO Q or Qualcomm IQ8 (QCS8275); Python 3.10+; optional Genie endpoint (QAIRT 2.47) on a trusted Snapdragon host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/multimodal-event-pipeline/SKILL.md)

## Use Cases

- Check that AURA detects a person in a camera frame and records an event
- Validate speech events from the microphone without storing the audio
- Verify AURA's memory entries for the last perception run
- Produce privacy-safe evidence of my AURA perception pipeline
