# Status and Evidence Rules

## Status Definitions

### Completed

Assign only when the requested workflow ran end-to-end and objective evidence
confirms the expected result. Tool installation or file presence alone is not
completion.

### User Completed

Use when the participant completed the activity before the assessment and the
resulting state is confirmed, but the exact workflow was not replayed. State
what was verified and what remains based on participant evidence.

### Partial

Use when meaningful stages passed but a required final stage was intentionally
deferred or remains unverified. Example: static-IP planning and profile checks
passed, but live activation was deferred over the only SSH path.

### Blocked

Use after an attempted workflow reaches a repeatable external blocker, such as
missing hardware, unavailable runtime, unsupported driver, or failed
prerequisite. Include command, return code, error, and an unblock action.

### Not Tested

Use when the workflow was not attempted. Explain whether it was deferred for
safety, time, missing approval, or unavailable test conditions.

### Not Applicable

Use when the workflow does not apply to the supplied setup, such as second-
device deployment when only one device exists. Prefer this spelling over `NA`.

## Minimum Evidence by Domain

| Domain | Minimum evidence |
|---|---|
| Identity/version | Hostname, architecture, OS release, build provenance |
| Connectivity | Interface, address/prefix, route, DNS, reachability, SSH proof |
| Static IP | Profile method/address/gateway/DNS, conflict probe, live verification or reason deferred |
| Transfer/storage | Source/destination paths, byte sizes, hashes, capacity |
| Audio | Device, format, sample rate/channels, duration, bytes, RMS, listening status |
| Camera | Device node, driver, format/resolution, return code, bytes, signature, hash |
| AI | Model, backend, command, input, return code, parsed result, timing |
| Agent | Tool observation, model/endpoint if used, final response, uncertainty |
| Debug | Debugger connection, breakpoint/backtrace/crash proof, isolated process |
| Deployment | Source revision, destination, output before/after update, cleanup |
| A2A | Listen address, Agent Card, JSON-RPC request/response, process proof |

## Evidence Storage

Use a device/date-specific hierarchy:

```text
evidence/<device>-YYYY-MM-DD/
  baseline.json
  summary.json
  deep/
    network/
    audio/
    camera/
    ai/
    agents/
    debug/
    deploy/
  screenshots/
```

Prefer JSON and text for durable evidence. Keep large media and model artifacts
outside Git. Record UTC timestamps when possible and preserve exact commands
after removing secrets.

## Credential and Privacy Rules

- Never persist passwords, private keys, tokens, cookies, or access secrets.
- Replace discovered secrets with `Stored in password manager`.
- Use trusted SSH fingerprints; do not silently disable host-key checking.
- Avoid recording personal SSIDs, internal URLs, or participant data unless required.
- Redact secrets before adding output to a workbook or report.

## Workbook and Report Consistency

Before delivery:

1. Count statuses in `App to Build`.
2. Count statuses in `Persona Tracker`.
3. Ensure every `Completed`/`User Completed` app exists once in `Completed Apps`.
4. Ensure non-completed apps do not appear in `Completed Apps`.
5. Reconcile findings with the latest reruns.
6. Regenerate the Word report after every workbook status change.
7. Search for stale blocker language and prior device identifiers.
