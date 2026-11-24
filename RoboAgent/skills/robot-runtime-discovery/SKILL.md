---
name: robot-runtime-discovery
description: "Inspect whether the QNN runtime and the Pi coding assistant are ready for RoboAgent on a Windows on Snapdragon PC, without changing the machine by default."
version: 0.1.0
---

# RoboAgent Runtime Discovery

Inspect the local RoboAgent runtime before starting a model or enabling tools.

1. Read `README.md`, `tools/pi/README.md`, and `REPOSITORY_STATUS.md` to identify
   the expected Gemma model, QNN environment, named pipe, and supported launcher.
2. Use `tools\pi\start-roboagent-pi.ps1` only after approval; it starts the host
   and Pi and can consume model/runtime resources.
3. Before restarting a failed host, inspect `logs\host-recovery-gemma4.log` and
   record the observed recovery error.
4. Record host OS/architecture, QNN readiness, selected profile, host status,
   and unknown fields. Keep the QNN SDK environment isolated to the launcher.
5. Stop and report missing runtime dependencies; do not alter `Path`, install a
   QNN SDK, copy models, or modify host configuration automatically.

The default is read-only inspection. Starting or restarting the persistent host
requires explicit approval.
