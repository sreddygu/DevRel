# gwapps Fault Detection — Reference AI Gateway Application

> **What this is**: a vendored snapshot of Qualcomm's reference
> fault-detection / anomaly-detection app for the AI Gateway, taken
> from the framework team's `ad.mcs.0.0` branch. It is the canonical
> production-grade pattern that DevRel's codegen aims to reproduce.
>
> **What this isn't**: not a from-scratch DevRel-generated demo. For
> that, see `samples/ai_gateway_classifier/` — the simple "first 15
> minutes" walkthrough.

---

## Why this sample matters

This is what an AI Gateway app actually looks like in production:

- Multi-module C layout (`fd/` ≈ 12 `.c` + 11 `.h` files)
- Real NWAIOS lifecycle with async callbacks for compute
  available/unavailable
- Per-band model loading (separate models for 2.4 GHz / 5 GHz / 6 GHz
  WLAN)
- `runc` OCI bundle deploy (the `config.json` here is a runtime
  spec, not the LCM service descriptor)
- `Dockerfile FROM scratch` + `build_containers.sh` packaging
- Domain-specific input pipeline (WLAN HW-queue counters, peer stats,
  rate-of-change features)
- Integration with the cloud bridge (`cia_services`), license
  verification (`license_verify`), syslog ingestion, notification
  push

DevRel's `devrel-codegen` skill produces a *minimal* scaffold today
(6 files). The fault-detection app shows the target pattern that
the codegen's `scaffold="modular"` mode (in progress) should emit
by default for production apps.

## Layout

```
upstream/                       (source-only mirror of ad/)
├── ad_build/                   build orchestrator
│   ├── build.sh                multi-arch driver
│   ├── aarch64-openwrt-linux/  per-arch CMake configs
│   ├── aarch64-prpl-linux/
│   ├── aarch64-rdk-linux/
│   ├── arm-openwrt-linux/
│   ├── incident-dashboard-frontend/   frontend stub (fetched at build)
│   ├── log_summarization/             log summarization stub
│   └── serviceability-backend/        backend stub
├── faultdetection/
│   ├── fd/                     main C app — see Layout details below
│   ├── fd_lib/                 shared library used by fd/
│   ├── incident-dashboard-frontend/   frontend assets (fetch.sh)
│   ├── log_summarization/      log post-processor
│   └── serviceability-backend/ backend service stub
├── systemad/                   placeholder for system-level daemon
└── unit_test/
    ├── ad_data_collection/
    ├── ad_debuggability/
    ├── ad_unit_test/
    └── log_summarization/
```

## Layout — `faultdetection/fd/` in detail

| File(s) | Role |
|---|---|
| `fault_detection.c/h` | Entrypoint. Signal handling, main loop, lib_init / lib_deinit, dispatch to module functions. |
| `model_inferencing.c/h` | NWAIOS lifecycle. `nwaios_lib_init` with callback, three model_load (2G/5G/6G), `nwaios_execute`, NWAIOS callback handler routing local vs. remote compute events. |
| `preprocess.c/h` | Build the input feature vector from WiFi stats. |
| `postprocess.c/h` | Decode the autoencoder reconstruction, compute anomaly score, threshold check. |
| `notification_processing.c/h` | Alert delivery — wraps the cloud bridge / transport. |
| `syslog_processing.c/h` | Pull syslog and route into the pipeline. |
| `log_capture.h` | Log collection helpers. |
| `peer_stats.h` | Domain-specific WLAN peer telemetry. |
| `wifistats_rate_of_change.c` | Feature engineering: rate-of-change for 50+ HW counters. |
| `cia_services.c/h` | Cloud bridge wrapper (HTTP/MQTT to backend). |
| `debugging.c/h` | Log levels + `log_message()` macro used everywhere. |
| `CMakeLists.txt` | Links `dl + GwAppstransport + nwaios + gwapps_license_lib + json-c`. C99, `-O2 -fstack-protector-strong`. |
| `config.json` | runc OCI bundle spec — NOT an LCM service.json. Bind-mounts `/etc/license`, `/etc/softsku-qwin-agent`, `/etc/fd`, `/dev/lm_device`. Capabilities: `NET_BIND_SERVICE`, `NET_RAW`, `NET_ADMIN`. |
| `Dockerfile` | `FROM scratch` + `COPY ad /app/ad` — produces a minimal OCI image, used as input to the runc bundle. |
| `build_containers.sh` | Builds both the docker image (`tar`) and the runc bundle (`tar.gz`). |
| Other: `.gitignore` | — |

## Build (Qualcomm internal)

This vendored copy is **source-only** — build outputs (`.so`, `.dlc`,
`.tar`, `.tar.gz`, the `ad_libs_bins/` tree) are deliberately excluded
to keep the sample tractable. To rebuild from this source:

```bash
# 1. Set up the gwapps framework + toolchains (see DevRel/DevRel_Packages/gwapps/README.md)
devrel doctor --section gwapps     # confirm SDK reachable

# 2. From a fresh gwapps_framework_uio workspace, drop this ad/ tree alongside frmwrk/
cp -r upstream  /path/to/gwapps_workspace/ad
cd /path/to/gwapps_workspace
ls    # should show: ad/  frmwrk/  qsdk/  scripts/  toolchain/

# 3. Build all four targets
cd ad/ad_build
./build.sh aarch64 openwrt
./build.sh aarch64 prpl
./build.sh aarch64 rdk
./build.sh arm openwrt
```

Outputs land under `ad/ad_libs_bins/<arch>/`. The trained `.dlc`
weights for 2.4/5/6 GHz models are produced by a separate offline
training pipeline and dropped under
`ad_libs_bins/<arch>/mylib_package/usr/sbin/WIN-NW-FD-AE-{2G,5G,6G}.dlc`.

### Third-party build artifacts (not committed)

Two classes of file this sample's build needs are **not** committed to the
repo — they are third-party and were removed per open-source review:

- **`ipkg-build`** (OpenWrt's `.ipk` packaging script, GPL). Each
  `ad_build/<arch>/build.sh` downloads it from the OpenWrt upstream on first
  run and caches it beside the script (`.gitignore`'d). Set `IPKG_BUILD_URL`
  to point at an internal mirror if your network blocks the default.
- **`<arch>-toolchain.cmake`** cross-compile configs. Supply these from your
  own OpenWrt/prpl/RDK SDK; the build sources compiler paths from the
  `toolchain/` tree (see step 1) rather than a committed toolchain file.

## How this maps to DevRel's lifecycle

| Step | This app's reality | DevRel equivalent |
|---|---|---|
| Codegen | Hand-written, multi-module | `devrel gwapps create` (Phase 3, minimal today; modular scaffold in progress) |
| Cross-compile | `ad_build/build.sh <arch>` directly invokes per-arch CMake | `devrel gwapps build --target <arch>` (Phase 4) — same logical step |
| Package | `build_containers.sh` → docker image + runc bundle | `devrel gwapps build` packs IPK today; OCI runc bundle support tracked as Phase 4b |
| Deploy | `runc` bundle installed via LCM | `devrel gwapps deploy` via LCM (Phase 5) |
| Profile | Reads `nwaios_app_stats` directly | `profile_workload --platform=gateway` (Phase 6) |

## What we learned from this reference (deltas vs the simple sample)

1. **Apps split inference into a dedicated `model_inferencing.c/h`** so
   the user replaces just that module — not `main.c`.
2. **Multiple models per app** is normal (2G + 5G + 6G here) — the
   `NWAIOS_MAX_MODELS_PER_APP = 10` limit is real.
3. **runc OCI bundle is the production deploy unit**, not raw IPK
   binaries. LCM start passes the OCI bundle path.
4. **`Dockerfile FROM scratch`** keeps the image to just the binary —
   no rootfs overhead. Bind-mounts handle `/lib`, `/usr/lib`, `/etc`
   from the host gateway.
5. **License-lib + cloud-bridge are first-class deps**, linked into
   every production app (`gwapps_license_lib`, plus CIA helpers).
6. **`-fstack-protector-strong -O2 -rdynamic -g3`** is the production
   compile profile.
7. **Domain-specific input pipelines** (`wifistats_rate_of_change.c`,
   `peer_stats.h`) — codegen can stub these but the user *will*
   replace them.

These observations are folded into Phase 3 codegen iteration —
specifically, splitting `model_inferencing` into its own module and
adding `Dockerfile` + `oci_config.json` templates. See
`DevRel/docs/GWAPPS_AD_REFERENCE_REVIEW.md` for the full readout and
`DevRel/docs/DevRel_GWAPPS_PROGRESS.md` for which template improvements
have landed.

## Source

Vendored from `gwapps_ad_temp_running/ad/` (branch `ad.mcs.0.0`).
The DevRel workspace's `gwapps_ad_temp_running/` directory holds the
full repo with binaries + `.git` history; this `samples/` copy is
source-only.
