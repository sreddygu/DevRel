#!/usr/bin/env python3
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
entrypoint_vllm.py
------------------
Container startup script (pure Python — no bash dependency).

Startup sequence:
  1. Launch vLLM OpenAI-compatible server (downloads model on first run).
  2. Poll GET /health until vLLM is ready (up to VLLM_STARTUP_TIMEOUT_S seconds).
  3. os.execvp into gunicorn, which serves the summarization API on port 8000.

Environment variables (all optional — defaults shown):
  HF_MODEL_NAME             mistralai/Mistral-7B-Instruct-v0.2
  VLLM_PORT                 8001
  VLLM_MAX_MODEL_LEN        32000
  VLLM_GPU_MEMORY_UTIL      0.90
  VLLM_TENSOR_PARALLEL_SIZE 1
  HF_CACHE_DIR              /root/.cache/huggingface
  VLLM_STARTUP_TIMEOUT_S    600
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ── Configuration ─────────────────────────────────────────────────────────────

MODEL = os.environ.get("HF_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2")
PORT = int(os.environ.get("VLLM_PORT", "8001"))
MAX_MODEL_LEN = int(os.environ.get("VLLM_MAX_MODEL_LEN", "32000"))
GPU_MEMORY_UTIL = float(os.environ.get("VLLM_GPU_MEMORY_UTIL", "0.90"))
TENSOR_PARALLEL_SIZE = int(os.environ.get("VLLM_TENSOR_PARALLEL_SIZE", "1"))
HF_CACHE_DIR = os.environ.get("HF_CACHE_DIR", "/root/.cache/huggingface")
STARTUP_TIMEOUT = int(os.environ.get("VLLM_STARTUP_TIMEOUT_S", "600"))
HEALTH_POLL_INTERVAL = 5  # seconds between health checks


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    """Timestamped stdout log (flush immediately so Docker captures it)."""
    print(f"[entrypoint] {msg}", flush=True)


def _wait_for_vllm(port: int, timeout: int) -> bool:
    """
    Poll GET http://localhost:<port>/health every HEALTH_POLL_INTERVAL seconds.
    Returns True when a 200 response is received within *timeout* seconds.
    """
    url = f"http://localhost:{port}/health"
    deadline = time.monotonic() + timeout
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    _log(f"vLLM is ready (attempt {attempt})")
                    return True
        except (urllib.error.URLError, OSError):
            pass

        remaining = int(deadline - time.monotonic())
        _log(f"  waiting for vLLM on :{port} ... ({remaining}s remaining)")
        time.sleep(HEALTH_POLL_INTERVAL)

    return False


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    _log("Starting vLLM server")
    _log(f"  model          : {MODEL}")
    _log(f"  port           : {PORT}")
    _log(f"  max_model_len  : {MAX_MODEL_LEN}")
    _log(f"  gpu_memory_util: {GPU_MEMORY_UTIL}")
    _log(f"  tensor_parallel: {TENSOR_PARALLEL_SIZE}")
    _log(f"  cache dir      : {HF_CACHE_DIR}")
    _log(f"  startup timeout: {STARTUP_TIMEOUT}s")

    # Build vLLM command
    vllm_cmd = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        MODEL,
        "--port",
        str(PORT),
        "--host",
        "0.0.0.0",
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--gpu-memory-utilization",
        str(GPU_MEMORY_UTIL),
        "--tensor-parallel-size",
        str(TENSOR_PARALLEL_SIZE),
        "--served-model-name",
        MODEL,
        "--max-num-seqs",
        "32",
        "--download-dir",
        HF_CACHE_DIR,
        "--trust-remote-code",
        "--enable-chunked-prefill",
        "--max-num-batched-tokens",
        "32000",
        "--dtype",
        "bfloat16"
    ]

    # Launch vLLM as a background subprocess
    vllm_proc = subprocess.Popen(
        vllm_cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    _log(f"vLLM process started (pid={vllm_proc.pid})")
    _log(f"Waiting up to {STARTUP_TIMEOUT}s for vLLM to become healthy ...")

    if not _wait_for_vllm(PORT, STARTUP_TIMEOUT):
        _log("ERROR: vLLM did not become healthy within the timeout period.")
        vllm_proc.terminate()
        try:
            vllm_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            vllm_proc.kill()
        sys.exit(1)

    _log("vLLM is healthy. Launching gunicorn summarization service ...")

    # exec replaces this process — gunicorn inherits the vLLM child process
    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "--chdir",
            "/app",
            "-c",
            "gunicorn_conf.py",
            "main:app",
        ],
    )

    # os.execvp never returns on success; reaching here means it failed
    _log("ERROR: os.execvp('gunicorn') failed — gunicorn not found?")
    sys.exit(1)


if __name__ == "__main__":
    main()
