# DevRel Runtime Snapshot

This directory is the self-contained devrelAgent runtime baseline prepared on
August 7, 2026.

- Source commit: `3cfd3dafc1c66a7808e0308888a6ab23dd07c6a7`
- Package version: `0.2.0`
- License: Apache-2.0; see `LICENSE`
- Included: Python client package, bundled skills, tests, docs, tools, scripts,
  examples, and lightweight sample source files.
- Excluded: virtual environments, caches, generated outputs, downloaded model
  artifacts, large binaries, and upstream source mirrors.

The snapshot intentionally includes the source working tree as inspected,
including local changes present in these runtime files:

- `src/devrel_client/doc_generator.py`
- `src/devrel_client/local/board/serial.py`
- `src/devrel_client/local/device_agent.py`
- `src/devrel_client/local/download.py`
- `src/devrel_client/local/render.py`

`devrel_client.py` loads only this bundled `devrel_runtime/src` tree.
