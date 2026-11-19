# STC Classifier - Architecture

## Overview

`stc_classifier` is a Smart Traffic Classifier (STC) for IPQ-class WLAN
AI Gateways. It classifies WLAN flows into 5 application categories
(video / voip / web / iot / bulk) using a tiny 1D-CNN running on the
gateway's Hexagon NSP, then writes the decision to syslog so the
gateway's normal log shipping picks it up.

The app uses QUAD's modular gateway scaffold (17 files, mirrors
`samples/gwapps_fault_detection/`) and follows the standard AI Gateway
three-function architecture:

```
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │   INGEST /   │     │              │     │              │
   │  PREPROCESS  │────▶│  INFERENCE   │────▶│   TURNKEY    │
   │ (tensor_io)  │     │ (model_infer)│     │  (turnkey.c) │
   └──────────────┘     └──────────────┘     └──────────────┘
   nfqueue / pcap          NWAIOS NSP          openlog +
   64 header bytes         [1,1,64] -> [1,5]   syslog(LOG_INFO)
   norm to [0,1]           softmax + argmax    LOG_USER facility
```

## Target platform

| Property | Value |
|---|---|
| SoC | Qualcomm IPQ-class (IPQ9574 reference) |
| NPU | Hexagon NSP |
| Compute engine name | `aim_htp` (NWAIOS) |
| OS | OpenWrt (`aarch64-openwrt-linux`) |
| RAM budget | ~512 MB total; loaded model ~256 KB |
| Power envelope | ~3 W sustained |
| Lifecycle manager | `lcmd` + `nwaios_lib` |
| SDK | gwapps 1.0.0-from-source-20260521 (vendored under `QUAD/sdks/gwapps/`) |

## Components

| File | Responsibility | Key APIs |
|---|---|---|
| `main.c` | SIGINT-safe inference loop, calls into the three modules | `signal()`, `usleep()` |
| `tensor_io.c` | Preprocess + postprocess (STC-specific) | `prepare_inputs()`, `consume_outputs()`, `softmax()`, `stc_class_name()` |
| `model_inferencing.c/h` | NWAIOS lifecycle wrapper | `nwaios_lib_init`, `nwaios_model_load`, `nwaios_execute`, `nwaios_get_stats` |
| `turnkey.c/h` | Action stage - syslog sink for STC | `openlog()`, `syslog()`, `closelog()` |
| `debugging.c/h` | Logging macros (`LOG_INFO`, `LOG_TRACE`, etc.) | `vfprintf`, level filtering |
| `cloud_services.c/h` | Cloud egress stub (unused by STC) | placeholder |
| `service.json` | LCM service descriptor | license_features, restart_policy, keepalives |
| `ipk_control` | OpenWrt IPK metadata | name, version, depends |
| `CMakeLists.txt` | Cross-compile recipe | links libnwaios + libGwAppstransport |
| `Dockerfile`, `oci_config.json` | runc OCI bundle for container deploys | optional |

## Model card

| Property | Value |
|---|---|
| Name | `stc_1dcnn` |
| Architecture | Conv1d(1→8, k=3) → Relu → Conv1d(8→16, k=3) → Relu → GlobalAveragePool → MatMul(16→5) |
| Input | `[1, 1, 64]` float32; 64 packet header bytes / 255.0 |
| Output | `[1, 5]` float32; per-class logits (softmax applied in postprocess) |
| Classes | `video`, `voip`, `web`, `iot`, `bulk` |
| Size (FP32 ONNX) | 2.5 KB |
| Size (INT8 .bin / .dlc, est.) | ~1 KB |
| Calibration | Synthetic for the scaffold; replace with ISCXVPN2016 / CIC-IDS2017 for production |
| Latency target on NSP | < 1 ms (small model) |

## Data flow per iteration

```
   t=0    nfq_handle_packet()  -> 64 bytes packet header
            │
            │  (tensor_io.c)
            ▼
          float buf[64] = bytes / 255.0
            │
            │  (model_inferencing.c)
            ▼
          nwaios_execute(model_id, 0)
            │
            ▼
          float logits[5]
            │
            │  (tensor_io.c)
            ▼
          softmax + argmax -> decision_t {label, score, valid}
            │
            │  (turnkey.c)
            ▼
          syslog(LOG_INFO, "class=%s confidence=%.3f", ...)
            │
   t=1ms  loop repeats
```

In the scaffold, `prepare_inputs` synthesizes deterministic header
bytes from a sequence counter so the loop runs without nfqueue. Real
deployments replace it with `nfq_open()` + `nfq_create_queue()`.

## Deployment lifecycle

```
   build_model.py  -> stc_1dcnn.onnx
        │
        │  convert_model (qnn INT8) -- mock-OK, real-mode uses qairt-quantizer
        ▼
   stc_classifier.bin
        │
        │  generate.py / generate_code(scaffold="modular")
        ▼
   app/{17 files}
        │
        │  quad gwapps build --target aarch64-openwrt-linux
        ▼
   app/stc_classifier.ipk
        │
        │  quad gwapps deploy --host <gw>
        ▼
   ssh push -> /tmp/quad_deploy/stc_classifier.ipk
        │
        │  lcm install + lcm start
        ▼
   /usr/bin/stc_classifier  (running, restart_policy=on-failure)
        │
        │  profile_workload(platform=gateway)
        ▼
   nwaios_get_stats() -> latency / throughput / power per engine
```

## KPIs (target)

These are the production targets for an IPQ9574 NSP. Mock mode on a
Snapdragon X laptop returns 0 for latency (no real app running) - the
KPIs apply once the IPK is installed on a real gateway.

| Metric | Target | Measured by |
|---|---|---|
| Latency P50 (NSP) | < 1 ms | NWAIOS `nwaios_app_stats` |
| Latency P99 | < 5 ms | NWAIOS |
| Throughput | > 1000 fps | derived from latency |
| Memory resident | < 16 MB | `/proc/<pid>/status` |
| Power (NSP only) | < 0.5 W incremental | host_thermal_model (estimate) |
| App restart count | 0 over 24h | `lcm status` polled by ops |
| License gate | `smart_traffic_classifier` in `softsku_feature_list.conf` | service.json refused at start otherwise |

## Power & thermal

The NSP runs at the gateway's "balanced" perf profile by default, which
keeps incremental power well under the 3 W gateway envelope. For
always-on classification at sub-millisecond cadence, NSP is the right
fit; the CPU fallback (compute_engine = `cpu`) costs roughly 30× more
energy per inference and is only acceptable for diagnostic mode.

## Mock vs real

| Concern | Mock (this laptop) | Real (gateway) |
|---|---|---|
| Build | `--dry-run` prints cmake commands | Cross-compiles via gwapps toolchain |
| Deploy | `MockLCMAdapter` returns `state=running` in-process | SSH + `lcm install` + `lcm start` |
| Profile | NWAIOS mock returns shape with 0 latency + `not_measured` notes | Real `nwaios_app_stats` from `aigw_daemon` |
| License gate | not enforced | enforced by `lcmd` against `softsku_feature_list.conf` |
| nfqueue input | synthesized from sequence counter | live packet headers |

## Test gates passed

- `pytest tests/ -q` -- 26 tests, exit 0
- `quad gwapps build --dry-run` -- emits valid cmake plan + IPK target
- `quad gwapps deploy <ipk>` (mock) -- `state=running pid=1000`
- `profile_workload(platform=gateway, runtime=npu)` -- returns
  NWAIOS-shaped report with `measurement_notes` annotation

## See also

- `samples/ai_gateway_classifier/` - 15-minute MobileNetV2 walkthrough
- `samples/gwapps_fault_detection/` - production framework reference
- `QUAD/docs/QUAD_GWAPPS_INTEGRATION_PLAN.md` - full integration plan
- `QUAD/templates/gateway/c_modular/` - the template directory this scaffold came from
