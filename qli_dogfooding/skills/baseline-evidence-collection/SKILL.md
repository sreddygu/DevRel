---
name: baseline-evidence-collection
description: "Collect read-only evidence over SSH about a Qualcomm Linux (QLI) device (OS, hardware, services) as the baseline for a readiness assessment."
version: 1.0.0
---

# Baseline Evidence Collection

Collect device/date-specific SSH evidence before deep readiness workflows.

1. Require host, device label, and an output path under
   `evidence/<device>-YYYY-MM-DD/`.
2. Run `python scripts/qli_device_validation.py --host <host> --device-label
   <label> --output <path>` and supply only approved SSH options.
3. Inspect the resulting JSON for identity, OS/build, storage, network, media,
   QNN/QAIRT, and endpoint observations.
4. Redact secrets and private endpoints before using evidence in reports.

The result is complete when the output JSON is present and command evidence can
be traced to the requested device. Tool availability alone is not evidence.
