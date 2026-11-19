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
#                     Example (Hydra/AIC100): https://dev.apigwx-op.qualcomm.com/aips/sparq/api/v1
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
export VSAAS_LLM_BASE_URL="${VSAAS_LLM_BASE_URL:-}"  # OpenAI-compatible server (e.g. Hydra/AIC100 or local 8080)

mkdir -p "$ROOT_DIR/data"

# Optional: load SparQ/Hydra creds from a local env file (do not print/store secrets).
# Usage:
#   VSAAS_LOAD_SPARQ_ENV=1 ./scripts/run_cloud.sh
# Or:
#   VSAAS_LOAD_SPARQ_ENV=1 VSAAS_SPARQ_ENV_FILE=~/.config/vsaas/sparq.env ./scripts/run_cloud.sh
if [[ "${VSAAS_LOAD_SPARQ_ENV:-}" =~ ^(1|true|yes)$ ]]; then
  ENV_FILE="${VSAAS_SPARQ_ENV_FILE:-$HOME/.config/vsaas/sparq.env}"
  if [[ -f "$ENV_FILE" ]]; then
    set +x
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set -x
  fi
  # Convenience: allow older env files to set `HYDRA_BASE_URL` instead of `VSAAS_LLM_BASE_URL`.
  if [[ -z "${VSAAS_LLM_BASE_URL:-}" && -n "${HYDRA_BASE_URL:-}" ]]; then
    export VSAAS_LLM_BASE_URL="$HYDRA_BASE_URL"
  fi
fi

exec python3 -m uvicorn vsaas.cloud_api:app --host "$VSAAS_HOST" --port "$VSAAS_PORT"
