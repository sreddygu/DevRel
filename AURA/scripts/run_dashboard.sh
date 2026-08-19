#!/usr/bin/env bash
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
# Launch the AURA FastAPI dashboard locally.
#
#   ./scripts/run_dashboard.sh
#
# Requires the dashboard extra:  pip install -e ".[dashboard]"
set -euo pipefail

cd "$(dirname "$0")/.."

HOST="${AURA_DASHBOARD_HOST:-127.0.0.1}"
PORT="${AURA_DASHBOARD_PORT:-8000}"

# aura.dashboard.api:create_app is the FastAPI app factory.
exec uvicorn --factory aura.dashboard.api:create_app --host "$HOST" --port "$PORT"
