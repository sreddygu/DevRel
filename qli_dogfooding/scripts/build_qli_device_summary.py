"""Build a device-neutral dogfooding summary from verified evidence.

Baseline evidence is used only for checks it proves directly. Deep workflow
statuses, findings, metadata, and artifact descriptions come from an optional
assessment-results JSON file so results from one device are never copied to
another target.
"""

import argparse
import getpass
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path


STATUSES = (
    "Completed",
    "User Completed",
    "Partial",
    "Blocked",
    "Not Tested",
    "Not Applicable",
)

PERSONA_NAMES = (
    "Team Lead Recovery",
    "Embedded Developer New to Device",
    "First Time User",
    "Inherited Device",
    "Iteration Speed",
    "New WiFi Network",
    "Upgrade QLI",
    "Update QLI Package",
    "Run Samples",
    "Early AI Developer",
    "Advanced AI Developer",
)

WORKFLOWS = (
    ("Device Identity Inspector", "Inherited Device"),
    ("First Boot Experience", "First Time User"),
    ("Host Environment Validation", "Embedded Developer New to Device"),
    ("Device Connectivity Check", "Embedded Developer New to Device"),
    ("Device Recovery Discovery", "Team Lead Recovery"),
    ("Flash Latest QLI Build", "Upgrade QLI"),
    ("Verify Flash Succeeded", "First Time User"),
    ("Identify Installed Version", "Inherited Device"),
    ("Roll Forward from Old Image", "Upgrade QLI"),
    ("Recover Misconfigured Device", "Team Lead Recovery"),
    ("Join New WiFi Network", "New WiFi Network"),
    ("Switch WiFi Networks", "New WiFi Network"),
    ("Configure Static IP", "New WiFi Network"),
    ("SSH to Device", "Embedded Developer New to Device"),
    ("Transfer File to Device", "Embedded Developer New to Device"),
    ("Speaker Beep", "First Time User"),
    ("Multi Tone Generator", "First Time User"),
    ("Play WAV File", "First Time User"),
    ("Record Audio Sample", "First Time User"),
    ("Audio Loopback Test", "First Time User"),
    ("Capture Single Image", "First Time User"),
    ("Save Timestamped Photos", "First Time User"),
    ("Capture Burst Images", "First Time User"),
    ("Display Camera Metadata", "Early AI Developer"),
    ("Motion Snapshot Trigger", "Early AI Developer"),
    ("Create Log File", "First Time User"),
    ("Read Configuration File", "First Time User"),
    ("Store Photo to Disk", "First Time User"),
    ("Storage Capacity Reporter", "First Time User"),
    ("Rotate Log Files", "First Time User"),
    ("Download Model from AI Hub", "Early AI Developer"),
    ("Run Image Classification", "Early AI Developer"),
    ("Top 5 Predictions Viewer", "Early AI Developer"),
    ("Dog vs Non Dog Detector", "Early AI Developer"),
    ("Object Detection on Camera Image", "Early AI Developer"),
    ("Compare Two AI Models", "Early AI Developer"),
    ("Inference Timing Benchmark", "Early AI Developer"),
    ("Confidence Score Analyzer", "Early AI Developer"),
    ("AI Powered Device Q&A", "Advanced AI Developer"),
    ("Camera Observation Agent", "Advanced AI Developer"),
    ("Audio Event Agent", "Advanced AI Developer"),
    ("Device Health Agent", "Advanced AI Developer"),
    ("Remote Debug Hello World", "Iteration Speed"),
    ("Breakpoint Validation", "Iteration Speed"),
    ("Crash Investigation", "Iteration Speed"),
    ("Log Based Diagnostics", "Inherited Device"),
    ("Deploy Hello World", "Iteration Speed"),
    ("Deploy Updated Build", "Iteration Speed"),
    ("Deploy to Second Device", "Iteration Speed"),
    ("Clean Build Deploy Verify", "Iteration Speed"),
    ("On-Device A2A Device Health Agent", "Advanced AI Developer"),
)

WORKFLOW_CATEGORIES = (
    ("Device Setup",) * 5
    + ("Flashing",) * 5
    + ("Connectivity",) * 5
    + ("Audio",) * 5
    + ("Camera",) * 5
    + ("Storage",) * 5
    + ("AI",) * 8
    + ("Agentic AI",) * 4
    + ("Debugging",) * 4
    + ("Deployment",) * 4
    + ("Agentic AI",)
)


def read_json(path: Path) -> dict:
    """Read a JSON object from a UTF-8 file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def make_default_apps() -> list[dict]:
    """Create the canonical workflow list with conservative defaults."""
    return [
        {
            "name": name,
            "status": "Not Tested",
            "finding": "No verified result was supplied for this workflow.",
            "persona": persona,
            "category": category,
        }
        for (name, persona), category in zip(WORKFLOWS, WORKFLOW_CATEGORIES, strict=True)
    ]


def check_succeeded(check: object) -> bool:
    """Return whether a baseline check has a successful return code."""
    return isinstance(check, dict) and check.get("returncode") == 0


def extract_qli_version(identity_output: str) -> str | None:
    """Extract a release identifier from standard os-release output."""
    match = re.search(r'^VERSION_ID=["\']?([^"\'\r\n]+)', identity_output, re.MULTILINE)
    return match.group(1).strip() if match else None


def set_app_result(apps_by_name: dict[str, dict], name: str, status: str, finding: str) -> None:
    """Set one workflow result after validating its status."""
    if status not in STATUSES:
        raise ValueError(f"Invalid status for {name}: {status}")
    apps_by_name[name]["status"] = status
    apps_by_name[name]["finding"] = finding


def infer_baseline_results(apps_by_name: dict[str, dict], baseline: dict) -> dict:
    """Apply only results directly proven by the baseline collector."""
    checks = baseline.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError("Baseline field 'checks' must be a JSON object")

    identity = checks.get("identity", {})
    identity_output = identity.get("stdout", "") if isinstance(identity, dict) else ""
    qli_version = extract_qli_version(identity_output)
    if check_succeeded(identity) and identity_output.strip():
        set_app_result(
            apps_by_name,
            "Device Identity Inspector",
            "Completed",
            "Baseline evidence captured hostname, kernel, architecture, and operating-system identity.",
        )
        if qli_version:
            set_app_result(
                apps_by_name,
                "Identify Installed Version",
                "Completed",
                f"Baseline os-release evidence reported VERSION_ID={qli_version}.",
            )

    network = checks.get("network", {})
    if check_succeeded(network):
        set_app_result(
            apps_by_name,
            "Device Connectivity Check",
            "Completed",
            "The baseline collector completed over SSH and captured live addresses and routes.",
        )
        set_app_result(
            apps_by_name,
            "SSH to Device",
            "Completed",
            "Remote baseline commands completed successfully over SSH.",
        )

    transfer = checks.get("file_transfer", {})
    if isinstance(transfer, dict):
        expected_hash = transfer.get("expected_sha256")
        copy_result = transfer.get("copy", {})
        verify_result = transfer.get("verify_and_cleanup", {})
        verify_output = verify_result.get("stdout", "") if isinstance(verify_result, dict) else ""
        if (
            expected_hash
            and check_succeeded(copy_result)
            and check_succeeded(verify_result)
            and expected_hash in verify_output
        ):
            set_app_result(
                apps_by_name,
                "Transfer File to Device",
                "Completed",
                "The baseline SCP probe matched its SHA-256 hash and removed the remote temporary file.",
            )

    deployment = checks.get("deployment", {})
    if check_succeeded(deployment):
        deployment_finding = (
            "The baseline deployment probe created, ran, updated, syntax-checked, and removed a temporary Python application."
        )
        for name in (
            "Deploy Hello World",
            "Deploy Updated Build",
            "Clean Build Deploy Verify",
        ):
            set_app_result(apps_by_name, name, "Completed", deployment_finding)

    return {"qli_version": qli_version}


def apply_app_overrides(apps_by_name: dict[str, dict], overrides: object) -> None:
    """Validate and apply explicit deep-workflow results."""
    if overrides is None:
        return
    if not isinstance(overrides, dict):
        raise ValueError("Results field 'apps' must be a JSON object")
    unknown_apps = sorted(set(overrides) - set(apps_by_name))
    if unknown_apps:
        raise ValueError(f"Unknown workflow name(s): {', '.join(unknown_apps)}")

    allowed_fields = {"status", "finding", "persona"}
    for name, override in overrides.items():
        if not isinstance(override, dict):
            raise ValueError(f"Workflow override for {name} must be a JSON object")
        unknown_fields = sorted(set(override) - allowed_fields)
        if unknown_fields:
            raise ValueError(f"Unknown field(s) for {name}: {', '.join(unknown_fields)}")
        status = override.get("status", apps_by_name[name]["status"])
        if status not in STATUSES:
            raise ValueError(f"Invalid status for {name}: {status}")
        if (
            "status" in override
            and status != "Not Tested"
            and not str(override.get("finding", "")).strip()
        ):
            raise ValueError(f"Workflow {name} requires a finding for status {status}")
        finding = override.get("finding", apps_by_name[name]["finding"])
        if status != "Not Tested" and not str(finding).strip():
            raise ValueError(f"Workflow {name} requires a finding for status {status}")
        persona = override.get("persona", apps_by_name[name]["persona"])
        if persona not in PERSONA_NAMES:
            raise ValueError(f"Unknown persona for {name}: {persona}")
        apps_by_name[name].update(
            status=status,
            finding=str(finding).strip(),
            persona=persona,
        )


def derive_persona_status(statuses: list[str]) -> str:
    """Derive a conservative persona status from its mapped workflows."""
    if not statuses or all(status == "Not Tested" for status in statuses):
        return "Not Tested"
    if all(status == "Not Applicable" for status in statuses):
        return "Not Applicable"
    if all(status in {"Completed", "User Completed"} for status in statuses):
        return "Completed" if "Completed" in statuses else "User Completed"
    if "Partial" in statuses:
        return "Partial"
    if "Blocked" in statuses and not any(
        status in {"Completed", "User Completed"} for status in statuses
    ):
        return "Blocked"
    return "Partial"


def build_personas(apps: list[dict], overrides: object) -> list[dict]:
    """Build persona results and apply optional explicit overrides."""
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError("Results field 'personas' must be a JSON object")
    persona_overrides = overrides or {}
    unknown_personas = sorted(set(persona_overrides) - set(PERSONA_NAMES))
    if unknown_personas:
        raise ValueError(f"Unknown persona name(s): {', '.join(unknown_personas)}")

    personas = []
    for persona_name in PERSONA_NAMES:
        statuses = [app["status"] for app in apps if app["persona"] == persona_name]
        counts = Counter(statuses)
        status = derive_persona_status(statuses)
        finding = (
            "; ".join(f"{counts[item]} {item}" for item in STATUSES if counts[item]) + "."
            if statuses
            else "No workflows are mapped to this persona in the canonical activity list."
        )
        override = persona_overrides.get(persona_name, {})
        if not isinstance(override, dict):
            raise ValueError(f"Persona override for {persona_name} must be a JSON object")
        unknown_fields = sorted(set(override) - {"status", "finding"})
        if unknown_fields:
            raise ValueError(
                f"Unknown field(s) for persona {persona_name}: {', '.join(unknown_fields)}"
            )
        status = override.get("status", status)
        if (
            "status" in override
            and status != "Not Tested"
            and not str(override.get("finding", "")).strip()
        ):
            raise ValueError(
                f"Persona {persona_name} requires a finding for status {status}"
            )
        finding = str(override.get("finding", finding)).strip()
        if status not in STATUSES:
            raise ValueError(f"Invalid status for persona {persona_name}: {status}")
        if status != "Not Tested" and not finding:
            raise ValueError(f"Persona {persona_name} requires a finding for status {status}")
        personas.append({"name": persona_name, "status": status, "finding": finding})
    return personas


def validate_findings(findings: object) -> list[dict]:
    """Validate friction findings without inventing device-specific claims."""
    if findings is None:
        return []
    if not isinstance(findings, list):
        raise ValueError("Results field 'findings' must be a JSON array")
    normalized = []
    required_fields = ("area", "severity", "description", "workaround")
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise ValueError(f"Finding {index} must be a JSON object")
        missing = [field for field in required_fields if field not in finding]
        if missing:
            raise ValueError(f"Finding {index} is missing: {', '.join(missing)}")
        normalized.append({field: str(finding[field]).strip() for field in required_fields})
    return normalized


def build_evidence(args: argparse.Namespace, results: dict) -> dict:
    """Build a report-friendly evidence inventory."""
    evidence = {
        "baseline": str(args.baseline),
        "artifacts": [
            {
                "artifact": str(args.baseline),
                "purpose": "Non-destructive baseline identity, network, transfer, and deployment evidence.",
            }
        ],
    }
    if args.deep_evidence:
        evidence["deep_directory"] = str(args.deep_evidence)
        evidence["artifacts"].append(
            {
                "artifact": str(args.deep_evidence),
                "purpose": "Directory containing explicitly reviewed deep-workflow evidence.",
            }
        )

    supplied_evidence = results.get("evidence", {})
    if supplied_evidence is None:
        supplied_evidence = {}
    if not isinstance(supplied_evidence, dict):
        raise ValueError("Results field 'evidence' must be a JSON object")
    artifacts = supplied_evidence.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("Results field 'evidence.artifacts' must be a JSON array")
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            raise ValueError(f"Evidence artifact {index} must be a JSON object")
        artifact_name = artifact.get("artifact", artifact.get("path", artifact.get("name")))
        purpose = artifact.get("purpose")
        if not artifact_name or not purpose:
            raise ValueError(f"Evidence artifact {index} requires artifact/path/name and purpose")
        evidence["artifacts"].append(
            {"artifact": str(artifact_name), "purpose": str(purpose)}
        )
    return evidence


def main() -> None:
    """Parse evidence paths and write the normalized device summary JSON."""
    parser = argparse.ArgumentParser(description="Build a reusable QLI dogfooding device summary.")
    parser.add_argument("--device", required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--ip-address", required=True)
    parser.add_argument("--owner", default=getpass.getuser())
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--deep-evidence", type=Path)
    parser.add_argument(
        "--results",
        type=Path,
        help="Optional JSON file containing verified workflow, persona, metadata, finding, and evidence overrides.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = read_json(args.baseline)
    results = read_json(args.results) if args.results else {}
    metadata = results.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Results field 'metadata' must be a JSON object")

    apps = make_default_apps()
    apps_by_name = {app["name"]: app for app in apps}
    inferred = infer_baseline_results(apps_by_name, baseline)
    apply_app_overrides(apps_by_name, results.get("apps"))
    personas = build_personas(apps, results.get("personas"))
    counts = Counter(app["status"] for app in apps)
    status_counts = {status: counts[status] for status in STATUSES}
    qli_version = metadata.get("qli_version", inferred.get("qli_version") or "Not reported")

    template_replacements = results.get("template_replacements", {})
    if not isinstance(template_replacements, dict):
        raise ValueError("Results field 'template_replacements' must be a JSON object")
    if any(not str(key) for key in template_replacements):
        raise ValueError("Template replacement source text cannot be empty")

    summary = {
        "device": args.device,
        "hostname": args.hostname,
        "ip_address": args.ip_address,
        "owner": args.owner,
        "host_os": metadata.get("host_os", "Not provided"),
        "qli_version": str(qli_version),
        "report_date": metadata.get("report_date", date.today().isoformat()),
        "captured_at_utc": baseline.get("captured_at_utc"),
        "device_display": metadata.get("device_display", f"{args.device} / {args.hostname}"),
        "initial_state": metadata.get(
            "initial_state",
            "Baseline evidence collected; unverified workflows remain Not Tested.",
        ),
        "inventory_status": metadata.get("inventory_status", "In Use"),
        "workflow_count": len(apps),
        "status_counts": status_counts,
        "personas": personas,
        "apps": apps,
        "findings": validate_findings(results.get("findings")),
        "evidence": build_evidence(args, results),
        "template_replacements": {
            str(key): str(value) for key, value in template_replacements.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
