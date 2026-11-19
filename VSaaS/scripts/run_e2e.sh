#!/usr/bin/env bash
# VSaaS E2E: Edge camera → Cloud API → NL query summary

set -euo pipefail

# Determine the repo root (one level up from this script)
WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKDIR"

# Activate the Python virtual environment
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi

# Ensure Python code is on PYTHONPATH
export PYTHONPATH="$WORKDIR/src:${PYTHONPATH:-}"

# Create a logs directory for this run
mkdir -p logs

# Load SparQ/Hydra credentials when available so the Cloud API hits the remote LLM.
# Set `VSAAS_LOAD_SPARQ_ENV=1` for run_cloud.sh when the env file exists.
SPARQ_ENV_FILE="${SPARQ_ENV_FILE:-$HOME/.config/vsaas/sparq.env}"
if [[ -f "$SPARQ_ENV_FILE" ]]; then
  export VSAAS_LOAD_SPARQ_ENV=1
  export VSAAS_SPARQ_ENV_FILE="$SPARQ_ENV_FILE"
fi

echo "=== Starting Cloud API (logs/cloud_e2e_TIMESTAMP.log) ==="
nohup ./scripts/run_cloud.sh >logs/cloud_e2e_$(date +%Y%m%d_%H%M%S).log 2>&1 &
CLOUD_PID=$!

echo "Waiting for Cloud API readiness..."
for i in $(seq 1 60); do
  if curl -fs http://127.0.0.1:9000/health >/dev/null 2>&1; then
    echo "Cloud API is ready."
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 60 ]; then
    echo
    echo "Error: Cloud API did not become ready after $i seconds." >&2
    exit 1
  fi
done
echo

echo "=== Starting Edge Camera Agent (logs/edge_e2e_TIMESTAMP.log) ==="
# Default to ONNX YOLOv8 if no detector is specified
export VSAAS_DETECTOR="${VSAAS_DETECTOR:-onnx_yolov8}"
export VSAAS_YOLO_ONNX_PATH="${VSAAS_YOLO_ONNX_PATH:-$WORKDIR/models/yolov8n.onnx}"

# Prefer the QMMF source when the shared camera service already owns /dev/video.
if [[ -z "${VSAAS_VIDEO_SOURCE:-}" ]]; then
  if systemctl is-active cam-server.service >/dev/null 2>&1; then
    export VSAAS_VIDEO_SOURCE="qmmf://video_0"
  else
    export VSAAS_VIDEO_SOURCE="/dev/video0"
  fi
fi

# Enable edge AI + telemetry signals.
export VSAAS_ENABLE_EDGE_AI="${VSAAS_ENABLE_EDGE_AI:-1}"
export VSAAS_RECORD_ON_EVENT="${VSAAS_RECORD_ON_EVENT:-1}"
export VSAAS_PPE_CHECKER="${VSAAS_PPE_CHECKER:-mock}"
if [[ -z "${VSAAS_ZONES_JSON:-}" && -f "$WORKDIR/docs/zones.example.json" ]]; then
  export VSAAS_ZONES_JSON="$WORKDIR/docs/zones.example.json"
fi

nohup ./scripts/run_edge_camera.sh >logs/edge_e2e_$(date +%Y%m%d_%H%M%S).log 2>&1 &
EDGE_PID=$!

echo "Capturing events for 10 seconds..."
sleep 10

echo "=== Fetching recent events (limit=5) ==="
curl -s http://127.0.0.1:9000/events?limit=5 | jq .

echo "=== Running summarization query ==="
./scripts/run_query.sh "summarize recent events" | jq .

echo "=== Cleaning up processes ==="
kill "${EDGE_PID:-}" "${CLOUD_PID:-}" >/dev/null 2>&1 || true

echo "E2E flow complete."
