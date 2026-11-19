# Pi + QNN Issues And Fixes

Last updated: October 6, 2026

This note records the issues found while connecting Pi to the local Gemma 4
model through `qnn_llm_host.exe`, along with the implemented fix and the
recommended verification command.

## Quick Verification

From the RoboAgent project directory in a VS Code PowerShell terminal, run:

```powershell
.\tools\pi\start-roboagent-pi.ps1 -NoTools -NoSession -Prompt "What is a CPU? Answer in one sentence."
```

A successful run returns an English answer followed by a per-request line like:

```text
Tokens used: input 806 | output 28 | total 834
```

The exact numbers vary by prompt.

## Resolved Issues

| Symptom | Root Cause | Fix | Verification |
|---|---|---|---|
| Pi stalled or timed out after an answer. | The adapter left the named-pipe client connected after a terminal response, so later lifecycle handling could wait on a stale connection. | The adapter closes the socket after a final response and clears the shared socket reference. | Run two short Pi prompts in separate sessions; each should finish and exit cleanly. |
| Context recovery failed with `RoboAgent host exited during context recovery`, leaving the next Pi question on `Working...`. | The recovery script force-stopped the QNN host and waited a fixed 300 ms before loading the NPU model again. The QNN resources were occasionally still being released. | The script now waits up to 10 seconds for the old host to exit, retries host startup once, and includes the recent host stderr log if both attempts fail. | Run `.\tools\pi\restart-roboagent-host.ps1 -PipeName gemma4 -SeqLen 3800`, then run the quick verification prompt. |
| Pi remains on `Working...` after using `pi -e .\tools\pi\roboagent-gemma4.ts ...`. | The direct Pi command registers the provider but does not start `qnn_llm_host.exe`; there is no `\\.\pipe\gemma4` host to answer the request. | Use `.\tools\pi\start-roboagent-pi.ps1` for normal operation. Direct Pi use requires a separate terminal with the QNN host already listening. The adapter now reports this condition with an actionable connection error. | Run `.\tools\pi\start-roboagent-pi.ps1 -NoTools -NoSession -Prompt "What is a CPU?"`. |
| The QNN host stopped with `sequence length exceeded` after a few turns. | The model has 3,872 usable compiled tokens, but the managed runner starts with `--seq_len 3800`. The adapter previously guarded against 3,872, leaving a 72-token overrun window. | The model profile, recovery guard, and visible QNN-context display now use the real 3,800-token runner ceiling. | Continue a short Pi chat until it nears the limit; recovery should occur before the host assertion. |
| A new answer had almost no room after `QNN context` approached the limit. | The old recovery condition considered only the incoming prompt, not the configured 512-token response budget. | Before every request, the adapter now resets the QNN host when the current cache, new prompt, and 512-token response reserve would exceed 3,800. It replays only the newest bounded conversation text and explicitly drops older turns. | Continue chatting after `QNN context` exceeds roughly 3,250 tokens; the next request should restart and continue with recent context instead of exhausting the cache. |
| Pi reports that the recovered host did not report readiness, or remains on `Working...` while the context is being reset. | Model reload can take longer than the old fixed 20-second marker wait. In addition, a detached PowerShell restart could fail without updating the readiness state. | Recovery now keeps the restart process attached while Pi waits for the validated ready signal, allows up to 100 seconds, detects process startup/exit failures immediately, and writes `logs\host-recovery-gemma4.log`. The ready marker remains in `.roboagent-runtime` and is created only after both `Listening on` and a named-pipe connection probe succeed. | Let a session approach the QNN limit, then send one more prompt. It should recover and answer. If it fails, copy the immediate recovery-process error and inspect `host-recovery-gemma4.log`. |
| Pi opened even though `\\.\pipe\gemma4` was not usable. | The managed launcher treated an old `Listening on` log entry as proof that a host was ready. | The launcher now opens a short named-pipe probe before it starts Pi, so stale logs cannot produce a no-host interactive session. | Start Pi with `.\tools\pi\start-roboagent-pi.ps1`; it should either open a usable session or report startup failure before Pi appears. |
| The host context was consumed faster than expected. | The large English/general-answer/tool instruction block was counted and sent on every turn, although the warm host retained it from the first turn. | Shared instructions are sent and counted only when a host starts or recovers. Later requests send only the new user prompt or tool result. | Start Pi, ask two short questions, and inspect `logs\pi-protocol.jsonl` with `ROBOAGENT_DEBUG_PROTOCOL=1`. |
| Replies included another language or gave poor answers to common questions. | Earlier versions sent the English policy only as the initial system prompt, so later conversation turns could drift into another language. | The adapter now places a compact English-only instruction in every user and tool-result request. As a safety backstop, it suppresses model output containing non-Latin scripts or common Portuguese phrases rather than displaying it. | Start a fresh Pi session and ask `what is GPU`, `what is NPU`, or a technical comparison; the response should be useful and entirely English. |
| The model tried to use tools for questions that did not require local files. | Tool instructions were available without a clear priority for direct general answers. | The system instructions now say to use workspace tools only for project files, repository state, or other local evidence. | Run text-only Pi and ask `What is a CPU?`; no tool request should appear. |
| Tool calls could be malformed, repeated, or unsafe. | Gemma/QNN does not provide native structured tool calls; tool requests are prompt-format text. | The adapter accepts one `<tool_call>` payload per exchange, validates the JSON schema and tool name, rejects repeated calls, and requires a final grounded answer after a tool result. | Run `.\tools\pi\test-roboagent-protocol.ps1`. It should print `PROTOCOL_TEST_PASSED`. |
| File writes, patches, or commands could be requested without a safe workflow. | Mutation tools need explicit user control in a local coding agent. | Mutation tools require `-ReadOnlyTools -EnableMutations` and Pi asks for interactive approval for every `write_file`, `apply_patch`, and `run_command` action. | Run `.\tools\pi\test-approved-mutations.ps1`, approve only the three displayed fixture requests, then type `exit`. |
| It was not clear how many tokens each request used. | The QNN host returned `prompt_tokens` and `generated_tokens`, but the Pi adapter discarded them and reported zero usage. | The protocol now types those metrics, Pi usage metadata receives them, and final answers display input, output, and total counts. | Run the quick verification command above and confirm the `Tokens used:` line. |
| It was not clear how much real model context remained. | Pi's footer tracks Pi session bookkeeping rather than the QNN runner's smaller context ceiling. | Completed answers now also show `QNN context: used X / 3800 | available Y`, which is the managed host budget. | Run the quick verification command and confirm both token and QNN-context lines appear. |
| Pi displayed `fd not found` or `ripgrep not found. Offline mode enabled`. | Pi could not find optional file-search binaries and therefore skipped downloading them in offline mode. | No QNN runtime change is required; basic chat still works. Install the missing binaries only if Pi's own file-search feature requires them. | Start Pi and ask a general question; it should still answer normally. |

## Operating Limits

- The compiled Gemma 4 model has a theoretical usable capacity of `3,872`
  tokens, derived from the 4,000-token context minus its 128-token
  autoregressive chunk. The active managed profile deliberately uses a
  `3,800`-token runtime ceiling to reserve headroom and prevent host-side
  sequence-length assertions.
- Keep prompts and tool results targeted. For a long session, start a fresh Pi
  session or allow the managed launcher to recover the host.
- Use `-KeepHostRunning` only when you want to reuse a loaded model. Start later
  clients with the same profile and pipe name, then shut the host down when done.
- Only the `gemma4` compiled-model profile is currently available. Add another
  model through `tools\pi\roboagent-model-profiles.ps1`; do not hard-code model
  paths in the provider or launcher.

## Related Files

- `tools\pi\roboagent-gemma4.ts` — named-pipe provider, context accounting, English
  response policy, tool shim, and token reporting.
- `tools\pi\roboagent-protocol.ts` — request/response types and tool-call validation.
- `tools\pi\start-roboagent-pi.ps1` — managed QNN host launcher and tool-mode gate.
- `tools\pi\IMPLEMENTATION_STATUS.md` — implementation handoff and remaining work.
- `README.md` — low-level QNN environment and runner troubleshooting.
