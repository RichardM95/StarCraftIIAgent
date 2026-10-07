#!/usr/bin/env python3
"""Validate agent-config.json and its configured SC2 project paths."""
from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from sc2_dependencies import build_dependency_graph
from sc2_paths import CONFIG_FILENAME, config_path, load_project_config, resolve_configured_path, project_data_dir


REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PATHS = (
    "workspace_dir",
    "sc2_install_dir",
    "mods_dir",
    "campaign_maps_dir",
)
OPTIONAL_EXISTENCE_PATHS = {"campaign_maps_dir"}


def main() -> int:
    path = config_path(REPO_ROOT)
    if not path.is_file():
        print(f"ERROR: Missing {path}")
        return 1

    try:
        config = load_project_config(REPO_ROOT)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    failures: list[str] = []
    warnings: list[str] = []
    if config.get("schema_version") != 1:
        failures.append("schema_version must be 1")

    paths = config.get("paths")
    if not isinstance(paths, Mapping):
        failures.append("paths must be an object")
        paths = {}

    resolved_paths: dict[str, Path] = {}
    for key in REQUIRED_PATHS:
        value = paths.get(key)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"paths.{key} must be a non-empty string")
            continue
        resolved = resolve_configured_path(REPO_ROOT, value)
        resolved_paths[key] = resolved
        if not resolved.is_dir():
            message = f"paths.{key} directory not found: {resolved}"
            if key in OPTIONAL_EXISTENCE_PATHS:
                warnings.append(message)
            else:
                failures.append(message)
        if Path(value).is_absolute():
            warnings.append(
                f"paths.{key} uses a machine-specific absolute path: {value}"
            )

    project = config.get("project")
    if not isinstance(project, Mapping):
        failures.append("project must be an object")
        project = {}

    primary_mod = project.get("primary_mod")
    primary_path: Path | None = None
    if not isinstance(primary_mod, str) or not primary_mod.strip():
        failures.append("project.primary_mod must be a non-empty string")
    elif "mods_dir" in resolved_paths:
        mods_root = resolved_paths["mods_dir"].resolve(strict=False)
        raw_primary = Path(primary_mod)
        if raw_primary.is_absolute():
            failures.append("project.primary_mod must be relative to paths.mods_dir")
        else:
            primary_path = (mods_root / raw_primary).resolve(strict=False)
            try:
                primary_path.relative_to(mods_root)
            except ValueError:
                failures.append("project.primary_mod must stay inside paths.mods_dir")
                primary_path = None
            if primary_path is not None and primary_path.suffix.casefold() != ".sc2mod":
                failures.append("project.primary_mod must end with .SC2Mod")
            if (project.get("source_mode", "in_place") != "workspace_copy"
                    and primary_path is not None and not primary_path.is_dir()):
                failures.append(f"project.primary_mod directory not found: {primary_path}")

    recursive = project.get("resolve_dependencies_recursive", True)
    if not isinstance(recursive, bool):
        failures.append("project.resolve_dependencies_recursive must be true or false")

    source_mode = project.get("source_mode", "in_place")
    if source_mode not in {"in_place", "workspace_copy"}:
        failures.append("project.source_mode must be 'in_place' or 'workspace_copy'")
    if source_mode == "workspace_copy":
        source_mod = project.get("source_mod")
        if not isinstance(source_mod, str) or not source_mod.strip():
            failures.append("project.source_mod is required in workspace_copy mode")
            primary_path = None
        else:
            primary_path = resolve_configured_path(REPO_ROOT, source_mod)
            if primary_path.suffix.casefold() != ".sc2mod":
                failures.append("project.source_mod must end with .SC2Mod")
            if not primary_path.is_dir():
                failures.append(f"project.source_mod directory not found: {primary_path}")

    try:
        project_data_dir(REPO_ROOT, config)
    except ValueError as exc:
        failures.append(str(exc))

    validation = config.get("validation", {})
    if not isinstance(validation, Mapping):
        failures.append("validation must be an object")
        validation = {}
    include_dependencies = validation.get("include_dependencies", False)
    if not isinstance(include_dependencies, bool):
        failures.append("validation.include_dependencies must be true or false")
    exclude_mods = validation.get("exclude_mods", [])
    if not isinstance(exclude_mods, list) or not all(
        isinstance(name, str) and name.strip() for name in exclude_mods
    ):
        failures.append("validation.exclude_mods must be an array of non-empty strings")
        exclude_mods = []
    for name in exclude_mods:
        if not name.casefold().endswith(".sc2mod"):
            failures.append(f"validation.exclude_mods entry must end with .SC2Mod: {name}")

    dependency_graph = None
    if recursive and primary_path is not None and primary_path.is_dir() and "mods_dir" in resolved_paths:
        dependency_graph = build_dependency_graph(primary_path, resolved_paths["mods_dir"])
        failures.extend(dependency_graph["errors"])
        for edge in dependency_graph["missing"]:
            failures.append(
                f"missing recursive mod dependency: {edge['target_name']} "
                f"(declared by {dependency_graph['nodes'][edge['source']]['name']})"
            )

    print(f"Configuration: {path}")
    for key in REQUIRED_PATHS:
        if key in resolved_paths:
            print(f"  {key}: {resolved_paths[key]}")
    print(f"  source_mode: {source_mode}")
    if dependency_graph is not None:
        print(f"  recursive_component_mods: {len(dependency_graph['nodes'])}")

    if warnings:
        print(f"{CONFIG_FILENAME} warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    if failures:
        print(f"{CONFIG_FILENAME} validation failed ({len(failures)} issue(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"{CONFIG_FILENAME} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
