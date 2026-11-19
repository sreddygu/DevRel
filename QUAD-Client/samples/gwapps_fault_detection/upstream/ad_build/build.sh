#!/bin/bash
set -euo pipefail
set -x

show_help() {
    echo "Usage:"
    echo "  $0 <arch> <middleware> <APP_OR_LIB_TO_BUILD>"
    echo ""
    echo "Arguments:"
    echo "  arch: aarch64 | arm | all"
    echo "  middleware: openwrt | prpl | rdk | all"
    echo "  APP_OR_LIB_TO_BUILD: ad_lib | ad_app | all"
    echo ""
    echo "Examples:"
    echo "  $0 aarch64 openwrt ad_lib"
    echo "  $0 arm ad_app"
    echo "  $0 aarch64 prpl all"
    echo "  $0 all                      # Builds all"
    echo "  $0 all release              # Builds all, including log_summarization_vllm and gwapps images"
    echo "                              # (gwapps: pulls :latest from registry if reachable, else uses bundled tar)"
    echo "  $0 --help                   # Show this help message"
}

# Show help if requested
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

# Argument parsing
RELEASE_MODE=false

if [ "$#" -eq 0 ]; then
    echo "Error: At least one argument is required."
    show_help
    exit 1
elif [ "$#" -eq 1 ]; then
    ARCH=$1
    MIDDLEWARE="all"
    APP_OR_LIB_TO_BUILD="all"
elif [ "$#" -eq 2 ]; then
    if [ "$1" == "all" ] && [ "$2" == "release" ]; then
        ARCH="all"
        MIDDLEWARE="all"
        APP_OR_LIB_TO_BUILD="all"
        RELEASE_MODE=true
    else
        echo "Error: Invalid arguments."
        show_help
        exit 1
    fi
elif [ "$#" -eq 3 ]; then
    ARCH=$1
    MIDDLEWARE=$2
    APP_OR_LIB_TO_BUILD=$3
else
    echo "Invalid number of arguments."
    show_help
    exit 1
fi

# Normalize middleware to match directory naming
normalize_middleware() {
    case "$1" in
        openwrt) echo "openwrt-linux" ;;
        prpl) echo "prpl-linux" ;;
        rdk) echo "rdk-linux" ;;
        all) echo "all" ;;
        *) echo "unknown" ;;
    esac
}

build_all() {
    for dir in  aarch64-openwrt-linux aarch64-prpl-linux aarch64-rdk-linux arm-openwrt-linux; do
        if [ -d "$dir" ]; then
            cd "$dir"
            ./build.sh all
            cd ..
        else
            echo "Warning: Directory $dir not found, skipping."
        fi
    done
    
    if [ "$RELEASE_MODE" == "true" ]; then
        for dir in log_summarization serviceability-backend incident-dashboard-frontend; do
            if [ -d "$dir" ]; then
                cd "$dir"
                ./build.sh
                cd ..
            else
                echo "Warning: Directory $dir not found, skipping."
            fi
        done
    fi
}

build_specific() {
    NORMALIZED_MIDDLEWARE=$(normalize_middleware "$MIDDLEWARE")
    if [ "$NORMALIZED_MIDDLEWARE" == "unknown" ]; then
        echo "Error: Unknown middleware '$MIDDLEWARE'"
        show_help
        exit 1
    fi

    TARGET_DIR="${ARCH}-${NORMALIZED_MIDDLEWARE}"
    if [ -d "$TARGET_DIR" ]; then
        cd "$TARGET_DIR"
        ./build.sh "$APP_OR_LIB_TO_BUILD"
        cd ..
    else
	echo "$TARGET_DIR is not yet implemented, stay tuned!"
        exit 1
    fi
}

# Dispatch
if [ "$ARCH" == "all" ] && [ "$MIDDLEWARE" == "all" ] && [ "$APP_OR_LIB_TO_BUILD" == "all" ]; then
    build_all
else
    build_specific
fi
