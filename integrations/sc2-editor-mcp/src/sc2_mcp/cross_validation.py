"""Compare provable references before and after a complete candidate change set.

Only an independent workspace is written. CatalogSession supplies the actual
include/merge view; both views use a frozen copy of the local XML/scripts. A
dependency declaration change requires explicit before/after resolved roots.
Existing missing references are retained as diagnostics, never grandfathered by
count alone. Actor event strings, binary M3 references and dynamic Galaxy remain
outside this validator's proof boundary.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

from .catalog import CatalogSession
from .dependencies import decode_declarations
from .errors import SC2Error
from .script import _strip_comments_strings
from .storage import atomic_write, digest, guard_absolute_path, map_files, normalize_relative_path, safe_path

_LITERAL = re.compile(r"^[\w.-]+$", re.UNICODE)
_SPATIAL_FUNCTIONS = {
    "PointFromId": {"ObjectPoint"}, "UnitFromId": {"ObjectUnit"},
    "DoodadFromId": {"ObjectDoodad"}, "CameraFromId": {"Camera", "ObjectCamera"},
    "CameraInfoFromId": {"Camera", "ObjectCamera"}, "RegionFromId": {"region"},
    "UnitGroupFromId": {"Group:ObjectUnit"}, "DoodadGroupFromId": {"Group:ObjectDoodad"},
    "ObjectGroupFromId": {"Group"},
}


def _xml(data, source):
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise SC2Error("unsupported_xml", "引用验证不接受 DTD 或实体声明", source=source)
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise SC2Error("invalid_xml", "引用源 XML 不能解析", source=source, error=str(exc)) from exc


def _dependencies(data):
    if data is None:
        raise SC2Error("dependency_validation_context_required", "不能对缺失 DocumentInfo 推断依赖")
    return decode_declarations(data)


def _relevant(relative):
    folded = relative.casefold()
    return (folded in {"objects", "regions", "documentinfo"} or folded.endswith(".galaxy")
            or (folded.endswith(".xml") and any(p.endswith(".sc2data") for p in folded.split("/"))))


def _roots(values, root):
    if not isinstance(values, (list, tuple)):
        raise SC2Error("invalid_dependency_roots", "引用验证需要已解析的组件目录列表")
    result = []
    for value in values:
        path = guard_absolute_path(Path(value)).resolve()
        if not path.is_dir():
            raise SC2Error("dependency_not_materialized", "引用验证不能直接使用归档或缺失依赖", path=str(path))
        if path in result:
            raise SC2Error("duplicate_dependency_root", "引用验证加载链包含重复根目录", path=str(path))
        result.append(path)
    if root not in result:
        result.append(root)
    return result


def _edge_key(edge):
    return (edge["from"]["catalog"], edge["from"]["object_id"], edge["field"],
            edge["to"]["catalog"], edge["to"]["object_id"])


def _catalog_graph(session):
    identifiers = [(kind, identifier) for kind in session.catalog_names() for identifier in session.object_ids(kind)]
    cycles = {}
    for kind, identifier in identifiers:
        try:
            session.trace(kind, identifier)
            break
        except SC2Error as exc:
            if exc.code != "catalog_parent_cycle":
                raise
            chain = tuple(sorted({tuple(item) for item in exc.details.get("chain", [])}))
            cycles[chain] = {"kind": "catalog_parent_cycle", **exc.details}
    # CatalogSession.trace constructs a graph for the whole session once. Reading
    # that internal cache avoids rebuilding reachability for every single object.
    cache = getattr(session._library, "_reference_cache", ([], [], []))
    _edges, missing, warnings = cache
    for warning in warnings:
        if warning.get("code") == "catalog_parent_cycle":
            chain = tuple(sorted({tuple(item) for item in warning.get("chain", [])}))
            cycles[chain] = {"kind": "catalog_parent_cycle", **warning}
    proven, unknown = {}, []
    for edge in missing:
        if edge.get("confidence") != "typed_field":
            continue
        if not _LITERAL.fullmatch(edge["to"]["object_id"]):
            unknown.append({"kind": "nonliteral_catalog_reference", "edge": edge})
        else:
            proven[_edge_key(edge)] = {"kind": "catalog_reference", **edge}
    return proven, cycles, unknown, set(identifiers)


def _check_dependency_sources(before_session, after_session, roots, root, area):
    expected = {}
    for session in (before_session, after_session):
        for name, fingerprint in session.file_fingerprints().items():
            path = Path(name)
            if path.is_relative_to(area):
                continue
            if name in expected and expected[name] != fingerprint:
                raise SC2Error("reference_dependency_changed", "引用验证的前后视图读取到了不同的依赖内容", path=name)
            expected[name] = fingerprint
    external = []
    for path in roots:
        if not path.is_relative_to(root) and path not in external:
            external.append(path)
    if not external:
        return 0
    try:
        # Reload only selected Catalog documents, including include manifests.
        # Comparing the loaded set also catches newly added standard catalogs
        # without hashing unrelated textures or other large dependency assets.
        current = CatalogSession(external).file_fingerprints()
    except (OSError, SC2Error) as exc:
        raise SC2Error("reference_dependency_changed", "引用验证期间依赖目录无法再次读取", error=str(exc)) from exc
    if current != expected:
        differences = [name for name in sorted(set(expected) | set(current)) if expected.get(name) != current.get(name)]
        raise SC2Error("reference_dependency_changed", "引用验证期间依赖文件或加载清单发生变化", paths=differences)
    return len(expected)


def _spatial(files):
    result = []
    for component, expected in (("Objects", "PlacedObjects"), ("Regions", "Regions")):
        if component not in files:
            continue
        document = _xml(files[component], component)
        if document.tag != expected:
            raise SC2Error("unsupported_spatial_format", "空间组件根元素不正确", component=component)
        seen = set()
        for node in document:
            attribute = "id" if component == "Regions" else "Id"
            identifier = node.get(attribute)
            if identifier is None or not identifier.isdigit():
                continue
            key = int(identifier)
            if key in seen:
                raise SC2Error("ambiguous_spatial_id", "空间组件含重复编号", component=component, object_id=key)
            seen.add(key)
            result.append((component, node.tag, key, node.attrib, list(node)))
    return result


def _spatial_catalog_refs(objects, session, known, previous=None):
    missing, unknown = {}, []
    previous = previous or session
    previous_known = {(kind, identifier) for kind in previous.catalog_names() for identifier in previous.object_ids(kind)}
    for component, kind, identifier, attrs, _children in objects:
        if kind == "ObjectUnit" and attrs.get("UnitType"):
            field, target_kind, value = "UnitType", "Unit", attrs["UnitType"]
        elif kind == "ObjectDoodad" and (attrs.get("DoodadType") or attrs.get("Type")):
            field = "DoodadType" if attrs.get("DoodadType") else "Type"
            value = attrs[field]
            target_kind = None
            for view, index in ((session, known), (previous, previous_known)):
                if ("Actor", value) in index and view.inspect("Actor", value)["class"].startswith("CActorDoodad"):
                    target_kind = "Actor"
                    break
            if target_kind is None:
                unknown.append({"kind": "doodad_catalog_type_unverified", "source": component,
                                "object_id": identifier, "field": field, "value": value})
                continue
        else:
            continue
        edge = {"kind": "placed_object_catalog_reference", "source": component, "object_kind": kind,
                "object_id": identifier, "field": field, "to": {"catalog": target_kind, "object_id": value}}
        if not _LITERAL.fullmatch(value):
            unknown.append({**edge, "reason": "nonliteral_reference"})
        elif (target_kind, value) not in known:
            missing[(component, kind, identifier, field, target_kind, value)] = edge
    return missing, unknown


def _script_refs(files, objects, known):
    spatial = {}
    for component, kind, identifier, attrs, children in objects:
        spatial.setdefault(kind, set()).add(identifier)
        if kind == "Group" and attrs.get("Type"):
            spatial.setdefault("Group:" + attrs["Type"], set()).add(identifier)
    missing, unit_calls, unknown = {}, {}, []
    for relative, raw in files.items():
        if not relative.casefold().endswith(".galaxy"):
            continue
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SC2Error("invalid_script_encoding", "引用源脚本不是 UTF-8", source=relative) from exc
        code, diagnostics = _strip_comments_strings(text)
        if diagnostics:
            raise SC2Error("invalid_script_lexing", "引用源脚本的字符串或注释未闭合", source=relative, diagnostics=diagnostics)
        for match in re.finditer(r"\b([A-Za-z_]\w*FromId)\s*\(\s*(0[xX][\da-fA-F]+|\d+)\s*\)", code):
            function, value = match.groups()
            if function not in _SPATIAL_FUNCTIONS:
                continue
            identifier = int(value, 16 if value.lower().startswith("0x") else 10)
            if not any(identifier in spatial.get(kind, set()) for kind in _SPATIAL_FUNCTIONS[function]):
                key = (relative, function, identifier)
                missing[key] = {"kind": "galaxy_spatial_reference", "source": relative, "function": function,
                                "object_id": identifier, "line": text.count("\n", 0, match.start()) + 1}
        for call in re.finditer(r"\bUnitCreate\s*\(", code):
            # Native UnitCreate's second argument is Unit type. Accept only a
            # literal second argument and a simple first argument; do not guess
            # nested expressions, custom wrappers or dynamic variables.
            literal = re.match(r'UnitCreate\s*\(\s*[^,()]+,\s*"((?:\\.|[^"\\])*)"\s*,', text[call.start():])
            if not literal:
                unknown.append({"kind": "dynamic_unit_create", "source": relative,
                                "line": text.count("\n", 0, call.start()) + 1})
                continue
            value = re.sub(r'\\(["\\])', r'\1', literal.group(1))
            key = (relative, value)
            unit_calls[key] = {"kind": "galaxy_unit_type", "source": relative, "value": value,
                               "line": text.count("\n", 0, call.start()) + 1, "resolved": ("Unit", value) in known}
    for component, kind, identifier, attrs, children in objects:
        if kind != "Group":
            continue
        expected = attrs.get("Type")
        if expected not in {"ObjectUnit", "ObjectDoodad", "ObjectPoint"}:
            unknown.append({"kind": "group_type_unverified", "source": component, "object_id": identifier})
            continue
        for member in children:
            value = member.get("Id", "")
            if member.tag == "GroupObject" and value.isdigit() and int(value) not in spatial.get(expected, set()):
                missing[(component, "Group", identifier, int(value))] = {
                    "kind": "group_member_reference", "source": component, "group_id": identifier,
                    "object_kind": expected, "object_id": int(value)}
    return missing, unit_calls, unknown


def validate_references(root: Path, changes: dict[str, bytes | None], dependency_roots, workspace: Path) -> dict:
    """Reject newly missing typed links while preserving pre-existing diagnostics.

    dependency_roots is an ordered list of materialized component roots for
    ordinary edits, or {'before': [...], 'after': [...]} when declarations change.
    The source root may be present and is appended if absent. Resolved roots are
    caller supplied; no completeness or engine equivalence is inferred here.
    workspace must lie outside every supplied source directory.
    """
    root = guard_absolute_path(Path(root)).resolve()
    if not root.is_dir() or not isinstance(changes, dict):
        raise SC2Error("invalid_reference_input", "需要有效组件目录和候选修改表")
    canonical = {}
    for relative, data in changes.items():
        rel = normalize_relative_path(relative)
        if rel in canonical or (data is not None and not isinstance(data, bytes)):
            raise SC2Error("invalid_reference_input", "候选路径重复或内容不是 bytes")
        canonical[rel] = data
    limitations = ["仅覆盖所给依赖目录，不证明依赖完整或引擎合并完全一致。",
                   "不解释 Actor 事件语法、模型二进制引用或 Galaxy 动态调用。",
                   "对象类型无法由已知 Catalog 证明的装饰物引用仅列为未知。"]
    if not any(_relevant(rel) for rel in canonical):
        return {"static": "not_applicable", "scope": "no_catalog_or_spatial_reference_source_changed",
                "engine_parity": False, "limitations": limitations}
    mapping = isinstance(dependency_roots, dict)
    if mapping:
        if set(dependency_roots) != {"before", "after"}:
            raise SC2Error("invalid_dependency_roots", "依赖上下文映射必须包含 before 和 after")
        before_roots = _roots(dependency_roots["before"], root)
        after_roots = _roots(dependency_roots["after"], root)
    else:
        before_roots = _roots(dependency_roots, root)
        after_roots = list(before_roots)
    if "DocumentInfo" in canonical:
        before_deps = _dependencies(safe_path(root, "DocumentInfo").read_bytes())
        after_deps = _dependencies(canonical["DocumentInfo"])
        if before_deps != after_deps and not mapping:
            raise SC2Error("dependency_validation_context_required", "依赖声明改变时必须分别提供修改前后的已解析加载链")
    workspace = guard_absolute_path(Path(workspace)).resolve()
    if any(workspace.is_relative_to(source) for source in {*before_roots, *after_roots, root}):
        raise SC2Error("unsafe_validation_workspace", "引用验证工作目录不能位于源工程或依赖目录内")
    area = workspace / ("references-" + uuid.uuid4().hex)
    before_stage, after_stage = area / "before.SC2Map", area / "after.SC2Map"
    before_stage.mkdir(parents=True, exist_ok=False)
    after_stage.mkdir(parents=True, exist_ok=False)
    originals = {rel: path.read_bytes() for rel, path in map_files(root) if _relevant(rel)}
    candidates = dict(originals)
    for rel, data in canonical.items():
        if not _relevant(rel):
            continue
        if data is None:
            candidates.pop(rel, None)
        else:
            candidates[rel] = data
    for stage, files in ((before_stage, originals), (after_stage, candidates)):
        for rel, data in files.items():
            atomic_write(safe_path(stage, rel), data)
    def redirected(roots, stage):
        redirected_roots=[]
        for path in roots:
            if path.is_relative_to(root):
                target=stage/path.relative_to(root)
                # SourceContext explicitly includes locale roots even when no
                # Catalog reference-bearing files exist in that locale.
                target.mkdir(parents=True,exist_ok=True)
                redirected_roots.append(target)
            else:redirected_roots.append(path)
        return redirected_roots
    before_session = CatalogSession(redirected(before_roots, before_stage))
    after_session = CatalogSession(redirected(after_roots, after_stage))
    before_missing, before_cycles, before_unknown, before_ids = _catalog_graph(before_session)
    after_missing, after_cycles, after_unknown, after_ids = _catalog_graph(after_session)
    new_missing = [edge for key, edge in after_missing.items() if key not in before_missing]
    new_missing += [value for key, value in after_cycles.items() if key not in before_cycles]
    before_objects, after_objects = _spatial(originals), _spatial(candidates)
    before_placed, _ = _spatial_catalog_refs(before_objects, before_session, before_ids)
    after_placed, placed_unknown = _spatial_catalog_refs(after_objects, after_session, after_ids, before_session)
    new_missing += [value for key, value in after_placed.items() if key not in before_placed]
    before_spatial, before_calls, _ = _script_refs(originals, before_objects, before_ids)
    after_spatial, after_calls, script_unknown = _script_refs(candidates, after_objects, after_ids)
    new_missing += [value for key, value in after_spatial.items() if key not in before_spatial]
    for key, call in after_calls.items():
        if call["resolved"]:
            continue
        if key in before_calls and before_calls[key]["resolved"]:
            new_missing.append(call)
        else:
            script_unknown.append({**call, "reason": "unit_type_not_in_supplied_roots"})
    # Domain callers receive a clear conflict even outside a enclosing transaction.
    current = {rel: digest(path.read_bytes()) for rel, path in map_files(root) if _relevant(rel)}
    if current != {rel: digest(data) for rel, data in originals.items()}:
        raise SC2Error("reference_source_changed", "引用验证期间源地图发生变化")
    checked_dependency_files = _check_dependency_sources(
        before_session, after_session, [*before_roots, *after_roots], root, area)
    report = {"static": "passed" if not new_missing else "failed", "scope": "new_typed_catalog_and_literal_spatial_references",
              "new_missing": new_missing, "existing_catalog_missing_count": len(before_missing),
              "existing_spatial_missing_count": len(before_placed) + len(before_spatial),
              "catalog_objects_checked": len(after_ids), "unresolved": after_unknown + placed_unknown + script_unknown,
              "dependency_context": "caller_supplied_before_after" if mapping else "caller_supplied_same_load_order",
              "dependency_files_checked": checked_dependency_files,
              "engine_parity": False, "workspace": str(area), "limitations": limitations}
    if new_missing:
        raise SC2Error("new_missing_references", "候选引入新的可证明引用断链", report=report)
    return report
