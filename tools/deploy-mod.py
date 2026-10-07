#!/usr/bin/env python3
"""Copy a component .SC2Mod to StarCraft II Mods without editing generated files."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

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
        if path.is_dir():
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
) -> Path:
    if not source.is_dir():
        raise SystemExit(f"Source mod directory not found: {source}")

    source = source.resolve(strict=False)
    target_mods_dir = target_mods_dir.resolve(strict=False)
    destination = (target_mods_dir / source.name).resolve(strict=False)

    print(f"Deploying component mod:\n  Source: {source}\n  Target: {destination}")
    if source == destination:
        print("Source already is the configured target; no copy was performed.")
        return destination
    if dry_run:
        print("Dry run; no files were changed.")
        return destination

    if clean and destination.exists():
        print(f"Cleaning existing deployment at {destination}...")
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    def ignore_patterns(dir_path: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name.endswith((".bak", ".tmp", ".orig")) or name == "__pycache__":
                ignored.add(name)
        return ignored

    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore_patterns)

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
    parser.add_argument("--source", help="Path to source .SC2Mod folder")
    parser.add_argument("--mods-dir", help="Explicit SC2 Mods directory path")
    parser.add_argument("--clean", action="store_true", help="Remove target directory before copy")
    parser.add_argument("--dry-run", action="store_true", help="Print source and target without changing files")
    args = parser.parse_args()

    mods = find_local_mods(args.source)
    if not mods:
        print("No .SC2Mod directory found to deploy.")
        return 1

    source_mod = mods[0]
    mods_dir = resolve_mods_dir(args.mods_dir)
    config = load_project_config(REPO_ROOT)
    project = config.get("project", {}) if isinstance(config.get("project"), dict) else {}
    source_mode = project.get("source_mode", "in_place")
    if source_mode == "in_place" and source_mod.resolve(strict=False).parent == mods_dir.resolve(strict=False):
        print(
            "In-place source mode: the configured primary mod is the authoritative source "
            "inside the SC2 Mods directory. Validate and edit it directly; deployment is a no-op."
        )
    deploy_mod(source_mod, mods_dir, clean=args.clean, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
