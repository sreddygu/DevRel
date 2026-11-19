# QLI Dogfooding

This directory contains reusable QLI device applications, validation utilities, workbook tooling, evidence, and historical IQ8 dogfooding artifacts. The Python applications under `src/` are device-generic and can be configured for IQ8, IQ9, and other Linux-based QLI targets.

[`skills/developer-readiness-assessment/`](skills/developer-readiness-assessment/)
packages the toolkit as the framework-neutral **Developer Readiness Assessment**
skill. Any agent framework or model router can index
[`skill.yaml`](skills/developer-readiness-assessment/skill.yaml), load
[`SKILL.md`](skills/developer-readiness-assessment/SKILL.md), and use the
existing `src/` and `scripts/` tools for full assessments, focused reruns,
comparisons, workbooks, and reports. `agents/openai.yaml` is an optional adapter,
not a core dependency.

## Synapse Skills

The toolkit publishes three composable Synapse layers plus a shared tooling layer
and defines the agent orchestration contract for the hosting framework:

| Layer | QLI implementation | Purpose |
| --- | --- | --- |
| Context | `skills/qli-linux-domain/` | Inject QLI Linux support, safety, evidence, and ownership context before any skill runs. Not a selectable skill. |
| Domain | `skills/host-environment-validation/`, `skills/device-identity-discovery/`, `skills/baseline-evidence-collection/`, `skills/ai-model-execution/`, `skills/diagnostic-log-collection/` | Execute one validated operation requiring conditional judgment. |
| Journey | `skills/developer-readiness-assessment/` | Compose a full readiness, rerun, comparison, or deliverable outcome. |
| MCP Tools | `skills/mcp-tools.yaml` — `device-connectivity-validation`, `ai-inference-benchmark`, `readiness-report-generation` | Deterministic single-step operations; call directly, no skill wrapper. Check the shared MCP inventory first. |
| Agent | `skills/qli-readiness-agent/` | Select approved skills, explain the plan, enforce approvals, validate results, and route failures to recovery. The hosting framework runs it. |

Start with `developer-readiness-assessment` for an outcome-based request, or
select an individual domain skill for one bounded operation (or call an MCP tool
directly for a deterministic single step). See
[`CONTEXT.md`](CONTEXT.md) for the canonical layer terms and
[`docs/adr/0001-adopt-synapse-skill-layers.md`](docs/adr/0001-adopt-synapse-skill-layers.md)
for the architectural decision. The complete catalog is in
[`skills/README.md`](skills/README.md).

For a meeting-ready walkthrough of this implementation as a Synapse proof of
concept, including a safe connectivity demonstration, evidence, decision asks,
and current integration boundaries, see
[`docs/synapse-guide.md`](docs/synapse-guide.md).

## Use the Developer Readiness Assessment Skill

Skill location:

```text
skills/developer-readiness-assessment/
```

The framework-neutral skill ID is `developer-readiness-assessment`. Agent
frameworks should index
[`skills/developer-readiness-assessment/skill.yaml`](skills/developer-readiness-assessment/skill.yaml)
and load
[`skills/developer-readiness-assessment/SKILL.md`](skills/developer-readiness-assessment/SKILL.md)
when a user asks for device readiness, dogfooding, workflow reruns, device
comparisons, or readiness workbook/report generation.

Generic explicit invocation for any agent or model router:

```text
Use the developer-readiness-assessment skill to run a safe full readiness
assessment for DEVICE_LABEL at DEVICE_IP and produce evidence, a workbook, and
a Word report.
```

Focused rerun example:

```text
Use the developer-readiness-assessment skill to rerun the camera, object
detection, and camera observation workflows on this device. Preserve existing
evidence and update the workbook and report only from verified results.
```

OpenAI/Codex-compatible adapters may invoke the optional skill alias directly:

```text
$developer-readiness-assessment Assess the connected IQ8 device and report all
Completed, Partial, Blocked, Not Tested, and Not Applicable workflows.
```

Validate the skill and discover all toolkit workflows from this
`qli_dogfooding` directory:

```powershell
py -3 .\skills\developer-readiness-assessment\scripts\inspect_toolkit.py `
  --project-root .
```

Expected result: **52 module entries representing 51 unique workflows**, with
`Toolkit validation: PASS`.

Framework integration guidance is available in
[`framework-integration.md`](skills/developer-readiness-assessment/references/framework-integration.md).

Validate local Markdown links and heading anchors:

```powershell
py -3 .\scripts\validate_markdown_links.py --project-root .
```

Expected result: `Markdown link validation: PASS`.

## Directory Layout

| Path | Purpose |
| --- | --- |
| `src/` | Generic device application and agent CLIs covering all 51 dogfooding workflows. |
| `scripts/` | Workbook automation, validation, reporting, formatting, and recovery scripts. |
| [`skills/`](skills/) | Synapse context document, domain skills, MCP tool specs, and journey skill package. |
| [`CONTEXT.md`](CONTEXT.md) | Canonical QLI Synapse vocabulary. |
| [`docs/adr/`](docs/adr/) | Durable architecture decisions. |
| `resources/` | Workbooks, exported JSON data, rendered PDFs, and preserved rerun workbooks. |
| `reference/` | Source DOCX reference documents. |
| `audit/` | Extracted reference text and workbook inventory data. |
| `evidence/` | Device validation results intended as durable evidence. |

## Requirements

- Python 3.10 or newer.
- Linux device utilities as needed: `ssh`, `scp`, `nmcli`, `v4l2-ctl`, `aplay`, `arecord`, `gdb`, `gdbserver`, and QNN/model runner tools.
- Windows PowerShell and Microsoft Excel for scripts that use Excel or Word COM automation.
- `openpyxl` for `audit_sources.py` and `create_qli_device_workbook.py`.

From the repository's `projects` directory, create and select a dedicated QLI environment:

```powershell
python -m venv .\qli_dogfooding\.venv
$python = ".\qli_dogfooding\.venv\Scripts\python.exe"
```

Install the workbook dependency when needed:

```powershell
& $python -m pip install -r .\qli_dogfooding\requirements.txt
```

Do not store passwords, API tokens, SSH private keys, or Wi-Fi credentials in this repository. Pass credentials through a password manager, environment variables, SSH agent, or interactive tooling.

## Discover Available Workflows

Every Python application supports `--help` and `--list-workflows`:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py --list-workflows
& $python .\qli_dogfooding\src\qli_network_apps.py --list-workflows
& $python .\qli_dogfooding\src\qli_media_storage_apps.py --list-workflows
& $python .\qli_dogfooding\src\qli_ai_apps.py --list-workflows
& $python .\qli_dogfooding\src\qli_debug_deploy_apps.py --list-workflows
& $python .\qli_dogfooding\src\qli_audio_event_agent.py --list-workflows
& $python .\qli_dogfooding\src\qli_device_health_agent.py --list-workflows
& $python .\qli_dogfooding\src\qli_a2a_agent.py --list-workflows
```

Use module or subcommand help for complete options:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py --help
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py connectivity --help
```

## Device Lifecycle and Connectivity

`src/qli_device_lifecycle_apps.py` covers identity, first boot, host validation, connectivity, recovery discovery, flashing, version checks, Wi-Fi, SSH, and file transfer.

Inspect the local device:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py identity
```

Check whether SSH is reachable:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py connectivity --host DEVICE_IP --port 22
```

Run a remote command:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py ssh --host DEVICE_IP --user root uname -a
```

Transfer a file:

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py transfer --host DEVICE_IP --user root --source .\app.py --destination /tmp/app.py
```

Flashing, recovery, Wi-Fi changes, and static-IP changes default to plan-only output. Review the generated command and add `--execute` only when the target and parameters are correct.

```powershell
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py flash --command FLASH_TOOL ARGUMENTS
& $python .\qli_dogfooding\src\qli_device_lifecycle_apps.py flash --execute --command FLASH_TOOL ARGUMENTS
```

For Wi-Fi passwords, use `--password-env` with an environment variable instead of entering the password in source or command history.

### Persistent Static IPv4

`src/qli_network_apps.py` implements the `Configure Static IP` workflow with
NetworkManager. Run it on the QLI device. It discovers the active connection,
derives a candidate from the current subnet, performs a best-effort conflict
probe, and prints a dry-run plan by default.

Inspect the current DHCP/profile state:

```bash
python3 src/qli_network_apps.py inspect --interface wlp1s0
```

Plan a static host address using the current subnet and gateway:

```bash
python3 src/qli_network_apps.py configure-static \
  --interface wlp1s0 \
  --host-number 250
```

Persist the profile without cycling the active remote connection:

```bash
python3 src/qli_network_apps.py configure-static \
  --interface wlp1s0 \
  --host-number 250 \
  --execute \
  --backup /root/qli-network-before-static.json
```

Use `--execute --activate` only from a serial/local console or during an
approved network-maintenance window. Activation may terminate SSH. Reserve the
address in DHCP or confirm it with the network administrator; a failed ping does
not prove that an address is unused.

Verify or restore DHCP:

```bash
python3 src/qli_network_apps.py verify \
  --interface wlp1s0 \
  --expected-address 192.168.29.250/24

python3 src/qli_network_apps.py restore-dhcp \
  --interface wlp1s0 \
  --execute --activate
```

## Audio, Camera, and Storage

`src/qli_media_storage_apps.py` covers tones, WAV playback and recording, loopback, image capture, camera metadata, motion snapshots, logs, configuration files, photo storage, capacity reporting, and log rotation.

Generate a WAV beep without playing it:

```powershell
& $python .\qli_dogfooding\src\qli_media_storage_apps.py beep --output .\qli_dogfooding\resources\beep.wav
```

Run camera workflows on the device. Discover the correct node with
`v4l2-ctl --list-devices`; `/dev/video28` below is an example USB-camera node:

```bash
python3 src/qli_media_storage_apps.py camera-metadata --device /dev/video28
```

Capture one image and timestamped or burst photos:

```bash
python3 src/qli_media_storage_apps.py capture-image \
  --device /dev/video28 --width 640 --height 480 --pixel-format MJPG \
  --output /tmp/capture.jpg

python3 src/qli_media_storage_apps.py timestamped-photo \
  --device /dev/video28 --directory /tmp/photos --suffix .jpg

python3 src/qli_media_storage_apps.py burst \
  --device /dev/video28 --directory /tmp/burst --suffix .jpg \
  --count 3 --interval 0.5
```

Run the lightweight byte-difference motion trigger and store a captured photo:

```bash
python3 src/qli_media_storage_apps.py motion-snapshot \
  --device /dev/video28 --directory /tmp/motion \
  --samples 3 --interval 0.5 --threshold 0.001 --suffix .jpg

python3 src/qli_media_storage_apps.py store-photo \
  --source /tmp/capture.jpg --destination /root/photos/capture.jpg
```

Successful captures report `returncode: 0` and a nonzero `output_bytes` value.
The motion workflow is a dependency-free compressed-frame byte heuristic, not
an object-aware motion detector; tune `--threshold` for each camera and scene.

Report storage capacity:

```powershell
& $python .\qli_dogfooding\src\qli_media_storage_apps.py storage-capacity --path /
```

Log rotation is plan-only until `--execute` is supplied.

## AI and Model Applications

`src/qli_ai_apps.py` covers model downloads, classification, prediction display, dog detection, object detection, model comparison, benchmarking, confidence analysis, device Q&A, and camera observation.

Display the five highest scores:

```powershell
& $python .\qli_dogfooding\src\qli_ai_apps.py top5 --scores scores.json --labels labels.txt
```

Analyze confidence scores:

```powershell
& $python .\qli_dogfooding\src\qli_ai_apps.py confidence --scores scores.json --labels labels.txt
```

Run an external classifier. Use `{input}` where the runner expects the image path:

```powershell
& $python .\qli_dogfooding\src\qli_ai_apps.py classify --image image.jpg --command qnn-runner --input "{input}"
```

Arguments after `--command` belong to the external command, so place `--command` last.

Device Q&A and camera observation use an OpenAI-compatible local chat-completions endpoint. Override `--endpoint` and `--model` for the runtime available on the target.

On the validated IQ8 AURA image, run the installed YOLOv8 W8A8 DLC on QNN HTP
for a captured frame:

```bash
python3 src/qli_ai_apps.py object-detect \
  --image /tmp/capture.jpg \
  --command python3 /opt/aura-vision/aura_npu_detect.py
```

Summarize the detector output with the available local OpenAI-compatible model:

```bash
python3 src/qli_ai_apps.py camera-agent \
  --image /tmp/capture.jpg \
  --endpoint http://127.0.0.1:8080/v1/chat/completions \
  --model /opt/aura-llm/qwen2.5-3b-instruct-q4_k_m.gguf \
  --command python3 /opt/aura-vision/aura_npu_detect.py
```

The installed model names and paths are image-specific; query `/v1/models` and
verify the AURA vision bundle before reusing these commands on another device.

Model download URLs and tokens should come from approved tooling or environment variables. Do not add AI Hub credentials to files.

## Device Agents

- `src/qli_audio_event_agent.py` provides the RMS-based Audio Event Agent.
- `src/qli_device_health_agent.py` produces a structured device-health report.
- `src/qli_a2a_agent.py` exposes device-health Q&A through A2A JSON-RPC endpoints.

Create a device-health report:

```powershell
& $python .\qli_dogfooding\src\qli_device_health_agent.py --output .\qli_dogfooding\evidence\device_health.json
```

Run the RMS-based audio event agent:

```powershell
& $python .\qli_dogfooding\src\qli_audio_event_agent.py --device default --duration 2 --threshold 150
```

Start the on-device A2A device-health agent:

```powershell
& $python .\qli_dogfooding\src\qli_a2a_agent.py `
  --host 0.0.0.0 `
  --port 8765 `
  --camera-device /dev/video0 `
  --qnn-root /opt/qnn `
  --genie-endpoint http://127.0.0.1:18081/v1/chat/completions `
  --model qwen3-4b-genie
```

The A2A endpoints are:

- `GET /health`
- `GET /.well-known/agent-card.json`
- `POST /rpc`

## Debugging and Deployment

`src/qli_debug_deploy_apps.py` covers remote debugging, breakpoints, crash investigation, log diagnostics, deployment, and clean build verification.

Inspect system logs:

```powershell
& $python .\qli_dogfooding\src\qli_debug_deploy_apps.py logs --priority warning --lines 200
```

Run the local clean-build verification workflow:

```powershell
& $python .\qli_dogfooding\src\qli_debug_deploy_apps.py clean-build
```

Remote deployment defaults to plan-only. Review the generated `scp` and `ssh` commands before adding `--execute`:

```powershell
& $python .\qli_dogfooding\src\qli_debug_deploy_apps.py deploy-hello `
  --host DEVICE_IP `
  --source .\hello.py `
  --destination /tmp/hello.py `
  --remote-command python3 /tmp/hello.py
```

## Evidence, Workbook, and Report Tooling

The active pipeline is device-neutral. It collects evidence, builds a normalized
51-workflow summary, updates the established Excel template, and generates a
Word report. IQ8-only historical scripts are retained under
`scripts/legacy_iq8/` and must not be used for new devices.

Collect baseline device evidence:

```powershell
$env:QLI_SSH_PASSWORD = "Stored in password manager"
& $python .\qli_dogfooding\scripts\qli_device_validation.py `
  --host DEVICE_IP `
  --device-label DEVICE_NAME `
  --hostkey "SSH_HOST_KEY" `
  --output .\qli_dogfooding\evidence\device_validation.json
Remove-Item Env:QLI_SSH_PASSWORD
```

Record verified deep-workflow outcomes in an assessment-results JSON file. The
schema and example are in
[`assessment-results-schema.md`](skills/developer-readiness-assessment/references/assessment-results-schema.md).
The builder infers only identity, installed version, connectivity, SSH, transfer,
and its baseline deployment probe; all other activities remain `Not Tested`
unless explicitly supplied.

Build the normalized summary:

```powershell
& $python .\qli_dogfooding\scripts\build_qli_device_summary.py `
  --device DEVICE_NAME `
  --hostname DEVICE_HOSTNAME `
  --ip-address DEVICE_IP `
  --baseline .\qli_dogfooding\evidence\device_validation.json `
  --deep-evidence .\qli_dogfooding\evidence\device_deep `
  --results .\qli_dogfooding\evidence\assessment_results.json `
  --output .\qli_dogfooding\evidence\device_summary.json
```

Create the device workbook from the established template:

```powershell
& $python .\qli_dogfooding\scripts\create_qli_device_workbook.py `
  --summary .\qli_dogfooding\evidence\device_summary.json `
  --template C:\path\to\QLI_Dogfooding_Template.xlsx `
  --output C:\path\to\DEVICE_QLI_2.0_Dogfooding_Hub.xlsx
```

New workbook templates should use `{{DEVICE}}`, `{{HOSTNAME}}`,
`{{IP_ADDRESS}}`, and `{{OWNER}}`. For an approved legacy template, pass exact
replacements without modifying the generic builder:

```powershell
& $python .\qli_dogfooding\scripts\create_qli_device_workbook.py `
  --summary .\qli_dogfooding\evidence\device_summary.json `
  --template C:\path\to\Legacy_Template.xlsx `
  --replace "OLD_DEVICE_LABEL=DEVICE_NAME" `
  --replace "old-hostname=DEVICE_HOSTNAME" `
  --output C:\path\to\DEVICE_QLI_2.0_Dogfooding_Hub.xlsx
```

Create the Word report and optionally include screenshots:

```powershell
.\qli_dogfooding\scripts\create_qli_device_report.ps1 `
  -SummaryPath .\qli_dogfooding\evidence\device_summary.json `
  -OutputPath C:\path\to\QLI_2.0_Dogfooding_DEVICE.docx `
  -ScreenshotDirectory C:\path\to\device\screenshots
```

Working spreadsheets and exported JSON resources are stored under `resources/`.

Audit reference documents and a workbook:

```powershell
& $python .\qli_dogfooding\scripts\audit_sources.py `
  --reference-dir .\qli_dogfooding\reference `
  --workbook .\qli_dogfooding\resources\QLI_Dogfooding_Hub_working.xlsx `
  --output-dir .\qli_dogfooding\audit
```

Format a workbook using Excel COM automation:

```powershell
.\qli_dogfooding\scripts\format_workbook.ps1 `
  -InputPath .\qli_dogfooding\resources\QLI_Dogfooding_Hub_working.xlsx `
  -OutputPath .\qli_dogfooding\resources\QLI_Dogfooding_Hub_formatted.xlsx
```

## Evidence and Historical Artifacts

- Store durable validation output in `evidence/`.
- Store reusable source documents and generated workbooks in `resources/`.
- Treat `scripts/legacy_iq8/` as historical reproduction tooling, not the active multi-device pipeline.
- Avoid committing generated models, large datasets, credentials, or unnecessary temporary output.

## Validation

Run the repeatable catalog and documentation checks:

```powershell
py -3 .\skills\developer-readiness-assessment\scripts\inspect_toolkit.py `
  --project-root .
py -3 .\scripts\validate_markdown_links.py --project-root .
```

The Academy pull-request workflow runs these checks when `qli_dogfooding/` or
its CI workflow changes.

Check all application entry points:

```powershell
Get-ChildItem .\qli_dogfooding\src\*.py | ForEach-Object {
  & $python -B $_.FullName --help
  & $python -B $_.FullName --list-workflows
}
```

The eight Python application files collectively advertise 52 module entries
covering exactly 51 unique workflows; `Configure Static IP` appears in both the
lifecycle planner and the dedicated network implementation.
