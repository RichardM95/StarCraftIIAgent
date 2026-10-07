#!/usr/bin/env python3
"""Shared project-path discovery for SC2 validation tools.

Project paths normally come from ``agent-config.json``.  Environment variables
and sibling-layout discovery are fallbacks only when no primary project is configured. Explicit CLI paths override configuration.
"""
from __future__ import annotations

import os
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "agent-config.json"


def config_path(repo_root: Path) -> Path:
    return repo_root / CONFIG_FILENAME


def load_project_config(repo_root: Path) -> dict[str, Any]:
    """Load the optional workspace configuration without machine-specific state."""
    path = config_path(repo_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid {CONFIG_FILENAME}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {CONFIG_FILENAME}: root value must be an object")
    return data


def _config_value(config: Mapping[str, Any], section: str, key: str) -> str | None:
    section_value = config.get(section, {})
    if not isinstance(section_value, Mapping):
        return None
    value = section_value.get(key)
    return value if isinstance(value, str) and value.strip() else None


def resolve_configured_path(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve(strict=False)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve(strict=False)).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def candidate_mod_roots(
    repo_root: Path,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Return portable candidate directories that may contain project mods."""
    env = os.environ if env is None else env
    config = load_project_config(repo_root) if config is None else config
    roots: list[Path] = []

    configured_root = _config_value(config, "paths", "mods_dir")
    if configured_root:
        roots.append(resolve_configured_path(repo_root, configured_root))

    environment_root = env.get("SC2_MODS_PATH")
    if environment_root:
        roots.append(Path(environment_root).expanduser())

    roots.extend((repo_root, repo_root.parent))

    # Supports layouts such as:
    #   <parent>/StarCraftIIAgent
    #   <parent>/StarCraft II/Mods/AeonOfIhanrii.SC2Mod
    for ancestor in repo_root.parents:
        roots.append(ancestor / "StarCraft II" / "Mods")

    return _unique_paths(roots)


def find_project_mods(
    repo_root: Path,
    explicit: str | None = None,
    *,
    primary_name: str | None = None,
    env: Mapping[str, str] | None = None,
    config: Mapping[str, Any] | None = None,
) -> list[Path]:
    """Find the configured primary mod, or resolve one explicit mod path.

    An explicit relative path is resolved from ``repo_root``.  Automatic
    discovery intentionally selects only the configured primary project mod;
    validating every dependency in the SC2 Mods directory would produce
    unrelated failures and make the pre-flight suite non-deterministic.
    """
    env = os.environ if env is None else env
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = repo_root / path
        path = path.resolve(strict=False)
        return [path] if path.is_dir() else []

    config = load_project_config(repo_root) if config is None else config

    project = config.get("project", {})
    source_mode = project.get("source_mode", "in_place") if isinstance(project, Mapping) else "in_place"
    if source_mode == "workspace_copy":
        source = _config_value(config, "project", "source_mod")
        if not source:
            return []
        path = resolve_configured_path(repo_root, source)
        return [path] if path.is_dir() and path.suffix.casefold() == ".sc2mod" else []
    if source_mode != "in_place":
        return []

    configured_primary = _config_value(config, "project", "primary_mod")
    if isinstance(project, Mapping) and "primary_mod" in project:
        if not configured_primary:
            return []
        configured_root = _config_value(config, "paths", "mods_dir")
        if not configured_root:
            return []
        root = resolve_configured_path(repo_root, configured_root)
        relative = Path(configured_primary)
        if relative.is_absolute() or relative.suffix.casefold() != ".sc2mod":
            return []
        path = (root / relative).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError:
            return []
        return [path] if path.is_dir() else []

    mod_name = (
        primary_name
        or _config_value(config, "project", "primary_mod")
        or env.get("SC2_PRIMARY_MOD")
    )
    if not mod_name:
        return []
    if not mod_name.lower().endswith(".sc2mod"):
        mod_name += ".SC2Mod"

    matches: list[Path] = []
    for root in candidate_mod_roots(repo_root, env, config):
        resolved_root = root.resolve(strict=False)
        candidate = (resolved_root / mod_name).resolve(strict=False)
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        if candidate.is_dir():
            matches.append(candidate)
    return _unique_paths(matches)


def project_identity_path(repo_root: Path, config: Mapping[str, Any]) -> Path | None:
    """Installed primary identity, independent of workspace_copy's editing source."""
    project = config.get("project", {})
    if not isinstance(project, Mapping):
        raise ValueError("project must be an object")
    if "primary_mod" not in project:
        return None
    primary = project["primary_mod"]
    mods = _config_value(config, "paths", "mods_dir")
    if not isinstance(primary, str) or not primary.strip() or not mods:
        raise ValueError("project.primary_mod and paths.mods_dir must be non-empty strings")
    mods_root = resolve_configured_path(repo_root, mods)
    raw = Path(primary)
    path = (mods_root / raw).resolve()
    if raw.is_absolute() or not path.is_relative_to(mods_root) or path.suffix.casefold() != ".sc2mod":
        raise ValueError("project.primary_mod must be a relative .SC2Mod inside paths.mods_dir")
    return path


def project_data_dir(repo_root: Path, config: Mapping[str, Any] | None = None,
                     primary: Path | None = None) -> Path | None:
    """Resolve only; no files or directories are created."""
    config = load_project_config(repo_root) if config is None else config
    identity = project_identity_path(repo_root, config)
    project = config.get("project", {})
    explicit_other = False
    if primary is not None:
        primary = primary.resolve()
        source = _config_value(config, "project", "source_mod") if project.get("source_mode") == "workspace_copy" else None
        configured_source = resolve_configured_path(repo_root, source) if source else identity
        explicit_other = primary not in (identity, configured_source)
        if explicit_other:
            identity = primary
    if identity is None:
        if "data_dir" in project:
            raise ValueError("project.data_dir requires a selected primary project")
        return None
    if "data_dir" in project and not explicit_other:
        value = project["data_dir"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("project.data_dir must be a non-empty string")
        result = resolve_configured_path(repo_root, value)
    else:
        result = identity.with_name(identity.stem + ".agent").resolve()
    if result.is_relative_to(repo_root.resolve()):
        raise ValueError("Project data must be outside the development suite: " + str(result))
    if any(p.suffix.casefold() in (".sc2mod", ".sc2map") for p in (result, *result.parents)):
        raise ValueError("Project data must be outside game Components: " + str(result))
    for path in (result, *result.parents):
        if path.exists() and not path.is_dir():
            raise ValueError("Project data path is blocked by a file: " + str(path))
    return result


def catalog_output_dir(repo_root: Path, config: Mapping[str, Any] | None = None,
                       primary: Path | None = None) -> Path:
    data = project_data_dir(repo_root, config, primary)
    return data / "runtime/catalog" if data else repo_root.resolve().with_name(repo_root.name + "-data") / "reference"


def ensure_project_data(data: Path) -> None:
    """Called only for a real write; preserve an existing user's ignore file."""
    data.mkdir(parents=True, exist_ok=True)
    ignore = data / ".gitignore"
    try:
        with ignore.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("runtime/\n")
    except FileExistsError:
        if not ignore.is_file():
            raise ValueError("Project .gitignore is not a file: " + str(ignore))
