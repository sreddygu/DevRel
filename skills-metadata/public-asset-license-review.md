---
name: public-asset-license-review
description: "Review the licenses of source code, models, datasets, binaries and documents before a project is distributed publicly, mark each as redistributable, download-by-user, evaluation-only or prohibited, and flag anything that cannot be shared."
---

# Public Asset License Review

Review the licenses of source code, models, datasets, binaries and documents before a project is distributed publicly, mark each as redistributable, download-by-user, evaluation-only or prohibited, and flag anything that cannot be shared.

## Catalog

- **Level:** Academy shared skill
- **Owner:** `sreddygu`
- **Category:** `general`
- **Version:** `1.0.0`
- **Agents:** `claude`, `codex`, `cursor`
- **Tags:** `license`, `assets`, `distribution`, `public`, `asset`, `review`, `open-source`, `release`, `shared-skills`
- **License:** `Apache-2.0`
- **Compatibility:** host OS `linux`, `windows`, `macos`
- **References:** [Delivery models](../skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](../docs/skills-hub-compatibility-values.md)
- **Hub triggers:** none
- **Manifest:** [`skills.json`](../skills.json)
- **Procedure:** [`SKILL.md`](../skills/public-asset-license-review/SKILL.md)

## Use Cases

- Can I publish this model checkpoint with my project?
- Review the licenses of my new Python dependency before I add it
- List every asset in my release bundle with its source, checksum and license
- Check which files in this repo must not be redistributed
- Which assets should users download themselves instead of me bundling them?
- Is this dataset allowed in a public sample, or is it evaluation-only?
- Write the license acknowledgement users must accept before downloading the model
