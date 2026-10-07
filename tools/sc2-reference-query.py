#!/usr/bin/env python3
"""Query bundled official and partner SC2 component samples without broad rescans."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REFERENCE_ROOT = ROOT / "DataEditorXML" / "SC2GameDataComponents"
COMPONENT_SUFFIXES = (".sc2mod", ".sc2campaign")
TEXT_SUFFIXES = {".xml", ".txt", ".galaxy", ".sc2layout"}
MAX_OUTPUT_LINE_CHARS = 400


def component_name(path: Path) -> str | None:
    for part in path.parts:
        if part.lower().endswith(COMPONENT_SUFFIXES):
            return part
    return None


def content_area(path: Path) -> str | None:
    lowered = [part.lower() for part in path.parts]
    for name in ("enus.sc2data", "zhcn.sc2data"):
        if name in lowered:
            return name.removesuffix(".sc2data")
    for index, part in enumerate(lowered[:-1]):
        if part == "base.sc2data" and lowered[index + 1] == "gamedata":
            return "gamedata"
    return None


def iter_reference_files(root: Path, *, source=None, component=None, area="all", family=None):
    component_filter = component.casefold() if component else None
    family_files = {f"{family.casefold()}data.xml", "gamedata.xml"} if family else None
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if not relative.parts or (source and relative.parts[0].casefold() != source.casefold()):
            continue
        package = component_name(relative)
        if package is None or (component_filter and component_filter not in package.casefold()):
            continue
        file_area = content_area(relative)
        if file_area is None or (area != "all" and file_area != area):
            continue
        if family_files and path.name.casefold() not in family_files:
            continue
        yield path, relative, package, file_area


def list_components(root: Path, source: str | None) -> int:
    entries = defaultdict(set)
    for _, relative, package, area in iter_reference_files(root, source=source):
        entries[(relative.parts[0], package)].add(area)
    for (source_name, package), areas in sorted(entries.items(), key=lambda item: tuple(x.casefold() for x in item[0])):
        print(f"{source_name}/{package}\t{','.join(sorted(areas))}")
    print(f"components: {len(entries)}")
    return 0


def show_stats(root: Path, source: str | None) -> int:
    files = size = 0
    components = set()
    areas = defaultdict(int)
    for path, relative, package, area in iter_reference_files(root, source=source):
        files += 1
        size += path.stat().st_size
        components.add((relative.parts[0], package))
        areas[area] += 1
    print(f"components: {len(components)}")
    print(f"searchable_files: {files}")
    print(f"searchable_bytes: {size}")
    for area in sorted(areas):
        print(f"{area}: {areas[area]}")
    return 0


def read_text_lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp936"):
        try:
            return raw.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").splitlines()


def compact_line(line: str, needle: str, ignore_case: bool) -> str:
    if len(line) <= MAX_OUTPUT_LINE_CHARS:
        return line
    comparable = line.casefold() if ignore_case else line
    position = comparable.find(needle)
    start = max(0, position - 100) if position >= 0 else 0
    end = min(len(line), start + MAX_OUTPUT_LINE_CHARS)
    if end - start < MAX_OUTPUT_LINE_CHARS:
        start = max(0, end - MAX_OUTPUT_LINE_CHARS)
    return ("…" if start else "") + line[start:end] + ("…" if end < len(line) else "")


def find_matches(args: argparse.Namespace) -> int:
    needle = args.term.casefold() if args.ignore_case else args.term
    matches = scanned = 0
    for path, relative, _, _ in iter_reference_files(
        args.root, source=args.source, component=args.component, area=args.area, family=args.family
    ):
        scanned += 1
        try:
            lines = read_text_lines(path)
        except OSError as exc:
            print(f"warning: cannot read {relative}: {exc}", file=sys.stderr)
            continue
        for line_number, line in enumerate(lines, start=1):
            haystack = line.casefold() if args.ignore_case else line
            if needle not in haystack:
                continue
            start = max(0, line_number - 1 - args.context)
            end = min(len(lines), line_number + args.context)
            for index in range(start, end):
                marker = ">" if index == line_number - 1 else " "
                print(f"{marker} {relative}:{index + 1}:{compact_line(lines[index], needle, args.ignore_case)}")
            matches += 1
            if matches >= args.limit:
                print(f"matches: {matches} (limit reached); files scanned: {scanned}")
                return 0
    print(f"matches: {matches}; files scanned: {scanned}")
    return 0 if matches else 1


def show_objects(args: argparse.Namespace) -> int:
    if ":" not in args.target:
        raise SystemExit("Object target must be Family:Id, for example Unit:Marine")
    family, object_id = args.target.split(":", 1)
    if not family or not object_id:
        raise SystemExit("Object target must be Family:Id")
    matches = 0
    for path, relative, _, _ in iter_reference_files(
        args.root, source=args.source, component=args.component, area="gamedata", family=family
    ):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            print(f"warning: cannot parse {relative}: {exc}", file=sys.stderr)
            continue
        for element in root:
            if element.get("id") != object_id or not element.tag.startswith("C" + family):
                continue
            xml = ET.tostring(element, encoding="unicode")
            print(f"# {relative} [{element.tag} parent={element.get('parent', '')}]")
            print(xml[: args.max_chars] if args.max_chars else xml)
            if args.max_chars and len(xml) > args.max_chars:
                print(f"... truncated {len(xml) - args.max_chars} characters; use --max-chars 0 for full XML")
            matches += 1
            if matches >= args.limit:
                print(f"objects: {matches} (limit reached)")
                return 0
    print(f"objects: {matches}")
    return 0 if matches else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_REFERENCE_ROOT, help="sample-data root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("components", "stats"):
        command = subparsers.add_parser(name)
        command.add_argument("--source", choices=("mods", "campaigns", "CM"))
    find = subparsers.add_parser("find")
    find.add_argument("term")
    find.add_argument("--source", choices=("mods", "campaigns", "CM"))
    find.add_argument("--component", help="case-insensitive component-name substring")
    find.add_argument("--area", choices=("all", "gamedata", "enus", "zhcn"), default="all")
    find.add_argument("--family", help="catalog family, such as Unit, Actor, Effect, or Validator")
    find.add_argument("--ignore-case", action="store_true")
    find.add_argument("--limit", type=int, default=40)
    find.add_argument("--context", type=int, default=0)
    obj = subparsers.add_parser("object", help="show an exact catalog object from raw component XML")
    obj.add_argument("target", help="Family:Id, for example Unit:Marine")
    obj.add_argument("--source", choices=("mods", "campaigns", "CM"))
    obj.add_argument("--component", help="case-insensitive component-name substring")
    obj.add_argument("--limit", type=int, default=5)
    obj.add_argument("--max-chars", type=int, default=6000, help="maximum XML characters per object; 0 means full")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    if not args.root.is_dir():
        parser.error(f"sample-data root does not exist: {args.root}")
    if args.command == "components":
        return list_components(args.root, args.source)
    if args.command == "stats":
        return show_stats(args.root, args.source)
    if args.command == "object":
        if args.limit < 1 or args.max_chars < 0:
            parser.error("--limit must be positive and --max-chars cannot be negative")
        return show_objects(args)
    if args.limit < 1 or args.context < 0:
        parser.error("--limit must be positive and --context cannot be negative")
    return find_matches(args)


if __name__ == "__main__":
    raise SystemExit(main())
