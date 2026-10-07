from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ELEMENT_RE = re.compile(
    r'(?m)^    <Element Type="(?P<type>[^"]+)" Id="(?P<id>[0-9A-F]{8})">'
)


def fresh_id(used_ids: set[str]) -> str:
    while True:
        candidate = secrets.token_hex(4).upper()
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate


def find_repairs(text: str) -> list[tuple[str, str, str]]:
    declarations: dict[str, list[str]] = defaultdict(list)
    for match in ELEMENT_RE.finditer(text):
        declarations[match.group("id")].append(match.group("type"))

    used_ids = set(declarations)
    repairs: list[tuple[str, str, str]] = []
    for element_id, element_types in sorted(declarations.items()):
        if len(element_types) < 2:
            continue
        if len(set(element_types)) != len(element_types):
            raise RuntimeError(
                f"Duplicate ID {element_id} is reused by the same element type; "
                "references cannot be disambiguated safely"
            )
        for element_type in element_types[1:]:
            repairs.append((element_id, element_type, fresh_id(used_ids)))
    return repairs


def apply_repairs(text: str, repairs: list[tuple[str, str, str]]) -> str:
    for old_id, element_type, new_id in repairs:
        pattern = re.compile(
            rf'(Type="{re.escape(element_type)}" Id="){re.escape(old_id)}(")'
        )
        text, count = pattern.subn(rf"\g<1>{new_id}\2", text)
        if count < 2:
            raise RuntimeError(
                f"Expected declaration and reference for {element_type} {old_id}; found {count}"
            )
    return text


def duplicate_ids(text: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for match in ELEMENT_RE.finditer(text):
        element_id = match.group("id")
        if element_id in seen:
            duplicates.add(element_id)
        seen.add(element_id)
    return sorted(duplicates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair globally duplicated SC2 Trigger Element IDs only when each collision "
            "uses distinct element types."
        )
    )
    parser.add_argument("triggers", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.triggers.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    ET.fromstring(text)

    repairs = find_repairs(text)
    print(f"Repairable duplicate declarations: {len(repairs)}")
    for old_id, element_type, new_id in repairs:
        print(f"  {old_id} ({element_type}) -> {new_id}")
    if not args.apply or not repairs:
        return 0

    updated = apply_repairs(text, repairs)
    ET.fromstring(updated)
    remaining = duplicate_ids(updated)
    if remaining:
        raise RuntimeError("Duplicate Element IDs remain: " + ", ".join(remaining))

    if args.backup:
        if args.backup.exists():
            raise FileExistsError(f"Backup already exists: {args.backup}")
        shutil.copy2(args.triggers, args.backup)

    temporary = args.triggers.with_name(args.triggers.name + ".codex.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(updated)
        shutil.copystat(args.triggers, temporary)
        os.replace(temporary, args.triggers)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"Applied repairs: {len(repairs)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
