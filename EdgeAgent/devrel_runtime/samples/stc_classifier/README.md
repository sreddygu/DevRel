# STC Classifier - Smart Traffic Classifier on AI Gateway

> **Goal**: a 5-class smart traffic classifier (video / voip / web / iot
> / bulk) that runs on an IPQ-class WLAN AI Gateway via NWAIOS NSP, with
> the full DevRel lifecycle - convert, scaffold, build, deploy, profile.
>
> **Scope**: build · convert · deploy · profile - all mock-testable
> end-to-end on a Snapdragon X laptop with no real gateway required.
>
> **Companion**: `samples/ai_gateway_classifier/` (the 15-minute
> MobileNetV2 walkthrough) and `samples/gwapps_fault_detection/`
> (the production 10-file reference vendored from the framework team).

---

## Architecture

```
        +---------------+    +---------------+    +-------------+
        |    INGEST     |--->|  INFERENCING  |--->|   TURNKEY   |
        |  (tensor_io)  |    | (model_infer) |    | (turnkey.c) |
        +---------------+    +---------------+    +-------------+
        nfqueue / pcap         NWAIOS NSP          syslog sink
        64 header bytes        [1,1,64] -> [1,5]    class + conf
        normalized to [0,1]    softmax + argmax
```

The three-function pattern (feature extraction → inferencing → turnkey)
is the standard AI Gateway architecture. Each module is independently
replaceable - swap `nfqueue` for `pcap`, swap NSP for CPU, swap syslog
for MQTT or NSS QoS hooks.

## Model

| Property | Value |
|---|---|
| Architecture | 1D-CNN (Conv1d 1→8 → Relu → Conv1d 8→16 → Relu → GAP → MatMul) |
| Input shape | `[1, 1, 64]` float32 (64 packet header bytes / 255.0) |
| Output shape | `[1, 5]` float32 (per-class logits) |
| Classes | `video`, `voip`, `web`, `iot`, `bulk` |
| Size (FP32 ONNX) | 2.5 KB |
| Quantization | INT8 for production (NSP runs INT8 + FP16) |
| Runtime | Hexagon NSP (compute_engine = `aim_htp`) |

`build_model.py` synthesizes a deterministic ONNX (seed=17) so the
file is byte-stable across runs. Replace it with a model trained on
ISCXVPN2016 / CIC-IDS2017 packet headers when you have real data.

## Files

```
samples/stc_classifier/
├── build_model.py         # synthesize 5-class 1D-CNN ONNX
├── generate.py            # call generate_code -> render app/
├── stc_1dcnn.onnx         # output of build_model.py
├── requirements.txt       # numpy, onnx, pytest
├── run.ps1                # uv-based venv installer + DevRel editable install
├── README.md              # this file
├── ARCHITECTURE.md        # deep architecture + KPIs
├── tests/
│   ├── conftest.py        # fixtures (sample_root, app_dir, onnx_path)
│   ├── test_smoke.py      # imports, scaffold structure, ONNX validity
│   ├── test_units.py      # softmax + input normalization unit tests
│   └── test_end_to_end.py # codegen, dry-run build, mock deploy, profile
└── app/                   # generated NWAIOS C app (17 files, modular layout)
    ├── main.c             # SIGINT-safe inference loop
    ├── tensor_io.c        # *** STC-customized: nfq stub + softmax/argmax
    ├── turnkey.c          # *** STC-customized: openlog/syslog
    ├── model_inferencing.c/h
    ├── debugging.c/h
    ├── cloud_services.c/h
    ├── service.json       # *** STC-customized: smart_traffic_classifier
    ├── ipk_control
    ├── CMakeLists.txt
    ├── Dockerfile
    ├── oci_config.json
    └── README.md
```

The three `***`-marked files were customized after generation. The rest
are the unmodified modular scaffold output.

---

## Quickstart - mock-only on a Snapdragon X laptop

```powershell
cd samples\stc_classifier

# 1. One-time setup
.\run.ps1

# 2. Synthesize the ONNX
.venv\Scripts\python.exe build_model.py

# 3. Render the C app (overwrites app/ except for the 3 customized files)
.venv\Scripts\python.exe generate.py

# 4. Run the host test suite -- 26 tests, all green
.venv\Scripts\python.exe -m pytest tests/ -q
```

### Build (dry-run via DevRel CLI)

```powershell
$DevRel = "C:\work\DevRel\DevRel"
$SDK  = "$DevRel\sdks\gwapps\1.0.0-from-source-20260521"

cd $DevRel
.venv\Scripts\python.exe -m devrel.cli.main gwapps build `
    --source C:\work\DevRel\devrelAgent\samples\stc_classifier\app `
    --target aarch64-openwrt-linux `
    --sdk-root $SDK `
    --dry-run
```

Output: the cmake configure + build commands that *would* run if you
had the cross-toolchain on PATH. Drop `--dry-run` to actually build
once you have `cmake` + the gwapps cross-toolchain installed.

### Deploy (mock LCM)

```powershell
# GATEWAY_HOST unset -> MockLCMAdapter runs the lifecycle in-process
.venv\Scripts\python.exe -m devrel.cli.main gwapps deploy `
    C:\work\DevRel\devrelAgent\samples\stc_classifier\app\stc_classifier.ipk
```

Expected output:
```
  • push stc_classifier.ipk -> /tmp/devrel_deploy/stc_classifier.ipk
  • lcm install /tmp/devrel_deploy/stc_classifier.ipk
  • lcm start stc_classifier
[OK]  app=stc_classifier state=running pid=1000
```

### Profile (NWAIOS mock)

```powershell
.venv\Scripts\python.exe -c @'
import asyncio
from devrel.adapters.factory import AdapterFactory
from devrel.config import load_config
from devrel.core.operations.profile_workload import profile_workload
report = asyncio.run(profile_workload(
    model_path="/var/run/nwaios/stc_classifier/m.bin",
    platform="gateway", runtime="npu", duration_s=10,
    factory=AdapterFactory(load_config()),
))
print("latency:", report["latency"])
print("throughput:", report["throughput_fps"], "fps")
print("power:", report["power_mw"], "mW")
print("notes:", report["measurement_notes"])
'@
```

In mock mode without a running app, latency reports `0.0` with the
note `latency=not_measured:parser_no_match`. On a real gateway with the
app installed, NWAIOS reads `nwaios_app_stats` via the daemon socket
and returns measured numbers.

---

## Going to a real gateway

| Step | What changes |
|---|---|
| Install gwapps cross-toolchain | Pulls cmake + the aarch64-openwrt-linux compiler. After that, drop `--dry-run` from the build step. |
| `export GATEWAY_HOST=gw.local` | Flips deploy from mock to real SSH + lcmd. Phase 5b's SSH adapter is the underlying transport. |
| Start `aigw_daemon` on the gateway | Required for real-mode profiling (the daemon owns `/tmp/nwaios_ipc_ctrl.sock`). Doctor will warn until it's up. |
| Replace synthetic input feed in `tensor_io.c` | Use `nfq_open()` + `nfq_create_queue()` to pull live packet headers. Wire the queue number via `service.json` args. |
| Set `license_features` correctly | `smart_traffic_classifier` is the NWAIOS license feature ID; the gateway will refuse to start the app if the feature is not in `softsku_feature_list.conf`. |

---

## Class labels

| Index | Class | Typical traffic |
|---|---|---|
| 0 | `video` | Streaming video (HLS, DASH, RTMP) |
| 1 | `voip` | Voice / video calls (RTP, SRTP) |
| 2 | `web` | Browsing (HTTP/2, QUIC) |
| 3 | `iot` | Constrained IoT (MQTT, CoAP, periodic small payloads) |
| 4 | `bulk` | Large-file transfers (BitTorrent, S3 sync, backup) |

Defined in three places that must stay in sync:
- `app/tensor_io.c` -- `STC_CLASS_NAMES[]` array
- `app/service.json` -- `metadata.class_labels` list
- This README

The `test_class_label_set_matches_service_json` unit test enforces it.
