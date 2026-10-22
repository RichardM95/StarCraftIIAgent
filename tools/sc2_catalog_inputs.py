"""Input inventory for the SC2 catalog index and its freshness checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sc2_dependencies import find_info_component
from sc2_official import catalog_paths, cache_manifest, component_file, safe_path
from sc2_components import component_path, archive_of, provenance, verify_archives, source_for


MANIFEST_SUFFIX = ".inputs.json"
MANIFEST_VERSION = 8
LOCALIZATION_NAMES = ("GameStrings.txt", "ObjectStrings.txt", "TriggerStrings.txt")


def catalog_xml_inputs(root: Path, mods: tuple[Path, ...] | list[Path], *, official_research=False, manifests=None) -> list[Path]:
    files: list[Path] = []
    manifests = {} if manifests is None else manifests
    registrations = {}
    for directory in (root / "DataEditorXML", root / "XMLFromDependenciesWeDontUse"):
        if directory.is_dir():
            files.extend(sorted(directory.glob("*.txt")))
    for mod in mods:
        manifest = cache_manifest(mod)
        if manifest and manifest not in manifests:
            manifests[manifest] = json.loads(manifest.read_text(encoding='utf-8'))
        if manifest and not official_research and manifest not in registrations:
            from sc2_engine_dependencies import catalog_registration
            data = manifests[manifest]
            registrations[manifest] = (catalog_registration(Path(data['identity']['install']), data['identity'], data['engine'])
                                       if data.get('engine') else False)
        files.extend(catalog_paths(mod, research=official_research, manifest_data=manifests.get(manifest),
                                   registration=registrations.get(manifest, False)))
    return list(dict.fromkeys(path for path in files if path.is_file()))


def index_inputs(root: Path, mods: tuple[Path, ...] | list[Path], *, official_research=False) -> list[Path]:
    data_by_manifest = {}
    files = catalog_xml_inputs(root, mods, official_research=official_research, manifests=data_by_manifest)
    manifests = set()
    config = root / "agent-config.json"
    if config.is_file():
        files.append(config)
    for mod in mods:
        mod = component_path(mod)
        for name in ("ComponentList.SC2Components", "DocumentInfo"):
            path = mod / name
            if path.is_file():
                files.append(path)
        info, _errors = find_info_component(mod)
        if info is not None:
            files.append(info)
        for language in ("enUS", "zhCN"):
            files.extend(path for name in LOCALIZATION_NAMES
                         if (path := component_file(mod, language + ".SC2Data/LocalizedData/" + name)).is_file())
        official = cache_manifest(mod)
        if official:
            manifests.add(official)
        archive = archive_of(mod)
        if archive:
            files.append(archive)
            files.extend(Path(__file__).with_name(name) for name in ('sc2_components.py', 'sc2_mpq.py', 'sc2_casc.py'))
            files.append(Path(__file__).parent / 'vendor/stormlib/StormLib.dll')
    for official in sorted(manifests):
        data = data_by_manifest.get(official)
        if data is None:
            data = json.loads(official.read_text(encoding="utf-8"))
        files.extend((official, Path(data["identity"]["install"]) / ".build.info"))
        if data.get('engine') and data['engine'].get('path'):
            files.append(Path(data['engine']['path']))
        # Include each cache inventory once: registries, includes and available locales.
        files.extend(path for k in data["files"] if (path := safe_path(official.parent, k)).is_file())
    if manifests:
        files.extend(Path(__file__).with_name(name) for name in ('sc2_official.py', 'sc2_engine_dependencies.py', 'sc2_dependencies.py'))
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
    verify_archives()
    result = {}
    for path in paths:
        stat = path.stat()
        result[path.resolve(strict=False).as_posix()] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": file_digest(path),
        }
        if archive_of(path) and Path(path) != archive_of(path):
            entry = result[path.resolve(strict=False).as_posix()]
            entry['source'] = provenance(path, member_sha256=entry['sha256'])
    verify_archives()
    return result


def save_manifest(index_path: Path, files: dict[str, dict[str, int | str]], *,
                  dependencies: dict | None = None, build_id: str | None = None,
                  selection: dict | None = None) -> None:
    path = manifest_path(index_path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps({"version": MANIFEST_VERSION, "files": files,
                                "dependencies": dependencies or {"status": "complete", "problems": []},
                                "build_id": build_id, "selection": selection},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def read_manifest(index_path: Path) -> dict:
    path = manifest_path(index_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = data.setdefault("dependencies", {"status": "complete", "problems": []})
        if (data.get("version") not in {1, 2, 3, 4, 5, 6, 7, MANIFEST_VERSION} or not isinstance(data.get("files"), dict)
                or state.get("status") not in {"complete", "partial"}
                or not isinstance(state.get("problems"), list)
                or not all(isinstance(item, str) for item in state["problems"])
                or bool(state["problems"]) != (state["status"] == "partial")):
            raise ValueError("Unsupported input/dependency manifest")
        return data
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"Catalog manifest requires rebuild: {path} ({exc})") from exc


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
        if manifest["version"] != MANIFEST_VERSION or not isinstance(old, dict):
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
            if archive_of(item):
                current_archive = source_for(item).sha256
                recorded_archive = (previous.get('source') or {}).get('archive_sha256') if Path(item) != archive_of(item) else previous.get('sha256')
                if recorded_archive != current_archive:
                    return item
            if verify_hashes and file_digest(item) != previous.get("sha256"):
                return item
        except OSError:
            return item
    return None
