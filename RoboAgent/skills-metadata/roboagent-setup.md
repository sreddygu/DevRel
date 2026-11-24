---
name: roboagent-setup
description: "Set up the ExecuTorch and QNN backend build environment natively on Windows on Snapdragon ARM64 (no cross-compile, no adb: the device is both host and target)."
---

# ExecuTorch QNN Build Setup on Windows on Snapdragon

Set up the ExecuTorch and QNN backend build environment natively on Windows on Snapdragon ARM64 (no cross-compile, no adb: the device is both host and target).

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `setup`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/setup/SKILL.md)

## Use Cases

- Set up the ExecuTorch QNN build environment on my Snapdragon PC
- Check prerequisites before building a QNN runner
- Prepare this device as both host and target for QNN
- What do I install before building ExecuTorch with the QNN backend?
