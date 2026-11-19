#!/bin/sh
set -eu

GENIEX_BIN="${GENIEX_BIN:-/usr/local/bin/geniex}"
GENIEX_DATA_DIR="${GENIEX_DATA_DIR:-/opt/geniex-data}"
GENIEX_HOST="${GENIEX_HOST:-0.0.0.0:18181}"

exec "$GENIEX_BIN" \
    --data-dir "$GENIEX_DATA_DIR" \
    --skip-update \
    serve \
    --host "$GENIEX_HOST"
