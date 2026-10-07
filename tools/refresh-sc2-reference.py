#!/usr/bin/env python3
"""Verify or refresh the official/partner component reference snapshot."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "DataEditorXML" / "SC2GameDataComponents"
SELECTIONS = ("Base.SC2Data/GameData", "enUS.SC2Data", "zhCN.SC2Data")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def source_files(sources: dict[str, Path]) -> tuple[dict[Path, Path], int]:
    files: dict[Path, Path] = {}
    packages = 0
    for category, source_root in sources.items():
        if not source_root.is_dir():
            raise ValueError(f"source directory does not exist: {source_root}")
        for package in sorted(source_root.rglob("*")):
            if not package.is_dir() or not package.name.casefold().endswith((".sc2mod", ".sc2campaign")):
                continue
            selected = False
            for selection in SELECTIONS:
                directory = package / selection
                if not directory.is_dir():
                    continue
                selected = True
                for source in directory.rglob("*"):
                    if source.is_file():
                        relative = Path(category) / package.relative_to(source_root) / selection / source.relative_to(directory)
                        files[relative] = source
            packages += selected
    return files, packages


def compare(files: dict[Path, Path], target: Path) -> tuple[list[Path], list[Path], list[Path], int]:
    actual = {
        path.relative_to(target): path
        for path in target.rglob("*")
        if path.is_file() and path.relative_to(target) != Path("README.md")
    } if target.is_dir() else {}
    missing = sorted(files.keys() - actual.keys())
    extra = sorted(actual.keys() - files.keys())
    changed = []
    total_bytes = 0
    for relative, source in files.items():
        total_bytes += source.stat().st_size
        destination = actual.get(relative)
        if destination and (
            source.stat().st_size != destination.stat().st_size
            or digest(source) != digest(destination)
        ):
            changed.append(relative)
    return missing, extra, changed, total_bytes


def updated_readme(readme: Path, packages: int, files: int, size: int) -> str:
    if not readme.is_file():
        raise ValueError(f"snapshot README is missing: {readme}")
    original = readme.read_text(encoding="utf-8")
    pattern = r"本次提取覆盖 [\d,]+ 个组件包、[\d,]+ 个源文件，共 [\d,]+ 字节。"
    replacement = f"本次提取覆盖 {packages:,} 个组件包、{files:,} 个源文件，共 {size:,} 字节。"
    updated, count = re.subn(pattern, replacement, original)
    if count != 1:
        raise ValueError("snapshot README count line was not found exactly once")
    return updated


def refresh(files: dict[Path, Path], target: Path, readme_text: str) -> Path:
    stage = Path(tempfile.mkdtemp(prefix=".sc2-reference-stage-", dir=target.parent))
    backup = target.parent / f".sc2-reference-backup-{stage.name.rsplit('-', 1)[-1]}"
    try:
        for relative, source in files.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if source.stat().st_size != destination.stat().st_size or digest(source) != digest(destination):
                raise ValueError(f"staging copy mismatch: {relative}")
        (stage / "README.md").write_text(readme_text, encoding="utf-8")
        target.rename(backup)
        try:
            stage.rename(target)
        except OSError:
            backup.rename(target)
            raise
        return backup
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mods", type=Path, required=True)
    parser.add_argument("--campaigns", type=Path, required=True)
    parser.add_argument("--cm", type=Path, required=True)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--apply", action="store_true", help="replace the verified snapshot and retain a backup")
    args = parser.parse_args()
    target = args.target.resolve()
    sources = {"mods": args.mods.resolve(), "campaigns": args.campaigns.resolve(), "CM": args.cm.resolve()}
    try:
        files, packages = source_files(sources)
        if not files or not target.is_dir():
            raise ValueError("source selection or existing snapshot is empty")
        missing, extra, changed, size = compare(files, target)
        print(f"packages={packages} files={len(files)} bytes={size}")
        print(f"missing={len(missing)} extra={len(extra)} changed={len(changed)}")
        readme_text = updated_readme(target / "README.md", packages, len(files), size)
        readme_changed = readme_text != (target / "README.md").read_text(encoding="utf-8")
        if not (missing or extra or changed or readme_changed):
            return 0
        for label, items in (("missing", missing), ("extra", extra), ("changed", changed)):
            for relative in items[:10]:
                print(f"{label}: {relative}")
        if not args.apply:
            return 1
        backup = refresh(files, target, readme_text)
        print(f"refreshed; previous snapshot retained at {backup}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
