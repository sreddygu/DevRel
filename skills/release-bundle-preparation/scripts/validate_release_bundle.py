"""Validate a public release-bundle.json using only the Python standard library."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path


CHANNELS = {"incubating", "preview", "stable", "lts"}
DELIVERY_MODELS = {"source-skill-pack", "installable-starter-kit", "device-ready-release-kit"}
SEMVER_PATTERN = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def require_non_empty_string(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")


def validate(bundle: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if bundle.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("project",):
        require_non_empty_string(bundle.get(field), field, errors)
    version = bundle.get("version")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        errors.append("version must be SemVer, for example v1.2.3 or v1.2.3-preview.1")
    if bundle.get("channel") not in CHANNELS:
        errors.append("channel must be incubating, preview, stable, or lts")
    if bundle.get("delivery_model") not in DELIVERY_MODELS:
        errors.append("delivery_model is not recognized")

    source = bundle.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for field in ("repository", "revision", "released_on"):
            require_non_empty_string(source.get(field), f"source.{field}", errors)
        released_on = source.get("released_on")
        if isinstance(released_on, str):
            try:
                date.fromisoformat(released_on)
            except ValueError:
                errors.append("source.released_on must use YYYY-MM-DD")

    compatibility = bundle.get("compatibility")
    if not isinstance(compatibility, dict):
        errors.append("compatibility must be an object")
    else:
        for field in ("hosts", "devices", "known_exclusions"):
            if not isinstance(compatibility.get(field), list):
                errors.append(f"compatibility.{field} must be a list")

    skills = bundle.get("skills")
    if not isinstance(skills, list) or not skills:
        errors.append("skills must be a non-empty list")
    elif any(not isinstance(skill, str) or not SKILL_ID_PATTERN.fullmatch(skill) for skill in skills):
        errors.append("skills must contain lowercase hyphenated IDs")

    assets = bundle.get("assets")
    if not isinstance(assets, list):
        errors.append("assets must be a list")
    else:
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                errors.append(f"assets[{index}] must be an object")
                continue
            for field in ("name", "retrieval", "license"):
                require_non_empty_string(asset.get(field), f"assets[{index}].{field}", errors)
            checksum = asset.get("sha256")
            if not isinstance(checksum, str) or not SHA256_PATTERN.fullmatch(checksum):
                errors.append(f"assets[{index}].sha256 must be a lowercase SHA-256")

    validation = bundle.get("validation")
    safety = bundle.get("safety")
    for section, fields in ((validation, ("command", "evidence")), (safety, ("rollback", "secrets_policy"))):
        if not isinstance(section, dict):
            errors.append("validation and safety must be objects")
            continue
        for field in fields:
            require_non_empty_string(section.get(field), field, errors)
    if isinstance(safety, dict) and not isinstance(safety.get("approval_gates"), list):
        errors.append("safety.approval_gates must be a list")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: py -3 validate_release_bundle.py <release-bundle.json>")
        return 2
    bundle_path = Path(sys.argv[1])
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read {bundle_path}: {error}")
        return 2
    if not isinstance(bundle, dict):
        print("Release bundle must contain a JSON object.")
        return 1
    errors = validate(bundle)
    if errors:
        print("Release bundle validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Release bundle is valid: {bundle['project']} {bundle['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
