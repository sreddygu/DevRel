# Pi + RoboAgent Gemma 4

This extension registers the local RoboAgent QNN host as a Pi provider. It uses the
existing Windows named-pipe protocol and does not modify ExecuTorch or the model
runner.

Generated host, recovery, protocol, evaluation, and test output is stored under
`logs\`. See `logs\README.md` for the layout. `.roboagent-runtime\` contains
only short-lived control files and the disposable mutation fixture.

See `IMPLEMENTATION_STATUS.md` for the current implementation handoff,
validation results, run commands, and remaining follow-up work. See
`TROUBLESHOOTING.md` for the issues encountered, their fixes, and manual
verification steps.

## Run

The launcher starts and shuts down the host automatically. The stable default
is text-only:

```powershell
.\tools\pi\start-roboagent-pi.ps1
```

Opt into the current read-only tool protocol with:

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ReadOnlyTools
```

Enable mutation tools only when you intend to approve individual writes, patches,
or commands in Pi:

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ReadOnlyTools -EnableMutations
```

`write_file`, `apply_patch`, and `run_command` each display an approval prompt.
The launcher rejects mutation mode unless read-only tools are also enabled.
Mutation mode is enabled and approval-gated, but it has not yet been validated
against a real write, patch, or command request.

Validate all three mutation tools against a disposable runtime fixture with:

```powershell
.\tools\pi\test-approved-mutations.ps1
```

This starts interactive Pi. Approve only the three displayed requests, then
type `exit`; the script verifies the fixture result.

## Model Profiles And Warm Hosts

`tools\pi\roboagent-model-profiles.ps1` is the model-profile module. It contains
the model artifact paths, decoder version, context limit, Pi model ID, and
default pipe name for each compiled model. It also sets the per-turn response
budget used to keep the runner's cumulative sequence length bounded. Add a
profile there, then select it
without changing the provider adapter:

```powershell
.\tools\pi\start-roboagent-pi.ps1 -ModelProfile gemma4
```

The Pi session window is intentionally larger than the QNN host context window.
The compiled model has a theoretical 3,872-token usable capacity, while the
managed profile intentionally uses a 3,800-token ceiling. The 72-token reserve
prevents host-side sequence-length assertions. The adapter manages that
3,800-token cumulative budget, so Pi does not run an unnecessary internal
compaction turn after normal short exchanges.

The provider answers ordinary general-knowledge questions directly in English.
It uses workspace tools only when a question needs project-specific evidence.
A compact English-only instruction is included with every request. If the model
still returns non-English scripts or known language-drift phrases, the adapter
suppresses the response rather than displaying it. Full shared instructions are
sent when a QNN host starts or recovers; later turns retain only the compact
required instruction plus the new prompt or tool result. Informal questions
receive a useful general answer unless they explicitly ask for current, live,
or local conditions.

Every completed response also displays the actual QNN host token counts in this
format:

```text
Tokens used: input 806 | output 28 | total 834
```

The counts include the prompt and generated tokens for that individual QNN
request. Pi also receives the same values through its standard usage metadata.
Each completed response also displays the managed QNN context position, for
example `QNN context: used 834 / 3800 | available 2966`.

When the next request would exceed the managed context budget, the adapter
restarts the host and replays bounded recent context. This takes several
seconds. If recovery fails, Pi reports the recovery process failure directly;
inspect `logs\host-recovery-gemma4.log` and
`logs\host.stderr.log` before restarting manually.

Use `-KeepHostRunning` to leave a host loaded after Pi exits. A later Pi client
can reuse that warm host by selecting the same model profile and pipe name.
Send the host a normal shutdown request when the warm session is no longer
needed; a managed launcher without `-KeepHostRunning` does this automatically.

The read-only tools are workspace-scoped and pass the current deterministic
smoke suite. The adapter limits each exchange to one validated tool call, then
requires a grounded final answer. Keep text-only mode available as the fallback
when testing a new compiled model or prompt format.

For a manually managed host, start `qnn_llm_host.exe` using the commands in the
project `README.md`. Wait for `Listening on \\.\pipe\gemma4`.

The direct `pi -e ...` commands below do **not** start the QNN host. Use the
managed `start-roboagent-pi.ps1` command for normal VS Code use, or keep the manual
host terminal running before starting Pi directly.

In another terminal, from the RoboAgent directory, run:

```powershell
pi -e .\tools\pi\roboagent-gemma4.ts --provider roboagent --model gemma4 --no-tools -p "Say hello in one short sentence."
```

For interactive mode:

```powershell
pi -e .\tools\pi\roboagent-gemma4.ts --provider roboagent --model gemma4 --no-tools
```

Set `ROBOAGENT_PIPE_NAME` if the host uses a different `--pipe_name`.

Each adapter request carries a `roboagent-pi/1` envelope with `session_id`,
`turn_id`, `phase`, and `tool_turn_limit`. The current C++ host ignores these
extra JSON fields, so this protocol can be introduced without rebuilding the
runner. See `SCOPE_STATUS.md` for milestone progress.

Read-only tools are registered by default: `read_file`, `list_directory`,
`search_files`, `get_git_status`, and `get_git_diff`. They are workspace-scoped.

Mutation tools (`write_file`, `apply_patch`, and `run_command`) are available only
when `ROBOAGENT_ENABLE_MUTATIONS=1`, and each asks for interactive approval.

Run the smoke evaluation with:

```powershell
.\tools\pi\evaluate-roboagent.ps1
```

Run the isolated English-only output regression without touching the warm Gemma
host with:

```powershell
.\tools\pi\test-english-output.ps1
```

The test uses a dedicated mock named pipe that deliberately returns Chinese and
Portuguese text. It passes only when the adapter suppresses that unsafe output.
