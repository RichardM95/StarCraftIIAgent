"""SC2 组件依赖解析与依赖清单规划（纯库，不写盘）。

约定：
- ``root`` 是已解析的组件根目录（通常是 ``*.SC2Map`` / ``*.SC2Mod``）。
- ``resolve_dependencies`` 只读取 ``DocumentInfo`` 中的 ``<Dependencies>``，
  跟随 ``file:`` 与 ``bnet:`` 引用；无法解析的 Battle.net 引用一律记为缺失，
  绝不伪装成已解析。
- ``plan_dependencies`` 只返回 ``dict[str, bytes | None]``，由中央服务负责提交。
  编辑采用定点字节替换，依赖块之外的字节保持不变。
- ``DocumentHeader`` 存在时仅接受通过完整结构检查的 H2CS v8，同步依赖字符串，
  未解释的固定前缀和本地化后缀逐字节保留；未知版本拒绝修改。
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from .errors import SC2Error

_BACKUP_DIR_NAMES = {"backup", "backups", ".git", "__pycache__", ".svn", ".hg"}

_ATTR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*(\"([^\"]*)\"|'([^']*)')")
_DEP_OPEN_RE = re.compile(r"<Dependencies\b([^<>]*?)(/?)>", re.IGNORECASE | re.DOTALL)
_DEP_CLOSE_RE = re.compile(r"</Dependencies\s*>", re.IGNORECASE)
_VALUE_RE = re.compile(r"<Value\b([^<>]*?)(/?)>", re.IGNORECASE | re.DOTALL)
_VALUE_CLOSE_RE = re.compile(r"</Value\s*>", re.IGNORECASE)
_DOCINFO_OPEN_RE = re.compile(r"<DocInfo\b([^<>]*?)(/?)>", re.IGNORECASE | re.DOTALL)
_DOCINFO_CLOSE_RE = re.compile(r"</DocInfo\s*>", re.IGNORECASE)
_INDENTED_LINE_RE = re.compile(r"(?m)^([ \t]+)\S")
_VALUE_INDENT_RE = re.compile(r"(?m)^([ \t]+)<Value")
_ATTR_STYLE_RE = re.compile(r"<Value\b[^<>]*\b(?:file|bnet|value)\s*=", re.IGNORECASE)
_XML_TOKEN_RE = re.compile(r'<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|</?[A-Za-z_][\w:.-]*(?:[^<>\"\x27]|\"[^\"]*\"|\x27[^\x27]*\x27)*>')


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def _norm(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:  # pragma: no cover - 仅极端文件系统
        return str(path.absolute())


def _iter_entries(directory: Path):
    try:
        return sorted(directory.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return []


def _is_backup_path(relative: Path) -> bool:
    for part in relative.parts:
        low = part.lower()
        if low in _BACKUP_DIR_NAMES or low.endswith((".bak", ".backup", "~")):
            return True
    return False


def _resolve_ci(base: Path, relative: str) -> Path | None:
    """在 ``base`` 下做大小写不敏感的相对路径解析（Windows 语义）。"""

    if not relative or relative.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", relative):
        raise SC2Error("unsafe_dependency_path", "依赖必须使用搜索根内的相对路径", path=relative)
    parts = [p for p in re.split(r"[\\/]+", relative) if p]
    if any(p in {".", ".."} or any(c in p for c in '<>:"|?*') or p.endswith((".", " ")) for p in parts):
        raise SC2Error("unsafe_dependency_path", "依赖路径包含越界或 Windows 非法片段", path=relative)
    if not parts:
        return None
    current = base
    for part in parts:
        if not current.is_dir():
            return None
        matches = [entry for entry in _iter_entries(current) if entry.name.casefold() == part.casefold()]
        if len(matches) > 1:
            raise SC2Error("dependency_case_collision", "依赖路径大小写冲突", path=relative)
        if not matches:
            return None
        current = matches[0]
        if not current.resolve().is_relative_to(base.resolve()):
            raise SC2Error("unsafe_dependency_path", "依赖链接离开搜索根", path=str(current))
    return current


def _decode_xml(data: bytes, path: Path) -> tuple[str, str]:
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data.decode("utf-8"), "utf-8"
        except UnicodeDecodeError as exc:
            raise SC2Error("unsupported_encoding", "文件不是合法 UTF-8", path=str(path), reason=str(exc))
    if data.startswith(b"\xff\xfe"):
        try:
            return data.decode("utf-16-le"), "utf-16-le"
        except UnicodeDecodeError as exc:
            raise SC2Error("unsupported_encoding", "文件不是合法 UTF-16LE", path=str(path), reason=str(exc))
    if data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16-be"), "utf-16-be"
        except UnicodeDecodeError as exc:
            raise SC2Error("unsupported_encoding", "文件不是合法 UTF-16BE", path=str(path), reason=str(exc))
    if b"\x00" in data:
        raise SC2Error("unsupported_encoding", "文件包含 NUL 字节，拒绝作为 XML 编辑", path=str(path))
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as exc:
        raise SC2Error("unsupported_encoding", "文件不是合法 UTF-8", path=str(path), reason=str(exc))


def _apply_edit(data: bytes, text: str, encoding: str, start: int, end: int, replacement: str, path: Path) -> bytes:
    """在已解码文本的 ``[start, end)`` 上做字节级定点替换。"""

    pre = text[:start].encode(encoding)
    mid = text[start:end].encode(encoding)
    post = text[end:].encode(encoding)
    if data != pre + mid + post:
        raise SC2Error(
            "encoding_roundtrip_failed",
            "编码往返校验失败，拒绝编辑以保护原始字节",
            path=str(path),
        )
    return pre + replacement.encode(encoding) + post


def _parse_attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _ATTR_RE.finditer(raw or ""):
        value = match.group(3) if match.group(3) is not None else match.group(4)
        out[match.group(1).lower()] = value
    return out


def _value_reference(attrs: dict[str, str], inner: str) -> str | None:
    if attrs.get("file") and attrs.get("bnet"):
        file_value = attrs["file"].strip()
        bnet_value = attrs["bnet"].strip()
        return (bnet_value if bnet_value.lower().startswith("bnet:") else "bnet:" + bnet_value) + "," + (file_value if file_value.lower().startswith("file:") else "file:" + file_value)
    for key in ("file", "bnet", "value"):
        raw = attrs.get(key)
        if raw is not None and raw.strip():
            value = raw.strip()
            if key == "bnet" and not value.lower().startswith("bnet:"):
                return "bnet:" + value
            if key == "file" and not value.lower().startswith("file:"):
                return "file:" + value
            return value
    if inner and inner.strip():
        return inner.strip()
    return None


def _classify_reference(reference: str) -> tuple[str, str]:
    parts = _reference_parts(reference)
    if parts.get("file"):
        return "file", parts["file"]
    if parts.get("bnet"):
        return "bnet", parts["bnet"]
    raise SC2Error("invalid_dependency_value", "没有可解析的依赖引用", reference=reference)


def _reference_parts(reference: str) -> dict[str, str]:
    """A single SC2 reference can carry both depot identity and local path."""
    reference = reference.strip()
    result = {}
    for item in re.split(r",(?=\s*(?:file|bnet):)", reference, flags=re.I):
        item = item.strip()
        match = re.match(r"^(file|bnet):(.*)$", item, re.I | re.S)
        if match:
            key, value = match.group(1).lower(), match.group(2).strip()
        else:
            key, value = "file", item
        if not value or key in result:
            raise SC2Error("invalid_dependency_value", "依赖引用为空或包含重复方案", reference=reference)
        result[key] = value
    return result


def _validate_dependency_value(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SC2Error("invalid_dependency_value", "依赖值必须是非空字符串", value=value)
    text = value.strip()
    if any(ch in text for ch in "<>\"'") or any(ord(ch) < 32 for ch in text):
        raise SC2Error("invalid_dependency_value", "依赖值包含非法字符", value=value)
    parts = _reference_parts(text)
    if "file" in parts:
        # Validate without consulting the filesystem. _resolve_ci also checks
        # links when actual resolution runs.
        path = parts["file"]
        if path.startswith(("/", "\\")) or any(p in {".", ".."} or ":" in p for p in re.split(r"[\\/]+", path)):
            raise SC2Error("unsafe_dependency_path", "依赖路径不能越过搜索根", path=path)
    return text


# --------------------------------------------------------------------------- #
# DocumentInfo 解析 / 渲染
# --------------------------------------------------------------------------- #
def _parse_document_info(text: str, path: Path) -> dict:
    info: dict = {
        "values": [],
        "span": None,
        "open_end": None,
        "close_start": None,
        "self_closing": False,
        "open_tag": None,
        "close_tag": None,
        "indent": "",
        "declarations": [],
    }
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise SC2Error("unsafe_document_info", "DocumentInfo 不允许 DTD 或实体声明", path=str(path))
    try:
        document = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SC2Error("malformed_document_info", "DocumentInfo XML 不能解析", path=str(path), reason=str(exc)) from exc
    if document.tag != "DocInfo":
        raise SC2Error("malformed_document_info", "DocumentInfo 根节点必须为 DocInfo", path=str(path))
    dependencies = list(document.findall("Dependencies"))
    if len(dependencies) > 1:
        raise SC2Error("ambiguous_dependencies", "DocumentInfo 有多个直接 Dependencies 节点", path=str(path))
    spans = _document_spans(text)
    info["root_span"] = spans
    dep_spans = [span for span in spans["children"] if span["tag"] == "Dependencies"]
    if not dependencies:
        return info
    dep = dep_spans[0]
    info.update({"open_tag": text[dep["start"]:dep["open_end"]], "span": (dep["start"], dep["end"]),
                 "open_end": dep["open_end"], "close_start": dep["close_start"], "self_closing": dep["self_closing"],
                 "close_tag": text[dep["close_start"]:dep["end"]] if not dep["self_closing"] else None})
    line_start = text.rfind("\n", 0, dep["start"]) + 1
    prefix = text[line_start:dep["start"]]
    info["indent"] = prefix if not prefix.strip() else ""
    value_spans = [span for span in dep["children"] if span["tag"] == "Value"]
    elements = list(dependencies[0])
    if any(element.tag != "Value" for element in elements):
        raise SC2Error("unsupported_dependency_element", "Dependencies 中包含未知元素", path=str(path))
    for ordinal, (element, span) in enumerate(zip(elements, value_spans, strict=True)):
        if len(element):
            raise SC2Error("unsupported_dependency_value", "依赖 Value 不能包含子元素", path=str(path))
        attrs = {key.lower(): value for key, value in element.attrib.items()}
        reference = _value_reference(attrs, element.text or "")
        if reference is not None:
            info["values"].append(reference)
            info["declarations"].append({"reference": reference, "ordinal": ordinal,
                                         "line": text.count("\n", 0, span["start"]) + 1,
                                         "span": (span["start"], span["end"]), "source": str(path)})
    return info


def _document_spans(text: str) -> dict:
    """Token spans after XML validation; comments/CDATA/PIs cannot become tags."""
    stack = []
    root = None
    for token in _XML_TOKEN_RE.finditer(text):
        raw = token.group()
        if raw.startswith(("<!--", "<![CDATA[", "<?")):
            continue
        if raw.startswith("</"):
            span = stack.pop()
            span["close_start"], span["end"] = token.start(), token.end()
            continue
        tag = re.match(r"<([\w:.-]+)", raw).group(1)
        span = {"tag": tag, "start": token.start(), "open_end": token.end(), "end": token.end(),
                "close_start": token.end(), "self_closing": raw.endswith("/>"), "children": []}
        if stack:
            stack[-1]["children"].append(span)
        else:
            root = span
        if not span["self_closing"]:
            stack.append(span)
    return root


def _detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _detect_unit(text: str, default: str = "  ") -> str:
    previous = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        if indent > previous:
            return line[:indent]
        previous = indent
    return default


def _format_value(reference: str, attr_style: bool) -> str:
    safe = escape(reference, {'"': "&quot;", "'": "&apos;"})
    if attr_style:
        if len(_reference_parts(reference)) > 1:
            return f'<Value value="{safe}"/>'
        low = reference.lower()
        if low.startswith("bnet:"):
            return f'<Value bnet="{safe[5:]}"/>'
        if low.startswith("file:"):
            return f'<Value file="{safe[5:]}"/>'
        return f'<Value value="{safe}"/>'
    return f"<Value>{safe}</Value>"


def _render_dependencies(body: str, values: list[str], indent: str, newline: str, unit: str) -> str:
    if not values:
        return ""
    indent_match = _VALUE_INDENT_RE.search(body)
    child_indent = indent_match.group(1) if indent_match else indent + unit
    attr_style = bool(_ATTR_STYLE_RE.search(body))
    lines = "".join(child_indent + _format_value(value, attr_style) + newline for value in values)
    return newline + lines + indent


def _apply_dependency_values(text: str, info: dict, values: list[str]) -> str:
    """返回包含 ````<Dependencies>```` 的替换文本。"""

    if info["values"] == values:
        return text[info["span"][0]:info["span"][1]]
    # Replace only active Value elements. In particular, never erase comments
    # or surrounding metadata merely because they sit in Dependencies.
    if info["declarations"]:
        block_start, block_end = info["span"]
        block = text[block_start:block_end]
        edits = []
        declarations = info["declarations"]
        for position, declaration in enumerate(declarations):
            start, end = declaration["span"]
            if position >= len(values):
                replacement = ""
            elif declaration["reference"] == values[position]:
                continue
            else:
                replacement = _replace_value_text(text[start:end], values[position])
            edits.append((start - block_start, end - block_start, replacement))
        if len(values) > len(declarations):
            newline = _detect_newline(text)
            unit = _detect_unit(text)
            body = text[info["open_end"]:info["close_start"]]
            indent_match = _VALUE_INDENT_RE.search(body)
            child_indent = indent_match.group(1) if indent_match else info["indent"] + unit
            closing = info["close_start"]
            line_start = text.rfind("\n", 0, closing) + 1
            tail = text[line_start:closing]
            if not tail.strip():
                insert_at = line_start
                prefix = ""
            else:
                insert_at = closing
                prefix = newline
            attr_style = bool(_ATTR_STYLE_RE.search(body))
            inserted = prefix + "".join(child_indent + _format_value(value, attr_style) + newline for value in values[len(declarations):])
            edits.append((insert_at - block_start, insert_at - block_start, inserted))
        for start, end, replacement in sorted(edits, reverse=True):
            block = block[:start] + replacement + block[end:]
        return block

    indent = info.get("indent") or ""
    if not indent:
        indent = _detect_unit(text)
    unit = _detect_unit(text)
    newline = _detect_newline(text)
    if info["self_closing"]:
        body = ""
        open_tag = info["open_tag"][:-2].rstrip() + ">"
    else:
        body = text[info["open_end"]:info["close_start"]]
        open_tag = info["open_tag"]
    if not values:
        if info["self_closing"]:
            return info["open_tag"]
        return open_tag + info["close_tag"]
    inner = _render_dependencies(body, values, indent, newline, unit)
    return open_tag + inner + "</Dependencies>"


def _replace_value_text(raw: str, reference: str) -> str:
    """Preserve a Value's unknown attributes and quote style when possible."""
    span = _document_spans(raw)
    element = ET.fromstring(raw)
    reference_attrs = {name.lower() for name in element.attrib} & {"file", "bnet", "value"}
    if not reference_attrs:
        if "<!--" in raw or "<![CDATA[" in raw:
            raise SC2Error("unsupported_dependency_value", "带内嵌注释或 CDATA 的 Value 需要专门编辑，已保留原文")
        safe = escape(reference)
        if span["self_closing"]:
            return raw[:span["open_end"] - 2] + ">" + safe + "</Value>"
        return raw[:span["open_end"]] + safe + raw[span["close_start"]:]
    parts = _reference_parts(reference)
    selected = next(iter(parts)) if len(parts) == 1 else "value"
    new_value = parts[selected] if selected != "value" else reference
    safe = escape(new_value, {'"': "&quot;", "'": "&apos;"})
    opening = raw[:span["open_end"]]
    edits = []
    replaced = False
    for match in _ATTR_RE.finditer(opening):
        if match.group(1).lower() not in reference_attrs:
            continue
        if not replaced:
            quote = match.group(2)[0]
            replacement = f"{selected}={quote}{safe}{quote}"
            replaced = True
        else:
            replacement = ""
        edits.append((match.start(), match.end(), replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw


def _insertion_for_dependencies(text: str, values: list[str], path: Path) -> tuple[int, str]:
    span = _parse_document_info(text, path)["root_span"]
    if span["self_closing"]:
        raise SC2Error("malformed_document_info", "DocumentInfo 的 <DocInfo> 为自闭合，无法插入依赖", path=str(path))
    newline = _detect_newline(text)
    unit = _detect_unit(text)
    line_start = text.rfind("\n", 0, span["close_start"]) + 1
    between = text[line_start:span["close_start"]]
    if between.strip() == "":
        insert_at = line_start
        doc_indent = between
        prefix = ""
    else:
        insert_at = span["close_start"]
        doc_indent = ""
        prefix = newline
    indent = doc_indent + unit
    body = ""
    inner = _render_dependencies(body, values, indent, newline, unit)
    block = prefix + indent + "<Dependencies>" + inner + "</Dependencies>" + newline
    return insert_at, block


# --------------------------------------------------------------------------- #
# 公共 API：解析
# --------------------------------------------------------------------------- #
def _resolve_graph(root: Path, search_roots: list[Path], root_values: list[str] | None = None) -> dict:
    """递归解析组件依赖，返回可 JSON 序列化的依赖图。"""

    root_path = Path(root)
    if not root_path.is_dir():
        raise SC2Error("invalid_root", "组件根必须是已存在的目录", path=str(root_path))
    roots = [Path(p) for p in (search_roots or [])]

    nodes: list[dict] = []
    edges: list[dict] = []
    missing: list[dict] = []
    warnings: list[str] = []
    cycles: list[list[str]] = []
    order: list[str] = []
    visited: set[str] = set()
    visiting: list[str] = []
    incomplete: list[dict] = []

    def record_cycle(cycle: list[str]) -> None:
        if cycle not in cycles:
            cycles.append(cycle)
            warnings.append("检测到循环依赖: " + " -> ".join(cycle))

    def resolve_target(relative: str, origin: Path) -> Path | None:
        for base in [origin if origin.is_dir() else origin.parent, *roots]:
            found = _resolve_ci(base, relative)
            if found is not None:
                return found
        if not Path(relative).suffix:
            for suffix in (".SC2Mod", ".SC2Map"):
                for base in [origin if origin.is_dir() else origin.parent, *roots]:
                    found = _resolve_ci(base, relative + suffix)
                    if found is not None:
                        return found
        return None

    def visit(component: Path, kind: str) -> None:
        key = _norm(component)
        if key in visiting:
            index = visiting.index(key)
            record_cycle(visiting[index:] + [key])
            return
        if key in visited:
            return
        visiting.append(key)

        container = component.is_dir()
        values: list[str] = []
        declarations: list[dict] = []
        metadata_source = str(component / "DocumentInfo") if container else f"{component}!DocumentInfo"
        metadata_complete = False
        if not container:
            try:
                import mpyq
                with component.open("rb") as stream:
                    archive = mpyq.MPQArchive(stream, listfile=False)
                    raw_docinfo = archive.read_file("DocumentInfo")
                if not raw_docinfo:
                    raise SC2Error("missing_document_info", "归档缺少 DocumentInfo")
                text, _encoding = _decode_xml(raw_docinfo, Path(metadata_source))
                parsed = _parse_document_info(text, Path(metadata_source))
                values, declarations = parsed["values"], parsed["declarations"]
                metadata_complete = True
            except Exception as exc:
                reason = exc.code if isinstance(exc, SC2Error) else "archive_metadata_unreadable"
                incomplete.append({"path": key, "reason": reason, "source": metadata_source, "detail": str(exc)})
                warnings.append(f"归档依赖元数据未解析: {component} ({reason})")
        else:
            docinfo = _resolve_ci(component, "DocumentInfo")
            if docinfo is None or not docinfo.is_file():
                if kind == "root":
                    raise SC2Error("missing_document_info", "组件根缺少 DocumentInfo", path=str(component))
                warnings.append(f"依赖缺少 DocumentInfo，递归完整性未知: {component}")
                incomplete.append({"path": key, "reason": "missing_document_info", "source": metadata_source})
            else:
                text, _encoding = _decode_xml(docinfo.read_bytes(), docinfo)
                parsed = _parse_document_info(text, docinfo)
                values, declarations = parsed["values"], parsed["declarations"]
                metadata_source = str(docinfo)
                metadata_complete = True

        node = {
            "path": key,
            "name": component.name,
            "kind": kind,
            "container": container,
            "dependencies": list(values),
            "resolved_dependencies": [],
            "metadata_source": metadata_source,
            "metadata_complete": metadata_complete,
        }
        if kind == "root" and root_values is not None:
            values = list(root_values)
            declarations = [{"reference": value, "ordinal": ordinal, "line": None,
                             "source": metadata_source} for ordinal, value in enumerate(values)]
            node["dependencies"] = list(values)
        nodes.append(node)

        for reference, declaration in zip(values, declarations, strict=True):
            declared_sources = _reference_parts(reference)
            ref_kind, relative = _classify_reference(reference)
            edge_source = {"file": declaration["source"], "line": declaration["line"], "ordinal": declaration["ordinal"]}
            if ref_kind == "bnet":
                missing.append(
                    {
                        "reference": reference,
                        "kind": "bnet",
                        "requested_by": key,
                        "reason": "battle_net_reference_not_resolved",
                        "source": edge_source,
                    }
                )
                edges.append({"from": key, "to": None, "reference": reference, "resolved": False, "source": edge_source, "declared_sources": declared_sources})
                warnings.append(f"未解析的 Battle.net 引用: {reference}")
                continue
            target = resolve_target(relative, component)
            if target is None:
                missing.append(
                    {
                        "reference": reference,
                        "kind": "file",
                        "requested_by": key,
                        "relative": relative,
                        "reason": "file_not_found",
                        "source": edge_source,
                    }
                )
                edges.append({"from": key, "to": None, "reference": reference, "resolved": False, "source": edge_source, "declared_sources": declared_sources})
                continue
            target_key = _norm(target)
            node["resolved_dependencies"].append(target_key)
            edge = {"from": key, "to": target_key, "reference": reference, "resolved": True,
                    "source": edge_source, "declared_sources": declared_sources, "resolved_via": "file",
                    "bnet_identity_verified": False if "bnet" in declared_sources else None}
            edges.append(edge)
            visit(target, "dependency")

        visiting.pop()
        visited.add(key)
        order.append(key)

    visit(root_path, "root")

    return {
        "nodes": nodes,
        "edges": edges,
        "load_order": order,
        "missing": missing,
        "cycles": cycles,
        "complete": not missing and not cycles and not incomplete,
        "incomplete": incomplete,
        "warnings": warnings,
    }


def resolve_dependencies(root: Path, search_roots: list[Path]) -> dict:
    """Resolve the actual DocumentInfo graph; this never writes a component."""
    return _resolve_graph(root, search_roots)


def resolve_proposed_dependencies(root: Path, search_roots: list[Path], values: list[str]) -> dict:
    """Resolve a proposed root declaration while reading unchanged dependencies."""
    return _resolve_graph(root, search_roots, [_validate_dependency_value(v) for v in values])


def decode_declarations(data: bytes) -> list[str]:
    """Use the same active-element parser for all supported Value syntaxes."""
    path=Path('DocumentInfo')
    text,_encoding=_decode_xml(data,path)
    return _parse_document_info(text,path)['values']


# --------------------------------------------------------------------------- #
# 公共 API：规划
# --------------------------------------------------------------------------- #
def plan_dependencies(root: Path, values: list[str]) -> dict[str, bytes | None]:
    """同步规划 DocumentInfo 与已验证 H2CS v8 头部；不写盘。"""

    root_path = Path(root)
    if not root_path.is_dir():
        raise SC2Error("invalid_root", "组件根必须是已存在的目录", path=str(root_path))

    docinfo = _resolve_ci(root_path, "DocumentInfo")
    if docinfo is None or not docinfo.is_file():
        raise SC2Error("missing_document_info", "组件根缺少 DocumentInfo", path=str(root_path))

    normalized = [_validate_dependency_value(value) for value in values]
    data = docinfo.read_bytes()
    text, encoding = _decode_xml(data, docinfo)
    info = _parse_document_info(text, docinfo)
    header = _resolve_ci(root_path, "DocumentHeader")
    header_candidate = None
    if header is not None:
        from .shell import replace_header_dependencies
        try:
            header_candidate = replace_header_dependencies(header.read_bytes(), info["values"], normalized)
        except SC2Error as exc:
            if exc.code == "unsupported_header":
                raise SC2Error("unsupported_header", str(exc), path=str(header), requirement="document_header_codec",
                               operation="plan_dependencies", **exc.details) from exc
            raise

    if info["span"] is None:
        if not normalized:
            return {}
        start, replacement = _insertion_for_dependencies(text, normalized, docinfo)
        new_data = _apply_edit(data, text, encoding, start, start, replacement, docinfo)
    else:
        replacement = _apply_dependency_values(text, info, normalized)
        if replacement == text[info["span"][0]:info["span"][1]]:
            return {}
        new_data = _apply_edit(data, text, encoding, info["span"][0], info["span"][1], replacement, docinfo)

    candidate_text, _ = _decode_xml(new_data, docinfo)
    candidate_info = _parse_document_info(candidate_text, docinfo)
    if candidate_info["values"] != normalized:
        raise SC2Error("dependency_candidate_mismatch", "候选依赖清单与请求不一致，拒绝写入")
    result = {docinfo.name: new_data}
    if header_candidate is not None and header_candidate != header.read_bytes():
        result[header.name] = header_candidate
    return result


def analyze_dependency_impact(root: Path, values: list[str], search_roots: list[Path],
                              catalogs: list[str] | None = None, limit: int = 10000, *,
                              before_context: dict | None = None, after_context: dict | None = None) -> dict:
    """Compare a proposed dependency order without writing temporary maps.

    ``limit`` caps returned object/field details, never the computed counts.
    Callers should select catalogs to bound computation. Archives must first
    be materialized as component roots by the host for Catalog comparison;
    metadata-only archive resolution is explicitly reported as incomplete.
    """
    from .catalog import CatalogSession

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100000:
        raise SC2Error("invalid_impact_limit", "limit 必须在 1 到 100000 之间")
    normalized = [_validate_dependency_value(value) for value in values]
    selected_catalogs = list(dict.fromkeys(catalogs if catalogs is not None else
                                         ["Unit", "Abil", "Weapon", "Effect", "Behavior", "Actor", "Model"]))
    if not selected_catalogs:
        raise SC2Error("impact_catalogs_required", "至少选择一个 Catalog 类型")
    if (before_context is None) != (after_context is None):
        raise SC2Error("source_context_pair_required", "影响分析需要同时提供 before/after 来源上下文")
    if before_context is not None:
        from .source_context import assert_source_context_current
        for context in (before_context, after_context):
            assert_source_context_current(context)
            if Path(context["root"]).resolve() != Path(root).resolve():
                raise SC2Error("source_context_root_mismatch", "影响分析上下文不是目标图")
        declared = next(node["dependencies"] for node in after_context["dependency_report"]["nodes"] if node["kind"] == "root")
        if declared != normalized:
            raise SC2Error("source_context_declarations_mismatch", "after 上下文与请求依赖声明不一致")
        before_declared = next(node["dependencies"] for node in before_context["dependency_report"]["nodes"] if node["kind"] == "root")
        actual_info = _resolve_ci(Path(root), "DocumentInfo")
        if actual_info is None or before_declared != decode_declarations(actual_info.read_bytes()):
            raise SC2Error("source_context_declarations_mismatch", "before 上下文不是目标图的真实依赖声明")
        before_graph, after_graph = before_context["dependency_report"], after_context["dependency_report"]
    else:
        before_graph = resolve_dependencies(root, search_roots)
        after_graph = _resolve_graph(root, search_roots, normalized)
    unresolved = []
    for label, graph in (("before", before_graph), ("after", after_graph)):
        context = before_context if label == "before" else after_context
        if context is not None and not context.get("complete"):
            unresolved.extend({"phase": label, "kind": "source_context_unknown", "detail": issue}
                              for issue in context.get("unknown", []) if issue.get("code") != "client_build_not_selected")
        for name in ("missing", "incomplete", "cycles"):
            for issue in graph[name]:
                unresolved.append({"phase": label, "kind": name, "detail": issue})
        for path in graph["load_order"]:
            if before_context is None and not Path(path).is_dir():
                unresolved.append({"phase": label, "kind": "archive_catalog_not_materialized", "path": path})
    before_roots = [Path(path) for path in before_context["roots"]] if before_context else [Path(path) for path in before_graph["load_order"] if Path(path).is_dir()]
    after_roots = [Path(path) for path in after_context["roots"]] if after_context else [Path(path) for path in after_graph["load_order"] if Path(path).is_dir()]
    before = CatalogSession(before_roots)
    after = before if before_roots == after_roots else CatalogSession(after_roots)
    added, removed, changed = [], [], []
    counts = {"added_objects": 0, "removed_objects": 0, "changed_objects": 0,
              "changed_fields": 0, "compared_objects": 0}
    retained_details = 0
    truncated = False
    for kind in selected_catalogs:
        old_ids, new_ids = set(before.object_ids(kind)), set(after.object_ids(kind))
        for label, identifiers, session, output in (("added_objects", new_ids - old_ids, after, added),
                                                    ("removed_objects", old_ids - new_ids, before, removed)):
            counts[label] += len(identifiers)
            for object_id in sorted(identifiers):
                if retained_details >= limit:
                    truncated = True
                    continue
                try:
                    item = session.inspect(kind, object_id)
                    output.append({"catalog": kind, "object_id": object_id, "sources": item["sources"]})
                    retained_details += 1
                except SC2Error as exc:
                    unresolved.append({"catalog": kind, "object_id": object_id, "error": exc.as_dict()})
        for object_id in sorted(old_ids & new_ids):
            counts["compared_objects"] += 1
            if before is after:
                continue
            try:
                old, new = before.inspect(kind, object_id), after.inspect(kind, object_id)
            except SC2Error as exc:
                unresolved.append({"catalog": kind, "object_id": object_id, "error": exc.as_dict()})
                continue
            field_changes = []
            for field in sorted(set(old["fields"]) | set(new["fields"])):
                old_field, new_field = old["fields"].get(field), new["fields"].get(field)
                if old_field == new_field:
                    continue
                counts["changed_fields"] += 1
                if len(field_changes) < limit:
                    field_changes.append({"field": field, "before": old_field, "after": new_field})
                else:
                    truncated = True
            structural = old["class"] != new["class"] or old["inheritance"] != new["inheritance"] or old["removed"] != new["removed"]
            if field_changes or structural:
                counts["changed_objects"] += 1
                if retained_details < limit:
                    changed.append({"catalog": kind, "object_id": object_id, "fields": field_changes,
                                    "before_inheritance": old["inheritance"], "after_inheritance": new["inheritance"],
                                    "before_removed": old["removed"], "after_removed": new["removed"],
                                    "before_class": old["class"], "after_class": new["class"]})
                    retained_details += 1
                else:
                    truncated = True
            for label, inspected in (("before", old), ("after", new)):
                for issue in inspected["warnings"]:
                    if issue["code"] in {"missing_catalog_parent", "unevaluated_catalog_expression", "catalog_class_changed"}:
                        unresolved.append({"phase": label, "catalog": kind, "object_id": object_id, "detail": issue})
    return {"before": before_graph, "after": after_graph, "catalogs": selected_catalogs,
            "added": added, "removed": removed, "changed": changed, "counts": counts,
            "unresolved": unresolved, "truncated": truncated,
            "complete": before_graph["complete"] and after_graph["complete"] and not unresolved,
            "validation": "static", "engine_parity": False,
            "limitations": ["报告使用 Catalog 静态合并规则，不是编辑器或游戏验收", "统计覆盖所选类型，details 受 limit 限制"]}
