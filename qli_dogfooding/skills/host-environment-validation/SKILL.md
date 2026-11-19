# Host Environment Validation

Validate the host before a QLI workflow that depends on external tools.

1. Resolve the toolkit root two directories above this skill.
2. Confirm the requested tools with:
   `python src/qli_device_lifecycle_apps.py host-validate --tools <tool...>`.
3. Report each tool as available or missing. Do not install, upgrade, or change
   PATH without explicit user approval.

The result is complete only when the required tools are reported available. A
missing tool is a blocker with an install or access action, not a partial pass.
