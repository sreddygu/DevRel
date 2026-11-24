---
name: roboagent-qnn
description: "Run and troubleshoot the local Gemma 4 ExecuTorch QNN model host on Windows on Snapdragon, including context recovery."
---

# Local Gemma 4 QNN Host Operation

Run and troubleshoot the local Gemma 4 ExecuTorch QNN model host on Windows on Snapdragon, including context recovery.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `qnn`, `llm`, `executorch`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.pi/skills/roboagent-qnn/SKILL.md)

## Use Cases

- Start the local Gemma 4 QNN host
- Troubleshoot the QNN host on my Snapdragon PC
- Restart the on-device Gemma 4 server
- Recover from a QNN context error
