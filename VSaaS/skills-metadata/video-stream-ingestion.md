---
name: video-stream-ingestion
description: "Validate simulated or approved camera ingestion for VSaaS (a privacy-first edge video analytics prototype) with privacy-aware evidence."
---

# Video Stream Ingestion Check

Validate simulated or approved camera ingestion for VSaaS (a privacy-first edge video analytics prototype) with privacy-aware evidence.

## Catalog

- **Level:** Project skill for VSaaS
- **Owner:** `sreddygu`
- **Category:** `hardware`
- **Version:** `0.1.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `vsaas`, `edge-ai`, `video`, `stream`, `ingestion`, `video-analytics`, `computer-vision`, `yolov8`, `iq8`
- **License:** `Apache-2.0`
- **Compatibility:** devkits `qcs8275-iq-8275-evk-pro`
- **Requirements:** Python 3.12 and Linux (Ubuntu 24.04); ONNX Runtime or QNN YOLOv8 DLC for real perception
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/video-stream-ingestion/SKILL.md)

## Use Cases

- Check that the simulated camera stream is ingested correctly
- Validate my approved RTSP camera with VSaaS
- Confirm only metadata leaves the edge device
- Run the ingestion test on my IQ8
