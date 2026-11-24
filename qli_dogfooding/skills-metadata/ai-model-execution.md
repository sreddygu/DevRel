---
name: ai-model-execution
description: "Run a model command discovered on a Qualcomm Linux (QLI) device against a supplied image and capture the parsed result."
---

# Qualcomm Linux AI Model Run

Run a model command discovered on a Qualcomm Linux (QLI) device against a supplied image and capture the parsed result.

## Catalog

- **Level:** Project skill for qli_dogfooding
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `edge-ai`, `model`, `execution`, `qli-linux`, `qualcomm-linux`, `qli`, `iq8`, `iq9`, `readiness`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`, `qcs9075-iq-9075-evk`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Qualcomm Linux 2.0 on IQ8 or IQ9; SSH access; Python 3.10+ on the host
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/ai-model-execution/SKILL.md)

## Use Cases

- Run image classification on my IQ8 with this picture
- Execute the sample model on my board and save the output
- Does the AI runtime on my device produce a valid result?
- Parse the model output from my last run
