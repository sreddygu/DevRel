# Qualcomm Academy

This workspace collects hands-on Qualcomm developer-relations projects, learning journeys, and reusable delivery resources for edge AI development.

## Featured Projects

| Project | Focus |
| --- | --- |
| [AURA](AURA/) | Autonomous, responsive on-device agent workflows. |
| [EdgeAgent](EdgeAgent/) | Portable tool-using LLM agent for local and edge devices. |
| [GesturDJ](GesturDJ/) | Gesture-controlled music and generative-audio experiences. |
| [LLM](LLM/) | GGUF and `llama.cpp` workflows for UNOQ devices. |
| [mojo-max-int](mojo-max-int/) | Mojo examples and deployment targets. |
| [QUAD-Client](QUAD-Client/) | Qualcomm Unified AI Developer client and samples. |
| [RoboAgent](RoboAgent/) | ExecuTorch QNN playground for Windows on Snapdragon. |
| [VSaaS](VSaaS/) | Private edge video intelligence with searchable insights. |
| [wake_word](wake_word/) | `hey_dragon` keyword-spotting training and streaming demo. |

## Learning Journeys

- [AI Across Devices](AI-Across-Devices/)
- [Developer Journey](Developer-Journey/)
- [Edge AI for Everyone](Edge-AI-for-Everyone/)
- [Multiverse of Developers](Multiverse-of-Developers/)
- [Wearable AI](Wearable-AI/)
- [XR Experiences](XR-Experiences/)
- [Qualcomm Academy Intermediate Curriculum](qa-intermediate-curriculum/)

## Tooling and References

- [QLI Dogfooding](qli_dogfooding/)

## Skills Catalog

[`skills.json`](skills.json) is the Academy Skills Hub entry point. It directly
publishes the shared Academy skills and federates project catalogs that contain
published `SKILL.md` procedures. Projects without skill documents are not
listed as sources, so the catalog contains only installable, documented skills.

Each catalog level also has a sibling `skills-metadata/` directory. It contains
one concise `<skill-id>.md` discovery document per published skill, linked to
its manifest entry and `SKILL.md` procedure.

Catalog entries are generated and checked by
[`tools/skills_hub_manifest.py`](tools/skills_hub_manifest.py) from the plain-language
copy in [`tools/skills_hub_copy.json`](tools/skills_hub_copy.json). Every listed skill
must have a self-explanatory name and description (acronyms such as AURA, QUAD, NPU and
QNN expanded on first use), at least five example prompts, and declared
compatibility (devkits, target OS, host OS). The same compatibility table and
example prompts are written into every published `SKILL.md`, including the QUAD-Client
copies (the tool keeps their three byte-identical forms in sync). [`skills-synapse.json`](skills-synapse.json) is the single inventory of all listed skills
(project, manifest, metadata page and full entry), generated from the per-project
`skills.json` files so it cannot drift. Run
`python tools/skills_hub_manifest.py --check` before opening a catalog PR; it fails if the inventory is stale.

| Shared skill | Use when |
| --- | --- |
| [`project-onboarding`](skills/project-onboarding/) | Starting, reviewing, or promoting an Academy project. |
| [`evidence-and-compatibility`](skills/evidence-and-compatibility/) | Recording reproducible evidence and supported environments. |
| [`release-bundle-preparation`](skills/release-bundle-preparation/) | Preparing an incubating, preview, stable, or LTS release. |
| [`public-asset-license-review`](skills/public-asset-license-review/) | Reviewing assets before public distribution. |
| [`device-readiness`](skills/device-readiness/) | Establishing a hardware target's documented readiness. |

## Repository Guidance

Commit source code, documentation, scripts, tests, manifests, and example configuration only. Do not commit local virtual environments, downloaded models, datasets, generated outputs, live credentials, logs, or device-specific runtime state.
