---
name: roboagent-setup
description: "Set up the ExecuTorch and Qualcomm AI Engine Direct (QNN) backend build environment natively on a Windows on Snapdragon ARM64 PC (no cross-compile, no adb: the PC is both host and target) for RoboAgent, an ExecuTorch QNN playground."
---

# ExecuTorch QNN Build Setup on Windows on Snapdragon

Set up the ExecuTorch and Qualcomm AI Engine Direct (QNN) backend build environment natively on a Windows on Snapdragon ARM64 PC (no cross-compile, no adb: the PC is both host and target) for RoboAgent, an ExecuTorch QNN playground.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `setup`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.51; no adb or cross-compile
- **References:** [RoboAgent README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/setup/SKILL.md)

## Use Cases

- Set up the ExecuTorch QNN build environment on my Snapdragon PC
- Check prerequisites before building a QNN runner
- Prepare this device as both host and target for QNN
- What do I install before building ExecuTorch with the QNN backend on Windows?
- Verify my QAIRT 2.51 install is visible to the ExecuTorch build
- Why does the ExecuTorch QNN build fail on my ARM64 Windows PC?
