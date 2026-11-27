---
name: robot-runtime-discovery
description: "Inspect whether the QNN runtime and the Pi coding assistant are ready for RoboAgent on a Windows on Snapdragon PC, without changing the machine by default."
---

# RoboAgent Runtime Check

Inspect whether the QNN runtime and the Pi coding assistant are ready for RoboAgent on a Windows on Snapdragon PC, without changing the machine by default.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `robot`, `runtime`, `discovery`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.51; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/robot-runtime-discovery/SKILL.md)

## Use Cases

- Is my Snapdragon PC ready to run RoboAgent?
- Check the QNN runtime and Pi installation for RoboAgent
- What is missing before I can start the RoboAgent host?
- Inspect my RoboAgent environment without changing anything
