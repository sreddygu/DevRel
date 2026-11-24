---
name: client-inference-validation
description: "Validate a model inference workflow run through the QUAD client (Qualcomm AI MCP server client) and keep evidence that separates local simulation from execution observed on a device."
---

# QUAD Inference Validation

Validate a model inference workflow run through the QUAD client (Qualcomm AI MCP server client) and keep evidence that separates local simulation from execution observed on a device.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `client`, `inference`, `validation`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/client-inference-validation/SKILL.md)

## Use Cases

- Run an inference validation for my model with QUAD and keep the evidence
- Measure NPU latency for this model on my Snapdragon X Elite PC
- Was this result simulated or measured on the device?
- Benchmark CPU versus NPU with the QUAD sample
