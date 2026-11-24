---
name: qli-linux-domain
description: "Context document that states which devices and platforms the Qualcomm Linux (QLI) skills support (IQ8, IQ9 and equivalent Linux targets) and the safety and evidence rules they follow."
version: 2.0.0
---

# QLI Linux Domain

Apply this domain skill before selecting or executing a QLI device skill. It
defines the supported context for IQ8, IQ9, and equivalent Linux-based QLI
targets; it does not execute a developer outcome itself.

## Use

1. Confirm the target device, Linux image, access path, requested outcome, and
   available peripherals or AI runtime.
2. Read [domain support](references/domain-support.md) and the project
   [README](../../README.md).
3. Select a domain skill, MCP tool, or journey skill that matches the requested
   outcome. Do not select a skill solely because its command is available.
4. Apply the evidence and safety requirements from the selected skill.

## Boundaries

- Treat IQ8 and IQ9 as supported target families, not interchangeable device
  configurations. Discover actual interfaces, drivers, paths, and runtimes.
- Default to inspection and dry-run behavior.
- Require explicit approval and a recovery path before state-changing actions.
- Keep credentials, private endpoints, and personal network details out of
  evidence and generated deliverables.
