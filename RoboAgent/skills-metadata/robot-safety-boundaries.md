---
name: robot-safety-boundaries
description: "Context rules for RoboAgent: read-only first, and interactive approval before any action that changes state."
---

# RoboAgent Safety Rules

Context rules for RoboAgent: read-only first, and interactive approval before any action that changes state.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `robot`, `safety`, `boundaries`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/robot-safety-boundaries/SKILL.md)

## Use Cases

- Apply the read-only-first policy to this RoboAgent request
- Ask for my approval before an action changes anything
- Check a RoboAgent command against its safety rules
- Which RoboAgent actions need approval?
