#!/usr/bin/env bash
#
# Download public demo models for VSaaS edge inference.
#
# By default this fetches a YOLOv8n ONNX model for COCO object detection.
# The model is used when `VSAAS_DETECTOR=onnx_yolov8`.
#
# Usage:
#   ./scripts/get_models.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p models

YOLO_PATH="${VSAAS_YOLO_ONNX_PATH:-$ROOT_DIR/models/yolov8n.onnx}"

if [[ -f "$YOLO_PATH" ]]; then
  echo "OK: already present: $YOLO_PATH"
  exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Downloading YOLOv8n ONNX -> $YOLO_PATH"

# Try a small set of known public asset URLs. If these change, re-point here.
urls=(
  "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.onnx"
  "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.onnx"
)

ok=0
for u in "${urls[@]}"; do
  echo "  - $u"
  if command -v curl >/dev/null 2>&1; then
    if curl -fL --retry 3 --retry-delay 1 -o "$tmp/model.onnx" "$u"; then ok=1; break; fi
  elif command -v wget >/dev/null 2>&1; then
    if wget -O "$tmp/model.onnx" "$u"; then ok=1; break; fi
  else
    echo "Need curl or wget to download." >&2
    exit 2
  fi
done

if [[ "$ok" -ne 1 ]]; then
  echo "Failed to download YOLOv8n ONNX. Provide the file manually and set VSAAS_YOLO_ONNX_PATH." >&2
  exit 3
fi

mkdir -p "$(dirname "$YOLO_PATH")"
mv "$tmp/model.onnx" "$YOLO_PATH"
echo "Wrote: $YOLO_PATH"
