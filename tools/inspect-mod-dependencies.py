#!/usr/bin/env python3
"""Inspect an SC2 component mod's recursive dependency graph."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sc2_dependencies import build_dependency_graph, render_dependency_tree, resolve_dependency_root, dependency_state
from sc2_paths import find_project_mods, load_project_config, resolve_configured_path


REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-dir", help="Primary .SC2Mod component directory")
    parser.add_argument("--mods-dir", help="Explicit dependency Mods root")
    parser.add_argument("--allow-incomplete-dependencies", action="store_true", help="Explicit partial read-only dependency investigation; does not certify completeness")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    try:
        config = load_project_config(REPO_ROOT)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    mods = find_project_mods(REPO_ROOT, args.mod_dir, config=config)
    if not mods:
        print("ERROR: Primary .SC2Mod directory not found.")
        return 1

    try:
        mods_dir = resolve_dependency_root(REPO_ROOT, mods[0], config, args.mods_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    graph = build_dependency_graph(mods[0], mods_dir)
    state = dependency_state(graph)
    graph["dependency_status"] = state
    if state["status"] == "partial" and args.allow_incomplete_dependencies:
        print("WARNING: PARTIAL read-only investigation: " + "; ".join(state["problems"]), file=sys.stderr)

    if args.json:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
    else:
        print("RECURSIVE MOD DEPENDENCY GRAPH")
        print("=" * 60)
        for line in render_dependency_tree(graph):
            print(line)
        external_count = sum(1 for edge in graph["edges"] if edge["kind"] == "external")
        print("=" * 60)
        print(f"Local component mods: {len(graph['nodes'])}")
        print(f"Engine/network references: {external_count}")
        print(f"Missing local component mods: {len(graph['missing'])}")
        print(f"Component metadata errors: {len(graph['errors'])}")
        for error in graph["errors"]:
            print(f"  [ERROR] {error}")

    return 1 if state["status"] == "partial" and not args.allow_incomplete_dependencies else 0


if __name__ == "__main__":
    sys.exit(main())
