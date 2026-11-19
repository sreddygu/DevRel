"""Validate the GesturDJ Synapse skill catalog.

Portable counterpart of qli_dogfooding's inspect_toolkit.py. That script is hardwired to the QLI skill ids and
project layout; this one reuses its required-field lists (copied 2026-11-05) with GesturDJ's own skill ids, and
adds what that script cannot do (finding F23): it checks that EVIDENCE is real, not merely that the field exists.

Checks
  structure  every skill has skill.yaml + SKILL.md, the right layer, all required fields, resolvable dependencies/docs
  evidence   each `evidence/...` path cited in two_config_evidence exists; a skill whose validation_evidence gate says
             "met" must have at least one backed entry; skills with no backed entry are listed (warning)
  tools      each tool in mcp-tools.yaml has an existing implementation and cites existing evidence

Usage: python validate_skills.py          (exit code 1 if anything is wrong; warnings do not fail)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SKILLS_DIR.parent
STANDARD_CATALOG_PATH = SKILLS_DIR / "synapse-skill-catalog.json"
METRICS_TEMPLATE_PATH = SKILLS_DIR / "skill-metrics-baseline.template.json"

# id -> expected synapse.layer. Planned (not yet written) skills are listed in README.md only.
SKILLS = {
    "gesturdj-agent": "agent",
    "gesturdj-build-journey": "journey",
    "device-and-host-discovery": "domain",
    "gesture-dataset-preparation": "domain",
    "gesture-model-training-and-evaluation": "domain",
    "model-export-and-deployment": "domain",
    "on-device-gesture-validation": "domain",
    "gesture-to-live-mix-design": "domain",
    "audio-output-integration": "domain",
    "live-mixer-and-latency-validation": "domain",
    "music-model-npu-deployment": "domain",
    "npu-quantization-and-accuracy-gating": "domain",
    "library-generation-and-quality-evaluation": "domain",
    "gesture-event-contract": "context",
    "p3-self-service-boundaries": "context",
}

REQUIRED_MANIFEST_FIELDS = (
    "schema_version:", "version:", "entrypoint:", "synapse:", "domain:", "owner:", "visibility:",
    "maturity:", "authoritative_docs:", "safety:",
    "backup_owner:", "review_cadence:", "supported_versions:", "dependencies:",
    "developer_journey_stage:", "feedback_channel:", "deprecation_path:",
    "authority:", "approved_tools:", "endpoints:", "provenance:",
    "control:", "consequential_actions:", "recovery_and_rollback:", "review_gates:",
)
CONTRACT_FIELDS = (
    "contract:", "inputs:", "outputs:", "validation:", "failure_behavior:",
    "negative_scope:", "known_failure_modes:", "two_config_evidence:",
)
CONTRACT_EXEMPT_LAYERS = ("context", "journey")
AGENT_FIELDS = ("responsibilities:", "not_responsible_for:", "approval_gates:", "failure_behavior:")
EVIDENCE_PATH = re.compile(r"evidence/[\w\-./]+\.\w+")
NOT_EVIDENCE = re.compile(r"\b(none yet|not run|never run)\b", re.I)
STANDARD_SKILL_FIELDS = (
    "id",
    "layer",
    "selection_mode",
    "reuse_class",
    "applicability_tags",
    "environment_tags",
    "publication_state",
    "evidence_state",
    "similarity_keys",
    "tool_refs",
)
METRIC_RECORD_FIELDS = (
    "recorded_at",
    "skill_id",
    "layer",
    "reuse_class",
    "environment_tags",
    "request_type",
    "token_measurement_available",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "elapsed_seconds",
    "tool_call_count",
    "retry_count",
    "approval_prompt_count",
    "validation_result",
    "evidence_reused",
    "evidence_path",
    "redaction_verified",
    "notes",
)


def scalar(text: str, key: str) -> str | None:
    m = re.search(rf'^\s*{key}:\s*"?([^"\n]+)"?\s*$', text, re.M)
    return m.group(1).strip() if m else None


def list_items(text: str, key: str) -> list[str]:
    m = re.search(rf'^\s*{key}:\s*\[(.*?)\]', text, re.M)
    return [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()] if m else []


def block_items(text: str, key: str) -> list[str]:
    """Items of a YAML block list like `key:` followed by `- "..."` lines."""
    m = re.search(rf'^(\s*){key}:\s*\n((?:\1\s+-\s.*\n?)+)', text, re.M)
    return [re.sub(r'^\s*-\s*"?|"?\s*$', "", ln) for ln in m.group(2).splitlines()] if m else []


def check_skills(problems: list[str], warnings: list[str]) -> dict[str, tuple[int, int]]:
    evidence_summary: dict[str, tuple[int, int]] = {}
    for skill_id, layer in SKILLS.items():
        d = SKILLS_DIR / skill_id
        manifest, instructions = d / "skill.yaml", d / "SKILL.md"
        for path in (manifest, instructions):
            if not path.is_file():
                problems.append(f"{skill_id}: missing {path.name}")
        if not manifest.is_file():
            continue
        text = manifest.read_text(encoding="utf-8")
        if scalar(text, "id") != skill_id:
            problems.append(f"{skill_id}: id in skill.yaml is {scalar(text, 'id')!r}")
        if scalar(text, "layer") != layer:
            problems.append(f"{skill_id}: layer is {scalar(text, 'layer')!r}, expected {layer!r}")
        for f in REQUIRED_MANIFEST_FIELDS:
            if f not in text:
                problems.append(f"{skill_id}: missing field {f}")
        if layer not in CONTRACT_EXEMPT_LAYERS:
            for f in CONTRACT_FIELDS:
                if f not in text:
                    problems.append(f"{skill_id}: missing contract field {f}")
        if layer == "agent":
            for f in AGENT_FIELDS:
                if f not in text:
                    problems.append(f"{skill_id}: missing agent field {f}")
        for dep in list_items(text, "dependencies"):
            if dep not in SKILLS:
                problems.append(f"{skill_id}: dependency {dep!r} is not in this catalog")
        for doc in list_items(text, "authoritative_docs"):
            if not (d / doc).resolve().exists():
                problems.append(f"{skill_id}: authoritative doc not found: {doc}")
        if "foundational" in text.lower() and layer != "context":
            problems.append(f"{skill_id}: mentions the removed 'foundational' layer")

        # ---- evidence (F23): must cite real files
        if layer not in CONTRACT_EXEMPT_LAYERS:
            entries = block_items(text, "two_config_evidence")
            backed = 0
            for e in entries:
                paths = EVIDENCE_PATH.findall(e)
                for rel in paths:
                    if not (PROJECT_ROOT / rel).is_file():
                        problems.append(f"{skill_id}: evidence file cited but missing: {rel}")
                if paths and not NOT_EVIDENCE.match(e.strip().lower()):
                    backed += 1
            evidence_summary[skill_id] = (backed, len(entries))
            gate = scalar(text, "validation_evidence") or ""
            if gate.lower().startswith("met") and backed == 0:
                problems.append(f"{skill_id}: validation_evidence says 'met' but no evidence entry cites a file")
            if backed == 0:
                warnings.append(f"{skill_id}: no backed evidence (no run recorded)")
            if len(entries) >= 2 and backed < len(entries):
                warnings.append(f"{skill_id}: {len(entries) - backed} of {len(entries)} evidence entries are not backed (e.g. a configuration not run)")

    for d in sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        if d.name not in SKILLS:
            problems.append(f"{d.name}: directory exists but is not declared in SKILLS")
    return evidence_summary


def check_tools(problems: list[str]) -> int:
    path = SKILLS_DIR / "mcp-tools.yaml"
    if not path.is_file():
        problems.append("mcp-tools.yaml missing")
        return 0
    text = path.read_text(encoding="utf-8")
    n = 0
    for block in re.split(r"^  - id:", text, flags=re.M)[1:]:
        n += 1
        tool_id = block.splitlines()[0].strip().strip('"')
        impl = re.search(r'^\s*implementation:\s*"([^"]+)"', block, re.M)
        ev = re.search(r'^\s*evidence:\s*"([^"]+)"', block, re.M)
        if not impl or not (PROJECT_ROOT / impl.group(1)).is_file():
            problems.append(f"tool {tool_id}: implementation missing or not found")
        if not ev or not (PROJECT_ROOT / ev.group(1)).is_file():
            problems.append(f"tool {tool_id}: evidence missing or not found")
    return n


def check_standard_catalog(problems: list[str]) -> int:
    if not STANDARD_CATALOG_PATH.is_file():
        problems.append("synapse-skill-catalog.json missing")
        return 0
    try:
        catalog = json.loads(STANDARD_CATALOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        problems.append(f"synapse-skill-catalog.json is invalid JSON: {error}")
        return 0

    if catalog.get("schema_version") != 1:
        problems.append("standard catalog schema_version must be 1")
    if catalog.get("tool_catalog") != "mcp-tools.yaml":
        problems.append("standard catalog must reference mcp-tools.yaml")
    if catalog.get("metrics_template") != METRICS_TEMPLATE_PATH.name:
        problems.append("standard catalog must reference the metrics template")

    tool_ids = set(re.findall(r'^  - id: "([^"]+)"', (SKILLS_DIR / "mcp-tools.yaml").read_text(encoding="utf-8"), re.M))
    entries = catalog.get("skills")
    if not isinstance(entries, list):
        problems.append("standard catalog skills must be a list")
        return 0

    indexed_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("standard catalog skill entry must be an object")
            continue
        skill_id = entry.get("id")
        if not isinstance(skill_id, str) or skill_id not in SKILLS:
            problems.append(f"standard catalog has unknown skill: {skill_id!r}")
            continue
        if skill_id in indexed_ids:
            problems.append(f"standard catalog duplicates skill: {skill_id}")
        indexed_ids.add(skill_id)
        for field in STANDARD_SKILL_FIELDS:
            if field not in entry:
                problems.append(f"standard catalog {skill_id}: missing {field}")
        if entry.get("layer") != SKILLS[skill_id]:
            problems.append(f"standard catalog {skill_id}: layer does not match skill manifest")
        expected_selection = "injected" if SKILLS[skill_id] == "context" else "selected"
        if entry.get("selection_mode") != expected_selection:
            problems.append(f"standard catalog {skill_id}: selection_mode must be {expected_selection}")
        if "p3" not in entry.get("applicability_tags", []):
            problems.append(f"standard catalog {skill_id}: applicability_tags must include p3")
        for tool_id in entry.get("tool_refs", []):
            if tool_id not in tool_ids:
                problems.append(f"standard catalog {skill_id}: unknown MCP tool {tool_id!r}")

    missing = set(SKILLS) - indexed_ids
    if missing:
        problems.append("standard catalog is missing skills: " + ", ".join(sorted(missing)))

    if not METRICS_TEMPLATE_PATH.is_file():
        problems.append("skill-metrics-baseline.template.json missing")
    else:
        try:
            metrics = json.loads(METRICS_TEMPLATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"metrics template is invalid JSON: {error}")
        else:
            records = metrics.get("records")
            if metrics.get("schema_version") != 1 or not isinstance(records, list) or not records:
                problems.append("metrics template needs schema_version 1 and one template record")
            elif not isinstance(records[0], dict):
                problems.append("metrics template record must be an object")
            else:
                for field in METRIC_RECORD_FIELDS:
                    if field not in records[0]:
                        problems.append(f"metrics template record missing {field}")
    return len(indexed_ids)


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []
    summary = check_skills(problems, warnings)
    tools = check_tools(problems)
    standard_skills = check_standard_catalog(problems)

    print(f"checked {len(SKILLS)} skills and {tools} tools in {SKILLS_DIR}")
    print(f"checked {standard_skills} normalized skill records and metrics template")
    print("evidence (backed entries / total entries):")
    for sid, (b, t) in summary.items():
        print(f"  {sid:42} {b}/{t}")
    for w in warnings:
        print("WARNING", w)
    for p in problems:
        print("PROBLEM", p)
    print("PASS" if not problems else f"FAIL ({len(problems)} problems)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
