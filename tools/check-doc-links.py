#!/usr/bin/env python3
"""Check repository Markdown links without reading generated or release output."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
TOOL_REF_RE = re.compile(r"(?<![\w/])tools/[A-Za-z0-9_.-]+\.py")
SKIP_PARTS = {".git", "publish", "sc2-catalog-graph-out", ".workspace-recovery"}


def markdown_files(root: Path):
    for path in root.rglob("*.md"):
        if not SKIP_PARTS.intersection(path.relative_to(root).parts):
            yield path


def tool_reference_files(root: Path):
    for suffix in ("*.md", "*.yaml", "*.yml"):
        for path in root.rglob(suffix):
            if not SKIP_PARTS.intersection(path.relative_to(root).parts):
                yield path


def local_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    if not target or target.startswith(("#", "http://", "https://", "mailto:", "app://")):
        return None
    return unquote(target.split("#", 1)[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []

    for source in markdown_files(root):
        text = source.read_text(encoding="utf-8-sig")
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target_text = local_target(match.group(1))
                if target_text is None:
                    continue
                target = Path(target_text)
                resolved = target if target.is_absolute() else source.parent / target
                if not resolved.exists():
                    failures.append(
                        f"{source.relative_to(root)}:{line_no}: missing {match.group(1)}"
                    )

    for source in tool_reference_files(root):
        text = source.read_text(encoding="utf-8-sig")
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in TOOL_REF_RE.finditer(line):
                target = root / Path(match.group(0))
                if not target.is_file():
                    failures.append(
                        f"{source.relative_to(root)}:{line_no}: missing tool {match.group(0)}"
                    )

    if failures:
        print("Broken local documentation references:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("Markdown links and documented tool references OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
