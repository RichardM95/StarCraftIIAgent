#!/usr/bin/env python3
"""Validate active issue-ledger lifecycle labels and required evidence fields."""
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "wiki" / "implementation" / "bug-reports" / "latest.md"
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
    text = LEDGER.read_text(encoding="utf-8").split("## Issue Template", 1)[0]
    sections = re.split(r"(?m)^### (?=ISSUE-\d+:)", text)[1:]
    failures: list[str] = []
    for section in sections:
        title = section.splitlines()[0].strip()
        fields = {
            match.group(1): match.group(2).strip()
            for match in re.finditer(r"(?m)^- \*\*(.+?):\*\*\s*(.*)$", section)
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
