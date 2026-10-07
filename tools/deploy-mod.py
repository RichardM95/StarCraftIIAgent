#!/usr/bin/env python3
"""Copy a component .SC2Mod to StarCraft II Mods without editing generated files."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from sc2_publication import publish_directory, staged_directory
from sc2_catalog_inputs import file_digest
from sc2_paths import find_project_mods, load_project_config, resolve_configured_path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SC2_MODS_DIR = Path(r"C:\Program Files (x86)\StarCraft II\Mods")


def find_local_mods(explicit: str | None = None) -> list[Path]:
    """Resolve the explicit or configured primary component mod."""
    return find_project_mods(REPO_ROOT, explicit)


def resolve_mods_dir(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        path = path.resolve(strict=False)
        if not path.is_dir():
            raise SystemExit(f"Target Mods directory not found: {path}")
        return path

    config = load_project_config(REPO_ROOT)
    configured = config.get("paths", {}).get("mods_dir") if isinstance(config.get("paths"), dict) else None
    if isinstance(configured, str) and configured.strip():
        path = resolve_configured_path(REPO_ROOT, configured)
        if not path.is_dir():
            raise SystemExit(f"Configured target Mods directory not found: {path}")
        return path

    env = os.environ.get("SC2_MODS_PATH")
    if env:
        path = Path(env).expanduser()
        if path.is_dir():
            return path

    if DEFAULT_SC2_MODS_DIR.is_dir():
        return DEFAULT_SC2_MODS_DIR

    raise SystemExit(
        "Could not resolve the StarCraft II Mods directory. "
        "Pass --mods-dir, correct agent-config.json, or set SC2_MODS_PATH."
    )


def deploy_mod(
    source: Path,
    target_mods_dir: Path,
    clean: bool = False,
    dry_run: bool = False,
    *,
    relative_destination: str | None = None,
) -> Path:
    if not source.is_dir():
        raise SystemExit(f"Source mod directory not found: {source}")

    source = source.resolve(strict=False)
    target_mods_dir = target_mods_dir.resolve(strict=False)
    relative = Path(relative_destination or source.name)
    if relative.is_absolute() or relative.suffix.casefold() != ".sc2mod":
        raise SystemExit("Deployment target must be a relative .SC2Mod path")
    destination = (target_mods_dir / relative).resolve(strict=False)
    try:
        destination.relative_to(target_mods_dir)
    except ValueError as exc:
        raise SystemExit("Deployment target must stay inside the Mods directory") from exc

    print(f"Deploying component mod:\n  Source: {source}\n  Target: {destination}")
    if source == destination:
        print("Source already is the configured target; no copy was performed.")
        return destination
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise SystemExit("Source and deployment target must not contain one another")
    if dry_run:
        print("Dry run; no files were changed.")
        return destination

    def ignored(name):
        return name.endswith((".bak", ".tmp", ".orig")) or name == "__pycache__"
    def snapshot(directory):
        values = {}
        for path in directory.rglob("*"):
            relative = path.relative_to(directory)
            if any(ignored(part) for part in relative.parts):
                continue
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Source member escaped component directory: " + str(path))
            if path.is_file():
                values[relative.as_posix()] = file_digest(path)
        return values
    before = snapshot(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with staged_directory(destination) as stage:
        if destination.exists() and not clean:
            shutil.copytree(destination, stage, dirs_exist_ok=True)
        shutil.copytree(source, stage, dirs_exist_ok=True,
                        ignore=lambda _directory, names: {name for name in names if ignored(name)})
        if snapshot(source) != before:
            raise RuntimeError("Source changed during deployment; previous deployment was preserved")
        for relative, digest in before.items():
            if file_digest(stage / relative) != digest:
                raise RuntimeError("Deployment copy verification failed: " + relative)
        publish_directory(stage, destination, "mod-deployment")

    manifest = destination / "ComponentList.SC2Components"
    if manifest.is_file():
        print(f"Deployment complete. Verified {manifest.name}.")
    else:
        print("Deployment complete.")
    print("Generated Galaxy files were copied unchanged; save in the SC2 Editor to regenerate them.")

    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy .SC2Mod component folder to SC2 Mods directory."
    )
    parser.add_argument("--source", help="Explicit source .SC2Mod folder; deploy by folder name. Automatic deployment preserves project.primary_mod subdirectories.")
    parser.add_argument("--mods-dir", help="Explicit SC2 Mods directory path")
    parser.add_argument("--clean", action="store_true", help="Stage a clean replacement, verify it, then switch; retain one tool-owned previous version")
    parser.add_argument("--dry-run", action="store_true", help="Print source and target without changing files")
    args = parser.parse_args()

    mods = find_local_mods(args.source)
    if not mods:
        print("No .SC2Mod directory found to deploy.")
        return 1

    source_mod = mods[0]
    mods_dir = resolve_mods_dir(args.mods_dir)
    config = {} if args.source else load_project_config(REPO_ROOT)
    project = config.get("project", {}) if isinstance(config.get("project"), dict) else {}
    primary = project.get("primary_mod")
    if not args.source and (not isinstance(primary, str) or not primary.strip()):
        raise SystemExit("Automatic deployment requires project.primary_mod; pass --source for a one-off mod")
    deploy_mod(source_mod, mods_dir, clean=args.clean, dry_run=args.dry_run,
               relative_destination=primary if not args.source else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
