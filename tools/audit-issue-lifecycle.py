#!/usr/bin/env python3
"""Validate active issue-ledger lifecycle labels and required evidence fields."""
from __future__ import annotations

import argparse
import re
from sc2_paths import project_data_dir
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STAGES = (
    "reported",
    "root cause confirmed",
    "source fixed",
    "static validation passed",
    "Editor accepted",
    "packaged runtime passed",
)
BASE_FIELDS = ("Status", "Map / Context", "Reproduction", "Observed", "Expected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--ledger", type=Path, help="Explicit issue ledger; missing explicit files fail")
    selection.add_argument("--target", type=Path, help="Components target whose project ledger is checked")
    args = parser.parse_args()
    try:
        if args.target is not None and (not args.target.is_dir() or args.target.suffix.casefold() not in {".sc2mod", ".sc2map"}):
            raise ValueError("Not a Components target: " + str(args.target))
        data = project_data_dir(REPO_ROOT, primary=args.target) if args.ledger is None else None
        ledger = args.ledger if args.ledger is not None else data / "docs/issues.md" if data else None
        if args.ledger is None and (ledger is None or not ledger.exists()):
            print("SKIP Issue lifecycle audit: no active project or project ledger: " + str(ledger))
            return 0
        text = ledger.read_text(encoding="utf-8-sig").split("## Issue Template", 1)[0]
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc))
        return 1
    sections = re.split(r"(?m)^### (?=ISSUE-\d+:)", text)[1:]
    failures: list[str] = []
    for section in sections:
        title = section.splitlines()[0].strip()
        fields = {
            match.group(1): match.group(2).strip()
            for match in re.finditer(r"(?m)^- \*\*(.+?):\*\*[ \t]*([^\r\n]*)$", section)
        }
        for field in BASE_FIELDS:
            if not fields.get(field):
                failures.append(f"{title}: missing {field}")
        status = fields.get("Status")
        if status not in STAGES:
            failures.append(f"{title}: invalid lifecycle status {status!r}")
            continue
        stage = STAGES.index(status)
        if stage >= STAGES.index("root cause confirmed") and not fields.get("Root Cause"):
            failures.append(f"{title}: {status} requires Root Cause evidence")
        if stage >= STAGES.index("source fixed") and not fields.get("Fix"):
            failures.append(f"{title}: {status} requires Fix evidence")
        if stage >= STAGES.index("static validation passed"):
            if not fields.get("Validation"):
                failures.append(f"{title}: static validation status requires an explicit Validation field")
        for gate, field in (("Editor accepted", "Editor Validation"),
                            ("packaged runtime passed", "Runtime Validation")):
            if stage >= STAGES.index(gate) and not fields.get(field):
                failures.append(f"{title}: {gate} requires {field} evidence")
    if not sections and "当前无活动问题。" not in text:
        failures.append("active ledger contains no ISSUE sections")
    if failures:
        print(f"Issue lifecycle audit FAILED ({len(failures)} issue(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"Issue lifecycle audit passed ({len(sections)} active issues).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
