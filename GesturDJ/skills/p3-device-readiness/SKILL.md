---
name: p3-device-readiness
description: Establish whether a publicly obtainable hardware target is ready for a project’s documented P3 workflow without changing device state. Use before installing a runtime, deploying a model, recording sensors, or claiming device support.
version: 1.0.0
---

# P3 Device Readiness

1. Confirm that the developer owns or controls the device and has a public
   setup path. Record device model, OS/image version, host connection method,
   runtime version, and available storage.
2. Run only read-only discovery and project-documented smoke checks by default.
3. Compare the observed environment with the project compatibility declaration.
   Name mismatches and unsupported targets; do not silently substitute another
   device’s result.
4. Require explicit approval before device package installation, model copying,
   camera or microphone access, sensor recording, flashing, or network changes.
5. Write a dated, redacted readiness record and link it from validation evidence.

On a failed check, stop and report the failed condition and recovery path. Never
claim device support solely because a host-side workflow completed.
