# Assessment Playbook

## Prepare the Host

Resolve the toolkit root relative to this skill and validate it:

```powershell
$skill = "<toolkit-root>\skills\developer-readiness-assessment"
$toolkit = (Resolve-Path "$skill\..\..").Path
py -3 "$skill\scripts\inspect_toolkit.py" --project-root $toolkit
py -3 -m pip install -r "$toolkit\requirements.txt"
```

Confirm Python 3 and SSH or PuTTY. Excel and Word are needed only for the
corresponding deliverables. Do not install dependencies without approval.

## Create Evidence Storage

```powershell
$device = "DEVICE_LABEL"
$date = Get-Date -Format "yyyy-MM-dd"
$evidence = Join-Path $toolkit "evidence\$device-$date"
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
```

Do not commit credentials, models, media, workbooks, reports, or temporary
device output unless repository policy explicitly allows them.

## Collect Baseline Evidence

Use a trusted SSH fingerprint. Read passwords interactively or from an approved
environment variable.

```powershell
py -3 "$toolkit\scripts\qli_device_validation.py" `
  --host DEVICE_IP `
  --user root `
  --device-label DEVICE_LABEL `
  --hostkey "TRUSTED_FINGERPRINT" `
  --output "$evidence\baseline.json"
```

## Discover Device-Specific Resources

Run read-only discovery before deep tests:

```bash
hostname
cat /etc/os-release
cat /etc/buildinfo 2>/dev/null || true
ip -brief address
ip route
nmcli connection show --active 2>/dev/null || true
aplay -l 2>/dev/null || true
arecord -l 2>/dev/null || true
v4l2-ctl --list-devices 2>/dev/null || true
find /opt /usr -maxdepth 4 -type f \( -name 'qnn-net-run' -o -iname '*.dlc' -o -iname '*genie*' \) 2>/dev/null
```

Probe local model-list APIs and record the actual model ID. Do not assume names,
ports, camera nodes, audio devices, interfaces, or tensor paths from another
device.

## Execute by Risk Tier

### Tier 1: Read-Only or Temporary

Run identity, version, connectivity, storage, metadata, logs, health,
classification, scoring, and endpoint discovery first.

### Tier 2: Reversible Changes

Audio playback/recording, camera capture, file transfer, temporary deployment,
breakpoints, and loopback services are allowed after paths and cleanup are
confirmed.

### Tier 3: Connectivity Risk

Wi-Fi switching and static-IP activation require an approved network, reserved
address, alternate access path, profile backup, and rollback command. Run
`qli_network_apps.py configure-static` without `--execute` first. Add
`--activate` only during an approved maintenance window.

### Tier 4: Destructive or Fault Injection

Flashing, forced recovery, rollback, and controlled crash tests require explicit
approval. Use a disposable process for crash investigation, never a critical
service.

## Validate Camera Workflows

1. Inspect metadata and supported formats.
2. Capture one supported frame.
3. Require return code zero and nonzero `output_bytes`.
4. Verify file signature and hash.
5. Run timestamped, burst, motion, and stored-photo workflows.
6. Run object detection on a fresh frame.
7. Run camera observation and separate detector facts from model reasoning.

## Validate Audio Workflows

1. Discover playback/capture devices.
2. Generate a tone without playback.
3. Play the tone and record a sample.
4. Validate WAV metadata, bytes, and RMS.
5. Run loopback and audio-event classification.
6. Record whether a human listening check occurred.

## Validate AI Workflows

1. Record model artifact, runtime/backend, preprocessing, tensors, and labels.
2. Run real inference and retain command, return code, and output.
3. Parse predictions and confidence metrics.
4. Compare models under identical input/runtime conditions.
5. Separate accelerator time from end-to-end time.
6. Verify the endpoint model list before Q&A or camera-agent calls.

## Validate Debug and Deployment

Use a temporary working directory. Capture debugger connection proof,
breakpoint/backtrace evidence, deployment output before and after update, and
cleanup confirmation. Use `Not Applicable` for second-device deployment when
only one device is supplied.

## Build Deliverables

```powershell
py -3 "$toolkit\scripts\build_qli_device_summary.py" `
  --device DEVICE_LABEL `
  --hostname DEVICE_HOSTNAME `
  --ip-address DEVICE_IP `
  --owner OWNER `
  --baseline "$evidence\baseline.json" `
  --deep-evidence "$evidence\deep" `
  --results "$evidence\assessment_results.json" `
  --output "$evidence\summary.json"

py -3 "$toolkit\scripts\create_qli_device_workbook.py" `
  --summary "$evidence\summary.json" `
  --template "APPROVED_TEMPLATE.xlsx" `
  --output "$evidence\DEVICE_Dogfooding_Hub.xlsx"

& "$toolkit\scripts\create_qli_device_report.ps1" `
  -SummaryPath "$evidence\summary.json" `
  -OutputPath "$evidence\DEVICE_Developer_Readiness.docx" `
  -ScreenshotDirectory "$evidence\screenshots"
```

Create `assessment_results.json` from verified evidence using the
[assessment-results schema](assessment-results-schema.md), then review
`summary.json` before building the documents. Workflows not proven by the
baseline or results file remain
`Not Tested` by design.

## Verify Deliverables

- Status totals agree across summary, workbook, and report.
- Every completed app appears once in `Completed Apps`.
- Persona findings agree with app statuses.
- No prior device name, IP, camera, endpoint, or model remains.
- Partial/blocked items include evidence and next actions.
- Backups exist before overwriting user deliverables.
