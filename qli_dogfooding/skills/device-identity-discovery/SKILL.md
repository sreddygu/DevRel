---
name: device-identity-discovery
description: "Identify a connected Qualcomm Linux (QLI) device (board, SoC, image and OS version) before choosing device-specific work."
version: 1.0.0
---

# Device Identity Discovery

Use this skill to establish the target identity before selecting device-specific
workflows.

1. Resolve the toolkit root two directories above this skill.
2. Run `python src/qli_device_lifecycle_apps.py identity` in the intended target
   context.
3. Capture the observed identity and compare it with the requested device label.
4. Stop and request clarification if the observed target differs from the
   requested target.

This skill is complete only when the identity observation is recorded. It does
not establish remote connectivity or validate an installed image.
