"""Validate the workspace Synapse project registry without external packages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PORTFOLIO_DIRECTORY = Path(__file__).resolve().parent
ACADEMY_ROOT = PORTFOLIO_DIRECTORY.parent
CATALOG_PATH = PORTFOLIO_DIRECTORY / "synapse-project-catalog.json"
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VALID_STATUSES = {"enabled", "proposed"}
SHARED_SKILLS_DIRECTORY = ACADEMY_ROOT / "skills"
NON_PROJECT_DIRECTORIES = {
    ".git",
    "academy",
    "archive",
    "docs",
    "portfolio",
    "skills",
    "__pycache__",
    "qa-intermediate-curriculum",
    "qa-intermediate-curriculum.worktrees",
}


def validate() -> list[str]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []

    if catalog.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    projects = catalog.get("projects")
    if not isinstance(projects, list) or not projects:
        return ["projects must be a non-empty list"]
    shared_profiles = catalog.get("shared_profiles")
    if not isinstance(shared_profiles, dict) or not shared_profiles:
        return ["shared_profiles must be a non-empty object"]
    for profile_name, skill_ids in shared_profiles.items():
        if not isinstance(profile_name, str) or not SKILL_ID_PATTERN.fullmatch(profile_name):
            errors.append(f"invalid shared profile name: {profile_name!r}")
        if not isinstance(skill_ids, list) or not skill_ids:
            errors.append(f"{profile_name}: shared profile must contain skill IDs")
        elif any(
            not isinstance(skill_id, str) or not SKILL_ID_PATTERN.fullmatch(skill_id)
            for skill_id in skill_ids
        ):
            errors.append(f"{profile_name}: shared profile has an invalid skill ID")

    discovered_projects = {
        path.name
        for path in ACADEMY_ROOT.iterdir()
        if path.is_dir() and path.name not in NON_PROJECT_DIRECTORIES
    }
    listed_projects: set[str] = set()

    for project in projects:
        directory = project.get("directory")
        status = project.get("status")
        shared_profile = project.get("shared_profile")
        next_skills = project.get("next_skills")

        if not isinstance(directory, str) or not directory:
            errors.append("every project requires a directory")
            continue
        if directory in listed_projects:
            errors.append(f"duplicate project entry: {directory}")
        listed_projects.add(directory)
        if directory not in discovered_projects:
            errors.append(f"catalog project directory does not exist: {directory}")
        if status not in VALID_STATUSES:
            errors.append(f"{directory}: invalid status {status!r}")
        if not isinstance(shared_profile, str) or shared_profile not in shared_profiles:
            errors.append(f"{directory}: shared_profile must reference a declared shared profile")
        if not isinstance(next_skills, list):
            errors.append(f"{directory}: next_skills must be a list")
            continue
        if status == "enabled":
            catalog_path = project.get("catalog")
            if not isinstance(catalog_path, str) or not (ACADEMY_ROOT / catalog_path).is_file():
                errors.append(f"{directory}: enabled project needs an existing catalog")
            enabled_skill_count = project.get("enabled_skill_count")
            if not isinstance(enabled_skill_count, int) or enabled_skill_count < 1:
                errors.append(f"{directory}: enabled project needs enabled_skill_count")
                continue

            project_skills_directory = ACADEMY_ROOT / directory / "skills"
            if not project_skills_directory.is_dir():
                errors.append(f"{directory}: enabled project needs a skills directory")
                continue

            project_skill_directories = sorted(
                path
                for path in project_skills_directory.iterdir()
                if path.is_dir() and (path / "SKILL.md").is_file() and (path / "skill.yaml").is_file()
            )
            if len(project_skill_directories) != enabled_skill_count:
                errors.append(
                    f"{directory}: enabled_skill_count is {enabled_skill_count}, "
                    f"but found {len(project_skill_directories)} complete local skills"
                )
            for skill_path in project_skill_directories:
                metadata = (skill_path / "skill.yaml").read_text(encoding="utf-8")
                if f'id: "{skill_path.name}"' not in metadata:
                    errors.append(
                        f"{directory}/{skill_path.name}: skill.yaml id does not match directory"
                    )
                if 'entrypoint: "SKILL.md"' not in metadata or "synapse:" not in metadata:
                    errors.append(
                        f"{directory}/{skill_path.name}: skill.yaml needs Synapse metadata and SKILL.md entrypoint"
                    )
        elif not next_skills:
            errors.append(f"{directory}: proposed project needs at least one next skill")
        for skill_id in next_skills:
            if not isinstance(skill_id, str) or not SKILL_ID_PATTERN.fullmatch(skill_id):
                errors.append(f"{directory}: invalid skill id {skill_id!r}")

    missing_projects = discovered_projects - listed_projects
    if missing_projects:
        errors.append("projects missing from catalog: " + ", ".join(sorted(missing_projects)))

    shared_skill_adoption = catalog.get("shared_skill_adoption")
    if not isinstance(shared_skill_adoption, dict) or not shared_skill_adoption:
        errors.append("shared_skill_adoption must be a non-empty object")
    else:
        for skill_id, adopters in shared_skill_adoption.items():
            if not isinstance(skill_id, str) or not SKILL_ID_PATTERN.fullmatch(skill_id):
                errors.append(f"invalid shared skill id: {skill_id!r}")
                continue
            skill_path = SHARED_SKILLS_DIRECTORY / skill_id
            skill_instructions = skill_path / "SKILL.md"
            skill_metadata = skill_path / "skill.yaml"
            if not skill_instructions.is_file() or not skill_metadata.is_file():
                errors.append(f"shared skill files are missing: {skill_id}")
            else:
                instructions = skill_instructions.read_text(encoding="utf-8")
                metadata = skill_metadata.read_text(encoding="utf-8")
                if not instructions.startswith("---\n") or f"name: {skill_id}\n" not in instructions:
                    errors.append(f"{skill_id}: SKILL.md needs matching YAML frontmatter")
                if f'id: "{skill_id}"' not in metadata:
                    errors.append(f"{skill_id}: skill.yaml id does not match directory")
                if 'entrypoint: "SKILL.md"' not in metadata or "synapse:" not in metadata:
                    errors.append(f"{skill_id}: skill.yaml needs Synapse metadata and SKILL.md entrypoint")
            if not isinstance(adopters, list) or not adopters:
                errors.append(f"{skill_id}: adopters must be a non-empty list")
                continue
            if len(adopters) != len(set(adopters)):
                errors.append(f"{skill_id}: duplicate adopter")
            unknown_adopters = set(adopters) - listed_projects
            if unknown_adopters:
                errors.append(
                    f"{skill_id}: unknown adopters: " + ", ".join(sorted(unknown_adopters))
                )

        expected_adoption: dict[str, set[str]] = {}
        for project in projects:
            directory = project.get("directory")
            profile_name = project.get("shared_profile")
            if not isinstance(directory, str) or not isinstance(profile_name, str):
                continue
            profile_skills = shared_profiles.get(profile_name, [])
            if not isinstance(profile_skills, list):
                continue
            for skill_id in profile_skills:
                if isinstance(skill_id, str):
                    expected_adoption.setdefault(skill_id, set()).add(directory)
        if set(shared_skill_adoption) != set(expected_adoption):
            errors.append("shared_skill_adoption keys must match the declared shared profiles")
        for skill_id, expected_adopters in expected_adoption.items():
            actual_adopters = shared_skill_adoption.get(skill_id, [])
            if isinstance(actual_adopters, list) and set(actual_adopters) != expected_adopters:
                errors.append(f"{skill_id}: adopters do not match project shared_profile assignments")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Synapse catalog validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Synapse catalog is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
