---
name: video-evidence-reporting
description: "Create reviewable, redacted reports from video analytics event records (metadata only, no raw video), and label every claim as simulated, host-observed or target-observed."
---

# Video Event Evidence Report

Create reviewable, redacted reports from video analytics event records (metadata only, no raw video), and label every claim as simulated, host-observed or target-observed.

## Catalog

- **Level:** Project skill for VSaaS
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `vsaas`, `edge-ai`, `video`, `evidence`, `reporting`, `video-analytics`, `computer-vision`, `yolov8`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** portable (no hardware constraint declared)
- **Requirements:** Python 3.12 and Linux (Ubuntu 24.04); ONNX Runtime or QNN YOLOv8 DLC for real perception
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/video-evidence-reporting/SKILL.md)

## Use Cases

- Generate an evidence report from my detection events
- Redact personal data in the event export
- Show where each event came from and how it was produced
- Create a report I can share without raw video
