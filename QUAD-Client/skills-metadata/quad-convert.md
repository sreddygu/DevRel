---
name: quad-convert
description: "Walk through converting a model for Snapdragon (ONNX or PyTorch to QNN or SNPE), including calibration data and image format guidance."
---

# QUAD Model Conversion

Walk through converting a model for Snapdragon (ONNX or PyTorch to QNN or SNPE), including calibration data and image format guidance.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `quad-client`, `edge-ai`, `quad`, `convert`, `qualcomm-ai`, `mcp`, `npu`, `snapdragon-x-elite`, `qairt`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `windows`, `linux`
- **Requirements:** Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-convert/SKILL.md)

## Use Cases

- Convert my ONNX model to run on the NPU
- Quantize my PyTorch model with calibration data
- Compile this model to QNN
- What calibration images format does the converter need?
