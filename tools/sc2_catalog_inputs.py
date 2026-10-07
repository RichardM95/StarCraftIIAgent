"""Input inventory for the SC2 catalog index and its freshness checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


MANIFEST_SUFFIX = ".inputs.json"
LOCALIZATION_NAMES = ("GameStrings.txt", "ObjectStrings.txt", "TriggerStrings.txt")


def catalog_xml_inputs(root: Path, mods: tuple[Path, ...] | list[Path]) -> list[Path]:
    files: list[Path] = []
    for directory in (root / "DataEditorXML", root / "XMLFromDependenciesWeDontUse"):
        if directory.is_dir():
            files.extend(directory.glob("*.txt"))
    for mod in mods:
        directory = mod / "Base.SC2Data" / "GameData"
        if directory.is_dir():
            files.extend(directory.glob("*.xml"))
    return sorted((path for path in files if path.is_file()), key=lambda path: str(path).casefold())


def index_inputs(root: Path, mods: tuple[Path, ...] | list[Path]) -> list[Path]:
    files = catalog_xml_inputs(root, mods)
    config = root / "agent-config.json"
    if config.is_file():
        files.append(config)
    for mod in mods:
        for name in ("ComponentList.SC2Components", "DocumentInfo"):
            path = mod / name
            if path.is_file():
                files.append(path)
        locale = mod / "enUS.SC2Data" / "LocalizedData"
        files.extend(path for name in LOCALIZATION_NAMES if (path := locale / name).is_file())
    return sorted(set(files), key=lambda path: str(path).casefold())


def manifest_path(index_path: Path) -> Path:
    return index_path.with_name(index_path.name + MANIFEST_SUFFIX)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(paths: list[Path]) -> dict[str, dict[str, int | str]]:
    result = {}
    for path in paths:
        stat = path.stat()
        result[path.resolve(strict=False).as_posix()] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": file_digest(path),
        }
    return result


def save_manifest(index_path: Path, files: dict[str, dict[str, int | str]]) -> None:
    path = manifest_path(index_path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps({"version": 1, "files": files}, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def changed_input(
    index_path: Path, paths: list[Path], *, verify_hashes: bool = False
) -> Path | None:
    """Return the first changed input; metadata is fast, optional hashes are exact."""
    path = manifest_path(index_path)
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        old = manifest["files"]
        if manifest["version"] != 1 or not isinstance(old, dict):
            return path
    except (OSError, ValueError, KeyError, TypeError):
        return path
    current = {item.resolve(strict=False).as_posix(): item for item in paths}
    for key in sorted(set(old) | set(current)):
        item = current.get(key)
        previous = old.get(key)
        if item is None or not isinstance(previous, dict):
            return Path(key)
        try:
            stat = item.stat()
            if stat.st_size != previous.get("size") or stat.st_mtime_ns != previous.get("mtime_ns"):
                return item
            if verify_hashes and file_digest(item) != previous.get("sha256"):
                return item
        except OSError:
            return item
    return None
