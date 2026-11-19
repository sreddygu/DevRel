# RoboAgent Pi Implementation Status

Last updated: October 6, 2026

## Goal

Run the local Gemma 4 QNN model through Pi, keep the host warm when needed,
support safe workspace tools, and make it easy to test another compiled model.

## Completed

- Fixed the Pi/QNN response lifecycle so terminal responses close their named
  pipe connection. Prompted runs no longer leave `node.exe` or
  `qnn_llm_host.exe` running.
- Added a workspace-scoped read-only tool loop with validated `read_file`,
  `list_directory`, `search_files`, Git status, and Git diff calls.
- Added source-file support to `search_files(query, path?)` and excluded
  generated `logs` output from search results.
- Added model profiles in `roboagent-model-profiles.ps1`. The `gemma4` profile
  centralizes model artifacts, decoder version, context limit, Pi model ID,
  pipe name, and default sequence length.
- Added `-EnableMutations` and `-KeepHostRunning` to the managed launcher.
- Bound every QNN request to the estimated cumulative conversation position plus
  the profile response budget. This prevents Pi auto-compaction from generating
  until the runner's global sequence limit and exceeding Pi's 120-second timeout.
- Decoupled Pi's session window from the QNN host window. Pi retains its local
  session history without immediately auto-compacting, while the adapter remains
  responsible for the host's 3,800-token managed cumulative limit. The adapter
  reinforces English-only output on every request, suppresses detected
  foreign-language drift, and answers ordinary general-knowledge questions
  directly before considering workspace tools.
- On October 6, 2026, multi-turn chat revealed that the adapter repeated and
  counted its large instruction block on every turn even though the host only
  received it once. Later turns now retain only a compact required instruction
  alongside the new user prompt or tool result; full shared instructions are
  sent again after host restart or recovery.
- Informal general questions are interpreted as requests for a useful general
  answer unless they explicitly ask for current, live, or local conditions.
- Propagated the QNN host's `prompt_tokens` and `generated_tokens` metrics into
  Pi's standard assistant-message usage metadata. Completed answers now visibly
  report the input, output, and total token counts for the individual request.
- Hardened `restart-roboagent-host.ps1` against NPU host teardown races. It now waits
  for the previous `qnn_llm_host.exe` process to exit, retries startup once, and
  reports the recent host log if recovery still fails.
- Aligned the adapter's context guard with the managed runner's actual
  `--seq_len 3800` ceiling. The model has 3,872 usable compiled tokens, but the
  additional 72-token headroom prevents a host-side sequence-length assertion.
- Reserved the profile's 512-token response budget before each QNN request. When
  the next prompt plus that reserve would exceed the 3,800-token runner limit,
  the adapter restarts the host and replays only recent bounded conversation
  text; older turns are deliberately removed.
- Replaced the detached PowerShell recovery launch with an observable child
  process. The adapter waits for an explicit host-ready marker, verifies the
  named pipe, detects process start/exit failures, and reports diagnostic log
  tails instead of leaving Pi on `Working...` without context.
- Hardened the managed launcher against stale host logs by probing the live
  `\\.\pipe\gemma4` endpoint before it starts Pi.
- Kept `write_file`, `apply_patch`, and `run_command` individually gated by
  Pi approval prompts.
- Updated the evaluation harness so every task requests source evidence through
  read-only tools.

## Validated

- `tools\pi\test-roboagent-protocol.ps1` prints `PROTOCOL_TEST_PASSED`.
- `tools\pi\evaluate-roboagent.ps1` completes all four tasks with exit code `0`,
  valid tool requests, grounded final answers, and no repeated or malformed
  calls.
- The source-search task reports `cpp/qnn_llm_host.cpp:321` for `Listening on`.
- A warm host served two separate Pi clients without loading the model again,
  then shut down cleanly through the named-pipe `shutdown` request.
- PowerShell syntax checks pass for the profile module and launcher.
- On October 5, 2026, a `who are you` interactive Pi turn reproduced the former
  compaction failure: the host generated 2,703 tokens until `seq_len=3800`,
  while Pi timed out at 120 seconds. The fixed path capped the compaction result
  at 287 generated tokens, returned in 39 seconds, and left no host process.
- On October 6, 2026, a fresh QNN/Pi prompt completed successfully and displayed
  `Tokens used: input 806 | output 28 | total 834`.
- On October 6, 2026, the repaired context-recovery path loaded the host, opened
  `\\.\pipe\gemma4`, and a following CPU request completed with 806 input and
  28 output tokens.
- On October 6, 2026, a clean managed startup returned an NPU answer with 807
  input tokens, 32 output tokens, and `2,961` remaining QNN context tokens.
- On October 6, 2026, `tools\pi\test-english-output.ps1` passed. It sent a
  mocked Chinese/Portuguese response through the public named-pipe/Pi seam and
  verified that the adapter suppressed the non-English text.

## Run Commands

### Text-only chat

```powershell
.\tools\pi\start-roboagent-pi.ps1
```

### Read-only workspace tools

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ReadOnlyTools
```

### Approved mutation tools

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ReadOnlyTools -EnableMutations
```

The model can request `write_file`, `apply_patch`, or `run_command`, but Pi
must show and receive approval for every individual action.

### Keep the QNN model warm

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ReadOnlyTools -KeepHostRunning
```

Run later clients with the same model profile and pipe name. Shut down the warm
host when finished; a managed launcher without `-KeepHostRunning` does this
automatically.

### Select a model profile

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ModelProfile gemma4
```

To test another compiled model, add its profile to
`tools\pi\roboagent-model-profiles.ps1`; do not hard-code its artifact paths in the
launcher or provider adapter.

## Current Tool Shim

The QNN runner does not provide native structured tool calls. The adapter asks
the model to emit one prompt-format payload:

```text
<tool_call>{"name":"read_file","arguments":{"path":"README.md"}}</tool_call>
```

`roboagent-gemma4.ts` validates this payload, converts it to a Pi `ToolCall`,
executes one approved/read-only tool, and requires a grounded final answer. The
current loop intentionally allows only one tool call per exchange.

## Remaining Work

- Run `tools\pi\test-approved-mutations.ps1` interactively and approve its
  three displayed requests. Pi deliberately returns `false` for confirmations
  in non-interactive `-Prompt` mode, so this validation requires a person at
  the Pi approval dialogs. The script uses a disposable
  `.roboagent-runtime\mutation-fixture.txt` file, not production files.
- Locate the local `tiny-tool-calling` repository or provide its path. Compare
  its deterministic output grammar with the current `<tool_call>` shim before
  adding a second parser or OpenAI-compatible response adapter.
- Run a fresh interactive multi-turn session past approximately `3,200 / 3,800`
  QNN context tokens and confirm that one additional prompt completes after the
  automatic recovery/replay path. The recovery script and startup probes are
  validated independently; this full live-session scenario remains the final
  operational check.
- Only the `gemma4` compiled-model profile is currently available locally. When
  another compiled model is added under `models`, add its profile first and run
  the deterministic protocol test plus the four-task QNN smoke evaluation.
- Keep prompts targeted because the current managed profile has a practical
  3,800-token runtime context budget. The compiled model's theoretical usable
  capacity is 3,872 tokens, but the 72-token reserve is intentional.

## Key Files

- `tools\pi\roboagent-model-profiles.ps1` — compiled-model profile module.
- `tools\pi\start-roboagent-pi.ps1` — managed host launcher and tool-mode gate.
- `tools\pi\roboagent-gemma4.ts` — named-pipe provider and tool-call shim.
- `tools\pi\roboagent-tools.ts` — workspace tools and per-action approvals.
- `tools\pi\evaluate-roboagent.ps1` — four-task QNN smoke evaluation.
- `tools\pi\SCOPE_STATUS.md` — milestone-level scope status.
