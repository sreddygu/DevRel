# Assessment Results Schema

Use an assessment-results JSON file to record verified deep-workflow outcomes.
The summary builder infers only identity, installed version, connectivity, SSH,
file transfer, and the baseline deployment probe. Every other workflow defaults
to `Not Tested` until this file explicitly supplies a result.

## Top-Level Fields

| Field | Type | Purpose |
|---|---|---|
| `metadata` | object | Host/release/session values used in deliverables. |
| `apps` | object | Workflow overrides keyed by canonical activity name. |
| `personas` | object | Optional persona status/finding overrides. |
| `findings` | array | Evidence-backed friction and recommended actions. |
| `evidence.artifacts` | array | Artifact paths or names with their purpose. |
| `template_replacements` | object | Optional legacy-template text substitutions. |

Unknown workflow names, personas, statuses, or override fields are rejected.
Allowed statuses are `Completed`, `User Completed`, `Partial`, `Blocked`,
`Not Tested`, and `Not Applicable`.

## Example

```json
{
  "metadata": {
    "host_os": "Windows 11",
    "qli_version": "2.0",
    "initial_state": "Device booted; network already configured",
    "inventory_status": "In Use"
  },
  "apps": {
    "Capture Single Image": {
      "status": "Completed",
      "finding": "Captured a nonzero JPEG and verified its image signature."
    },
    "Configure Static IP": {
      "status": "Partial",
      "finding": "Persistent profile validation passed; activation was deferred because SSH was the only access path."
    },
    "Object Detection on Camera Image": {
      "status": "Blocked",
      "finding": "The workflow reached the model runner, which reported a missing compatible model artifact."
    }
  },
  "personas": {
    "Early AI Developer": {
      "status": "Partial",
      "finding": "Classification completed; object detection remains blocked by the missing model artifact."
    }
  },
  "findings": [
    {
      "area": "Networking",
      "severity": "Medium",
      "description": "Static-address activation would interrupt the only remote access path.",
      "workaround": "Use a serial console or approved maintenance window before activation."
    }
  ],
  "evidence": {
    "artifacts": [
      {
        "artifact": "deep/camera_capture.json",
        "purpose": "Camera command, return code, image metadata, and output hash."
      }
    ]
  },
  "template_replacements": {
    "OLD_TEMPLATE_DEVICE": "DEVICE_LABEL"
  }
}
```

## Metadata Fields

Supported metadata keys are:

- `host_os`
- `qli_version`
- `report_date` in ISO `YYYY-MM-DD` form
- `device_display`
- `initial_state`
- `inventory_status`

Omitted metadata uses conservative values such as `Not provided` or
`Not reported` rather than assuming a host, release, network, model, or device
state.

## Workflow Overrides

Each `apps` entry supports:

- `status`: one allowed status.
- `finding`: concise evidence and result; required for a verified status.
- `persona`: optional canonical persona reassignment.

Use activity names exactly as listed in the [workflow map](workflow-map.md). Do not assign
`Completed` from tool presence, a planned command, or evidence copied from
another device.

## Persona Derivation

Persona status is derived from its mapped workflow statuses. Use a `personas`
override only when the workbook persona represents scope beyond those mapped
activities, and include a finding that explains the evidence.

## Workbook Template Replacement

New templates should use `{{DEVICE}}`, `{{HOSTNAME}}`, `{{IP_ADDRESS}}`, and
`{{OWNER}}`. For an approved legacy template, add exact substitutions under
`template_replacements` or pass repeated `--replace OLD=NEW` arguments to the
workbook builder. Replacements are explicit so a prior device name or address
is never guessed.
