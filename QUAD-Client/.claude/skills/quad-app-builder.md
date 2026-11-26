---
name: quad-app-builder
description: Use when the user asks "build an app", "create a QUAD application", "scaffold an inference app", "I want to build a vision/LLM/ASR app on Snapdragon", "create a production inference pipeline", or invokes /quad-app-builder. Guides through the full lifecycle — requirements, implementation, testing, hardening, documentation, and git push.
trigger: "app-builder"
---

# QUAD App Builder — Full Lifecycle Orchestrator

Build a complete, production-ready inference application on Qualcomm
hardware. This skill orchestrates the existing QUAD skills through
8 phases — from gathering requirements to pushing to GitHub.

**Reference app:** `samples/mobilenetv2/run_mobilenetv2.py` — a
complete CPU vs GPU vs NPU benchmark that follows every convention
below.

**The deliverable is a fully tested app, not just code.** Every app
this skill produces MUST include:

1. The application script(s) under `samples/<app_name>/`
2. `requirements.txt` and `run.ps1`
3. `README.md` and `ARCHITECTURE.md`
4. **A pytest test suite under `samples/<app_name>/tests/`** that
   covers smoke import, all helper/preprocessing/postprocessing
   functions, and an end-to-end run on a small fixture input.
5. A clean `pytest -q` run AND a clean end-to-end app run, both
   captured before any commit happens.
6. **A self-contained dependency bootstrap** — see Phase 3.8. The
   app must install or carry every prerequisite it needs (Python
   wheels, native SDKs that ship as wheels, model bundles fetched
   on first launch, gradle/CMake fetched deps). The user runs ONE
   command — `run.ps1`, `install_prerequisites.bat`, double-click
   the EXE, `adb install`, or `quad gwapps deploy` — and gets a
   working app. They do NOT run `pip install …` for missing
   pieces afterward.

**CRITICAL RULE — verify before commit:** You MUST complete Phase 4
(end-to-end verification) with a clean `pytest -q` run AND a clean
end-to-end app run BEFORE proceeding to documentation or git push.
If either fails, fix and re-run until both pass. The user should
never be the one to discover a broken download URL, missing import,
runtime error, or failing test.

**CRITICAL RULE — no manual prerequisite steps:** The README's
"Quick start" section MUST be a single command for the user's
target (`./run.ps1`, double-click `SAGE.exe`, `adb install …`,
`quad gwapps deploy …`). If your README ever asks the user to
manually `pip install <pkg>` to make a feature work, you have
shipped an incomplete app — fix it by either pinning the dep in
`requirements.txt`, bundling it in the EXE/APK/IPK, or wiring an
in-app background bootstrap (see Phase 3.8).

---

## On-device NPU LLM checklist (hard-won — apply to EVERY app with an NPU LLM path)

These are not optional polish. Each line is a bug that has already
shipped and been fixed once; a new app that ignores it will reproduce
the failure. SAGE (`sewa-apps/SAGE`) is the reference implementation
for all of them.

1. **Use `onnxruntime-genai` — NOT `onnxruntime-genai-qnn`.** The `-qnn`
   GenAI distribution **does not exist on PyPI**. There is ONE package,
   `onnxruntime-genai`; its win-arm64 wheel carries the QNN/Hexagon
   support, other platforms get the CPU build. (`onnxruntime-qnn` is a
   *different, real* package — the ONNX Execution Provider wheel for
   embeddings/vision. Don't confuse the two.)
2. **Native arm64 Python is mandatory for the runtime on X-Elite.** A
   Snapdragon X-Elite often runs an *emulated x86-64* Python under Prism,
   where `platform.machine()` returns `AMD64`. The NPU wheels are
   arm64-only and won't load there. Detect it (`machine()=AMD64` while
   `processor()` is Qualcomm/ARM), and have `run.ps1` prefer a native
   arm64 interpreter and auto-recreate a wrong-arch venv. Reference:
   `host_arch_status()` in `npu_llm.py` and SAGE's `run.ps1`.
3. **Two interpreters, two venvs on X-Elite.** QAIRT *conversion* host
   tools need x86_64 Python 3.10; the NPU *runtime* needs native arm64.
   Neither does the other's job — never uninstall one for the other.
   QUAD's `install.ps1` provisions both (`.venv` + `.venv-arm64`).
4. **LLMs use the Genie export path**, not the vision one. Call
   `python -m qai_hub_models.models.<slug>.export --target-runtime genie
   --device "<AI Hub Models device>"` (AIMET quantize → AI Hub Models cloud compile →
   QNN context binary). `export(target_runtime="qnn")` fails on Llama/Qwen
   with "quantized checkpoint must have an ONNX model".
   **Build host ≠ run host:** the exporter (`qai-hub-models`) pulls `torch`,
   which has **no win_arm64 wheel** — so a bundle CANNOT be built on the
   Windows-arm64 X-Elite where it runs. Build on WSL (arm64 Linux has torch
   wheels) or any x86/macOS/Linux box, then copy `models/<name>/` to the
   X-Elite. The runtime install must NOT list `qai-hub-models` on win-arm64.
   **Registry first — don't rebuild what's already built.** Before building,
   call `mcp__quad__aihub_select(action="ensure", model_id=<id>, platform=...)`.
   It detects the host and either **pulls** a prebuilt bundle (sha256-verified,
   unpacked to `models/<id>/` — no build, no torch), or — when this client
   can't build (win-arm64 / not enough RAM) — records a **build job** and
   returns the operator runbook + `job_id`. Run the build on a capable tier,
   then `aihub_select(action="build_status", job_id=…)` until `published` and
   pull. After any local build, `aihub_select(action="publish", …)` so the
   next teammate pulls instead of rebuilding. Full flow: the
   `quad-build-npu-bundle` skill.
5. **Two credentials, both as saved in-app fields (never env-only):**
   the AI Hub Models token (`QAI_HUB_API_KEY`/`QAI_HUB_API_TOKEN`) for every
   bundle, and the Hugging Face token (`HF_TOKEN`) **only for gated
   weights** (Llama/Qwen). Mark each catalog model gated/open; open models
   (Falcon3) need no HF token. Fail early with a precise message, not a
   deep 403.
6. **Per-model extras are keyed by SLUG.** Install
   `qai-hub-models[<slug>]` (e.g. `llama-v3-1-8b-instruct`), NOT the
   friendly id — the wrong name silently installs nothing. Back it with a
   loop that installs whatever module the `ImportError` names.
7. **Self-heal at runtime, but guard `sys.frozen`.** Catch a missing-dep
   `ImportError` → pip-install → `invalidate_caches()` → retry. In a
   frozen EXE this is impossible (`sys.executable` is the app, would
   relaunch the GUI) — early-return and ship the bundle as a drop-in
   `models/<id>/` folder; disable the in-app Download button.
8. **NPU-vs-CPU is a runtime probe, never an assertion.** Detect the
   active EP at load time (`qnn_genai_runtime_available()`), surface it in
   the UI, and fall back to CPU gracefully. Don't claim "runs on NPU"
   from a wheel name.
9. **Catalog-driven model picker** with per-model "✓ ready / ⬇ needs
   download" status (filesystem probe of `models/<id>/`). Gate the
   in-process NPU provider on `models/`; server providers test the server.

The single source of truth for provisioning all of this is the
`quad-npu-prereqs` skill — invoke it rather than re-deriving the rules.

---

## Supported Target Platforms

| ID | Platform | SoC | NPU | TOPS | Hexagon | Interface | SDK |
|----|----------|-----|-----|------|---------|-----------|-----|
| `windows-x-elite` | Windows AI PC | Snapdragon X Elite (X1E-80-100) | Hexagon V75 (HTP) | 45 | v75 | Local | QNN 2.x |
| `unoq` | Arduino UNO Q | QCS2210 | Hexagon DSP V66 | 1.0 | v66 | SSH | SNPE 2.x |
| `rubio-pi` | Rubio Pi (RB3 Gen 2) | QCS6490 | Hexagon V69 (HTP) | 12.0 | v69 | SSH | QNN 2.x |
| `iq-9075` | Dragonwing IQ-9075 EVK | QCS9075 | Hexagon HTP V73 | 100 | v73 | **SSH (default, ~95% of workflows) — ADB is a bootstrap-only fallback before Wi-Fi is up; see profile below** | QNN 2.x — **NPU works via one specific path (2.47.0+ image); GPU blocked on any image tested; see profile below** |
| `android-8elite` | Android Phone/Tablet | Snapdragon 8 Elite (SM8750) | Hexagon V79 (HTP) | 45 | v79 | ADB | QNN 2.x / SNPE 2.x |
| `rb5` | Robotics RB5 | QCS8250 | Hexagon V68 (HTP) | 15 | v68 | SSH | QNN 2.x |
| `ai-gateway` | **AI Gateway** (IPQ-class WLAN) | Qualcomm IPQ9574 | Hexagon NSP | ~8 | NSP | SSH (via LCM) | gwapps SDK / NWAIOS |
| `custom-linux` | Custom Linux Board | User-specified | User-specified | — | — | SSH | User-specified |

### Target Profiles

Each target has specific constraints and capabilities that shape the
entire build pipeline:

#### Arduino UNO Q (`unoq`)
- **RAM:** 2 GB — models must stay under ~500 MB loaded
- **NPU:** DSP V66, INT8 only (FP32 falls back to CPU)
- **Interface:** SSH (configure via `/quad-unoq configure`)
- **Build:** Cross-compile ARM64 or Python over SSH
- **Deploy:** `scp` + `snpe-net-run --use_dsp`
- **Skel:** `libSnpeDspV66Skel.so`
- **Power envelope:** <2W sustained
- **Use cases:** Always-on sensing, keyword detection, tiny classifiers
- **Reference:** `/quad-unoq` skill for board management

#### Rubio Pi / RB3 Gen 2 (`rubio-pi`)
- **RAM:** 8 GB — can handle medium models (up to ~2 GB)
- **NPU:** HTP V69, INT8 + INT16 + FP16
- **Interface:** SSH (same pattern as UNO Q but more capable)
- **Build:** Cross-compile ARM64 or native compile on device
- **Deploy:** `scp` + `qnn-net-run` or native app
- **Skel:** `libSnpeHtpV69Skel.so` / `libQnnHtpV69Skel.so`
- **Power envelope:** <5W sustained
- **Use cases:** Vision pipelines, LLM at 1-3B params, multi-model orchestration, robotics
- **Cloud profiling:** Available via AI Hub Models as "QCS6490 (Proxy)"
- **Reference:** Same SSH patterns as `/quad-unoq`

#### Dragonwing IQ-9075 EVK (`iq-9075`)

**⚠️ This board's software state is not fixed — it has been observed in
two materially different states (different OS image, different NPU/GPU
status) on the same physical unit. Always run `qnn-net-run --version`
(or `scripts/board_profile.py detect`) before assuming which state you're
in — do not assume from this doc alone. Transport, however, IS settled:
prior investigation validated SSH as the default connection for this
board, consistent with Qualcomm Linux (QLI)'s own intended design once
the board is on Wi-Fi — see the Transport note below.**

| | QLI 1.6 (original factory image) | QLI 2.0 (after a board reflash) |
|---|---|---|
| On-device QAIRT/QNN | 2.38.0 | 2.47.0 (or newer — 2.48.40 confirmed to behave identically for GPU) |
| Root FS | `/usr` read-only, no pip, no internet | Fully writable, internet works, `pip3 install` works |
| Reachable transport | **ADB only** (USB-C; DIAG/QDSS have no Windows driver; board not yet on Wi-Fi) | **SSH/Wi-Fi confirmed working (the validated, default path)**; ADB still works over USB as a bootstrap fallback |
| NPU via `qnn-net-run` + pre-compiled artifact | Blocked — AI Hub compiles for QAIRT ≥2.45, this image is 2.38.0 | **Works** — 2.47.0+ clears AI Hub's compile floor |
| NPU/GPU via `onnxruntime_qnn` plugin EP | Blocked | **Still blocked** — different bug, unaffected by the QAIRT bump |
| GPU via `qnn-net-run`/`qairt-net-run` + DLC | Not meaningfully testable (blocked by the same QAIRT wall as NPU) | **Blocked for a different, driver-specific reason** — see below |

**Transport (settled): SSH is the default and validated path for this
board — ~95% of workflows go this way once the board has Wi-Fi
configured, matching Qualcomm Linux's own intended design rather than a
USB-tethered workflow. Store connection details in `.env_boards` (copy
from `.env_boards.example` at the repo root; gitignored, never
committed) instead of hardcoding IP/credentials per script.
`scripts/board_profile.py`'s `iq-9075` profile defaults `--transport` to
`ssh` accordingly. ADB is retained as a **bootstrap-only fallback** — the
one legitimate case is a freshly flashed board that isn't on Wi-Fi yet;
once SSH is reachable, prefer it. If ADB is needed, on-device
`android-tools-adbd.service` requires the marker file
`/etc/usb-debugging-enabled` to exist (absent on every fresh flash/reflash
by design — not a bug): `touch /etc/usb-debugging-enabled && systemctl
start android-tools-adbd.service` before `adb devices` will see the
board.**


**RAM:** 33.8–35.3 GB depending on image — ample for anything up to a mid-size vision model.
**NPU:** Hexagon HTP V73, ~100 dense TOPS — confirmed via on-device `dsp_skel` and user-provided datasheet spec.
**GPU:** Adreno 663 — confirmed real and present (`/dev/kgsl-3d0`, `gpu_model` sysfs), exposed via the `kgsl` kernel interface, **not** DRM — this is *why* the generic `onnxruntime`-discovery blocker below applies to GPU too, not just NPU.

**Physical USB topology (hardware fact, applies to both OS images):**
the board exposes three USB ports, not one. **USB0** (USB-C, 3.1 Gen 2)
is the one everything in this doc uses — on Windows it enumerates as 3
composite interfaces (VID `05C6`): MI_00 (DIAG, `CM_PROB_FAILED_INSTALL`
— no driver on Windows, expected, ignore it), MI_01 (QDSS trace, same
story), and MI_02 (**ADB, WinUSB-bound, works immediately** — this is
the bootstrap-fallback interface, useful before Wi-Fi/SSH is up).
Confirm with `Get-PnpDevice | Where-Object {
$_.InstanceId -match 'VID_05C6' }` — the ADB interface should show
`Status: OK`; DIAG/QDSS showing `Error` is correct and expected, not a
problem to fix. **USB1** (USB-C) is host-mode only, not used for
bring-up. **USB2** (Micro-USB) doubles as a debug/"alpaca" UART
(`/dev/ttyUSB*` on the host) — a serial-console fallback for initial
Wi-Fi setup or if both SSH and ADB become unreachable; default on-device
login for that path is `root`/`oelinux123`. Not needed once SSH is
configured, but know it exists before assuming a silent board is bricked.

**Two dead ends, already investigated — do not re-attempt these:**
existing `samples/mobilenetv2/` (the X-Elite CPU/GPU/NPU sample) has
nothing IQ-9075-specific to reuse — its `.onnx`/DLC artifacts and
conversion scripts are generic, not compiled for this SoC. Separately,
if this repo's own connected MCP server is available, it will NOT help
compile a QAIRT-2.38.0-compatible artifact either — its own bundled
QAIRT (confirmed 2.41.0 in an earlier session) is still *newer* than
QLI-1.6-class devices' 2.38.0 runtime, the same directional mismatch as
AI Hub, just a smaller gap. Full detail:
`export_assets/mobilenet_v2_iq9075_qnn/SAMPLES_AND_MCP_SERVER_EXPLORATION_IQ9075.md`.

**Two structurally independent NPU/GPU code paths — do not conflate their status:**

1. **`qnn-net-run` (or `qairt-net-run`) + a pre-compiled QNN context binary or DLC.** This is the path that actually works for NPU on a QLI 2.0-class image (QAIRT ≥2.45). A `.bin` context binary is **NPU-only by design** (confirmed via AI Hub's own docs — "the context binary is designed only for the NPU"); a `.dlc` is device-agnostic and can be loaded against any backend at run time via `qairt-net-run --input_dlc <f> --use_htp|--use_gpu|--use_cpu`, or via the lower-level `qnn-net-run --dlc_path <f> --backend <lib.so>`. **On QLI 1.6-class images (QAIRT <2.45), this entire path is blocked** by a one-directional compiler/runtime version wall — AI Hub will not compile for a runtime that old, and there is no in-place fix short of a board reflash. **For GPU specifically, this path is blocked on every QLI 2.0-class image tested (QAIRT 2.47.0 AND the newest available release, 2.48.40)** by a *different* problem: `libQnnGpu.so` requires OpenCL extension symbols (`clGetDeviceImageInfoQCOM`, `cl_khr_semaphore` family, and others) that the board's installed Adreno OpenCL driver does not export — confirmed via `LD_DEBUG=libs` symbol-level tracing, not inferred from the (generic, misleading) `QNN_BACKEND_ERROR_CANNOT_INITIALIZE`/`GPU_ERROR_DOES_NOT_EXIST` error text alone. The GPU hardware, kernel driver, and OpenCL runtime are all independently confirmed working — this is a driver/SDK version gap, and there is no package-manager or OTA-firmware channel reachable from a Windows client to update it (checked: no `opkg`, `dnf` has zero configured repos, `fwupd`/LVFS doesn't track a GPU component on this platform). **Do not re-attempt fixing this without new information — see `GPU_INVESTIGATION_IQ9075.md` for the full, already-exhausted diagnostic trail before spending time on it again.**
2. **`onnxruntime_qnn` Python plugin EP** (what a plain `providers=["QNNExecutionProvider"]` or the newer `get_ep_devices()`-based API exercises). This registers successfully but **never surfaces an NPU or GPU device** — `onnxruntime`'s own Linux hardware-discovery code (`device_discovery.cc`) expects a DRM node with a `vendor` sysfs file; this board's only DRM node (`card0`) is the *display* controller, not a GPU, and the Hexagon NPU is exposed via `/dev/fastrpc-*` instead — a convention this discovery code doesn't recognize. **This is structurally unfixable from a client, not merely "not yet fixed": the failing code lives inside the `onnxruntime` pip package itself, not in QAIRT** — confirmed by direct file-path inspection, and reconfirmed with the newest QAIRT SDK available (2.48.40) having no effect, exactly as that structural fact predicts. No newer `onnxruntime`/`onnxruntime-qnn` release exists to try, and `onnxruntime`'s device objects (`OrtHardwareDevice`/`OrtEpDevice`) have no public constructor, so there is no manual override path either. **Do not spend time trying to fix path 2 — treat it as permanently blocked on this board and use path 1 instead.**

**What DOES work today, and how to get it, depending on image:**
- **CPU (both images):** via a manually-installed `onnxruntime` on QLI 1.6 (no pip — extract wheel locally, tarball it, `adb push`, extract on-device into a writable `/data/local/tmp/...` dir, run with `PYTHONPATH` set), or via plain `pip3 install onnxruntime` on QLI 2.0 (internet + writable rootfs). **The onnxruntime version materially changes the latency number** — verified, not noise: 14.85ms mean (v1.22.1) vs 6.14ms mean (v1.24.2) on QLI 1.6, and ~6.1ms mean (v1.27.0) on QLI 2.0, all for the same MobileNetV2 fp32 model. Always state the onnxruntime version alongside any latency number for this board.
- **NPU (QLI 2.0-class images only):** via `qnn-net-run --retrieve_context <model.bin> --backend /usr/lib/libQnnHtp.so --input_list <f> --output_dir <d> --profiling_level client`, then parse real latency out of `qnn-profile-viewer --input_log <output_dir>/qnn-profiling-data*.log`. Measured, reproducible across 9+ independent runs spanning multiple sessions: **1.98–3.18ms mean, ~290–500 FPS**, correctness-verified against a CPU baseline on a real photo (not this board's own synthetic test fixture — see the correctness pitfall below). **Input contract for a context binary/DLC is NHWC float32, `[0,1]`-range** — check the artifact's own `metadata.json` rather than assuming the NCHW/ImageNet-normalized contract that the CPU/plugin-EP paths use; feeding the wrong format won't error, it will silently produce a plausible-looking but numerically wrong result.
- **GPU:** not working via any path tried, on any image tested. Do not attempt without first reading `GPU_INVESTIGATION_IQ9075.md` in full.

**A correctness-verification pitfall specific to this board — avoid repeating it:** an early correctness check compared NPU vs. CPU output using this repo's own `test_input.jpg` fixture and a weak "do the top-5 lists overlap" metric. That image is a **synthetic placeholder** (a flat sky/field gradient with a solid tan circle, not a photograph of any real object) — there is no ground truth to check against, and it briefly produced a false-alarm-looking disagreement between two genuinely correct backends (which, it turned out, are also comparing against two *different trained checkpoints* of the same architecture — AI Hub's own catalog model vs. an ONNX Model Zoo export — so some numeric disagreement is expected even on a real photo). **Always use a real photo with unambiguous ground truth for any correctness check on this board**, and compare *argmax*, not list overlap.

**Build/Deploy:** do NOT hand-roll adb/ssh push or detect logic — reuse `scripts/board_profile.py` (`detect`/`push`/`profile`/`report` subcommands, `--transport adb|ssh` — defaults to `ssh` for `iq-9075`, override with `--transport adb` only for the pre-Wi-Fi bootstrap case, `--board iq-9075`). It already encodes the tarball-push workaround for adb (plain `adb push` of a multi-file directory crashes with `libc++abi: ... std::bad_alloc` on this board's adb client; tarring first and extracting on-device with `tar` works reliably) and the correct `PYTHONPATH`-based on-device Python invocation. **Note:** `board_profile.py`'s `profile` subcommand predates the QLI 2.0 findings above — it knows the `--retrieve_context` shape but not `--dlc_path`/`--use_gpu`/`--use_htp`, `--profiling_level client` + `qnn-profile-viewer` parsing, or the NHWC input-format requirement. For a from-scratch app targeting this board's NPU today, follow `samples/mobilenetv2_iq9075/deploy/inference.py`'s `attempt_qnn_context_binary()` function as the current reference implementation instead of the script's CLI profiling path.
**Skel:** `libQnnHtpV73Skel.so` (present on both images, confirmed) — reachable via the `qnn-net-run`+artifact path on QLI 2.0-class images; unreachable on QLI 1.6-class images for the version-wall reason above.
**Power envelope:** not measured this session.
**Use cases:** industrial/embedded IoT vision and classification workloads. On a QLI 2.0-class image, this is now a genuinely NPU-capable target for that class of workload (via the `qnn-net-run`+artifact path) — GPU acceleration remains unavailable pending a Qualcomm driver update this project cannot self-provide.
**Reference:** `scripts/board_profile.py` for generic board interaction; `samples/mobilenetv2_iq9075/` for the reference app; the `quad-qnn-runtime-debug` skill for the actual `qnn-net-run`/`qairt-net-run` execution and backend-failure-diagnosis procedure (use this if a QNN artifact fails to load or a backend won't initialize — don't re-derive the diagnosis from scratch); `export_assets/mobilenet_v2_iq9075_qnn/SOP_IQ9075_BOARD_BRINGUP.md` for the full physical bring-up procedure (USB identification, troubleshooting table, on-device setup) if bringing up a new/another unit of this board; `export_assets/mobilenet_v2_iq9075_qnn/FULL_RETROSPECTIVE_IQ9075.md` for the complete story of why this took the investigation it did, if you want the full context before building on this board again.

#### Windows AI PC (`windows-x-elite`)
- **RAM:** 16-32 GB — large models OK
- **NPU:** HTP V75, INT8 + INT16 + FP16
- **Interface:** Local execution
- **Build:** Native build, Python venv, or CMake + Visual Studio
- **Deploy:** Local — no file transfer needed
- **Power envelope:** 15-45W (laptop TDP)
- **Use cases:** Development, LLMs up to 7B, real-time video, multi-model
- **Reference:** Default target for most samples

#### Android (`android-8elite`)
- **RAM:** 12-16 GB
- **NPU:** HTP V79, INT8 + INT16 + FP16
- **Interface:** ADB (USB or WiFi)
- **Build:** Kotlin/Java (Android Studio) or C++ (NDK)
- **Deploy:** `adb push` + `adb shell` or APK install
- **Skel:** `libSnpeHtpV79Skel.so`
- **Use cases:** Mobile apps, camera pipelines, on-device LLM

#### Robotics RB5 (`rb5`)
- **RAM:** 8 GB
- **NPU:** HTP V68, INT8 + FP16
- **Interface:** SSH
- **Build:** Cross-compile or native on device
- **Skel:** `libSnpeHtpV68Skel.so`
- **Use cases:** Drones, autonomous robots, edge gateways

#### AI Gateway (`ai-gateway`)
- **RAM:** ~1 GB (resource-constrained — typical disk-loaded models ≤ 256 MB)
- **NPU:** Hexagon NSP (no exposed GPU)
- **Quantization:** INT8 + FP16; INT8 strongly preferred for energy
- **Interface:** SSH; **deploy is LCM-driven IPK install** (not bare `scp + run`)
- **Build:** Cross-compile via the gwapps toolchain — `quad gwapps build` (Phase 4)
- **Deploy:** `quad gwapps deploy <ipk> --host <gw>` (Phase 5; mock + SSH-ready)
- **Profile:** `quad profile_workload --platform=gateway --runtime=npu` reads
  `nwaios_app_stats` from the running app (Phase 6, NWAIOS-shaped report)
- **OS targets:** OpenWrt / prplOS / RDK on aarch64 (or arm 32-bit legacy)
- **Power envelope:** ~3 W typical sustained
- **Use cases:** WLAN traffic anomaly detection, smart traffic classification,
  always-on edge ML at the home/enterprise gateway boundary
- **SDK:** Licensed gwapps SDK delivered via QPM3
  (`qpm-cli --install qualcomm_gwapps_sdk`); QUAD vendors a pinned version
  under `QUAD_Packages/gwapps/<ver>/` and validates ABI via
  `quad doctor --section gwapps`
- **Programming model:** C app linking `libnwaios` + `libGwAppstransport`;
  `nwaios_lib_init → model_load → execute → unload → lib_deinit` lifecycle
- **Reference:** `docs/QUAD_GWAPPS_INTEGRATION_PLAN.md`,
  `docs/GWAPPS_INTEGRATION.md`, `docs/QUAD_GWAPPS_PROGRESS.md`

#### Custom Linux Board (`custom-linux`)
- User provides: hostname, SSH creds, Hexagon version, SDK path
- Falls back to generic SSH deploy pattern

---

## Phase 1 — Requirements & Planning

Before writing any code, gather requirements from the user. Use
`AskUserQuestion` to collect all of these:

### Required information

| Question | Options | Why |
|----------|---------|-----|
| **What ML task?** | classification, detection, segmentation, LLM, ASR, custom | Determines preprocessing/postprocessing |
| **What model?** | path to ONNX, model name from zoo, or "help me choose" | Input to convert_model |
| **Target platform?** | Two-step picker — see "Target platform picker" below | Drives codegen, build, and deploy pipeline |
| **App type?** | Python script, Native C++, Native C (AI Gateway), Arduino sketch (.ino), Kotlin/Android | Drives codegen language param |
| **Preferred runtime?** | NPU (default), GPU (Adreno), CPU, auto | Backend selection |
| **Quantization?** | FP32 (default), INT8, INT4 | See "Quantization choice" below |
| **Latency target?** | e.g. "<10ms", "real-time 30fps", "best effort" | Drives quantization and power mode |
| **Power constraint?** | performance, balanced, efficiency | Orchestration mode |
| **Input source?** | file, camera, HTTP endpoint, microphone, sensor, network packets (AI Gateway) | Shapes app architecture |
| **Output format?** | console, JSON, HTTP response, file, actuator, MQTT topic (AI Gateway) | Shapes postprocessing |

### Target platform picker — two-step (mandatory)

`AskUserQuestion` only allows 4 options per question. We support 7
platforms, so asking the target as a single question forces the model
to bucket platforms together — and AI Gateway gets buried under
"Other". To prevent that, ALWAYS ask the target platform as two
questions:

**Step 1 — Form factor.** Ask exactly these 4 options, in this order:

| Option | Maps to (resolved in Step 2) |
|--------|-------------------------------|
| Windows AI PC | `windows-x-elite` |
| AI Gateway (IPQ-class WLAN) | `ai-gateway` |
| Mobile (Android) | `android-8elite` |
| IoT / Embedded SBC | `unoq` / `rubio-pi` / `rb5` / `iq-9075` / `custom-linux` |

The first three options resolve directly — **do NOT ask Step 2** if
the user picks "Windows AI PC", "AI Gateway", or "Mobile (Android)".

**Step 2 — (only if Step 1 = "IoT / Embedded SBC")** drill down:

| Option | Maps to |
|--------|---------|
| Arduino UNO Q (QCS2210) | `unoq` |
| Rubio Pi / RB3 Gen 2 (QCS6490) | `rubio-pi` |
| Robotics RB5 (QCS8250) | `rb5` |
| Dragonwing IQ-9075 EVK (QCS9075) | `iq-9075` |

This guarantees AI Gateway and Mobile each get their own first-class
top-level slot, and IoT boards (UNO-Q, Rubio Pi, RB5, IQ-9075) are
surfaced together rather than collapsed under "Other".

**Why "Custom Linux Board" isn't in the list above:** `AskUserQuestion`
hard-caps at 4 explicit options per question (confirmed against the
tool's own schema — `maxItems: 4`), and this drill-down already has 4
named boards. The tool always offers an automatic "Other" free-text
slot beyond the listed options — a user with a genuinely custom board
selects "Other" and types their board name, which still resolves to
`custom-linux`. Do not try to cram a 5th explicit option in here.

### Target-specific follow-ups

After the user picks a target, ask follow-ups based on the platform:

**If `unoq` or `rubio-pi` or `rb5` or `custom-linux`:** (SSH-based boards)
- "What is the board's IP address or hostname?"
- "SSH username?" (default: `root`)
- "SSH key path?" (default: `~/.ssh/id_rsa`)
- "Is the SNPE/QNN SDK already installed on the device?"

**If `iq-9075`:** (SSH is the default, validated transport — ~95% of workflows; ADB is only a bootstrap fallback before Wi-Fi is up)
- "What is the board's IP address?" (default user `root`, default password `oelinux123` unless changed — store in `.env_boards`, copied from `.env_boards.example`, rather than hardcoding it)
- If the board isn't on Wi-Fi yet (fresh flash, no SSH reachable): "Is the board reachable over ADB (USB) as a bootstrap step? (`adb devices`)" — get it onto Wi-Fi via `docs/IQ9075_SOPs.md`, then switch to SSH for everything else.
- Regardless of transport, run `qnn-net-run --version` (over whichever transport works) before assuming NPU status — QAIRT <2.45 means the NPU-via-context-binary path is blocked (compiler/runtime version wall); QAIRT ≥2.45 means it works. Tell the user up front either way:
  - **If QAIRT ≥2.45:** "This board's on-device QAIRT (X.X.X) supports NPU inference via a pre-compiled context binary or DLC — this app will benchmark CPU and NPU for real. GPU is a separate, currently-blocked path on every image tested (a driver/SDK compatibility gap) — see `GPU_INVESTIGATION_IQ9075.md` before spending time on it."
  - **If QAIRT <2.45:** "NPU/GPU profiling on this board's current image is a known, documented limitation (QAIRT compiler/runtime version wall) — this app will benchmark CPU for real and report the exact reason NPU/GPU isn't available, not fabricate numbers. A board reflash to a newer OS image is the only known fix. See `NPU_GPU_INVESTIGATION_IQ9075.md` for the full writeup."
  - **In either case**, do not attempt the `onnxruntime_qnn` plugin-EP path expecting it to work for NPU/GPU auto-dispatch — it is blocked by a separate, permanent bug inside `onnxruntime` itself, unrelated to QAIRT version. Use the `qnn-net-run`+artifact path for real NPU acceleration.

**If `ai-gateway`:**
- "What is the gateway's hostname or IP?" (or set `GATEWAY_HOST` env var)
- "Cross-compile target arch?" — `aarch64-openwrt-linux` (default),
  `aarch64-prpl-linux`, `aarch64-rdk-linux`, or `arm-openwrt-linux`
- "Is the gwapps SDK installed?" — confirm with
  `quad doctor --section gwapps`. Install via
  `qpm-cli --install qualcomm_gwapps_sdk` if not.
- "Which license features does this app need?" — list NWAIOS feature IDs
  (Smart Traffic Classifier, Anomaly Detection, etc.)
- "Compute engine?" — `nsp` (default; Hexagon NSP) or `cpu` (fallback)
- "Is `lcmd` running on the gateway?" — required for IPK install + start

**If `android-8elite`:**
- "Is ADB connectivity established? (`adb devices` shows the device?)"
- "NDK version?" (for C++ apps)

**If `unoq`:**
- "Is this for always-on/low-power sensing or burst inference?"
  (drives perf_profile choice: `low_balanced` vs `burst`)

**If `rubio-pi`:**
- "Is this for a robotics pipeline (multi-model, sensor fusion) or
  single-model inference?"
- "Do you need real-time guarantees (< 33ms per frame)?"

**Any Snapdragon NPU target (all of the above) — provision prerequisites
early.** If the app will use AI Hub Models models or the Hexagon NPU runtime,
invoke the `quad-npu-prereqs` skill during Phase 1/2 so the **AI Hub Models API
token is queried up front** (not discovered at runtime) and the
arch-correct NPU wheels are scheduled for the app's `requirements.txt`.
Getting the token now avoids a stall at the convert/download step later.

### Quantization choice — read this verbatim to the user before they pick

When you ask the quantization question, present these trade-offs in
the question's `description` so the user can make an informed choice:

| Mode | When to use | Conversion time | Calibration data needed | Runs on |
|------|-------------|-----------------|------------------------|---------|
| **FP32** (default) | First-time conversion; any model with no calibration audio/images on hand; Transformer encoders (Whisper, BERT) | ~30 s for 30 MB model | None | NPU + GPU + CPU |
| **INT8** | Production deploys where you have a calibration dataset (≥ 32 representative samples) and need 2-4× lower latency | 1-3 min on CNNs with calibration; **hangs indefinitely on Transformers without real calibration data** | Yes — real samples, NOT random | NPU + CPU |
| **INT4** | Aggressive size/latency reduction; LLMs only; needs AIMET PTQ + a calibration set | 5-15 min | Yes — real samples | NPU only |

**Target-specific quantization guidance:**

| Target | Recommended | Reason |
|--------|-------------|--------|
| `unoq` | INT8 mandatory for DSP | V66 DSP only runs INT8; FP32 falls back to CPU (10x slower) |
| `rubio-pi` | INT8 or FP16 | V69 HTP supports both; INT8 for best latency |
| `windows-x-elite` | FP32 or INT8 | Start FP32, quantize later for production |
| `android-8elite` | INT8 | Best mobile latency/power trade-off |
| `rb5` | INT8 or FP16 | V68 HTP supports both |
| `iq-9075` | **FP32** (CPU always works; NPU works if the board's QAIRT is ≥2.45 — check first) | Precision choice for NPU is unaffected by the blockers on this board (they're at the container-format/discovery level, before precision matters) — FP32 is the safe default either way. GPU is blocked regardless of precision on every image tested — see profile above. |
| `ai-gateway` | INT8 | NSP supports INT8/FP16; INT8 cuts power ~2× and matches the gateway's tight envelope |

**Strong recommendation:** start with FP32 unless the user explicitly
requests quantization AND has a calibration dataset. Exception: for
`unoq`, recommend INT8 upfront since DSP V66 requires it for useful
performance.

If the user picks INT8/INT4, ask:
- "Do you have a calibration dataset? (≥ 32 representative inputs as
  numpy arrays, .raw files, or a directory of images/audio?)"
- If no: warn explicitly that the conversion will hang on
  Transformer-style models and recommend FP32 first, then revisit
  quantization once they have calibration data.

### Model size validation for target

Before proceeding, validate the model fits the target:

| Target | Max model (loaded) | Max model (disk) | Action if exceeded |
|--------|-------------------|-------------------|-------------------|
| `unoq` | ~500 MB | ~200 MB | Suggest smaller model or aggressive quantization |
| `rubio-pi` | ~2 GB | ~1 GB | Suggest INT8 or model pruning |
| `windows-x-elite` | ~8 GB | ~4 GB | Proceed normally |
| `android-8elite` | ~4 GB | ~2 GB | Suggest INT8 |
| `rb5` | ~2 GB | ~1 GB | Suggest INT8 or model pruning |
| `iq-9075` | ~30 GB (35.3 GB RAM, generous) | ~10 GB (99 GB free on rootfs) | Proceed normally for model size; the real constraint is the NPU/GPU blocker, not RAM/disk |
| `ai-gateway` | ~512 MB | ~256 MB | Aggressive INT8 + smaller model class; gateways are RAM-constrained |

### Generate the plan

After collecting answers, produce a **phased implementation plan**
as a numbered markdown checklist. The plan MUST include target-specific
steps. Example for UNO Q:

```markdown
## Implementation Plan: MobileNetV2 Classifier on Arduino UNO Q

1. [ ] Verify model download URLs are reachable
2. [ ] Detect hardware via SSH (quad-detect --platform linux)
3. [ ] Convert model to INT8 DLC (SNPE, calibration required for DSP V66)
4. [ ] Write application code (Python or C++ cross-compiled for ARM64)
5. [ ] Create run.ps1 + requirements.txt (host-side tooling)
6. [ ] Write pytest test suite under tests/
7. [ ] Cross-compile / package for target
8. [ ] Deploy to board via SSH (quad-unoq deploy)
9. [ ] Run on-target smoke test
10. [ ] Performance KPI validation (quad-unoq perf)
11. [ ] Stability soak test — 1 hour (quad-unoq stability)
12. [ ] Power profiling (quad-unoq power)
13. [ ] Generate ARCHITECTURE.md
14. [ ] Final verification gate
15. [ ] Commit and push
```

Present the plan and get user approval before proceeding.

---

## Phase 2 — Discovery & Pre-flight Checks

### 2.1 Hardware detection

Invoke the `quad-detect` skill:
- Call `mcp__quad__hardware_detect` with the target platform
- Show the device table with CPU/GPU/NPU specs
- Note `gpu_backend_available` status

**For remote SSH targets (unoq, rubio-pi, rb5, custom-linux, and iq-9075 — SSH is the default transport for iq-9075 too, see its own block below):**
```bash
# Verify SSH connectivity first
ssh -o ConnectTimeout=5 <user>@<board-ip> "echo ALIVE"

# Detect hardware on remote board
ssh <user>@<board-ip> "cat /proc/cpuinfo | head -20 && free -m"
```

### 2.2 Validate all external URLs BEFORE writing code

**This step is mandatory.** For every URL the app will download from
(model files, labels, test data), verify reachability now:

```bash
# HEAD request — checks URL exists without downloading the full file
curl -sfSL -o /dev/null -w "%{http_code}" --head "<URL>"
```

- **If 404/403:** Find the correct URL immediately. For Hugging Face
  models, check the repo file listing via the API:
  `https://huggingface.co/api/models/<org>/<model>` — the JSON
  response includes a `siblings` array with every file path.
- **If redirected:** Follow redirects and use the final working URL.
- **If the model is gated:** Warn the user they need to accept the
  license on Hugging Face and pass a token.

Only proceed to implementation once every URL returns 200.

### 2.3 Target-specific pre-flight

**For `unoq`:**
```bash
ssh <user>@<board-ip> "ls /usr/lib/rfsa/adsp/libSnpeDspV66Skel.so"
ssh <user>@<board-ip> "df -h / | tail -1"  # Check free space
ssh <user>@<board-ip> "free -m | grep Mem"  # Check available RAM
```

**For `rubio-pi`:**
```bash
ssh <user>@<board-ip> "ls /opt/qnn/lib/libQnnHtpV69Skel.so 2>/dev/null || \
                       ls /usr/lib/rfsa/adsp/libSnpeHtpV69Skel.so"
ssh <user>@<board-ip> "cat /proc/device-tree/model 2>/dev/null"
```

**For `android-8elite`:**
```bash
adb devices  # Must show device
adb shell "cat /proc/cpuinfo | grep Hardware"
adb shell "ls /vendor/lib64/libSnpeHtpV79Skel.so 2>/dev/null"
```

**For `rb5`:**
```bash
ssh <user>@<board-ip> "ls /opt/qnn/lib/libSnpeHtpV68Skel.so"
```

**For `iq-9075`:** (SSH is the default, validated transport — see Target Profiles above; ADB below is bootstrap-only, for a board not yet on Wi-Fi)
```bash
# ssh transport (default — QLI 2.0-class images, board on Wi-Fi)
ssh -o ConnectTimeout=5 root@<board-ip> "echo ALIVE && qnn-net-run --version"

# adb transport (bootstrap fallback only, before Wi-Fi/SSH is up)
adb devices
adb -s <serial> shell "qnn-net-run --version"   # <2.45 = NPU blocked; >=2.45 = NPU works
```
Prior investigation validated SSH as the recommended, default flow for this board — it concurs with Qualcomm Linux (QLI)'s own intended design once the board is on Wi-Fi. Try SSH first; fall back to ADB only if the board isn't on Wi-Fi yet.

**For `ai-gateway`:**
```bash
# 1. SDK + manifest pin reachable on the dev box?
quad doctor --section gwapps     # five-check baseline (presence, headers,
                                  # ABI hash match, libs per arch, toolchain)

# 2. Gateway reachable + lcmd running?
ssh <user>@<gateway-ip> "echo ALIVE && pgrep lcmd >/dev/null && echo LCMD_OK"

# 3. License-lib feature mask
ssh <user>@<gateway-ip> "cat /etc/softsku-qwin-agent/softsku_feature_list.conf | head"

# 4. Free disk + RAM
ssh <user>@<gateway-ip> "df -h /tmp && free -m"
```

If `quad doctor --section gwapps` fails: `qpm-cli --install qualcomm_gwapps_sdk
--version <ver>` (or place a bundle under `QUAD_Packages/gwapps/` and run
`scripts/adapters/setup_gwapps.sh`).

### 2.4 Validate model (if user already has an ONNX file)

```python
import onnx
model = onnx.load(model_path)
onnx.checker.check_model(model)
input_shape = model.graph.input[0].type.tensor_type.shape
```

If the model has dynamic shapes or Gather/Concat constant subgraphs,
apply `onnxsim` simplification (same pattern as mobilenetv2 sample).

---

## Phase 3 — Implementation

### 3.1 Convert the model

Invoke the `quad-convert` skill:
- Call `mcp__quad__convert_model` with:
  - `source_format` from Phase 1
  - `quantization` — see target-specific guidance above
  - `target_sdk`:
    - `unoq`, `rb5`: "snpe"
    - `rubio-pi`: "qnn" (preferred) or "snpe"
    - `windows-x-elite`: "qnn"
    - `android-8elite`: "qnn" or "snpe"
  - `input_dimensions` from model validation
- Capture `output_path`, `supported_ops_pct`, `unsupported_ops`

**Target-specific conversion notes:**

| Target | SDK | Quantization | Output format | Notes |
|--------|-----|--------------|---------------|-------|
| `unoq` | SNPE | INT8 (mandatory for DSP) | .dlc | V66 DSP requires INT8 |
| `rubio-pi` | QNN | INT8 or FP16 | .bin (QNN context) | V69 supports both |
| `windows-x-elite` | QNN | FP32 or INT8 | .bin (QNN context) | V75, full precision support |
| `android-8elite` | QNN/SNPE | INT8 | .dlc or .bin | V79, optimized for mobile |
| `rb5` | QNN | INT8 or FP16 | .bin | V68 |
| `iq-9075` | QNN | FP32 | `.onnx` (always) + `.bin`/`.dlc` (NPU, only if the board's on-device QAIRT is ≥2.45) | **Check `qnn-net-run --version` on the board before choosing.** If QAIRT ≥2.45: compile a `.dlc` (device-agnostic, run via `qairt-net-run --use_htp`) for NPU inference — this is a genuinely working path, verified reproducible. If QAIRT <2.45: **do NOT attempt `.bin`/`.dlc`** — every AI-Hub-compiled QNN context binary and QNN DLC has been confirmed rejected on-device (`Using newer context binary on old SDK` / `Failed to create dlc handle`) on that image class. Always also produce a plain `.onnx` for the CPU path regardless of QAIRT version — CPU always works via onnxruntime. Never attempt GPU via any artifact — confirmed blocked on every image tested (see profile above). |
| `ai-gateway` | gwapps / NWAIOS | INT8 | .bin / .dlc / .so / .onnx (NWAIOS routes them all) | Place model under `/var/run/nwaios/<app>/m.<ext>` (≤ 64 bytes path) |

**MCP call timeout — set ≥ 600 seconds.** Conversion is multi-stage
and the qairt-quantizer step alone has an internal 600s budget.

**Calibration data for INT8/INT4 — pass real samples or do not quantize.**
If `quantization` is `int8` or `int4`, you MUST supply real
calibration data. Without it, `qairt-quantizer` hangs indefinitely on
Transformer-style models.

### 3.2 Profile the model

Invoke the `quad-profile` skill:
- Call `mcp__quad__profile_workload` with:
  - `runtime` from Phase 1
  - `profiling_level` = "detailed" first, then "linting" for bottlenecks
- Capture latency stats, throughput, power, utilization

**For remote targets:** use AI Hub Models cloud profiling if available:
- `rubio-pi` → "QCS6490 (Proxy)" device in AI Hub Models
- For `unoq` and `rb5` → deploy to device and profile on-target

### 3.3 Orchestrate allocation

Invoke the `quad-orchestrate` skill:
- Call `mcp__quad__orchestrate_workload` with each power mode
- Show the 3-mode comparison table
- Select the mode matching the user's power constraint

**Target-specific power mode defaults:**

| Target | Default mode | Reason |
|--------|-------------|--------|
| `unoq` | `low_balanced` | 2W power budget, always-on use cases |
| `rubio-pi` | `balanced` | 5W budget, sustained workloads |
| `windows-x-elite` | `high_performance` | Plugged in, dev workflow |
| `android-8elite` | `balanced` | Battery life matters |
| `rb5` | `balanced` | Robotics: sustained + responsive |
| `iq-9075` | `balanced` (only meaningful if NPU is reachable — check QAIRT version first) | On a QLI 2.0-class image (QAIRT ≥2.45), NPU dispatch works via `qnn-net-run`+artifact, so `--perf_profile` (e.g. `burst`/`balanced`/`low_power_saver`) is a real, testable knob for that path. On a QLI 1.6-class image, no NPU/GPU dispatch is reachable, so this is nominal. GPU power modes are not reachable on any image tested. |

### 3.4 Generate code

Invoke the `quad-codegen` skill:
- Call `mcp__quad__generate_code` with:
  - `platform`: `unoq`/`rubio-pi`/`rb5`/`iq-9075`/`custom-linux` → "linux";
    `windows-x-elite` → "windows"; `android-8elite` → "android"
  - `language`: based on app type + target:
    - `unoq` + Arduino sketch → "arduino_sketch"
    - `unoq`/`rubio-pi`/`rb5` + C++ → "cpp" (cross-compiled)
    - `unoq`/`rubio-pi`/`rb5` + Python → "python"
    - `windows-x-elite` → "python" or "cpp"
    - `android-8elite` → "kotlin" or "cpp"
    - `ai-gateway` → **"c"** (NWAIOS C app, cross-compiled via gwapps toolchain)
  - `sdk`, `runtime` from Phase 1
    - `ai-gateway`: `sdk="nwaios"`, plus pass `target_arch` (default
      `aarch64-openwrt-linux`)
  - `model_path` = converted model path
- Capture source files, build instructions, dependencies

### 3.5 Scaffold the complete application

Create the app directory under `samples/<app_name>/` with:

**For Python apps (all targets):**
- `<app_name>.py` — main script following the pattern:
  - Step 1: Download/load model
  - Step 2: Preprocess input (task-specific)
  - Step 3: Run inference
  - Step 4: Postprocess output
  - Step 5: Display results
- Include CPU, GPU, and NPU benchmark paths (three-way comparison)
- Graceful degradation if GPU/NPU unavailable

**For Arduino sketch (.ino) — `unoq` only:**
- `inference.ino` — generated from Jinja2 template
- Uses SNPE C++ API with DSP runtime
- Build with: `arduino-cli compile --fqbn qualcomm:arm:unoq`
- Upload with: `arduino-cli upload --fqbn qualcomm:arm:unoq -p /dev/ttyUSB0`

**For native C++ (remote targets):**
- `main.cpp` + `CMakeLists.txt`
- Cross-compile: `aarch64-linux-gnu-g++ -O2 -o app main.cpp -I<SDK>/include -L<SDK>/lib/aarch64-linux-gcc -lSNPE`
- Or on-device build if target has compiler

**For Kotlin/Android:**
- `app/src/main/java/` — Activity + inference wrapper
- `app/build.gradle.kts` — dependencies + NDK config
- `app/src/main/assets/` — model placement

**For native C (`ai-gateway`):**
- Six-file scaffold emitted by `generate_code(platform="gateway",
  language="c", sdk="nwaios", target_arch="<arch>")`:
  `CMakeLists.txt`, `main.c`, `tensor_io.c`, `service.json`,
  `ipk_control`, `README.md`
- Build with: `quad gwapps build --source <app> --target <arch>` (Phase 4
  build wrapper — wraps cmake + IPK packaging)
- Deploy with: `quad gwapps deploy <app>.ipk --host <gw>` (Phase 5 device
  manager + LCM client)
- Profile with: `quad profile_workload --platform=gateway --runtime=npu`
  (Phase 6 NWAIOS profiler — returns NWAIOS-shaped report)
- Customize `prepare_inputs()` / `consume_outputs()` in `tensor_io.c`
  with the app's real data pipeline; the scaffold ships deterministic
  byte patterns

**Always create (host-side):**
- `requirements.txt` — all Python deps with `>=` pins, plus
  `pytest>=7.0` and `pytest-timeout>=2.1`
- `run.ps1` — canonical uv-based installer (from `quad-run-ps1` skill)
- `README.md` — quick start, prerequisites, CLI options
- `tests/` directory — see 3.7

**For remote targets, also create:**
- `deploy.sh` — script to push artifacts to board
- `run_on_target.sh` — script to execute on-device
- `Makefile` or `CMakeLists.txt` — if C++ cross-compilation needed

### 3.6 Task-specific patterns

| Task | Preprocessing | Postprocessing | Reference |
|------|--------------|----------------|-----------|
| Classification | resize 224, normalize ImageNet mean/std, NCHW | softmax → top-K | `samples/mobilenetv2` |
| Detection | resize, pad, normalize | NMS, bbox decode, draw | `projects/plan1_vision` |
| Segmentation | resize, normalize | argmax → color mask | `projects/plan1_vision` |
| LLM | tokenize, embed | decode loop, KV cache | `projects/plan2_llm` |
| ASR | audio chunk 80ms, mel spectrogram | CTC/attention decode | `projects/plan4_asr` |

### 3.7 Test suite (MANDATORY deliverable)

Every app MUST ship with a pytest test suite under
`samples/<app_name>/tests/`. The suite is part of the deliverable —
not optional, not a follow-up — and it must pass cleanly before the
app is committed.

**Required test files:**

```
samples/<app_name>/tests/
├── __init__.py              # empty
├── conftest.py              # fixtures: tiny model, fixture input, tmp dirs
├── test_smoke.py            # imports, CLI --help, version checks
├── test_units.py            # every helper / preprocess / postprocess function
└── test_end_to_end.py       # one full run on a small fixture, asserts output shape and exit code
```

**For remote targets, add:**
```
├── test_deploy.py           # verify deploy.sh creates correct file structure
└── test_on_target.py        # SSH-based smoke test (skipped if board unreachable)
```

**Conventions:**
- Use `tmp_path` fixture for any file I/O — never write to the repo
- Mock network calls with `monkeypatch` or pre-stage cached models
- Skip NPU-only tests with `pytest.skip` when `QNN_SDK_ROOT` is unset
- Skip on-target tests when board is unreachable (ping check in fixture)
- All tests share the app's `.venv`; pytest is invoked as
  `.venv/Scripts/python.exe -m pytest tests/ -q` (Windows) or
  `.venv/bin/python -m pytest tests/ -q` (macOS/Linux)

### 3.8 Self-contained dependency bootstrap (MANDATORY)

The user must NEVER have to chase down missing prerequisites. Every
app this skill produces ships with everything it needs to run on a
clean target machine, fetched the moment the app launches (or baked
into the artifact at build time). Decide HOW the deps arrive based
on the app type below, but the goal is identical: one command, no
follow-up `pip install` / `apt install` / `gradle dependencies`
hunts by the user.

**Source of truth — `requirements.txt`.** List every Python dep
with a `>=` pin, including ones that look "optional" but light up
real features (Anthropic SDK for cloud LLM, `qai-hub` /
`qai-hub-models` for AI Hub Models bundles, `onnxruntime-genai` for
NPU LLM, `onnxruntime-qnn` for NPU embeddings, `pdfplumber` /
`python-docx` for parsers, etc.). If a feature is listed in the
README, its deps are listed here.

**Layer 1 — `run.ps1` / `install_prerequisites.bat` (host-side, source).**
The canonical Windows installer (`quad-run-ps1` skill) creates the
`.venv` and runs `pip install -r requirements.txt` in one step.
For SAGE-style multi-stage installs (core + arch-specific NPU stack
+ optional corp-only SDKs), an `install_prerequisites.bat` runs the
same pip flow but with `[OK] / [WARN]` per stage so a failing
optional dep doesn't block the rest. Either way the user runs ONE
script and walks away.

**Layer 2 — In-app background bootstrap (runtime).** When a dep is
optional / late-binding (e.g. an NPU LLM stack only useful when the
user picks `provider=npu`), wire a daemon-thread bootstrap that
runs on first launch:

```python
# src/<app>_deps.py — pattern lifted from sewa-apps/SAGE/src/npu_deps.py
def required_packages():
    # onnxruntime-genai is one package (no -qnn variant); the win-arm64
    # wheel carries the NPU support, other platforms get the CPU build.
    return [
        ("qai_hub",          "qai-hub"),
        ("qai_hub_models",   "qai-hub-models"),
        ("onnxruntime_genai", "onnxruntime-genai"),
    ]

def bootstrap_async(log_fn=None, on_done=None):
    if getattr(sys, "frozen", False):
        return                          # bundled — see Layer 3
    missing = [p for p in required_packages()
               if importlib.util.find_spec(p[0]) is None]
    threading.Thread(target=lambda: _install(missing, ...), daemon=True).start()
```

Call it once in app startup; surface install progress through the
existing log queue / status bar so the user sees what's happening
without it blocking the GUI.

**Layer 2b — On-demand self-heal at the point of use.** Some deps are
too heavy or too situational to install for every user at startup — e.g.
a specific model's `qai-hub-models[<slug>]` extras (which drag in
`transformers` + `torch`), or an arch-specific runtime wheel only needed
once the NPU path actually runs. For these, install lazily the first
time the feature is invoked, and **never surface a `pip install` command
to the user**. Pattern: catch the missing-dep `ImportError` → install the
spec in-process via `subprocess` on `sys.executable` →
`importlib.invalidate_caches()` → re-import → only fail with a clear
message if the install itself fails. Note the extra is keyed by the
package **slug** (`llama-v3-1-8b-instruct`), not the friendly id — the
wrong name silently installs nothing — so back the extra with a loop that
installs whatever concrete module the `ImportError` actually names:

```python
mod = None
tried_extra = False
while mod is None:
    try:
        mod = importlib.import_module(f"qai_hub_models.models.{slug}")
    except ImportError as e:
        if not tried_extra:                       # 1) the published extra
            tried_extra = True
            _pip_install(f"qai-hub-models[{slug.replace('_', '-')}]")
        else:                                      # 2) the concrete missing module
            _pip_install((e.name or "").split(".")[0])
        importlib.invalidate_caches()             # retry (cap attempts in real code)
```

Reference: `download_bundle` (per-model extras) and `_ensure_loaded`
(self-healing `onnxruntime-genai` install) in
`sewa-apps/SAGE/src/npu_llm.py`. A README or in-app message that tells
the user to run `pip install …` to fix a feature is a bug — auto-install
it instead.

**Self-heal is for source/venv runs only — guard it with `sys.frozen`.**
In a PyInstaller/py2exe build, `sys.executable` is the **app EXE, not
Python**, so `subprocess([sys.executable, "-m", "pip", …])` relaunches
your GUI (a phantom second window) and still can't add modules to the
frozen archive. Always early-return when `getattr(sys, "frozen", False)`
and surface an honest, actionable message instead — e.g. "produce this
artifact once from source and drop it next to the EXE" — never attempt
the install. Heavy/situational assets a frozen build can't self-heal
(multi-GB model bundles, export-time deps like `transformers`/`torch`/
AIMET) must be **bundled at build time (Layer 3) or shipped as a
drop-in folder**; also disable/relabel the in-app "Download" affordance
when frozen so the user isn't invited to click a no-op. Reference:
SAGE's frozen guard in `download_bundle` / `_pip_install`.

**Layer 3 — Bundled artifacts (frozen / packaged build).** When the
app ships as an EXE / APK / IPK, the deps live INSIDE the artifact
— Layer 2 detects `frozen` and no-ops. Per packaging system:

| Packaging | How deps land in the artifact |
|-----------|-------------------------------|
| **PyInstaller `.spec`** | `collect_all('<pkg>')` for every package with native DLLs or non-trivial data files (lxml, pdfminer, pptx, AI Hub stack, ORT-GenAI). Add lazy / try/except imports to `hiddenimports`. Wrap optional deps in a `_safe_collect()` so the spec still builds when the dep isn't installed locally. Reference: `sewa-apps/SAGE/SAGE.spec`. |
| **Android APK** | Pin every Maven dep in `app/build.gradle.kts`; ship JNI native libs under `app/src/main/jniLibs/<abi>/`. Models go under `app/src/main/assets/`. |
| **Native C++ (CMake)** | `FetchContent_Declare` + `FetchContent_MakeAvailable` for header-only deps (cxxopts, fmt). For linked SDKs, link statically when license allows; otherwise vendor them under `third_party/<sdk>/<arch>/` and load via rpath. |
| **AI Gateway IPK** | `ipk_control` `Depends:` line for every shared lib the app dlopens; bundle private deps under `/opt/<app>/lib/` and add the path to `LD_LIBRARY_PATH` in the LCM service launcher. |
| **Arduino sketch** | Pin libraries in a `library.properties` `depends=` line; commit the `arduino-cli` build cache directives so `arduino-cli compile` resolves them offline. |

**Architecture-aware wheel selection.** `onnxruntime-qnn` (the NPU
embeddings EP) is win-arm64 only — pair it with a commented CPU
`onnxruntime` fallback. `onnxruntime-genai` (NPU LLM) is a single package
whose win-arm64 wheel carries the NPU support, so it needs no per-arch
split. There is **no** `onnxruntime-genai-qnn`. The real arch concern for
the runtime is the *interpreter*: native arm64 Python vs emulated x86 (see
the NPU checklist near the top). In `install_prerequisites.bat` you may
still branch on `%PROCESSOR_ARCHITECTURE%` for the embeddings EP.

**Snapdragon / NPU apps — run `quad-npu-prereqs`.** When the app
targets the Hexagon NPU, do NOT hand-roll the AI Hub Models token + NPU wheel
provisioning here. Invoke the `quad-npu-prereqs` skill: it reviews the
token + arch-correct wheels + env/config with the user and writes them
into the app's `.env` / `quad.toml` / `requirements.txt`. That skill is
the single source of truth for the canonical `QAI_HUB_API_KEY`
(+ `QAI_HUB_API_TOKEN` alias) and the `onnxruntime-qnn` /
`onnxruntime-genai` wheel split.

**Model bundles fetched on first launch.** When a model file is too
large for a wheel or git LFS, ship a `fetch_<model>.py` that lazy-
imports the downloader and pulls into a stable cache directory the
app discovers on every launch (e.g. `<base>/models/<name>/`). Make
the same script work in `--verify` (default, no new deps) and
`--download` (lazy-imports the SDK) modes — see
`sewa-apps/SAGE/fetch_llm_model.py`.

**Reference implementations:**
- `sewa-apps/SAGE/src/npu_deps.py` — the runtime background-install
  pattern (frozen-aware, arch-aware, daemon thread, status callback).
- `sewa-apps/SAGE/install_prerequisites.bat` — the multi-stage
  installer with optional-dep `[WARN]` handling.
- `sewa-apps/SAGE/SAGE.spec` — the `_safe_collect()` /
  `hiddenimports` pattern for PyInstaller.
- `sewa-apps/SAGE/requirements.txt` — universal-base + arch-comment
  layout for split wheels.

---

## Phase 4 — End-to-End Verification (MANDATORY)

**This phase is NOT optional.** Do NOT proceed to documentation or
git push until every check below passes.

### 4.1 Install dependencies

```bash
cd samples/<app_name>
# Windows:
.\run.ps1
# macOS/Linux:
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 4.2 Syntax and import check

```bash
cd samples/<app_name>
.venv/bin/python -c "import ast; ast.parse(open('<app>.py').read()); print('syntax OK')"
.venv/bin/python -c "import <main_module>"
```

### 4.3 Run the test suite (MANDATORY)

```bash
cd samples/<app_name>
.venv/bin/python -m pytest tests/ -q --tb=short 2>&1
echo "PYTEST EXIT: $?"
```

**Passing criteria — ALL must be true:**
- Exit code is 0
- No `FAILED` or `ERROR` lines
- At least one test from each test file actually ran
- Skipped tests are acceptable only with explicit `pytest.skip()`

### 4.4 Run the app end-to-end (host)

```bash
cd samples/<app_name>
.venv/bin/python <app>.py [--test-flags] 2>&1
echo "EXIT CODE: $?"
```

### 4.5 On-target verification (remote targets only)

**For `unoq`, `rubio-pi`, `rb5`, `custom-linux`:** (SSH-based boards)

After host-side tests pass, deploy and validate on the actual board:

```bash
# Deploy
scp -r ./build/ <user>@<board-ip>:/data/local/tmp/quad/app/
scp ./models/*.dlc <user>@<board-ip>:/data/local/tmp/quad/models/

# Run single inference on target
ssh <user>@<board-ip> "cd /data/local/tmp/quad && \
  snpe-net-run --container models/model.dlc \
    --input_list input_list.txt \
    --use_dsp \
    --perf_profile balanced 2>&1"
```

Or invoke `/quad-unoq deploy` for the full deployment pipeline.

**Passing criteria for on-target:**
- SSH connection succeeds
- Model loads without error
- Single inference completes (exit code 0)
- Output shape matches expected
- No DSP crash in `dmesg`

**For `iq-9075`:** (SSH is the default transport — validated as the recommended flow, matching Qualcomm Linux's own intended design once the board is on Wi-Fi; see Target Profiles above. Swap `--transport adb --host <serial>` only as a bootstrap fallback before Wi-Fi is up)

```bash
# Detect + confirm the board's actual state (transport, QAIRT version) before assuming anything
.venv/Scripts/python.exe scripts/board_profile.py detect <host-or-serial> --board iq-9075 --transport ssh

# CPU path -- always attempt this, works on any image
.venv/Scripts/python.exe scripts/board_profile.py push <host-or-serial> --board iq-9075 --transport ssh --model <path.onnx>
.venv/Scripts/python.exe scripts/board_profile.py profile <host-or-serial> --board iq-9075 --transport ssh --model <path.onnx>

# NPU path -- only if `qnn-net-run --version` reported QAIRT >=2.45 above.
# board_profile.py's own `profile` subcommand does not yet know this artifact's
# NHWC input contract or --profiling_level client -- use the sample app's
# reference implementation instead (samples/mobilenetv2_iq9075/run_iq9075.py
# --qnn-context-bin <compiled.bin>), or replicate its
# attempt_qnn_context_binary() function for a new app.
```

**Passing criteria for on-target (`iq-9075`):**
- `detect` reports `detection_successful: true` and an empty (or
  already-known/expected) `diffs_vs_profile` list
- CPU benchmark completes with real, non-zero latency numbers, on any image
- **If the board's QAIRT is ≥2.45:** the NPU-via-context-binary/DLC path also
  completes with real, non-zero, reproducible latency numbers (expect
  roughly 2-3ms mean for a MobileNetV2-class model, but don't hardcode this
  — measure fresh) — this is a genuine PASS requirement on a QLI 2.0-class
  image, not an optional bonus.
- The `onnxruntime_qnn` plugin-EP NPU/GPU attempt (if the app's own code
  exercises it) exits 0 and reports the specific, documented blocker message
  — **a clean, informative failure is a PASS here, not a FAIL**, on any
  image, since this path is permanently blocked regardless of QAIRT version.
  Treat a silent crash, a hang, or a wrong/generic error message as the
  actual failure, not "NPU unavailable" itself.
- Any GPU attempt via any path is expected to fail cleanly with a
  documented blocker message on every image tested — same standard as above.

### 4.6 Fix-and-rerun loop

If any check in 4.1–4.5 fails:
1. Diagnose the root cause from the error output
2. Fix the code (Edit tool)
3. Re-run from the failing step
4. Repeat until the full pipeline passes cleanly

**Maximum 3 fix-and-rerun cycles.** If still failing after 3
attempts, stop and present the error to the user.

### 4.7 Clean-machine bootstrap check (MANDATORY)

Prove the app self-bootstraps (Phase 3.8) end-to-end. Use a
throw-away venv that has NONE of the app's deps pre-installed,
then run ONLY the user-facing entry point. If anything inside
fails to import without the user manually running `pip install`,
the bootstrap is incomplete — fix it before proceeding.

```bash
# Source-app form: simulate a clean checkout
cd samples/<app_name>
rm -rf .venv && python -m venv .venv
# Windows:    .\run.ps1
# macOS/Linux: .venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import <main_module>; print('imports OK')"
.venv/bin/python <app>.py --self-test 2>&1
echo "BOOTSTRAP EXIT: $?"
```

For frozen / packaged artifacts, run the same gate against the
artifact:

```bash
# PyInstaller EXE — must launch without an external Python
./dist/<App>.exe --self-test

# Android APK — install on a fresh emulator
adb install -r ./app/build/outputs/apk/release/app-release.apk
adb shell am start -n com.example.<app>/.MainActivity

# AI Gateway IPK
quad gwapps deploy ./build/<app>.ipk --host <gw>
ssh root@<gw> "lcm-cli list | grep <app>"
```

**Passing criteria — ALL must be true:**
- The user runs ONE command (run.ps1 / EXE / `adb install` / `quad gwapps deploy`).
- No `ModuleNotFoundError`, missing-DLL, or "install X to enable Y" prompts.
- Optional features that need late-binding deps either install in
  the background (Phase 3.8 Layer 2) or surface a non-fatal status
  message (e.g. "AI Hub Models deps installing… NPU LLM available shortly").

If any check fails, return to Phase 3.8 and either pin the missing
dep, add it to the spec/gradle/IPK manifest, or extend the
in-app bootstrap.

---

## Phase 5 — Target KPI Validation

### 5.1 Performance testing

**For local targets (windows-x-elite):**
- Run three-way benchmark: CPU vs GPU vs NPU
- Print latency, throughput, power estimates

**For remote targets — invoke `/quad-unoq perf` or equivalent:**

```bash
# UNO Q / Rubio Pi / RB5
ssh <user>@<board-ip> "snpe-net-run \
  --container models/model.dlc \
  --input_list input_list.txt \
  --use_dsp \
  --perf_profile balanced \
  --duration 30 2>&1 | grep -E 'Total Inference|Init Time'"
```

**Target-specific KPI thresholds:**

| Target | Latency P50 | Latency P99 | Throughput | Init time |
|--------|-------------|-------------|------------|-----------|
| `unoq` | < 33ms | < 50ms | > 30 fps | < 2s |
| `rubio-pi` | < 15ms | < 25ms | > 60 fps | < 1.5s |
| `windows-x-elite` | < 10ms | < 20ms | > 100 fps | < 1s |
| `android-8elite` | < 10ms | < 15ms | > 100 fps | < 1s |
| `rb5` | < 20ms | < 35ms | > 45 fps | < 1.5s |
| `iq-9075` | CPU: ~6.1ms measured (MobileNetV2 fp32, onnxruntime 1.27.0 on a QLI 2.0 image — earlier measured 14.85ms on v1.22.1 and 6.14ms on v1.24.2, both on a QLI 1.6 image; onnxruntime version materially changes this number, always state which version alongside any figure). NPU (only if QAIRT ≥2.45): ~2-3ms measured via `qnn-net-run`+artifact, reproducible across 9+ runs — GPU: blocked on every image tested, see profile | CPU: ~6.1ms; NPU: ~2-3ms if reachable | CPU: ~164 fps measured; NPU: ~290-500 fps if reachable | not measured this session |
| `ai-gateway` | < 5ms (NSP) / < 30ms (CPU) | < 10ms / < 50ms | > 200 fps (NSP) / > 30 fps (CPU) | < 1s |

(Thresholds above are for typical small models like MobileNetV2.
Scale expectations for larger models.)

### 5.2 Stability testing (remote targets)

For `unoq`, `rubio-pi`, `rb5` — invoke `/quad-unoq stability`:

```bash
# 1-hour soak test
ssh <user>@<board-ip> "nohup bash -c '
  PASS=0; FAIL=0; START=\$(date +%s)
  while [ \$(((\$(date +%s) - START))) -lt 3600 ]; do
    if snpe-net-run --container models/model.dlc \
      --input_list input_list.txt --use_dsp --perf_profile balanced \
      >/dev/null 2>&1; then PASS=\$((PASS+1))
    else FAIL=\$((FAIL+1)); fi
  done
  echo \"PASS=\$PASS FAIL=\$FAIL\" > /tmp/soak.txt
' &"
```

**Stability KPIs:**

| Metric | Target |
|--------|--------|
| Success rate | > 99.9% |
| Memory leak | < 5 MB growth/hour |
| Thermal | < 75°C sustained |
| DSP crashes | 0 |
| Latency drift | < 10% P99 increase over 1 hour |

### 5.3 Power profiling (remote targets)

For `unoq`, `rubio-pi`, `rb5` — invoke `/quad-unoq power`:

**`iq-9075` is excluded from this section's example command (which uses `snpe-net-run --use_dsp`, not applicable to this board's toolchain), but power profiling itself is NOT categorically unavailable anymore.** On a QLI 2.0-class image (QAIRT ≥2.45), `qnn-net-run`/`qairt-net-run` accept a `--perf_profile` flag (`burst`/`balanced`/`low_power_saver`, etc.) when running the NPU-via-context-binary path — this is a real, testable knob, just not yet measured against a power meter this session. On a QLI 1.6-class image, no NPU dispatch is reachable at all, so there is genuinely no meaningful power number to measure. Check the board's QAIRT version before deciding whether to attempt this. Do not fabricate a row for it in the table below either way.

```bash
for mode in low_balanced balanced high_performance burst; do
  echo "=== $mode ==="
  ssh <user>@<board-ip> "snpe-net-run --container models/model.dlc \
    --input_list input_list.txt --use_dsp --perf_profile $mode \
    --duration 10 2>&1 | grep 'Total Inference'"
done
```

**Power KPIs:**

| Target | Mode | Max sustained power |
|--------|------|-------------------|
| `unoq` | balanced | 1.0W |
| `unoq` | low_balanced | 0.5W |
| `rubio-pi` | balanced | 3.0W |
| `rubio-pi` | high_performance | 5.0W |
| `rb5` | balanced | 4.0W |

### 5.4 Performance iteration

| Problem | Action |
|---------|--------|
| Latency too high | Try INT8/INT4 → re-convert → re-profile |
| Accuracy too low | Switch to FP32, check preprocessing |
| Power too high | Switch to `efficiency` mode, reduce batch |
| Unsupported ops | Fall back to CPU for those layers |
| Thermal throttling | Reduce perf_profile, add heatsink (board) |
| Memory exceeded | Quantize more aggressively, reduce batch, use smaller model |

### 5.5 Production hardening

Add to the application code:
- **Input validation:** Check file exists, image dimensions, audio sample rate
- **Error handling:** Graceful fallback if NPU/GPU unavailable (use CPU)
- **Logging:** Structured logging with timestamps, latency per inference
- **Resource cleanup:** Proper model unload, temp file cleanup
- **CLI arguments:** argparse with `--model`, `--input`, `--runtime`, `--output`
- **Watchdog (remote targets):** Restart on DSP hang, thermal throttle recovery

---

## Phase 6 — Documentation

Generate two documents. Invoke the `quad-app-document` skill, or
generate directly:

### 6.1 ARCHITECTURE.md

Write to `<app_dir>/ARCHITECTURE.md`:

```markdown
# <App Name> — Architecture

## Overview
[1-2 paragraph description]

## Target Platform
[Board name, SoC, NPU specs, interface method]

## System Diagram
Input → Preprocess → [Runtime] → Postprocess → Output
                        │
                   ┌────┴────┐
                   │ NPU/DSP │  ← primary
                   │ GPU     │  ← fallback
                   │ CPU     │  ← baseline
                   └─────────┘

## Components
[Table: component, file, description, dependencies]

## Model Card
[Model name, task, input/output shape, quantization, size, accuracy]

## Deployment
[How to get the app onto the target device — deploy.sh, scp, adb, etc.]

## KPIs
[Table: metric, measured value, target, pass/fail]

## Power & Thermal
[Power mode, sustained wattage, thermal profile]
```

### 6.2 app_documentation.docx

Use the `doc_generator.py` module to create a Word document with:
- Title page, TOC
- Architecture diagram
- Setup & installation
- Deployment instructions (target-specific)
- KPI results table
- Troubleshooting guide

---

## Phase 7 — Final Verification Gate

Before committing, re-run BOTH gates:

```bash
cd samples/<app_name>

# Gate 1 — tests must pass
.venv/bin/python -m pytest tests/ -q --tb=short 2>&1
echo "PYTEST EXIT: $?"

# Gate 2 — app must run end-to-end
.venv/bin/python <app>.py [--test-flags] 2>&1
echo "APP EXIT: $?"

# Gate 3 — bootstrap is self-contained on a clean checkout
#         (see Phase 4.7; re-run from a fresh venv)
rm -rf .venv && python -m venv .venv && .\run.ps1   # Windows
.venv/bin/python -c "import <main_module>; print('imports OK')"

# Gate 4 (remote targets) — on-target smoke
ssh <user>@<board-ip> "cd /data/local/tmp/quad && \
  snpe-net-run --container models/model.dlc \
  --input_list input_list.txt --use_dsp 2>&1 | tail -3"
```

If any fails, go back to Phase 4.6 fix-and-rerun.

---

## Phase 8 — Git Push

### 8.1 Ask for repository

Use `AskUserQuestion`:
- "Where should I push this code?"
- Options: existing repo URL, create new, skip

### 8.2 Prepare commit

```bash
echo ".venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.raw" >> .gitignore
echo "output/" >> .gitignore

git add <app_dir>/
git status
```

Show the user what will be committed. Get confirmation.

### 8.3 Commit and push

```bash
git checkout -b feature/<app_name>
git commit -m "feat: add <app_name> — <task> on <target> via QUAD"
git push -u origin feature/<app_name>
```

### 8.4 Optionally create PR

```bash
gh pr create \
    --title "Add <app_name>: <task> inference on <target>" \
    --body "## Summary\n- <description>\n\n## Target\n<platform details>\n\n## KPIs\n<metrics table>"
```

---

## Conventions to follow

- Every app MUST have `run.ps1` + `requirements.txt` (see `quad-run-ps1` skill)
- Every app MUST have a passing `tests/` directory
- **Every app MUST self-bootstrap its prerequisites** — `requirements.txt`
  is exhaustive; `install_prerequisites.bat` (or `run.ps1`) installs the
  whole stack in one shot; optional / late-binding deps install via an
  in-app daemon thread (Phase 3.8 Layer 2). Frozen builds bundle the same
  deps via `collect_all()` / `hiddenimports` so the EXE/APK/IPK is
  single-artifact.
- **Architecture-aware deps:** when a wheel only exists for one arch
  (e.g. `onnxruntime-qnn`, the NPU embeddings EP, is win-arm64 only),
  branch on `%PROCESSOR_ARCHITECTURE%` / `platform.machine()` and install
  the CPU fallback (`onnxruntime`) on other hosts so the import always
  resolves. `onnxruntime-genai` needs no split. The bigger arch trap is
  the *interpreter*: the NPU runtime needs native arm64 Python, not the
  emulated x86 Python an X-Elite may default to.
- **PyInstaller specs** must `collect_all()` every native-DLL or data-
  bearing optional dep, wrapped in a `_safe_collect()` so the spec still
  builds without the dep installed locally. Lazy / try-except imports go
  in `hiddenimports`.
- Place apps under `samples/<app_name>/`
- Use `>=` version pins in requirements.txt
- Never commit `.env`, `.venv/`, `__pycache__/`, `*.raw`, `output/`
- Three-way benchmark (CPU vs GPU vs NPU) whenever hardware supports it
- Graceful degradation: always fall back to CPU if GPU/NPU unavailable
- UTF-8 output wrapper on Windows (see mobilenetv2 pattern)
- Tests must run on a plain CPU machine — gate target tests with `pytest.skip`
- Remote targets: always include `deploy.sh` and `run_on_target.sh`

## Error recovery

- If MCP server fails to start: check `quad doctor`, verify QUAD is installed
- If conversion fails: try `onnxsim` simplification first
- **If conversion "times out" at 60s:** bump to 600s and retry
- **If `qairt-quantizer` hangs:** fall back to FP32; INT8 needs real calibration
- If NPU inference fails: check DSP signature, try `--enable_init_cache`
- If GPU benchmark fails: check `QnnGpu.dll` exists in SDK lib dir
- If SSH to board fails: check network, try serial console, power cycle
- If DSP crashes on target: restart remoteproc, check skel version match
- If git push fails: check credentials, offer `! gh auth login`
- **Board-specific recovery:** invoke `/quad-unoq debug` for systematic diagnosis
- **`iq-9075` — "Using newer context binary on old SDK" / "Failed to create dlc handle":** this is NOT a transient error to retry — it's the documented QAIRT compiler/runtime version wall (AI Hub compiles ≥2.45; the board's on-device QAIRT is what determines whether this fails — check `qnn-net-run --version`). Do not attempt `--qairt_version <old>` (AI Hub rejects out-of-range overrides as invalid) or try a different precision/quantization (irrelevant — the failure is at the container-format level, before any op executes). If the board's QAIRT is genuinely <2.45, fall back to CPU via plain `.onnx` + onnxruntime and tell the user a board reflash to a newer image is the only known fix; see `NPU_GPU_INVESTIGATION_IQ9075.md` §4.1/§4.4. If the board's QAIRT is ≥2.45 and you still see this error, something else is wrong (e.g. wrong artifact for this board's chipset) — don't assume it's the version wall without checking.
- **`iq-9075` — QNN EP registers but `get_ep_devices()` never shows an NPU/GPU device:** NOT a registration bug, and NOT fixed by a newer QAIRT SDK (re-confirmed with the newest available release, 2.48.40 — no change) — `onnxruntime`'s own Linux device-discovery code doesn't recognize this SoC's `/dev/fastrpc-*` NPU exposure (it expects a DRM-GPU-with-vendor-file). This is compiled into the `onnxruntime` pip package itself, not QAIRT — there is no client-side fix, no newer package to try, and no manual device-override API. Use the `qnn-net-run`+context-binary/DLC path instead for real NPU acceleration (works if the board's QAIRT is ≥2.45). See `NPU_GPU_INVESTIGATION_IQ9075.md` §4.2/§4.7.
- **`iq-9075` — NPU works via `qnn-net-run`/`qairt-net-run` but GPU (`libQnnGpu.so`/`--use_gpu`) fails with `QNN_BACKEND_ERROR_CANNOT_INITIALIZE` or `GPU_ERROR_DOES_NOT_EXIST`:** this is a confirmed, board-specific driver/SDK version gap (the GPU backend needs OpenCL extension symbols this board's installed Adreno driver doesn't export), reproduced identically across three separate QAIRT releases including the newest available. It is NOT a config-file issue, NOT an ICD-registration issue, and NOT fixed by trying a different QAIRT version. Do not attempt to fix this without new information (e.g. a genuinely updated Adreno driver package, which has no known update channel from this client) — see `GPU_INVESTIGATION_IQ9075.md` for the full, already-exhausted diagnostic trail before re-attempting.
- **`iq-9075` — NPU/GPU numeric output looks "wrong" when checked against a CPU baseline:** before concluding there's a bug, check (1) whether the input is a real photo with unambiguous ground truth or this repo's synthetic placeholder test image (which has none — don't use it for correctness checks), and (2) whether the two backends are using the exact same trained model checkpoint (an AI-Hub-compiled artifact and an ONNX-Model-Zoo-sourced `.onnx` are often *different* checkpoints of the same architecture, which will disagree somewhat even when both are correct). Compare *argmax* on a real photo, not list-overlap on an ambiguous one. See `NPU_GPU_INVESTIGATION_IQ9075.md` §4.5.
- **`iq-9075` — `adb push` of a directory crashes with `libc++abi: ... std::bad_alloc`, transferring zero files (exit 0, masking the failure):** tar the directory into a single file first (`tar czf pkg.tar.gz -C srcdir .`), `adb push` the tarball, then `tar xzf` on-device. Always verify with a follow-up `ls`/`find` — a crashed push can report exit 0. This is specific to adb transport — scp (ssh transport) has not shown this failure mode.
- **`iq-9075` — `pip`/`ensurepip` missing on-device:** only applies to a QLI 1.6-class image (read-only rootfs, no internet) — extract a matching manylinux aarch64 wheel locally and push its package directory (tarball technique above); do not attempt to install pip itself. **On a QLI 2.0-class image, `pip3 install` works directly** (writable rootfs + internet) — check which image you're on before assuming this workaround is needed.
- **`iq-9075` — pushed model fails to load with a missing `.data` file error:** the AI Hub float ONNX export uses external-data format; push the accompanying `.data` file alongside the `.onnx`, not just the graph file.
- **`iq-9075` — a QNN context binary or DLC loads but produces subtly wrong output, or `qnn-net-run` reports a shape/format error:** check the artifact's own `metadata.json` for its declared input contract before assuming the standard NCHW/ImageNet-normalized format — AI-Hub-compiled context binaries/DLCs commonly expect **NHWC float32, `[0,1]`-range** input instead, which is silently wrong (not an error) if you feed the CPU-path format to it.
- **`iq-9075` — attempting NPU then GPU (or GPU then NPU) via the `onnxruntime_qnn` plugin EP in the same process, and the second attempt fails with `library is already registered under QNNExecutionProvider`:** this masks the real, informative error (e.g. "no GPU device found") behind a confusing registration error — `onnxruntime` raises if you call `register_execution_provider_library()` twice for the same EP name in one process. Guard with a module-level flag (`if not _qnn_registered: register(...); _qnn_registered = True`) — see `samples/mobilenetv2_iq9075/deploy/inference.py`'s `attempt_qnn()` for the exact pattern already applied. Apply the same guard in any new script that attempts both NPU and GPU via this plugin-EP path in one process.
- **`iq-9075` — `adb push`/`adb shell` command fails with a garbled or Windows-style path in the error (e.g. `C:/Program Files/Git/data/local/tmp/...`):** this is Git Bash's MSYS layer silently rewriting a leading `/` path as if it were a Windows path — it only happens when `adb` is invoked through a shell command string, not when invoked as a direct argument list (e.g. Python's `subprocess.run([adb_exe, "shell", ...])`, which `scripts/board_profile.py` uses and is unaffected). If hand-rolling any shell-string adb command (as `samples/mobilenetv2_iq9075/run_iq9075.py` does), set `MSYS_NO_PATHCONV=1` in the environment for that invocation.
- **`iq-9075` — `tar xzf`/file extraction on-device prints a "time stamp NNNN is NNN s in the future" warning:** cosmetic, not a real error — this board's on-device clock is stale (not NTP-synced, no internet) and can read a year or more behind actual time. Confirmed live (board reported a date over a year in the past during this workstream). Don't treat this warning as an extraction failure, and don't trust on-device file timestamps for anything (e.g. don't use `mtime` to infer how recently a file was pushed).

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Windows, Linux (or WSL) |
| Requirements | Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows |

References: [QUAD Client README](https://github.com/sreddygu/DevRel/blob/main/QUAD-Client/README.md).

## Example prompts

- Build a vision app on Snapdragon with QUAD
- Create a QUAD application that runs an LLM on the NPU
- Scaffold an inference app and test it end to end
- I want to build a speech-recognition app on my Snapdragon X Elite laptop
- Add tests and documentation to my Snapdragon app and push it to git
- Harden my app: error handling, input validation and logging

<!-- skills-hub:end -->
