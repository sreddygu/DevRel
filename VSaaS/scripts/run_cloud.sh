#!/usr/bin/env bash
#
# VSaaS Cloud API (prototype)
#
# Starts the local FastAPI service (event sink + query endpoint) via uvicorn.
#
# Usage:
#   ./scripts/run_cloud.sh
#
# Environment:
#   VSAAS_HOST         Bind host (default: 127.0.0.1)
#   VSAAS_PORT         Bind port (default: 9000)
#   VSAAS_DB_PATH      SQLite DB path (default: data/events.db)
#   VSAAS_LLM_BASE_URL Optional LLM base URL (default: empty/disabled)
#                     Example (hosted): https://api.example.com/v1
#                     Example (local): http://127.0.0.1:8080
#
# Notes:
# - This script auto-activates `.venv` when present.
# - Pairs with `scripts/run_edge_sim.sh` or `scripts/run_edge_camera.sh`.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${VIRTUAL_ENV:-}" && -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

export VSAAS_DB_PATH="${VSAAS_DB_PATH:-$ROOT_DIR/data/events.db}"
export VSAAS_HOST="${VSAAS_HOST:-127.0.0.1}"
export VSAAS_PORT="${VSAAS_PORT:-9000}"
export VSAAS_LLM_BASE_URL="${VSAAS_LLM_BASE_URL:-}"  # Hosted or local OpenAI-compatible server

mkdir -p "$ROOT_DIR/data"

exec python3 -m uvicorn vsaas.cloud_api:app --host "$VSAAS_HOST" --port "$VSAAS_PORT"
