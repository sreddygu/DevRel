# RoboAgent Synapse Skill Catalog

RoboAgent runs local Gemma 4 through a persistent QNN host and Pi. It uses the
shared `p3-device` profile; these skills preserve the project's read-only-first
tool policy and explicit mutation approvals.

| Layer | ID | Use when | Default outcome |
| --- | --- | --- | --- |
| Domain | [`robot-runtime-discovery`](robot-runtime-discovery/SKILL.md) | Inspecting local QNN/Pi runtime readiness | A read-only readiness record |
| Domain | [`multimodal-command-validation`](multimodal-command-validation/SKILL.md) | Evaluating grounded model responses and tool calls | A deterministic evaluation result |
| Context | [`robot-safety-boundaries`](robot-safety-boundaries/SKILL.md) | Any RoboAgent request | Mandatory read-only and approval policy |

Do not commit named-pipe details, local model paths, logs containing user data,
or QNN environment values that are not intended for public distribution.
