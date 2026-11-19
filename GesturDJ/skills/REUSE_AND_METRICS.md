# GestureDJ Reuse and Metrics

## Reuse model

GestureDJ is enabled as a P3 pilot catalog. Its project-local procedures remain
in `skills/`, while portfolio-wide policy and delivery procedures are consumed
from the `p3-device` shared profile. Do not copy a shared P3 skill into this
project.

| Reuse class | Meaning | GestureDJ examples | Next action |
| --- | --- | --- | --- |
| Portfolio shared candidate | Applicable beyond this project and should be assessed centrally | `p3-self-service-boundaries` | Compare with existing P3 safety and onboarding context before promotion. |
| Reusable candidate | A domain or deterministic capability that may serve other projects | host discovery, ONNX export/validation, NPU accuracy gate, audio latency validation | Search the portfolio catalog by `similarity_keys`; promote only after evidence on another project/configuration. |
| Project composed | Orchestrates reusable pieces for this experience | `gesturdj-build-journey` | Keep project-local. |
| Project specific/context | Encodes GestureDJ behavior or contract | live gesture mix, gesture event contract | Keep local; tag for discovery rather than cloning. |

`synapse-skill-catalog.json` is the machine-readable index. It references
`mcp-tools.yaml` as the authoritative catalog for deterministic tools. The MCP
tools must be searched before an equivalent tool is added elsewhere.

## Discovery and publishing

- Discover a skill by `applicability_tags`, `environment_tags`, and
  `similarity_keys`, then confirm its evidence and safety contract in
  `skill.yaml`.
- `p3` is an applicability tag, not a reason to create a duplicate skill.
- This catalog is **enabled-pilot**: its procedures are discoverable in P3, but
  public publication or cross-catalog exchange requires the review gates and
  licensing checks already recorded by the individual manifests.
- P1/P2/Dragon Genie catalog exchange is intentionally not assumed here. This
  index provides stable metadata for a future adapter or publishing workflow.

## Metrics baseline

Use `skill-metrics-baseline.template.json` to record observations before setting
targets. Capture one record per evaluated skill/request combination:

1. Skill ID, layer, reuse class, target environment, and request type.
2. Input/output/total tokens when the host exposes them; otherwise use `null`
   with `token_measurement_available: false`.
3. Elapsed time, tool-call count, retries, approval prompts, validation result,
   and whether existing evidence was reused.
4. Evidence path and redaction status. Never store prompts, sensor data,
   credentials, private endpoints, or raw model paths in the baseline.

No efficiency target is declared until comparable baselines exist across more
than one project or environment.
