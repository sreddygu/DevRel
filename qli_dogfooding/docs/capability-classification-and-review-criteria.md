# Synapse Architecture: Capability Classification and Review Criteria

Reference document for the Dev Ex working session — October 21, 2026.
Drawn from `qli_dogfooding` as the reference implementation.

---

## 1. The Three-Layer Capability Model (plus Agent coordination layer)

The team aligned that skills are not the right container for everything.
The question for each capability is: **where does the reasoning boundary sit?**

| Layer | What it is | Who authors it | When to use it |
|---|---|---|---|
| **Documentation** | Canonical reference for concepts, constraints, options, and golden paths | Product / DevRel teams | Any time a human or AI agent needs to know *what* something is or *how* Qualcomm recommends approaching it |
| **Deterministic Tool / MCP** | Executable that produces a predictable, repeatable result | Engineering / platform teams | Any operation where the correct action is known and agent reasoning adds no value — and errors are costly |
| **Skill** | Structured orchestration instruction that interprets developer intent, selects tools, enforces safety gates, and adapts to context | DevEx / capability owners | Multi-step journeys where tool selection, sequencing, or safety judgment must be conditional on discovered state |
| **Agent Skill** | Context-aware coordinator that interprets open-ended intent, selects the skill path, presents an approved plan, gates approvals, checkpoints execution, and routes failures to recovery | DevEx / capability owners | Open-ended developer requests that require intent interpretation, approval gating, or cross-step state management |

**Decision rule:** If you could replace the skill with a single CLI call plus good documentation, it is a tool. If you could replace it with a reference doc and a few code samples, it is documentation. A skill is justified only when the *sequencing and safety judgment* require an agent. An agent skill is justified only when *intent interpretation, planning, and approval gating* sit outside the responsibility of a specific journey or domain skill.

---

### Three-question test

1. **Documentation:** could a developer answer this from a doc page? If yes, it is documentation, not a skill.
2. **Deterministic tool / MCP:** could this be a CI step with a pass/fail criterion? If yes, it is a tool, not a skill. Check the MCP inventory first, and contribute the tool back if it is missing.
3. **Skill:** does it decide differently for two developers with different setups? If no, collapse it.

Discoverability and reuse alone do not justify a skill.

## 2. What Belongs Where — QLI Dogfooding as the Concrete Example

> **Historical analysis (2026-10-21).** The "Foundational" column below is the
> pre-decision classification. Section 6 records the final layers adopted on
> 2026-10-22.

The `qli_dogfooding` project spans all three layers. Here is how each existing capability classifies, using the new criteria.

### Documentation

These are things the agent needs to *know* before acting. They do not execute; they constrain.

| Content | Current location | Note |
|---|---|---|
| Supported device families, Linux image versions, chipset variants | `skills/qli-linux-domain/references/domain-support.md` | Move to authoritative product docs; domain skill becomes a pointer |
| Evidence and status rules (Completed, Partial, Blocked, Not Tested, Not Applicable) | `references/status-and-evidence.md` | Human and agent reference; keep as structured doc |
| Workflow map — the 51 activities | `references/workflow-map.md` | Authoritative capability inventory; humans and agents both read it |
| Assessment playbook — risk tiers, delivery pipeline | `references/assessment-playbook.md` | Golden path documentation; includes the recommended execution sequence |
| Assessment results schema | `references/assessment-results-schema.md` | Machine-readable contract; belongs in doc layer as a schema file |
| README usage examples | `README.md` | Developer-facing golden path; good documentation, not a skill |

### Deterministic Tools / MCP

These operations have known correct outputs and must not involve agent interpretation. Errors are expensive (device state changes, evidence corruption, report generation failures).

| Operation | Current implementation | Classification rationale |
|---|---|---|
| Check SSH port reachability | `qli_device_lifecycle_apps.py connectivity` | Binary pass/fail; no reasoning needed |
| Run a remote SSH command | `qli_device_lifecycle_apps.py ssh` | Executes a caller-supplied command; agent decides *what* to run, tool does it |
| Transfer a file | `qli_device_lifecycle_apps.py transfer` | Deterministic SCP wrapper |
| Collect device identity (`hostname`, `uname`, `/etc/os-release`) | `scripts/qli_device_validation.py` (baseline) | Read-only, structured output; pure tool |
| Audio tone generation, playback, recording | `qli_media_storage_apps.py` | Device I/O; outcome is observable, not reasoned |
| Camera capture — single frame, burst, motion snapshot | `qli_media_storage_apps.py` | Same; binary success criterion |
| AI inference run — execute model, return scores | `qli_ai_apps.py classify`, `benchmark` | Runner invocation; timing/scores are facts, not judgments |
| Build normalized 51-workflow summary JSON | `scripts/build_qli_device_summary.py` | Pure data transformation |
| Generate Excel workbook from summary | `scripts/create_qli_device_workbook.py` | Deterministic template fill |
| Generate Word report | `scripts/create_qli_device_report.ps1` | Deterministic document generation |
| Validate toolkit structure | `scripts/inspect_toolkit.py` | Pass/fail catalog check |
| Static IP planning, DHCP restore | `qli_network_apps.py` | Dangerous enough to warrant explicit `--execute` gate; deterministic once approved |

**MCP exposure candidates** (operations that would be most useful as MCP tools for an agent framework):
- `connectivity` — ping-and-report
- `ssh` — remote command execution with credential injection
- `build_qli_device_summary` — evidence → JSON summary
- `inspect_toolkit` — catalog validation

### Skills

Justified only where conditional sequencing, safety judgment, or multi-tool orchestration is required and cannot be pre-encoded deterministically.

| Skill | Layer | Justification for remaining a skill |
|---|---|---|
| `developer-readiness-assessment` | Journey | Interprets developer intent; selects which of 51 workflows to run based on scope; manages approval gates across four risk tiers; handles resume from checkpoint. Cannot be pre-encoded as a single tool call. |
| `qli-linux-domain` | Domain | Applies device-family context before any QLI skill runs. Provides the safety and evidence constraints that shape *how* tools are called. Justified as a skill because it is loaded conditionally and modifies downstream behavior. |
| `device-connectivity-validation` | Foundational | **Borderline — consider collapsing.** Currently a one-paragraph instruction wrapping a single CLI call. Value is in making the safety boundary explicit (do not switch Wi-Fi, do not change routes) rather than in orchestration. If the safety rule is in documentation and the tool enforces it, this skill is redundant. |
| `ai-inference-benchmark` | Foundational | **Borderline — consider collapsing.** One-step tool invocation with a stated prerequisite. The prerequisite check and evidence-separation rule belong in documentation; the benchmark itself is a tool call. |
| `host-environment-validation` | Foundational | **Keep if** it performs conditional checks (is `plink` available? fall back to `ssh`?). **Collapse if** it is just a checklist of which binaries to run. |
| `baseline-evidence-collection` | Foundational | **Keep.** Gathers N discovery commands, validates completeness, stores structured evidence. Conditional on what is found. Has meaningful agent judgment. |
| `diagnostic-log-collection` | Foundational | **Keep.** Called on failure; must select which log sources are relevant to the failure mode. Conditional routing is the value. |
| `readiness-report-generation` | Foundational | **Collapse to tool.** Calls three scripts in sequence. No judgment required. The pipeline is deterministic once the summary JSON exists. |
| `device-identity-discovery` | Foundational | **Borderline.** Runs `hostname` + `uname` + `os-release`. Pure read operations — could be a tool. Value as a skill is only if the agent must decide *which* identity fields are needed for a given context. |

**Net result for QLI:** 9 skills → **2 clear keeps** (journey + domain), **3 probable keeps** (baseline evidence, diagnostics, host validation), **4 candidates to collapse** into tools + documentation. That is a ~50% reduction before the first refactor pass.

---

## 3. Skills That Belong in Each Bucket — Generalized Criteria

These are the criteria that apply across products, not just QLI.

### A domain skill is justified when it:

- Makes a conditional decision about *which* tool to invoke based on discovered state
- Enforces a safety gate that the tool itself cannot enforce (because the gate depends on context)
- Has at least two meaningful execution paths depending on what it finds
- Would produce different actions for two developers with different device states

A domain skill is **not justified** when it is a single tool call with a fixed argument pattern. That is an MCP tool with documentation.

### A context document is justified when it:

- Applies a constraint set that modifies the behavior of multiple domain skills
- Is product/platform-specific knowledge that would otherwise be duplicated across multiple skills
- Has a clear owner who will maintain it as the product evolves

### A journey skill is justified when it:

- Composes more than two domain skills or MCP tools in a sequence that depends on what each step finds
- Manages approval gates between risk tiers
- Produces a developer-deliverable artifact (report, workbook, evidence package)
- Has resume/checkpoint behavior because the total work exceeds a single session

### Nothing should be a skill when:

- The same thing can be expressed as a documentation golden path + a tool
- The skill has one owner and one caller — that is a private implementation detail, not a shared capability
- No one has committed to maintaining it when the underlying API or device changes

---

## 4. Review and Exit Criteria for External Developer Capabilities

Before any capability is presented to external developers as a supported experience, it must pass the following gates.

### Gate 1: Ownership

- Named individual primary owner, not a team and not "the working group"
- Named backup / escalation contact
- Defined review cadence — at minimum, once per major SDK or device release

A capability without a committed owner does not exit pilot.

### Gate 2: Scope and Boundary Definition

- The capability's input, output, and side effects are documented
- What it will *not* do is explicit (negative scope)
- Prerequisites are declared, not assumed
- If it touches device state: the state before and after is defined

### Gate 3: Validation Evidence

- At least one complete end-to-end execution on a supported target, with evidence retained
- Known failure modes documented with their recovery actions
- Tested against at least two configurations (device models, image versions, host OS variants) before claiming cross-product applicability
- A pass/fail criterion exists — not "it seemed to work"

For QLI specifically: `inspect_toolkit.py` passing + a complete `evidence/` directory from the target device = minimum validation evidence.

### Gate 4: Developer Feedback Mechanism

- There is a channel where a developer can report that the capability is wrong, broken, or missing something
- Someone is committed to reading that channel
- The feedback loop is described in the capability's documentation (not buried in an internal wiki or chat thread). Preferred: a public GitHub Issues queue or the DevRel intake form

### Gate 5: Discoverability

- The capability can be found without already knowing its name
- It appears in the appropriate product or SDK documentation
- If it is a skill: its `skill.yaml` triggers and aliases reflect real usage patterns
- It is discoverable by the agent frameworks it targets (MCP and A2A)

### Gate 6: Lifecycle Commitment

- A deprecation/retirement path exists
- Developers are not left depending on a capability that will go stale silently
- Version is declared and follows a scheme the team will honor
- The maturity label in `skill.yaml` reflects the actual state

### What "pilot" means under these criteria

A pilot capability has passed Gate 1 (ownership) and Gate 3 (at least one validated execution). It has not yet passed Gates 4–6. It should be labeled as pilot in documentation and in `skill.yaml` (`maturity: pilot`) so developers know what they are getting.

A capability at `maturity: supported` has passed all six gates.

---

## 5. Immediate Recommendations for QLI Dogfooding

Based on the classification above and the architecture direction from both working sessions.

1. **Collapse `readiness-report-generation` into a tool call.** The three-script pipeline is deterministic. Remove the skill; document the sequence in the assessment playbook.

2. **Collapse `device-connectivity-validation` and `ai-inference-benchmark` into tool + documentation.** The safety rules belong in `qli-linux-domain` documentation; the operations are single CLI calls.

3. **Expose `connectivity`, `ssh`, `baseline-evidence-collection`, and `build_qli_device_summary` as MCP tools.** These are the operations an agent framework needs to call predictably without interpreting.

4. **Rename `qli-linux-domain` from a skill to a context document.** It never executes — it is documentation that shapes how other skills behave. Load it as a system-prompt injection or referenced doc, not as a selectable skill.

5. **Keep `developer-readiness-assessment` as the single journey skill.** It is the one place where conditional sequencing, safety gating, and resume behavior genuinely require an agent. It is also the right granularity for external developers to invoke.

6. **Set maturity targets:** The journey skill should reach `maturity: supported` when it has passed all six review gates above. Current status: pilot (Gate 1 + partial Gate 3 satisfied for IQ9; IQ8 assessment blocked).

7. **Publish `qli-readiness-agent` as the agent-layer skill.** Intent interpretation, plan presentation, approval gating, checkpoint management, and failure routing belong in a declared skill — not as an implicit hosting-framework responsibility. The agent skill declares responsibilities, not_responsible_for, approval gates, failure behavior, and an A2A role.

---

## 6. Decisions Recorded — 2026-10-22

The P3 Skill Standards working session adopted all five recommendations in
section 5. The following decisions are now in effect and reflected in the
skill.yaml files and ADR `0001-adopt-synapse-skill-layers.md`:

1. **`readiness-report-generation` collapsed to MCP tool.** Three-script
   pipeline is deterministic; sequence documented in the assessment playbook.
2. **`device-connectivity-validation` and `ai-inference-benchmark` collapsed
   to MCP tools.** Safety rules now documented in the QLI Linux context
   document; operations are single CLI calls.
3. **`device-connectivity-validation`, `ssh`, `baseline-evidence-collection`,
   and `build_qli_device_summary` flagged as MCP exposure candidates** in the
   shared MCP inventory. Check inventory before re-implementing.
4. **`qli-linux-domain` reclassified as a context document.** Load as injected
   context or system-prompt injection; not presented as a selectable skill.
5. **`developer-readiness-assessment` retained as the single journey skill.**
   Confirmed as the correct granularity for external developer invocation.
6. **Maturity target:** journey skill advances to `maturity: supported` after
   passing all six review gates. Current status remains `pilot`.
7. **`qli-readiness-agent` published as the agent-layer skill (2026-10-23).**
   Intent interpretation, plan presentation, approval gating, checkpointing,
   and failure routing declared in a skill contract rather than left as implicit
   hosting-framework behavior. Skill declares responsibilities,
   not_responsible_for, approval_gates, failure_behavior, two_config_evidence,
   and A2A role.
