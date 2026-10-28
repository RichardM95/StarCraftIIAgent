"""Byte-preserving, in-memory structural Catalog candidate planning.

Supported operations: set, append, remove, restore, create, clone. Explicit
numeric slots are mandatory for structural arrays. No source file is written.
Clones select fields explicitly; the API does not guess a complete unit chain.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .catalog import (_Library, _Patch, _Span, _catalog_name, _type_catalog, _spans, _parts, _quoted,
                      _insert_child, _replace_attribute, _ATTRIBUTE_NAMES, _ARRAY_NAMES, _CONTROL_ATTRIBUTES)
from .catalog_rules import INDEXED_ARRAYS
from .errors import SC2Error
from .storage import guard_absolute_path

_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*\Z")
_ATTR = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*\Z")


def _value(value):
    if not isinstance(value, str) or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise SC2Error("invalid_catalog_value", "字段值必须为 XML 字符串")
    if "##" in value or "$" in value:
        raise SC2Error("catalog_macro_unsupported", "结构补丁不能自动解释宏或表达式", value=value)
    try:
        ET.fromstring(b'<V value="' + _quoted(value) + b'"/>')
    except ET.ParseError as exc:
        raise SC2Error("invalid_catalog_value", "字段含非法 XML 字符") from exc
    return value


def _ascii(raw):
    return bool(re.match(br"(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding\s*=\s*['\"](?:us-ascii|ascii)['\"]", raw, re.I))


def _find_object(raw: bytes, class_name: str, object_id: str) -> _Span:
    document = _spans(raw)
    matches = [node for node in document.children if node.attributes.get("id") == object_id and _type_catalog(node.tag) == _type_catalog(class_name)]
    if len(matches) != 1 or matches[0].tag != class_name:
        raise SC2Error("ambiguous_catalog_object", "不能唯一定位本地对象", object_id=object_id)
    return matches[0]


def _unambiguous_path(library, kind, identifier, path):
    tree, _inheritance, _sources = library._effective((kind, identifier), [], [])
    parts = _parts(path)
    current = tree
    for position, (name, index) in enumerate(parts):
        if position == len(parts) - 1 and index is None and name in current.attributes:
            return ".".join([*(part for part in path.split(".")[:-1]), "@" + name])
        matching = [child for child in current.children if child.tag == name and child.index == index]
        if len(matching) != 1:
            return path
        current = matching[0]
    return path


def _set(raw: bytes, node: _Span, path: str, value: str, expected=None) -> bytes:
    parts = _parts(path)
    current, attr, missing = node, "value", None
    for position, (name, index) in enumerate(parts):
        final = position == len(parts) - 1
        matches = [child for child in current.children if child.tag == name and child.attributes.get("index") == index]
        is_attr = final and index is None and (name.startswith("@") or name in current.attributes or position > 0 and name in _ATTRIBUTE_NAMES and not matches)
        if is_attr:
            attr = name.lstrip("@")
            break
        same_tag = [child for child in current.children if child.tag == name]
        if (name.endswith("Array") or name in _ARRAY_NAMES or any("index" in child.attributes for child in same_tag)) and index is None:
            raise SC2Error("catalog_array_index_required", "数组字段必须指定索引", field_path=path)
        if index is not None and any("index" not in child.attributes for child in same_tag):
            raise SC2Error("ambiguous_unindexed_array", "本地无索引数组不能按推测槽位修改", field_path=path)
        if len(matches) > 1:
            raise SC2Error("ambiguous_catalog_field", "字段路径匹配多个节点", field_path=path)
        if not matches:
            missing = position
            break
        current = matches[0]
        if current.attributes.get("removed") == "1":
            raise SC2Error("catalog_field_removed", "数组项已删除，需要明确恢复", field_path=path)
    actual = current.attributes.get(attr) if missing is None else None
    if expected is not None and actual != expected:
        raise SC2Error("catalog_expected_mismatch", "本地字段与期望值不一致", expected=expected, actual=actual)
    if missing is None:
        return raw if actual == value else _replace_attribute(raw, current, attr, value, _ascii(raw))
    remaining = parts[missing:]
    leaf_attr = "value"
    if len(remaining) > 1 and remaining[-1][1] is None and (remaining[-1][0].startswith("@") or remaining[-1][0] in _ATTRIBUTE_NAMES):
        leaf_attr, remaining = remaining[-1][0].lstrip("@"), remaining[:-1]
    if not remaining or any(name.startswith("@") for name, _ in remaining):
        raise SC2Error("invalid_catalog_field_path", "不能建立此字段路径", field_path=path)
    fragment = b""
    for position, (name, index) in reversed(list(enumerate(remaining))):
        if (name.endswith("Array") or name in _ARRAY_NAMES) and index is None:
            raise SC2Error("catalog_array_index_required", "新增数组必须指定索引", field_path=path)
        attrs = b' index="' + _quoted(index, ascii_only=_ascii(raw)) + b'"' if index is not None else b""
        if position == len(remaining) - 1:
            fragment = b"<" + name.encode() + attrs + b" " + leaf_attr.encode() + b'="' + _quoted(value, ascii_only=_ascii(raw)) + b'"/>'
        else:
            fragment = b"<" + name.encode() + attrs + b">" + fragment + b"</" + name.encode() + b">"
    return _insert_child(raw, current, fragment)


class _Planner:
    def __init__(self, root, roots):
        self.root = guard_absolute_path(Path(root)).resolve()
        self.roots = [guard_absolute_path(Path(path)).resolve() for path in roots]
        if self.roots.count(self.root) != 1:
            raise SC2Error("catalog_patch_root_order", "修改目标必须为 roots 中唯一且最后的组件根")
        self.root_layer = self.roots.index(self.root)
        if any(path.parent != self.root or not path.name.casefold().endswith(".sc2data")
               for path in self.roots[self.root_layer + 1:]):
            raise SC2Error("catalog_patch_root_order", "目标组件之后仅允许显式选定的本地图语言层")
        self.original = _Library(self.roots)
        self.local = _Library([self.root])
        self.changes: dict[Path, bytes] = {}
        self.baselines = {}

    def library(self):
        # Retain exact active-file discovery/order and replace only the parsed
        # entries for planned local files. New files are standard implicit ones.
        library = _Library.__new__(_Library)
        library.objects, library.defaults = defaultdict(list), defaultdict(list)
        library.files = list(self.original.files)
        library.file_sha256 = dict(self.original.file_sha256)
        library.warnings = list(self.original.warnings)
        library.arrays, library._seen, library._roots = set(), set(), self.roots
        replacements = {}
        for path in self.changes:
            if path not in library.files:
                library.files.append(path)
            document = ET.fromstring(self.changes[path])
            for child in document:
                if _type_catalog(child.tag):
                    key = (path, child.tag, child.get("id"))
                    replacements.setdefault(key, []).append(_Patch(child, path, self.root, self.root_layer, hashlib.sha256(self.changes[path]).hexdigest()))
        consumed = defaultdict(int)
        # Keep each original object's true include/patch order. Grouping the
        # original patches by file would reorder inline includes in Catalogs.
        for original, target in ((self.original.objects, library.objects), (self.original.defaults, library.defaults)):
            for key, patches in original.items():
                for patch in patches:
                    replacement_key = (patch.file, patch.node.tag, patch.node.get("id"))
                    if patch.file in self.changes:
                        position = consumed[replacement_key]
                        matches = replacements.get(replacement_key, [])
                        if position >= len(matches):
                            raise SC2Error("catalog_patch_identity_changed", "规划不得删除或重命名已有对象")
                        target[key].append(matches[position])
                        consumed[replacement_key] += 1
                    else:
                        target[key].append(patch)
        for key, patches in replacements.items():
            for patch in patches[consumed[key]:]:
                identifier = patch.node.get("id")
                if identifier:
                    values = library.objects[(_type_catalog(patch.node.tag), identifier)]
                    values.append(patch)
                    values.sort(key=lambda value: value.layer)
                elif patch.node.get("default") == "1":
                    library.defaults[patch.node.tag].append(patch)
        for patches in [*library.objects.values(), *library.defaults.values()]:
            for patch in patches:
                library._array_hints(patch.node, patch.node.tag, ())
        return library

    def read(self, path):
        if path in self.changes:
            return self.changes[path]
        raw = path.read_bytes() if path.is_file() else b'<?xml version="1.0" encoding="utf-8"?>\n<Catalog>\n</Catalog>\n'
        self.baselines.setdefault(path, path.read_bytes() if path.is_file() else None)
        return raw

    def save(self, path, raw):
        _spans(raw)
        self.changes[path] = raw

    def object(self, kind, identifier, *, create=False, class_name=None):
        library = self.library()
        patches = library.objects.get((kind, identifier), [])
        local = [patch for patch in patches if patch.root == self.root]
        if len(local) > 1:
            raise SC2Error("ambiguous_catalog_object", "本地同 ID 有多条声明", object_id=identifier)
        if create and patches:
            raise SC2Error("catalog_id_exists", "新增 ID 已存在于来源链", object_id=identifier)
        if not create and not patches:
            raise SC2Error("catalog_object_not_found", "不能覆盖不存在的来源对象", object_id=identifier)
        if local:
            path = local[0].file
            base = next((path for path in self.root.iterdir() if path.name.casefold() == "base.sc2data"), self.root / "Base.SC2Data")
            if not path.resolve().is_relative_to(base.resolve()):
                raise SC2Error("catalog_patch_locale_unsupported", "结构补丁仅修改 Base.SC2Data")
            return path, local[0].node.tag
        classes = {patch.node.tag for patch in patches}
        if not create and len(classes) != 1:
            raise SC2Error("catalog_class_ambiguous", "来源对象类型变化，不能自动建立覆盖", object_id=identifier)
        class_name = class_name if create else next(iter(classes))
        if not isinstance(class_name, str) or not _ID.fullmatch(class_name) or _type_catalog(class_name) != kind:
            raise SC2Error("invalid_catalog_class", "class 与 Catalog 类型不匹配", class_name=class_name, catalog=kind)
        observed_classes = {patch.node.tag for entries in library.objects.values() for patch in entries} | set(library.defaults)
        if class_name != "C" + kind and class_name not in observed_classes:
            raise SC2Error("unknown_catalog_class", "新对象类型未在来源中验证", class_name=class_name)
        # Use the canonical implicit file; do not add a custom include or edit
        # GameData.xml merely to establish a minimal object override.
        base = next((path for path in self.root.iterdir() if path.name.casefold() == "base.sc2data"), self.root / "Base.SC2Data")
        gamedata = next((path for path in base.iterdir() if path.name.casefold() == "gamedata"), base / "GameData") if base.is_dir() else base / "GameData"
        path = next((path for path in gamedata.iterdir() if path.name.casefold() == (kind + "Data.xml").casefold()), gamedata / (kind + "Data.xml")) if gamedata.is_dir() else gamedata / (kind + "Data.xml")
        guard_absolute_path(path)
        if not path.resolve().is_relative_to(self.root):
            raise SC2Error("unsafe_catalog_path", "输出离开目标图")
        raw = self.read(path)
        document = _spans(raw)
        if document.tag != "Catalog":
            raise SC2Error("unsupported_catalog_document", "标准目标文件不是 Catalog")
        fragment = b"<" + class_name.encode() + b' id="' + _quoted(identifier, ascii_only=_ascii(raw)) + b'"/>'
        self.save(path, _insert_child(raw, document, fragment))
        return path, class_name

    def array_rule(self, kind, identifier, path):
        parts = _parts(path)
        if len(parts) != 1 or parts[0][1] is None or not parts[0][1].isdigit() or str(int(parts[0][1])) != parts[0][1]:
            raise SC2Error("catalog_explicit_index_required", "结构数组操作需要单层规范数字索引", field_path=path)
        name, index = parts[0]
        if (kind, name) not in INDEXED_ARRAYS:
            raise SC2Error("unknown_catalog_array_rule", "该数组没有已支持的结构修改规则", catalog=kind, field_path=path)
        library = self.library()
        effective = library.inspect(kind, identifier)
        if any(warning["code"] in {"missing_catalog_parent", "catalog_class_changed", "unknown_removed_value"} for warning in effective["warnings"]):
            raise SC2Error("catalog_structure_unknown", "来源继承或删除规则不完整，拒绝修改结构")
        related = [identifier, *effective["inheritance"]]
        patches = [patch for related_id in related for patch in library.objects.get((kind, related_id), [])]
        for class_name in {patch.node.tag for patch in patches}:
            patches.extend(library.defaults.get(class_name, []))
        for patch in patches:
            matching = [child for child in patch.node if child.tag == name]
            if any(child.get("index") is None for child in matching):
                raise SC2Error("ambiguous_unindexed_array", "来源含无索引数组，不能按静态推测槽位改结构", field_path=path)
            slots = [child.get("index") for child in matching]
            if len(slots) != len(set(slots)):
                raise SC2Error("ambiguous_catalog_field", "同层数组索引重复", field_path=path)
        tree, _ancestors, _sources = library._effective((kind, identifier), [], [])
        effective["_array_slots"] = {f"{name}[{node.index}]": node.removed for node in tree.children if node.tag == name}
        return name, index, effective

    def apply(self, operation):
        if not isinstance(operation, dict):
            raise SC2Error("invalid_catalog_operation", "每项操作需要对象参数")
        action = operation.get("operation")
        raw_kind = operation.get("catalog", "")
        if not isinstance(raw_kind, str):
            raise SC2Error("unsupported_catalog", "Catalog 类型需要字符串")
        kind, identifier = _catalog_name(raw_kind), operation.get("object_id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise SC2Error("invalid_catalog_id", "对象 ID 格式不受支持")
        if action not in {"set", "append", "remove", "restore", "create", "clone"}:
            raise SC2Error("unsupported_catalog_operation", "未知 Catalog 结构操作", operation=action)
        if action == "clone":
            source_id, selection = operation.get("source_id"), operation.get("fields")
            if (not isinstance(selection, list) or not selection or any(not isinstance(path, str) for path in selection)
                    or len(set(selection)) != len(selection)):
                raise SC2Error("catalog_clone_fields_required", "克隆必须明确选择不重复字段路径")
            library = self.library()
            effective = library.inspect(kind, source_id)
            if any(warning["code"] in {"missing_catalog_parent", "catalog_class_changed", "unknown_removed_value"} for warning in effective["warnings"]):
                raise SC2Error("catalog_structure_unknown", "克隆来源继承或删除规则不完整")
            chosen = {}
            for field in selection:
                if field not in effective["fields"]:
                    raise SC2Error("catalog_clone_field_missing", "克隆字段不存在", field_path=field)
                if "[" in field:
                    top = field.split(".", 1)[0]
                    self.array_rule(kind, source_id, top)
                chosen[_unambiguous_path(library, kind, source_id, field)] = _value(effective["fields"][field]["value"])
            path, class_name = self.object(kind, identifier, create=True, class_name=effective["class"])
            for field, value in chosen.items():
                raw = self.read(path)
                self.save(path, _set(raw, _find_object(raw, class_name, identifier), field, value))
            return
        if action == "create":
            fields = operation.get("fields", {})
            if not isinstance(fields, dict):
                raise SC2Error("invalid_catalog_fields", "新增 fields 需要字段映射")
            path, class_name = self.object(kind, identifier, create=True, class_name=operation.get("class"))
            for field, value in fields.items():
                if not isinstance(field, str):
                    raise SC2Error("invalid_catalog_field_path", "字段路径需要字符串")
                if "[" in field:
                    self.array_rule(kind, identifier, field.split(".", 1)[0])
                raw = self.read(path)
                self.save(path, _set(raw, _find_object(raw, class_name, identifier), field, _value(value)))
            return
        field = operation.get("field_path")
        if not isinstance(field, str) or not field:
            raise SC2Error("invalid_catalog_field_path", "需要 field_path")
        if action == "set":
            if "[" in field:
                self.array_rule(kind, identifier, field.split(".", 1)[0])
            # Validate the entire effective inherited field if requested; the
            # legacy plan_catalog_set retains its local-attribute comparison.
            expected = operation.get("expected")
            library = self.library()
            effective = library.inspect(kind, identifier)
            if any(warning["code"] in {"missing_catalog_parent", "catalog_class_changed", "unknown_removed_value"} for warning in effective["warnings"]):
                raise SC2Error("catalog_structure_unknown", "字段来源继承或删除规则不完整")
            read_field = field.replace(".@", ".")
            if expected is not None:
                actual = library.inspect(kind, identifier)["fields"].get(read_field, {}).get("value")
                if actual != expected:
                    raise SC2Error("catalog_expected_mismatch", "有效静态字段与期望不同", expected=expected, actual=actual)
            path, class_name = self.object(kind, identifier)
            raw = self.read(path)
            write_path = _unambiguous_path(library, kind, identifier, field)
            self.save(path, _set(raw, _find_object(raw, class_name, identifier), write_path, _value(operation.get("value"))))
            if self.library().inspect(kind, identifier)["fields"].get(read_field, {}).get("value") != operation.get("value"):
                raise SC2Error("catalog_patch_shadowed", "候选字段被后续语言层或来源覆盖，拒绝报告修改成功", field_path=field)
            return
        name, index, effective = self.array_rule(kind, identifier, field)
        prefixes = {path for path, removed in effective["_array_slots"].items() if not removed}
        removed = {path for path, removed in effective["_array_slots"].items() if removed}
        present = field in prefixes
        if action == "append":
            indices = [int(match.group(1)) for prefix in prefixes | removed if (match := re.fullmatch(re.escape(name) + r"\[(\d+)\]", prefix))]
            expected_index = max(indices, default=-1) + 1
            if int(index) != expected_index or present or field in removed:
                raise SC2Error("catalog_append_index_mismatch", "追加必须明确使用下一未分配槽位；移除槽位不重排", expected_index=expected_index, requested=index)
        elif action == "remove" and not present:
            raise SC2Error("catalog_array_slot_missing", "不能移除不存在或已删除的槽位", field_path=field)
        elif action == "restore" and field not in removed:
            raise SC2Error("catalog_array_slot_not_removed", "恢复只接受明确删除的槽位", field_path=field)
        attrs = operation.get("attributes", {})
        if not isinstance(attrs, dict) or action in {"append", "restore"} and not attrs:
            raise SC2Error("catalog_array_payload_required", "追加/恢复需要完整明确的属性载荷")
        for attr, value in attrs.items():
            if not isinstance(attr, str) or not _ATTR.fullmatch(attr) or attr in _CONTROL_ATTRIBUTES | {"id", "parent", "default"}:
                raise SC2Error("invalid_catalog_attribute", "不允许数组控制或身份属性", attribute=attr)
            _value(value)
        path, class_name = self.object(kind, identifier)
        raw = self.read(path)
        node = _find_object(raw, class_name, identifier)
        matches = [child for child in node.children if child.tag == name and child.attributes.get("index") == index]
        if len(matches) > 1:
            raise SC2Error("ambiguous_catalog_field", "本地槽位重复", field_path=field)
        if matches:
            raw = _replace_attribute(raw, matches[0], "removed", "1" if action == "remove" else "0", _ascii(raw)) if action != "append" else raw
        else:
            fragment = b"<" + name.encode() + b' index="' + index.encode() + b'"'
            if action in {"remove", "restore"}:
                fragment += b' removed="' + (b"1" if action == "remove" else b"0") + b'"'
            fragment += b"/>"
            raw = _insert_child(raw, node, fragment)
        self.save(path, raw)
        if action != "remove":
            # Restore writes all explicitly requested attributes, never revives
            # unknown inherited contents or infers the deleted slot's payload.
            for attr, value in attrs.items():
                raw = self.read(path)
                if action == "restore":
                    target = next(child for child in _find_object(raw, class_name, identifier).children if child.tag == name and child.attributes.get("index") == index)
                    self.save(path, _replace_attribute(raw, target, attr, value, _ascii(raw)))
                else:
                    self.save(path, _set(raw, _find_object(raw, class_name, identifier), field + ".@" + attr, value))
        after = self.array_rule(kind, identifier, field)[2]
        if after["_array_slots"].get(field) != (action == "remove"):
            raise SC2Error("catalog_patch_shadowed", "候选数组槽位被后续语言层覆盖", field_path=field)
        if action == "restore":
            declared = {field if attr == "value" else field + "." + attr for attr in attrs}
            observed = {key for key in after["fields"] if key == field or key.startswith(field + ".")}
            if observed != declared:
                raise SC2Error("catalog_array_payload_incomplete", "恢复载荷必须覆盖全部最终属性，不能静默复活旧字段或嵌套内容", field_path=field, additional_fields=sorted(observed - declared))
        if action != "remove":
            for attr, value in attrs.items():
                payload_field = field if attr == "value" else field + "." + attr
                if after["fields"].get(payload_field, {}).get("value") != value:
                    raise SC2Error("catalog_patch_shadowed", "候选数组载荷被后续语言层覆盖", field_path=field, attribute=attr)


def _build_catalog_patch(root: Path, roots: list[Path], operations: list[dict]):
    """Return a single atomic candidate; invalid later operations write nothing.

    ``set.expected`` compares the effective static candidate. ``append``,
    ``remove`` and ``restore`` require field_path ``WeaponArray[2]`` style;
    append/restore additionally require explicit ``attributes``. ``create``
    requires class and a field mapping, while ``clone`` requires source_id and
    a nonempty field-path list. All unknown array schemas/macros are rejected.
    """
    if not isinstance(operations, list) or not operations or len(operations) > 10000:
        raise SC2Error("invalid_catalog_operations", "需要 1 至 10000 项 Catalog 操作")
    planner = _Planner(root, roots)
    for operation in operations:
        planner.apply(operation)
    for path, before in planner.baselines.items():
        if (path.read_bytes() if path.is_file() else None) != before:
            raise SC2Error("catalog_source_changed", "规划期间本地来源变化", path=str(path))
    for path, expected in planner.original.file_sha256.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SC2Error("catalog_source_changed", "规划期间依赖或 Catalog 内容变化", path=str(path))
    changes = {path.relative_to(planner.root).as_posix(): raw for path, raw in planner.changes.items()
               if planner.baselines.get(path) != raw}
    return planner, changes


def plan_catalog_patch(root: Path, roots: list[Path], operations: list[dict]) -> dict[str, bytes | None]:
    """Plan exact Catalog bytes without writing sources or applying a candidate."""
    return _build_catalog_patch(root, roots, operations)[1]


def plan_catalog_patch_report(root: Path, roots: list[Path], operations: list[dict], *, source_context=None) -> dict:
    """Return the identical byte candidate plus a bound static impact report."""
    from .catalog_impact import inspect_patch_impact
    if source_context is not None:
        from .source_context import assert_source_context_current
        assert_source_context_current(source_context)
        if [str(Path(path).resolve()) for path in roots] != source_context.get('roots'):
            raise SC2Error('source_context_roots_mismatch', '补丁报告来源与选定上下文不一致')
    planner, changes = _build_catalog_patch(root, roots, operations)
    report = inspect_patch_impact(planner.original, planner.library(), operations, changes, source_context)
    for path, expected in planner.original.file_sha256.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SC2Error('catalog_source_changed', '影响报告生成期间来源变化', file=str(path))
    if source_context is not None:
        assert_source_context_current(source_context)
    return {'changes': changes, 'report': report}
