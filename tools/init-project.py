#!/usr/bin/env python3
"""Configure this agent workspace from one primary .SC2Mod folder path."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from sc2_dependencies import build_dependency_graph, render_dependency_tree
from sc2_paths import CONFIG_FILENAME, config_path, load_project_config, project_identity_path, project_data_dir


REPO_ROOT = Path(__file__).resolve().parent.parent


def infer_project_layout(
    primary_mod: Path,
    *,
    mods_dir: Path | None = None,
    sc2_install_dir: Path | None = None,
    campaign_maps_dir: Path | None = None,
) -> dict[str, Path]:
    """Infer the standard SC2 layout from a primary component-mod directory."""
    primary_mod = primary_mod.resolve(strict=False)
    if mods_dir is not None:
        resolved_mods = mods_dir.resolve(strict=False)
    else:
        resolved_mods = next(
            (parent for parent in primary_mod.parents if parent.name.casefold() == "mods"),
            primary_mod.parent,
        ).resolve(strict=False)
    resolved_install = (
        sc2_install_dir
        or (resolved_mods.parent if resolved_mods.name.casefold() == "mods" else None)
    )
    if resolved_install is None:
        raise ValueError(
            "Could not infer the SC2 install directory because the mod's parent is not named "
            "'Mods'. Pass --sc2-install-dir."
        )
    resolved_install = resolved_install.resolve(strict=False)
    resolved_maps = (
        campaign_maps_dir or resolved_install / "Maps" / "Campaign"
    ).resolve(strict=False)
    return {
        "workspace_dir": REPO_ROOT,
        "sc2_install_dir": resolved_install,
        "mods_dir": resolved_mods,
        "campaign_maps_dir": resolved_maps,
    }


def config_path_value(path: Path) -> str:
    """Prefer a portable relative path, falling back to absolute across drives."""
    try:
        relative = os.path.relpath(path, REPO_ROOT)
    except ValueError:
        return path.resolve(strict=False).as_posix()
    return Path(relative).as_posix()


def primary_mod_config_value(primary_mod: Path, mods_dir: Path) -> str:
    """Return the primary mod path relative to the configured Mods directory."""
    try:
        relative = primary_mod.resolve(strict=False).relative_to(
            mods_dir.resolve(strict=False)
        )
    except ValueError as exc:
        raise ValueError(
            f"Primary mod must be inside the configured Mods directory: {mods_dir}"
        ) from exc
    return relative.as_posix()


def build_config(primary_mod: Path, layout: dict[str, Path], project_data: str | None = None) -> dict[str, Any]:
    """Preserve unknown config keys while replacing project path selection."""
    config = load_project_config(REPO_ROOT)
    previous_identity = project_identity_path(REPO_ROOT, config)
    previous_has_data = previous_identity == primary_mod.resolve() and "data_dir" in config.get("project", {})
    previous_data = config.get("project", {}).get("data_dir") if previous_has_data else None
    config["schema_version"] = 1
    paths = config.setdefault("paths", {})
    if not isinstance(paths, dict):
        paths = {}
        config["paths"] = paths
    paths.update(
        {
            "workspace_dir": ".",
            "sc2_install_dir": config_path_value(layout["sc2_install_dir"]),
            "mods_dir": config_path_value(layout["mods_dir"]),
            "campaign_maps_dir": config_path_value(layout["campaign_maps_dir"]),
        }
    )
    project = config.setdefault("project", {})
    if not isinstance(project, dict):
        project = {}
        config["project"] = project
    project.update(
        {
            "primary_mod": primary_mod_config_value(primary_mod, layout["mods_dir"]),
            "source_mode": "in_place",
            "resolve_dependencies_recursive": True,
        }
    )
    project.pop("dependency_mod_patterns", None)
    project.pop("data_dir", None)
    if project_data is not None:
        project["data_dir"] = project_data
    elif previous_has_data:
        project["data_dir"] = previous_data
    data = project_data_dir(REPO_ROOT, config)
    project["data_dir"] = config_path_value(data)
    return config


def write_config_atomic(config: dict[str, Any]) -> None:
    target = config_path(REPO_ROOT)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("primary_mod", help="Path to the primary .SC2Mod component folder")
    parser.add_argument("--project-data-dir", help="Project documentation/runtime directory; default: sibling <primary-name>.agent")
    parser.add_argument("--mods-dir", help="Override the inferred Mods directory")
    parser.add_argument("--sc2-install-dir", help="Override the inferred SC2 install directory")
    parser.add_argument("--campaign-maps-dir", help="Override the inferred campaign maps directory")
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write configuration even when local dependencies or metadata are incomplete",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print without writing")
    args = parser.parse_args()

    primary_mod = Path(args.primary_mod).expanduser()
    if not primary_mod.is_absolute():
        primary_mod = REPO_ROOT / primary_mod
    primary_mod = primary_mod.resolve(strict=False)

    failures: list[str] = []
    if not primary_mod.is_dir():
        failures.append(f"Primary mod directory not found: {primary_mod}")
    if primary_mod.suffix.casefold() != ".sc2mod":
        failures.append(f"Primary mod folder must end with .SC2Mod: {primary_mod.name}")
    if not (primary_mod / "ComponentList.SC2Components").is_file():
        failures.append(f"Primary mod is not a Components folder: {primary_mod}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    try:
        layout = infer_project_layout(
            primary_mod,
            mods_dir=Path(args.mods_dir).expanduser() if args.mods_dir else None,
            sc2_install_dir=(
                Path(args.sc2_install_dir).expanduser() if args.sc2_install_dir else None
            ),
            campaign_maps_dir=(
                Path(args.campaign_maps_dir).expanduser() if args.campaign_maps_dir else None
            ),
        )
        config = build_config(primary_mod, layout, args.project_data_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    warnings: list[str] = []
    for key in ("sc2_install_dir", "mods_dir"):
        if not layout[key].is_dir():
            failures.append(f"Inferred {key} directory not found: {layout[key]}")
    if not layout["campaign_maps_dir"].is_dir():
        warnings.append(
            "Campaign maps directory does not exist yet; Mod-only setup can continue: "
            f"{layout['campaign_maps_dir']}"
        )

    graph = build_dependency_graph(primary_mod, layout["mods_dir"])
    failures.extend(graph["errors"])
    for edge in graph["missing"]:
        source_name = graph["nodes"][edge["source"]]["name"]
        failures.append(
            f"Missing local dependency {edge['target_name']} declared by {source_name}"
        )

    print("PROJECT INITIALIZATION")
    print("Project data (created only when needed): " + str(project_data_dir(REPO_ROOT, config)))
    print("=" * 60)
    print(f"Workspace:      {REPO_ROOT}")
    print(f"Primary mod:    {primary_mod}")
    print(f"SC2 install:    {layout['sc2_install_dir']}")
    print(f"Mods directory: {layout['mods_dir']}")
    print(f"Campaign maps:  {layout['campaign_maps_dir']}")
    print()
    for line in render_dependency_tree(graph):
        print(line)
    print()
    print(f"Recursive local component mods: {len(graph['nodes'])}")

    if warnings:
        print(f"Initialization warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    if failures:
        print(f"Initialization checks found {len(failures)} issue(s):")
        for failure in failures:
            print(f"  - {failure}")
        if not args.allow_incomplete:
            print(f"Configuration was not changed. Use --allow-incomplete only if intentional.")
            return 1

    if args.dry_run:
        print("\nDry run; configuration was not changed.")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    write_config_atomic(config)
    print(f"\nConfigured project successfully: {config_path(REPO_ROOT)}")
    print(
        "Project identity was not guessed; verify AGENTS.md Library ID, Bank, "
        "script block, and code prefixes before implementation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
