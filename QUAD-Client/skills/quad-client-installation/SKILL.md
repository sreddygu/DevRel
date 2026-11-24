---
name: quad-client-installation
description: "Install and validate the QUAD client (quad-mcp-client) and choose how it reaches the QUAD server (hosted URL, SSH or local), without changing MCP settings by default."
version: 0.1.0
---

# QUAD-Client Installation

Prepare QUAD-Client and choose an MCP transport without changing an agent or
IDE configuration by default.

1. Work from `QUAD-Client` with Python 3.10 or later.
2. Install the client only after approval: `python -m pip install -e ".[dev]"`.
3. Select one transport: `stdio-local`, `stdio-ssh`, or `sse-http`.
4. Generate a read-only configuration preview with `quad-client preview
   --transport <transport>` plus only runtime-supplied settings.
5. Verify the selected transport with `quad-client connect-test <transport>`.
6. Record client version, selected transport, redacted preview, probe outcome,
   and any unmet prerequisites in a dated evidence record.

`quad-client install` writes client configuration and copies bundled skills, so
it requires explicit approval. Do not use `--force`, write settings files, or
record private endpoint or credential values by default.
