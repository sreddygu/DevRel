# QLI Execution Workflow Catalog

QLI Dogfooding exposes 51 unique executable workflows through Python CLI modules. The toolkit reports 52 module entries because `Configure Static IP` appears in both the lifecycle planner and the dedicated NetworkManager module; it is counted once as a developer activity.

Synapse skills select and validate these execution capabilities. The CLI modules perform the underlying device, host, AI, diagnostic, and reporting work.

## Run a Workflow

Run commands from the `qli_dogfooding` project root. Every execution module supports `--help` and `--list-workflows`.

```powershell
py -3 .\src\qli_device_lifecycle_apps.py --list-workflows
py -3 .\src\qli_device_lifecycle_apps.py connectivity --help
```

Generic pattern:

```powershell
py -3 .\src\<module>.py <command> [options]
```

State-changing actions, including flashing, recovery, network changes, controlled crash tests, and overwriting deliverables, require explicit approval. The QLI Linux domain skill defines these safety boundaries: [`qli-linux-domain`](../skills/qli-linux-domain/SKILL.md).

## Inventory

| Group | Unique workflows | Execution modules |
| --- | ---: | --- |
| Device lifecycle and connectivity | 16 | `qli_device_lifecycle_apps.py`, `qli_network_apps.py` |
| Audio, camera, and storage | 15 | `qli_media_storage_apps.py` |
| AI and model operations | 10 | `qli_ai_apps.py` |
| Device agents | 3 | `qli_audio_event_agent.py`, `qli_device_health_agent.py`, `qli_a2a_agent.py` |
| Debugging and deployment | 8 | `qli_debug_deploy_apps.py` |
| **Total** | **51** | **Eight executable Python modules** |

## Device Lifecycle and Connectivity

Module: `src/qli_device_lifecycle_apps.py`

| Command | Activity |
| --- | --- |
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

Dedicated static-IP execution uses `src/qli_network_apps.py`:

| Command | Purpose |
| --- | --- |
| `inspect` | Inspect DHCP/static state without changes. |
| `configure-static` | Plan or persist a static address; dry-run by default. |
| `verify` | Compare persistent profile and live state. |
| `restore-dhcp` | Plan or restore DHCP settings. |

The two modules provide complementary execution surfaces for one unique `Configure Static IP` workflow: lifecycle planning plus NetworkManager inspection, persistence, verification, and rollback.

## Audio, Camera, and Storage

Module: `src/qli_media_storage_apps.py`

| Command | Activity |
| --- | --- |
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

## AI and Model Operations

Module: `src/qli_ai_apps.py`

| Command | Activity |
| --- | --- |
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

When an AI workflow accepts `--command`, place it last because subsequent arguments belong to the external model runner. Use `{input}` only when the runner requires a specific image argument position; otherwise the wrapper appends the input path.

## Device Agents

| Module | Activity |
| --- | --- |
| `src/qli_audio_event_agent.py` | Audio Event Agent |
| `src/qli_device_health_agent.py` | Device Health Agent |
| `src/qli_a2a_agent.py` | On-Device A2A Device Health Agent |

## Debugging and Deployment

Module: `src/qli_debug_deploy_apps.py`

| Command | Activity |
| --- | --- |
| `remote-debug` | Remote Debug Hello World |
| `breakpoint` | Breakpoint Validation |
| `crash` | Crash Investigation |
| `logs` | Log Based Diagnostics |
| `deploy-hello` | Deploy Hello World |
| `deploy-updated` | Deploy Updated Build |
| `deploy-second` | Deploy to Second Device |
| `clean-build` | Clean Build Deploy Verify |

## Evidence and Deliverable Tooling

| Tool | Purpose |
| --- | --- |
| `scripts/qli_device_validation.py` | Collect non-destructive baseline evidence over SSH. |
| `scripts/build_qli_device_summary.py` | Normalize baseline and deep evidence. |
| `scripts/create_qli_device_workbook.py` | Populate a device workbook from a template. |
| `scripts/create_qli_device_report.ps1` | Generate a Word readiness report. |
| `scripts/format_workbook.ps1` | Apply Excel formatting and status colors. |
| `scripts/audit_sources.py` | Extract reference DOCX text and workbook inventory. |
| `scripts/test_uvc_quirks.sh` | Run controlled UVC diagnostics and restore settings. |

These tools support the [`baseline-evidence-collection`](../skills/baseline-evidence-collection/SKILL.md), [`diagnostic-log-collection`](../skills/diagnostic-log-collection/SKILL.md), domain skills and the [`readiness-report-generation`](../skills/readiness-report-generation/SKILL.md) MCP tool.

## Relationship to Synapse Skills

| Synapse layer | Role in execution |
| --- | --- |
| Context document | `qli-linux-domain`: injected before any skill; applies QLI Linux support boundaries, safety behavior, evidence expectations, and ownership. |
| Domain | Chooses and validates one bounded operation that needs conditional judgment, such as baseline evidence or diagnostics. |
| Shared tooling (MCP) | Deterministic single-step operations such as connectivity validation, AI benchmark, and report generation. |
| Journey | Coordinates selected operations for a readiness or benchmarking outcome. |
| Agent | `qli-readiness-agent`: interprets developer intent, presents the plan, obtains approvals, records checkpoints, and adapts after failures. |

The complete skill catalog and routing diagrams are in [`skills/README.md`](../skills/README.md). The detailed journey mapping is maintained in [`workflow-map.md`](../skills/developer-readiness-assessment/references/workflow-map.md).
