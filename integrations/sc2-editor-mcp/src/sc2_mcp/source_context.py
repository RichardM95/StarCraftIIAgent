"""Hash-bound, restart-safe source resolution shared by read-only domains.

Component sources stay in place. Archive/CASC caches contain metadata and the
active Catalog/include closure only, never a copy of the complete map. Cache
files are immutable candidates: every reuse verifies their complete inventory.
``complete`` describes source/metadata closure, not native engine equivalence.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from xml.etree import ElementTree as ET

from . import archives, casc, dependencies
from .catalog import _CATALOGS
from .errors import SC2Error
from .storage import file_lock, guard_absolute_path, map_files

PARSER_VERSION = "source-context-2"
RULES_VERSION = "catalog-rules-1"


def _hash_file(path: Path) -> str:
    guard_absolute_path(path)
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _context_id(context: dict) -> str:
    return hashlib.sha256(_canonical({key: value for key, value in context.items()
                                    if key != "source_context_id"})).hexdigest()


def _inventory(root: Path) -> dict[str, str]:
    return {relative: _hash_file(path) for relative, path in map_files(root)}


def _relative(raw: str) -> str:
    return archives._validate_member_name(raw)


def _find_local_dependency(relative: str, origin: Path, search: list[Path]) -> Path | None:
    candidates = [relative] if Path(relative).suffix else [relative, relative + ".SC2Mod", relative + ".SC2Map"]
    for candidate in candidates:
        for base in [origin, origin.parent, *search]:
            found = dependencies._resolve_ci(base, candidate)
            if found is not None:
                return found.resolve()
    return None


def _find_install_component(relative: str, installation: Path | None) -> tuple[Path | None, Path | None]:
    if installation is None:
        return None, None
    names = [relative] if Path(relative).suffix else [relative, relative + ".SC2Mod", relative + ".SC2Map"]
    for name in names:
        candidate = dependencies._resolve_ci(installation, name)
        if candidate is not None:
            if candidate.is_file() or dependencies._resolve_ci(candidate, "DocumentInfo"):
                return candidate.resolve(), None
            return None, candidate.resolve()
    return None, None


def _xml(raw: bytes, path: str) -> ET.Element:
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I):
        raise SC2Error("unsafe_xml", "来源 XML 不接受 DTD 或实体", path=path)
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SC2Error("invalid_catalog_xml", "来源 XML 无法解析", path=path, reason=str(exc)) from exc


def _seed_names(locale: str) -> list[str]:
    names = ["DocumentInfo", "DocumentHeader", "ComponentList.SC2Components"]
    for data in ("Base.SC2Data", f"{locale}.SC2Data"):
        names.append(f"{data}/GameData.xml")
        names.extend(f"{data}/GameData/{kind}Data.xml" for kind in _CATALOGS)
        names.extend(f"{data}/LocalizedData/{name}" for name in ("GameStrings.txt", "ObjectStrings.txt", "GameHotkeys.txt"))
    return names


def _catalog_closure(read_many, locale: str) -> tuple[dict[str, bytes], list[dict]]:
    """Discover only implicit catalogs and explicitly referenced includes.

    read_many returns a case-insensitive mapping of requested virtual names to
    (actual spelling, bytes), omitting absent names. Both resolution bases are
    checked for nested includes, matching Catalog's ambiguity guard.
    """
    available = read_many(_seed_names(locale))
    selected = {name: raw for name, raw in available.values()}
    issues: list[dict] = []
    queued, pending, adjacency = set(), [], {}
    for data in ("Base.SC2Data", f"{locale}.SC2Data"):
        for name in [*(f"{data}/GameData/{kind}Data.xml" for kind in _CATALOGS), f"{data}/GameData.xml"]:
            item = available.get(name.casefold())
            if item:
                pending.append((item[0], item[1], data))
                queued.add(item[0].casefold())
    while pending:
        requests, declarations = [], []
        for name, raw, data in pending:
            selected[name] = raw
            adjacency.setdefault(name.casefold(), [])
            try:
                document = _xml(raw, name)
                if document.tag not in {"Catalog", "Includes"}:
                    raise SC2Error("unsupported_catalog_document", "未知 Catalog 根节点", path=name, tag=document.tag)
                for element in document:
                    if element.tag not in {"Catalog", "Include", "Includes"} or not element.get("path"):
                        continue
                    relative = _relative(element.get("path", ""))
                    options = list(dict.fromkeys([f"{data}/{relative}", f"{PurePosixPath(name).parent}/{relative}"]))
                    requests.extend(options)
                    declarations.append((name, data, relative, options))
            except SC2Error as exc:
                issues.append(exc.as_dict())
        # One backend opening per include frontier, including all documents at
        # that depth. Catalog loading still interprets the original DFS order.
        unique = list({name.casefold(): name for name in requests}.values())
        found = read_many(unique) if unique else {}
        pending = []
        for name, data, relative, options in declarations:
            resolved = {found[option.casefold()][0].casefold(): found[option.casefold()]
                        for option in options if option.casefold() in found}
            if len(resolved) > 1:
                issues.append({"code": "ambiguous_catalog_include", "path": relative, "file": name})
                continue
            if not resolved:
                issues.append({"code": "missing_catalog_include", "file": name, "path": relative})
                continue
            actual, contents = next(iter(resolved.values()))
            if not actual.casefold().startswith(data.casefold() + "/"):
                issues.append({"code": "unsafe_catalog_path", "path": actual})
                continue
            adjacency[name.casefold()].append(actual.casefold())
            if actual.casefold() not in queued:
                queued.add(actual.casefold())
                pending.append((actual, contents, data))
    checked = set()
    def check_cycles(name, active):
        if name in active:
            issues.append({"code": "catalog_include_cycle", "paths": [*active[active.index(name):], name]})
            return
        if name not in checked:
            for target in adjacency.get(name, []):
                check_cycles(target, [*active, name])
            checked.add(name)
    for name in adjacency:
        check_cycles(name, [])
    return selected, issues


def _cache_load(directory: Path, identity: dict) -> tuple[Path, list[dict]] | None:
    if not directory.exists():
        return None
    try:
        manifest_path = guard_absolute_path(directory / "manifest.json")
        manifest = json.loads(manifest_path.read_text("utf-8"))
        files = directory / "files"
        if manifest.get("identity") != identity or _inventory(files) != manifest.get("files"):
            raise ValueError("cache inventory or identity mismatch")
        return files, manifest["issues"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SC2Error("source_cache_tampered", "来源缓存验证失败，保留原缓存并拒绝复用", path=str(directory), reason=str(exc)) from exc


def _cache_publish(cache: Path, identity: dict, files: dict[str, bytes], issues: list[dict]) -> Path:
    cache.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".source-", dir=cache.parent))
    materialized = stage / "files"
    materialized.mkdir()
    records = {}
    for name, raw in files.items():
        relative = _relative(name)
        target = materialized / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        records[relative] = hashlib.sha256(raw).hexdigest()
    manifest = {"identity": identity, "files": records, "issues": issues}
    (stage / "manifest.json").write_bytes(_canonical(manifest))
    if _inventory(materialized) != records:
        raise SC2Error("source_cache_verification", "来源缓存发布前验证失败", path=str(stage))
    if cache.exists():
        # The caller holds the shared cache lock, but never overwrite if a
        # foreign process created the destination while extraction ran.
        raise SC2Error("source_cache_conflict", "缓存目标已存在，保留两份来源", path=str(cache), stage=str(stage))
    for path in [*(materialized / name for name in records), stage / "manifest.json"]:
        path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    stage.rename(cache)
    return cache / "files"


@contextmanager
def _archive_reader(source: Path):
    archives._assert_mpq_file(source)
    with archives._managed_reader(source) as reader:
        names = {}
        for original in reader.members():
            name = _relative(original)
            key = name.casefold()
            if key in names:
                raise SC2Error("source_case_collision", "归档来源路径大小写冲突", path=str(source), member=name)
            names[key] = (name, original)

        def read_many(requested):
            result = {}
            for request in requested:
                item = names.get(_relative(request).casefold())
                if item:
                    name, original = item
                    result[request.casefold()] = (name, reader.read(original))
            return result
        yield read_many


def _read_casc_batch(installation: Path, prefix: str, names: list[str], cache_root: Path, build: dict) -> dict:
    """Harvest only SHA-verified output, including optional absent candidates.

    The existing CASC extractor deliberately rejects any missing name. Discovery
    requests contain optional standard catalog files, so its retained result is
    consumed only after validating every returned row independently.
    """
    request = [prefix + "/" + _relative(name) for name in names]
    staging_parent = cache_root / "casc-discovery"
    staging_parent.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="batch-", dir=staging_parent)) / "files"
    try:
        result = casc.extract_casc(installation, request, destination,
                                   product=build["product"], branch=build["branch"])
        rows, output = result["files"], Path(result["destination"])
    except SC2Error as exc:
        if exc.code != "CASC_ASSET_MISSING" or not exc.details.get("diagnostics"):
            raise
        diagnostics = guard_absolute_path(Path(exc.details["diagnostics"]))
        # The extractor owns this diagnostic directory below our destination's
        # parent. Never trust a path supplied by arbitrary caller data.
        if not diagnostics.resolve().is_relative_to(destination.parent.resolve()):
            raise SC2Error("source_casc_diagnostics", "CASC 诊断目录不属于本次请求") from exc
        data = json.loads((diagnostics / "result.json").read_text("utf-8"))
        rows, output = data.get("files", []), diagnostics / "files"
        missing = data.get("missing", [])
        missing_names = {item if isinstance(item, str) else item.get("path") for item in missing}
        if {row.get("path") for row in rows} | missing_names != set(request):
            raise SC2Error("CASC_OUTPUT_INVALID", "CASC 部分提取记录与请求不一致") from exc
    result = {}
    seen = set()
    for row in rows:
        name = row.get("path")
        if name not in request or name.casefold() in seen:
            raise SC2Error("CASC_OUTPUT_INVALID", "CASC 返回未请求或重复来源", path=name)
        seen.add(name.casefold())
        path = guard_absolute_path(output / _relative(name))
        if not path.is_file() or path.stat().st_size != row.get("bytes") or _hash_file(path) != row.get("sha256"):
            raise SC2Error("CASC_OUTPUT_INVALID", "CASC 来源指纹不一致", path=name)
        relative = name[len(prefix) + 1:]
        result[relative.casefold()] = (relative, path.read_bytes())
    return result


def prepare_source_context(root: Path, search_roots: list[Path], cache_root: Path,
                           installation: Path | None = None, locale: str = "zhCN",
                           product: str | None = None, branch: str | None = None, *,
                           dependency_values: list[str] | None = None) -> dict:
    """Resolve actual declarations recursively; return a JSON-safe snapshot.

    Missing dependencies, cycles, unreadable metadata/includes and unverified
    Battle.net identities produce an incomplete context. Unsafe paths and
    corrupt caches are hard errors. No source/map/installation file is written.
    """
    if not isinstance(locale, str) or not re.fullmatch(r"[A-Za-z]{2}[A-Za-z]{2}", locale):
        raise SC2Error("invalid_locale", "语言需要四字母地区代码")
    source = guard_absolute_path(Path(root)).resolve()
    if dependency_values is not None:
        if not isinstance(dependency_values, list):
            raise SC2Error("invalid_dependency_values", "虚拟依赖声明必须为列表")
        dependency_values = [dependencies._validate_dependency_value(value) for value in dependency_values]
    search = [guard_absolute_path(Path(path)).resolve() for path in search_roots]
    cache = guard_absolute_path(Path(cache_root)).resolve()
    if not source.exists():
        raise SC2Error("project_missing", "来源地图不存在", path=str(source))
    for boundary in [*([source] if source.is_dir() else []), *[p for p in search if p.is_dir()]]:
        if cache == boundary or cache.is_relative_to(boundary):
            raise SC2Error("source_cache_in_source", "缓存不能写入地图或依赖搜索树", path=str(cache), boundary=str(boundary))
    install = guard_absolute_path(Path(installation)).resolve() if installation else None
    if install and (cache == install or cache.is_relative_to(install)):
        raise SC2Error("source_cache_in_source", "缓存不能写入客户端安装目录", path=str(cache))
    # Resolve local declarations before creating even the cache lock. A sibling
    # dependency need not occur in search_roots and may otherwise contain cache.
    preflight_seen = set()
    def preflight(actual, root=False):
        if actual in preflight_seen:
            return
        preflight_seen.add(actual)
        if actual.is_dir() and (cache == actual or cache.is_relative_to(actual)):
            raise SC2Error("source_cache_in_source", "缓存不能写入已解析的来源组件", path=str(cache), boundary=str(actual))
        try:
            if root and dependency_values is not None:
                values = dependency_values
            else:
                if actual.is_dir():
                    metadata = dependencies._resolve_ci(actual, "DocumentInfo")
                    if metadata is None or not metadata.is_file():
                        return
                    raw = metadata.read_bytes()
                else:
                    with _archive_reader(actual) as reader:
                        selected = reader(["DocumentInfo"])
                    if "documentinfo" not in selected:
                        return
                    raw = selected["documentinfo"][1]
                    metadata = actual
                text, _ = dependencies._decode_xml(raw, metadata)
                values = dependencies._parse_document_info(text, metadata)["values"]
        except SC2Error:
            # The normal visitor records unavailable metadata as incomplete.
            return
        for reference in values:
            relative = dependencies._reference_parts(reference).get("file")
            if relative is None:
                continue
            origin = actual if actual.is_dir() else actual.parent
            target = _find_local_dependency(relative, origin, search)
            if target is None:
                target, _ = _find_install_component(relative, install)
            if target is not None:
                preflight(target)
    preflight(source, True)
    build = None
    build_info = None
    unknown = []
    if install:
        inspection = casc.inspect_installation(install)
        build = casc.select_build(inspection, product=product, branch=branch)
        build_info = {"installation": str(install), "build_info_sha256": inspection["build_info_sha256"],
                      "build_config_sha256": _hash_file(Path(build["build_config"])), **build}
    else:
        unknown.append({"code": "client_build_not_selected"})
    nodes, edges, order, missing, cycles, incomplete = [], [], [], [], [], []
    components, inventories, fingerprints = {}, {}, {}
    resolution_checks = []
    visiting, visited = [], set()
    parser = {"parser_version": PARSER_VERSION, "rules_version": RULES_VERSION}

    def materialize(key: str, actual: Path | None, virtual: str | None) -> tuple[Path, str, list[dict]]:
        if actual and actual.is_dir():
            if cache == actual or cache.is_relative_to(actual):
                raise SC2Error("source_cache_in_source", "缓存不能写入已解析的来源组件", path=str(cache), boundary=str(actual))
            inventory = _inventory(actual)
            inventories[str(actual)] = inventory
            fingerprints.update({str(actual / name): digest for name, digest in inventory.items()})
            def read_many(names):
                found = {}
                for name in names:
                    target = dependencies._resolve_ci(actual, name)
                    if target and target.is_file():
                        found[name.casefold()] = (target.relative_to(actual).as_posix(), target.read_bytes())
                return found
            _selected, issues = _catalog_closure(read_many, locale)
            return actual, "component", issues
        archive_hash = _hash_file(actual) if actual else None
        if actual:
            fingerprints[str(actual)] = archive_hash
        identity = {**parser, "kind": "mpq" if actual else "casc", "source": str(actual) if actual else virtual,
                    "source_sha256": archive_hash, "build": build_info, "locale": locale}
        directory = cache / "sources" / hashlib.sha256(_canonical(identity)).hexdigest()
        reused = _cache_load(directory, identity)
        if reused:
            materialized, issues = reused
        elif actual:
            with _archive_reader(actual) as reader:
                selected, issues = _catalog_closure(reader, locale)
            if _hash_file(actual) != archive_hash:
                raise SC2Error("source_changed", "物化期间归档变化", path=str(actual))
            materialized = _cache_publish(directory, identity, selected, issues)
        else:
            known, absent = {}, set()
            def read_many(names):
                needed = [name for name in names if name.casefold() not in known and name.casefold() not in absent]
                if needed:
                    extracted = _read_casc_batch(install, virtual, needed, cache, build)
                    known.update(extracted)
                    absent.update(name.casefold() for name in needed if name.casefold() not in extracted)
                return {name.casefold(): known[name.casefold()] for name in names if name.casefold() in known}
            selected, issues = _catalog_closure(read_many, locale)
            materialized = _cache_publish(directory, identity, selected, issues)
        inventory = _inventory(materialized)
        inventories[str(materialized)] = inventory
        fingerprints.update({str(materialized / name): digest for name, digest in inventory.items()})
        fingerprints[str(directory / "manifest.json")] = _hash_file(directory / "manifest.json")
        return materialized, "mpq" if actual else "casc", issues

    def resolve(relative: str, origin: Path) -> tuple[Path | None, str | None]:
        found = _find_local_dependency(relative, origin, search)
        if found is None:
            found, ignored = _find_install_component(relative, install)
            if ignored:
                issue = {"code": "installation_component_metadata_missing", "path": str(ignored), "resolution": "CASC_fallback"}
                if issue not in unknown:
                    unknown.append(issue)
        resolution_checks.append({"relative": relative, "origin": str(origin), "selected": str(found) if found else None})
        if found is not None:
            return found, None
        if install:
            virtual = _relative(relative)
            if not Path(virtual).suffix:
                virtual += ".SC2Mod"
            return None, virtual
        return None, None

    def visit(actual: Path | None, virtual: str | None, kind: str):
        key = str(actual) if actual else "casc:" + virtual.casefold()
        if key in visiting:
            cycle = [*visiting[visiting.index(key):], key]
            if cycle not in cycles:
                cycles.append(cycle)
            return key
        if key in visited:
            return key
        visiting.append(key)
        try:
            component, source_kind, issues = materialize(key, actual, virtual)
        except SC2Error as exc:
            if exc.code in {"source_cache_in_source", "source_cache_tampered", "source_changed", "source_case_collision", "unsafe_path", "unsafe_dependency_path", "unsafe_catalog_path", "linked_path", "hardlinked_file"}:
                raise
            incomplete.append({"path": key, "reason": exc.code, "detail": exc.as_dict()})
            visiting.pop()
            visited.add(key)
            return key
        components[key] = component
        incomplete.extend({"path": key, "reason": issue.get("code"), "detail": issue} for issue in issues)
        metadata = dependencies._resolve_ci(component, "DocumentInfo")
        values, declarations = [], []
        metadata_complete = False
        if metadata and metadata.is_file():
            try:
                raw = metadata.read_bytes()
                text, _ = dependencies._decode_xml(raw, metadata)
                parsed = dependencies._parse_document_info(text, metadata)
                values, declarations = parsed["values"], parsed["declarations"]
                metadata_complete = True
            except SC2Error as exc:
                incomplete.append({"path": key, "reason": exc.code, "detail": exc.as_dict()})
        else:
            incomplete.append({"path": key, "reason": "missing_document_info"})
        if kind == "root" and dependency_values is not None:
            values = list(dependency_values)
            declarations = [{"source": str(metadata) if metadata else key + "!DocumentInfo", "line": None,
                             "ordinal": ordinal} for ordinal, _ in enumerate(values)]
        node = {"path": key, "name": actual.name if actual else virtual, "kind": kind,
                "container": source_kind == "component", "source_kind": source_kind, "materialized_root": str(component),
                "dependencies": values, "resolved_dependencies": [], "metadata_source": str(metadata) if metadata else key + "!DocumentInfo",
                "metadata_complete": metadata_complete, "cache_readonly": source_kind != "component"}
        node["build_identity"] = "selected_casc_build" if source_kind == "casc" else "component_fingerprint_only"
        if actual and install and actual.is_relative_to(install):
            node["build_identity"] = "unknown_install_component"
            unknown.append({"code": "installation_component_build_unverified", "path": str(actual)})
        nodes.append(node)
        for reference, declaration in zip(values, declarations, strict=True):
            parts = dependencies._reference_parts(reference)
            edge = {"from": key, "to": None, "reference": reference, "resolved": False, "declared_sources": parts,
                    "source": {"file": declaration["source"], "line": declaration["line"], "ordinal": declaration["ordinal"]},
                    "bnet_identity_verified": False if "bnet" in parts else None}
            if "bnet" in parts:
                unknown.append({"code": "battle_net_identity_not_verified", "reference": reference, "requested_by": key})
            if "file" not in parts:
                missing.append({"reference": reference, "requested_by": key, "kind": "bnet", "reason": "battle_net_reference_not_resolved"})
                edges.append(edge)
                continue
            origin = actual if actual and actual.is_dir() else actual.parent if actual else source.parent
            target, casc_name = resolve(parts["file"], origin)
            if target is None and casc_name is None:
                missing.append({"reference": reference, "requested_by": key, "kind": "file", "relative": parts["file"], "reason": "file_not_found"})
            else:
                target_key = visit(target, casc_name, "dependency")
                edge.update({"to": target_key, "resolved": target_key in components, "resolved_via": "file" if target else "casc"})
                if edge["resolved"]:
                    node["resolved_dependencies"].append(target_key)
                else:
                    missing.append({"reference": reference, "requested_by": key, "kind": "file", "reason": "source_unavailable"})
            edges.append(edge)
        visiting.pop()
        visited.add(key)
        order.append(key)
        return key

    cache.mkdir(parents=True, exist_ok=True)
    with file_lock(cache / "source-context.lock"):
        visit(source, None, "root")
    roots = []
    for key in order:
        component = components[key]
        roots.append(str(component))
        local = dependencies._resolve_ci(component, f"{locale}.SC2Data")
        if local and local.is_dir():
            roots.append(str(local))
    unknown.extend({"code": "source_incomplete", "detail": issue} for issue in incomplete)
    graph = {"nodes": nodes, "edges": edges, "load_order": order, "missing": missing, "cycles": cycles,
             "incomplete": incomplete, "complete": not missing and not cycles and not incomplete,
             "warnings": [issue["code"] for issue in unknown]}
    context = {"root": str(source), "search_roots": [str(path) for path in search], "cache_root": str(cache),
               "roots": roots, "locale": locale, "product": build["product"] if build else product,
               "branch": build["branch"] if build else branch, "build": build_info, **parser,
               "dependency_report": graph, "fingerprints": fingerprints, "inventories": inventories,
               "resolution_checks": resolution_checks, "proposed_dependencies": dependency_values,
               "complete": graph["complete"] and not any(item["code"] in {"battle_net_identity_not_verified", "installation_component_build_unverified"} for item in unknown),
               "unknown": unknown, "engine_parity": False}
    context["source_context_id"] = _context_id(context)
    assert_source_context_current(context)
    return context


def materialize_dependency_report(report: dict, root: Path, search_roots: list[Path], cache_root: Path,
                                  installation: Path | None = None, locale: str = "zhCN",
                                  product: str | None = None, branch: str | None = None) -> dict:
    """Prepare a shared context for an existing actual or proposed graph.

    The supplied root declaration is resolved anew against real source files;
    graph-supplied paths are never trusted as materialization commands.
    """
    declarations = [node.get("dependencies") for node in report.get("nodes", []) if node.get("kind") == "root"]
    if len(declarations) != 1 or not isinstance(declarations[0], list):
        raise SC2Error("invalid_dependency_report", "依赖报告必须有唯一根声明")
    return prepare_source_context(root, search_roots, cache_root, installation, locale, product, branch,
                                  dependency_values=declarations[0])


def assert_source_context_current(context: dict) -> dict:
    """Validate persisted context identity and all bound sources after restart.

    This checks file additions/deletions as well as byte changes. It does not
    refresh in place; callers prepare a new context after stale-source errors.
    """
    if not isinstance(context, dict) or context.get("source_context_id") != _context_id(context):
        raise SC2Error("invalid_source_context", "SourceContext ID 与内容不匹配")
    if context.get("parser_version") != PARSER_VERSION or context.get("rules_version") != RULES_VERSION:
        raise SC2Error("source_context_stale", "解析器或规则版本已变化")
    changed = []
    for root, inventory in context.get("inventories", {}).items():
        path = guard_absolute_path(Path(root))
        if not path.is_dir() or _inventory(path) != inventory:
            changed.append(root)
    for raw_path, expected in context.get("fingerprints", {}).items():
        path = guard_absolute_path(Path(raw_path))
        if not path.is_file() or _hash_file(path) != expected:
            changed.append(raw_path)
    for check in context.get("resolution_checks", []):
        current = _find_local_dependency(check["relative"], Path(check["origin"]), [Path(path) for path in context["search_roots"]])
        if current is None:
            current, _ignored = _find_install_component(check["relative"], Path(context["build"]["installation"]) if context.get("build") else None)
        if (str(current) if current else None) != check["selected"]:
            changed.append("dependency_resolution:" + check["relative"])
    build = context.get("build")
    if build:
        path = Path(build["installation"]) / ".build.info"
        config = Path(build["build_config"])
        if not path.is_file() or _hash_file(path) != build["build_info_sha256"]:
            changed.append(str(path))
        if not config.is_file() or _hash_file(config) != build["build_config_sha256"]:
            changed.append(str(config))
    if changed:
        raise SC2Error("source_context_stale", "来源内容、文件清单或构建已变化", paths=sorted(set(changed)))
    return {"source_context_id": context["source_context_id"], "current": True, "validation": "sha256"}
