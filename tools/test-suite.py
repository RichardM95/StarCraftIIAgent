#!/usr/bin/env python3
"""Unified test suite runner for StarCraft II Custom Campaign projects.

Executes fast static linters, schema validators, integrity checks, and link audits.
Designed for AI coding agents and developers to run before committing any changes.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from sc2_dependencies import build_dependency_graph, resolve_dependency_root, dependency_problems
from sc2_paths import (
    config_path,
    find_project_mods,
    load_project_config,
    resolve_configured_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def validation_settings(config: Mapping[str, object]) -> tuple[bool, set[str]]:
    """Return dependency-scan defaults from agent-config.json."""
    raw = config.get("validation", {})
    if not isinstance(raw, Mapping):
        return False, set()
    include_dependencies = raw.get("include_dependencies", False) is True
    raw_exclusions = raw.get("exclude_mods", [])
    if not isinstance(raw_exclusions, list):
        return include_dependencies, set()
    exclusions = {
        name.strip().casefold()
        for name in raw_exclusions
        if isinstance(name, str) and name.strip()
    }
    return include_dependencies, exclusions


def dependency_validation_targets(
    primary_mod: Path,
    config: Mapping[str, object],
    exclusions: set[str],
    explicit_mods: str | None = None,
) -> tuple[list[Path], list[str]]:
    """Resolve active component dependencies selected for static validation."""
    try:
        mods_dir = resolve_dependency_root(REPO_ROOT, primary_mod, config, explicit_mods)
    except ValueError as exc:
        return [], [str(exc)]
    graph = build_dependency_graph(primary_mod, mods_dir)
    problems = dependency_problems(graph)
    primary_key = str(primary_mod.resolve(strict=False)).casefold()
    targets: list[Path] = []
    for key, node in graph["nodes"].items():
        if key == primary_key:
            continue
        path = Path(node["path"])
        if path.name.casefold() in exclusions:
            continue
        targets.append(path)
    return targets, problems


def run_step(name: str, cmd: list[str], verbose: bool) -> bool:
    print(f"--> Running {name}...")
    start = time.time()
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    elapsed = time.time() - start
    if res.returncode == 0:
        print(f"    [PASS] {name} ({elapsed:.2f}s)")
        if verbose and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                print(f"      {line}")
        return True
    else:
        print(f"    [FAIL] {name} ({elapsed:.2f}s)")
        if res.stdout.strip():
            print(res.stdout.strip())
        if res.stderr.strip():
            print(res.stderr.strip())
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run fast static pre-flight checks and linters."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show passing subtool output as well as the compact summary.",
    )
    parser.add_argument(
        "--mod-dir",
        help=(
            "Explicit .SC2Mod component directory. If omitted, discover the "
            "primary mod strictly from agent-config.json; environment/layout fallbacks apply only without a configured primary."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=("all", "tools", "docs", "mod"),
        default="all",
        help="Run the full suite or only tool, documentation, or mod checks.",
    )
    parser.add_argument("--mods-dir", help="Explicit dependency Mods root for a one-off component")
    parser.add_argument("--campaigns-dir", help="Explicit dependency Campaigns root for trigger validation")
    dependency_group = parser.add_mutually_exclusive_group()
    dependency_group.add_argument(
        "--include-dependencies",
        dest="include_dependencies",
        action="store_true",
        default=None,
        help="Validate active local component dependencies as well as the primary mod.",
    )
    dependency_group.add_argument(
        "--primary-only",
        dest="include_dependencies",
        action="store_false",
        help="Validate only the primary mod, overriding agent-config.json.",
    )
    parser.add_argument(
        "--exclude-mod",
        action="append",
        default=[],
        help="Component mod folder name to exclude from dependency validation (repeatable).",
    )
    args = parser.parse_args()

    if args.scope in {"tools", "docs"}:
        scoped_steps = (
            [("Tool Unit Tests", [sys.executable, "-m", "unittest", "discover", "-s", "tools/tests", "-p", "test_*.py"])]
            if args.scope == "tools"
            else [
                ("Skill Frontmatter Validator", [sys.executable, "tools/audit-skill-frontmatter.py"]),
                ("Documentation Link Integrity Checker", [sys.executable, "tools/check-doc-links.py"]),
            ]
        )
        print(f"SC2 PRE-FLIGHT: {args.scope} scope")
        results = [run_step(name, command, args.verbose) for name, command in scoped_steps]
        return 0 if all(results) else 1

    try:
        config = load_project_config(REPO_ROOT)
        mods = find_project_mods(REPO_ROOT, args.mod_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        print("Repair agent-config.json or rerun tools/init-project.py with the primary Mod path.")
        return 2
    if not mods:
        requested = args.mod_dir or "the configured primary project mod"
        print(f"ERROR: Could not find {requested}.")
        print(
            "Pass --mod-dir or correct agent-config.json (SC2_MODS_PATH is only a fallback without a configured primary)."
        )
        return 2
    mod_dir = str(mods[0])
    configured_include, configured_exclusions = validation_settings(config)
    include_dependencies = (
        configured_include
        if args.include_dependencies is None
        else args.include_dependencies
    )
    exclusions = configured_exclusions | {
        name.strip().casefold() for name in args.exclude_mod if name.strip()
    }
    dependency_targets: list[Path] = []
    dependency_problems: list[str] = []
    if include_dependencies:
        dependency_targets, dependency_problems = dependency_validation_targets(
            mods[0], config, exclusions, args.mods_dir
        )

    print("=" * 60)
    print("SC2 CUSTOM CAMPAIGN PRE-FLIGHT TEST SUITE")
    print("=" * 60)
    if config_path(REPO_ROOT).is_file():
        print(f"Path config: {config_path(REPO_ROOT)}")
    print(f"Target mod: {mod_dir}")
    if include_dependencies:
        print(f"Dependency validation targets: {len(dependency_targets)}")
        if exclusions:
            print(f"Excluded component mods: {', '.join(sorted(exclusions))}")
    print()

    steps = [
        (
            "Tool Unit Tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tools/tests",
                "-p",
                "test_*.py",
            ],
        ),
        (
            "Agent Path Configuration Validator",
            [sys.executable, "tools/validate-agent-config.py"],
        ),
        (
            "Static XML & Galaxy Script Validator",
            [sys.executable, "tools/validate-mod.py", "--mod-dir", mod_dir],
        ),
        (
            "Command Card Integrity Linter",
            [sys.executable, "tools/audit-actor-and-card-integrity.py", "--mod-dir", mod_dir],
        ),
        (
            "GameStrings Anchor & Localization Audit",
            [sys.executable, "tools/audit-gamestrings-anchors.py", "--mod-dir", mod_dir],
        ),
        ("Issue Lifecycle Ledger Audit", [sys.executable, "tools/audit-issue-lifecycle.py"]),
        ("Skill Frontmatter Validator", [sys.executable, "tools/audit-skill-frontmatter.py"]),
        ("Documentation Link Integrity Checker", [sys.executable, "tools/check-doc-links.py"]),
    ]

    trigger_command = [sys.executable, 'tools/sc2-trigger-query.py', '--target', mod_dir]
    for option, value in (('--mods-dir', args.mods_dir), ('--campaigns-dir', args.campaigns_dir)):
        if value:
            trigger_command.extend([option, value])
    trigger_command.append('check')
    steps.insert(3, ('GUI Trigger Dependency Validator', trigger_command))

    primary_static_index = next(
        index for index, (name, _) in enumerate(steps) if name == "Static XML & Galaxy Script Validator"
    )
    dependency_steps = [
        (
            f"Dependency Static Validator [{target.name}]",
            [sys.executable, "tools/validate-mod.py", "--mod-dir", str(target)],
        )
        for target in dependency_targets
    ]
    steps[primary_static_index + 1:primary_static_index + 1] = dependency_steps
    if args.scope == "mod":
        steps = [
            (name, command)
            for name, command in steps
            if name not in {
                "Tool Unit Tests",
                "Skill Frontmatter Validator",
                "Documentation Link Integrity Checker",
            }
        ]

    all_passed = True
    start_total = time.time()
    passed_steps = 0
    if dependency_problems:
        all_passed = False
        print("Dependency resolution failed:")
        for problem in dependency_problems:
            print(f"  - {problem}")
        print()
    for name, cmd in steps:
        if run_step(name, cmd, args.verbose):
            passed_steps += 1
        else:
            all_passed = False
        print()

    total_elapsed = time.time() - start_total
    print("=" * 60)
    if all_passed:
        print(f"ALL {passed_steps} STATIC PRE-FLIGHT CHECKS PASSED in {total_elapsed:.2f}s.")
        print("=" * 60)
        return 0
    else:
        print(f"TEST SUITE FAILED in {total_elapsed:.2f}s. Please resolve issues above.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
