"""Validate the qli_dogfooding toolkit and print its workflow catalog."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


WORKFLOW_MODULES = (
    "qli_device_lifecycle_apps.py",
    "qli_network_apps.py",
    "qli_media_storage_apps.py",
    "qli_ai_apps.py",
    "qli_audio_event_agent.py",
    "qli_device_health_agent.py",
    "qli_a2a_agent.py",
    "qli_debug_deploy_apps.py",
)

REQUIRED_AUTOMATION = (
    "audit_sources.py",
    "build_qli_device_summary.py",
    "create_qli_device_report.ps1",
    "create_qli_device_workbook.py",
    "format_workbook.ps1",
    "qli_device_validation.py",
    "test_uvc_quirks.sh",
)

REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "skill.yaml",
    "README.md",
    "references/assessment-playbook.md",
    "references/assessment-results-schema.md",
    "references/framework-integration.md",
    "references/status-and-evidence.md",
    "references/workflow-map.md",
)

SYNAPSE_SKILLS = {
    "host-environment-validation": "domain",
    "device-identity-discovery": "domain",
    "baseline-evidence-collection": "domain",
    "ai-model-execution": "domain",
    "diagnostic-log-collection": "domain",
    "device-connectivity-validation": "mcp-tool",
    "ai-inference-benchmark": "mcp-tool",
    "readiness-report-generation": "mcp-tool",
    "qli-linux-domain": "context",
    "developer-readiness-assessment": "journey",
    "qli-readiness-agent": "agent",
}

SYNAPSE_REQUIRED_FILES = {
    "qli-linux-domain": ("references/domain-support.md",),
}

SYNAPSE_REQUIRED_MANIFEST_FIELDS = (
    "schema_version:",
    "version:",
    "entrypoint:",
    "synapse:",
    "domain:",
    "owner:",
    "visibility:",
    "maturity:",
    "authoritative_docs:",
    "safety:",
    # Publishing contract and review gates from the Synapse skill standards deck.
    "backup_owner:",
    "review_cadence:",
    "supported_versions:",
    "dependencies:",
    "developer_journey_stage:",
    "feedback_channel:",
    "deprecation_path:",
    "authority:",
    "approved_tools:",
    "endpoints:",
    "provenance:",
    "control:",
    "consequential_actions:",
    "recovery_and_rollback:",
    "review_gates:",
)

# Executable skills and MCP tools must also declare an operation contract.
SYNAPSE_CONTRACT_FIELDS = (
    "contract:",
    "inputs:",
    "outputs:",
    "validation:",
    "failure_behavior:",
    "negative_scope:",
    "known_failure_modes:",
    "two_config_evidence:",
)
CONTRACT_EXEMPT_LAYERS = ("context", "journey")

EXPECTED_UNIQUE_WORKFLOWS = 51


def default_project_root() -> Path:
    """Return the toolkit root relative to this skill script."""
    return Path(__file__).resolve().parents[3]


def list_workflows(module: Path) -> tuple[list[str], str | None]:
    """Run one module discovery interface and return workflows or an error."""
    completed = subprocess.run(
        [sys.executable, str(module), "--list-workflows"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        return [], f"return code {completed.returncode}: {detail}"
    workflows = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return workflows, None


def inspect_synapse_skills(project_root: Path) -> tuple[dict, list[str], dict]:
    """Validate the declared Synapse skill catalog without a YAML dependency."""
    skills_dir = project_root / "skills"
    catalog = {}
    missing = []
    errors = {}

    for skill_id, expected_layer in SYNAPSE_SKILLS.items():
        skill_dir = skills_dir / skill_id
        manifest = skill_dir / "skill.yaml"
        instructions = skill_dir / "SKILL.md"
        catalog[skill_id] = {"expected_layer": expected_layer}

        for path in (manifest, instructions):
            if not path.is_file():
                missing.append(str(path))

        for relative in SYNAPSE_REQUIRED_FILES.get(skill_id, ()):
            path = skill_dir / relative
            if not path.is_file():
                missing.append(str(path))

        if not manifest.is_file():
            continue

        text = manifest.read_text(encoding="utf-8")
        skill_errors = []
        for field in SYNAPSE_REQUIRED_MANIFEST_FIELDS:
            if field not in text:
                skill_errors.append(f"missing manifest field {field}")
        if expected_layer not in CONTRACT_EXEMPT_LAYERS:
            for field in SYNAPSE_CONTRACT_FIELDS:
                if field not in text:
                    skill_errors.append(f"missing contract field {field}")
        if f'id: "{skill_id}"' not in text:
            skill_errors.append("manifest ID does not match directory")
        if not re.search(rf'^  layer: "{re.escape(expected_layer)}"$', text, re.MULTILINE):
            skill_errors.append(f"expected synapse layer {expected_layer}")
        if skill_errors:
            errors[skill_id] = skill_errors
        else:
            catalog[skill_id]["layer"] = expected_layer

    return catalog, missing, errors


def inspect(project_root: Path) -> dict:
    """Inspect required files and collect module workflow declarations."""
    source_dir = project_root / "src"
    automation_dir = project_root / "scripts"
    skill_dir = project_root / "skills" / "developer-readiness-assessment"
    missing = []
    errors = {}
    modules = {}

    for name in WORKFLOW_MODULES:
        path = source_dir / name
        if not path.is_file():
            missing.append(str(path))
            continue
        workflows, error = list_workflows(path)
        modules[name] = workflows
        if error:
            errors[name] = error

    for name in REQUIRED_AUTOMATION:
        path = automation_dir / name
        if not path.is_file():
            missing.append(str(path))

    for relative in REQUIRED_SKILL_FILES:
        path = skill_dir / relative
        if not path.is_file():
            missing.append(str(path))

    catalog_path = project_root / "skills" / "README.md"
    context_path = project_root / "CONTEXT.md"
    adr_path = project_root / "docs" / "adr" / "0001-adopt-synapse-skill-layers.md"
    for path in (catalog_path, context_path, adr_path):
        if not path.is_file():
            missing.append(str(path))

    synapse_skills, synapse_missing, synapse_errors = inspect_synapse_skills(project_root)
    missing.extend(synapse_missing)

    unique_workflows = []
    seen = set()
    for workflows in modules.values():
        for workflow in workflows:
            if workflow not in seen:
                seen.add(workflow)
                unique_workflows.append(workflow)

    return {
        "project_root": str(project_root),
        "modules": modules,
        "module_entries": sum(len(items) for items in modules.values()),
        "unique_workflows": unique_workflows,
        "unique_workflow_count": len(unique_workflows),
        "expected_unique_workflow_count": EXPECTED_UNIQUE_WORKFLOWS,
        "missing": missing,
        "errors": errors,
        "synapse_skills": synapse_skills,
        "synapse_errors": synapse_errors,
        "ok": not missing
        and not errors
        and not synapse_errors
        and len(unique_workflows) == EXPECTED_UNIQUE_WORKFLOWS,
    }


def main() -> int:
    """Parse arguments, inspect the toolkit, and report validation results."""
    parser = argparse.ArgumentParser(
        description="Validate qli_dogfooding files and discover its workflow catalog."
    )
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = inspect(args.project_root.resolve())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Project root: {result['project_root']}")
        print(f"Module entries: {result['module_entries']}")
        print(
            "Unique workflows: "
            f"{result['unique_workflow_count']}/{result['expected_unique_workflow_count']}"
        )
        for name, workflows in result["modules"].items():
            print(f"- {name}: {len(workflows)}")
        for path in result["missing"]:
            print(f"MISSING: {path}")
        for name, error in result["errors"].items():
            print(f"ERROR: {name}: {error}")
        print(f"Synapse skills: {len(result['synapse_skills'])}/{len(SYNAPSE_SKILLS)}")
        for name, details in result["synapse_skills"].items():
            layer = details.get("layer", "invalid")
            print(f"- {name}: {layer}")
        for name, errors in result["synapse_errors"].items():
            print(f"SYNAPSE ERROR: {name}: {'; '.join(errors)}")
        print("Toolkit validation: " + ("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
