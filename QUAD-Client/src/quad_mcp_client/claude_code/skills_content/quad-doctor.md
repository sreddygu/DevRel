---
name: quad-doctor
description: Use when the user asks "is QUAD set up correctly", "diagnose my install", "why isn't real mode working", "check the SDK", or invokes /quad-doctor. Runs the local diagnostic suite and explains each warning + the exact fix.
trigger: "doctor"
user-invocable: true
allowed-tools:
  - Bash(quad-client *)
---

# /quad-doctor -- QUAD Diagnostic Suite

Checks Python version, SDK env vars, SDK tools on PATH, DSP env, Android tools, DLC compatibility, WER support, and Python arch vs OS.

Arguments passed: `$ARGUMENTS`

---

## Diagnostic steps

1. **Run diagnostics** -- run `.venv/Scripts/python.exe -m quad_mcp_client.cli doctor` via the Bash tool.

2. **Explain results** -- show the output. For each WARN or FAIL row, describe the fix from the Detail column.

   - **Corporate-TLS CA bundle (`TLS CA bundle env vars` row).** A FAIL here
     means `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` / `CURL_CA_BUNDLE` /
     `QUAD_CA_BUNDLE` points at a file that no longer exists — which breaks
     **all** HTTPS downloads (AI Hub Models assets, models) with "Could not find a
     suitable TLS CA certificate bundle" / `CERTIFICATE_VERIFY_FAILED`. This was
     a real IQ-9075 blocker (a stale `REQUESTS_CA_BUNDLE`). Fix: unset the var,
     or point it at your real corporate CA `.pem` (or `pip install truststore`
     to use the OS trust store).

3. **NPU / AI Hub Models prerequisites** -- additionally verify the Snapdragon
   NPU path is provisioned:
   - **Native arm64 Python (X Elite)** — the single most common trap. On a
     Snapdragon X Elite, Windows can run an *emulated x86-64* Python under
     Prism, in which case `platform.machine()` returns `AMD64` even though
     `platform.processor()` reports a Qualcomm/ARMv8 CPU. The arm64-only NPU
     wheels (`onnxruntime-genai` / `onnxruntime-qnn`) neither install nor
     reach the Hexagon NPU under emulated Python. **Flag `machine != ARM64`
     while the processor is Qualcomm/ARM as a HARD finding**; the fix is to
     install native arm64 Windows Python and rebuild the venv (QUAD's
     `install.ps1` provisions it as `.venv-arm64`; SAGE's `run.ps1` auto-
     recreates a wrong-arch venv). Note the two-venv split: x86_64 3.10 for
     QAIRT *conversion*, native arm64 for the NPU *runtime*.
   - **AI Hub Models token** — is `QAI_HUB_API_KEY` (or the `QAI_HUB_API_TOKEN`
     alias) set in the environment / `.env`, or is `~/.qai_hub/client.ini`
     present?
   - **NPU runtime wheels** — are the arch-correct wheels importable?
     On win-arm64: `onnxruntime-qnn` (check
     `'QNNExecutionProvider' in onnxruntime.get_available_providers()`)
     and `onnxruntime-genai`; plus `qai-hub` / `qai-hub-models`.
   If any are missing, the fix is: **run `/quad-npu-prereqs`** — it
   reviews and provisions the token + wheels + env/config in one pass.
