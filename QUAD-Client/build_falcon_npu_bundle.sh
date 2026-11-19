#!/usr/bin/env bash
# build_falcon_npu_bundle.sh — build a Genie NPU LLM bundle for Falcon3 7B
# Instruct on a NON-arm64 build host, then stage it for the Snapdragon
# X-Elite where SAGE's native-arm64 runtime loads it onto the Hexagon NPU.
#
# WHY A SEPARATE BUILD HOST: the AI Hub exporter (qai-hub-models) pulls
# torch, which has NO win_arm64 wheel — so the bundle cannot be built on a
# Windows-arm64 X-Elite even though that's where it RUNS. And the export
# loads Falcon-7B in fp32 (~28 GB) before tracing it to ONNX, so the build
# host needs real headroom.
#
#   *** BUILD-HOST REQUIREMENT: >= 64 GB RAM (or RAM + large swap). ***
#
# A 32 GB box (e.g. WSL on the X-Elite itself) OOM-kills mid-export: fp32
# weights fill RAM before swap engages. Use an x86/Linux/cloud box with
# >=64 GB, or a smaller model (llama-3.2-3b ~6 GB fp32) on constrained hosts.
#
# Falcon3 is OPEN — no Hugging Face token required. The only secret is the
# AI Hub token (the heavy compile is a cloud AOT step).
#
# Usage (on the build host):
#   export QAI_HUB_API_TOKEN=<your-token>
#   # optional: override where the staged bundle is written
#   export DST=/path/to/SAGE/models/falcon-v3-7b-instruct
#   bash build_falcon_npu_bundle.sh
#
# Then copy $DST to the X-Elite at:
#   C:\work\QUAD\QUAD-Deliverables\sewa-apps\SAGE\models\falcon-v3-7b-instruct\
set -euo pipefail

SLUG="falcon_v3_7b_instruct"
FRIENDLY="falcon-v3-7b-instruct"
DEVICE="${DEVICE:-Snapdragon X Elite CRD}"
# Default staging dir targets WSL's view of the Windows disk; override via
# $DST on any other build host.
DST="${DST:-/mnt/c/work/QUAD/QUAD-Deliverables/sewa-apps/SAGE/models/${FRIENDLY}}"
EXPORT_DIR="${EXPORT_DIR:-$HOME/falcon_export}"
VENV="${VENV:-$HOME/aihub-build}"

if [ -z "${QAI_HUB_API_TOKEN:-}" ]; then
  echo "ERROR: export QAI_HUB_API_TOKEN=<token> first (get one at app.aihub.qualcomm.com)." >&2
  exit 1
fi

# torch/qai-hub-models need CPython 3.10–3.12. Prefer an existing python3.12;
# otherwise provision one via uv (handles distros that ship only 3.13/3.14).
echo "==> [1/5] Select a Python 3.10–3.12 interpreter"
PY=""
for cand in python3.12 python3.11 python3.10; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$(command -v "$cand")"; break; fi
done
if [ -z "$PY" ]; then
  echo "    no system 3.10–3.12 found; provisioning CPython 3.12 via uv"
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
  uv python install 3.12
  PY="$(uv python find 3.12)"
fi
echo "    interpreter: $PY"
"$PY" -m venv "$VENV"
# shellcheck disable=SC1090
source "$VENV/bin/activate"
python -m pip install -U pip

echo "==> [2/5] Install exporter (qai-hub, qai-hub-models, + Falcon extra)"
# The Falcon extra pins onnxsim (sdist-only on aarch64) — build host needs a
# C/C++ toolchain (build-essential + cmake) for that compile.
pip install -U "qai-hub" "qai-hub-models[${SLUG//_/-}]"

echo "==> [3/5] Authenticate the qai-hub SDK"
qai-hub configure --api_token "$QAI_HUB_API_TOKEN"

echo "==> [4/5] Confirm the device label exists in the catalog"
qai-hub list-devices | grep -i "x elite" || {
  echo "ERROR: '$DEVICE' not found in qai-hub list-devices output." >&2
  exit 1
}

echo "==> [5/5] Genie export (W4A16 quantize -> AI Hub cloud AOT -> download)"
echo "    (loads Falcon-7B fp32 ~28 GB first — needs the RAM noted at top)"
mkdir -p "$EXPORT_DIR"
python -m "qai_hub_models.models.${SLUG}.export" \
        --target-runtime genie \
        --device "$DEVICE" \
        --output-dir "$EXPORT_DIR" 2>&1 | tee /tmp/falcon_export.log

echo "--- export log tail ---"
tail -20 /tmp/falcon_export.log

# The export CLI may nest the bundle one level down; find genai_config.json.
OUT=""
if [ -f "$EXPORT_DIR/genai_config.json" ]; then
  OUT="$EXPORT_DIR"
else
  CFG=$(find "$EXPORT_DIR" -name genai_config.json -print -quit 2>/dev/null || true)
  [ -n "$CFG" ] && OUT="$(dirname "$CFG")"
fi

if [ -z "${OUT:-}" ] || [ ! -d "${OUT:-/nonexistent}" ]; then
  echo
  echo "Could not locate genai_config.json under $EXPORT_DIR. If the export was"
  echo "OOM-killed, use a build host with >=64 GB RAM. Otherwise look in the log"
  echo "above for the bundle directory, then copy it manually:"
  echo "   mkdir -p '$DST' && cp -r <export-dir>/* '$DST'/"
  exit 1
fi

echo "==> Staging bundle from $OUT into $DST"
mkdir -p "$DST"
cp -r "$OUT"/* "$DST"/
echo
echo "DONE. Bundle staged at: $DST"
echo "Copy that folder to the X-Elite at:"
echo "  C:\\work\\QUAD\\QUAD-Deliverables\\sewa-apps\\SAGE\\models\\${FRIENDLY}\\"
ls -la "$DST"
