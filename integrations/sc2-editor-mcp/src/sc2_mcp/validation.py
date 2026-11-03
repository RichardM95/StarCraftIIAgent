from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import SC2Error
from .storage import map_files, safe_path

XML_COMPONENTS = {"DocumentInfo", "ComponentList.SC2Components", "Objects", "Regions", "Triggers", "Attributes"}


def lexical_balance(data: bytes):
    if data.startswith(b"\xef\xbb\xbf") or b"\0" in data:
        raise SC2Error("invalid_script_encoding", "Galaxy 含 BOM 或 NUL")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise SC2Error("invalid_script_encoding", "Galaxy 不是有效 UTF-8") from exc
    from .script import _strip_comments_strings
    cleaned, diagnostics = _strip_comments_strings(text)
    if diagnostics:
        raise SC2Error("invalid_script_lexing", "Galaxy 字符串或注释未正确闭合", diagnostics=diagnostics)
    stack = []
    pairs = {"}": "{", ")": "(", "]": "["}
    for index, char in enumerate(cleaned):
        if char in "{([":
            stack.append((char, index))
        elif char in pairs:
            if not stack or stack[-1][0] != pairs[char]:
                raise SC2Error("unbalanced_script", "Galaxy 括号配对不正确", offset=index)
            stack.pop()
    if stack:
        raise SC2Error("unbalanced_script", "Galaxy 括号未闭合", offset=stack[-1][1])
    return {"balanced": True, "compiler": "not_run"}


def validate_changes(root: Path, changes: dict, profile="generic", domain="general"):
    checked = []
    for relative, data in changes.items():
        safe_path(root, relative)
        if data is None:
            if relative in ("ComponentList.SC2Components", "DocumentInfo", "MapInfo", "BankList.xml"):
                raise SC2Error("protected_component", "不能删除核心组件", path=relative)
            continue
        p = Path(relative)
        if p.suffix.casefold() in (".xml", ".sc2layout", ".sc2components") or relative in XML_COMPONENTS:
            try:
                ET.fromstring(data)
            except ET.ParseError as exc:
                raise SC2Error("invalid_xml", "修改结果 XML 无法解析", path=relative, error=str(exc)) from exc
        if p.suffix.casefold() == ".galaxy":
            lexical_balance(data)
        if p.suffix.casefold() == ".txt":
            try:
                data.decode("utf-8")
            except UnicodeError as exc:
                raise SC2Error("invalid_text", "文本不是 UTF-8", path=relative) from exc
            if b"\0" in data:
                raise SC2Error("invalid_text", "文本含 NUL", path=relative)
        checked.append(relative)
    if any(rel.startswith('t3') or rel.startswith('CellAttribute_') for rel in changes):
        from .terrain import Terrain
        Terrain(root, changes)
    return {"static": "passed", "scope":"changed-file structure and profile guards",
            "checked_files": checked, "compiler":"not_run", "engine_semantics":"not_verified",
            "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed"}


def inspect_project(root: Path, profile="generic", cancel=None):
    errors, files = [], 0
    required=['DocumentInfo','DocumentHeader','ComponentList.SC2Components']
    if (root/'t3Terrain.xml').exists():required.append('MapInfo')
    for name in required:
        if not (root/name).is_file():errors.append({'file':name,'code':'missing_component','message':'缺少必要外壳组件'})
    for rel, path in map_files(root):
        if cancel and cancel.is_set():raise SC2Error('cancelled','验证已取消')
        if Path(rel).suffix.casefold() in (".xml", ".sc2layout", ".galaxy", ".sc2components", ".txt") or rel in XML_COMPONENTS:
            files += 1
            try:
                validate_changes(root, {rel: path.read_bytes()}, "generic")
            except SC2Error as exc:
                errors.append({"file": rel, **exc.as_dict()})
    return {"static": "failed" if errors else "passed", "files_checked": files, "errors": errors,
            "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed", "profile": profile}
