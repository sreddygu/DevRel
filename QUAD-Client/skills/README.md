# QUAD-Client Synapse Skill Catalog

QUAD-Client provisions an MCP-compatible development client for QUAD and
supports local or device-backed QNN workflows. It builds on the shared
`p3-device` profile; these skills describe only QUAD-Client procedures.

| Layer | ID | Use when | Default outcome |
| --- | --- | --- | --- |
| Journey | [`quad-client-installation`](quad-client-installation/SKILL.md) | Preparing QUAD-Client and choosing a transport | A verified installation plan without writing agent configuration |
| Domain | [`device-target-configuration`](device-target-configuration/SKILL.md) | Discovering and validating an approved device target | A redacted target-readiness record |
| Domain | [`client-inference-validation`](client-inference-validation/SKILL.md) | Validating an approved QNN inference workflow | A reproducible inference and benchmark record |

Run client commands from `QUAD-Client/`. Keep endpoint addresses, SSH keys,
authentication values, private model paths, and generated artifacts out of
versioned evidence.
