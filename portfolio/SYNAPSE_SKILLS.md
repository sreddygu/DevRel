# P3 Synapse Skills Enablement

This directory is a portfolio of independent developer projects. Synapse
enablement is tracked centrally so P3 developers can see both the skills that
are already usable and the next skills each project needs. A project should
only create a `skills/<skill-id>/` folder when it can provide a bounded,
evidence-backed procedure; do not add empty skill placeholders.

The machine-readable source of truth is
[`synapse-project-catalog.json`](synapse-project-catalog.json). Validate it
after updates with:

```powershell
py -3 .\portfolio\validate_synapse_catalog.py
```

P3 release lanes, bundle contents, and open-source distribution rules are in
the onboarding skill's
[`P3_DELIVERY_MODELS.md`](../skills/project-onboarding/references/P3_DELIVERY_MODELS.md).
Use the release skill's bundled schema and validator when a project moves beyond
a source skill pack.

Shared P3 procedures are in [`../skills/`](../skills/), and the project-to-profile
mapping is in [`synapse-project-catalog.json`](synapse-project-catalog.json).

## How to read the catalog

- **Enabled** means the project contains usable `SKILL.md` and `skill.yaml`
  definitions. P3 developers can discover and load these now.
- **Proposed** names the smallest reusable skills to implement next. They are
  deliberately not presented as runnable skills.
- **Context** is injected for every request in a project; it is not selected
  like a procedural skill.
- **MCP tool** is a deterministic operation invoked directly. Reuse an existing
  shared tool before building another wrapper.

## Shared Skill Profiles

Common skills are defined **once** at the portfolio level in
[Skills Hub catalog](../); do not copy them into each project's `skills/`
folder. Projects are marked with one shared profile in the registry:

| Profile | Shared skills | Apply to |
| --- | --- | --- |
| `p3-core` | `p3-project-onboarding`, `p3-evidence-and-compatibility`, `p3-release-bundle-preparation`, `p3-public-asset-license-review` | Every project. |
| `p3-device` | Every `p3-core` skill plus `p3-device-readiness` | Projects that claim a board, device, sensor, camera, microphone, accelerator, or device deployment path. |

The profile is a project-level dependency declaration. The next-skills column
below contains only domain-specific work for that project.

## Project Enablement Matrix

| Project | Current state | Shared profile | Project-specific skills to enable next |
| --- | --- | --- | --- |
| `qli_dogfooding` | **Enabled**: 11 Synapse skills | `p3-device` | Maintain the existing QLI catalog; no bootstrap work required. |
| `GesturDJ` | **Enabled**: 15 Synapse skills | `p3-device` | Maintain the existing GesturDJ catalog; no bootstrap work required. |
| `AI-Across-Devices` | Proposed | `p3-device` | `cross-device-context`, `session-handoff-journey`, `local-sync-validation` |
| `AURA` | **Enabled**: 3 Synapse skills | `p3-device` | Maintain the existing AURA catalog; no bootstrap work required. |
| `Developer-Journey` | Proposed | `p3-core` | `developer-journey-mapping`, `experience-evidence-review`, `journey-report-generation` |
| `Edge-AI-for-Everyone` | Proposed | `p3-device` | `edge-ai-environment-setup`, `model-path-selection`, `edge-demo-validation` |
| `EdgeAgent` | **Enabled**: 3 Synapse skills | `p3-device` | Maintain the existing EdgeAgent catalog; no bootstrap work required. |
| `LLM` | Proposed | `p3-device` | `local-llm-runtime-setup`, `model-inference-validation`, `npu-inference-benchmark` |
| `mojo-max-int` | Proposed | `p3-core` | `mojo-project-setup`, `kernel-performance-validation`, `build-artifact-verification` |
| `Multiverse-of-Developers` | Proposed | `p3-core` | `developer-persona-mapping`, `experience-composition`, `portfolio-demo-validation` |
| `QUAD-Client` | **Enabled**: 3 Synapse skills | `p3-device` | Maintain the existing QUAD-Client catalog; no bootstrap work required. |
| `RoboAgent` | **Enabled**: 3 Synapse skills | `p3-device` | Maintain the existing RoboAgent catalog; no bootstrap work required. |
| `sinewave` | Proposed | `p3-core` | `audio-signal-generation`, `waveform-output-validation` |
| `VSaaS` | **Enabled**: 3 Synapse skills | `p3-device` | Maintain the existing VSaaS catalog; no bootstrap work required. |
| `wake_word` | Proposed | `p3-device` | `wake-word-data-capture`, `keyword-model-training`, `onnx-streaming-validation` |
| `Wearable-AI` | Proposed | `p3-device` | `wearable-sensing-context`, `tiny-model-gating`, `hub-handoff-validation` |
| `XR-Experiences` | Proposed | `p3-device` | `spatial-scene-pipeline`, `grounded-xr-assistance`, `xr-proxy-validation` |

## Standard Project Shape

When a proposed skill is ready, add it independently inside its project:

```text
<project>/
  SYNAPSE_SKILLS.md                 # project catalog and routing rules
  skills/
    <skill-id>/
      SKILL.md                      # concise, triggerable procedure
      skill.yaml                    # Synapse metadata, ownership, safety
```

Use the QLI and GesturDJ implementations as the canonical references:

- [`qli_dogfooding/skills/README.md`](../qli_dogfooding/skills/README.md) shows
  agent, context, domain, journey, and MCP-tool layers.
- [`GesturDJ/GESTURDJ_SYNAPSE_SKILLS.md`](../GesturDJ/GESTURDJ_SYNAPSE_SKILLS.md)
  shows a project catalog with P3 self-service boundaries and validation.

## Enablement Gate

Before changing any entry from `proposed` to `enabled`, the project must have:

1. A named owner and a documented maintenance/review cadence.
2. A bounded trigger, expected inputs/outputs, and explicit negative scope.
3. Non-destructive defaults and approval gates for consequential actions.
4. A reproducible validation command or evidence artifact.
5. A `SKILL.md` plus `skill.yaml` in the project-local `skills/` directory.

This keeps the catalog honest: P3 developers can discover real capabilities
without confusing design ideas with deployable automation.
