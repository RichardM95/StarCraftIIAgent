"""Independent terrain validation copies; source maps are strictly read-only."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil

from .errors import SC2Error
from .storage import write_json
from .terrain import Terrain, plan_terrain, render_terrain
from .transactions import Transactions


def _files(root: Path) -> dict[str, str]:
    result = {}
    seen = set()
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in folders + names:
            p = Path(directory) / name
            if p.is_symlink() or p.is_junction():
                raise SC2Error("FIXTURE_LINK", "验证模板不能包含符号链接或目录联接。", path=str(p))
        for name in sorted(names):
            p = Path(directory) / name
            relative = p.relative_to(root).as_posix()
            if relative.casefold() in seen:
                raise SC2Error("FIXTURE_COLLISION", "验证模板存在大小写文件名碰撞。", path=relative)
            seen.add(relative.casefold())
            with p.open("rb") as stream:
                result[relative] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def create_editor_validation_fixture(source: Path, destination: Path, operations: list[dict] | None = None) -> dict:
    """Copy a component map twice, transact candidate edits, and keep previews."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir() or source.suffix.casefold() != ".sc2map" or not (source / "DocumentInfo").is_file():
        raise SC2Error("INVALID_FIXTURE_SOURCE", "验证模板必须是包含 DocumentInfo 的组件地图。")
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise SC2Error("INVALID_FIXTURE_DESTINATION", "验证输出必须是模板之外的全新目录。")
    operations = operations if operations is not None else [{"op": "raise", "rect": [30, 30, 40, 40], "value": 0.25}]
    before = _files(source)
    destination.mkdir(parents=True, exist_ok=False)
    original, candidate = destination / "original.SC2Map", destination / "candidate.SC2Map"
    shutil.copytree(source, original, copy_function=shutil.copy2)
    shutil.copytree(source, candidate, copy_function=shutil.copy2)
    if _files(original) != before or _files(candidate) != before or _files(source) != before:
        raise SC2Error("FIXTURE_SOURCE_CHANGED", "复制期间模板发生变化；已保留诊断副本，未执行地形修改。")
    transactions = Transactions(destination / "state")
    transaction = transactions.run(candidate, lambda: plan_terrain(candidate, operations), label="independent_editor_height_validation",
                                   validator=lambda changes: {"static": "parsed", "terrain": Terrain(candidate, changes).summary()})
    original_preview = render_terrain(original, destination / "previews" / "original")
    candidate_preview = render_terrain(candidate, destination / "previews" / "candidate")
    after = _files(candidate)
    unchanged = _files(source) == before and _files(original) == before
    if not unchanged:
        raise SC2Error("FIXTURE_SOURCE_CHANGED", "模板或原样副本在创建期间发生变化；未标记验证成功。")
    result = {"source": str(source), "directory": str(destination), "original": str(original), "candidate": str(candidate),
              "source_unchanged": unchanged, "operations": operations, "source_hashes": before,
              "candidate_hashes": after,
              "changed_files": sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name) and not name.startswith(".sc2-mcp/")),
              "tooling_files": sorted(name for name in after if name.startswith(".sc2-mcp/")),
              "transaction": transaction, "previews": {"original": original_preview, "candidate": candidate_preview},
              "evidence": {"static": "passed", "editor": "not_run", "runtime": "not_run", "visual": "not_accepted"}}
    write_json(destination / "fixture.json", result)
    return result
