#!/bin/bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

set -e

# Ensure the data directory exists and is writable
if [ -n "$LOG_SUMMARIZATION_DATA_DIR" ]; then
    echo "Checking permissions for $LOG_SUMMARIZATION_DATA_DIR" >&2

    # Try to create the directory if it doesn't exist
    mkdir -p "$LOG_SUMMARIZATION_DATA_DIR" 2>/dev/null || true

    # Test if we can write to the directory
    if [ -w "$LOG_SUMMARIZATION_DATA_DIR" ]; then
        echo "Directory $LOG_SUMMARIZATION_DATA_DIR is writable" >&2
    else
        echo "WARNING: Directory $LOG_SUMMARIZATION_DATA_DIR is not writable by current user" >&2
        echo "Please ensure the host directory has proper permissions:" >&2
        echo "  sudo chown -R 10001:10001 \$LOG_SUMMARIZATION_HOST_DIR" >&2
        echo "  or" >&2
        echo "  sudo chmod -R 777 \$LOG_SUMMARIZATION_HOST_DIR" >&2
    fi
fi

# Execute the main command
exec "$@"
