---
name: developer-readiness-assessment
description: Assess the developer readiness of IQ8, IQ9, and other Linux-based edge devices by orchestrating lifecycle, networking, audio, camera, storage, AI, agent, debugging, deployment, evidence, workbook, and report workflows. Use for device dogfooding, new-device or new-image validation, readiness reruns, device comparisons, failure triage, and synchronized readiness deliverables.
version: 1.1.0
---

# Developer Readiness Assessment

Run a safe, evidence-driven readiness assessment with the `qli_dogfooding`
toolkit. This procedure is framework-neutral: any agent or model may execute it
when given filesystem and command-execution tools.

Resolve the toolkit root as two directories above this skill directory. Do not
assume the process working directory.

## Synapse Composition

This is a **journey skill** invoked by the `qli-readiness-agent` agent skill.
Inject `qli-linux-domain` context before selecting device work. Select domain
skills when conditional judgment is needed; call MCP tools directly for
deterministic single steps:

Domain skills:
- `host-environment-validation`
- `device-identity-discovery`
- `baseline-evidence-collection`
- `ai-model-execution`
- `diagnostic-log-collection`

MCP tools (call directly — no skill wrapper):
- `device-connectivity-validation`
- `ai-inference-benchmark`
- `readiness-report-generation`

An external agent router may select this journey when a request requires a
multi-step plan, approval management, or resume behavior. Do not duplicate a
domain skill or MCP tool procedure in this journey when it can be invoked directly.

## Required Reading

1. Read `skill.yaml` for machine-readable selection metadata.
2. Run `scripts/inspect_toolkit.py --project-root <toolkit-root>`.
3. Read the [assessment playbook](references/assessment-playbook.md) before accessing a device.
4. Read the [workflow map](references/workflow-map.md) when selecting activities.
5. Read [status and evidence rules](references/status-and-evidence.md) before assigning statuses.
6. Read the [assessment-results schema](references/assessment-results-schema.md) before generating deliverables.

## Execution Sequence

### 1. Establish Scope

Collect the device label, host/IP, SSH user, expected software release, host OS,
available access paths, peripherals, AI runtimes, and requested deliverables.
Decide whether the request is a baseline check, full assessment, focused rerun,
cross-device comparison, or workbook/report generation.

Keep passwords, private keys, tokens, and private endpoints out of files and
command history. Use key-based access, environment variables, interactive
prompts, or an approved password manager.

### 2. Apply Safety Gates

Default to non-destructive inspection and dry-run behavior.

- Do not flash, recover, reset, switch Wi-Fi, activate static IP, force crashes,
  or overwrite device data without explicit approval.
- Require a rollback plan and alternate access path before connectivity changes.
- Preserve healthy devices; do not manufacture failures only to complete a row.
- Use temporary directories and clean up temporary processes and files.
- Treat tool presence as discovery, not proof of successful execution.

### 3. Collect Baseline Evidence

Run `<toolkit-root>/scripts/qli_device_validation.py` for non-destructive SSH
evidence. Store results in a device/date-specific directory under `evidence/`.

Verify identity, OS/build, uptime, storage, interfaces/routes, active network
profiles, SSH/SCP, audio devices, camera nodes, failed services, QNN/QAIRT
assets, and local model endpoints.

### 4. Execute Deep Workflows

Use the modules under `<toolkit-root>/src/`:

- `qli_device_lifecycle_apps.py`: setup, flashing, recovery, Wi-Fi, SSH, transfer.
- `qli_network_apps.py`: static-IP inspect, plan, verify, and DHCP rollback.
- `qli_media_storage_apps.py`: audio, camera, logs, configuration, storage.
- `qli_ai_apps.py`: models, inference, scoring, detection, Q&A, observation.
- `qli_audio_event_agent.py`, `qli_device_health_agent.py`, `qli_a2a_agent.py`: agents.
- `qli_debug_deploy_apps.py`: debugging and deployment iteration.

Run `--help` and `--list-workflows` before constructing commands. Discover real
interfaces, camera/audio devices, model paths, tensors, labels, and endpoint
model IDs instead of copying values from a different device.

### 5. Validate Results

Require objective evidence appropriate to the domain:

- Network: persistent profile plus live address, route, DNS, and reachability.
- Audio: nonzero WAV, format metadata, RMS, and listening status.
- Camera: zero return code, nonzero output, image signature, metadata, unique files.
- AI: actual runner, model/backend identity, return code, parsed result, timing.
- Agent: tool observation plus model response when reasoning is required.
- Debug/deploy: process proof, breakpoint/backtrace or output change, and cleanup.

Run AI-camera workflows on a fresh captured frame. Do not call a text model
multimodal when it only summarizes detector output.

### 6. Assign Statuses

Use [status and evidence rules](references/status-and-evidence.md). Distinguish
product blockers from test-environment limitations. Normalize new artifacts to `Completed`,
`User Completed`, `Partial`, `Blocked`, `Not Tested`, or `Not Applicable`.
Record verified deep-workflow outcomes in an assessment-results JSON file. Do
not rely on the summary builder to infer multimedia, AI, debugging, recovery,
network-change, or agent results from file presence.

### 7. Generate Deliverables

Use the device-neutral pipeline:

1. `scripts/build_qli_device_summary.py`
2. `scripts/create_qli_device_workbook.py`
3. `scripts/create_qli_device_report.ps1`
4. `scripts/format_workbook.ps1` when Excel formatting is required

Review the normalized summary before generating documents. Keep `App to Build`,
`Persona Tracker`, `Completed Apps`, status totals, findings, and report prose
synchronized. Every completed activity must have one matching completed record.

### 8. Final Quality Check

- Reopen XLSX/DOCX outputs and verify sheet names, row counts, totals, and findings.
- Search for stale device names, IPs, camera blockers, endpoints, and models.
- Confirm no secrets, large models, media, or temporary evidence are staged for Git.
- Summarize status totals and any deferred destructive tests.
- State the approval and recovery conditions needed for deferred operations.

## Resources

- [Workflow map](references/workflow-map.md): all 51 activities and their owning modules.
- [Assessment playbook](references/assessment-playbook.md): commands, risk tiers, and deliverable pipeline.
- [Status and evidence rules](references/status-and-evidence.md): statuses, minimum evidence, consistency checks.
- [Assessment-results schema](references/assessment-results-schema.md): validated result overrides and template placeholders.
- [Framework integration](references/framework-integration.md): framework/model-neutral loading contract.
- `scripts/inspect_toolkit.py`: validates required files and workflow discovery.
