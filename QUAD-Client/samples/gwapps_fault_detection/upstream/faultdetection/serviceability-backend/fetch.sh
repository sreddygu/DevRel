# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

#!/bin/bash
set -euo pipefail
set -x

IMAGE="docker-registry.qualcomm.com/win-cloud-service/gwapps:serviceability-backend-latest"
OUT_DIR="$(dirname "$0")"

docker pull "$IMAGE"
rm -f "$OUT_DIR"/*.tar
docker save "$IMAGE" -o "$OUT_DIR/serviceability-backend.tar"
