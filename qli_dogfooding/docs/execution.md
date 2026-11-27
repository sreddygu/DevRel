# QLI Execution Proof

This presentation-safe summary draws on QLI Dogfooding execution artifacts.
The IQ9 evidence was captured on **August 12, 2026**. It proves the recorded
execution and evidence model; it is not a claim about the current state of any
device on **October 9, 2026**.

## Evidence at a Glance

| Capability | Recorded result | Supporting artifact |
| --- | --- | --- |
| QNN model execution | Graph execution completed with `returncode=0` | `qnn_run.txt` (local evidence, not committed) |
| QNN profiling | MobileNetV2 recorded 277.3925 inferences/sec with four HVX threads | `qnn_profile.txt` (local evidence, not committed) |
| Audio playback | WAV playback completed with `returncode=0` | `audio_loopback.txt` (local evidence, not committed) |
| Device-health inspection | Health agent recorded capabilities and a warning state | `device_health_stdout.txt` (local evidence, not committed) |
| A2A agent validation | Health service was ready; unavailable Genie endpoint was retained as an error | `a2a_validation.json` (local evidence, not committed) |

## QNN Execution and Performance

The raw QNN execution record shows graph execution completed with a successful
exit status:

```text
Finished Executing Graphs
returncode=0
```

Source: `qnn_run.txt` (local evidence, not committed).

The corresponding profile identifies `mobilenetv2` and records these results:

| Measurement | Recorded value |
| --- | --- |
| NetRun throughput, including I/O and miscellaneous time | 277.3925 inferences/sec |
| NetRun total inference time | 2354 microseconds |
| QNN accelerator execution time | 1995 microseconds |
| HVX threads used | 4 |

Source: `qnn_profile.txt` (local evidence, not committed).

This demonstrates successful AI execution plus measurable performance, rather
than a generated plan or a claimed capability.

## Device and Media Execution

The audio workflow captured a successful `aplay` execution with `returncode=0`
and playback of a 48 kHz mono WAV file. Source:
`audio_loopback.txt` (local evidence, not committed).

The device-health agent captured a `WARN` state rather than reporting an
unqualified success. The same artifact recorded 10 audio devices, 32 camera
devices, and 85 QNN assets. Source:
`device_health_stdout.txt` (local evidence, not committed).

This shows that the implementation retains diagnostic findings and supports a
recovery decision instead of concealing a non-ideal device condition.

## Agent Execution and Recorded Limitation

The A2A validation artifact reports the device-health service as `ready`. It
also preserves a failed RPC call caused by an unavailable Genie endpoint.
Source: `a2a_validation.json` (local evidence, not committed).

This demonstrates the intended Synapse behavior: validated work and known
limitations are retained as evidence. A failed dependency is not turned into a
false success.

## Current Catalog Verification

The following command was run locally on **October 9, 2026** against this
project:

```powershell
py -3 .\skills\developer-readiness-assessment\scripts\inspect_toolkit.py `
  --project-root .
```

It returned:

```text
Module entries: 52
Unique workflows: 51/51
Synapse skills: 10/10
Toolkit validation: PASS
```

The execution inventory is documented in [`workflow.md`](workflow.md). The
full IQ9 result summary is available in
`iq9_summary_2026-08-12.json` (local evidence, not committed).

## Presentation Sequence

1. Show successful QNN execution and measured throughput.
2. Show the device-health warning and A2A endpoint limitation.
3. Connect those outcomes to the Synapse route: evidence is collected, failures
   remain visible, and the next action is selected safely.
4. Use the current catalog verification to show that the implementation exposes
   51 unique workflows through 10 structured Synapse skills.

No device address, credential, token, private endpoint, or personal data is
included in this summary.
