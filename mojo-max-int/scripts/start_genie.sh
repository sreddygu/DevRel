#!/usr/bin/env bash
# start_genie.sh — start the Genie server on IQ9 for the mojo-max-int project.
# Run this on the IQ9, then connect from Mojo with: mojo run src/agent.mojo -- --host 127.0.0.1

set -euo pipefail

BUNDLE_DIR="${BUNDLE_DIR:-/opt/aura-llm/gemma4-genie/bundle}"
RUNTIME_BIN="${RUNTIME_BIN:-/opt/aura-llm/gemma4-genie/runtime/bin}"
RUNTIME_LIB="${RUNTIME_LIB:-/opt/aura-llm/gemma4-genie/runtime/lib}"
QNN_LIB="${QNN_LIB:-/opt/qnn/lib}"
QNN_DSP="${QNN_DSP:-/opt/qnn/dsp}"
MODEL_NAME="${MODEL_NAME:-gemma-4-e4b-genie}"
PORT="${PORT:-8081}"

# Path to genie_server.py (relative to this script, inside the EdgeAgent project)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENIE_SERVER="${GENIE_SERVER:-$SCRIPT_DIR/../../EdgeAgent/genie_server.py}"

export LD_LIBRARY_PATH="$RUNTIME_LIB:$QNN_LIB:$QNN_DSP${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ADSP_LIBRARY_PATH="$QNN_DSP${ADSP_LIBRARY_PATH:+;$ADSP_LIBRARY_PATH}"
export PATH="$RUNTIME_BIN:$PATH"

echo "Bundle:  $BUNDLE_DIR"
echo "Runtime: $RUNTIME_BIN"
echo "Model:   $MODEL_NAME"
echo "Port:    $PORT"
echo ""

python3 "$GENIE_SERVER" \
    --bundle "$BUNDLE_DIR" \
    --model-name "$MODEL_NAME" \
    --chat-template gemma \
    --host 0.0.0.0 \
    --port "$PORT"
