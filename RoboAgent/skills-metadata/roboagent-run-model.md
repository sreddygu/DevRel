---
name: roboagent-run-model
description: "Run an ExecuTorch .pte model built for the Qualcomm AI Engine Direct (QNN) backend on a Windows on Snapdragon PC: simple operator tests with qnn_executor_runner, or large language models such as Gemma with qnn_llama_runner."
---

# Run a QNN Model on Windows on Snapdragon

Run an ExecuTorch .pte model built for the Qualcomm AI Engine Direct (QNN) backend on a Windows on Snapdragon PC: simple operator tests with qnn_executor_runner, or large language models such as Gemma with qnn_llama_runner.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `run`, `model`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.51; no adb or cross-compile
- **References:** [RoboAgent README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/run-model/SKILL.md)

## Use Cases

- Run this .pte model on my Snapdragon PC
- Benchmark LLM tokens per second with qnn_llama_runner
- Debug a qnn_executor_runner failure
- Validate my QNN model with a simple operator test
- Run Gemma on the NPU of my Windows on Snapdragon laptop
- Why does my .pte file load but produce wrong output?
