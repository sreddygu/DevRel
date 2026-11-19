---
name: quad-detect
description: "Use when the user asks \"what hardware do I have\", \"is this a Snapdragon\", \"do I have an NPU\", \"what's on this machine\", \"what targets are connected\", \"probe my UNO Q\", \"probe my IQ-9075\", or invokes /quad-detect. Probes the local host AND any reachable target devices -- USB-attached boards via adb, plus SSH targets configured in quad.toml -- rendering chipset, CPU/GPU/NPU, RAM, runtimes, and SDK status for each. Fully probe-driven: reads the target's own device-tree/SoC strings, never assumes a specific board."
---

# Quad Detect

Use when the user asks "what hardware do I have", "is this a Snapdragon", "do I have an NPU", "what's on this machine", "what targets are connected", "probe my UNO Q", "probe my IQ-9075", or invokes /quad-detect. Probes the local host AND any reachable target devices -- USB-attached boards via adb, plus SSH targets configured in quad.toml -- rendering chipset, CPU/GPU/NPU, RAM, runtimes, and SDK status for each. Fully probe-driven: reads the target's own device-tree/SoC strings, never assumes a specific board.

## Catalog

- **Level:** Project skill for QUAD-Client
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `academy`, `quad-client`, `edge-ai`
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../.claude/skills/quad-detect/SKILL.md)

## Use Cases

- Quad Detect
