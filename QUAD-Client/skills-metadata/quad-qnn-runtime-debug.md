---
name: quad-qnn-runtime-debug
description: "Use when the user is debugging a QNN/QAIRT runtime failure on already-compiled artifacts -- \"QNN backend won't initialize\", \"unable to find a valid interface\", \"QNN_BACKEND_ERROR_CANNOT_INITIALIZE\", \"GPU_ERROR_DOES_NOT_EXIST\", \"qnn-net-run fails\", \"my .bin/.dlc won't load\", \"backend initialization failure\", or invokes /quad-qnn-runtime-debug. Diagnoses backend-init, ABI/version, symbol-resolution, and input-contract failures at the dynamic-loader level rather than trusting generic QNN error strings."
---

# Quad Qnn Runtime Debug

Use when the user is debugging a QNN/QAIRT runtime failure on already-compiled artifacts -- "QNN backend won't initialize", "unable to find a valid interface", "QNN_BACKEND_ERROR_CANNOT_INITIALIZE", "GPU_ERROR_DOES_NOT_EXIST", "qnn-net-run fails", "my .bin/.dlc won't load", "backend initialization failure", or invokes /quad-qnn-runtime-debug. Diagnoses backend-init, ABI/version, symbol-resolution, and input-contract failures at the dynamic-loader level rather than trusting generic QNN error strings.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `academy`, `quad-client`, `edge-ai`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-qnn-runtime-debug/SKILL.md)

## Use Cases

- Quad Qnn Runtime Debug
