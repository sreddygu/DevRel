# VSaaS Technical Report

> This document summarizes the VSaaS functional prototype implementation.

## Section 1: Problem Overview
- Enterprise video systems flood the cloud with raw frames, which spikes
  bandwidth/storage and exposes private footage.
- VSaaS aims to keep processing at the edge (IQ8 EVK) and ship only
  metadata + approved clip identifiers to the cloud for search/query.
- The design emphasizes a policy-driven, privacy-safe edge-to-cloud workflow
  plus natural-language query over events.

## Section 2: Architecture Recap
- Edge agent (simulator) emitted structured events (person/object/zone).
- Cloud API (FastAPI + SQLite) stored events and exposed `/events` + `/query`.
- Optional LLM summarization via an OpenAI-compatible Hydra endpoint.
- Balanced the need for real-time alerts (edge) with storytelling/search (cloud).

## Section 3: Implementation Environment
- Ubuntu 24.04.4 LTS on Qualcomm IQ8 (aarch64), kernel 6.8.0-1071-qcom.
- Python 3.12 virtual environment (`.venv`) with FastAPI, ONNX Runtime,
  imageio, and an OpenAI-compatible LLM client (Hydra/AIC100).
- Repository layout ensures scripts, docs, and collaterals stay together for
  submission.

## Section 4: Data Flow & Interfaces
- Edge captures camera frames (USB `/dev/videoX` or CSI `qmmf://video_0`)
  and optionally runs ONNX YOLOv8 + PPE pantry check.
- Each emit includes `camera_id`, `event_type`, `payload` (frame/clip paths,
  detection summary, zone metadata).
- Cloud inserts batches into SQLite, then `/query` reads the most recent events
  and optionally calls the Hydra LLM for summarization.
- `scripts/run_query.sh` shows how operators can list events or request summaries.

## Section 5: Implementation Highlights
- Edge camera mode now generates **real CSI/USB clips** and writes them to
  `data/recordings/`; metadata-only events reference the clip path.
- `scripts/run_edge_camera.sh` auto-activates the venv and respects
  `VSAAS_RECORD_ON_EVENT`, `VSAAS_CLIP_SECONDS`, and `VSAAS_EMIT_INTERVAL_SEC`.
- Introduced `scripts/replay_events.py` to repopulate the cloud store from
  `data/events.db` so the submission can include consistent event logs.
- Cloud API now documents Hydra-friendly env vars + error handling when
  SparQ rejects requests (e.g., 403 for missing QAIC/APIGEE tokens).

## Section 6: Testing & Performance (Updated)
- Benchmarked metadata capture: ~230 ms total latency per clip (2s duration)
  and ~4.5 events/sec per Cloud API instance (see `benchmarks/benchmark_log.json`).
- Query summarization rounds trip in ~120 ms; when Hydra returns 403, Cloud
  provides fallback counts (`llm_used=false`).
- `collaterals/video_demo.mp4` and the phase-2 slides (`collaterals/deck.pptx`)
  document the live flow; recorded logs live under `logs/cloud_e2e_csi.log` +
  `logs/edge_e2e_csi.log`.
- Replay script ensures `/events` always exposes data for `/query` during demos.

## Section 7: Deployment & Operational Notes (Updated)
- Hydra/AIC100 integration uses `VSAAS_LLM_BASE_URL` and `VSAAS_LLM_MODEL`
  (`qwen3_vl_32b_instruct`) plus credentials exported in the shell (do not store in notes).
- For Cloud API resiliency, batches are posted via `scripts/replay_events.py`.
- The repo copies the IQ8 workspace to the submission path so reviewers
  can run `./scripts/run_cloud.sh`, `./scripts/run_edge_camera.sh`, and
  `./scripts/run_query.sh` in order.
- `collaterals/technical_report.md`, `collaterals/video_demo.mp4`, and
  `collaterals/deck.pptx` accompany the artifact submission so reviewers
  can verify architecture, perf, and demo states.

## Section 8: Next Steps
- Integrate QNN YOLOv8 targeting HTP/NPU for true on-device acceleration.
- Expand policy/zone definitions in `docs/zones.demo.json` + detection masks.
- Capture performance logs over multiple hardware configs (Hydra + LLM) and
  drop them into `benchmarks/benchmark_log.json` for benchmarking/submission.
- Clean up docs/README to describe how to rebuild the environment (`pip install
  -r requirements.txt`, `scripts/get_models.sh`, `scripts/run_edge_camera.sh`).
