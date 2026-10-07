#!/usr/bin/env python3
"""Read an SC2 component mod's dependency graph recursively."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any
from collections.abc import Mapping

from sc2_paths import resolve_configured_path


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
    return list(graph.get("errors", [])) + [
        f"missing dependency: {edge['target_name']} (declared by {edge['source']})"
        for edge in graph.get("missing", [])]


def dependency_state(graph: dict) -> dict:
    problems = dependency_problems(graph)
    return {"status": "partial" if problems else "complete", "problems": problems,
            "mods_dir": graph.get("mods_dir"), "primary": graph.get("primary")}


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
    errors: list[str] = []
    component_list = mod_dir / "ComponentList.SC2Components"
    if not component_list.is_file():
        return None, [f"{mod_dir.name}: missing ComponentList.SC2Components"]
    try:
        root = ET.parse(component_list).getroot()
    except ET.ParseError as exc:
        return None, [f"{mod_dir.name}: invalid ComponentList.SC2Components ({exc})"]

    for component in root.findall("DataComponent"):
        if component.get("Type") == "info" and component.text and component.text.strip():
            relative = PurePosixPath(component.text.strip().replace("\\", "/"))
            info_path = mod_dir.joinpath(*relative.parts)
            if not info_path.is_file():
                errors.append(
                    f"{mod_dir.name}: info component does not exist: {component.text.strip()}"
                )
                return None, errors
            return info_path, errors
    return None, [f"{mod_dir.name}: ComponentList has no Type='info' component"]


def read_mod_dependencies(mod_dir: Path) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Return (info component, dependency refs, errors) for one component mod."""
    info_path, errors = find_info_component(mod_dir)
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
    except ET.ParseError as exc:
        return info_path.name, [], [f"{mod_dir.name}: invalid {info_path.name} ({exc})"]

    refs: list[dict[str, Any]] = []
    for value in root.findall("./Dependencies/Value"):
        if value.text:
            refs.extend(extract_dependency_refs(value.text.strip()))
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


def build_dependency_graph(primary_mod: Path, mods_dir: Path) -> dict[str, Any]:
    """Recursively resolve local component dependencies with cycle protection."""
    primary_mod = primary_mod.resolve(strict=False)
    mods_dir = mods_dir.resolve(strict=False)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    errors: list[str] = []
    missing: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(mod_dir: Path, stack: tuple[str, ...]) -> None:
        source_key = _path_key(mod_dir)
        if source_key in visited:
            return
        visited.add(source_key)

        info_component, refs, node_errors = read_mod_dependencies(mod_dir)
        errors.extend(node_errors)
        nodes[source_key] = {
            "name": mod_dir.name,
            "path": str(mod_dir),
            "info_component": info_component,
        }

        next_stack = stack + (source_key,)
        for ref in refs:
            edge: dict[str, Any] = {
                "source": source_key,
                "raw": ref["raw"],
                "file_path": ref.get("file_path"),
            }
            target = _resolve_local_mod(ref, mods_dir)
            if target is None or (ref.get("is_network") and not target.is_dir()):
                edge["kind"] = "external"
                edges.append(edge)
                continue

            target_key = _path_key(target)
            edge.update(
                {
                    "kind": "local",
                    "target": target_key,
                    "target_name": target.name,
                    "target_path": str(target),
                    "exists": target.is_dir(),
                    "cycle": target_key in next_stack,
                }
            )
            edges.append(edge)
            if not target.is_dir():
                missing.append(edge)
            elif target_key not in visited:
                visit(target, next_stack)

    visit(primary_mod, ())
    return {
        "primary": _path_key(primary_mod),
        "mods_dir": str(mods_dir),
        "nodes": nodes,
        "edges": edges,
        "missing": missing,
        "errors": errors,
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
