---
name: devrel-npu-prereqs
description: Use when the user wants to "develop on Snapdragon", "build for the NPU", "run a model on the Hexagon NPU", "set up NPU prerequisites", "configure my AI Hub Models token", "install onnxruntime-qnn / onnxruntime-genai", or invokes /devrel-npu-prereqs. Detects the host arch + target, reviews the AI Hub Models token + NPU pip wheels + env/config prerequisites with the user, then provisions them so the Snapdragon developer workflow is seamless.
trigger: "npu-prereqs"
user-invocable: true
---

# DevRel NPU Prerequisites — Provision the Snapdragon/AI Hub Models workflow

Any time a developer targets a Snapdragon SoC and wants to use the
Hexagon NPU, the path has hard prerequisites that are easy to miss and
annoying to debug after the fact:

- **AI Hub Models auth token** — required to download / cloud-compile AI Hub Models
  models and Genie LLM bundles.
- **NPU runtime wheels** — `onnxruntime-qnn` (the Hexagon ONNX Execution
  Provider for embeddings/vision, **win-arm64 only** with a CPU
  `onnxruntime` fallback; in 2.x a *plugin* EP — see "QNN EP usage") and
  `onnxruntime-genai` (Genie/LLM decode — ONE package whose win-arm64
  wheel carries the Hexagon support; there is **no**
  `onnxruntime-genai-qnn`), plus `qai-hub`. `qai-hub-models` is a
  **BUILD-host** dep only — it pulls `torch`/scipy, which have no
  `win_arm64` wheels, so it fails to install on an X-Elite (confirmed
  2026-06: meson "Unknown compiler" on a transitive build dep).
- **Env / config wiring** — the token in `.env`, the AI Hub Models adapter in
  `devrel.toml`, and (for the qai-hub SDK/CLI) `~/.qai_hub/client.ini`.

This skill makes that seamless. It **reviews the prerequisites with the
user, queries for the AI Hub Models token, and provisions pip + env + config**
— it does not silently install or guess secrets.

This skill is the single source of truth for NPU provisioning. Other
skills (`devrel-quickstart`, `devrel-configure`, `devrel-doctor`,
`devrel-run-ps1`, `devrel-codegen`, `devrel-app-builder`, `devrel-aihub`) hand
off here rather than reimplementing the flow.

## Canonical environment variable

Standardize on **`QAI_HUB_API_KEY`** — this matches DevRel core and the
`[adapters.ai_hub] api_key_env` setting in `devrel.toml`.

Also set **`QAI_HUB_API_TOKEN`** to the same value as an **alias**:
SAGE-style apps (`sewa-apps/SAGE`) and `fetch_llm_model.py` read that
name. Writing both keeps every consumer happy.

The `qai-hub` Python SDK/CLI reads its token from
`~/.qai_hub/client.ini`, written by `qai-hub configure --api_token …`.
Setting the env var alone is **not** always sufficient for the SDK —
run `qai-hub configure` too (Phase 5) so both the env consumers and the
SDK are satisfied.

---

## Phase 1 — Detect host + target

1. **Host architecture** decides which wheels exist:
   ```bash
   python -c "import platform, sys; print(sys.platform, platform.machine(), '|', platform.processor())"
   ```
   - `win32` + `ARM64`/`AARCH64` → **Snapdragon X-Elite**: the real NPU
     wheels (`onnxruntime-qnn`, `onnxruntime-genai`) apply.
   - anything else (x86_64 dev box, macOS, Linux) → **CPU fallback
     wheels** (`onnxruntime`, `onnxruntime-genai`) so imports still
     resolve and the app runs without the NPU.
   - **CRITICAL TRAP — emulated x86 on an X-Elite.** If `machine()` is
     `AMD64` but `processor()` names a Qualcomm/ARMv8 CPU, this is an
     *emulated x86-64* Python running under Windows-on-ARM (Prism). The NPU
     wheels are arm64-only, so they will NOT install or reach the NPU here.
     Stop and tell the user to install **native arm64 Windows Python** and
     rebuild the venv before provisioning. Also mind the **two-venv split on
     an X-Elite**: QAIRT *conversion* host tools need x86_64 Python 3.10,
     while the NPU *runtime* needs native arm64 — they are different
     interpreters and neither can do the other's job. DevRel's `install.ps1`
     installs both and builds a separate `.venv-arm64` for the runtime.
   - **CRITICAL — bundle BUILD vs RUN are different hosts.** Producing an
     LLM bundle needs the AI Hub Models exporter (`qai-hub-models`), which pulls
     **`torch` — and torch has NO `win_arm64` wheel.** So a bundle **cannot
     be built on a Windows-arm64 X-Elite at all**, even though that's where
     it RUNS. Build on a non-arm64 host — **WSL on the same X-Elite** (arm64
     Linux *does* have torch wheels), or any x86 / macOS / Linux box — then
     copy `models/<name>/` to the X-Elite. The runtime host needs only
     `onnxruntime-genai` (+ the QAIRT QnnHtp libs). Do NOT list
     `qai-hub-models` as a win-arm64 runtime dep — it will never resolve
     there. (SAGE's `npu_deps.required_packages()` drops it on win-arm64.)
   - **Before provisioning a build host at all — check the registry.** If a
     prebuilt bundle already exists, the X-Elite needs *none* of the export
     toolchain (`qai-hub-models` / `torch` / 64 GB). Call
     `mcp__devrel__aihub_select(action="ensure", model_id=<id>, platform="windows")`:
     it pulls a published bundle (sha256-verified) when one exists, and only
     then do you need the build prerequisites below. See `devrel-build-npu-bundle`.
2. **Target platform** (if a calling skill already knows it, e.g. from
   `devrel-detect` / `hardware_detect`): a remote SSH/ADB board does its
   NPU runtime on-device, so the host only needs `qai-hub` /
   `qai-hub-models` for the export step — note that distinction in the
   plan you present.
   - **CAVEAT — a Linux SoC board does NOT mirror the Windows X-Elite flow.**
     On a Qualcomm Linux SoC (confirmed live on IQ-9075), `pip install
     onnxruntime` / `onnxruntime-qnn` installs cleanly **on-device**, but
     `QNNExecutionProvider` **never actually appears** in
     `get_available_providers()` there — an unverified, non-primary path. Do
     **not** assume the ORT QNN EP is the runtime on a Linux board. The
     confirmed-working path is the **CLI tools** (`qnn-net-run` /
     `snpe-net-run`); cross-link `/devrel-qnn-runtime-debug` for direct execution
     and symbol-level diagnosis when the EP is absent.

## Phase 2 — Inventory what's already present (never fail)

Probe quietly and build a "have / missing" list. Do NOT install yet.

- **AI Hub Models auth:**
  - `QAI_HUB_API_KEY` / `QAI_HUB_API_TOKEN` in the environment.
  - A `QAI_HUB_API_KEY=` line in `.env`.
  - `~/.qai_hub/client.ini` (the SDK's own credential store).
- **pip packages** (use `importlib.util.find_spec`, not import, so a
  broken optional dep doesn't crash the probe):
  ```bash
  python -c "import importlib.util as u; print({n: u.find_spec(n) is not None for n in ['qai_hub','qai_hub_models','onnxruntime','onnxruntime_qnn','onnxruntime_genai']})"
  ```
  (**Packaging changed in `onnxruntime-qnn` 2.x** — see "QNN EP usage"
  below. It is now a *separate* `onnxruntime_qnn` import package that pins
  an exact base `onnxruntime` and ships the Hexagon DLLs alongside it; it
  is **not** a drop-in `onnxruntime` build. Crucially, the QNN EP does
  **NOT** appear in `onnxruntime.get_available_providers()` — that check
  reports `False` even when the NPU works. Probe the NPU with
  `get_ep_devices()` after registering the provider library instead:
  ```bash
  python -c "import os,onnxruntime_qnn as q; os.add_dll_directory(os.path.dirname(q.__file__)); import onnxruntime as o; o.register_execution_provider_library('QNNExecutionProvider', q.get_library_path()); print(any(d.ep_name=='QNNExecutionProvider' and str(d.device.type).endswith('NPU') for d in o.get_ep_devices()))"
  ```)
- **config:** is there an `[adapters.ai_hub]` block in `devrel.toml`?

## Phase 3 — Present the provisioning plan and get approval

**Review-then-apply.** Use `AskUserQuestion` (or a clear summary + a
yes/no) to show exactly what will happen before changing anything:

- **Wheels to install for the detected arch:**

  | Host | Active wheels | Purpose |
  |------|---------------|---------|
  | win-arm64 (X-Elite) | `qai-hub`, `onnxruntime-qnn`, `onnxruntime-genai` | Catalog + Hexagon ONNX-EP + Genie LLM (**no** `qai-hub-models` — torch won't build here) |
  | x86 / other (dev) | `qai-hub`, `qai-hub-models`, `onnxruntime`, `onnxruntime-genai` | Catalog + bundle build + CPU fallbacks |

  **Per-model extras.** `qai-hub-models` is only the catalog base. Each
  model needs its own extras — which pull heavy deps like `transformers`
  and `torch`. **The extra is keyed by the package SLUG, not the friendly
  model id** (e.g. `qai-hub-models[llama-v3-1-8b-instruct]`, NOT
  `qai-hub-models[llama-3.1-8b-instruct]`) — installing the wrong name
  matches no extra and silently installs nothing. The slug is the
  `qai_hub_models.models.<slug>` submodule name with underscores → dashes.
  This is the dep that's missing when you see
  `ModuleNotFoundError: transformers` from a model submodule. As a
  backstop, if an import still fails after installing the extra, install
  the concrete module the `ImportError` names and retry (extras can chain).

- **Env/config writes:** `QAI_HUB_API_KEY` (+ `QAI_HUB_API_TOKEN` alias)
  into `.env`; `[adapters.ai_hub]` ensured in `devrel.toml`; optional
  `qai-hub configure`.
- **For Genie / LLM bundles**, also flag: the Llama/Qwen weights are
  gated — the user must accept the license on Hugging Face and have
  `HF_TOKEN` in their environment, and the export is large (~5 GB).

Only proceed once the user approves. Let them opt out of any single
item (e.g. "skip the wheels, just write the token").

## Phase 4 — Query the AI Hub Models token

If no token is present (or the user wants to change it), ask for the
**Qualcomm AI Hub Models API key**. Treat it as a secret: never echo it back,
never write it to `devrel.toml` or any committed file. Tell the user they
get one at <https://app.aihub.qualcomm.com> (Account → API token).

Skip this phase if a token is already present and the user declines to
replace it.

## Phase 5 — Apply

After approval:

1. **`.env`** — append or update (create from `.env.example` if absent):
   ```bash
   QAI_HUB_API_KEY=<token>
   QAI_HUB_API_TOKEN=<token>   # alias for SAGE-style apps / fetch_llm_model.py
   ```
   Update `.env.example` with blank placeholders for both names (this
   file IS committed). Ensure `.env` is in `.gitignore`.
2. **`devrel.toml`** — ensure:
   ```toml
   [adapters.ai_hub]
   api_key_env = "QAI_HUB_API_KEY"
   base_url = "https://app.aihub.qualcomm.com/api/v1"
   ```
3. **`requirements.txt`** — add the arch-correct NPU wheels. Mirror the
   SAGE layout: the arch-specific wheel as the **active** line, the CPU
   fallback as a **commented** alternative, with a comment explaining
   the split. Example for an X-Elite-targeting app:
   ```
   # AI Hub Models + on-device NPU LLM. onnxruntime-genai is ONE package (its
   # win-arm64 wheel carries the Hexagon support) -- no per-arch split,
   # no onnxruntime-genai-qnn (that name does not exist on PyPI).
   qai-hub
   onnxruntime-genai          # Genie / LLM decode (NPU on win-arm64, else CPU)

   # qai-hub-models is a BUILD-host dep ONLY -- it pulls torch/scipy, which
   # have no win_arm64 wheels, so it will NOT install on an X-Elite. List it
   # only in the build host's requirements (x86 / macOS / WSL), never in the
   # win-arm64 runtime requirements. See "bundle BUILD vs RUN" in Phase 1.
   # qai-hub-models           # build host only (x86/WSL) -- omit on win-arm64

   # Hexagon NPU ONNX EP (win-arm64 only). In onnxruntime-qnn 2.x this is
   # a separate `onnxruntime_qnn` plugin package that auto-pins a matching
   # base `onnxruntime` and ships the QnnHtp DLLs -- see "QNN EP usage".
   onnxruntime-qnn>=1.17.0    # X-Elite Hexagon ONNX Execution Provider
   # onnxruntime>=1.17.0      # x86 fallback (use instead of onnxruntime-qnn)
   ```
   Then install via the app's `run.ps1` (preferred) or directly:
   `python -m pip install -r requirements.txt`.

   **QNN EP usage (onnxruntime-qnn 2.x — verified on X-Elite, 2026-06).**
   The 2.x wheel is **not** a drop-in `onnxruntime` replacement and the EP
   does **not** show up in `get_available_providers()`. It is a *plugin
   execution provider*: register its library, find the NPU device via
   `get_ep_devices()`, then attach it with `add_provider_for_devices()`.
   The old `providers=[('QNNExecutionProvider', {...})]` arg silently falls
   back to CPU. Canonical sequence:
   ```python
   import os, onnxruntime_qnn as q, onnxruntime as o
   os.add_dll_directory(os.path.dirname(q.__file__))   # let the QnnHtp DLLs load
   o.register_execution_provider_library("QNNExecutionProvider", q.get_library_path())
   npu = [d for d in o.get_ep_devices()
          if d.ep_name == "QNNExecutionProvider" and str(d.device.type).endswith("NPU")]
   so = o.SessionOptions(); so.add_provider_for_devices(npu, {})
   sess = o.InferenceSession(model_bytes, sess_options=so)
   # sess.get_providers() -> ['QNNExecutionProvider', 'CPUExecutionProvider']
   ```
   `onnxruntime_qnn` also exposes `get_qnn_htp_path()` / `get_qnn_cpu_path()`
   / `get_qnn_gpu_path()` for the three Qualcomm backends (NPU/CPU/GPU).
4. **`qai-hub configure`** (so the SDK's own credential store is set):
   ```bash
   qai-hub configure --api_token <token>
   ```
5. **Verify** — re-probe imports + token presence and print a status
   table (have/missing for each item). Hand control back to the calling
   skill so the developer workflow continues uninterrupted.

---

## Reference implementation

The SAGE app already implements this pattern end-to-end — use it as the
canonical example (paths relative to `DevRel-Deliverables`):

- `sewa-apps/SAGE/src/npu_deps.py` — background installer for the AI Hub Models
  stack (`qai-hub`, `qai-hub-models`, `onnxruntime-genai`); frozen-build
  no-op, daemon-thread install, status callback.
- `sewa-apps/SAGE/install_prerequisites.bat` — multi-stage installer with
  `[OK]/[WARN]` per stage so an optional dep failing doesn't block the rest.
- `sewa-apps/SAGE/requirements.txt` — the universal-base + arch-comment
  layout to copy for an app's NPU deps.
- `sewa-apps/SAGE/fetch_llm_model.py` — the AI Hub Models token + gated-weight
  download flow (`QAI_HUB_API_TOKEN`, `--download`, verify-only default).

## Model selection UX (apps that run a specific on-device model)

When an app lets the user pick which model runs on the NPU, drive it from
a **catalog with per-model presence**, not a free-text box:

1. **Present a dropdown** of the curated AI Hub Models LLM ids the app supports
   (a small list, not all ~123 catalog extras — only the text LLMs that
   make sense for the app). Keep a single source-of-truth catalog mapping
   `friendly_id → slug → label → gated`; the pip extra is
   `slug.replace("_","-")`.
2. **Show ready/needs-download status per entry** by checking
   `models/<friendly_id>/` for a complete bundle — e.g. render
   `"<id>  ✓ ready"` vs `"<id>  ⬇ needs download"`. The check is just a
   filesystem probe; nothing imports the heavy AI Hub Models packages.
3. **Gate on the in-process NPU provider only.** Server-backed providers
   (`ollama`, `openai_compat`, `npu_openai_compat`) host the model in an
   external server — test the *server* has it, don't check `models/`.
4. **Select → download (if missing) → Test Connection → Save → use.**
   After a successful download, persist the chosen id and flip the row to
   "ready" without a restart; Test Connection should verify the *selected*
   model's bundle specifically, not "any bundle present".

### Two credentials — AI Hub Models token vs Hugging Face token

Downloading a bundle can need **two different secrets**, and they do
different jobs — surface both as saved in-app fields, never as env vars
the user must set out of band:

- **AI Hub Models token** (`QAI_HUB_API_TOKEN` / `QAI_HUB_API_KEY`) —
  authenticates to Qualcomm AI Hub Models for the cloud compile/export. Needed
  for **every** bundle.
- **Hugging Face token** (`HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN`) — the
  exporter pulls the *original* base weights from Hugging Face before
  quantizing. For **gated** models (Llama, Qwen) the user must (a) accept
  the model's license on its HF page and (b) provide an HF token. **Open**
  models (e.g. Falcon3) need no HF token at all.

So mark each catalog entry `gated: true/false`. For gated models, show an
HF-token field and fail early with a precise message if it's missing
(don't let `from_pretrained` throw a deep 403). For open models, hide the
HF field — the AI Hub Models token alone suffices. Persist both tokens to the
app's settings so the user enters them once.

Reference: SAGE's `NPU_LLM_CATALOG` (with the `gated` flag) /
`catalog_models()` / `is_gated()` in `sewa-apps/SAGE/src/npu_llm.py` and
the AI Hub Models token + HF-token fields in `sewa-apps/SAGE/app.py`.

## Notes

- This skill **provisions prerequisites**; it does not pick or download a
  specific model. For browsing/picking an AI Hub Models model, chain into
  `devrel-aihub`; to **build an NPU LLM bundle and stage it onto the
  X-Elite** (the build-host-vs-run-host workflow), use
  `devrel-build-npu-bundle`.
- On a non-arm64 host you cannot run the NPU — that's expected. The CPU
  fallback wheels keep the app importable and runnable so development can
  proceed; the real NPU path lights up when the same app runs on an
  X-Elite.
- **Self-healing at runtime — never surface a `pip install` to the user.**
  An app's runtime code should treat a missing-dep `ImportError` as a
  cue to install in-process and retry, not as a dead end with a copy-paste
  pip command. Pattern: catch `ImportError` → `pip install <spec>` via
  `subprocess` on `sys.executable` → `importlib.invalidate_caches()` →
  re-import → only fail with a clear message if the install itself fails.
  This is the runtime corollary to provisioning here, and matters most for
  the on-demand pieces (per-model `qai-hub-models[<slug>]` extras — keyed
  by slug, not friendly id — and the `onnxruntime-genai` runtime wheel)
  that aren't worth installing for every user up front. Reference:
  `download_bundle` and `_ensure_loaded` in `sewa-apps/SAGE/src/npu_llm.py`.
- **Frozen builds can't self-heal — guard with `sys.frozen`.** In a
  PyInstaller EXE `sys.executable` is the app itself, not Python, so the
  pattern above would relaunch the GUI (a phantom second window) and still
  couldn't add modules to the frozen archive. Early-return when
  `getattr(sys, "frozen", False)` and tell the user the bundle/deps must be
  produced once from source and dropped next to the EXE — disable the
  in-app download affordance rather than letting it no-op. Reference:
  SAGE's frozen guard in `download_bundle` / `_pip_install`.
