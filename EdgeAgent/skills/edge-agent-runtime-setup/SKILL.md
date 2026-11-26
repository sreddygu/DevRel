---
name: edge-agent-runtime-setup
description: "Prepare and inspect the EdgeAgent runtime (llama.cpp CPU backend or Genie NPU backend) on a Snapdragon X Elite PC or IQ8/IQ9 board without changing MCP client settings by default."
version: 0.1.0
---

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

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Dragonwing IQ-8275 EVK (`qcs8275-iq-8275-evk-pro`), Dragonwing IQ-9075 EVK (`qcs9075-iq-9075-evk`) |
| Target OS | Qualcomm Linux (`qli-2.0`, `qualcomm-linux-proprietary`) |
| Host OS | Windows, Linux (or WSL) |
| Requirements | Python 3.10+; llama.cpp server (CPU) or Genie shim over QAIRT (NPU, Snapdragon X Elite host) |

References: [EdgeAgent README](https://github.com/sreddygu/DevRel/blob/main/EdgeAgent/README.md), [Run on IQ8](https://github.com/sreddygu/DevRel/blob/main/EdgeAgent/RUN_ON_IQ8.md), [NPU quickstart](https://github.com/sreddygu/DevRel/blob/main/EdgeAgent/devrel_runtime/docs/NPU_QUICKSTART.md).

## Example prompts

- Set up EdgeAgent with a local llama.cpp server
- Point EdgeAgent at the Genie NPU backend on my Snapdragon X Elite PC
- Run the EdgeAgent doctor check and explain every failure
- Preview the MCP client configuration for the stdio-ssh transport without installing it
- Check whether EdgeAgent can reach its model server on my IQ8
- What do I need installed to run EdgeAgent on an IQ9 board?
- Which EdgeAgent transport fits my setup: stdio-local, stdio-ssh or sse-http?

<!-- skills-hub:end -->
