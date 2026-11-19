# Workflow Map

Run each module with `--help` before using a subcommand. The toolkit exposes 52
module entries representing 51 unique activities because `Configure Static IP`
appears in both the lifecycle planner and dedicated network implementation.

## Device Lifecycle and Connectivity

Module: `src/qli_device_lifecycle_apps.py`

| Command | Activity |
|---|---|
| `identity` | Device Identity Inspector |
| `first-boot` | First Boot Experience |
| `host-validate` | Host Environment Validation |
| `connectivity` | Device Connectivity Check |
| `recovery-discovery` | Device Recovery Discovery |
| `flash` | Flash Latest QLI Build |
| `verify-flash` | Verify Flash Succeeded |
| `installed-version` | Identify Installed Version |
| `roll-forward` | Roll Forward from Old Image |
| `recover` | Recover Misconfigured Device |
| `wifi-join` | Join New WiFi Network |
| `wifi-switch` | Switch WiFi Networks |
| `static-ip` | Configure Static IP planning |
| `ssh` | SSH to Device |
| `transfer` | Transfer File to Device |

Dedicated static-IP module: `src/qli_network_apps.py`

| Command | Purpose |
|---|---|
| `inspect` | Inspect DHCP/static state without changes |
| `configure-static` | Plan or persist a static address; dry-run by default |
| `verify` | Compare persistent profile and live state |
| `restore-dhcp` | Plan or restore DHCP settings |

## Audio, Camera, and Storage

Module: `src/qli_media_storage_apps.py`

| Command | Activity |
|---|---|
| `beep` | Speaker Beep |
| `multi-tone` | Multi Tone Generator |
| `play-wav` | Play WAV File |
| `record-audio` | Record Audio Sample |
| `audio-loopback` | Audio Loopback Test |
| `capture-image` | Capture Single Image |
| `timestamped-photo` | Save Timestamped Photos |
| `burst` | Capture Burst Images |
| `camera-metadata` | Display Camera Metadata |
| `motion-snapshot` | Motion Snapshot Trigger |
| `create-log` | Create Log File |
| `read-config` | Read Configuration File |
| `store-photo` | Store Photo to Disk |
| `storage-capacity` | Storage Capacity Reporter |
| `rotate-logs` | Rotate Log Files |

## AI and Model Workflows

Module: `src/qli_ai_apps.py`

| Command | Activity |
|---|---|
| `download-model` | Download Model from AI Hub |
| `classify` | Run Image Classification |
| `top5` | Top 5 Predictions Viewer |
| `dog-detector` | Dog vs Non Dog Detector |
| `object-detect` | Object Detection on Camera Image |
| `compare-models` | Compare Two AI Models |
| `benchmark` | Inference Timing Benchmark |
| `confidence` | Confidence Score Analyzer |
| `device-qna` | AI Powered Device Q&A |
| `camera-agent` | Camera Observation Agent |

Arguments after `--command` belong to the external runner; place `--command`
last. Use `{input}` only when the runner needs the image at a specific argument
position. Otherwise the wrapper appends the input path.

## Device Agents

| Module | Activity |
|---|---|
| `src/qli_audio_event_agent.py` | Audio Event Agent |
| `src/qli_device_health_agent.py` | Device Health Agent |
| `src/qli_a2a_agent.py` | On-Device A2A Device Health Agent |

## Debugging and Deployment

Module: `src/qli_debug_deploy_apps.py`

| Command | Activity |
|---|---|
| `remote-debug` | Remote Debug Hello World |
| `breakpoint` | Breakpoint Validation |
| `crash` | Crash Investigation |
| `logs` | Log Based Diagnostics |
| `deploy-hello` | Deploy Hello World |
| `deploy-updated` | Deploy Updated Build |
| `deploy-second` | Deploy to Second Device |
| `clean-build` | Clean Build Deploy Verify |

## Evidence and Deliverables

| Tool | Purpose |
|---|---|
| `scripts/qli_device_validation.py` | Collect non-destructive baseline evidence over SSH |
| `scripts/build_qli_device_summary.py` | Normalize baseline and deep evidence |
| `scripts/create_qli_device_workbook.py` | Populate a device workbook from a template |
| `scripts/create_qli_device_report.ps1` | Generate a Word readiness report |
| `scripts/format_workbook.ps1` | Apply Excel formatting and status colors |
| `scripts/audit_sources.py` | Extract reference DOCX text and workbook inventory |
| `scripts/test_uvc_quirks.sh` | Run controlled UVC diagnostics and restore settings |
