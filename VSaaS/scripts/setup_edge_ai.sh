#!/usr/bin/env bash
#
# Install optional dependencies for VSaaS edge vision inference (ONNX + image processing).
#
# Usage:
#   ./scripts/setup_edge_ai.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  echo "Missing venv at $ROOT_DIR/.venv. Create it first." >&2
  exit 2
fi

# shellcheck disable=SC1091
source "$ROOT_DIR/.venv/bin/activate"

python3 -m pip install --upgrade pip
python3 -m pip install -r "$ROOT_DIR/requirements.txt"
echo "OK: installed edge deps from requirements.txt"
