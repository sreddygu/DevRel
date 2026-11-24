---
name: evidence-and-compatibility
description: "Record reproducible validation evidence for a project workflow and document which devices, operating systems and SDK versions are supported or excluded, so public claims match what was actually tested."
---

# Validation Evidence and Compatibility Notes

Record reproducible validation evidence for a project workflow and document which devices, operating systems and SDK versions are supported or excluded, so public claims match what was actually tested.

## Catalog

- **Level:** Academy shared skill
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `validation`, `compatibility`, `evidence`, `open-source`, `release`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/evidence-and-compatibility/SKILL.md)

## Use Cases

- Write up what I validated on my board and which environments are not covered
- Can I claim my demo works on IQ-9075? Check the evidence first
- Create a compatibility table for my release
- Decide whether this workflow has enough evidence to be promoted from preview to stable
