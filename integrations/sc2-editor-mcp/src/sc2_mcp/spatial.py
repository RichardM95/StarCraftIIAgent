"""Read SC2 spatial components and build byte-preserving candidate edits.

This module never writes a map. Positions and scales are three comma-separated
finite numbers; rotation/pitch/roll are radians as stored by the editor. Region
rectangles are [left, bottom, right, top]. Existing IDs cannot be changed.
Camera schemas are accepted only when already present in the supplied map.
Static literal-reference checks are not a Galaxy compiler or runtime proof.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.parsers import expat
from xml.sax.saxutils import escape

from .errors import SC2Error

_KINDS = {"ObjectUnit", "ObjectDoodad", "ObjectPoint", "Camera", "ObjectCamera", "Group"}
_ALIASES = {"unit": "ObjectUnit", "doodad": "ObjectDoodad", "point": "ObjectPoint",
            "camera": "Camera", "group": "Group"}
_EXCLUDED = {"_codex_backups", ".git", ".venv", "__pycache__", ".pytest_cache", ".sc2-mcp"}
_ATTR = re.compile(rb'''([A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*(["'])(.*?)\2''', re.S)
_BASE_ATTRIBUTES = {
    "ObjectUnit": {"Id", "Position", "Rotation", "Scale", "UnitType", "Player", "Name"},
    "ObjectDoodad": {"Id", "Position", "Rotation", "Scale", "Type", "Variation", "Name",
                     "Pitch", "Roll", "TintColor", "TeamColor"},
    "ObjectPoint": {"Id", "Position", "Rotation", "Scale", "Type", "Name", "Color"},
    "Group": {"Id", "Type", "Name"},
    "Camera": {"Id", "Name"},
    "ObjectCamera": {"Id", "Name"},
}
_ID_FUNCTIONS = {
    "ObjectUnit": {"UnitFromId"},
    "ObjectDoodad": {"DoodadFromId"},
    "ObjectPoint": {"PointFromId"},
    "Camera": {"CameraFromId", "CameraInfoFromId"},
    "ObjectCamera": {"CameraFromId", "CameraInfoFromId"},
    "Group": {"GroupFromId", "ObjectGroupFromId", "UnitGroupFromId", "DoodadGroupFromId"},
    "region": {"RegionFromId"},
}
_KNOWN_ID_FUNCTIONS = set().union(*_ID_FUNCTIONS.values())


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    start: int
    open_end: int
    close_start: int = 0
    end: int = 0
    children: list["_Node"] = field(default_factory=list)


def _path(root: Path, name: str) -> Path:
    base = Path(root).resolve()
    if not base.is_dir():
        raise SC2Error("missing_project", "地图组件目录不存在", path=str(root))
    target = base / name
    current = target
    while current != base:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise SC2Error("linked_path", "组件路径不能通过符号链接或目录联接", path=name)
        current = current.parent
    if not target.resolve().is_relative_to(base):
        raise SC2Error("path_escape", "组件路径越出地图目录", path=name)
    return target


def _read(root: Path, name: str) -> bytes:
    target = _path(root, name)
    if not target.is_file():
        raise SC2Error("missing_component", "地图缺少组件", component=name)
    try:
        return target.read_bytes()
    except OSError as exc:
        raise SC2Error("component_read_failed", "无法读取组件", component=name, error=str(exc)) from exc


def _tag_end(data: bytes, start: int) -> int:
    quote = None
    for i in range(start, len(data)):
        b = data[i]
        if quote is not None:
            if b == quote:
                quote = None
        elif b in (34, 39):
            quote = b
        elif b == 62:
            return i + 1
    raise SC2Error("invalid_xml", "XML 标签未结束")


def _parse(data: bytes, component: str) -> _Node:
    if b"\0" in data:
        raise SC2Error("invalid_xml", "XML 组件含 NUL 或非 UTF-8 编码", component=component)
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SC2Error("unsupported_encoding", "仅支持 UTF-8 空间组件", component=component) from exc
    parser = expat.ParserCreate()
    stack: list[_Node] = []
    document: list[_Node] = []

    def start(tag, attrs):
        offset = parser.CurrentByteIndex
        node = _Node(tag, dict(attrs), offset, _tag_end(data, offset))
        if stack:
            stack[-1].children.append(node)
        else:
            document.append(node)
        stack.append(node)

    def end(tag):
        node = stack.pop()
        if data[node.start:node.open_end].rstrip().endswith(b"/>"):
            node.close_start = node.open_end - 2
            node.end = node.open_end
        else:
            node.close_start = parser.CurrentByteIndex
            node.end = _tag_end(data, node.close_start)

    def forbid(*args):
        raise SC2Error("unsupported_xml", "空间组件不允许 DTD 或实体声明", component=component)

    def declaration(version, encoding, standalone):
        if encoding and encoding.lower().replace("-", "") != "utf8":
            raise SC2Error("unsupported_encoding", "仅支持 UTF-8 空间组件", component=component)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = forbid
    parser.EntityDeclHandler = forbid
    parser.ExternalEntityRefHandler = forbid
    parser.XmlDeclHandler = declaration
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise SC2Error("invalid_xml", "无法解析空间组件", component=component, error=str(exc)) from exc
    if len(document) != 1:
        raise SC2Error("invalid_xml", "空间组件必须有唯一根元素", component=component)
    return document[0]


def _load(root: Path, component: str) -> tuple[bytes, _Node]:
    data = _read(root, component)
    node = _parse(data, component)
    expected = {"Objects": "PlacedObjects", "Regions": "Regions"}[component]
    if node.tag != expected:
        raise SC2Error("unsupported_spatial_format", "未知空间组件根元素", component=component, root=node.tag)
    return data, node


def _id(value: str | int) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise SC2Error("invalid_spatial_id", "空间对象 ID 必须为十进制正整数", value=value)
    number = int(value)
    if not 0 < number <= 2147483647:
        raise SC2Error("invalid_spatial_id", "空间对象 ID 超出正 32 位整数范围", value=value)
    return number


def _unique(nodes: list[_Node], value: str | int, attr: str = "Id") -> _Node:
    number = _id(value)
    matches = [n for n in nodes if n.attrs.get(attr, "").isdigit() and int(n.attrs[attr]) == number]
    if len(matches) != 1:
        raise SC2Error("ambiguous_spatial_id" if matches else "spatial_object_not_found",
                       "空间对象 ID 不唯一或不存在", object_id=str(value), count=len(matches))
    return matches[0]


def _check_ids(nodes: list[_Node], attr: str = "Id") -> None:
    seen = set()
    for node in nodes:
        if attr not in node.attrs:
            raise SC2Error("invalid_spatial_id", "空间对象缺少 ID", kind=node.tag)
        number = _id(node.attrs[attr])
        if number in seen:
            raise SC2Error("ambiguous_spatial_id", "空间对象 ID 冲突", object_id=str(number))
        seen.add(number)


def _finite(value: str, count: int, attr: str, positive=False) -> list[float]:
    try:
        parts = value.split(",")
        nums = [float(p) for p in parts]
    except (ValueError, AttributeError) as exc:
        raise SC2Error("invalid_spatial_number", "空间属性必须是有限数字", attribute=attr, value=value) from exc
    if len(nums) != count or any(not math.isfinite(n) or (positive and n <= 0) for n in nums):
        raise SC2Error("invalid_spatial_number", "空间属性维度、范围或数字无效", attribute=attr, value=value)
    return nums


def _value(value: str) -> str:
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise SC2Error("invalid_xml_value", "XML 属性必须是没有控制字符的字符串")
    # Reject XML-invalid code points before a candidate is returned.
    if any(0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        raise SC2Error("invalid_xml_value", "XML 属性含无效 Unicode 字符")
    return escape(value, {'"': "&quot;", "'": "&apos;"})


def _attributes(kind: str, values: dict[str, str], observed: set[str]) -> None:
    if not isinstance(values, dict):
        raise SC2Error("invalid_spatial_attributes", "空间属性必须是字典")
    allowed = _BASE_ATTRIBUTES[kind] | observed
    for key, value in values.items():
        if key not in allowed:
            raise SC2Error("unsupported_spatial_attribute", "属性尚无该对象格式依据", kind=kind, attribute=key)
        _value(value)
        if key == "Id":
            _id(value)
        elif key in {"Position", "Scale", "Target"}:
            _finite(value, 3, key, positive=key == "Scale")
        elif key in {"Rotation", "Pitch", "Roll", "Distance", "Yaw", "FieldOfView", "NearClip", "FarClip"}:
            _finite(value, 1, key)
        elif key in {"Player", "Variation", "TeamColor"}:
            if not re.fullmatch(r"[0-9]+", value):
                raise SC2Error("invalid_spatial_number", "属性必须是非负整数", attribute=key)
        elif key in {"Type", "UnitType"} and not value:
            raise SC2Error("invalid_spatial_attributes", "对象类型不能为空", attribute=key)


def _patch_attributes(data: bytes, node: _Node, changes: dict[str, str]) -> bytes:
    opening = data[node.start:node.open_end]
    offsets = {m.group(1).decode("ascii"): m for m in _ATTR.finditer(opening)}
    replacements = []
    appended = []
    for key, value in changes.items():
        if node.attrs.get(key) == value:
            continue
        escaped = _value(value).encode("utf-8")
        if key in offsets:
            match = offsets[key]
            replacements.append((match.start(3), match.end(3), escaped))
        else:
            appended.append(b" " + key.encode("ascii") + b'="' + escaped + b'"')
    for start, end, value in sorted(replacements, reverse=True):
        opening = opening[:start] + value + opening[end:]
    if appended:
        offset = len(opening) - (2 if opening.endswith(b"/>") else 1)
        opening = opening[:offset] + b"".join(appended) + opening[offset:]
    return data[:node.start] + opening + data[node.open_end:]


def _candidate(component: str, before: bytes, after: bytes) -> dict[str, bytes | None]:
    _parse(after, component)
    return {} if before == after else {component: after}


def _files(root: Path):
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d.casefold() not in _EXCLUDED]
        for name in dirs:
            child = Path(directory) / name
            if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                raise SC2Error("reference_scan_failed", "引用扫描不能越过目录链接", path=str(child))
        for name in files:
            if name.casefold().endswith(".galaxy") or name.casefold() == "triggers":
                relative = (Path(directory) / name).relative_to(root).as_posix()
                yield relative, _read(root, relative)


def _galaxy_tokens(text: str) -> tuple[str, list[tuple[str, int]]]:
    """Mask comments and strings without shifting offsets; retain string values."""
    tokens = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"')
    strings = []
    masked = list(text)
    for match in tokens.finditer(text):
        if match.group().startswith('"'):
            value = re.sub(r'\\(["\\])', r'\1', match.group()[1:-1])
            strings.append((value, match.start()))
        masked[match.start():match.end()] = ["\n" if c == "\n" else " " for c in match.group()]
    return "".join(masked), strings


def _references(root: Path, node: _Node, name_only: bool = False) -> list[dict]:
    identifier = int(node.attrs.get("Id", node.attrs.get("id", "0")))
    names = [node.attrs["Name"]] if node.attrs.get("Name") else []
    if node.tag == "region":
        names += [child.attrs["value"] for child in node.children if child.tag == "name" and child.attrs.get("value")]
    result = []
    # XML and Galaxy can refer to objects by stable ID or by literal name.
    for relative, data in _files(Path(root).resolve()):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SC2Error("reference_scan_failed", "无法检查非 UTF-8 脚本引用", source=relative) from exc
        if relative.casefold().endswith(".galaxy"):
            masked, strings = _galaxy_tokens(text)
            if not name_only:
                for match in re.finditer(r"\b([A-Za-z_]\w*FromId)\s*\(\s*(0[xX][0-9a-fA-F]+|[0-9]+)\s*\)", masked):
                    literal = match.group(2)
                    number = int(literal, 16 if literal.lower().startswith("0x") else 10)
                    function = match.group(1)
                    compatible = function in _ID_FUNCTIONS[node.tag] or function not in _KNOWN_ID_FUNCTIONS
                    if number == identifier and compatible:
                        result.append({"source": relative, "line": text.count("\n", 0, match.start()) + 1,
                                       "kind": "galaxy_literal_id", "function": match.group(1)})
            for value, start in strings:
                if value in names:
                    result.append({"source": relative, "line": text.count("\n", 0, start) + 1,
                                   "kind": "galaxy_literal_name", "value": value})
        else:
            trigger = _parse(data, relative)
            pending = [trigger]
            while pending:
                current = pending.pop()
                pending.extend(current.children)
                for key, value in current.attrs.items():
                    numeric_match = (not name_only and re.fullmatch(r"[0-9]+", value)
                                     and int(value) == identifier)
                    if value in names or numeric_match:
                        result.append({"source": relative, "line": data.count(b"\n", 0, current.start) + 1,
                                       "kind": "trigger_literal", "tag": current.tag, "attribute": key})
                inner = data[current.open_end:current.close_start].strip()
                if not current.children and inner:
                    # Trigger parameter values are usually element text.
                    try:
                        value = expat_text_value(inner)
                    except ValueError:
                        continue
                    if value in names or (not name_only and value.isdigit() and int(value) == identifier):
                        result.append({"source": relative, "line": data.count(b"\n", 0, current.start) + 1,
                                       "kind": "trigger_literal", "tag": current.tag})
    return result


def expat_text_value(data: bytes) -> str:
    parser = expat.ParserCreate()
    pieces = []
    parser.CharacterDataHandler = pieces.append
    try:
        parser.Parse(b"<v>" + data + b"</v>", True)
    except expat.ExpatError as exc:
        raise ValueError(str(exc)) from exc
    return "".join(pieces).strip()


def inspect_spatial(root: Path, kind: str = "all") -> dict:
    """Return actual XML fields, IDs, duplicate diagnostics, and source offsets."""
    requested = _ALIASES.get(kind, kind)
    if requested not in _KINDS | {"all", "region", "regions", "objects"}:
        raise SC2Error("invalid_spatial_kind", "未知空间对象种类", kind=kind)
    result = {"objects": [], "regions": [], "counts": {}, "diagnostics": [],
              "validation": "static_xml_only"}
    for component in ("Objects", "Regions"):
        if component == "Objects" and requested in {"region", "regions"}:
            continue
        if component == "Regions" and requested not in {"all", "region", "regions"}:
            continue
        if not _path(root, component).exists():
            result["diagnostics"].append({"code": "missing_component", "component": component})
            continue
        data, document = _load(root, component)
        ids = Counter(n.attrs.get("Id" if component == "Objects" else "id") for n in document.children)
        for object_id, count in ids.items():
            if count > 1:
                result["diagnostics"].append({"code": "duplicate_spatial_id", "component": component,
                                               "id": object_id, "count": count})
        for node in document.children:
            if component == "Objects" and requested not in {"all", "objects", node.tag}:
                continue
            entry = {"kind": node.tag, "id": node.attrs.get("Id", node.attrs.get("id")),
                     "attributes": node.attrs, "source": component,
                     "line": data.count(b"\n", 0, node.start) + 1,
                     "children": [_describe(n) for n in node.children]}
            result["objects" if component == "Objects" else "regions"].append(entry)
    result["counts"] = dict(Counter(n["kind"] for n in result["objects"] + result["regions"]))
    return result


def _describe(node: _Node) -> dict:
    return {"kind": node.tag, "attributes": node.attrs, "children": [_describe(n) for n in node.children]}


def plan_object_edit(root: Path, object_id: str, attributes: dict[str, str]) -> dict[str, bytes | None]:
    data, document = _load(root, "Objects")
    _check_ids(document.children)
    node = _unique(document.children, object_id)
    if node.tag not in _KINDS:
        raise SC2Error("unsupported_spatial_kind", "此对象格式尚未支持编辑", kind=node.tag)
    observed = {k for n in document.children if n.tag == node.tag for k in n.attrs}
    _attributes(node.tag, attributes, observed)
    if "Id" in attributes and attributes["Id"] != node.attrs["Id"]:
        raise SC2Error("stable_id_change", "禁止修改已有空间对象 ID", object_id=object_id)
    if "Name" in attributes and attributes["Name"] != node.attrs.get("Name"):
        references = _references(root, node, name_only=True)
        if references:
            raise SC2Error("spatial_reference", "对象名称仍有引用，不能单独改名", references=references)
    return _candidate("Objects", data, _patch_attributes(data, node, attributes))


def plan_object_add(root: Path, kind: str, attributes: dict[str, str]) -> dict[str, bytes | None]:
    kind = _ALIASES.get(kind, kind)
    if kind not in _KINDS:
        raise SC2Error("unsupported_spatial_kind", "不支持新增该对象格式", kind=kind)
    data, document = _load(root, "Objects")
    _check_ids(document.children)
    if kind in {"Camera", "ObjectCamera"} and not any(n.tag == kind for n in document.children):
        raise SC2Error("unsupported_spatial_schema", "缺少该镜头格式的已保存样本", kind=kind)
    if kind in {"Camera", "ObjectCamera"} and any(n.children for n in document.children if n.tag == kind):
        raise SC2Error("unsupported_spatial_schema", "镜头包含嵌套字段，不能仅凭属性创建完整镜头", kind=kind)
    if not isinstance(attributes, dict):
        raise SC2Error("invalid_spatial_attributes", "空间属性必须是字典")
    attrs = dict(attributes)
    observed = {k for n in document.children if n.tag == kind for k in n.attrs}
    _attributes(kind, attrs, observed)
    used = {int(n.attrs["Id"]) for n in document.children}
    if "Id" not in attrs:
        next_id = 1
        while next_id in used:
            next_id += 1
        attrs = {"Id": str(next_id), **attrs}
    if _id(attrs["Id"]) in used:
        raise SC2Error("ambiguous_spatial_id", "新增对象 ID 已存在", object_id=attrs["Id"])
    required = {"ObjectUnit": {"Position", "UnitType"}, "ObjectDoodad": {"Position", "Type"},
                "ObjectPoint": {"Position", "Type"}, "Group": {"Type", "Name"}}.get(kind, {"Name"})
    if kind in {"Camera", "ObjectCamera"}:
        required = observed - {"Id"}
    if not required.issubset(attrs):
        raise SC2Error("missing_spatial_attributes", "缺少必要对象属性", missing=sorted(required - attrs.keys()))
    if kind == "Group" and attrs["Type"] not in {"ObjectUnit", "ObjectDoodad", "ObjectPoint"}:
        raise SC2Error("unsupported_spatial_schema", "对象组类型无已验证格式", value=attrs["Type"])
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    indent = b"    "
    if document.children:
        first = document.children[0]
        prefix = data[data.rfind(b"\n", 0, first.start) + 1:first.start]
        if not prefix.strip():
            indent = prefix
    opening = b"<" + kind.encode("ascii")
    for key, value in attrs.items():
        opening += b" " + key.encode("ascii") + b'="' + _value(value).encode("utf-8") + b'"'
    opening += b"/>"
    if data[document.start:document.open_end].rstrip().endswith(b"/>"):
        old = data[document.start:document.open_end]
        replacement = old[:-2] + b">" + newline + indent + opening + newline + b"</PlacedObjects>"
        changed = data[:document.start] + replacement + data[document.end:]
    else:
        line_start = data.rfind(b"\n", 0, document.close_start) + 1
        if data[line_start:document.close_start].strip():
            offset, insertion = document.close_start, newline + indent + opening + newline
        else:
            offset, insertion = line_start, indent + opening + newline
        changed = data[:offset] + insertion + data[offset:]
    return _candidate("Objects", data, changed)


def plan_object_remove(root: Path, object_id: str) -> dict[str, bytes | None]:
    data, document = _load(root, "Objects")
    _check_ids(document.children)
    node = _unique(document.children, object_id)
    if node.tag not in _KINDS:
        raise SC2Error("unsupported_spatial_kind", "此对象格式尚未支持删除", kind=node.tag)
    references = _references(root, node)
    for other in document.children:
        if other is node:
            continue
        pending = list(other.children)
        while pending:
            child = pending.pop()
            pending.extend(child.children)
            if child.tag == "GroupObject" and child.attrs.get("Id", "").isdigit() and int(child.attrs["Id"]) == int(node.attrs["Id"]):
                references.append({"source": "Objects", "kind": "group_membership", "group_id": other.attrs.get("Id")})
    if references:
        raise SC2Error("spatial_reference", "对象仍被引用，不能删除", references=references)
    # Delete only the XML element span; surrounding whitespace/comments survive.
    return _candidate("Objects", data, data[:node.start] + data[node.end:])


def plan_region_edit(root: Path, region_id: int, name: str | None = None,
                     rect: list[float] | None = None) -> dict[str, bytes | None]:
    data, document = _load(root, "Regions")
    regions = [n for n in document.children if n.tag == "region"]
    _check_ids(regions, "id")
    region = _unique(regions, region_id, "id")
    replacements = []
    if name is not None:
        _value(name)
        names = [n for n in region.children if n.tag == "name"]
        if len(names) != 1:
            raise SC2Error("unsupported_region_schema", "区域名称节点不存在或不唯一", region_id=region_id)
        if names[0].attrs.get("value") != name:
            references = _references(root, region, name_only=True)
            if references:
                raise SC2Error("spatial_reference", "区域名称仍被引用，不能单独改名", references=references)
        replacements.append((names[0], {"value": name}))
    if rect is not None:
        if not isinstance(rect, (list, tuple)) or len(rect) != 4 or any(isinstance(n, bool) for n in rect):
            raise SC2Error("invalid_region_rect", "区域矩形必须为四个有限数字")
        try:
            numbers = [float(n) for n in rect]
        except (TypeError, ValueError, OverflowError) as exc:
            raise SC2Error("invalid_region_rect", "区域矩形必须为四个有限数字") from exc
        if any(not math.isfinite(n) for n in numbers) or numbers[0] >= numbers[2] or numbers[1] >= numbers[3]:
            raise SC2Error("invalid_region_rect", "区域矩形必须有正面积且使用有限坐标")
        shapes = [n for n in region.children if n.tag == "shape"]
        if len(shapes) != 1 or shapes[0].attrs.get("type") != "rect":
            raise SC2Error("unsupported_region_schema", "仅支持单矩形区域；不覆盖复合区域或圆形", region_id=region_id)
        quads = [n for n in shapes[0].children if n.tag == "quad"]
        if len(quads) != 1 or len(shapes[0].children) != 1:
            raise SC2Error("unsupported_region_schema", "区域矩形结构未知或不唯一", region_id=region_id)
        value = ",".join(format(n, ".15g") for n in numbers)
        replacements.append((quads[0], {"value": value}))
    changed = data
    for node, attrs in sorted(replacements, key=lambda item: item[0].start, reverse=True):
        changed = _patch_attributes(changed, node, attrs)
    return _candidate("Regions", data, changed)
