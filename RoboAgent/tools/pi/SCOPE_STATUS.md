# Pi + Gemma 4 Integration Scope Status

## Original milestone

> Call Gemma 4 through Pi using the supplied compiled model and runner, with
> basic commands proving the integration.

## Status

| Capability | Status | Evidence |
|---|---|---|
| Pi provider registration | Complete | `roboagent/gemma4` appears in Pi model discovery. |
| Local Gemma 4 inference | Complete | Non-interactive Pi prompts return text. |
| QNN host startup | Complete | `start-roboagent-pi.ps1` starts and waits for the named pipe. |
| Host shutdown | Complete | Launcher sends `shutdown` and cleans up its process. |
| Explicit turn envelope | Implemented | `roboagent-protocol.ts` adds session, turn, phase, and tool budget fields. |
| Project guidance | Complete | `AGENTS.md` and `.pi/skills/` are present. |
| Read-only tools | Implemented | Tools are workspace-scoped and opt-in with `-ReadOnlyTools`; tool calls are schema-validated. |
| Tool request/result/final loop | Validated for read-only tools | The adapter rejects malformed, unknown, and repeated calls; the deterministic protocol test and four-task QNN smoke suite pass with grounded final answers. |
| Context recovery/replay | Implemented; final live-session check pending | Budget exhaustion starts an observable recovery process, validates the ready named pipe, and replays bounded conversation text when launched by the managed launcher. |
| Per-turn sequence budget | Validated | The adapter sends the estimated cumulative position plus the profile response budget, preventing Pi auto-compaction from generating to the 3,800-token host ceiling. |
| Approved mutations | Enabled, not production-validated | `-ReadOnlyTools -EnableMutations` exposes writes, patches, and commands; every mutation still requires Pi approval. |
| Model profiles and warm host | Validated | `roboagent-model-profiles.ps1` centralizes compiled-model settings; `-KeepHostRunning` reuses a loaded host for later clients. |
| Per-request token usage | Validated | QNN `prompt_tokens` and `generated_tokens` populate Pi usage metadata and appear after each completed response. |
| English-only output | Adapter regression-tested | A compact English-only rule is sent with every request; `test-english-output.ps1` verifies that mocked Chinese/Portuguese output is suppressed. |
| Evaluation harness | Implemented | JSONL results record latency, tool requested/valid/repeated/invalid signals, and grounded-final status. |

## Executive conclusion

The requested initial milestone is complete: Pi can call the local Gemma 4
model through the supplied QNN runner. Read-only structured tool use and
English-only output handling are validated for the current prompt-based
`<tool_call>` shim. The remaining operational check is a real multi-turn context
recovery run; the next functional milestone is evaluating a deterministic/native
tool-call output format against another compiled model or the
`tiny-tool-calling` reference implementation.
