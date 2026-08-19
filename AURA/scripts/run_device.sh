#!/usr/bin/env bash
# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
# Deploy + run AURA on the VENTUNO Q over SSH.
#
#   AURA_BOARD_HOST=<ip> AURA_BOARD_USER=<user> ./scripts/run_device.sh
#
# PLACEHOLDER — filled in with Milestone 1. The intended flow mirrors the
# host-orchestrator + on-device pattern used by the sibling projects:
#   1. rsync/scp this repo (minus venv/models) to the board
#   2. create a venv on-device and `pip install -e ".[vision]"`
#   3. run `aura run` on the board, streaming logs back
set -euo pipefail

: "${AURA_BOARD_HOST:?set AURA_BOARD_HOST (see .env.example)}"
: "${AURA_BOARD_USER:?set AURA_BOARD_USER (see .env.example)}"

echo "run_device.sh is a placeholder — implemented in Milestone 1 (see docs/ROADMAP.md)."
echo "Target: ${AURA_BOARD_USER}@${AURA_BOARD_HOST}"
exit 1
