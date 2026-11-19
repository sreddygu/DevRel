---
name: quad-quickstart
description: Use when the user asks to "get started with QUAD", "set up Qualcomm AI", "configure my Snapdragon laptop for QUAD", or invokes /quad-quickstart. Walks through hardware detection, SDK check, MCP server connectivity, and sample inference end-to-end.
trigger: "quickstart"
user-invocable: true
allowed-tools:
  - Bash(quad-client *)
  - mcp__quad__hardware_detect
  - mcp__quad__convert_model
  - mcp__quad__profile_workload
  - mcp__quad__orchestrate_workload
  - mcp__quad__generate_code
---

# /quad-quickstart -- QUAD Setup Walkthrough

Guides the user from cold-start to running inference on Qualcomm hardware. The
walkthrough has two halves: **(A) the local client** (this machine — hardware,
SDK, NPU wheels) and **(B) the QUAD MCP server** (reachability, capabilities,
and how to build on it). Don't stop at the local checks — the whole point of
QUAD is the server, so always carry the user through to part B.

Arguments passed: `$ARGUMENTS`

---

## Part A — Local client checks

1. **Detect hardware** -- run `.venv/Scripts/python.exe -m quad_mcp_client.cli detect` via the Bash tool and show the output.

2. **Check SDK** -- run `.venv/Scripts/python.exe -m quad_mcp_client.cli doctor` via the Bash tool and show the output. For each WARN/FAIL row, explain the fix.

3. **NPU prerequisites (Snapdragon)** -- if detect reports a Snapdragon
   chipset / Hexagon NPU, or the user wants on-device NPU inference,
   invoke the `quad-npu-prereqs` skill before converting. It reviews the
   AI Hub Models API token + the arch-correct NPU pip wheels
   (`onnxruntime-qnn` / `onnxruntime-genai`) + env/config with the
   user, then provisions them. Skip on a pure mock / CPU walkthrough.

---

## Part B — QUAD MCP server

The local client (part A) is just the provisioner. The real work runs on the
**QUAD MCP server**, which the client is configured to talk to (locally as a
subprocess, over SSH, or as a hosted HTTP/SSE service).

4. **Confirm the server is configured** -- run
   `.venv/Scripts/python.exe -m quad_mcp_client.cli status` via the Bash tool.
   This shows whether `settings.json` and the skills are installed. Then read
   the `mcpServers.quad` block in `.claude/settings.json` to report the
   transport in use (`command`/`args` ⇒ stdio-local or stdio-ssh; a
   `transport.type: http` block ⇒ sse-http) and the target host.

5. **Verify the server actually answers** -- prove the server is reachable, not
   just configured. Two ways, in order of preference:
   - **No-write probe (CLI):** run
     `.venv/Scripts/python.exe -m quad_mcp_client.cli connect-test <transport>`
     where `<transport>` is `stdio-local`, `stdio-ssh`, or `sse-http`, matching
     what step 4 found. For SSH pass `--ssh-user`/`--ssh-host`; for HTTP pass
     `--sse-url` (and `--auth-token` if the server requires one). It runs a real
     MCP `initialize` handshake and exits non-zero on failure — show the result.
   - **Live tool call:** call `mcp__quad__hardware_detect` directly. A clean
     result proves the end-to-end path (client → transport → server → tool)
     works. If it errors, the server is down or the transport is misconfigured —
     fall back to `connect-test` to localise the failure, and point the user at
     `docs/TRANSPORTS.md` / `docs/TROUBLESHOOTING.md`.

6. **Show what the server can do** -- the QUAD MCP server exposes **six tools**.
   Present this capability table so the developer knows the full surface, not
   just the two used in this walkthrough:

   | MCP tool | What it does | Typical use |
   |----------|--------------|-------------|
   | `mcp__quad__hardware_detect` | Probe the **server's** SoC, CPU/GPU/NPU, RAM, runtimes, and installed SDKs | First call in any pipeline — branch your app on what hardware is present |
   | `mcp__quad__convert_model` | Convert/compile a model (ONNX, PyTorch, TFLite) to a Qualcomm runtime (QNN/QAIRT, SNPE, ExecuTorch `.pte`) with optional INT8/INT4 quantization + calibration | Get a model into a form the NPU can run |
   | `mcp__quad__profile_workload` | Measure latency, throughput, and CPU/GPU/NPU utilisation of a converted model | Find bottlenecks; verify a conversion meets a latency budget |
   | `mcp__quad__orchestrate_workload` | Allocate ops across CPU/GPU/NPU and compare performance / balanced / efficiency power modes | Decide where each op should run for a target power/latency trade-off |
   | `mcp__quad__generate_code` | Emit compilable inference boilerplate for a (platform, language, SDK) combo — C++, Python, Android JNI | Scaffold the runtime app once the model is converted |
   | `mcp__quad__aihub_select` | Search/score/download from the Qualcomm AI Hub Models catalog (~195 pre-optimized models) for the detected chipset | Start from a proven, pre-optimized model instead of converting your own |

7. **Convert a model** -- if hardware and SDK look ready, call
   `mcp__quad__convert_model` with `source_format="onnx"`,
   `model_path="mobilenetv2.onnx"`, `quantization="int8"`.

8. **Profile** -- call `mcp__quad__profile_workload` with `model_path` from the
   previous step.

---

## Part C — Build on QUAD

9. **What the developer can leverage** -- close the walkthrough by orienting the
   developer toward building real applications. The canonical app loop is:

   `hardware_detect` → `convert_model` → `profile_workload` →
   `orchestrate_workload` → `generate_code` → ship.

   Point them at the matching helper skills (each wraps one tool with guidance
   and richer output) and entry points:
   - **Build a full app:** `quad-app-builder` — requirements → implementation →
     testing → hardening → docs → git push. Start here for "I want to build a
     vision/LLM/ASR app".
   - **Convert / quantize:** `quad-convert`. **Profile:** `quad-profile`.
     **Orchestrate:** `quad-orchestrate`. **Generate code:** `quad-codegen`.
   - **Recommendations:** `quad-recommend` — turns a model + target + use case
     into a concrete deployment plan (NPU vs GPU, INT4 vs INT8).
   - **Serve / deploy:** `quad-serve` (HTTP inference API), `quad-deploy`
     (push to Android / UNO Q / Snapdragon targets).
   - **NPU LLM bundles:** `quad-build-npu-bundle` for Genie/Llama/Qwen on Hexagon.
   - **Examples & docs:** `examples/` and `samples/` in this repo, plus
     `docs/DEVELOPER_GUIDE.md` and `docs/QUAD_Capabilities_and_User_Guide.docx`.

   Every new app must follow the `run.ps1` + `requirements.txt` convention (see
   the `quad-run-ps1` skill).

10. **Next steps** -- recommend a concrete next action based on what parts A and
    B turned up (e.g. "your NPU is ready — try `quad-app-builder` to build a
    MobileNetV2 classifier", or "the server is on the lab box over SSH — start
    with `quad-recommend` for your model").
