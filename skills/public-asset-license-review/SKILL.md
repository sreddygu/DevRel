---
name: public-asset-license-review
description: Review source, model, data, binary, and documentation assets before public distribution. Use when adding a dependency, model checkpoint, dataset, generated artifact, or downloadable release asset.
version: 1.0.0
---

# Public Asset and License Review

1. Inventory each asset’s source, version, checksum, and license or terms.
2. Mark whether the asset may be redistributed, must be downloaded by the
   developer, is evaluation-only, or is prohibited from the public bundle.
3. Keep proprietary SDKs, private certificates, credentials, internal builds,
   and restricted weights out of the repository and release artifacts.
4. For developer-downloaded assets, publish public retrieval instructions,
   checksum verification, and any license acknowledgement required before use.
5. Add the final asset decision to the release bundle and project evidence.

If terms conflict or are unclear, stop distribution and label the asset as
unresolved. Do not infer redistribution rights from public availability.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Linux (or WSL), Windows, macOS |

References: [Delivery models](https://github.com/sreddygu/DevRel/blob/main/skills/project-onboarding/references/DELIVERY_MODELS.md), [Skills Hub compatibility values](https://github.com/sreddygu/DevRel/blob/main/docs/skills-hub-compatibility-values.md).

## Example prompts

- Can I publish this model checkpoint with my project?
- Review the licenses of my new Python dependency before I add it
- List every asset in my release bundle with its source, checksum and license
- Check which files in this repo must not be redistributed
- Which assets should users download themselves instead of me bundling them?
- Is this dataset allowed in a public sample, or is it evaluation-only?
- Write the license acknowledgement users must accept before downloading the model

<!-- skills-hub:end -->
