# Adopt Synapse Skill Layers

QLI Dogfooding will expose its device operations as domain skills and MCP tools,
group them under injected QLI Linux context, compose them through readiness
journeys, and coordinate them through a declared agent skill. This preserves the
existing 51-workflow toolkit while making ownership, discovery, safety,
validation, and reuse explicit instead of keeping them inside one monolithic
procedure.

## 2026-10-22 Update — P3 Skill Standards Working Session

The working session aligned on the following changes to the original architecture:

- **Foundational tier removed.** Replaced by two distinct containers: Domain
  Skills (require conditional judgment) and Shared Tooling / MCP (deterministic
  single-step operations).
- **Determinism is the classification test.** If the correct action is known
  and an agent adds no value, it is an MCP tool. If sequencing or safety
  judgment is conditional on discovered state, it is a domain skill.
- **MCP-first guidance.** Check the shared MCP inventory before writing a new
  tool. If a tool exists, reuse it. If not, write it and contribute it back.
- **`qli-linux-domain` reclassified as a context document.** It never executes;
  it documents constraints. Load it as injected context, not as a selectable
  skill.

**Resulting classification for QLI:**

| Capability | Old layer | New layer |
|---|---|---|
| `baseline-evidence-collection` | Foundational | Domain skill |
| `diagnostic-log-collection` | Foundational | Domain skill |
| `host-environment-validation` | Foundational | Domain skill |
| `device-identity-discovery` | Foundational | Domain skill |
| `ai-model-execution` | Foundational | Domain skill |
| `device-connectivity-validation` | Foundational | MCP tool |
| `ai-inference-benchmark` | Foundational | MCP tool |
| `readiness-report-generation` | Foundational | MCP tool |
| `qli-linux-domain` | Domain skill | Context document |
| `developer-readiness-assessment` | Journey | Journey (unchanged) |
| `qli-readiness-agent` | (absent) | Agent skill |

## 2026-10-23 Update — Agent Layer Published

The agent-layer coordinator is now a declared skill, not an implicit
hosting-framework responsibility:

- **`qli-readiness-agent` published.** Interprets developer intent, selects the
  smallest safe path, presents an approved plan, enforces approval gates,
  checkpoints execution, and routes failures to recovery.
- **Agent skill contract declared.** Includes responsibilities,
  not_responsible_for, approval_gates, failure_behavior, two_config_evidence,
  and A2A role — same gate-field standard as domain and MCP skills.
- **Catalog now has all five layers.** Context document, Domain skills, Journey
  skill, MCP tool candidates, and Agent skill are all represented in the
  `skills/` directory.

## 2026-10-26 Update — Aligned with the Skill Architecture and Standards Deck

The catalog now matches `Synapse_Skill_Architecture_and_Standards.pptx`:

- **Publishing contract.** Every `skill.yaml` declares all five areas:
  Ownership, Classification, Contract, Authority (approved tools, endpoints,
  provenance), and Control (consequential actions, recovery and rollback). It
  also declares `developer_journey_stage` and `supported_versions`.
- **Named individual owner.** `owner` is Srinivas Reddy Gudala. The DevRel
  Developer Experience team is the backup. Gate 1 does not accept a team name.
- **Review-gate status.** Each manifest records `review_gates`. Everything
  stays `pilot`. Discoverability (Gate 5) is open across the catalog. The
  journey and agent skills have only partial validation evidence.
- **Evidence audit (2026-10-26).** Every `two_config_evidence` line now cites
  a dated file under `evidence/`. Five packages have evidence from both
  devices: host validation, identity, connectivity, baseline, and diagnostics.
  Three have evidence from only one device: `ai-model-execution` and
  `ai-inference-benchmark` (IQ9 NPU only; IQ8 Not Tested, and no CPU-backend
  evidence) and `readiness-report-generation` (full pipeline evidenced for IQ8
  only). The earlier claims of IQ8 and CPU/NPU coverage were not backed by
  evidence and have been removed.
- **Validator updated.** `inspect_toolkit.py` now expects the context, domain,
  mcp-tool, journey, and agent layers. It also enforces the contract fields.
- **Private endpoints removed** from manifest evidence lines.

Open questions carried from the deck, still unresolved: sharper tier
definitions and examples, whether three skill tiers can simplify further, the
governance model, P2/P3 maturity alignment, and onboarding an Arduino
stakeholder.

- **IQ8 rerun (2026-10-26).** This rerun cleared the 10/12 block. It collected
  a fresh baseline and ran the same `mobilenetv2.dlc` on IQ8 NPU and CPU. The
  top-5 results match IQ9. `ai-model-execution` and `ai-inference-benchmark`
  now meet Gate 3. Profiler execute time is 5.2 ms on the NPU and 40.1 ms on
  the CPU, but per-process wall-clock shows the NPU as slower (666 ms vs
  110 ms) because of HTP init and finalize. The benchmark tool's wall-clock
  number is therefore not a valid NPU throughput claim. See
  `evidence/iq8-2026-10-26/assessment_checkpoint.md`.
- **Gate 3 closed for the journey, report, and agent packages (2026-10-26).**
  The IQ8 deep rerun reached 28 Completed. One run also exposed a
  `rotate-logs` defect, which was fixed and re-verified. The IQ9 report
  pipeline produced deliverables whose totals reconcile. A hosting agent then
  executed `qli-readiness-agent` on IQ8. The request mixed a safe AI-readiness
  check with an unapproved static-IP change. The agent completed the safe path
  and held the network change at the gate, and the device was verified still on
  DHCP. The run logged 14 protocol gaps in
  `evidence/iq8-2026-10-26/agent_run/protocol_gaps.md`, which feed the v1.1
  revision of the agent skill.
