---
name: release-bundle-preparation
description: Prepare and validate a public P3 release bundle with a version, compatibility data, checksums, evidence, safety gates, and rollback instructions. Use when publishing or promoting an incubating, preview, stable, or LTS project release.
version: 1.0.0
---

# P3 Release Bundle Preparation

1. Choose a SemVer version and release channel according to
   `references/P3_DELIVERY_MODELS.md`; do not overwrite an existing release artifact.
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
