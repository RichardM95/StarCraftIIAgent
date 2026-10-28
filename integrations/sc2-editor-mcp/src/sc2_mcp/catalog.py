"""Include-aware, provenance-bearing SC2 Catalog inspection and narrow edits.

``roots`` are ordered dependency component roots followed by the map. Component
roots load Base.SC2Data only; a locale.SC2Data directory must be supplied
explicitly to opt into locale data. Standard GameData/<Catalog>Data.xml files
are implicit; other XML is loaded only through GameData.xml includes.

Field paths: ``LifeMax`` means the value attribute on <LifeMax>;
``WeaponArray[0].Link`` means Link on the indexed WeaponArray;
``Cost[0].Cooldown.TimeUse`` addresses a nested attribute. ``.@attribute``
unambiguously addresses any attribute; indices may be numbers or named enums.
Inspection preserves removed slots as tombstones, so appends do not renumber
existing entries. This is an explicitly partial static merge, not an engine
schema or proof of editor/runtime behavior. Named default=1 objects are
templates, not global defaults; anonymous defaults apply to their exact class.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import hashlib
import re
from typing import Any
from xml.etree import ElementTree as ET
from xml.parsers import expat
from xml.sax.saxutils import escape

from .errors import SC2Error


# Explicit engine catalog filenames. Never glob XML: backups and unattached
# documents can contain valid, but inactive, Catalog entries.
_CATALOGS = (
    "Abil", "Achievement", "AchievementTerm", "Actor", "Alert", "ArmyCategory",
    "ArmyUnit", "ArmyUpgrade", "Artifact", "ArtifactSlot", "AttachMethod",
    "Beam", "Behavior", "Button", "Camera", "Campaign", "Character",
    "Cliff", "CliffMesh", "Conversation", "ConversationState", "Cursor",
    "DataCollection", "DataCollectionPattern", "Effect", "Error", "Footprint",
    "Game", "GameUI", "Herd", "Hero", "HeroAbil", "HeroStat", "Item",
    "ItemClass", "ItemContainer", "Kinetic", "LensFlareSet", "Light", "Loot",
    "Map", "Model", "Mount", "Mover", "Objective", "PhysicsMaterial",
    "Ping", "PlayerResponse", "PortraitPack", "Preload", "Race",
    "Requirement", "RequirementNode", "Reverb", "Reward", "ScoreResult",
    "ScoreValue", "Skin", "Sound", "SoundExclusivity", "SoundMixSnapshot",
    "Soundtrack", "Spray", "Tactical", "Talent", "TargetFind", "TargetSort",
    "Terrain", "TerrainObject", "TerrainTex", "Texture", "Tile", "Turret",
    "Unit", "Upgrade", "User", "Validator", "VoiceOver", "WarChest",
    "WarChestSeason", "Water", "Weapon",
)
_ARRAY_NAMES = {"CardLayouts", "LayoutButtons", "TriggerLibs", "Regions", "Events"}
_ATTRIBUTE_NAMES = {
    "Link", "Count", "Time", "TimeUse", "TimeStart", "TimeDelay", "Location",
    "Face", "Type", "AbilCmd", "Row", "Column", "DefaultButtonFace", "Unit",
    "Effect", "Behavior", "Weapon", "Validator", "Model", "Actor", "Button",
    "Requirements", "Chance", "Fraction", "Radius", "Arc", "Flags", "value",
}
_CONTROL_ATTRIBUTES = {"index", "removed"}
_PATH_PART = re.compile(r"(@?[A-Za-z_][A-Za-z_0-9-]*)(?:\[([^\[\].]+)\])?\Z")
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*\Z")


def _catalog_name(name: str) -> str:
    for candidate in _CATALOGS:
        if candidate.casefold() == name.casefold():
            return candidate
    raise SC2Error("unsupported_catalog", "未知 Catalog 类型", catalog=name)


def _type_catalog(tag: str) -> str | None:
    if not tag.startswith("C"):
        return None
    # Longest match avoids TerrainTex->Terrain, RequirementNode->Requirement.
    return next((name for name in sorted(_CATALOGS, key=len, reverse=True)
                 if tag.startswith("C" + name)), None)


def _case_path(base: Path, relative: str) -> Path | None:
    rel = PurePosixPath(relative.replace("\\", "/"))
    if rel.is_absolute() or any(p in {"..", "."} or ":" in p for p in rel.parts):
        raise SC2Error("unsafe_catalog_path", "Catalog 路径不能离开组件目录", path=relative)
    current = base
    for part in rel.parts:
        if not current.is_dir():
            return None
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        if len(matches) > 1:
            raise SC2Error("catalog_case_collision", "路径大小写冲突", path=str(current / part))
        if not matches:
            return None
        current = matches[0]
        if not current.resolve().is_relative_to(base.resolve()):
            raise SC2Error("unsafe_catalog_path", "Catalog 链接离开组件目录", path=str(current))
    return current


def _xml(path: Path) -> tuple[bytes, ET.Element]:
    raw = path.read_bytes()
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
        raise SC2Error("unsafe_xml", "不支持 DTD 或实体声明", path=str(path))
    try:
        return raw, ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SC2Error("invalid_catalog_xml", "Catalog XML 不能解析", path=str(path), reason=str(exc)) from exc


@dataclass
class _Patch:
    node: ET.Element
    file: Path
    root: Path
    layer: int
    sha256: str

    def source(self, kind: str = "object") -> dict:
        return {"file": str(self.file), "root": str(self.root), "layer": self.layer,
                "object_id": self.node.get("id"), "class": self.node.tag, "kind": kind, "sha256": self.sha256}


class _Library:
    def __init__(self, roots: list[Path]):
        if not roots:
            raise SC2Error("catalog_roots_required", "必须提供按加载顺序排列的组件路径")
        self.objects: dict[tuple[str, str], list[_Patch]] = defaultdict(list)
        self.defaults: dict[str, list[_Patch]] = defaultdict(list)
        self.files: list[Path] = []
        self.file_sha256: dict[Path, str] = {}
        self.warnings: list[dict] = []
        self.arrays: set[tuple[str, tuple[str, ...]]] = set()
        self._seen: set[Path] = set()
        self._roots = [Path(root).resolve() for root in roots]
        for layer, root in enumerate(self._roots):
            if not root.is_dir():
                raise SC2Error("catalog_root_not_directory", "Catalog 读取需要组件文件夹", path=str(root))
            if root.name.casefold().endswith(".sc2data"):
                data = root
            else:
                data = _case_path(root, "Base.SC2Data")
                locales = [p.name for p in root.iterdir() if p.is_dir()
                           and p.name.casefold().endswith(".sc2data")
                           and p.name.casefold() != "base.sc2data"]
                if locales:
                    self.warnings.append({"code": "locale_not_selected", "root": str(root), "locales": locales})
            if data is None:
                self.warnings.append({"code": "no_base_catalog", "root": str(root)})
                continue
            for catalog in _CATALOGS:
                path = _case_path(data, f"GameData/{catalog}Data.xml")
                if path and path.is_file():
                    self._load(path, data, root, layer, [])
            manifest = _case_path(data, "GameData.xml")
            if manifest:
                self._load(manifest, data, root, layer, [])

    def _load(self, path: Path, data: Path, root: Path, layer: int, active: list[Path]) -> None:
        path = path.resolve()
        if path in active:
            raise SC2Error("catalog_include_cycle", "Catalog include 出现循环", paths=[str(p) for p in [*active, path]])
        if path in self._seen:
            self.warnings.append({"code": "repeated_catalog_include", "file": str(path)})
            return
        self._seen.add(path)
        raw, document = _xml(path)
        document_digest = hashlib.sha256(raw).hexdigest()
        self.files.append(path)
        self.file_sha256[path] = document_digest
        if document.tag not in {"Includes", "Catalog"}:
            raise SC2Error("unsupported_catalog_document", "未知 Catalog 文档根节点", file=str(path), tag=document.tag)
        for element in document:
            if element.tag in {"Catalog", "Include", "Includes"} and element.get("path"):
                relative = element.get("path", "")
                included = _case_path(data, relative)
                # Nested include paths are relative to the current file only
                # when no data-root path resolves; ambiguous resolution fails.
                local = _case_path(path.parent, relative)
                if included and local and included.resolve() != local.resolve():
                    raise SC2Error("ambiguous_catalog_include", "include 同时匹配两条路径", path=relative)
                included = included or local
                if not included or not included.is_file():
                    raise SC2Error("missing_catalog_include", "声明的 Catalog 文件不存在", file=str(path), path=relative)
                if not included.resolve().is_relative_to(data.resolve()):
                    raise SC2Error("unsafe_catalog_path", "include 离开数据组件", path=str(included))
                self._load(included, data, root, layer, [*active, path])
                continue
            catalog = _type_catalog(element.tag)
            if not catalog:
                self.warnings.append({"code": "unsupported_catalog_entry", "file": str(path), "tag": element.tag})
                continue
            patch = _Patch(element, path, root, layer, document_digest)
            object_id = element.get("id")
            if object_id:
                self.objects[(catalog, object_id)].append(patch)
            elif element.get("default") == "1":
                self.defaults[element.tag].append(patch)
            else:
                self.warnings.append({"code": "entry_without_id", "file": str(path), "class": element.tag})
            self._array_hints(element, element.tag, ())

    def _array_hints(self, element: ET.Element, class_name: str, prefix: tuple[str, ...]) -> None:
        counts = Counter(child.tag for child in element)
        for child in element:
            path = (*prefix, child.tag)
            if (child.get("index") is not None or child.tag.endswith("Array")
                    or child.tag in _ARRAY_NAMES or counts[child.tag] > 1):
                self.arrays.add((class_name, path))
            self._array_hints(child, class_name, path)

    def inspect(self, catalog: str, object_id: str) -> dict:
        key = (catalog, object_id)
        if key not in self.objects:
            raise SC2Error("catalog_object_not_found", "已加载的数据中没有该对象", catalog=catalog, object_id=object_id)
        warnings = deepcopy(self.warnings)
        tree, inheritance, sources = self._effective(key, [], warnings)
        fields: dict[str, dict] = {}
        removed: list[dict] = []
        _flatten(tree, "", fields, removed)
        return {"catalog": catalog, "object_id": object_id, "class": self.objects[key][-1].node.tag,
                "fields": fields, "removed": removed, "inheritance": inheritance,
                "sources": sources, "files": [str(p) for p in self.files],
                "warnings": warnings, "engine_parity": False,
                "validation": "static",
                "limitations": ["仅处理所给 roots；不自动推断缺失依赖", "匿名默认仅按精确类名应用；原生类层次和内建默认未知",
                                "数组类型由索引、已知数组名和同级重复推断；非完整引擎 schema", "tokens、宏、表达式不求值"]}

    def _effective(self, key: tuple[str, str], active: list[tuple[str, str]], warnings: list[dict]) -> tuple[_Node, list[str], list[dict]]:
        if key in active:
            raise SC2Error("catalog_parent_cycle", "Catalog parent 出现循环", chain=[list(k) for k in [*active, key]])
        patches = self.objects[key]
        class_name = patches[-1].node.tag
        parent = None
        for patch in patches:
            if "parent" in patch.node.attrib:
                parent = patch.node.get("parent") or None
        result = _Node("Object")
        sources: list[dict] = []
        inheritance: list[str] = []
        for patch in self.defaults.get(class_name, []):
            _merge(result, patch.node, patch.source("class_default"), self.arrays, class_name, (), warnings)
            sources.append(patch.source("class_default"))
        if parent:
            parent_key = (key[0], parent)
            if parent_key in self.objects:
                inherited, ancestors, parent_sources = self._effective(parent_key, [*active, key], warnings)
                _overlay(result, inherited)
                inheritance = [parent, *ancestors]
                sources.extend(parent_sources)
            else:
                warnings.append({"code": "missing_catalog_parent", "object_id": key[1], "parent": parent})
                inheritance.append(parent)
        for patch in patches:
            if patch.node.get("removed") not in (None, "0"):
                raise SC2Error("unsupported_catalog_object_removal", "对象级删除语义尚未验证", object_id=key[1], source=patch.source())
            if patch.node.tag != class_name:
                warnings.append({"code": "catalog_class_changed", "object_id": key[1], "before": patch.node.tag, "after": class_name})
            _merge(result, patch.node, patch.source(), self.arrays, class_name, (), warnings)
            sources.append(patch.source())
        return result, inheritance, sources


@dataclass
class _Value:
    value: str
    source: dict
    history: list[dict] = field(default_factory=list)


@dataclass
class _Node:
    tag: str
    index: str | None = None
    attributes: dict[str, _Value] = field(default_factory=dict)
    children: list[_Node] = field(default_factory=list)
    removed: bool = False
    removal_source: dict | None = None


def _overlay(target: _Node, source: _Node) -> None:
    """Overlay effective inherited tree on defaults without losing siblings."""
    for key, value in source.attributes.items():
        target.attributes[key] = deepcopy(value)
    for node in source.children:
        existing = next((child for child in target.children if (child.tag, child.index) == (node.tag, node.index)), None)
        if existing is None:
            target.children.append(deepcopy(node))
        elif node.removed:
            existing.removed = True
            existing.removal_source = deepcopy(node.removal_source)
            existing.children.clear()
            existing.attributes.clear()
        else:
            existing.removed = False
            _overlay(existing, node)


def _merge(target: _Node, patch: ET.Element, source: dict, arrays: set, class_name: str,
           prefix: tuple[str, ...], warnings: list[dict]) -> None:
    if prefix:
        for attr, value in patch.attrib.items():
            if attr in _CONTROL_ATTRIBUTES:
                continue
            previous = target.attributes.get(attr)
            history = deepcopy(previous.history) if previous else []
            if previous:
                history.append({"value": previous.value, "source": deepcopy(previous.source)})
            target.attributes[attr] = _Value(value, deepcopy(source), history)
            if "##" in value or "$" in value:
                warnings.append({"code": "unevaluated_catalog_expression", "path": ".".join(prefix), "value": value, "source": source})
    if patch.text and patch.text.strip():
        warnings.append({"code": "catalog_text_not_evaluated", "path": ".".join(prefix), "source": source})
    counts = Counter(child.tag for child in patch)
    for child in patch:
        path = (*prefix, child.tag)
        is_array = ((class_name, path) in arrays or child.tag.endswith("Array")
                    or child.tag in _ARRAY_NAMES or counts[child.tag] > 1)
        index = child.get("index")
        if is_array and index is None:
            numbers = [int(node.index) for node in target.children
                       if node.tag == child.tag and node.index is not None and node.index.isdigit()]
            index = str(max(numbers, default=-1) + 1)
            operation = "append"
        else:
            operation = "indexed_merge" if index is not None else "scalar_merge"
        existing = next((node for node in target.children if node.tag == child.tag and node.index == index), None)
        if existing is None:
            existing = _Node(child.tag, index)
            target.children.append(existing)
        child_source = {**source, "operation": operation}
        if child.get("removed") == "1":
            existing.removed = True
            existing.removal_source = {**child_source, "operation": "remove"}
            existing.attributes.clear()
            existing.children.clear()
            continue
        if child.get("removed") not in (None, "0", "1"):
            warnings.append({"code": "unknown_removed_value", "path": ".".join(path), "source": source})
        existing.removed = False
        existing.removal_source = None
        _merge(existing, child, child_source, arrays, class_name, path, warnings)


def _flatten(node: _Node, prefix: str, fields: dict, removed: list) -> None:
    for child in node.children:
        name = child.tag + (f"[{child.index}]" if child.index is not None else "")
        path = f"{prefix}.{name}" if prefix else name
        if child.removed:
            removed.append({"path": path, "source": child.removal_source})
            continue
        for attr, record in child.attributes.items():
            key = path if attr == "value" else f"{path}.{attr}"
            fields[key] = {"value": record.value, "source": record.source, "history": record.history}
        _flatten(child, path, fields, removed)


def inspect_catalog(roots: list[Path], catalog: str, object_id: str) -> dict:
    return _Library(roots).inspect(_catalog_name(catalog), object_id)


class CatalogSession:
    """Read a fixed set of loaded XML documents once for a batch operation.

    A session is an in-memory snapshot of the supplied component files. It
    must be recreated after filesystem changes; no global stale cache exists.
    """

    def __init__(self, roots: list[Path]):
        self._library = _Library(roots)
        self._source_documents: dict[Path, tuple[bytes, _Span]] = {}

    def inspect(self, catalog: str, object_id: str) -> dict:
        return self._library.inspect(_catalog_name(catalog), object_id)

    def search(self, catalog: str, query: str = "", limit: int = 100) -> list[dict]:
        return _search(self._library, catalog, query, limit)

    def trace(self, catalog: str, object_id: str) -> dict:
        return _trace(self._library, catalog, object_id)

    def catalog_names(self) -> list[str]:
        return sorted({kind for kind, _identifier in self._library.objects})

    def object_ids(self, catalog: str) -> list[str]:
        kind = _catalog_name(catalog)
        return sorted(identifier for object_kind, identifier in self._library.objects if object_kind == kind)

    def files(self) -> list[str]:
        return [str(path) for path in self._library.files]

    def file_fingerprints(self) -> dict[str, str]:
        """Hashes of the exact document bytes loaded into this session."""
        return {str(path): value for path, value in self._library.file_sha256.items()}

    def source_entries(self, catalog: str, object_id: str) -> list[dict]:
        """Return exact UTF-8 entry text for exporting selected source layers."""
        key = (_catalog_name(catalog), object_id)
        if key not in self._library.objects:
            raise SC2Error("catalog_object_not_found", "Catalog 对象不存在", catalog=catalog, object_id=object_id)
        return self._entries(self._library.objects[key])

    def default_entries(self, class_name: str) -> list[dict]:
        return self._entries(self._library.defaults.get(class_name, []))

    def _entries(self, patches: list[_Patch]) -> list[dict]:
        entries = []
        occurrences: dict[tuple[Path, str, str | None], int] = defaultdict(int)
        for patch in patches:
            raw = patch.file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != patch.sha256:
                raise SC2Error("catalog_source_changed", "读取期间 Catalog 文件发生变化", source=patch.source())
            if patch.file in self._source_documents:
                _snapshot, document = self._source_documents[patch.file]
            else:
                document = _spans(raw)
                self._source_documents[patch.file] = (raw, document)
            key = (patch.file, patch.node.tag, patch.node.get("id"))
            matches = [node for node in document.children if node.tag == key[1] and node.attributes.get("id") == key[2]]
            position = occurrences[key]
            if position >= len(matches):
                raise SC2Error("catalog_source_changed", "读取期间 Catalog 源对象发生变化", source=patch.source())
            node = matches[position]
            occurrences[key] += 1
            entries.append({**patch.source(), "offset": node.start, "xml": raw[node.start:node.end].decode("utf-8")})
        return entries


def search_catalog(roots: list[Path], catalog: str, query: str = "", limit: int = 100) -> list[dict]:
    return _search(_Library(roots), catalog, query, limit)


def _search(library: _Library, catalog: str, query: str, limit: int) -> list[dict]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10000:
        raise SC2Error("invalid_catalog_limit", "limit 必须为 1 到 10000 的整数")
    catalog = _catalog_name(catalog)
    result = []
    for (kind, object_id), patches in library.objects.items():
        if kind != catalog or query.casefold() not in object_id.casefold():
            continue
        result.append({"catalog": catalog, "object_id": object_id, "class": patches[-1].node.tag,
                       "sources": [patch.source() for patch in patches],
                       "template": any(patch.node.get("default") == "1" for patch in patches)})
    return sorted(result, key=lambda item: item["object_id"].casefold())[:limit]


def _reference_kind(path: str, owner_class: str) -> str | None:
    tags = [re.sub(r"\[[^\]]*\]", "", part) for part in path.split(".")]
    leaf = tags[-1]
    if leaf == "Model" and owner_class.startswith("CModel"):
        return None  # CModel.Model is an asset filename, not a Model ID.
    if leaf == "AbilCmd":
        return "Abil"
    if leaf in {"DefaultButtonFace", "Face"}:
        return "Button"
    if leaf in {"Requirements", "Requirement"}:
        return "Requirement"
    if leaf == "parent":
        return _type_catalog(owner_class)
    for name in ("Unit", "Abil", "Weapon", "Effect", "Behavior", "Validator", "Actor", "Model", "Button", "Upgrade", "Mover", "Turret", "TargetFind", "TargetSort"):
        if leaf == name or leaf == name + "Array":
            return name
        if leaf == "Link" and len(tags) >= 2 and tags[-2] in {name, name + "Array"}:
            return name
    if leaf in {"LaunchEffect", "ImpactEffect", "InitialEffect", "FinalEffect", "PeriodicEffect", "CursorEffect", "ExpireEffect", "EffectOnDeath"}:
        return "Effect"
    if leaf == "NodeArray" and owner_class.startswith("CRequirement"):
        return "RequirementNode"
    return None


def trace_references(roots: list[Path], catalog: str, object_id: str) -> dict:
    return _trace(_Library(roots), catalog, object_id)


def _trace(library: _Library, catalog: str, object_id: str) -> dict:
    catalog = _catalog_name(catalog)
    target = library.inspect(catalog, object_id)
    index: dict[str, list[str]] = defaultdict(list)
    for kind, identifier in library.objects:
        index[identifier].append(kind)
    edges: list[dict] = []
    missing: list[dict] = []
    trace_warnings = []
    cached = getattr(library, "_reference_cache", None)
    for (kind, identifier), patches in ([] if cached is not None else library.objects.items()):
        try:
            effective = library.inspect(kind, identifier)
        except SC2Error as exc:
            if exc.code != "catalog_parent_cycle":
                raise
            trace_warnings.append({"code": exc.code, **exc.details})
            continue
        values = list(effective["fields"].items())
        parent_patch = next((patch for patch in reversed(patches) if "parent" in patch.node.attrib), None)
        if parent_patch and parent_patch.node.get("parent"):
            values.append(("parent", {"value": parent_patch.node.get("parent"), "source": parent_patch.source()}))
        for path, info in values:
            value = info["value"]
            if not value:
                continue
            expected_kind = _reference_kind(path, effective["class"])
            if path.endswith("AbilCmd"):
                value = value.split(",", 1)[0]
            if expected_kind:
                candidates = [expected_kind]
                confidence = "typed_field"
            else:
                candidates = index.get(value, [])
                confidence = "exact_id_candidate"
            for referenced_kind in candidates:
                edge = {"from": {"catalog": kind, "object_id": identifier}, "field": path,
                        "to": {"catalog": referenced_kind, "object_id": value},
                        "source": info["source"], "confidence": confidence}
                if (referenced_kind, value) in library.objects:
                    edges.append(edge)
                else:
                    missing.append(edge)
    if cached is None:
        library._reference_cache = (edges, missing, trace_warnings)
    else:
        edges, missing, trace_warnings = cached
    origin = {"catalog": catalog, "object_id": object_id}
    outgoing = [edge for edge in edges if edge["from"] == origin]
    incoming = [edge for edge in edges if edge["to"] == origin]
    reachable: list[dict] = []
    visited = {(catalog, object_id)}
    pending = [(catalog, object_id)]
    adjacency: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for edge in edges:
        adjacency[(edge["from"]["catalog"], edge["from"]["object_id"])].append(edge)
    while pending:
        item = pending.pop()
        for edge in adjacency[item]:
            ref = (edge["to"]["catalog"], edge["to"]["object_id"])
            if ref not in visited:
                visited.add(ref)
                pending.append(ref)
                reachable.append(edge["to"])
    missing = [edge for edge in missing if (edge["from"]["catalog"], edge["from"]["object_id"]) in visited]
    return {"catalog": catalog, "object_id": object_id, "outgoing": outgoing,
            "incoming": incoming, "reachable": reachable, "missing": missing,
            "edges": [edge for edge in edges if (edge["from"]["catalog"], edge["from"]["object_id"]) in visited],
            "warnings": target["warnings"] + trace_warnings, "engine_parity": False,
            "limitations": ["类型映射覆盖常见字段；其余同 ID 匹配仅为候选引用", "不解释 Actor 事件语法、宏、脚本动态引用"]}


@dataclass
class _Span:
    tag: str
    attributes: dict[str, str]
    start: int
    open_end: int
    self_closing: bool
    close_start: int = 0
    end: int = 0
    children: list[_Span] = field(default_factory=list)


def _tag_end(raw: bytes, start: int) -> int:
    quote = None
    for i in range(start, len(raw)):
        char = raw[i]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in (34, 39):
            quote = char
        elif char == 62:
            return i + 1
    raise SC2Error("invalid_catalog_xml", "XML 标签没有结束")


def _spans(raw: bytes) -> _Span:
    # Expat reports original UTF-8 byte offsets, preserving even Chinese text
    # and comments before/inside the exact edited object.
    if b"\x00" in raw:
        raise SC2Error("unsupported_catalog_encoding", "写入仅支持 UTF-8 或 ASCII XML")
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SC2Error("unsupported_catalog_encoding", "写入仅支持 UTF-8 或 ASCII XML") from exc
    declaration = re.match(br"(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)", raw, re.I)
    if declaration and declaration.group(1).lower() not in {b"utf-8", b"utf8", b"us-ascii", b"ascii"}:
        raise SC2Error("unsupported_catalog_encoding", "不支持此 XML 写入编码")
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
        raise SC2Error("unsafe_xml", "不支持 DTD 或实体声明")
    parser = expat.ParserCreate()
    stack: list[_Span] = []
    document: list[_Span] = []

    def start(tag, attributes):
        offset = parser.CurrentByteIndex
        end = _tag_end(raw, offset)
        span = _Span(tag, dict(attributes), offset, end, raw[offset:end].rstrip().endswith(b"/>"))
        if stack:
            stack[-1].children.append(span)
        else:
            document.append(span)
        stack.append(span)

    def end(tag):
        span = stack.pop()
        if span.self_closing:
            span.close_start = span.open_end
            span.end = span.open_end
        else:
            span.close_start = parser.CurrentByteIndex
            span.end = _tag_end(raw, span.close_start)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as exc:
        raise SC2Error("invalid_catalog_xml", "Catalog XML 不能解析", reason=str(exc)) from exc
    return document[0]


def _parts(field_path: str) -> list[tuple[str, str | None]]:
    result = []
    for part in field_path.split("."):
        match = _PATH_PART.fullmatch(part)
        if not match:
            raise SC2Error("invalid_catalog_field_path", "字段路径格式错误", path=field_path)
        name, index = match.groups()
        if name in _CONTROL_ATTRIBUTES or name in {"id", "parent", "default"} or name.startswith("@") and (index is not None or name[1:] in _CONTROL_ATTRIBUTES | {"id", "parent", "default"}):
            raise SC2Error("catalog_identity_edit_forbidden", "标识、继承和删除标记不能通过字段接口修改", path=field_path)
        result.append((name, index))
    if any(name.startswith("@") for name, _ in result[:-1]):
        raise SC2Error("invalid_catalog_field_path", "属性只能位于路径末尾", path=field_path)
    return result


def _quoted(value: str, quote: bytes = b'"', ascii_only: bool = False) -> bytes:
    value = escape(value, {'"': "&quot;", "'": "&apos;", "\t": "&#9;", "\n": "&#10;", "\r": "&#13;"})
    return value.encode("ascii", errors="xmlcharrefreplace") if ascii_only else value.encode("utf-8")


def _replace_attribute(raw: bytes, node: _Span, attr: str, value: str, ascii_only: bool) -> bytes:
    opening = raw[node.start:node.open_end]
    # Consume whole attribute values, so text resembling another attribute
    # inside a quoted string can never be selected for replacement.
    pattern = re.compile(rb"\s+([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=\s*(['\"])(.*?)\2", re.S)
    matches = [match for match in pattern.finditer(opening) if match.group(1) == attr.encode()]
    if len(matches) > 1:
        raise SC2Error("ambiguous_catalog_attribute", "同一个 XML 标签出现重复属性", attribute=attr)
    if matches:
        match = matches[0]
        replacement = _quoted(value, match.group(2), ascii_only)
        start, end = node.start + match.start(3), node.start + match.end(3)
        return raw[:start] + replacement + raw[end:]
    offset = node.open_end - (2 if node.self_closing else 1)
    return raw[:offset] + b" " + attr.encode() + b'="' + _quoted(value, ascii_only=ascii_only) + b'"' + raw[offset:]


def _indent(raw: bytes, offset: int) -> bytes:
    start = raw.rfind(b"\n", 0, offset) + 1
    content = raw[start:offset]
    return content if not content.strip() else b""


def _insert_child(raw: bytes, parent: _Span, fragment: bytes) -> bytes:
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    parent_indent = _indent(raw, parent.start)
    child_indent = _indent(raw, parent.children[0].start) if parent.children else parent_indent + b"    "
    if not child_indent:
        child_indent = parent_indent + b"    "
    if parent.self_closing:
        offset = parent.open_end - 2
        return (raw[:offset] + b">" + newline + child_indent + fragment + newline
                + parent_indent + b"</" + parent.tag.encode() + b">" + raw[parent.open_end:])
    offset = parent.close_start
    preceding = _indent(raw, offset)
    if preceding:
        offset -= len(preceding)
        insertion = child_indent + fragment + newline
    else:
        insertion = newline + child_indent + fragment + newline + parent_indent
    return raw[:offset] + insertion + raw[offset:]


def plan_catalog_set(root: Path, catalog: str, object_id: str, field_path: str,
                     value: str, expected: str | None = None) -> dict[str, bytes | None]:
    """Plan one exact local field override; never writes files.

    Existing object IDs must be visible in this component. Creating a brand new
    object, picking an absent dependency object's class, and editing ambiguous
    local unindexed arrays are deliberately rejected by this scalar interface.
    ``expected`` compares the existing local attribute, not an unknown engine
    inherited value. An absent field has no local expected value.
    """
    root = Path(root).resolve()
    catalog = _catalog_name(catalog)
    if not isinstance(value, str) or any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise SC2Error("invalid_catalog_value", "字段值必须为有效 XML 字符串")
    parts = _parts(field_path)
    library = _Library([root])
    patches = library.objects.get((catalog, object_id), [])
    if not patches:
        raise SC2Error("catalog_object_not_found", "本地没有可验证类型的对象；先导入或建立明确的本地覆盖", catalog=catalog, object_id=object_id)
    if len(patches) != 1:
        raise SC2Error("ambiguous_catalog_object", "同一本地组件存在多个同 ID 声明，不能自动选择修改位置", object_id=object_id, sources=[p.source() for p in patches])
    patch = patches[0]
    raw = patch.file.read_bytes()
    document = _spans(raw)
    objects = [node for node in document.children if node.tag == patch.node.tag and node.attributes.get("id") == object_id]
    if len(objects) != 1:
        raise SC2Error("ambiguous_catalog_object", "不能唯一定位 XML 对象", object_id=object_id)
    current = objects[0]
    ascii_only = bool(re.match(br"(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding\s*=\s*['\"](?:us-ascii|ascii)['\"]", raw, re.I))
    attr = "value"
    missing = None
    for position, (name, index) in enumerate(parts):
        final = position == len(parts) - 1
        child_matches = [child for child in current.children if child.tag == name and child.attributes.get("index") == index]
        is_attr = final and index is None and (name.startswith("@") or name in current.attributes
                   or position > 0 and name in _ATTRIBUTE_NAMES and not child_matches)
        if is_attr:
            attr = name.lstrip("@")
            break
        if name.startswith("@"):
            raise SC2Error("invalid_catalog_field_path", "属性只能出现在现有节点末尾")
        if (name.endswith("Array") or name in _ARRAY_NAMES) and index is None:
            raise SC2Error("catalog_array_index_required", "数组字段必须指定索引", field_path=field_path)
        same_tag = [child for child in current.children if child.tag == name]
        if index is not None and any(child.attributes.get("index") is None for child in same_tag):
            raise SC2Error("ambiguous_unindexed_array", "本地无索引数组的有效槽位依赖加载顺序，不能直接按位置编辑", field_path=field_path)
        if len(child_matches) > 1:
            raise SC2Error("ambiguous_catalog_field", "字段路径匹配多个节点", field_path=field_path)
        if index is None and any(child.attributes.get("index") is not None for child in same_tag):
            raise SC2Error("catalog_array_index_required", "数组字段必须指定索引", field_path=field_path)
        if not child_matches:
            if (name.endswith("Array") or name in _ARRAY_NAMES) and index is None:
                raise SC2Error("catalog_array_index_required", "新增数组字段必须指定索引", field_path=field_path)
            missing = position
            break
        current = child_matches[0]
        if current.attributes.get("removed") == "1":
            raise SC2Error("catalog_field_removed", "目标数组项已删除，不能隐式恢复", field_path=field_path)
    existing = current.attributes.get(attr) if missing is None else None
    if expected is not None and existing != expected:
        raise SC2Error("catalog_expected_mismatch", "本地字段与期望值不同", expected=expected, actual=existing)
    if missing is None:
        if existing == value:
            return {}
        candidate = _replace_attribute(raw, current, attr, value, ascii_only)
    else:
        remaining = parts[missing:]
        leaf_attr = "value"
        if len(remaining) > 1 and remaining[-1][1] is None and (remaining[-1][0].startswith("@") or remaining[-1][0] in _ATTRIBUTE_NAMES):
            leaf_attr = remaining[-1][0].lstrip("@")
            remaining = remaining[:-1]
        if not remaining or any(name.startswith("@") for name, _ in remaining):
            raise SC2Error("invalid_catalog_field_path", "不能建立此字段路径", field_path=field_path)
        fragment = b""
        for i, (name, index) in reversed(list(enumerate(remaining))):
            if (name.endswith("Array") or name in _ARRAY_NAMES) and index is None:
                raise SC2Error("catalog_array_index_required", "新增数组字段必须指定索引", field_path=field_path)
            attrs = b' index="' + _quoted(index, ascii_only=ascii_only) + b'"' if index is not None else b""
            if i == len(remaining) - 1:
                fragment = b"<" + name.encode() + attrs + b" " + leaf_attr.encode() + b'="' + _quoted(value, ascii_only=ascii_only) + b'"/>'
            else:
                fragment = b"<" + name.encode() + attrs + b">" + fragment + b"</" + name.encode() + b">"
        candidate = _insert_child(raw, current, fragment)
    _spans(candidate)
    return {patch.file.relative_to(root).as_posix(): candidate}
