#!/usr/bin/env python3
"""Read an SC2 component mod's dependency graph recursively."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any
from collections.abc import Mapping

from sc2_paths import resolve_configured_path
from sc2_components import component_path, component_exists, parse_xml, verify_archives


RECURSION_DISABLED = "Recursive dependency resolution is disabled by project configuration; only the primary component is available"

FILE_REF_RE = re.compile(r"(?:^|,)\s*file:([^,]+)", re.IGNORECASE)


def resolve_dependency_root(repo_root: Path, primary: Path, config: Mapping,
                            explicit_mods: str | None = None) -> Path:
    """Use an override, the configured editing source, or the explicit mod's Mods ancestor."""
    primary = primary.resolve(strict=False)
    if explicit_mods:
        root = resolve_configured_path(repo_root, explicit_mods)
        if not root.is_dir():
            raise ValueError(f"Explicit Mods directory not found: {root}")
        return root
    paths = config.get("paths", {})
    configured = paths.get("mods_dir") if isinstance(paths, Mapping) else None
    project = config.get("project", {})
    if isinstance(configured, str) and configured.strip():
        root = resolve_configured_path(repo_root, configured)
        source = project.get("source_mod") if isinstance(project, Mapping) else None
        is_copy = isinstance(project, Mapping) and project.get("source_mode") == "workspace_copy"
        if primary.is_relative_to(root) or (is_copy and isinstance(source, str)
                and resolve_configured_path(repo_root, source) == primary):
            return root
    for ancestor in primary.parents:
        if ancestor.name.casefold() == "mods":
            return ancestor
    raise ValueError(f"Cannot infer dependency Mods root for {primary}; pass --mods-dir")


class IncompleteDependenciesError(ValueError):
    """Current dependency completeness cannot be waived by historical-index permission."""


def dependency_problems(graph: dict) -> list[str]:
    return list(graph.get("errors", [])) + list(graph.get('official_problems', [])) + [
        f"missing dependency: {edge['target_name']} (declared by {edge['source']})"
        for edge in graph.get("missing", [])] + [
        f"unresolved engine/network dependency: {edge['raw']}"
        for edge in graph.get('edges', []) if edge.get('kind') == 'external']


def dependency_state(graph: dict) -> dict:
    problems = dependency_problems(graph)
    return {"status": "partial" if problems else "complete", "problems": problems,
            'hard_problems': dependency_problems({**graph, 'official_problems': []}),
            'official_problems': graph.get('official_problems', []),
            'bootstrap_loading': graph.get('bootstrap_loading', 'not_applicable'),
            'traversal_order': graph.get('traversal_order', []),
            'loading_order': graph.get('loading_order', {'status': 'unconfirmed'}),
            'relations': [{k: e.get(k) for k in ('source', 'target', 'ordinal', 'raw', 'relation', 'evidence', 'cycle')}
                          for e in graph.get('edges', [])],
            "mods_dir": graph.get("mods_dir"), "campaigns_dir": graph.get("campaigns_dir"), "primary": graph.get("primary"),
            "official_cache": graph.get("official_cache")}


def official_research_allowed(state: dict) -> bool:
    """Only independently verified official loading uncertainty is researchable."""
    return (state.get('status') == 'partial' and bool(state.get('official_problems'))
            and state.get('hard_problems') == [])


def _path_key(path: Path) -> str:
    return str(path.resolve(strict=False)).casefold()


def extract_dependency_refs(raw_value: str) -> list[dict[str, Any]]:
    """Extract file references from one SC2 ``Dependencies/Value`` string."""
    is_network = raw_value.lstrip().lower().startswith("bnet:")
    refs: list[dict[str, Any]] = []
    for match in FILE_REF_RE.finditer(raw_value):
        file_path = match.group(1).strip().replace("\\", "/").lstrip("/")
        lower = file_path.casefold()
        refs.append(
            {
                "raw": raw_value,
                "file_path": file_path,
                "is_network": is_network,
                "is_local_mod": lower.startswith("mods/") and lower.endswith(".sc2mod"),
            }
        )
    if not refs and raw_value.strip():
        refs.append(
            {
                "raw": raw_value,
                "file_path": None,
                "is_network": is_network,
                "is_local_mod": False,
            }
        )
    return refs


def find_info_component(mod_dir: Path) -> tuple[Path | None, list[str]]:
    """Resolve the Type=info component named by ComponentList.SC2Components."""
    mod_dir = component_path(mod_dir)
    errors: list[str] = []
    component_list = mod_dir / "ComponentList.SC2Components"
    if not component_list.is_file():
        return None, [f"{mod_dir.name}: missing ComponentList.SC2Components"]
    try:
        root = parse_xml(component_list).getroot()
    except ET.ParseError as exc:
        return None, [f"{mod_dir.name}: invalid ComponentList.SC2Components ({exc})"]

    for component in root.findall("DataComponent"):
        if component.get("Type") == "info" and component.text and component.text.strip():
            relative = PurePosixPath(component.text.strip().replace("\\", "/"))
            info_path = mod_dir.joinpath(*relative.parts)
            if relative.is_absolute() or not info_path.resolve().is_relative_to(mod_dir.resolve()):
                return None, [f"{mod_dir.name}: info component escapes component directory"]
            if not info_path.is_file():
                errors.append(
                    f"{mod_dir.name}: info component does not exist: {component.text.strip()}"
                )
                return None, errors
            return info_path, errors
    return None, [f"{mod_dir.name}: ComponentList has no Type='info' component"]


def read_mod_dependencies(mod_dir: Path, *, allow_unpacked: bool = False) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Return (info component, dependency refs, errors) for one component mod."""
    mod_dir = component_path(mod_dir)
    info_path, errors = find_info_component(mod_dir)
    # Raw official extracts may retain DocumentInfo without a component list.
    # Never replace a present but broken component list with guessed metadata.
    if (allow_unpacked and not (mod_dir / "ComponentList.SC2Components").exists()
            and (mod_dir / "DocumentInfo").is_file()):
        info_path, errors = mod_dir / "DocumentInfo", []
    if info_path is None:
        return None, [], errors
    try:
        text = info_path.read_text(encoding="utf-8-sig", errors="replace")
        content_without_declaration = re.sub(
            r"^\s*<\?xml[^?]*\?>",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        # Some Editor component mods contain an XML declaration-only
        # DocumentInfo when they declare no dependencies.
        if not content_without_declaration:
            return info_path.relative_to(mod_dir).as_posix(), [], errors
        root = ET.fromstring(text)
        if root.tag != 'DocInfo':
            return info_path.name, [], [f'{mod_dir.name}: invalid {info_path.name} root ({root.tag})']
    except ET.ParseError as exc:
        return info_path.name, [], [f"{mod_dir.name}: invalid {info_path.name} ({exc})"]

    refs: list[dict[str, Any]] = []
    for ordinal, value in enumerate(root.findall("./Dependencies/Value")):
        if value.text:
            refs.extend({**ref, 'ordinal': ordinal} for ref in extract_dependency_refs(value.text.strip()))
    return info_path.relative_to(mod_dir).as_posix(), refs, errors


def _resolve_local_mod(ref: dict[str, Any], mods_dir: Path) -> Path | None:
    file_path = ref.get("file_path")
    if not isinstance(file_path, str) or not ref.get("is_local_mod"):
        return None
    relative = PurePosixPath(file_path).parts[1:]
    target = mods_dir.joinpath(*relative).resolve(strict=False)
    try:
        target.relative_to(mods_dir.resolve(strict=False))
    except ValueError:
        return None
    return target


def build_dependency_graph(primary_mod: Path, mods_dir: Path, *,
                           campaigns_dir: Path | None = None,
                           allow_unpacked: bool = False,
                           strict_external: bool = False,
                           official_cache: Path | None | bool = None,
                           allow_partial_official_cache: bool = False) -> dict[str, Any]:
    """Resolve a component target; optional campaign roots preserve legacy callers."""
    primary_mod = primary_mod.resolve(strict=False)
    mods_dir = mods_dir.resolve(strict=False)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    errors: list[str] = []
    missing: list[dict[str, Any]] = []
    visited: set[str] = set()
    from sc2_official import cache_for_mods
    cache = None
    research_nodes = {}
    official_problems = []
    traversal_order = []
    try:
        if official_cache is not False:
            cache = cache_for_mods(mods_dir, Path(official_cache) if official_cache else None,
                                   allow_partial=allow_partial_official_cache, research=True)
            errors.extend(cache.hard_problems if cache else [])
            if cache and cache.partial:
                for path in cache.research_components():
                    research_nodes[_path_key(path)] = {'path': str(path), 'name': path.name,
                        'origin': 'casc', 'scope': 'research_only',
                        'casc': {'manifest': str(cache.manifest_path), 'identity': cache.identity,
                                 **cache.metadata(path)}}
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        errors.append('Official cache rejected: ' + str(exc))
    campaigns_dir = (campaigns_dir if campaigns_dir is not None else mods_dir.parent / 'Campaigns').resolve(strict=False)

    def visit(mod_dir: Path, stack: tuple[str, ...]) -> None:
        source_key = _path_key(mod_dir)
        if source_key in visited:
            return
        visited.add(source_key)

        cached = cache is not None and mod_dir.is_relative_to(cache.root)
        if cached:
            metadata = cache.metadata(mod_dir)
            evidence = metadata['dependency_evidence']
            info_component = (Path(evidence).relative_to(mod_dir.relative_to(cache.root)).as_posix()
                              if isinstance(evidence, str) else None)
            relation = metadata['assessment']['dependency_relation']
            ordinals = metadata.get('dependency_ordinals', list(range(len(metadata['dependencies']))))
            refs = [{**r, 'ordinal': ordinals[i], 'relation': relation, 'evidence': evidence}
                    for i, raw in enumerate(metadata['dependencies']) for r in extract_dependency_refs(raw)]
            refs.extend({**r, 'ordinal': i, 'relation': 'locale_chain', 'evidence': evidence}
                        for i, raw in enumerate(metadata.get('locale_dependencies', [])) for r in extract_dependency_refs(raw))
            node_errors = []
        else:
            try:
                info_component, refs, node_errors = (read_mod_dependencies(mod_dir, allow_unpacked=True)
                                                     if allow_unpacked else read_mod_dependencies(mod_dir))
            except (ValueError, OSError) as exc:
                info_component, refs, node_errors = None, [], [f'{mod_dir}: {exc}']
        errors.extend(node_errors)
        if not cached:
            refs = [{**r, 'relation': 'declared', 'evidence': str(mod_dir / info_component) if info_component else None}
                    for r in refs]
        if source_key == _path_key(primary_mod) and cache and cache.bootstrap:
            roots = cache.bootstrap['roots']
            refs = [{**r, 'ordinal': i, 'relation': 'bootstrap', 'evidence': cache.bootstrap}
                    for i, name in enumerate(roots) for r in extract_dependency_refs('file:' + name)] + refs
        nodes[source_key] = {
            "name": mod_dir.name,
            "path": str(mod_dir),
            "info_component": info_component,
            "origin": "casc" if cached else "local",
        }
        if cached:
            nodes[source_key]['casc'] = {'manifest': str(cache.manifest_path),
                                       'identity': cache.identity, **metadata}
            if (metadata['assessment']['problems'] or metadata.get('scope') == 'research_only'
                    or cache.data.get('engine') and not cache.bootstrap):
                nodes[source_key]['scope'] = 'research_only'
            nodes[source_key]['availability'] = 'verified'
            nodes[source_key]['assessment'] = metadata['assessment']

        next_stack = stack + (source_key,)
        for ordinal, ref in enumerate(refs):
            edge: dict[str, Any] = {
                "source": source_key,
                "raw": ref["raw"],
                "file_path": ref.get("file_path"),
                'ordinal': ref.get('ordinal', ordinal),
                'relation': ref['relation'], 'evidence': ref.get('evidence'),
            }
            target = _resolve_local_mod(ref, mods_dir)
            file_path = ref.get("file_path")
            if (campaigns_dir is not None and isinstance(file_path, str)
                    and file_path.casefold().startswith("campaigns/")
                    and file_path.casefold().endswith((".sc2campaign", ".sc2mod"))):
                candidate = campaigns_dir.joinpath(*PurePosixPath(file_path).parts[1:]).resolve()
                if candidate.is_relative_to(campaigns_dir.resolve()):
                    target = candidate
            # An existing local component, including a broken one, always wins.
            if cache is not None and isinstance(file_path, str) and (target is None or not target.exists()):
                cached_target = cache.component(file_path)
                if cached_target is not None:
                    target = cached_target
            if target is None or (ref.get("is_network") and not target.exists()):
                edge["kind"] = "external"
                edges.append(edge)
                if strict_external:
                    errors.append(f"{mod_dir}: unresolved dependency: {ref['raw']}")
                continue

            target_key = _path_key(target)
            edge.update(
                {
                    "kind": "local",
                    "target": target_key,
                    "target_name": target.name,
                    "target_path": str(target),
                    "exists": component_exists(target),
                    "cycle": target_key in next_stack,
                }
            )
            edges.append(edge)
            if edge['cycle']:
                errors.append('Dependency cycle: ' + ' -> '.join(nodes[k]['name'] for k in next_stack + (target_key,)))
            if not component_exists(target):
                missing.append(edge)
            elif target_key not in visited:
                visit(target, next_stack)
        traversal_order.append(source_key)

    visit(primary_mod, ())
    try:
        verify_archives()
    except (ValueError, OSError) as exc:
        errors.append(str(exc))
    # Keep research providers separate from active nodes, and respect local overrides.
    needs_reference_core = any(n.get('origin') == 'casc' for n in nodes.values())
    research_nodes = {k: n for k, n in research_nodes.items()
                      if needs_reference_core and Path(n['path']).relative_to(cache.root).as_posix() == 'mods/core.sc2mod'
                      and k not in nodes and not (mods_dir.parent / Path(n['path']).relative_to(cache.root)).exists()}
    if cache:
        relevant = [*nodes.values(), *research_nodes.values()]
        for node in relevant:
            if node.get('origin') == 'casc':
                logical = Path(node['path']).relative_to(cache.root).as_posix()
                official_problems.extend(logical + ': ' + p for p in cache.assessments[logical]['unconfirmed'])
        if cache.data.get('engine') and not cache.bootstrap and any(n.get('origin') == 'casc' for n in relevant):
            official_problems.append('Core/bootstrap loading unconfirmed for the current build')
        if needs_reference_core:
            official_problems.extend(cache.global_unconfirmed)
    return {
        "primary": _path_key(primary_mod),
        "mods_dir": str(mods_dir),
        "campaigns_dir": str(campaigns_dir),
        "nodes": nodes,
        "edges": edges,
        "missing": missing,
        "errors": errors,
        'official_problems': sorted(set(official_problems)),
        'traversal_order': traversal_order,
        'loading_order': {'status': 'confirmed' if not errors and not missing and not official_problems and all(
                            e['relation'] in {'declared', 'bootstrap', 'engine_dependency_chain'} and e['kind'] != 'external' for e in edges) else 'unconfirmed',
                          'components': traversal_order,
                          'scope': 'component_precedence', 'file_merge_order': 'unconfirmed',
                          'basis': 'Core base first; ordered dependency recursion; current component last'},
        'bootstrap_loading': 'confirmed' if cache and cache.bootstrap else 'unconfirmed' if cache and cache.data.get('engine') and any(n.get('origin') == 'casc' for n in [*nodes.values(), *research_nodes.values()]) else 'not_applicable',
        "research_nodes": research_nodes,
        "official_cache": ({'root': str(cache.root), 'identity': cache.identity,
                            'manifest': str(cache.manifest_path), 'status': 'partial' if cache.partial else 'complete',
                            'problems': cache.hard_problems + cache.unconfirmed, 'engine': cache.data.get('engine'),
                            'loading_rules': {'assessment_version': 3, 'bootstrap': cache.bootstrap, 'standard_catalog_rule': None,
                                              'dependency_chain': cache.dependency_rule,
                                              'catalog_registration': cache.registration},
                            'assessments': cache.assessments} if cache else None),
    }


def render_dependency_tree(graph: dict[str, Any]) -> list[str]:
    """Render a compact dependency tree, marking shared and cyclic nodes."""
    nodes = graph["nodes"]
    by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        by_source.setdefault(edge["source"], []).append(edge)

    primary = graph["primary"]
    root = nodes.get(primary, {"name": primary})
    lines = [f"{root['name']} [primary]"]
    expanded = {primary}

    def walk(source: str, prefix: str, stack: tuple[str, ...]) -> None:
        outgoing = by_source.get(source, [])
        for index, edge in enumerate(outgoing):
            last = index == len(outgoing) - 1
            branch = "`-- " if last else "|-- "
            child_prefix = prefix + ("    " if last else "|   ")
            if edge["kind"] == "external":
                label = edge.get("file_path") or edge["raw"]
                lines.append(f"{prefix}{branch}{label} [engine/network]")
                continue

            target = edge["target"]
            label = edge["target_name"]
            if nodes.get(target, {}).get('origin') == 'casc':
                label += ' [CASC verified source; ' + nodes[target].get('scope', 'declared_dependency') + ']'
            if edge.get('relation') == 'locale_chain':
                label += ' [locale relation; active loading unconfirmed]'
            if not edge["exists"]:
                lines.append(f"{prefix}{branch}{label} [MISSING]")
            elif edge.get("cycle") or target in stack:
                lines.append(f"{prefix}{branch}{label} [cycle]")
            elif target in expanded:
                lines.append(f"{prefix}{branch}{label} [shared; already expanded]")
            else:
                lines.append(f"{prefix}{branch}{label}")
                expanded.add(target)
                walk(target, child_prefix, stack + (target,))

    walk(primary, "", (primary,))
    return lines
