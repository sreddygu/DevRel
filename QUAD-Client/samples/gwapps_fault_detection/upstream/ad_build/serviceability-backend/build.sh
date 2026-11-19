#!/bin/bash
set -euo pipefail
set -x

REGISTRY_HOST="docker-registry.qualcomm.com"

build_serviceability_backend() {
    local src_dir="../../faultdetection/serviceability-backend"
    local fetch_script="${src_dir}/fetch.sh"
    local install_dir="../../ad_libs_bins/serviceability-backend"

    if curl --max-time 5 -s -o /dev/null "https://${REGISTRY_HOST}/v2/"; then
        echo "Registry ${REGISTRY_HOST} reachable; fetching latest image..."
        "$fetch_script"
    else
        echo "Registry ${REGISTRY_HOST} not reachable; using existing tar in ${src_dir}."
    fi

    local src_tar
    src_tar=$(find "$src_dir" -maxdepth 1 -name '*.tar' -type f | head -n 1)
    if [ -z "$src_tar" ]; then
        echo "Warning: no source tar in ${src_dir}, skipping. Run ${fetch_script} from a host with registry access."
        return
    fi

    local loaded_image
    loaded_image=$(docker load -i "$src_tar" | sed -n 's/^Loaded image: //p' | head -n 1)
    if [ -z "$loaded_image" ]; then
        echo "Error: could not determine image name loaded from ${src_tar}"
        return 1
    fi

    mkdir -p "$install_dir"
    docker tag "$loaded_image" serviceability-backend:latest
    docker save "$loaded_image" serviceability-backend:latest -o "${install_dir}/serviceability-backend.tar"
}

build_serviceability_backend
