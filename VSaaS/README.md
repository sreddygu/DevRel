# VSaaS — Private Edge Video Intelligence → Cloud Searchable Insights

Functional prototype scaffolding for VSaaS.

## What This Prototype Demonstrates

- **Edge-first video intelligence**: generate privacy-safe “events” (metadata) at the edge.
- **Metadata-only uplink**: store/search events without uploading raw video.
- **Natural-language queries over events**: optional LLM-backed query endpoint using `qwen3_vl_32b_instruct` through a hosted or local OpenAI-compatible server.

This repo is intentionally lightweight but now supports both:
1. **Simulated events** (default) for quick verification.
2. **Real edge perception** via an ONNX YOLOv8 detector or QNN YOLOv8 DLC (`models/yolov8_det_w8a8/yolov8_det_w8a8.dlc`) + optional PPE checker (see `docs/EDGE_AI.md` and https://aihub.qualcomm.com/models/yolov8_det?domain=Computer+Vision&useCase=Object+Detection).

## Quick Start (Local / IQ8)

1) Create a venv + install deps (includes ONNX stack):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Start the cloud API (event store + query):
```bash
./scripts/run_cloud.sh
```

3) Start the edge agent (simulated events):
```bash
./scripts/run_edge_sim.sh
```

3b) Start the edge agent (camera mode; records clips locally and uploads only metadata):
```bash
export VSAAS_VIDEO_SOURCE="/dev/video0"   # or rtsp://user:pass@ip/...
./scripts/run_edge_camera.sh
```

4) Query:
```bash
./scripts/run_query.sh "show last 5 events"
./scripts/run_query.sh "summarize the last 10 events"
```

## IQ8 Integration (LLM)

The Cloud API `/query` endpoint can optionally use an OpenAI-compatible backend for summarization.

### Option A: Hosted OpenAI-compatible service
```bash
export VSAAS_LLM_BASE_URL="https://api.example.com/v1"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"
export VSAAS_LLM_API_KEY="Stored in password manager"
# Optional for gateways that require a separate x-apikey header:
# export VSAAS_LLM_X_APIKEY="Stored in password manager"
export VSAAS_LLM_DEBUG=1
```

### Option B: Local IQ8 Qwen server
If you already run a local OpenAI-compatible Qwen server on IQ8 (local-only), point VSaaS at it:
```bash
export VSAAS_LLM_BASE_URL="http://127.0.0.1:8080"
export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"
```

Then restart `./scripts/run_cloud.sh` and use `./scripts/run_query.sh`.

## Real edge AI workflow

1. Install deps + download the model:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/get_models.sh
```
2. Run with YOLOv8 QNN DLC on IQ8 NPU/HTP (e.g., exported from Qualcomm AI Hub):
```bash
export VSAAS_DETECTOR=qnn_yolov8
export VSAAS_QNN_BACKEND=/lib/libQnnHtp.so
export VSAAS_QNN_DLC_PATH="$PWD/models/yolov8_det_w8a8/yolov8_det_w8a8.dlc"
export VSAAS_QNN_INPUT_NAME=images
export VSAAS_QNN_INPUT_SIZE=640
export VSAAS_DET_CONF=0.15
export VSAAS_DET_TOPK=8
export VSAAS_VIDEO_SOURCE="qmmf://video_0"   # CSI path; keep cam-server.service active
./scripts/run_edge_camera.sh
```
2b. Optional: run with YOLOv8 ONNX (CPUExecutionProvider):
```bash
export VSAAS_DETECTOR=onnx_yolov8
export VSAAS_YOLO_ONNX_PATH="$PWD/models/yolov8n.onnx"
export VSAAS_VIDEO_SOURCE="/dev/video2"
./scripts/run_edge_camera.sh
```
3. The agent emits `objects_detected` events listing each prediction; `person_detected`, `zone_entry`, `dwell_time`, and `ppe_violation` follow when the same detections are classified as people or violate policies. See `docs/EDGE_AI.md` for zone/PPE guidance.

## Cloud AI Work Flow

1. Start the Cloud API:
```bash
./scripts/run_cloud.sh
```
2. Post events into the Cloud API:
```bash
# Option A: run an edge agent
./scripts/run_edge_sim.sh

# Option B: replay from the local SQLite DB
python3 ./scripts/replay_events.py --db-path data/events.db --base-url http://127.0.0.1:9000 --batch-size 25
```
3. Validate + query:
```bash
curl -s http://127.0.0.1:9000/health
curl -s http://127.0.0.1:9000/events?limit=5
./scripts/run_query.sh "summarize recent events"  # uses the configured LLM when env vars are set
```

## Logs

Edge/cloud logs accumulate under `logs/` so they can be archived with SparQ benchmarks (`~/projects/VSaaS/logs`). The repo mirrors this directory (see `VSaaS/logs/`) to keep everything versioned together.

## Repo Layout

- `src/vsaas/cloud_api.py`: FastAPI “cloud” service (stores events, supports search + NL query)
- `src/vsaas/edge_agent.py`: Edge event generator (simulator; extend to real perception later)
- `docs/`: requirements + prototype notes
- `benchmarks/`: benchmark log template
- `collaterals/`: placeholders for video/deck/report pointers
