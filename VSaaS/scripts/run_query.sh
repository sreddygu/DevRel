#!/usr/bin/env bash
#
# VSaaS Query CLI (prototype)
#
# Sends a natural-language question to the Cloud API `/query` endpoint and prints
# the JSON response. Intended for quick manual testing.
#
# Usage:
#   ./scripts/run_query.sh "summarize last 10"
#
# Environment:
#   VSAAS_CLOUD_BASE_URL  Cloud API base URL (default: http://127.0.0.1:9000)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 \"your question\"" >&2
  exit 2
fi

BASE_URL="${VSAAS_CLOUD_BASE_URL:-http://127.0.0.1:9000}"
QUESTION="$1"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${VIRTUAL_ENV:-}" && -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

python3 - "$BASE_URL" "$QUESTION" <<'PY'
import json, sys, urllib.request
base=sys.argv[1]
q=sys.argv[2]
req=urllib.request.Request(
  f"{base}/query",
  data=json.dumps({"question": q}).encode("utf-8"),
  headers={"Content-Type":"application/json"},
  method="POST",
)
with urllib.request.urlopen(req, timeout=60) as r:
  obj=json.load(r)
print(json.dumps(obj, indent=2))
PY
