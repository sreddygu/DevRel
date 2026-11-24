---
name: gesture-to-live-mix-design
description: "Design how a recognized gesture changes music live (clip, tempo, volume, filter, layers) with debounce and a latency budget."
---

# Gesture-to-Music Mapping Design

Design how a recognized gesture changes music live (clip, tempo, volume, filter, layers) with debounce and a latency budget.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `gesture`, `live`, `mix`, `design`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`; target OS `qualcomm_linux` (qli-2.0)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/gesture-to-live-mix-design/SKILL.md)

## Use Cases

- Map a swipe gesture to a tempo change with debounce
- Design a mix map for five gestures and check its latency budget
- Which music controls should each gesture trigger?
- Why does my gesture trigger the wrong clip twice?
