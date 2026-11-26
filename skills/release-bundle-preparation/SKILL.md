---
name: release-bundle-preparation
description: Prepare and validate a public release bundle with a version, compatibility data, checksums, evidence, safety gates, and rollback instructions. Use when publishing or promoting an incubating, preview, stable, or LTS project release.
version: 1.0.0
---

# Release Bundle Preparation

1. Choose a SemVer version and release channel according to
   `references/DELIVERY_MODELS.md`; do not overwrite an existing release artifact.
2. Create `release-bundle.json` from `resources/release-bundle.example.json` and include
   only public source and legally distributable assets.
3. Add exact compatibility, included shared and project-local skill IDs,
   validation evidence, approval gates, and rollback instructions.
4. Produce SHA-256 values for every published binary or archive.
5. Run `py -3 scripts/validate_release_bundle.py <release-bundle.json>` before release.
6. Publish the source tag, manifest, release notes, and public support path as
   one immutable release.

Block release promotion if the manifest lacks evidence, the license status is
unknown, an asset cannot be redistributed, or the documented workflow requires
an internal account or private network.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Linux (or WSL), Windows, macOS |

References: [Delivery models](https://github.com/sreddygu/DevRel/blob/main/skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](https://github.com/sreddygu/DevRel/blob/main/docs/skills-hub-compatibility-values.md).

## Example prompts

- Package my project as a public release with checksums and rollback steps
- Promote my preview release to stable and validate the release metadata
- Create a release-bundle.json for v1.0.0 of my starter kit and run the validator
- Check that my release bundle has a version, license, evidence and compatibility table
- What do I need before I publish my sample as a stable release?
- Generate SHA-256 checksums for every archive in my release
- Which release channel (incubating, preview, stable, LTS) fits my project today?

<!-- skills-hub:end -->
