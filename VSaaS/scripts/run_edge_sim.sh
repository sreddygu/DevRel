#!/usr/bin/env bash
#
# VSaaS Edge Agent (simulate mode)
#
# Generates synthetic events and posts them to the VSaaS Cloud API. Useful for
# end-to-end testing without a camera.
#
# Usage:
#   ./scripts/run_cloud.sh        # in one terminal
#   ./scripts/run_edge_sim.sh     # in another terminal
#
# Environment:
#   VSAAS_CLOUD_BASE_URL     Cloud API base URL (default: http://127.0.0.1:9000)
#   VSAAS_CAMERA_ID          Camera identifier (default: iq8_cam_01)
#   VSAAS_EMIT_INTERVAL_SEC  Seconds between events (default: 2.0)
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
export VSAAS_EMIT_INTERVAL_SEC="${VSAAS_EMIT_INTERVAL_SEC:-2.0}"

exec python3 -m vsaas.edge_agent --mode simulate
