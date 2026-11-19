---
name: p3-evidence-and-compatibility
description: Capture reproducible P3 validation evidence and declare exact host, runtime, device, and known-exclusion compatibility. Use when validating a project workflow, publishing a demo claim, or deciding whether a release can be promoted.
version: 1.0.0
---

# P3 Evidence and Compatibility

1. State the source revision, host OS, runtime versions, hardware target, and
   test date before running a workflow.
2. Run the project’s documented non-destructive validation command. Record the
   command, exit status, output location, and observable result.
3. Separate validated targets from intended or narrative targets. Name known
   exclusions and untested configurations explicitly.
4. Redact credentials, private endpoints, personal data, and raw sensor content
   before publishing evidence.
5. Publish evidence beside the project or release manifest so another P3
   developer can reproduce the same result.

Stop at the first failed gate. Preserve the failure evidence and do not infer a
pass from tool installation, source availability, or a result from another
machine.
