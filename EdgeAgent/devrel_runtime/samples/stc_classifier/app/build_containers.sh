#!/usr/bin/env bash
#
# stc_classifier — container packaging script
#
# Builds the runc OCI bundle from the cross-compiled binary + the
# Dockerfile + oci_config.json that codegen produced. Mirrors the
# fault-detection reference's build_containers.sh (see
# samples/gwapps_fault_detection/upstream/faultdetection/fd/build_containers.sh).
#
# Usage:
#   ./build_containers.sh [--output <dir>] [--platform linux/arm64]
#
# Pre-requisites on PATH:
#   - docker (or podman, with `alias docker=podman`)
#   - tar
#
# Output:
#   <output>/stc_classifier-docker-image.tar    Docker image tarball
#   <output>/stc_classifier-runc.tar.gz         runc OCI bundle (deploy unit)

set -euo pipefail

APP_NAME="stc_classifier"
OUTPUT="${OUTPUT:-./build}"
PLATFORM="${PLATFORM:-linux/arm64}"

while [ $# -gt 0 ]; do
    case "$1" in
        --output)   OUTPUT="$2";   shift 2 ;;
        --platform) PLATFORM="$2"; shift 2 ;;
        -h|--help)
            sed -n '1,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$OUTPUT"

# 1. Build the docker image — FROM scratch keeps it tiny.
echo "▸ docker build (--platform $PLATFORM)..."
docker build --platform "$PLATFORM" -t "${APP_NAME}:latest" .
docker save -o "${OUTPUT}/${APP_NAME}-docker-image.tar" "${APP_NAME}:latest"
echo "  ✓ ${OUTPUT}/${APP_NAME}-docker-image.tar"

# 2. Convert the docker image into a runc OCI bundle.
BUNDLE_DIR="$(mktemp -d)"
trap "rm -rf '$BUNDLE_DIR'" EXIT

mkdir -p "${BUNDLE_DIR}/rootfs"
CID=$(docker create "${APP_NAME}:latest")
docker export "$CID" | tar -xf - -C "${BUNDLE_DIR}/rootfs"
docker rm "$CID" >/dev/null

cp "config/oci_config.json" "${BUNDLE_DIR}/config.json"

(cd "$BUNDLE_DIR" && tar czf "${OLDPWD}/${OUTPUT}/${APP_NAME}-runc.tar.gz" .)
echo "  ✓ ${OUTPUT}/${APP_NAME}-runc.tar.gz"

echo ""
echo "Deploy the runc bundle to the gateway:"
echo "  devrel gwapps deploy ${OUTPUT}/${APP_NAME}-runc.tar.gz --host <gateway-host>"
