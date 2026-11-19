#!/usr/bin/env bash
# ===========================================================================
# start_iq9_genie.sh -- NPU (Genie/QAIRT) helper for IQ9 (QCS9075, aarch64
# Linux). Linux analog of start_npu_genie.bat. Two modes:
#
#   ./start_iq9_genie.sh          Start the OpenAI shim (genie_server.py) so the
#                                 agent can reach the NPU on :8081.
#   ./start_iq9_genie.sh test     Direct NPU sanity check -- run genie-t2t-run
#                                 against the bundle (NO HTTP, NO agent). Answers
#                                 "does the NPU stack itself work?" first.
#
# Override any default with an env var:
#   QAIRT_HOME, BUNDLE_DIR, GENIE_T2T_RUN, GENIE_HOST, GENIE_PORT,
#   CHAT_TEMPLATE, MODEL_NAME
#
# NOTE (mmap gotcha): the bundle must live on a PLAIN local disk. Genie mmaps
# the ctx-bins ("use-mmap":true); cloud-synced / overlay paths can fail with
# "empty file / nothing to deserialize" even when the .bin files are present.
# /home/ubuntu/... is fine. This script warns on obvious synced paths.
#
# Paths verified on IQ9 2026-07-03 (QAIRT 2.46.0.260424):
#   bin: aarch64-oe-linux-gcc11.2   lib: aarch64-oe-linux-gcc11.2
#   skels: lib/hexagon-v73/unsigned   SoC: QCS9075 (HTP v73)
# ===========================================================================
set -euo pipefail

MODE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Defaults (override via env) -------------------------------------------
: "${QAIRT_HOME:=$HOME/qairt_2.46.0.260424/qairt/2.46.0.260424}"
: "${BUNDLE_DIR:=$HOME/genie_bundles/qwen3_8b}"
: "${GENIE_T2T_RUN:=$QAIRT_HOME/bin/aarch64-oe-linux-gcc11.2/genie-t2t-run}"
: "${GENIE_HOST:=0.0.0.0}"
: "${GENIE_PORT:=8081}"
: "${CHAT_TEMPLATE:=qwen}"
: "${MODEL_NAME:=qwen3-8b-genie}"

GENIE_SERVER_PY="$SCRIPT_DIR/genie_server.py"
CONFIG_JSON="$BUNDLE_DIR/genie_config.json"

# --- Environment Genie/QNN needs to load the Hexagon skels -----------------
export PATH="$QAIRT_HOME/bin/aarch64-oe-linux-gcc11.2:$PATH"
export LD_LIBRARY_PATH="$QAIRT_HOME/lib/aarch64-oe-linux-gcc11.2:${LD_LIBRARY_PATH:-}"
export ADSP_LIBRARY_PATH="$QAIRT_HOME/lib/hexagon-v73/unsigned"

# --- Shared checks ----------------------------------------------------------
if [[ ! -x "$GENIE_T2T_RUN" ]]; then
  echo "ERROR: missing/!executable genie-t2t-run: $GENIE_T2T_RUN" >&2
  echo "       Check QAIRT_HOME matches an installed version." >&2
  exit 1
fi
if [[ ! -f "$CONFIG_JSON" ]]; then
  echo "ERROR: bundle not found (no genie_config.json): $BUNDLE_DIR" >&2
  echo "       scp the exported Qwen3-8B bundle there first." >&2
  exit 1
fi
case "$BUNDLE_DIR" in
  *Dropbox*|*OneDrive*|*/gvfs/*)
    echo "WARN: BUNDLE_DIR looks cloud-synced ($BUNDLE_DIR) -- Genie mmap may fail." >&2
    echo "      Prefer a plain path like \$HOME/genie_bundles/..." >&2 ;;
esac

if [[ "${MODE,,}" == "test" ]]; then
  echo "=== Genie NPU sanity test (direct, no HTTP) ==="
  echo "QAIRT_HOME : $QAIRT_HOME"
  echo "BUNDLE_DIR : $BUNDLE_DIR"
  echo "ADSP_LIBRARY_PATH : $ADSP_LIBRARY_PATH"
  echo
  cd "$BUNDLE_DIR"
  PROMPT_FILE="sample_prompt.txt"
  [[ -f "$PROMPT_FILE" ]] || { echo "Hello from IQ9." > /tmp/iq9_prompt.txt; PROMPT_FILE=/tmp/iq9_prompt.txt; }
  echo "Running genie-t2t-run against $PROMPT_FILE ..."
  echo
  "$GENIE_T2T_RUN" -c genie_config.json --prompt_file "$PROMPT_FILE"
  echo
  echo "=== done ==="
  exit 0
fi

# --- Start the shim ---------------------------------------------------------
echo "=== Start Genie NPU shim (IQ9) ==="
echo "[npu] genie_server.py: $GENIE_SERVER_PY"
echo "[npu] config:          $CONFIG_JSON"
echo "[npu] binary:          $GENIE_T2T_RUN"
echo "[npu] listen:          http://$GENIE_HOST:$GENIE_PORT   (model: $MODEL_NAME, template: $CHAT_TEMPLATE)"
echo
[[ -f "$GENIE_SERVER_PY" ]] || { echo "ERROR: missing genie_server.py: $GENIE_SERVER_PY" >&2; exit 1; }

# Prefer a project venv python if present; else python3 on PATH.
PY="python3"
[[ -x "$SCRIPT_DIR/.venv/bin/python" ]] && PY="$SCRIPT_DIR/.venv/bin/python"

# IMPORTANT: CWD = bundle dir so relative ctx-bins/tokenizer paths resolve.
cd "$BUNDLE_DIR"
exec "$PY" "$GENIE_SERVER_PY" \
  --config "./genie_config.json" \
  --binary "$GENIE_T2T_RUN" \
  --chat-template "$CHAT_TEMPLATE" \
  --model-name "$MODEL_NAME" \
  --host "$GENIE_HOST" --port "$GENIE_PORT" \
  --timeout 300
