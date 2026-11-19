# Framework Integration

The skill core is framework-neutral. [`skill.yaml`](../skill.yaml) is the
discovery manifest and [`SKILL.md`](../SKILL.md) is the execution entrypoint.

## Generic Loader Contract

Implement the following behavior in any agent framework:

1. Scan skill directories for `skill.yaml`.
2. Index `id`, `name`, `description`, `selection.aliases`, `selection.triggers`,
   and `synapse.layer`.
3. Match the user request semantically or by explicit skill ID.
4. Load [`SKILL.md`](../SKILL.md) when the skill is selected.
5. Load referenced files and declared Synapse dependencies lazily as required by
   the current task.
6. Resolve project paths relative to the skill directory.
7. Expose filesystem, command, SSH, spreadsheet, and document tools as available.
8. Enforce the safety gates even if the user asks for full automation.

## Prompt-Only Models

Inject [`SKILL.md`](../SKILL.md) into the system or task context and ask the model to produce a
plan, command checklist, status rubric, or assessment report. Clearly state
that commands are proposed rather than executed.

## Tool-Using Single Agents

Register the skill description with the framework's router. After selection,
provide [`SKILL.md`](../SKILL.md) and tool access. The agent should run
`inspect_toolkit.py` before accessing the device and request approval for risky
operations.

## Multi-Agent Frameworks

Use the skill as a shared procedure and split responsibilities only when useful:

- Coordinator: scope, safety, status decisions, final consistency.
- Device operator: SSH, networking, media, runtime discovery.
- AI validator: inference, model comparison, endpoints, agent workflows.
- Evidence/report agent: summary, workbook, Word report, stale-text checks.

Keep one authoritative evidence directory and one status ledger to avoid agents
overwriting or contradicting each other.

## Router Examples

The skill should rank highly for requests containing concepts such as:

- developer readiness
- device dogfooding
- validate IQ8 or IQ9
- test a new Linux device image
- camera/audio/AI readiness
- create dogfooding workbook or report
- rerun blocked workflows
- compare device readiness

Do not select it for isolated code questions unrelated to device validation.

## Framework Adapters

- OpenAI/Codex-compatible UIs may use `agents/openai.yaml`.
- Claude, Gemini, local-model, LangChain/LangGraph, AutoGen, CrewAI, Semantic
Kernel, and custom routers can ingest [`skill.yaml`](../skill.yaml) and
[`SKILL.md`](../SKILL.md) directly or transform them into their native
prompt/tool/plugin format.
- MCP can expose the existing toolkit scripts as tools, while this skill remains
  the orchestration and safety policy.

Automatic discovery depends on the framework implementing the generic loader
contract or a small adapter. The skill content itself has no model dependency.

## Synapse Composition

The QLI toolkit exposes four layers:

1. `skills/*` packages with `synapse.layer: domain` perform one verified
   operation requiring conditional judgment; `synapse.layer: mcp-tool` packages
   define deterministic single-step operations (call directly as tools).
2. `qli-linux-domain` provides supported-platform, evidence, and safety context
   (injected as a context document, not selected as a skill).
3. `developer-readiness-assessment` composes domain skills and MCP tools into a
   readiness journey.
4. An external agent router selects skills, presents the plan, enforces approval
   gates, and stores checkpoints for resume behavior.

Routers should prefer the smallest matching domain skill (or MCP tool call) for
a bounded request. They should select the journey only when the request requires
a multi-workflow developer outcome. Intent interpretation, dynamic routing,
approval management, and resume logic remain responsibilities of the hosting
agent framework until this project has a runnable router integration.
