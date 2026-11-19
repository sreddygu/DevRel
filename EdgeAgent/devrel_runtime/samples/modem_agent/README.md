# Modem Agent

> **Status**: planning / scoping. No agent code yet.

This directory holds architecture and requirements artifacts for the
Modem Agent - an on-device AI decision system embedded in the UE
modem stack, **developed as a DevRel sample** (same lifecycle as
`samples/stc_classifier/` and `samples/ai_gateway_classifier/`).

| File | Purpose |
|---|---|
| [docs/requirements.md](docs/requirements.md) | What the agent must do, NFRs, compliance, acceptance criteria, DevRel framework integration |
| [docs/design.md](docs/design.md) | How the agent is structured: DevRel adapter set, three-tier architecture, data path, models, deployment, five-gate test strategy |
| [docs/open_questions.md](docs/open_questions.md) | Unresolved architectural / product / process decisions, with owners and recommendations |
| [make_docx.py](make_docx.py) | Markdown -> docx converter so docs ship in both formats |

## Headline use case (Release 1)

**UC-1 - Max-Retransmission-Based RLF Prevention**: predict Radio Link
Failure ~720 ms earlier than the legacy fixed-counter mechanism by
analyzing HARQ feedback patterns + last-valid-status-PDU recency +
scenario context (RF tuneaway / NTN / mmWave), and intervene with
adjusted recovery timers before user-visible outage begins.

## Why DevRel as the development framework

Modem dev cycles are slow: build, sign, flash, take device to lab.
The agent's algorithmic work (feature extraction, model training,
arbitration logic, safety filter) does not need a real modem to
develop and test. Following the AI Gateway pattern in this repo:

1. **Adapter pattern** - agent code targets `ModemPlatformAdapter` /
   `ModemInferenceAdapter` / `ModemTelemetryAdapter` /
   `ModemActionAdapter`. Mock implementations run on this Snapdragon X
   laptop; real implementations link into modem FW.
2. **Codegen scaffold** - `templates/modem/c_modular/` emits the
   per-use-case agent app structure (parallel to
   `templates/gateway/c_modular/`).
3. **Five-gate validation** - the same `test_procedure.ps1` pattern
   used by `samples/stc_classifier/`: pytest, dry-run build, mock
   deploy, profile shape, trace replay. Real-modem validation runs
   the same gates with `MODEM_HOST` set.
4. **Real flips on with one env var** - `MODEM_HOST=<device>` swaps
   mock adapters for real ones at process startup; agent code
   unchanged.

DevRel is the *development* framework, not a runtime dependency on the
shipped modem. Production builds collapse the adapter layer and link
vendor SDKs directly.

## Architectural principles

Three-tier separation:

1. **Agent tier** - observes telemetry, runs models, produces *recommendations*.
2. **Arbitration tier** - applies safety filter + confidence threshold + priority.
3. **Action tier** - the only tier that mutates modem state, through bounded hooks.

This guarantees no single ML model can take an unsafe action by itself
- the arbiter is the choke point.

## Next steps

1. Review the three docs (requirements / design / open_questions).
2. Drive open questions to closure (these are the blockers for Phase 0
   kickoff):
   * **Q-B.1** - DevRel adapter strategy (extend DevRel vs parallel framework)
   * **Q-B.1.1** - NSP runtime selection (NWAIOS / QNN-Hexagon / custom)
   * **Q-A.4** - RAT scope for R1
   * **Q-E.1** - Owning org
3. Phase 0: extend DevRel with the modem adapter set + codegen template
   + `devrel modem` CLI + `devrel doctor --section modem`. Mocks-only;
   no real modem dependency.
4. Phase 1+: agent core + UC-1, plugged into the Phase-0 adapters.

## Regenerating the .docx

```powershell
..\stc_classifier\.venv\Scripts\python.exe make_docx.py
```

The converter is re-runnable; edit the markdown sources, then refresh
the .docx outputs before sharing.
