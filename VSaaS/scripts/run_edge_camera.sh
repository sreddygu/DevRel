#!/usr/bin/env bash
#
# VSaaS Edge Agent (camera mode)
#
# Captures short clips from a camera source (e.g. /dev/video2 or RTSP), stores clips
# locally, and posts *metadata-only* events to the VSaaS Cloud API.
#
# Usage:
#   ./scripts/run_cloud.sh          # in one terminal
#   ./scripts/run_edge_camera.sh    # in another terminal
#
# Environment:
#   VSAAS_CLOUD_BASE_URL     Cloud API base URL (default: http://127.0.0.1:9000)
#   VSAAS_CAMERA_ID          Camera identifier (default: iq8_cam_01)
#   VSAAS_VIDEO_SOURCE       /dev/videoX or rtsp://... (default: /dev/video0)
#   VSAAS_RECORD_DIR         Output directory (default: data/recordings)
#   VSAAS_CLIP_SECONDS       Clip duration seconds (default: 3.0)
#   VSAAS_EMIT_INTERVAL_SEC  Seconds between events (default: 5.0)
#   VSAAS_ENABLE_EDGE_AI     Enable edge AI (default: 1)
#   VSAAS_ZONES_JSON         Optional zones file (default: docs/zones.example.json if present)
#   VSAAS_RECORD_ON_EVENT    Record clips only when actionable events occur (default: 1)
#
# Notes:
# - This script auto-activates `.venv` when present.
# - `/dev/video*` may require group `video` membership or passwordless sudo for ffmpeg.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${VIRTUAL_ENV:-}" && -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

export VSAAS_CLOUD_BASE_URL="${VSAAS_CLOUD_BASE_URL:-http://127.0.0.1:9000}"
export VSAAS_CAMERA_ID="${VSAAS_CAMERA_ID:-iq8_cam_01}"
export VSAAS_VIDEO_SOURCE="${VSAAS_VIDEO_SOURCE:-/dev/video0}"   # or rtsp://...
export VSAAS_RECORD_DIR="${VSAAS_RECORD_DIR:-$ROOT_DIR/data/recordings}"
export VSAAS_CLIP_SECONDS="${VSAAS_CLIP_SECONDS:-3.0}"
export VSAAS_EMIT_INTERVAL_SEC="${VSAAS_EMIT_INTERVAL_SEC:-5.0}"
export VSAAS_ENABLE_EDGE_AI="${VSAAS_ENABLE_EDGE_AI:-1}"
export VSAAS_RECORD_ON_EVENT="${VSAAS_RECORD_ON_EVENT:-1}"
if [[ -z "${VSAAS_ZONES_JSON:-}" && -f "$ROOT_DIR/docs/zones.example.json" ]]; then
  export VSAAS_ZONES_JSON="$ROOT_DIR/docs/zones.example.json"
fi
# Real detector option:
#   VSAAS_DETECTOR=onnx_yolov8  (requires `pip install -r requirements.txt` and a model under `models/`)

exec python3 -m vsaas.edge_agent --mode camera
