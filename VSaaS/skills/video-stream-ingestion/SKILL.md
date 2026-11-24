---
name: video-stream-ingestion
description: "Validate simulated or approved camera ingestion for VSaaS (a privacy-first edge video analytics prototype) with privacy-aware evidence."
version: 0.1.0
---

# VSaaS Video Stream Ingestion

Start with simulated events, then use a camera or RTSP source only after
explicit approval and a data-retention decision.

1. From `VSaaS`, install documented dependencies only after approval and start
   the local cloud API with `./scripts/run_cloud.sh`.
2. Use `./scripts/run_edge_sim.sh` for the default non-camera end-to-end path.
   Record cloud base URL class (local or approved remote), camera identifier,
   event count, and command outcome without retaining raw payloads.
3. Before camera mode, obtain approval to open the source, confirm permitted
   retention, and supply `VSAAS_VIDEO_SOURCE` only at runtime.
4. Run `./scripts/run_edge_camera.sh` only after that approval. Do not include
   an RTSP URL or camera credential in shell history, screenshots, or evidence.
5. Stop ingestion on an unexpected source, unapproved retention path, or failed
   endpoint connection; report the observed state instead of changing networking.

This skill does not enable camera capture, upload video, or alter network
configuration by default.
