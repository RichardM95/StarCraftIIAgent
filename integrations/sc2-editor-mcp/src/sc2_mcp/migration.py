"""Reviewable selected-object migrations into a new component SC2Mod.

The output keeps the source project's dependency declarations. Dependency
objects stay in those dependencies; only local definitions, local reference
closure, local asset overrides and referenced local strings are copied. This
avoids loading Blizzard definitions twice and appending their arrays twice.
Every function is read-only. Candidate maps are written only by the host into
a new destination. A valid empty mod template is mandatory; no map/mod shell
is invented. Structural template verification is not editor acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .assets import inspect_assets, missing_asset_references, plan_asset_import
from .catalog import CatalogSession
from .dependencies import plan_dependencies, resolve_dependencies
from .errors import SC2Error
from .shell import header_dependencies

_EXCLUDED = {".git", ".venv", ".sc2-mcp", "_codex_backups", "__pycache__", ".pytest_cache", "node_modules"}
_ASSET_SUFFIXES = {".m3", ".m3a", ".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".ogg",
                   ".wav", ".mp3", ".flac", ".wem", ".mp4", ".ogv", ".avi", ".sc2layout", ".anim", ".m4a", ".ttf", ".otf"}
_GENERATED_CATALOG = "Base.SC2Data/GameData/MigratedSelection.xml"


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _xml(data: bytes, path: Path | str) -> ET.Element:
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", data, re.I):
        raise SC2Error("unsafe_migration_xml", "迁移不接受 DTD 或实体声明", path=str(path))
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise SC2Error("invalid_migration_xml", "迁移 XML 无法解析", path=str(path), reason=str(exc)) from exc


def _template_files(root: Path) -> dict[str, bytes]:
    result = {}
    seen = set()
    for folder, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name.casefold() not in _EXCLUDED)
        for name in [*directories, *filenames]:
            path = Path(folder) / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise SC2Error("linked_migration_template", "模板不能包含链接目录或文件", path=str(path))
        for name in sorted(filenames):
            if name.casefold().endswith((".bak", ".backup", ".log")):
                continue
            path = Path(folder) / name
            if path.stat().st_nlink > 1:
                raise SC2Error("linked_migration_template", "模板不能包含硬链接文件", path=str(path))
            relative = path.relative_to(root).as_posix()
            if relative.casefold() in seen:
                raise SC2Error("migration_case_collision", "模板存在大小写冲突", path=relative)
            seen.add(relative.casefold())
            result[relative] = path.read_bytes()
    return result


def _validate_template(template_root: Path) -> tuple[dict, dict[str, bytes]]:
    root = Path(template_root).resolve()
    if root.suffix.casefold() != ".sc2mod" or not root.is_dir():
        raise SC2Error("mod_template_required", "必须提供独立组件 .SC2Mod 模板目录", path=str(root))
    files = _template_files(root)
    required = {"DocumentInfo", "DocumentHeader", "ComponentList.SC2Components"}
    if not required <= files.keys():
        raise SC2Error("mod_template_shell_missing", "模组模板缺少经过检查的外壳组件", missing=sorted(required - files.keys()))
    components = _xml(files["ComponentList.SC2Components"], root / "ComponentList.SC2Components")
    if components.tag != "Components":
        raise SC2Error("invalid_mod_template", "模板组件列表根节点错误")
    required_components = {(item.get("Type"), (item.text or "").strip()) for item in components}
    if not {("gada", "GameData"), ("info", "DocumentInfo")} <= required_components:
        raise SC2Error("invalid_mod_template", "模板必须声明 GameData 和 DocumentInfo")
    unsupported = [item.get("Type") for item in components if item.tag != "DataComponent" or item.get("Type") not in {"gada", "info", "text", "attr"}]
    if unsupported or any(name in files for name in {"MapInfo", "MapScript.galaxy", "Triggers", "t3Terrain.xml", "Objects", "Regions"}):
        raise SC2Error("nonempty_mod_template", "迁移需要空数据模组模板，不能套用地图或脚本工程外壳", components=unsupported)
    document = _xml(files["DocumentInfo"], root / "DocumentInfo")
    if document.tag != "DocInfo":
        raise SC2Error("invalid_mod_template", "模板 DocumentInfo 无效")
    # Public dependency planner checks that both existing declarations agree.
    graph = resolve_dependencies(root, [])
    dependencies = next(node["dependencies"] for node in graph["nodes"] if node["kind"] == "root")
    header = header_dependencies(files["DocumentHeader"])
    if header["values"] != dependencies:
        raise SC2Error("shell_mismatch", "模板依赖声明与头部不一致")
    template_catalog = CatalogSession([root])
    for filename in template_catalog.files():
        parsed = _xml(Path(filename).read_bytes(), filename)
        if parsed.tag == "Catalog" and any(node.tag.startswith("C") and node.tag not in {"Catalog"} for node in parsed):
            raise SC2Error("nonempty_mod_template", "模组模板已有数据对象或默认覆盖", file=filename)
    return {"root": str(root), "static": "passed", "editor": "not_verified", "runtime": "not_verified",
            "header_version": header["version"], "files": {name: _hash(data) for name, data in files.items()}}, files


def _append_xml_child(raw: bytes, fragment: bytes, root_tag: str) -> bytes:
    """Append to a verified empty-ish template document without reserialization."""
    parsed = _xml(raw, root_tag)
    if parsed.tag != root_tag or b"\x00" in raw:
        raise SC2Error("unsupported_template_xml", "模板 XML 结构或编码不支持局部追加", root=root_tag)
    try:
        raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise SC2Error("unsupported_template_xml", "模板 XML 必须为 UTF-8 或 ASCII") from exc
    # XML has already been validated; mask comments/PIs so fake close tags do
    # not become insertion points. Length remains byte-identical.
    masked = re.sub(br"<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!\[CDATA\[[\s\S]*?\]\]>", lambda match: b" " * len(match.group()), raw)
    closing = list(re.finditer(rb"</" + root_tag.encode() + rb"\s*>", masked))
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    if closing:
        offset = closing[-1].start()
        start_line = raw.rfind(b"\n", 0, offset) + 1
        indent = raw[start_line:offset]
        if not indent.strip():
            offset = start_line
        return raw[:offset] + b"    " + fragment + newline + raw[offset:]
    opening = re.search(rb"<" + root_tag.encode() + rb"(?:[^>\"']|\"[^\"]*\"|'[^']*')*/>", masked)
    if not opening:
        raise SC2Error("unsupported_template_xml", "不能定位模板根节点")
    return (raw[:opening.end() - 2] + b">" + newline + b"    " + fragment + newline
            + b"</" + root_tag.encode() + b">" + raw[opening.end():])


def _reference_key(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) > 1 and parts[0].casefold().endswith((".sc2assets", ".sc2data")):
        normalized = "/".join(parts[1:])
    return normalized.casefold()


def _asset_value(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return normalized.casefold().startswith("assets/") or Path(normalized).suffix.casefold() in _ASSET_SUFFIXES


def _selected_localization(source: Path, roots: list[Path], field_values: set[str], template_files: dict,
                           unresolved: list[dict]) -> tuple[dict[str, bytes], list[dict], set[str]]:
    candidate = {}
    copied = []
    locales = set()
    known_keys = set()
    for root in roots:
        for locale_dir in sorted(root.glob("*.SC2Data")):
            if not re.fullmatch(r"[a-z]{2}[A-Z]{2}\.SC2Data", locale_dir.name):
                continue
            path = locale_dir / "LocalizedData/GameStrings.txt"
            if not path.is_file():
                continue
            try:
                raw = path.read_bytes()
                text = raw.decode("utf-8-sig")
            except UnicodeError:
                unresolved.append({"kind": "localization_encoding", "file": str(path)})
                continue
            matched = []
            found = set()
            for line in text.splitlines(keepends=True):
                if "=" not in line or line.lstrip().startswith("//"):
                    continue
                key = line.split("=", 1)[0]
                if key not in field_values:
                    continue
                if key in found:
                    unresolved.append({"kind": "duplicate_localization_key", "file": str(path), "key": key})
                    continue
                found.add(key)
                known_keys.add(key)
                matched.append(line)
            if root != source or not matched:
                continue
            relative = path.relative_to(source).as_posix()
            existing = template_files.get(relative, b"")
            if existing:
                old_keys = {line.split("=", 1)[0] for line in existing.decode("utf-8-sig").splitlines() if "=" in line}
                if old_keys & found:
                    unresolved.append({"kind": "template_localization_collision", "file": relative, "keys": sorted(old_keys & found)})
                    continue
            newline = b"\r\n" if b"\r\n" in (existing or raw) else b"\n"
            body = "".join(matched).encode("utf-8")
            if existing and not existing.endswith((b"\n", b"\r")):
                existing += newline
            candidate[relative] = existing + body
            locale = locale_dir.name.split(".", 1)[0]
            locales.add(locale)
            copied.append({"file": relative, "keys": sorted(found), "source_sha256": _hash(raw)})
    for value in sorted(field_values):
        if re.match(r"^[A-Za-z]+/(?:Name|Tooltip|Description|EditorName|LifeArmorName|ShieldArmorName)/", value) and value not in known_keys:
            unresolved.append({"kind": "localization_key_not_found", "key": value})
    return candidate, copied, locales


def _build(source_root: Path, selections: list[dict[str, str]], template_root: Path,
           search_roots: list[Path] | None = None, source_context: dict | None = None) -> tuple[dict, dict[str, bytes | None]]:
    source, template = Path(source_root).resolve(), Path(template_root).resolve()
    if not selections or any(set(item) != {"catalog", "object_id"} or not item["catalog"] or not item["object_id"] for item in selections):
        raise SC2Error("migration_selection_required", "选择必须包含 catalog 和 object_id")
    template_report, template_files = _validate_template(template)
    if source_context is not None:
        from .source_context import assert_source_context_current
        assert_source_context_current(source_context)
        if Path(source_context["root"]).resolve() != source:
            raise SC2Error("source_context_root_mismatch", "迁移上下文不是所选来源")
        graph = source_context["dependency_report"]
        roots = [Path(path) for path in source_context["roots"]]
    else:
        graph = resolve_dependencies(source, search_roots or [])
        roots = [Path(path) for path in graph["load_order"] if Path(path).is_dir()]
    session = CatalogSession(roots)
    unresolved = []
    for category in ("missing", "incomplete", "cycles"):
        unresolved.extend({"kind": "dependency_" + category, "detail": issue} for issue in graph[category])
    if source_context is None:
        unresolved.extend({"kind": "archive_catalog_not_materialized", "path": path} for path in graph["load_order"] if not Path(path).is_dir())
    elif not source_context.get("complete"):
        unresolved.extend({"kind": "source_context_unknown", "detail": issue} for issue in source_context.get("unknown", [])
                          if issue.get("code") != "client_build_not_selected")
    selected = set()
    edge_map = {}
    missing_references = []
    for item in selections:
        inspected = session.inspect(item["catalog"], item["object_id"])
        key = (inspected["catalog"], inspected["object_id"])
        selected.add(key)
        traced = session.trace(*key)
        for edge in traced["edges"]:
            origin = (edge["from"]["catalog"], edge["from"]["object_id"])
            edge_map.setdefault(origin, []).append(edge)
        missing_references.extend(traced["missing"])
    closure = set(selected)
    pending = list(selected)
    while pending:
        key = pending.pop()
        for edge in edge_map.get(key, []):
            if edge["confidence"] != "typed_field":
                unresolved.append({"kind": "unverified_reference_candidate", "edge": edge})
                continue
            target = (edge["to"]["catalog"], edge["to"]["object_id"])
            if target not in closure:
                closure.add(target)
                pending.append(target)
    for edge in missing_references:
        if (edge["from"]["catalog"], edge["from"]["object_id"]) in closure:
            unresolved.append({"kind": "missing_catalog_reference", "edge": edge})
    # Actor event bindings can point backwards to Unit/Effect. They are not
    # ordinary Catalog links; report this gap rather than silently omitting it.
    if any(kind in {"Unit", "Effect"} for kind, _ in closure) and session.object_ids("Actor"):
        unresolved.append({"kind": "implicit_actor_bindings_unverified",
                           "detail": "Unit/Effect 到 Actor 的事件反向绑定尚未完整解析；可把相关 Actor 显式加入 selections"})
    entries = {}
    moved, retained = [], []
    field_values = set()
    sources = {}
    classes = set()
    for kind, object_id in sorted(closure):
        inspected = session.inspect(kind, object_id)
        classes.add(inspected["class"])
        field_values.update(info["value"] for info in inspected["fields"].values())
        for warning in inspected["warnings"]:
            if warning["code"] in {"missing_catalog_parent", "catalog_class_changed", "unevaluated_catalog_expression", "catalog_text_not_evaluated"}:
                unresolved.append({"kind": "catalog_semantics", "catalog": kind, "object_id": object_id, "detail": warning})
        local_entries = []
        for entry in session.source_entries(kind, object_id):
            sources[entry["file"]] = entry["sha256"]
            if Path(entry["root"]).resolve() == source:
                entries[(entry["file"], entry["offset"])] = entry
                local_entries.append(entry["file"])
        item = {"catalog": kind, "object_id": object_id, "sources": inspected["sources"]}
        if local_entries:
            moved.append(item)
        else:
            retained.append(item)
        if kind == "Actor" and any(".Send" in field or field.endswith(".Terms") for field in inspected["fields"]):
            unresolved.append({"kind": "actor_event_semantics_unverified", "object_id": object_id})
    for class_name in sorted(classes):
        for entry in session.default_entries(class_name):
            if Path(entry["root"]).resolve() == source:
                entries[(entry["file"], entry["offset"])] = entry
                sources[entry["file"]] = entry["sha256"]
                unresolved.append({"kind": "class_default_broad_effect", "class": class_name, "source": entry["file"]})
    changes = dict(template_files)
    source_dependencies = next(node["dependencies"] for node in graph["nodes"] if node["kind"] == "root")
    changes.update(plan_dependencies(template, source_dependencies))
    if entries:
        if _GENERATED_CATALOG.casefold() in {path.casefold() for path in changes}:
            raise SC2Error("migration_template_collision", "模板已占用迁移输出路径", path=_GENERATED_CATALOG)
        file_order = {path: index for index, path in enumerate(session.files())}
        ordered = sorted(entries.values(), key=lambda entry: (file_order[entry["file"]], entry["offset"]))
        raw_catalog = '<?xml version="1.0" encoding="utf-8"?>\n<Catalog>\n' + '\n'.join(entry["xml"] for entry in ordered) + '\n</Catalog>\n'
        changes[_GENERATED_CATALOG] = raw_catalog.encode("utf-8")
        manifest_path = "Base.SC2Data/GameData.xml"
        existing = changes.get(manifest_path, b'<?xml version="1.0" encoding="utf-8"?>\n<Includes/>\n')
        changes[manifest_path] = _append_xml_child(existing, b'<Catalog path="GameData/MigratedSelection.xml"/>', "Includes")
    inventory = {}
    for layer, root in enumerate(roots):
        listing = inspect_assets(root)
        for asset in listing["assets"]:
            inventory.setdefault(_reference_key(asset["logical_path"]), []).append({**asset, "root": str(root), "layer": layer})
    audited = missing_asset_references(roots)
    asset_requests = {value for value in field_values if _asset_value(value)}
    copied_assets, retained_assets = [], []
    asset_seen = set()
    while asset_requests:
        reference = asset_requests.pop()
        lookup = _reference_key(reference)
        if lookup in asset_seen:
            continue
        asset_seen.add(lookup)
        if re.search(r"[@#$%{}*?]", reference):
            unresolved.append({"kind": "unresolved_asset_macro", "reference": reference})
            continue
        matches = inventory.get(lookup, [])
        if not matches:
            unresolved.append({"kind": "missing_asset", "reference": reference})
            continue
        highest = max(item["layer"] for item in matches)
        winners = [item for item in matches if item["layer"] == highest]
        if len(winners) != 1:
            unresolved.append({"kind": "asset_collision", "reference": reference, "candidates": winners})
            continue
        winner = winners[0]
        if Path(winner["root"]).resolve() != source:
            retained_assets.append({"reference": reference, **winner})
            continue
        asset_path = source / winner["path"]
        try:
            planned = plan_asset_import(template, asset_path, winner["path"])
        except SC2Error as exc:
            unresolved.append({"kind": "asset_candidate_error", "reference": reference, "error": exc.as_dict()})
            continue
        changes.update(planned)
        sources[str(asset_path)] = _hash(asset_path.read_bytes())
        copied_assets.append({"reference": reference, **winner, "sha256": sources[str(asset_path)]})
        if asset_path.suffix.casefold() in {".m3", ".m3a"}:
            unresolved.append({"kind": "embedded_model_assets_unverified", "file": str(asset_path)})
        for status in ("resolved", "missing", "unresolved"):
            for asset_reference in audited[status]:
                if asset_reference["root"] == str(source) and asset_reference["source"] == winner["path"]:
                    asset_requests.add(asset_reference["reference"])
    for diagnostic in audited["diagnostics"]:
        source_file = diagnostic.get("details", {}).get("source")
        if source_file and str(source / source_file) in sources:
            unresolved.append({"kind": "asset_audit_diagnostic", "detail": diagnostic})
    localization, copied_strings, locales = _selected_localization(source, roots, field_values, changes, unresolved)
    changes.update(localization)
    components = _xml(changes["ComponentList.SC2Components"], "ComponentList.SC2Components")
    existing_locales = {item.get("Locale") for item in components if item.get("Type") == "text"}
    for locale in sorted(locales - existing_locales):
        changes["ComponentList.SC2Components"] = _append_xml_child(changes["ComponentList.SC2Components"], f'<DataComponent Type="text" Locale="{locale}">GameText</DataComponent>'.encode(), "Components")
    # No source changed while this candidate was assembled.
    for filename, digest in sources.items():
        if _hash(Path(filename).read_bytes()) != digest:
            raise SC2Error("migration_source_changed", "规划期间迁移源发生变化", file=filename)
    for relative, digest in template_report["files"].items():
        if _hash((template / relative).read_bytes()) != digest:
            raise SC2Error("migration_template_changed", "规划期间模板发生变化", file=relative)
    unique_issues = {json.dumps(issue, ensure_ascii=False, sort_keys=True): issue for issue in unresolved}
    unresolved = list(unique_issues.values())
    report = {"source": str(source), "source_context_id": source_context["source_context_id"] if source_context else None,
              "template": template_report, "selections": selections,
              "closure": [{"catalog": kind, "object_id": identifier} for kind, identifier in sorted(closure)],
              "copied_objects": moved, "retained_dependency_objects": retained, "dependencies": source_dependencies,
              "dependency_graph": graph, "copied_assets": copied_assets, "retained_dependency_assets": retained_assets,
              "copied_localization": copied_strings, "unresolved": unresolved,
              "complete": graph["complete"] and not unresolved, "validation": "static", "engine_parity": False,
              "candidate_files": {path: {"bytes": len(data), "sha256": _hash(data)} for path, data in changes.items()},
              "source_fingerprints": sources,
              "limitations": ["保留原依赖；不是移除全部外部依赖的打包", "Actor 事件、动态脚本、二进制模型嵌入引用仍需专门验证", "模板只做结构检查；编辑器与游戏验收未进行"]}
    return report, changes


def inspect_migration(source_root: Path, selections: list[dict[str, str]], template_root: Path,
                      search_roots: list[Path] | None = None, *, source_context: dict | None = None) -> dict:
    """Return closure, missing evidence and candidate file hashes; write nothing."""
    return _build(source_root, selections, template_root, search_roots, source_context)[0]


def plan_migration(source_root: Path, selections: list[dict[str, str]], template_root: Path,
                   search_roots: list[Path] | None = None, *, allow_incomplete: bool = False,
                   source_context: dict | None = None) -> dict[str, bytes | None]:
    """Return new-mod candidates; incomplete candidates require explicit opt-in.

    Even with allow_incomplete, invalid/missing template shells, ambiguous
    source encodings and source races remain errors. The host must use a new
    .SC2Mod destination and attach inspect_migration's report to its artifacts.
    """
    report, changes = _build(source_root, selections, template_root, search_roots, source_context)
    if not report["complete"] and not allow_incomplete:
        raise SC2Error("migration_incomplete", "引用或资源未完整解析，仅能生成明确标注的候选", unresolved=report["unresolved"])
    return changes
