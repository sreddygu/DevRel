# Developer Readiness Assessment Skill

This folder is a framework-neutral skill package for orchestrating the
`qli_dogfooding` toolkit. Its core files do not depend on a specific model,
agent framework, prompt format, or vendor runtime.

It is the Synapse **journey** layer. It injects the `qli-linux-domain` context
document and composes domain skills and MCP tools instead of treating the
51-workflow catalog as a flat list of commands.

## Portable Contract

An agent framework can load this skill by:

1. Indexing `skill.yaml`.
2. Matching a user request against `selection.aliases` and `selection.triggers`.
3. Loading [`SKILL.md`](SKILL.md) as the procedural instruction entrypoint.
4. Loading only the referenced files needed for the current task.
5. Resolving the toolkit root from `project.root_relative_to_skill`.
6. Providing filesystem and command-execution tools to the executing model.

The skill is usable by any model that can follow instructions and call the
required tools. Models without tool access can still use it to create an
assessment plan, command checklist, status rubric, or report outline.

## Adapters

`agents/openai.yaml` is an optional OpenAI/Codex UI adapter. It is not required
by the core skill. Other frameworks should map
[`skill.yaml`](skill.yaml) and [`SKILL.md`](SKILL.md) into their own skill,
tool, prompt, plugin, or router mechanism.

See [framework integration](references/framework-integration.md) for patterns
covering prompt routers, tool-using agents, multi-agent systems, and local
models. Use the [assessment-results schema](references/assessment-results-schema.md)
when converting verified device evidence into workbook and report statuses.

## Validation

```powershell
py -3 .\scripts\inspect_toolkit.py --project-root ..\..
```

Run the framework-specific skill validator when one is available. The OpenAI
adapter can additionally be checked with the skill-creator `quick_validate.py`.
