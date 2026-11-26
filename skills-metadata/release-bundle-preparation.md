---
name: release-bundle-preparation
description: "Prepare and validate a public release bundle for a sample project: semantic version, release channel, compatibility data, validation evidence, SHA-256 checksums, approval gates and rollback instructions, checked with a bundled validator script."
---

# Public Release Bundle Preparation

Prepare and validate a public release bundle for a sample project: semantic version, release channel, compatibility data, validation evidence, SHA-256 checksums, approval gates and rollback instructions, checked with a bundled validator script.

## Catalog

- **Level:** Academy shared skill
- **Owner:** `sreddygu`
- **Category:** `devtools`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `release`, `bundle`, `semver`, `preparation`, `open-source`, `shared-skills`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `linux`, `windows`, `macos`
- **References:** [Delivery models](../skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](../docs/skills-hub-compatibility-values.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/release-bundle-preparation/SKILL.md)

## Use Cases

- Package my project as a public release with checksums and rollback steps
- Promote my preview release to stable and validate the release metadata
- Create a release-bundle.json for v1.0.0 of my starter kit and run the validator
- Check that my release bundle has a version, license, evidence and compatibility table
- What do I need before I publish my sample as a stable release?
- Generate SHA-256 checksums for every archive in my release
- Which release channel (incubating, preview, stable, LTS) fits my project today?
