# AI Gateway Classifier — Sample Application

> **Goal**: a "first 15 minutes" walkthrough that takes you from
> nothing to a buildable, deployable inference app for an AI Gateway
> (IPQ-class WLAN device) using QUAD's full lifecycle.
>
> **Scope**: build · convert · deploy · profile — all mock-testable
> end-to-end on a developer box with no real device required.
>
> **Status**: works against the integration completed through Phase 6
> of `QUAD/docs/QUAD_GWAPPS_PROGRESS.md`. Phase 7 (port assistant) and
> Phase 8 (on-device debug) are still pending — flagged inline.
>
> **Companion**: `samples/gwapps_fault_detection/` — the production
> reference app (vendored from the framework team's `ad.mcs.0.0`
> branch). Read it after this walkthrough to see what an experienced
> team's gateway app looks like in steady state.

---

## Recommendation: which model to pick

### Primary recommendation — **MobileNetV2 (ImageNet, INT8)**

The cleanest "hello world" for the AI Gateway lifecycle:

| Property | Value | Why it matters |
|---|---|---|
| Source | ONNX Model Zoo / torchvision export | Public, no auth required |
| Size (INT8) | ~3.4 MB | Easily under the gateway's ~256 MB disk budget |
| Input | 224×224×3 RGB | Standard, well-documented preprocessing |
| Output | 1000-class softmax | Trivial postprocessing (argmax + class labels) |
| Quantization | INT8 with public calibration sets | NSP-friendly; no calibration scramble |
| Runtime fit | NSP perfectly suited for conv layers | Confirms the NPU end-to-end |
| Reference | `samples/mobilenetv2/` already exists | Reuse preprocessing logic |

You learn the full QUAD/AI-Gateway workflow without fighting model
quirks. Once this round-trips cleanly, swap in your real model.

### Alternative — **Tiny anomaly autoencoder (network features)**

More "gateway-native" — matches the framework's `ad/` (Anomaly
Detection) and `stc/` (Smart Traffic Classifier) headers. Use this
when you want a demo that's actually useful on a WLAN gateway:

| Property | Value |
|---|---|
| Architecture | 32-dim input → 16 → 8 → 16 → 32 dense autoencoder |
| Size (INT8) | < 200 KB |
| Input | 32 normalized network-flow features (RTT, throughput, packet sizes…) |
| Output | 32-dim reconstruction; anomaly score = MSE |
| Use case | Flag anomalous WLAN connections for closer inspection |

There's no off-the-shelf weights file for this; you'd train one in
PyTorch from a public dataset (CIC-IDS2017 et al.) before running
through QUAD. **Pick MobileNetV2 unless you have specific gateway-
native data on hand.**

---

## Quickstart — 15 minutes from zero

Assumes the gwapps SDK is reachable (`quad doctor --section gwapps`
shows "PASS"). If not, see
`QUAD/QUAD_Packages/gwapps/README.md` for the QPM3 install or local
bundle build.

### 1. Render the starter app (codegen — Phase 3)

```bash
cd /path/to/QUAD-Client/samples/ai_gateway_classifier

# Re-renders the C app tree under ./app/ from QUAD's gateway templates
python generate.py
```

**Output** — six files under `./app/`:

```
app/
├── CMakeLists.txt   ← links libnwaios + libGwAppstransport
├── main.c           ← nwaios_lib_init → model_load → execute → unload
├── tensor_io.c      ← prepare_inputs / consume_outputs scaffold
├── service.json     ← LCM service descriptor
├── ipk_control      ← IPK package metadata
└── README.md        ← per-app build/deploy/profile instructions
```

`generate.py` calls `generate_code(platform="gateway", language="c",
sdk="nwaios", model_path="/host/mobilenetv2.bin", runtime="npu")` —
the same MCP tool any Claude Code session would use via
`quad-codegen` skill.

### 2. Convert the model

```bash
# Mock mode — no real conversion happens; surfaces the metadata path
python -c "
import asyncio
from quad.core.operations.convert_model import convert_model
from quad.adapters.factory import AdapterFactory
from quad.config import load_config
factory = AdapterFactory(load_config())
result = asyncio.run(convert_model(
    model_path='./mobilenetv2.onnx',  # any path; mock doesn't read it
    source_format='onnx',
    target_sdk='qnn',                  # NWAIOS routes QNN .bin natively
    quantization='int8',
    factory=factory,
))
print(result)
"
```

Real-mode conversion uses `qairt-converter` + `qairt-quantizer` — out
of scope for this sample. The *output path* (`./mobilenetv2.bin`) is
what NWAIOS's `nwaios_model_cfg.path` will load on the device. The
codegen step in (1) already renders `service.json` with the correct
on-device path (`/var/run/nwaios/mobilenetv2/m.bin`).

### 3. Build the IPK (Phase 4)

```bash
cd /path/to/QUAD            # QUAD repo (where build wrapper lives)

# Dry-run first to see what cmake would do
.venv/bin/python -m quad.cli.main gwapps build \
    --source /path/to/QUAD-Client/samples/ai_gateway_classifier/app \
    --target aarch64-openwrt-linux \
    --dry-run

# Real build (needs cmake + cross-toolchain on PATH; otherwise dry-run
# is the demo)
.venv/bin/python -m quad.cli.main gwapps build \
    --source /path/to/QUAD-Client/samples/ai_gateway_classifier/app \
    --target aarch64-openwrt-linux
```

Output: `./mobilenetv2.ipk` (or `mobilenetv2.ipk.tar.gz` if `ar` isn't
on PATH — same internal layout, opkg won't accept the fallback).

### 4. Deploy via LCM (Phase 5)

```bash
# Mock-mode (no GATEWAY_HOST set) — runs the LCM lifecycle in-process
.venv/bin/python -m quad.cli.main gwapps deploy \
    /path/to/QUAD-Client/samples/ai_gateway_classifier/app/mobilenetv2.ipk

# Real-mode — needs a reachable IPQ gateway with lcmd running
GATEWAY_HOST=gw01.local \
.venv/bin/python -m quad.cli.main gwapps deploy \
    /path/to/.../mobilenetv2.ipk \
    --user root
```

Expected mock output:

```
  • push mobilenetv2.ipk -> /tmp/quad_deploy/mobilenetv2.ipk
  • lcm install /tmp/quad_deploy/mobilenetv2.ipk
  • lcm start mobilenetv2
[OK]  app=mobilenetv2 state=running pid=1000
```

### 5. Profile (Phase 6)

```bash
.venv/bin/python -c "
import asyncio
from quad.core.operations.profile_workload import profile_workload
from quad.adapters.factory import AdapterFactory
from quad.config import load_config
report = asyncio.run(profile_workload(
    model_path='/var/run/nwaios/mobilenetv2/m.bin',
    platform='gateway',
    runtime='npu',
    duration_s=10,
    factory=AdapterFactory(load_config()),
))
print('latency mean:', report['latency']['mean_ms'], 'ms')
print('throughput  :', report['throughput_fps'], 'fps')
print('power       :', report['power_mw'], 'mW')
print('utilization :', report['utilization'])
print('engine used :', report['runtime_used'])
"
```

In mock mode, the latency reflects the deterministic per-engine number
the NWAIOS profiler uses: ~1.2 ms on NSP, ~8.5 ms on CPU. Real-mode
returns whatever `nwaios_app_stats` reports from the running app.

---

## Pipeline at a glance

```
   ┌──────────────────────────────────────────────────────────────┐
   │  Step           │ Phase │ MCP tool / CLI                     │
   ├──────────────────────────────────────────────────────────────┤
   │  1. Render      │   3   │ generate_code | quad-codegen skill │
   │  2. Convert     │   —   │ convert_model                      │
   │  3. Build IPK   │   4   │ quad gwapps build                  │
   │  4. Deploy      │   5   │ quad gwapps deploy                 │
   │  5. Profile     │   6   │ profile_workload(platform=gateway) │
   ├──────────────────────────────────────────────────────────────┤
   │  6. Port app    │  7    │ quad gwapps port  (NOT YET LANDED) │
   │  7. Debug crash │  8    │ quad device diagnose (NOT YET)     │
   └──────────────────────────────────────────────────────────────┘
```

Phases 7 and 8 are tracked in
`QUAD/docs/QUAD_GWAPPS_PROGRESS.md` — port assistant for legacy-app
migration and on-device debug helpers (gdbserver / journalctl /
core-dump symbolication).

---

## Customizing the scaffold

`generate.py` regenerates the tree from QUAD's gateway templates with
the parameters at the top of the file. To target a different SoC,
change `target_arch`. To use CPU instead of NSP, change `runtime`.
To swap the source model, change `model_path`. To produce the richer
modular layout (10 files instead of 6, with `model_inferencing.c/h`
split out plus Dockerfile + `oci_config.json`), change
`SCAFFOLD = "modular"` — see
`samples/gwapps_fault_detection/README.md` for the production
pattern this scaffold mirrors.

After regeneration, replace the placeholder data pipeline:

* **`app/tensor_io.c`** — `prepare_inputs()` writes a deterministic
  byte pattern; `consume_outputs()` prints first-8-bytes hex digest.
  For MobileNetV2, replace with: load 224×224×3 image, normalize with
  ImageNet mean/std, NCHW layout. For the autoencoder alternative,
  read 32 floats from a feature feed.
* **`app/service.json`** — adjust `restart_policy`, `keepalive_*`,
  `license_features` for your deployment.

---

## Known mock-vs-real differences

| Step | Mock (default on dev box) | Real (with hardware) |
|---|---|---|
| Build | dry-run produces commands; real run needs cmake + cross-toolchain | cross-compiles natively |
| Deploy | in-process MockLCMAdapter | SSH + `lcm install` on the gateway (Phase 5b SSH adapter pending) |
| Profile | NWAIOS mock returns deterministic per-engine latency | reads `nwaios_app_stats` from the running app |
| Doctor | gwapps section against the local bundle (4 pass / 1 warn) | unchanged |

Set `GATEWAY_HOST` to flip to real-mode wherever it applies.

---

## Reference

- Build wrapper API: `QUAD/src/quad/build/gwapps.py`
- LCM adapter API: `QUAD/src/quad/adapters/lcm/`
- Device manager: `QUAD/src/quad/device/manager.py`
- NWAIOS profiler: `QUAD/src/quad/profiler/nwaios.py`
- Gateway codegen templates: `QUAD/templates/gateway/c/`
- Skill: `quad-codegen` (now AI Gateway-aware)
- Skill: `quad-app-builder` (AI Gateway target row + profile)
