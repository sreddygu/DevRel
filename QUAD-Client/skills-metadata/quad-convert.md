---
name: quad-convert
description: "Walk through converting a model for Snapdragon with QUAD (Qualcomm Unified AI Developer) (ONNX or PyTorch to QNN or SNPE), including quantization, calibration data and image format guidance. QNN is Qualcomm AI Engine Direct; SNPE is the Snapdragon Neural Processing Engine."
---

# Model Conversion for the Snapdragon NPU

Walk through converting a model for Snapdragon with QUAD (Qualcomm Unified AI Developer) (ONNX or PyTorch to QNN or SNPE), including quantization, calibration data and image format guidance. QNN is Qualcomm AI Engine Direct; SNPE is the Snapdragon Neural Processing Engine.

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
- **References:** [QUAD Client README](../README.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-convert/SKILL.md)

## Use Cases

- Convert my ONNX model to run on the NPU
- Quantize my PyTorch model to int8 with calibration data
- Compile this model to QNN
- What calibration image format does the converter need?
- Convert my YOLOv8 ONNX model to a QNN DLC
- My conversion failed with an unsupported operator. What now?
