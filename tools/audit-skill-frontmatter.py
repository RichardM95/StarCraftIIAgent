#!/usr/bin/env python3
"""Validate SKILL.md frontmatter for all skills under skills/.

Checks each SKILL.md for:
  - YAML frontmatter block delimited by leading ``---`` ... ``---``
  - ``name:`` field present and matches the parent directory name
  - ``description:`` field present, non-empty, and single-line (folded/literal
    YAML scalars ``>`` / ``|`` are rejected — use plain or quoted single-line)
  - Non-empty body content after the frontmatter block

Exit code 0 when all skills pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

NAME_RE = re.compile(r"^name:[ \t]*(.+?)[ \t]*$", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"^description:[ \t]*(.+?)[ \t]*$", re.MULTILINE)


def find_skill_files(root: Path) -> list[Path]:
    """Return every SKILL.md under root (skills/ + skills/galaxy/ + skills/sc2data/)."""
    if not root.exists():
        return []
    return sorted(root.rglob("SKILL.md"))


def parse_frontmatter(text: str) -> tuple[str | None, int]:
    """Return (frontmatter_text, end_line_index) where end_line_index is the
    zero-based line index of the closing ``---``. Returns (None, -1) if no
    well-formed frontmatter block exists at the top of the file.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), idx
    return None, -1


def validate_skill(skill_file: Path, root: Path) -> list[str]:
    """Return a list of failure strings for this skill file (empty = pass)."""
    failures: list[str] = []
    rel = skill_file.relative_to(root)
    expected_name = skill_file.parent.name

    try:
        text = skill_file.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return [f"{rel}: cannot read file ({exc})"]

    fm_text, end_idx = parse_frontmatter(text)
    if fm_text is None:
        failures.append(f"{rel}:1: missing YAML frontmatter block (expected leading '---' ... '---')")
        return failures

    # Verify non-empty body content after frontmatter (end_idx is the closing --- line).
    body_text = "\n".join(text.splitlines()[end_idx + 1:]).strip()
    if not body_text:
        failures.append(f"{rel}:1: empty body — SKILL.md has frontmatter but no content after it")

    name_match = NAME_RE.search(fm_text)
    if not name_match:
        failures.append(f"{rel}:1: frontmatter missing 'name:' field")
    else:
        name_value = name_match.group(1).strip().strip("\"'")
        if not name_value:
            failures.append(f"{rel}:1: 'name:' field is empty")
        elif name_value != expected_name:
            failures.append(
                f"{rel}:1: 'name:' value '{name_value}' does not match directory name '{expected_name}'"
            )

    desc_match = DESCRIPTION_RE.search(fm_text)
    if not desc_match:
        failures.append(f"{rel}:1: frontmatter missing 'description:' field")
    else:
        desc_raw = desc_match.group(1).strip()
        desc_value = desc_raw.strip("\"'")
        if not desc_value:
            failures.append(f"{rel}:1: 'description:' field is empty")
        elif not (desc_raw.startswith('"') or desc_raw.startswith("'")) and desc_value in (">", "|", ">-", "|-", ">+", "|+"):
            failures.append(
                f"{rel}:1: multi-line YAML scalar ('{desc_value}') is not supported — use single-line description"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-root",
        default=str(SKILLS_ROOT),
        help="skills/ directory to scan (default: <repo>/skills)",
    )
    args = parser.parse_args()

    skills_root = Path(args.skills_root).resolve()
    skill_files = find_skill_files(skills_root)

    if not skill_files:
        print(f"No SKILL.md files found under {skills_root}")
        return 1

    all_failures: list[str] = []
    for skill_file in skill_files:
        all_failures.extend(validate_skill(skill_file, skills_root))

    if all_failures:
        print(f"Skill frontmatter issues ({len(all_failures)}):")
        for failure in all_failures:
            print(f"  - {failure}")
        return 1

    print(f"Skill frontmatter OK ({len(skill_files)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
