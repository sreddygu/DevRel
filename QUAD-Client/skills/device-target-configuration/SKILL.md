---
name: device-target-configuration
description: "Discover and document an approved device target for the QUAD client (IQ-9075 board over SSH, Android over adb) without changing the device by default."
version: 0.1.0
---

# QUAD-Client Device Target Configuration

Discover and validate an approved target without reconfiguring it. This skill
records target facts and a proposed workload placement; it does not make device
state changes.

1. Run `quad-client detect --local-only --json` to capture host capabilities.
2. For a target device, run `quad-client profile-device` with runtime-supplied
   connection details and an approved model reference only when remote command
   execution has been approved.
3. Use `quad-client doctor` to inspect the local workflow prerequisites.
4. Record target OS/architecture, transport, available backend, requested
   workload placement, command exit status, and unknown fields in a dated
   target-readiness record.
5. Run `python -m pytest tests/test_local/test_board_portability.py
   tests/test_local/test_profile_device_cli.py -q` before claiming support.

Do not modify network settings, device users, SDK installation, firmware,
boot configuration, or board files. Pushing a model, using SSH/ADB, and running
the `unoq` board operations require explicit approval.
