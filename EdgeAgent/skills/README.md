# EdgeAgent Synapse Skill Catalog

EdgeAgent provisions an MCP-compatible development client and evaluates local or
device-backed edge-AI workflows. It builds on the shared `p3-device` profile;
these project-local skills cover only the EdgeAgent-specific procedures.

| Layer | ID | Use when | Default outcome |
| --- | --- | --- | --- |
| Journey | [`edge-agent-runtime-setup`](edge-agent-runtime-setup/SKILL.md) | Preparing a host to use EdgeAgent | A verified local runtime plan without changing IDE configuration |
| Domain | [`agent-tool-contract-validation`](agent-tool-contract-validation/SKILL.md) | Checking the MCP transport and generated tool contract | A redacted, validated transport result |
| Domain | [`device-agent-evaluation`](device-agent-evaluation/SKILL.md) | Evaluating an approved model on a discovered target | A reproducible device evaluation record |

Run the commands from `../devrel_runtime/`. Do not store SSH keys, bearer
tokens, device addresses, or model artifacts in evidence committed to this
repository.
