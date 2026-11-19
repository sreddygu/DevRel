# EdgeAgent Runtime Setup

Prepare the local EdgeAgent runtime and select a transport without writing an
IDE configuration by default.

1. Work from `EdgeAgent/devrel_runtime` with Python 3.10 or later.
2. Install the project only after approval: `python -m pip install -e ".[dev]"`.
3. Run `devrel-agent doctor` and record its pass/fail checks and package
   versions. Treat missing optional device tooling as a readiness gap, not a
   reason to install it automatically.
4. Select one transport: `stdio-local`, `stdio-ssh`, or `sse-http`.
5. Preview the exact configuration with `devrel-agent preview --transport
   <transport>` plus only runtime-supplied transport options.
6. Store the command, runtime version, selected transport, and redacted preview
   in a dated evidence record.

`preview` is read-only. `devrel-agent install` writes an MCP-client
configuration and may copy bundled skills, so require explicit approval before
running it. Do not persist private keys, bearer tokens, SSH hosts, or local
model paths in evidence.
