#!/bin/bash
# Cross-compile dit_server for the IQ8 (aarch64) in WSL against the QAIRT headers. Needs g++-aarch64-linux-gnu.
set -e
cd "$(dirname "$(readlink -f "$0")")"
I=${QAIRT_INCLUDE:-/mnt/c/Qualcomm/AIStack/QAIRT/2.51.40.260930/include/QNN}
aarch64-linux-gnu-g++ -std=c++17 -O2 -I"$I" -I"$I/System" -o dit_server dit_server.cpp -ldl -static-libstdc++ -static-libgcc
ls -la dit_server
