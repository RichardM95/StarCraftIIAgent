#!/usr/bin/env python3
"""Check local documentation files, Markdown anchors and documented tools."""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

from sc2_i18n import UIArgumentParser, tr, run_cli

LINK_START_RE = re.compile(r"!?\[[^\]\n]*\]\(")
TOOL_REF_RE = re.compile(r"(?<![\w/])tools/[A-Za-z0-9_.-]+\.py")
SKIP_PARTS = {".git", "publish", "sc2-catalog-graph-out", ".workspace-recovery",
              "backup", "backups", "_backup", "_backups", "tmp", "temp", "_tmp", "_temp",
              "reports", "__pycache__", ".pytest_cache", "node_modules", ".venv", ".runtime"}


def documentation_files(root: Path):
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d.casefold() not in SKIP_PARTS
                         and not d.casefold().startswith(('tmp', '.sc2-reference-stage-', '.sc2-reference-backup-')))
        for name in sorted(files):
            p = Path(directory) / name
            if p.suffix.lower() in {'.md', '.yaml', '.yml'}:
                yield p


def visible_lines(text: str):
    """Keep source line numbers while masking fenced examples."""
    fence, width = '', 0
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if match and match[1][0] == fence and len(match[1]) >= width and not match[2].strip():
                fence = ''
            yield number, ''
        elif match:
            fence, width = match[1][0], len(match[1])
            yield number, ''
        else:
            yield number, line


def link_destinations(line: str):
    for match in LINK_START_RE.finditer(line):
        start = match.end()
        while start < len(line) and line[start].isspace():
            start += 1
        if line[start:start + 1] == '<':
            end = line.find('>', start + 1)
            if end >= 0:
                yield line[start + 1:end]
            continue
        depth, end = 0, start
        while end < len(line):
            char = line[end]
            if char == '\\':
                end += 2
                continue
            if depth == 0 and (char == ')' or char.isspace()):
                break
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            end += 1
        yield re.sub(r'\\([ ()])', r'\1', line[start:end])


def slug(text: str) -> str:
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = html.unescape(text).strip().lower().replace('`', '')
    text = ''.join(c for c in text if c in '_-' or not unicodedata.category(c).startswith(('P', 'S')))
    return re.sub(r'\s', '-', text)


def anchors(lines: list[tuple[int, str]]) -> set[str]:
    result, headings = set(), set()
    previous = ''
    for _, line in lines:
        for match in re.finditer(r'<[^>]+\b(?:id|name)\s*=\s*([\'\"])(.*?)\1', line, re.I):
            result.add(html.unescape(match[2]))
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        title = heading[1] if heading else previous if previous and re.fullmatch(r' {0,3}(?:=+|-+)\s*', line) else None
        if title is not None:
            base = slug(title)
            value, count = base, 0
            while value in headings:
                count += 1
                value = f'{base}-{count}'
            headings.add(value)
            result.add(value)
        previous = '' if title is not None else line.strip()
    return result


def local_target(destination: str) -> tuple[str, str] | None:
    if destination.startswith('//'):
        return None
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', destination) and not re.match(r'^[a-zA-Z]:[/\\]', destination):
        return None
    path, _, fragment = destination.partition('#')
    return unquote(path), unquote(fragment)


def check(root: Path) -> list[str]:
    failures, cache = [], {}

    def read(path):
        if path not in cache:
            text = path.read_text(encoding='utf-8-sig')
            lines = list(visible_lines(text))
            cache[path] = text, lines, anchors(lines)
        return cache[path]

    for source in documentation_files(root):
        text, lines, _ = read(source)
        if source.suffix.lower() == '.md':
            for number, line in lines:
                for destination in link_destinations(line):
                    target = local_target(destination)
                    if target is None:
                        continue
                    path, fragment = target
                    resolved = (source.parent / path).resolve() if path else source
                    if not resolved.exists():
                        failures.append(f'{source.relative_to(root)}:{number}: missing {destination}')
                    elif fragment and resolved.suffix.lower() == '.md' and fragment not in read(resolved)[2]:
                        failures.append(f'{source.relative_to(root)}:{number}: missing anchor {destination}')
        # Commands in fenced examples still name real tools and must stay valid.
        for number, line in enumerate(text.splitlines(), 1):
            for match in TOOL_REF_RE.finditer(line):
                if not (root / match[0]).is_file():
                    failures.append(f'{source.relative_to(root)}:{number}: missing tool {match[0]}')
    return failures


def main() -> int:
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.', help='repository root')
    root = Path(parser.parse_args().root).resolve()
    if not root.is_dir():
        print(tr('Documentation root missing: {p0}', p0=root))
        return 1
    failures = check(root)
    if failures:
        print(tr('Broken local documentation references:'))
        print('\n'.join(f'- {failure}' for failure in failures))
        return 1
    print(tr('Markdown files, anchors and documented tool references OK'))
    return 0


if __name__ == '__main__':
    sys.exit(run_cli(main))
