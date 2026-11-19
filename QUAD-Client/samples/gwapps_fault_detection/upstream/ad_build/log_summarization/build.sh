#!/bin/bash
set -euo pipefail
set -x

build_log_summarization_vllm() {
    local src_dir="../../faultdetection/log_summarization/src/connectivity"
    local install_dir="../../ad_libs_bins/log_summarization"
    if [ -d "$src_dir" ]; then
        cd "$src_dir"
        docker build --build-arg BUILD_ENV=production -f Dockerfile.vllm \
            -t docker-registry.qualcomm.com/win-cloud-service/gwapps:incident-summary-service-latest \
            -t incident-summary-service:latest .
        cd -
        mkdir -p "$install_dir"
        docker save \
            docker-registry.qualcomm.com/win-cloud-service/gwapps:incident-summary-service-latest \
            incident-summary-service:latest \
            -o "${install_dir}/incident-summary-service.tar"
    else
        echo "Warning: Directory $src_dir not found, skipping."
    fi
}

build_log_summarization_vllm
