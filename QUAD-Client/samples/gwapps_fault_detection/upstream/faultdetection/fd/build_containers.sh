#!/bin/bash

#
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.
#

set -e

# === Default Configuration ===
APP_NAME=""
PLATFORM="linux/arm64"
CONFIG_PATH=""
OUTPUT_DIR=""
DOCKERFILE="Dockerfile"
VERBOSE=false
QUIET=false

# === Helper Functions ===

log() {
    if [ "$QUIET" = false ]; then
        echo "$@"
    fi
}

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo "[VERBOSE] $@"
    fi
}

print_help() {
    cat <<EOF
Usage: $0 [options] <app_name>

Options:
 --help                Show this help message and exit
 --platform <arch>     Set target platform (default: linux/arm64)
 --config <path>       Path to config.json (default: ./config.json)
 --output <dir>        Output directory (default: current directory)
 --dockerfile <path>   Path to Dockerfile (default: ./Dockerfile)
 --verbose             Enable verbose output
 --quiet               Suppress non-error output

Example:
 $0 --platform linux/amd64 --config ./myconfig.json --output ./out --dockerfile ./Dockerfile myapp

Warnings and Notes:
 - This script will create the following directories and files:
   • <output_dir>/<app_name>-runc/
   • <output_dir>/<app_name>-runc.tar.gz
   • <output_dir>/<app_name>-docker-image.tar
 - If these files or directories already exist, they will be **overwritten**.
 - A Docker container named <app_name>-container will be created and removed automatically.
   If a container with that name already exists, it will be **forcefully removed**.
 - The script requires a Dockerfile (default: ./Dockerfile).
 - The specified config.json must exist, or the script will exit with an error (Execute 'runc spec' to create a template config).
 - Docker Buildx will be used; a builder named 'mybuilder' will be created if it doesn't exist.

EOF
}

# === Argument Parsing ===

while [[ $# -gt 0 ]]; do
    case "$1" in
    --help)
        print_help
        exit 0
        ;;
    --platform)
        PLATFORM="$2"
        shift 2
        ;;
    --config)
        CONFIG_PATH="$2"
        shift 2
        ;;
    --output)
        OUTPUT_DIR="$2"
        shift 2
        ;;
    --dockerfile)
        DOCKERFILE="$2"
        shift 2
        ;;
    --verbose)
        VERBOSE=true
        shift
        ;;
    --quiet)
        QUIET=true
        shift
        ;;
    -*)
        echo "Unknown option: $1"
        print_help
        exit 1
        ;;
    *)
        APP_NAME="$1"
        shift
        ;;
    esac
done

# === Validation ===

if [ -z "$APP_NAME" ]; then
    echo "Error: app_name is required."
    print_help
    exit 1
fi
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: Dockerfile not found at '$DOCKERFILE'."
    exit 1
fi

CONFIG_PATH="${CONFIG_PATH:-./config.json}"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: config.json not found at '$CONFIG_PATH'."
    exit 1
fi

OUTPUT_DIR="${OUTPUT_DIR:-.}"
BUNDLE_DIR="${OUTPUT_DIR}/${APP_NAME}-runc"
TAR_FILE="${OUTPUT_DIR}/${APP_NAME}-runc.tar.gz"
IMAGE_NAME="${APP_NAME}-image"
CONTAINER_NAME="${APP_NAME}-container"
IMAGE_TAR_FILE="${OUTPUT_DIR}/${APP_NAME}-docker-image.tar"

# === Main Steps ===
ensure_buildx_builder() {
    local builder_name="mybuilder"

    if ! docker buildx inspect "$builder_name" &>/dev/null; then
        log "Creating Docker Buildx builder '$builder_name'..."
        docker buildx create --name "$builder_name" --use
    else
        verbose_log "Docker Buildx builder '$builder_name' already exists."
        docker buildx use "$builder_name"
    fi
}

build_image() {
    rm -rf ~/.docker
    log "Building Docker image '$IMAGE_NAME' for platform '$PLATFORM'..."
    docker buildx build --platform "$PLATFORM" -t "$IMAGE_NAME" -f "$DOCKERFILE" --load .
}

export_image_tar() {
    log "Exporting Docker image to '$IMAGE_TAR_FILE'..."
    docker save -o "$IMAGE_TAR_FILE" "$IMAGE_NAME"
}

create_container() {
    log "Creating container '$CONTAINER_NAME'..."
    if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
        verbose_log "Container '$CONTAINER_NAME' already exists. Removing it..."
        docker rm -f "$CONTAINER_NAME"
    fi
    docker create --name "$CONTAINER_NAME" "$IMAGE_NAME"
}

export_bundle() {
    log "Exporting container filesystem to '$BUNDLE_DIR'..."
    mkdir -p "$BUNDLE_DIR/rootfs"
    docker export "$CONTAINER_NAME" | tar -C "$BUNDLE_DIR/rootfs" -xvf - >/dev/null
}

generate_runc_spec() {
    log "Generating runc spec..."
    pushd "$BUNDLE_DIR" >/dev/null
    if [ -f config.json ]; then
        rm config.json
    fi
    popd >/dev/null
    cp "$CONFIG_PATH" "$BUNDLE_DIR"/
}

package_bundle() {
    log "Creating tarball '$TAR_FILE'..."
    tar -czf "$TAR_FILE" -C "$OUTPUT_DIR" "$(basename "$BUNDLE_DIR")"
}

cleanup_container() {
    verbose_log "Removing temporary container '$CONTAINER_NAME'..."
    docker rm "$CONTAINER_NAME" >/dev/null
    rm -rf "$BUNDLE_DIR"
}

# === Execution ===

ensure_buildx_builder
build_image
export_image_tar
create_container
export_bundle
generate_runc_spec
package_bundle
cleanup_container

log "Bundle created successfully: $TAR_FILE"
