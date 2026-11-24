---
name: roboagent-run-model
description: "Run a QNN .pte model on a Windows on Snapdragon device: simple operator tests with qnn_executor_runner, or LLMs with qnn_llama_runner."
---

# Run a QNN Model on Windows on Snapdragon

Run a QNN .pte model on a Windows on Snapdragon device: simple operator tests with qnn_executor_runner, or LLMs with qnn_llama_runner.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `run`, `model`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/run-model/SKILL.md)

## Use Cases

- Run this .pte model on my Snapdragon PC
- Benchmark LLM tokens per second with qnn_llama_runner
- Debug a qnn_executor_runner failure
- Validate my QNN model with a simple op test
