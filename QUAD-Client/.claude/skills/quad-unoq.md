---
name: quad-unoq
description: Use when the user asks to interact with Arduino UNO Q / QCS2210 board -- configure, flash, deploy, debug, monitor, profile, extract logs, check status, update firmware, run stability/performance/power tests, or develop applications targeting UNO-Q family boards. Triggers on "uno-q", "unoq", "arduino", "qcs2210", "board status", "flash firmware", "target device", "on-device testing".
allowed-tools:
  - Bash(quad-client *)
  - Bash(ssh *)
  - Bash(scp *)
  - Bash(adb *)
---

# QUAD UNO-Q Board Interaction (client-light)

Develop, deploy, test, and manage applications on the Arduino UNO Q (QCS2210) and family of Qualcomm Linux-based boards.

**Why local first:** every operation is SSH/SCP/ADB plumbing the client can do directly. The `quad-client unoq <cmd>` CLI exposes 12 typed subcommands so the skill becomes a thin router. No MCP server is involved.

## Board Family Reference

| Board | SoC | NPU | NPU TOPS | GPU | CPU | RAM | Hexagon |
|-------|-----|-----|----------|-----|-----|-----|---------|
| Arduino UNO Q | QCS2210 | Hexagon DSP V66 | 1.0 | Adreno 504 (0.4 TFLOPS) | 4x Kryo @ 2.0 GHz | 2 GB | v66 |
| Arduino Portenta Q | QCS6490 | Hexagon V69 | 12.0 | Adreno 643 (1.5 TFLOPS) | Kryo 670 @ 2.7 GHz | 8 GB | v69 |

## Interfaces

The board connects via:
1. **SSH** (primary) -- handled by `quad-client unoq <cmd>` for development, deploy, run, log extraction.
2. **ADB** (alternative) -- if board exposes Android Debug Bridge; use the OS `adb` directly for now.
3. **Serial/UART** -- early boot logs, bootloader, firmware flash. Manual: `screen /dev/ttyUSB0 115200` (Linux/macOS) or `putty -serial COM3 -sercfg 115200` (Windows).
4. **JTAG** (advanced) -- low-level debug; out of scope for this skill.

## Prerequisites

Before any board interaction, verify SSH connectivity:
```bash
quad-client unoq status <board-ip> --user root
```

If SSH is not configured, run `quad-client unoq configure <board-ip>` first to print a `quad.toml` `[target.*]` stanza you can paste into the project config.

The OS `ssh` binary is required (Windows users: install OpenSSH Client via "Add Optional Feature"). The user's `~/.ssh/config` and ssh-agent are respected automatically -- no paramiko, no extra deps.

---

## Commands & Workflows

### 1. Board Status (`/quad-unoq status`)

```bash
quad-client unoq status <board-ip> --user root
```

Bundles connectivity check + uname + os-release + memory + disk + loadavg + Hexagon dmesg + thermal sensors + running inference processes into one SSH session.

**Expected output:**
```
[OK] status -- all probes succeeded (1240 ms)

--- alive ---
ALIVE

--- uname ---
Linux unoq-board 5.4.x ...

--- memory ---
              total        used        free      shared  buff/cache   available
Mem:           2048         412         983         ...
... etc
```

---

### 2. Configure Board (`/quad-unoq configure`)

```bash
quad-client unoq configure <board-ip> --user root
```

Prints a `[target.*]` stanza for `quad.toml`. Append it to your project's `quad.toml`. Defaults: workspace `/data/local/tmp/quad/`, hexagon v66, max RAM 2048 MB.

---

### 3. Deploy Application (`/quad-unoq deploy`)

```bash
quad-client unoq deploy <board-ip> \
  --app ./build/inference_app \
  --model ./models/mobilenetv2_int8.dlc \
  --user root
```

Pipeline: pre-flight free space, scp app + model under `/data/local/tmp/quad/`, verify the artifacts landed.

For C++ apps, cross-compile first:
```bash
aarch64-linux-gnu-g++ -O2 -o build/inference_app main.cpp \
  -I/opt/snpe/include -L/opt/snpe/lib/aarch64-linux-gcc -lSNPE
```

---

### 4. Firmware (`/quad-unoq firmware`)

```bash
quad-client unoq firmware <board-ip>
```

Read-only check: build version, kernel, DSP skel libs in `/usr/lib/rfsa/adsp/`, SNPE libs in `/opt/snpe/lib`. Actual flashing is left to the user via `fwupdate` or `fastboot` over serial -- documented in the original recovery playbook below.

**Serial flash fallback (UART):** identical to before; not wrapped because it's interactive.

---

### 5. Log Extraction (`/quad-unoq logs`)

```bash
quad-client unoq logs <board-ip> --since 60
```

Pulls `dmesg | tail -200`, `journalctl --since N minutes`, recent SNPE logs, DSP trace, and any tombstones in one pass. Output goes to stdout; redirect to a file as needed.

**Log analysis priorities:**
1. DSP signature failures -> missing/mismatched skel library
2. Memory allocation failures -> model too large for 2 GB RAM
3. Thermal throttling -> sustained workload exceeding TDP
4. Runtime errors -> SNPE/QNN version mismatch

---

### 6. Debug Issues (`/quad-unoq debug`)

```bash
quad-client unoq debug <board-ip>
```

Diagnostic checklist: DSP state (`/sys/class/remoteproc/remoteproc0/state`), SNPE version on device, recent kernel errors, recent crashes.

**Common failure modes & resolution:**

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `Failed to load DSP` | Skel lib missing | Push `libSnpeDspV66Skel.so` to `/usr/lib/rfsa/adsp/` |
| `SNPE_ERROR_RUNTIME_INIT` | DSP signature mismatch | Sign skel with `snpe-skel-signer` or use unsigned testsig |
| `Out of memory` | Model exceeds 2GB RAM | Quantize to INT8, reduce batch, or partition model |
| `Inference timeout` | DSP hang | Reboot DSP: `echo stop > /sys/class/remoteproc/remoteproc0/state` |
| `Bus error (SIGBUS)` | Alignment issue in model | Re-convert model with `--force_aligned_tensors` |
| `Connection refused` | SSH daemon down | Connect via serial, restart sshd |
| `Thermal shutdown` | Overheating | Add heatsink, reduce perf_profile from `burst` to `balanced` |

---

### 7. Performance Testing (`/quad-unoq perf`)

```bash
quad-client unoq perf <board-ip> \
  --model /data/local/tmp/quad/models/mobilenetv2_int8.dlc \
  --duration 30 \
  --profile burst
```

Runs `snpe-net-run --debug` and parses out `Total Inference` / `Init Time` lines.

**KPI Framework (UNO Q targets):**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Latency (P50) | < 33 ms (30 FPS) | `snpe-net-run --duration 30` |
| Latency (P99) | < 50 ms | Parse timing output for percentiles |
| Throughput | > 30 inferences/sec | `snpe-throughput-net-run` |
| First inference | < 500 ms | Time from process start to first output |
| Model load time | < 2 s | `--debug` flag shows init time |

---

### 8. Stability Testing (`/quad-unoq stability`)

```bash
quad-client unoq stability <board-ip> \
  --model /data/local/tmp/quad/models/mobilenetv2_int8.dlc \
  --duration 3600
```

Kicks off a soak loop in the background on the device and returns the remote PID. Pull `/data/local/tmp/quad/logs/soak_result.txt` later via `quad-client unoq logs`.

**Stability KPIs:**

| Metric | Target | Duration |
|--------|--------|----------|
| Success rate | > 99.9% | 1 hour soak |
| Memory leak | < 5 MB growth/hour | Monitor RSS over time |
| Thermal stability | < 75 C sustained | Continuous monitoring |
| No DSP crashes | 0 remoteproc restarts | `dmesg | grep "remoteproc.*crashed"` |
| Latency drift | < 10% P99 increase | Compare first 5 min vs last 5 min |

---

### 9. Power Profiling (`/quad-unoq power`)

```bash
quad-client unoq power <board-ip>
```

Samples INA / cpufreq / GPU clock / thermal sensors in one pass.

**Power KPIs:**

| Mode | Expected Power | Use Case |
|------|---------------|----------|
| `low_balanced` | ~0.5W NPU | Always-on sensing |
| `balanced` | ~0.8W NPU | Intermittent inference |
| `high_performance` | ~1.2W NPU | Real-time vision |
| `burst` | ~1.5W NPU | Benchmark only (thermal limit) |

To compare modes, run `quad-client unoq perf` with each `--profile` value.

---

### 10. Application Lifecycle (`/quad-unoq app`)

```bash
quad-client unoq app <board-ip> myapp --action start
quad-client unoq app <board-ip> myapp --action status
quad-client unoq app <board-ip> myapp --action stop
```

Wraps `systemctl <action> quad-inference@<name>`. Falls back to `journalctl -u <name>` for status output.

---

### 11. OTA Update (`/quad-unoq ota`)

```bash
quad-client unoq ota <board-ip> --archive ./app_v2.tar.gz
```

Uploads the archive to `/data/local/tmp/quad/updates/` and extracts under `apps/`. Use `app --action restart` afterwards to pick up the new bits.

For multi-board fleet management, script around `quad-client unoq` -- the CLI is idempotent and safe to fan out.

---

### 12. End-to-End Test Suite (`/quad-unoq test`)

```bash
quad-client unoq test <board-ip>
```

Invokes `bash run_tests.sh` under the workspace and streams its stdout back. The test script is your responsibility to deploy (typically via `deploy` or `ota`).

**Test categories:**

1. **Functionality** -- correct inference output matches golden reference
2. **Performance** -- latency/throughput within KPI thresholds
3. **Stability** -- 1-hour soak with < 0.1% failure rate
4. **Power** -- stays within thermal/power envelope
5. **Recovery** -- graceful handling of DSP crash, OOM, thermal throttle

---

## Error Recovery Playbook

| Situation | Recovery Steps |
|-----------|---------------|
| Board unreachable (SSH timeout) | 1. Check network cable/WiFi. 2. Try serial console. 3. Power cycle board. |
| DSP hung (inference hangs) | 1. `echo stop > /sys/class/remoteproc/remoteproc0/state` 2. `echo start > ...` 3. Re-run |
| Out of memory | 1. Kill other processes. 2. Use smaller model. 3. Quantize to INT8. 4. Enable swap. |
| Thermal shutdown | 1. Wait 2 min for cooldown. 2. Reduce perf_profile. 3. Add heatsink. 4. Reduce duty cycle. |
| Corrupted filesystem | 1. Boot to recovery via serial. 2. `fsck` partition. 3. Re-flash if unrecoverable. |
| Model gives wrong output | 1. Verify model checksum. 2. Compare with host inference. 3. Check quantization accuracy. |

---

## Integration with QUAD Workflow

This skill works with the full QUAD pipeline:

1. **Develop** -- Write app using `/quad-codegen` (generates `.ino` or C++ for QCS2210)
2. **Convert** -- Use `/quad-convert` to quantize model to INT8 for Hexagon V66
3. **Deploy** -- Use `quad-client unoq deploy` to push app + model to board
4. **Test** -- Use `quad-client unoq test` to run full KPI validation
5. **Profile** -- Use `quad-client unoq perf` and `quad-client unoq power` for optimization
6. **Stabilize** -- Use `quad-client unoq stability` for soak testing
7. **Ship** -- Use `quad-client unoq ota` for production deployment

---

## Tips

- Always use `--profile balanced` for sustained workloads; `burst` is for benchmarks only
- QCS2210 has 2GB RAM -- keep model + runtime under 1.5GB to leave headroom for OS
- INT8 quantization is mandatory for DSP on V66 -- FP32 falls back to CPU
- If latency is inconsistent, check thermal throttling first (sample with `quad-client unoq power`)
- Use `snpe-diagview` on host to visualize profiling data pulled from device
- For multi-model pipelines, use `snpe-parallel-run` or implement model chaining in app code
- All `quad-client unoq` subcommands accept `--json` for machine-readable output
