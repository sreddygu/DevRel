---
name: devrel-build-npu-bundle
description: Use when the user wants to "build an NPU LLM bundle", "export a Llama/Qwen model for the Hexagon NPU", "download a model for the npu provider", "get a model onto the X-Elite NPU", "the Download NPU bundle button can't run here", or invokes /devrel-build-npu-bundle. Builds an AI Hub Models Genie bundle on a non-arm64 host (WSL / x86 / macOS / Linux) and stages it onto the Snapdragon X-Elite where it runs.
trigger: "build-npu-bundle"
user-invocable: true
---

# DevRel — Build an on-device NPU LLM bundle

A runnable on-device LLM bundle for the Hexagon NPU (genai_config.json +
QNN context binary + tokenizer) is produced by the AI Hub Models **Genie**
export. The single hard fact that shapes this whole skill:

> **The build host and the run host are different machines.** The
> exporter (`qai-hub-models`) pulls **`torch`, which has no `win_arm64`
> wheel** — so a bundle **cannot be built on the Windows-arm64 X-Elite**,
> even though that is exactly where it **runs**. Build it somewhere torch
> resolves (WSL arm64-Linux on the same PC, or any x86 / macOS / Linux
> box), then copy the bundle folder onto the X-Elite.

This skill is the companion to `devrel-npu-prereqs` (which provisions the
runtime) and `devrel-aihub` (which picks a model + emits a generic deploy
plan). Use this one when the goal is specifically: *get a bundle built
and onto the X-Elite so the in-process `npu` provider can load it.*

## Phase 0 — Try the registry FIRST (skip the build entirely)

**Building is the expensive, fragile step — don't do it if someone already
did.** A Genie bundle is portable across every host of the same device class
(a bundle built for "Snapdragon X Elite" runs on *any* X-Elite). So before
setting up a build host, ask the DevRel bundle registry whether a prebuilt
bundle already exists for this model + device:

```python
mcp__devrel__aihub_select(action="ensure", model_id="falcon-v3-7b-instruct",
                        platform="windows")
```

`ensure` is the front door — it detects the host, asks the registry, and
resolves to one of:

- **`pulled`** — a compatible bundle existed; it's already downloaded,
  sha256-verified, and unpacked to `~/.devrel/models/<id>/`. **You're done — no
  build, no torch, no 64 GB box.** Skip to Phase 6 (verify it runs).
- **`request_build`** — no bundle yet, and this client can't build it
  (Windows-on-ARM has no torch wheel). A build job is recorded; you get a
  `job_id` and the operator runbook. Hand the build to a capable box
  (Phases 1–5), then `build_status` → pull.
- **`build_local` / `cloud_aot`** — a light model you can build right here.

To pull explicitly from a remote MCP server (the build host serving the
registry over HTTP), pass `registry_url`:

```python
mcp__devrel__aihub_select(action="pull", model_id="falcon-v3-7b-instruct",
                        platform="windows",
                        registry_url="https://<build-host>:8000")
```

Only fall through to building (Phases 1–5) when `ensure` says no bundle
exists. After you build, **publish it (Phase 5b)** so the next person pulls
instead of rebuilding.

## Phase 1 — Confirm the host split

Ask / detect: is the machine the user is on a Windows-arm64 X-Elite?

```bash
python -c "import platform,sys; print(sys.platform, platform.machine(), '|', platform.processor())"
```

- `win32` + `ARM64` → **run host.** Cannot build here. Go to Phase 2
  (WSL) or build on another box.
- `win32` + `AMD64` with a Qualcomm processor → emulated x86 on an
  X-Elite; the exporter front-end *may* install but this Python can't run
  the bundle. Prefer building in WSL and running from native arm64.
- Linux / macOS / x86 Windows → **build host.** You can build directly
  here (skip to Phase 3), then copy to the X-Elite.

## Phase 2 — Set up the WSL build environment (same X-Elite)

WSL2 on an X-Elite is **arm64 Linux**, where `torch` and
`qai-hub-models` DO publish wheels — so it's the most convenient build
host. Install once (admin PowerShell): `wsl --install`, reboot. Then
inside WSL:

```bash
python3 -m venv ~/aihub-build && source ~/aihub-build/bin/activate
pip install -U qai-hub qai-hub-models
```

If `pip` hits a corporate TLS error, the box uses a custom CA — export
`REQUESTS_CA_BUNDLE` / `PIP_CERT` to the org bundle, or `pip install
--trusted-host pypi.org --trusted-host files.pythonhosted.org`.

## Phase 3 — Authenticate to AI Hub Models

The export is a **cloud compile**, so it needs an AI Hub Models token.

```bash
export QAI_HUB_API_TOKEN=<token>        # get one at app.aihub.qualcomm.com
qai-hub configure --api_token $QAI_HUB_API_TOKEN
```

**Treat the token as a secret** — never echo it back, never write it to a
committed file. If the user pasted a token into chat, tell them to rotate
it.

**Gated weights:** Llama / Qwen require accepting the model license on
Hugging Face and an `HF_TOKEN` in the environment. **Falcon (`falcon-v3-7b-instruct`)
is open** — no HF token — so it's the best first model to prove the
pipeline end-to-end.

## Phase 4 — Find the exact device label, then export

The `--device` string must match an AI Hub Models device exactly:

```bash
qai-hub list-devices | grep -i "x elite"     # e.g. "Snapdragon X Elite CRD"
```

Then run the Genie export (the published path — AIMET W4A16 quantize →
AI Hub Models cloud AOT compile → downloads the QNN context binary + tokenizer +
genai_config):

```bash
python -m qai_hub_models.models.<slug>.export \
    --target-runtime genie \
    --device "<exact device label>"
```

Use the **package slug**, not the friendly id — e.g.
`qai_hub_models.models.falcon_v3_7b_instruct.export`. (The friendly id is
`falcon-v3-7b-instruct`; the slug is the same with underscores. SAGE's
`npu_llm.NPU_LLM_CATALOG` maps friendly id → slug.)

Note the output directory the export prints — it contains
`genai_config.json`, the `*.bin` / `*.onnx` graph, and the tokenizer.

## Phase 5 — Stage the bundle onto the X-Elite

Copy the bundle into the app's `models/<friendly-id>/` folder. From WSL,
the Windows disk is under `/mnt/c`:

```bash
DST=/mnt/c/work/DevRel/DevRel-Deliverables/sewa-apps/SAGE/models/falcon-v3-7b-instruct
mkdir -p "$DST"
cp -r <export-output-dir>/* "$DST"/
```

For a packaged EXE, copy the folder next to `SAGE.exe` instead (the EXE's
`models/` dir). For a remote board (`unoq` / `rubio-pi` / gateway), use
`devrel deploy genie <bundle_dir> --transport <ssh|adb|local>` or
`mcp__devrel__aihub_select(action="stage", ...)` rather than hand-`scp`.

The folder name MUST be the **friendly id** the runtime resolves
(`models/<friendly-id>/`), because `get_generator(model_name=…)` →
`assets_present()` looks there.

## Phase 5b — Publish to the registry (so nobody rebuilds it)

You just paid the expensive build once. **Publish the bundle to the DevRel
registry** so every other X-Elite pulls it in seconds instead of repeating
the 64 GB export:

```python
mcp__devrel__aihub_select(
    action="publish",
    model_id="falcon-v3-7b-instruct",
    bundle_dir="<export-output-dir>",      # the dir with genai_config.json + *.bin + tokenizer
    device_class="snapdragon-x-elite",      # canonical class — NOT a single machine
    qairt_version="<QAIRT ver you built against>",
)
# → {ok, manifest{sha256,size,…}, store_path}
```

Or from a shell: `devrel aihub publish --model-id falcon-v3-7b-instruct
--bundle-dir <dir> --device-class snapdragon-x-elite`.

- **Licensing gate:** only **redistributable** models publish to a shared
  store. **Falcon is open** — it publishes freely. Gated models (Llama / Qwen /
  Phi) are **refused** unless you pass `allow_gated=True`, which marks the
  bundle `redistributable: false` for a **private** store only. Never publish
  gated weights to a shared registry.
- If a build job tracked this model (`request_build` in Phase 0), publishing
  flips its `build_status` to `published` automatically — the requesting
  client's poll then succeeds and it pulls.
- The registry is content-addressed by sha256 and serves bytes over a plain
  HTTP route (`/bundles/<id>/download`, resumable) on the same MCP server —
  set `DevRel_MCP_TOKEN` to gate it on a LAN.

## Phase 6 — Verify it runs on the NPU (the gap-closer)

On the X-Elite, from the app's **native arm64** venv (not emulated x86),
load the bundle and read back the *actual* execution provider — don't
infer it from a wheel name:

```bash
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'src'); from npu_llm import get_generator; g=get_generator('falcon-v3-7b-instruct'); g._ensure_loaded(); print('EP =', g.provider)"
```

- **`EP = QNN`** → success: the model is decoding on the Hexagon NPU.
  Confirm in SAGE Settings (`provider=npu` → status shows `EP: QNN`) and
  capture a Chat turn / Benchmark-tab number (NPU vs CPU latency, tok/s).
- **`EP = CPU`** → the bundle loaded but fell back. The QNN EP library
  isn't wired in. Ensure the QAIRT QnnHtp libs are reachable
  (`sdks/<ver>/lib/aarch64-windows-msvc/QnnHtp.dll`) and, if the
  ORT-GenAI build requires it, register the EP explicitly via
  `og.register_execution_provider_library("QnnHtp", "<…>/QnnHtp.dll")`
  before building the `Config`. See `_ensure_loaded` in
  `sewa-apps/SAGE/src/npu_llm.py`.

## Common failure modes

| Symptom | Cause → fix |
|---------|-------------|
| `No matching distribution found for onnxruntime-genai-qnn` | That package doesn't exist. Runtime uses `onnxruntime-genai`. |
| pip can't find a `win_arm64` wheel for `torch` | You're trying to BUILD on the X-Elite. Build in WSL / x86 / macOS / Linux instead. |
| `quantized checkpoint … must have an ONNX model` | Wrong export path. LLMs need `--target-runtime genie`, not the vision `export(target_runtime="qnn")`. |
| 403 / access denied during export | Gated weights — accept the license on Hugging Face and set `HF_TOKEN`. Or pick an open model (Falcon). |
| `EP = CPU` after a clean load | QNN EP not registered / QnnHtp.dll not reachable (Phase 6). |
| Download button greyed out in the EXE | Frozen builds can't build bundles — pull a prebuilt one with `aihub_select(action="ensure"/"pull")`, or produce on a build host and drop the folder next to the EXE. |
| About to build a 7B on a fresh machine | Check the registry first (`action="ensure"`) — someone may have already published it; pulling is seconds vs a 64 GB export. |

## Reference

- Runtime + per-model catalog: `sewa-apps/SAGE/src/npu_llm.py`
  (`NPU_LLM_CATALOG`, `download_bundle`, `host_arch_status`,
  `qnn_genai_runtime_available`, `_ensure_loaded`).
- CLI form of the same flow: `sewa-apps/SAGE/fetch_llm_model.py`
  (`--download`, `--device`, `--hf-token`).
- Prereqs provisioning: `devrel-npu-prereqs`. Model selection + generic
  deploy plan: `devrel-aihub`.
- Bundle registry (build-once, pull-many): `aihub_select` actions
  `ensure` / `pull` / `publish` / `request_build` / `build_status`; design in
  `docs/BUNDLE_REGISTRY_PLAN.md`. Prefer `ensure` as the front door — it pulls
  a prebuilt bundle when one exists and only routes to a build when it must.
