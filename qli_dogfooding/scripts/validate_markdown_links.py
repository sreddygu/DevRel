"""Validate local Markdown links and anchors in the QLI Dogfooding project."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?P<target>[^)\s]+)\)")
PLAIN_MARKDOWN_REFERENCE = re.compile(
    r"(?<![\w/.-])(?:[A-Za-z0-9_./-]+/)?[A-Za-z0-9_.-]+\.md\b"
)
HEADING = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
FENCE = re.compile(r"^\s*```")
IGNORED_DIRECTORIES = {
    "__pycache__",
    ".venv",
    "audit",
    "evidence",
    "reference",
    "resources",
}


def default_project_root() -> Path:
    """Return the project root relative to this script."""
    return Path(__file__).resolve().parents[1]


def markdown_files(project_root: Path) -> list[Path]:
    """Return checked Markdown files while excluding generated artifacts."""
    return sorted(
        path
        for path in project_root.rglob("*.md")
        if not any(part in IGNORED_DIRECTORIES for part in path.relative_to(project_root).parts)
    )


def slugify(heading: str) -> str:
    """Approximate GitHub's heading anchor format for local documentation."""
    normalized = heading.lower()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    return re.sub(r"\s+", "-", normalized).strip("-")


def headings(path: Path) -> set[str]:
    """Return normalized anchors defined by a Markdown file."""
    return {
        slugify(match.group("title"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if (match := HEADING.match(line))
    }


def relative_path(path: Path, project_root: Path) -> str:
    """Return a stable project-relative path for diagnostics."""
    return path.relative_to(project_root).as_posix()


def validate(project_root: Path) -> list[str]:
    """Return all local-link, anchor, and plain-reference documentation errors."""
    errors: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}

    for source in markdown_files(project_root):
        in_fence = False
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            links = list(MARKDOWN_LINK.finditer(line))
            for link in links:
                target = link.group("target")
                if target.startswith(("#", "http://", "https://", "mailto:")):
                    continue

                path_text, separator, anchor = target.partition("#")
                resolved = (source.parent / path_text).resolve()
                if not resolved.exists():
                    errors.append(
                        f"{relative_path(source, project_root)}:{line_number}: missing link target {target}"
                    )
                    continue
                if separator and resolved.suffix == ".md":
                    anchors = anchor_cache.setdefault(resolved, headings(resolved))
                    if anchor not in anchors:
                        errors.append(
                            f"{relative_path(source, project_root)}:{line_number}: "
                            f"missing anchor #{anchor} in {path_text}"
                        )

            without_links = MARKDOWN_LINK.sub("", line)
            for plain in PLAIN_MARKDOWN_REFERENCE.finditer(without_links):
                errors.append(
                    f"{relative_path(source, project_root)}:{line_number}: "
                    f"plain Markdown reference {plain.group(0)} must be linked"
                )

    return errors


def main() -> int:
    """Parse arguments, validate documentation, and print a concise result."""
    parser = argparse.ArgumentParser(
        description="Validate local Markdown links and heading anchors."
    )
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    errors = validate(project_root)
    for error in errors:
        print(f"ERROR: {error}")
    print(
        "Markdown link validation: "
        + ("PASS" if not errors else f"FAIL ({len(errors)} error(s))")
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
