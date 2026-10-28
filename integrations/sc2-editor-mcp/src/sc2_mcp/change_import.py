"""Hash-bound external candidates. Planning only; Transactions owns writes."""
from __future__ import annotations

import re
from pathlib import Path

from .errors import SC2Error
from .storage import digest, guard_absolute_path, normalize_relative_path, safe_path


def plan_import(root: Path, patches: list[dict]) -> dict[str, bytes | None]:
    if not isinstance(patches, list) or not 1 <= len(patches) <= 500:
        raise SC2Error('invalid_patch_manifest', '候选清单需要 1 至 500 个文件')
    result = {}
    seen = set()
    for entry in patches:
        if not isinstance(entry, dict) or set(entry) - {'path', 'baseline_sha256', 'candidate_file', 'candidate_sha256', 'delete'}:
            raise SC2Error('invalid_patch_manifest', '候选文件声明包含未知字段')
        rel = normalize_relative_path(entry.get('path'))
        if rel.casefold() in seen:
            raise SC2Error('case_collision', '候选清单包含重复路径', path=rel)
        seen.add(rel.casefold())
        target = safe_path(root, rel)
        baseline = entry.get('baseline_sha256')
        if baseline is not None and (not isinstance(baseline, str) or not re.fullmatch('[0-9a-f]{64}', baseline)):
            raise SC2Error('invalid_patch_manifest', '基准指纹必须为小写 SHA-256 或 null', path=rel)
        actual = digest(target.read_bytes()) if target.is_file() else None
        if actual != baseline:
            raise SC2Error('baseline_conflict', '候选基准与当前文件不符', path=rel, expected=baseline, actual=actual)
        delete = entry.get('delete', False)
        if not isinstance(delete, bool):
            raise SC2Error('invalid_patch_manifest', 'delete 必须为布尔值', path=rel)
        if delete:
            if entry.get('candidate_file') is not None or entry.get('candidate_sha256') is not None or baseline is None:
                raise SC2Error('invalid_patch_manifest', '删除声明必须指向现存文件且没有候选内容', path=rel)
            result[rel] = None
            continue
        filename = entry.get('candidate_file')
        expected = entry.get('candidate_sha256')
        if not isinstance(filename, str) or not filename or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise SC2Error('invalid_patch_manifest', '候选文件路径与 SHA-256 缺失', path=rel)
        source = guard_absolute_path(Path(filename)).resolve()
        if not source.is_file():
            raise SC2Error('candidate_missing', '候选文件不存在', path=str(source))
        if source.is_relative_to(root.resolve()):
            raise SC2Error('candidate_not_isolated', '候选文件必须位于地图之外', path=str(source))
        if source.stat().st_size > 256 * 1024 * 1024:
            raise SC2Error('candidate_too_large', '单个导入候选不能超过 256 MiB', path=rel)
        raw = source.read_bytes()
        if digest(raw) != expected:
            raise SC2Error('candidate_corrupt', '外部候选指纹不符', path=rel)
        result[rel] = raw
    return result
