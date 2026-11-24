---
name: roboagent-evaluation
description: "Evaluate response quality, latency and tool use of the local Gemma 4 model used by RoboAgent."
---

# RoboAgent Gemma 4 Evaluation

Evaluate response quality, latency and tool use of the local Gemma 4 model used by RoboAgent.

## Catalog

- **Level:** Project skill for RoboAgent
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `roboagent`, `edge-ai`, `evaluation`, `llm`, `executorch`, `qnn`, `windows-on-snapdragon`, `gemma`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`
- **Requirements:** Snapdragon X (SC8380XP) Windows on ARM device; QAIRT 2.47; no adb or cross-compile
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.pi/skills/roboagent-evaluation/SKILL.md)

## Use Cases

- Evaluate Gemma 4 response quality on my device
- Measure Gemma 4 latency and tokens per second
- Check Gemma 4 tool-use behaviour
- Compare two Gemma 4 runs
