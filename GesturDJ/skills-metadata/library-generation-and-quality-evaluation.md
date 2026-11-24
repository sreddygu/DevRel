---
name: library-generation-and-quality-evaluation
description: "Generate music clips in the background from style prompts with an on-device music model, then check each clip and the whole set with objective measurements such as loop seams."
---

# Background Music Clip Generation and Quality Check

Generate music clips in the background from style prompts with an on-device music model, then check each clip and the whole set with objective measurements such as loop seams.

## Catalog

- **Level:** Project skill for GesturDJ
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `gesturdj`, `edge-ai`, `library`, `generation`, `quality`, `evaluation`, `gesture-recognition`, `music`, `npu`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Requirements:** Python 3.10+; PC and Qualcomm IQ8 board (Qualcomm Linux 2.0); QAIRT for the NPU music path
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/library-generation-and-quality-evaluation/SKILL.md)

## Use Cases

- Generate a few instrumental clips from style prompts for my DJ library
- Check whether my generated clips loop cleanly
- Evaluate the quality of a generated clip set
- Generate clips in the background without affecting the live path
