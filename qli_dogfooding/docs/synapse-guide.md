# Synapse Skills: QLI Dogfooding

QLI Dogfooding is a concrete Synapse implementation. It demonstrates how
trusted skills, QLI Linux domain context, and controlled agent reasoning can
turn a developer request into a validated technical outcome. It also makes a
clear distinction between demonstrated capability and the next hosting-agent
integration milestone.

## Objective

Secure agreement that the QLI Dogfooding catalog is a valid initial Synapse
pilot: reusable operations are structured as trusted skills, organized with
QLI Linux context, composed into a developer outcome, and backed by evidence.

**Key message:**

> Synapse turns a developer request into a safe, evidence-backed outcome.
> For QLI, that means selecting the smallest trusted operation, applying the
> right device context, and returning a result the developer can act on.

## Demonstrated Capability

| Capability | QLI implementation | Why it matters |
| --- | --- | --- |
| Reusable domain operations | Five domain skills | A developer or agent can select one bounded, verifiable operation instead of copying a procedure. |
| Deterministic MCP tools | Three MCP tool specs (connectivity, benchmark, report pipeline) | Registered once in the shared MCP inventory; called directly without a skill wrapper. |
| Platform context | QLI Linux context document (injected, not selected) | Device support, safety gates, evidence expectations, and ownership travel with every operation. |
| End-to-end outcome | One developer-readiness journey | Multi-step readiness, reruns, comparisons, and deliverables use composition rather than duplicated instructions. |
| Existing capability | 51 unique dogfooding workflows across 52 module entries | Synapse packages existing technical capability; it does not invent a parallel tool catalog. |
| Evidence | Historical IQ9 validation and reporting artifacts | Completion is based on device evidence, not a command having been issued. |

The catalog and its routing diagrams are in
[`skills/README.md`](../skills/README.md). The architectural decision and
canonical terms are documented in
[`0001-adopt-synapse-skill-layers.md`](adr/0001-adopt-synapse-skill-layers.md)
and [`CONTEXT.md`](../CONTEXT.md).

## Narrative

### Developer Outcome

> A developer does not start by asking which command to run. They ask whether
> a device is ready, whether it is reachable, or whether a model meets a
> performance target. Synapse must turn that intent into a verified result.

The request **"Validate connectivity to this QLI device"** is a bounded,
non-destructive example that makes the routing decision visible.

### Layered Capability Model

The routing diagrams in [`skills/README.md`](../skills/README.md) illustrate
the division of responsibility:

| Layer | QLI role | Meeting message |
| --- | --- | --- |
| Agent skill | `qli-readiness-agent` | Interprets open-ended developer intent, selects the skill path, presents the plan, gates approvals, checkpoints execution, routes failures to recovery. Implemented in the QLI catalog — not a hosting-framework responsibility. |
| Journey | `developer-readiness-assessment` | Use this only when the requested outcome spans multiple operations. |
| Domain skills | `host-environment-validation`, `device-identity-discovery`, `baseline-evidence-collection`, `ai-model-execution`, `diagnostic-log-collection` | Load only when conditional judgment is needed about which tool to invoke. |
| MCP tools | `device-connectivity-validation`, `ai-inference-benchmark`, `readiness-report-generation` | Deterministic operations — call directly, no skill wrapper. Check the shared MCP inventory first. |
| Context document | `qli-linux-domain` | Injected as system context before any QLI skill runs. Not a selectable skill. |

**Selective loading:**

> A connectivity request does not need a readiness report, model benchmark, or
> full journey. Synapse loads the smallest path that can produce a validated
> result.

### Focused Operation Example

The **Bounded Task Route** diagram in
[`skills/README.md`](../skills/README.md#bounded-task-route) shows this route:

1. Developer asks to validate connectivity.
2. The hosting framework injects the QLI Linux context document.
3. It calls the
   [`device-connectivity-validation`](../skills/device-connectivity-validation/SKILL.md)
   MCP tool directly — no skill wrapper needed.
4. The tool checks reachability without changing Wi-Fi, routes, or IP
   configuration.
5. The developer receives a verified connectivity result and a safe next
   action.

For an approved device, this non-destructive command can be run from the
project root. Replace `<DEVICE_IP_OR_HOST>` only when running the command; private
endpoints do not belong in shared material.

```powershell
py -3 .\src\qli_device_lifecycle_apps.py connectivity `
  --host <DEVICE_IP_OR_HOST> --port 22
```

> The value is not the connectivity command itself. The value is that the
> operation is discoverable by intent, bounded by domain safety, and produces
> evidence that the next skill or developer can trust.

### Composed Outcome Example

The full composition and recovery diagram is in
[`skills/README.md`](../skills/README.md#how-synapse-is-applied-in-qli).

The following request requires a composed journey:

> Assess whether this IQ9 device is ready to run and benchmark an AI model.

This request crosses multiple operations, so it selects the
`developer-readiness-assessment` journey. The journey composes the applicable
domain skills and MCP tools: host validation, identity discovery, baseline
evidence collection, model execution, inference benchmark (MCP tool), diagnostics
if needed, and report generation (MCP tool).

**Recovery behavior:**

> A failure does not become a successful workflow because a command ran. It
> moves to bounded diagnostics, returns to the `qli-readiness-agent` for a recovery
> decision, and preserves the evidence trail.

### IQ9 Pilot Journey: Deploy and Benchmark Gemma

The proposed Synapse pilot is **"Deploy and benchmark Gemma on IQ9."** It maps
onto this catalog in five steps:

| Step | What happens | QLI capability |
| --- | --- | --- |
| 1. Intent | Capture goal, model, target, and constraints | `qli-readiness-agent` |
| 2. Select | Choose the approved journey and domain skills | `qli-readiness-agent` selects `developer-readiness-assessment` |
| 3. Prepare | Discover the device and host, then gather tools and artifacts | `host-environment-validation`, `device-connectivity-validation` (MCP), `device-identity-discovery`, `baseline-evidence-collection` |
| 4. Execute | Run with QNN, Genie, and Qualcomm Linux context | `qli-linux-domain` (injected), `ai-model-execution` |
| 5. Validate | Check correctness, latency, throughput, and recovery | `ai-inference-benchmark` (MCP), `diagnostic-log-collection` on failure, `readiness-report-generation` (MCP) |

Gemma on the IQ9 NPU is not yet part of the recorded evidence. The Genie
bundle is on the device, but the smoke test has not run. Benchmark targets are
still to be set. Until they are, this route is a proposed pilot, not a
validated result.

### Evidence and Validation

Catalog inspection from the project root:

```powershell
py -3 .\skills\developer-readiness-assessment\scripts\inspect_toolkit.py `
  --project-root .
```

Expected proof:

- **52 module entries representing 51 unique workflows**.
- **11 Synapse packages validated**: one agent skill (`qli-readiness-agent`),
  one journey, five domain skills, one context document (`qli-linux-domain`),
  and three MCP tools (also specified in `skills/mcp-tools.yaml`). Each
  manifest declares the five-part publishing contract and its review-gate status.
- `Toolkit validation: PASS`.

The historical IQ9 summary is available at
`evidence/iq9_summary_2026-08-12.json` (local evidence, not committed).
This evidence was captured on **August 12, 2026**; it demonstrates the implementation's
evidence model and is not a claim about current device state on **October 9,
2026**.

The recorded IQ9 assessment includes 36 Completed, 3 User Completed, 8 Not
Tested, 1 Blocked, 2 Partial, and 1 Not Applicable workflow results. It also
records QNN HTP sample profiling as completed, while retaining known gaps such
as unavailable object detection/two-model comparison and the absent local LLM
endpoint. This is useful proof because the assessment reports limitations rather than
hiding them.

A presentation-safe summary of the recorded QNN, media, device-health, agent,
and catalog-validation evidence is available in
[Evidence Summary](execution.md).

### Pilot Decisions

The pilot requires four decisions:

1. **Pilot outcome:** approve QLI device readiness and AI benchmarking as an
   initial Synapse journey pilot.
2. **Ownership:** confirm Srinivas Reddy Gudala as the named owner of the QLI
   domain skill and MCP tool contracts, with the DevRel Developer Experience
   team as backup; platform teams own their corresponding domains.
3. **Runtime boundary:** choose the hosting agent framework that will run
   `qli-readiness-agent`, index `skill.yaml`, load instructions selectively,
   enforce approvals, and retain checkpoints.
4. **Success measures:** track time to first validated result, journey
   completion, recovery rate, domain-skill and MCP-tool reuse, and coverage gaps.

**Closing line:**

> The QLI implementation shows the target operating model: developer intent in, selected
> trusted capabilities executed with evidence, validated outcome out.

## Current Scope and Next Milestone

| Demonstrated now | Not yet demonstrated |
| --- | --- |
| A reviewed catalog of 8 skill packages (1 agent skill, 5 domain, 1 journey, 1 context document) and 3 MCP tool specs with metadata, contracts, authoritative references, safety behavior, and layer ownership | A production hosting-agent router or MCP integration that automatically indexes and executes the catalog |
| [Workflow tooling for 51 unique QLI workflows](workflow.md) | Autonomous selection and resume behavior implemented in a specific agent runtime |
| Non-destructive focused validation such as device connectivity checks via MCP tool | A claim that all workflows or all QLI configurations are fully validated |
| Evidence-backed IQ9 reporting with Partial, Blocked, and Not Tested results retained | A live current-state assertion based solely on evidence captured on August 12, 2026 |

This honesty is a strength: the skill catalog is ready for integration, while
agent runtime integration is the next implementation milestone.

## Safety Boundaries

- Approved test devices and non-destructive connectivity validation are the
  appropriate demonstration boundary.
- Flashing, recovery, Wi-Fi changes, static-IP activation, controlled crash
  testing, and report overwrites remain explicit approval-gated activities.
- Device addresses, credentials, tokens, private endpoints, and personal data
  are excluded from shared material.
- Where a device is unavailable, the routing diagrams, catalog inspection, and
  dated IQ9 evidence demonstrate the catalog, contracts, validation, and
  evidence model.
- A failed connectivity check records evidence, selects diagnostic log
  collection, and requires a recovery decision before work continues.

## Decision Record

| Topic | Decision | Owner | Due date |
| --- | --- | --- | --- |
| Initial Synapse pilot outcome |  |  |  |
| Hosting-agent/runtime integration |  |  |  |
| Domain and skill owners |  |  |  |
| Authoritative documentation sources |  |  |  |
| Pilot success measures |  |  |  |
| Next review checkpoint |  |  |  |