"""Local asset inventory, literal reference auditing and import candidates.

Dependency roots are ordered low to high precedence. The audit is deliberately
local: unresolved engine macros, missing dependencies and references embedded in
binary M3 files cannot be resolved by a filesystem scan. No source is modified.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from pathlib import Path, PureWindowsPath
import xml.etree.ElementTree as ET

from .errors import SC2Error

_EXCLUDED = {"_codex_backups", ".git", ".venv", "__pycache__", ".pytest_cache", ".sc2-mcp"}
_SUFFIXES = {".m3", ".m3a", ".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".gif",
             ".ogg", ".wav", ".mp3", ".flac", ".wem", ".mp4", ".ogv", ".avi", ".sc2layout",
             ".anim", ".m4a", ".ttf", ".otf"}
_MACROS = re.compile(r"[@#$%{}*?]")


def _relative(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise SC2Error("unsafe_asset_path", "资源路径不能为空")
    win = PureWindowsPath(value)
    parts = value.replace("\\", "/").split("/")
    if win.drive or win.root or any(not p or p in {".", ".."} or p.casefold() in _EXCLUDED
                                  or re.search(r'[<>:"|?*\x00-\x1f]', p) or p.endswith((" ", "."))
                                  or re.match(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", p)
                                  for p in parts):
        raise SC2Error("unsafe_asset_path", "资源路径必须是安全的地图相对路径", path=value)
    return "/".join(parts)


def _safe(root: Path, relative: str) -> Path:
    relative = _relative(relative)
    base = Path(root).resolve()
    if not base.is_dir():
        raise SC2Error("missing_project", "地图组件目录不存在", path=str(root))
    target = base.joinpath(*relative.split("/"))
    current = target
    while current != base:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise SC2Error("linked_asset_path", "不通过链接访问地图资源", path=relative)
        current = current.parent
    if not target.resolve().is_relative_to(base):
        raise SC2Error("asset_path_escape", "资源路径越出地图目录", path=relative)
    if target.is_file() and target.stat().st_nlink > 1:
        raise SC2Error("hardlinked_asset", "资源是硬链接，请使用独立副本", path=relative)
    return target


def _files(root: Path):
    root = Path(root).resolve()
    if not root.is_dir():
        raise SC2Error("missing_project", "地图组件目录不存在", path=str(root))
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.casefold() not in _EXCLUDED)
        for name in sorted(files):
            relative = (Path(directory) / name).relative_to(root).as_posix()
            yield relative, _safe(root, relative)


def _logical(relative: str) -> str:
    parts = relative.split("/")
    if len(parts) > 1 and parts[0].lower().endswith((".sc2assets", ".sc2data")):
        return "/".join(parts[1:])
    return relative


def _asset(relative: str) -> bool:
    logical = _logical(relative)
    return logical.casefold().startswith("assets/") or Path(logical).suffix.casefold() in _SUFFIXES


def _kind(relative: str) -> str:
    suffix = Path(relative).suffix.casefold()
    if suffix in {".m3", ".m3a", ".anim"}:
        return "model"
    if suffix in {".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
        return "texture"
    if suffix in {".ogg", ".wav", ".mp3", ".flac", ".wem", ".m4a"}:
        return "sound"
    if suffix == ".sc2layout":
        return "layout"
    return "other"


def inspect_assets(root: Path, query: str = "") -> dict:
    assets = []
    indexed = defaultdict(list)
    for relative, path in _files(root):
        if not _asset(relative):
            continue
        logical = _logical(relative)
        indexed[logical.casefold()].append(relative)
        if query.casefold() in relative.casefold():
            assets.append({"path": relative, "logical_path": logical, "kind": _kind(relative),
                           "size": path.stat().st_size})
    return {"assets": assets, "count": len(assets),
            "collisions": [{"logical_path": key, "paths": values} for key, values in indexed.items() if len(values) > 1],
            "scope": "local_files_only", "root": str(Path(root).resolve())}


def _reference_value(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    suffix = Path(normalized).suffix.casefold()
    return suffix in _SUFFIXES or (normalized.casefold().startswith("assets/") and bool(_MACROS.search(normalized)))


def _xml_references(data: bytes, relative: str):
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise SC2Error("unsupported_xml", "资源引用扫描不接受 DTD 或实体声明", source=relative)
    try:
        document = ET.fromstring(data)
    except ET.ParseError as exc:
        raise SC2Error("invalid_xml", "资源引用源无法解析", source=relative, error=str(exc)) from exc
    for node in document.iter():
        for key, value in node.attrib.items():
            if _reference_value(value):
                yield value.strip(), {"source": relative, "tag": node.tag, "attribute": key}
        if node.text and _reference_value(node.text):
            yield node.text.strip(), {"source": relative, "tag": node.tag, "attribute": "#text"}


def _galaxy_references(data: bytes, relative: str):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SC2Error("unsupported_encoding", "脚本资源引用扫描需要 UTF-8", source=relative) from exc
    token = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"')
    for match in token.finditer(text):
        if not match.group().startswith('"'):
            continue
        value = re.sub(r'\\(["\\])', r'\1', match.group()[1:-1])
        if _reference_value(value):
            yield value.strip(), {"source": relative, "line": text.count("\n", 0, match.start()) + 1}


def missing_asset_references(roots: list[Path]) -> dict:
    """Audit local XML and Galaxy literals; report ambiguity and engine macros.

    All local XML is scanned, including XML not selected by GameData.xml. Each
    reference therefore carries its source; results are not effective-Catalog
    or binary-model validation. Pass resolved dependency roots for useful
    absence checks. Later roots override earlier roots only for unambiguous
    virtual paths; locale/base duplicates within a root remain unresolved.
    """
    if not roots:
        raise SC2Error("missing_asset_roots", "至少需要一个地图或依赖组件目录")
    available = defaultdict(list)
    references = []
    diagnostics = []
    for root_number, root in enumerate(roots):
        base = Path(root).resolve()
        for relative, path in _files(base):
            logical = _logical(relative)
            if _asset(relative):
                available[logical.casefold()].append({"root": str(base), "root_index": root_number,
                                                       "path": relative, "logical_path": logical})
            suffix = path.suffix.casefold()
            if suffix not in {".xml", ".sc2layout", ".galaxy"} and relative not in {"Triggers", "Objects"}:
                continue
            try:
                source = path.read_bytes()
                entries = _galaxy_references(source, relative) if suffix == ".galaxy" else _xml_references(source, relative)
                for value, origin in entries:
                    references.append({"reference": value, "root": str(base), **origin})
            except SC2Error as exc:
                diagnostics.append(exc.as_dict())
    missing, resolved, unresolved = [], [], []
    for entry in references:
        value = entry["reference"]
        if _MACROS.search(value):
            unresolved.append({**entry, "reason": "engine_macro"})
            continue
        try:
            logical = _logical(_relative(value))
        except SC2Error:
            unresolved.append({**entry, "reason": "nonrelative_or_unsupported_path"})
            continue
        matches = available.get(logical.casefold(), [])
        if not matches:
            missing.append({**entry, "reason": "not_in_supplied_roots"})
            continue
        highest = max(match["root_index"] for match in matches)
        winners = [match for match in matches if match["root_index"] == highest]
        if len(winners) != 1:
            unresolved.append({**entry, "reason": "ambiguous_virtual_path", "candidates": winners})
        else:
            resolved.append({**entry, "resolved": winners[0], "shadowed": [m for m in matches if m not in winners]})
    collisions = [{"logical_path": key, "candidates": candidates} for key, candidates in available.items()
                  if len(candidates) > 1]
    return {"missing": missing, "resolved": resolved, "unresolved": unresolved, "collisions": collisions,
            "diagnostics": diagnostics, "reference_count": len(references),
            "scope": "literal_references_in_all_local_xml_and_galaxy",
            "limitations": ["Unloaded XML may contribute references.", "CASC and Battle.net dependencies must be supplied as resolved component roots.",
                            "References embedded in binary models are not inspected; absence here does not prove complete assets."],
            "complete": not diagnostics and not unresolved and not missing}


def plan_asset_import(root: Path, source: Path, destination: str,
                      overwrite: bool = False) -> dict[str, bytes | None]:
    """Return one asset candidate; never mutate the source or target directory."""
    relative = _relative(destination)
    if not _asset(relative):
        raise SC2Error("invalid_asset_destination", "导入目标必须是资源路径或已知资源格式", path=destination)
    target = _safe(root, relative)
    # Preserve existing component spelling rather than introducing a second
    # casing on case-sensitive hosts or silently aliasing directories on Windows.
    parent = Path(root).resolve()
    for part in relative.split("/")[:-1]:
        if not parent.is_dir():
            break
        aliases = [p.name for p in parent.iterdir() if p.name.casefold() == part.casefold()]
        if len(aliases) > 1 or (aliases and aliases[0] != part):
            raise SC2Error("asset_collision", "资源父目录大小写与现有路径不一致", path=relative,
                           existing=aliases, requested=part)
        parent /= part
    source = Path(source)
    if not source.is_file():
        raise SC2Error("asset_source_missing", "待导入资源不存在", source=str(source))
    if target.exists() and not target.is_file():
        raise SC2Error("asset_collision", "资源目标被目录占用", path=relative)
    # Detect physical and virtual case-insensitive collisions on every host.
    matches = [(rel, path) for rel, path in _files(root)
               if rel.casefold() == relative.casefold() or _logical(rel).casefold() == _logical(relative).casefold()]
    if matches:
        if len(matches) != 1 or matches[0][0] != relative:
            raise SC2Error("asset_collision", "资源路径大小写或虚拟路径冲突", path=relative,
                           collisions=[rel for rel, _ in matches])
        if not overwrite:
            raise SC2Error("asset_exists", "资源已存在，未指定覆盖", path=relative)
    current = target.parent
    while current != Path(root).resolve():
        if current.exists() and not current.is_dir():
            raise SC2Error("asset_collision", "资源父路径被文件占用", path=str(current))
        current = current.parent
    try:
        content = source.read_bytes()
    except OSError as exc:
        raise SC2Error("asset_source_unreadable", "无法读取待导入资源", source=str(source), error=str(exc)) from exc
    if target.is_file() and hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(content).digest():
        return {}
    return {relative: content}
