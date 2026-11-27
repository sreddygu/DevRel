---
name: multimodal-command-validation
description: "Evaluate the responses and proposed tool calls of RoboAgent (a local Gemma 4 robot assistant running on Windows on Snapdragon) with deterministic, grounded checks."
---

# RoboAgent Response and Tool-Call Validation

Evaluate the responses and proposed tool calls of RoboAgent (a local Gemma 4 robot assistant running on Windows on Snapdragon) with deterministic, grounded checks.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `multimodal`, `command`, `validation`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.51; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/multimodal-command-validation/SKILL.md)

## Use Cases

- Check whether RoboAgent's tool call is valid and grounded
- Validate RoboAgent responses against the test cases
- Which RoboAgent answers failed the checks and why?
- Score a RoboAgent run without using another model
