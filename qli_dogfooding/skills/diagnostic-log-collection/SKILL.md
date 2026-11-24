---
name: diagnostic-log-collection
description: "Collect bounded logs and diagnostics from a Qualcomm Linux (QLI) device after a failed workflow, without changing device state."
version: 1.0.0
---

# Diagnostic Log Collection

Collect the smallest useful diagnostic window after a workflow fails or blocks.

1. Record the failed workflow, time window, and requested diagnostic scope.
2. Run `python src/qli_debug_deploy_apps.py logs` with bounded `--priority` or
   `--lines` options when needed.
3. Preserve return code and capture scope with the output.
4. Redact secrets, private endpoints, and personal data before attaching logs to
   evidence, workbooks, or reports.

This skill collects diagnostics. It does not restart services, change device
configuration, or reproduce destructive failures.
