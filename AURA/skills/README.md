# AURA Synapse Skill Catalog

AURA is a privacy-first physical-AI agent. It uses the shared `p3-device`
profile; these skills cover AURA's local orchestration, event pipeline, and
safe action-validation workflows.

| Layer | ID | Use when | Default outcome |
| --- | --- | --- | --- |
| Journey | [`aura-agent-orchestration`](aura-agent-orchestration/SKILL.md) | Preparing an AURA runtime and selected milestone | A tested, inspected runtime plan |
| Domain | [`multimodal-event-pipeline`](multimodal-event-pipeline/SKILL.md) | Validating perception, speech, and memory events | A scoped event-pipeline evidence record |
| Domain | [`on-device-action-validation`](on-device-action-validation/SKILL.md) | Evaluating approved action behavior on a target | A safety-gated action validation result |

Keep model paths, endpoints, device credentials, image frames, audio, and
personal event data out of versioned evidence.
