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
