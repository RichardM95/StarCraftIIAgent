from __future__ import annotations

import difflib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .errors import SC2Error
from .agent_bridge import guard_source_changes
from .storage import atomic_write, digest, file_lock, guard_absolute_path, normalize_relative_path, safe_path, snapshot, write_json

_RECOVERABLE = {'committing', 'rolling_back', 'recovery_conflict'}
_STATES = _RECOVERABLE | {'prepared', 'committed', 'reverted', 'rolled_back'}


_DIFF_LINE_LIMIT = 100000


def large_unified_diff(old_lines, new_lines, fromfile, tofile):
    """Return a single-hunk unified diff (list[str]) between two line lists."""

    def emit(out, prefix, payload):
        if payload.endswith("\n"):
            out.append(prefix + payload)
        else:
            out.append(prefix + payload + "\n")
            out.append("\\ No newline at end of file\n")

    old_len = len(old_lines)
    new_len = len(new_lines)
    limit = old_len if old_len < new_len else new_len

    p = 0
    while p < limit and old_lines[p] == new_lines[p]:
        p += 1
    if p == old_len and p == new_len:
        return []

    max_s = limit - p
    s = 0
    while s < max_s and old_lines[old_len - 1 - s] == new_lines[new_len - 1 - s]:
        s += 1

    L = p if p < 3 else 3
    R = s if s < 3 else 3
    old_start = p - L
    new_start = p - L
    old_tail = old_len - s
    new_tail = new_len - s
    old_count = old_tail + R - old_start
    new_count = new_tail + R - new_start

    def rng(start, count):
        if count == 0:
            return "%d,0" % start
        return "%d,%d" % (start + 1, count)

    out = [
        "--- " + fromfile + "\n",
        "+++ " + tofile + "\n",
        "@@ -" + rng(old_start, old_count) + " +" + rng(new_start, new_count) + " @@\n",
    ]
    for line in old_lines[old_start:p]:
        emit(out, " ", line)
    for line in old_lines[p:old_tail]:
        emit(out, "-", line)
    for line in new_lines[p:new_tail]:
        emit(out, "+", line)
    for line in old_lines[old_tail:old_tail + R]:
        emit(out, " ", line)
    return out


def _unified_diff(old_text, new_text, fromfile, tofile):
    """Unified diff lines: byte-identical legacy output below _DIFF_LINE_LIMIT.

    Larger inputs get a bounded, linear-time form instead of difflib: the exact
    common line prefix and suffix are trimmed, up to _DIFF_CONTEXT of each is kept
    as context, and every remaining old line is deleted and every remaining new
    line inserted in one hunk. Nothing in the middle is omitted, and the hunk
    carries absolute old/new coordinates so applying it reproduces new_text.
    """
    old_lines, new_lines = old_text.splitlines(True), new_text.splitlines(True)
    if len(old_lines) + len(new_lines) < _DIFF_LINE_LIMIT:
        return difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile)
    return large_unified_diff(old_lines, new_lines, fromfile, tofile)


class Transactions:
    """Optimistic transactions serialized across processes and state directories.

    Map-local .sc2-mcp metadata is excluded from snapshots and archive exports.
    An active journal marker blocks new writes until interrupted work is recovered.
    Uncooperative external editors cannot be locked: hashes are rechecked before
    each mutation, and restoration never overwrites a third fingerprint.
    """

    def __init__(self, state: Path):
        self.state = guard_absolute_path(Path(state)).resolve()

    def lock(self, root: Path):
        root = guard_absolute_path(Path(root)).resolve()
        if not root.is_dir():
            raise SC2Error('project_missing', '地图组件目录不存在', path=str(root))
        return file_lock(root / '.sc2-mcp' / 'transaction.lock')

    @staticmethod
    def check_cancel(cancel: threading.Event | None):
        if cancel and cancel.is_set():
            raise SC2Error('cancelled', '操作已取消')

    def _folder(self, change_id):
        if not isinstance(change_id, str) or not re.fullmatch(r'[A-Za-z0-9_]+', change_id):
            raise SC2Error('invalid_change_id', '修改记录 ID 不合法')
        return guard_absolute_path(self.state / 'changes' / change_id)

    def _save(self, manifest):
        write_json(self._folder(manifest['id']) / 'manifest.json', manifest)

    def _owner(self, folder):
        path = guard_absolute_path(folder / 'owner.json')
        try:
            record = json.loads(path.read_text('utf-8'))
            root = record['root']
            if (record['id'] != folder.name or record['state_directory'] != str(self.state)
                    or not isinstance(root, str) or not Path(root).is_absolute()
                    or str(Path(root).resolve()) != root):
                raise ValueError('invalid transaction owner')
            return root
        except FileNotFoundError:
            return None  # Legacy manifest.
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SC2Error('invalid_manifest', '归属记录损坏，请核查并从可信备份恢复', path=str(path)) from exc

    def _project_manifests(self, root):
        for path in sorted((self.state / 'changes').glob('*/manifest.json')):
            try:
                manifest = self.read(path.parent.name)
            except SC2Error as exc:
                owner = exc.details.get('verified_owner')
                if exc.code == 'invalid_manifest' and owner and Path(owner) != root:
                    continue
                raise
            if Path(manifest['root']).resolve() == root:
                yield manifest

    @staticmethod
    def _hash(root, relative):
        target = safe_path(root, relative)
        if target.exists() and not target.is_file():
            raise SC2Error('path_collision', '修改目标被目录占用', path=relative)
        return digest(target.read_bytes()) if target.is_file() else None

    def _marker(self, root):
        return guard_absolute_path(root / '.sc2-mcp' / 'active-change.json')

    def _check_pending(self, root, allowed_id=None):
        marker = self._marker(root)
        if marker.exists():
            try:
                pending = json.loads(marker.read_text('utf-8'))
            except (OSError, ValueError) as exc:
                raise SC2Error('recovery_required', '活动事务标记无法读取，先检查恢复记录', path=str(marker)) from exc
            if not isinstance(pending, dict) or (pending.get('id'), pending.get('state_directory')) != (allowed_id, str(self.state)):
                raise SC2Error('recovery_required', '项目有未完成事务，需要先恢复', pending=pending)
        for manifest in self._project_manifests(root):
            if manifest['state'] in _RECOVERABLE and manifest['id'] != allowed_id:
                raise SC2Error('recovery_required', '项目有未完成事务，需要先恢复', change_id=manifest['id'])

    def _activate(self, manifest):
        write_json(self._marker(Path(manifest['root'])), {'id': manifest['id'], 'state_directory': str(self.state)})

    def _clear(self, manifest):
        path = self._marker(Path(manifest['root']))
        if path.exists():
            value = json.loads(path.read_text('utf-8'))
            if value != {'id': manifest['id'], 'state_directory': str(self.state)}:
                raise SC2Error('recovery_required', '活动事务标记属于另一项操作')
            path.unlink()

    def application(self, candidate):
        """Resolve an apply receipt without modifying the candidate or its map."""
        key = candidate.get('applied_change_id') or candidate.get('author_applied_change_id')
        if not key:
            return None
        applied = self.read(key)
        if (applied['root'] != candidate['root'] or applied['label'] != 'apply_' + candidate['label']
                or (candidate.get('applied_change_id') and applied.get('candidate_id') != candidate['id'])):
            raise SC2Error('invalid_manifest', '提交记录与候选不匹配', change_id=key)
        return applied

    def completed_application(self, candidate):
        applied = self.application(candidate)
        if applied and applied['state'] in {'committed', 'rolled_back'}:
            return self.describe(applied)
        return None

    def run(self, root: Path, planner: Callable, *, label='edit', validator=None,
            cancel: threading.Event | None = None, preview_only=False, backup_root: Path | None = None,
            candidate_id=None):
        root = guard_absolute_path(Path(root)).resolve()
        if not callable(planner) or (validator is not None and not callable(validator)):
            raise SC2Error('invalid_plan', '修改器和验证器必须可调用')
        if not isinstance(preview_only, bool) or not isinstance(label, str):
            raise SC2Error('invalid_plan', 'preview_only 必须为布尔值，label 必须为字符串')
        for location in (self.state, guard_absolute_path(Path(backup_root)).resolve() if backup_root else None):
            if location is not None and location.is_relative_to(root):
                parts = location.relative_to(root).parts
                if not parts or parts[0].casefold() not in {'.sc2-mcp', '_codex_backups'}:
                    raise SC2Error('invalid_state_location', '事务状态与备份不能写入地图数据目录', path=str(location))
        with self.lock(root):
            self._check_pending(root)
            if candidate_id:
                candidate = self.read(candidate_id)
                if candidate['root'] != str(root) or candidate['state'] != 'prepared':
                    raise SC2Error('invalid_candidate', '候选不属于此项目或状态不正确')
                previous = self.completed_application(candidate)
                if previous:
                    return previous
            self.check_cancel(cancel)
            baseline = snapshot(root)
            raw = planner()
            if not isinstance(raw, dict):
                raise SC2Error('invalid_plan', '修改器必须返回文件修改表')
            changes, names = {}, set()
            for relative, content in raw.items():
                target = safe_path(root, relative)
                if target.exists() and not target.is_file():
                    raise SC2Error('path_collision', '文件修改目标不能是目录', path=relative)
                rel = relative.replace('\\', '/')
                if rel.casefold() in names:
                    raise SC2Error('case_collision', '修改计划含重复或大小写冲突路径', path=rel)
                names.add(rel.casefold())
                if content is not None and not isinstance(content, bytes):
                    raise SC2Error('invalid_plan', '文件内容必须为 bytes 或 None', path=rel)
                if (digest(content) if content is not None else None) != baseline.get(rel):
                    changes[rel] = content
            for rel in names:
                if any('/'.join(rel.split('/')[:index]) in names for index in range(1, len(rel.split('/')))):
                    raise SC2Error('path_collision', '修改计划将同一路径同时作为文件和父目录', path=rel)
            self.check_cancel(cancel)
            if snapshot(root) != baseline:
                raise SC2Error('baseline_conflict', '规划期间地图发生变化，请重新读取')
            if not changes:
                return {'state': 'unchanged', 'files': [], 'validation': {'static': 'not_needed'}}
            try:
                guard_source_changes(root, changes)
            except ValueError as exc:
                raise SC2Error('source_boundary', str(exc)) from exc
            validation = validator(dict(changes)) if validator else {'static': 'not_run'}
            if not isinstance(validation, dict):
                raise SC2Error('invalid_validation', '验证器必须返回结果字典')
            if validation.get('static') in {'failed', 'error'}:
                raise SC2Error('validation_failed', '候选静态验证失败', validation=validation)
            try:
                json.dumps(validation, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise SC2Error('invalid_validation', '验证结果不能序列化') from exc
            self.check_cancel(cancel)
            if snapshot(root) != baseline:
                raise SC2Error('baseline_conflict', '验证期间地图发生变化')
            change_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:12]
            folder = self._folder(change_id)
            folder.mkdir(parents=True, exist_ok=False)
            backup = guard_absolute_path(Path(backup_root) / change_id if backup_root else folder / 'backup')
            entries, diff = [], []
            for rel, content in changes.items():
                self.check_cancel(cancel)
                path = safe_path(root, rel)
                old = path.read_bytes() if rel in baseline else None
                if (digest(old) if old is not None else None) != baseline.get(rel):
                    raise SC2Error('baseline_conflict', '备份期间地图发生变化', path=rel)
                if old is not None:
                    atomic_write(backup / rel, old)
                if content is not None:
                    atomic_write(folder / 'candidate' / rel, content)
                entries.append({'path': rel, 'before': baseline.get(rel),
                                'after': digest(content) if content is not None else None})
                try:
                    old_text, new_text = (old or b'').decode('utf-8'), (content or b'').decode('utf-8')
                    if '\0' in old_text + new_text:
                        raise UnicodeError()
                    diff.extend(_unified_diff(old_text, new_text, 'before/' + rel, 'after/' + rel))
                except UnicodeError:
                    diff.append(f'Binary {rel}: {len(old or b"")} -> {len(content or b"")} bytes\n')
            manifest = {'id': change_id, 'root': str(root), 'label': label, 'state': 'prepared',
                        'backup': str(backup), 'entries': entries, 'validation': validation,
                        'baseline': baseline,
                        'created_at': datetime.now(timezone.utc).isoformat()}
            atomic_write(folder / 'changes.diff', ''.join(diff).encode('utf-8'))
            if candidate_id:
                manifest['candidate_id'] = candidate_id
            write_json(folder / 'owner.json', {'id': change_id, 'root': str(root), 'state_directory': str(self.state)})
            self._save(manifest)
            self.check_cancel(cancel)
            if snapshot(root) != baseline:
                raise SC2Error('baseline_conflict', '备份期间地图发生变化', change_id=change_id)
            if preview_only:
                return self.describe(manifest)
            if candidate_id:
                # Both records must exist before the first source write. A crash
                # before activation leaves only a prepared, unapplied attempt.
                candidate['applied_change_id'] = change_id
                self._save(candidate)
            try:
                self._activate(manifest)
                manifest['state'] = 'committing'
                self._save(manifest)
                for entry in entries:
                    self.check_cancel(cancel)
                    target = safe_path(root, entry['path'])
                    if self._hash(root, entry['path']) != entry['before']:
                        raise SC2Error('write_conflict', '写入前文件已变化', path=entry['path'])
                    if entry['after'] is None:
                        target.unlink()
                    else:
                        candidate = guard_absolute_path(folder / 'candidate' / entry['path']).read_bytes()
                        if digest(candidate) != entry['after']:
                            raise SC2Error('candidate_corrupt', '候选文件指纹不符', path=entry['path'])
                        if self._hash(root, entry['path']) != entry['before']:
                            raise SC2Error('write_conflict', '提交前文件已变化', path=entry['path'])
                        atomic_write(target, candidate)
                self.check_cancel(cancel)
                for entry in entries:
                    if self._hash(root, entry['path']) != entry['after']:
                        raise SC2Error('verification_failed', '写入后指纹不符', path=entry['path'])
                manifest['state'] = 'committed'
                self._save(manifest)
                self._clear(manifest)
            except BaseException as exc:
                conflicts = self._restore(manifest)
                manifest.update(state='recovery_conflict' if conflicts else 'reverted', failure=str(exc), conflicts=conflicts)
                self._save(manifest)
                if conflicts:
                    raise SC2Error('recovery_conflict', '操作失败，存在后续修改或备份问题；保留记录等待恢复',
                                   change_id=change_id, conflicts=conflicts) from exc
                self._clear(manifest)
                raise
            return self.describe(manifest)

    def _restore(self, manifest):
        root, backup = Path(manifest['root']), Path(manifest['backup'])
        conflicts = []
        for entry in reversed(manifest['entries']):
            try:
                target = safe_path(root, entry['path'])
                actual = self._hash(root, entry['path'])
                if actual == entry['before']:
                    continue
                if actual != entry['after']:
                    conflicts.append(entry['path'] + ': changed_after_transaction')
                    continue
                data = None
                if entry['before'] is not None:
                    data = guard_absolute_path(backup / entry['path']).read_bytes()
                    if digest(data) != entry['before']:
                        conflicts.append(entry['path'] + ': backup_corrupt')
                        continue
                if self._hash(root, entry['path']) != actual:
                    conflicts.append(entry['path'] + ': changed_during_recovery')
                    continue
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, data)
                if self._hash(root, entry['path']) != entry['before']:
                    conflicts.append(entry['path'] + ': recovery_verification_failed')
            except Exception as exc:
                conflicts.append(entry['path'] + ': ' + str(exc))
        return conflicts

    def read(self, change_id):
        path = guard_absolute_path(self._folder(change_id) / 'manifest.json')
        if not path.is_file():
            raise SC2Error('change_not_found', '修改记录不存在', change_id=change_id)
        owner = self._owner(path.parent)
        try:
            manifest = json.loads(path.read_text('utf-8'))
            if owner and isinstance(manifest, dict) and (
                    ('root' in manifest and manifest['root'] != owner)
                    or ('id' in manifest and manifest['id'] != change_id)):
                raise SC2Error('invalid_manifest', '清单与归属记录矛盾，请从可信备份核对两份记录', path=str(path))
            if (not isinstance(manifest, dict) or manifest.get('id') != change_id or manifest.get('state') not in _STATES
                    or not isinstance(manifest.get('root'), str) or not Path(manifest['root']).is_absolute()
                    or not isinstance(manifest.get('backup'), str) or not Path(manifest['backup']).is_absolute()
                    or not isinstance(manifest.get('entries'), list) or not isinstance(manifest.get('validation'), dict)):
                raise ValueError('invalid manifest fields')
            names = set()
            if 'baseline' in manifest:
                if not isinstance(manifest['baseline'], dict):
                    raise ValueError('invalid baseline')
                for rel, value in manifest['baseline'].items():
                    if normalize_relative_path(rel) != rel or not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
                        raise ValueError('invalid baseline entry')
            for entry in manifest['entries']:
                if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                    raise ValueError('invalid entry')
                rel = entry['path']
                normalize_relative_path(rel)
                if '\\' in rel or rel.casefold() in names:
                    raise ValueError('duplicate or noncanonical entry path')
                names.add(rel.casefold())
                for key in ('before', 'after'):
                    value = entry[key]
                    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value)):
                        raise ValueError('invalid fingerprint')
            return manifest
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SC2Error('invalid_manifest', '事务记录损坏，请保留现场并从可信备份恢复清单',
                           path=str(path), change_id=change_id, verified_owner=owner, error=str(exc)) from exc

    def _rollback_locked(self, manifest):
        root = Path(manifest['root'])
        self._check_pending(root, manifest['id'])
        if manifest['state'] in {'reverted', 'rolled_back'}:
            self._clear(manifest)
            return self.describe(manifest)
        if manifest['state'] not in {'committed', *_RECOVERABLE}:
            if manifest['state'] != 'prepared' or not self._marker(root).exists():
                raise SC2Error('invalid_change_state', '此修改尚未提交')
        for entry in manifest['entries']:
            actual = self._hash(root, entry['path'])
            allowed = [entry['after']] if manifest['state'] == 'committed' else [entry['before'], entry['after']]
            if actual not in allowed:
                raise SC2Error('rollback_conflict', '文件含后续修改，无法直接回滚', path=entry['path'])
            if entry['before'] is not None:
                path = guard_absolute_path(Path(manifest['backup']) / entry['path'])
                if not path.is_file() or digest(path.read_bytes()) != entry['before']:
                    raise SC2Error('backup_corrupt', '备份缺失或指纹不符', path=entry['path'])
        self._activate(manifest)
        manifest['state'] = 'rolling_back'
        self._save(manifest)
        conflicts = self._restore(manifest)
        manifest.update(state='recovery_conflict' if conflicts else 'rolled_back', conflicts=conflicts)
        self._save(manifest)
        if not conflicts:
            self._clear(manifest)
        return self.describe(manifest)

    def rollback(self, change_id, expected_root: Path):
        root = guard_absolute_path(Path(expected_root)).resolve()
        with self.lock(root):
            manifest = self.read(change_id)
            if Path(manifest['root']).resolve() != root:
                raise SC2Error('project_mismatch', '修改记录不属于当前项目')
            return self._rollback_locked(manifest)

    def recover(self, root: Path):
        root = guard_absolute_path(Path(root)).resolve()
        results = []
        with self.lock(root):
            marker = self._marker(root)
            active_id = None
            if marker.exists():
                try:
                    value = json.loads(marker.read_text('utf-8'))
                except (OSError, ValueError) as exc:
                    raise SC2Error('recovery_required', '活动事务标记损坏') from exc
                if not isinstance(value, dict) or value.get('state_directory') != str(self.state):
                    raise SC2Error('recovery_required', '请使用记录所属状态目录恢复事务', pending=value)
                active_id = value.get('id')
                if Path(self.read(active_id)['root']).resolve() != root:
                    raise SC2Error('recovery_required', '活动事务标记与地图不匹配', path=str(marker))
            for manifest in list(self._project_manifests(root)):
                if manifest['id'] == active_id and manifest['state'] in {'committed', 'reverted', 'rolled_back'}:
                    self._clear(manifest)
                    results.append(self.describe(manifest))
                elif manifest['state'] in _RECOVERABLE or manifest['id'] == active_id:
                    results.append(self._rollback_locked(manifest))
        return results

    def describe(self, manifest):
        folder = self._folder(manifest['id'])
        result = {'change_id': manifest['id'], 'state': manifest['state'], 'files': manifest['entries'],
                'backup': manifest['backup'], 'diff': str(folder / 'changes.diff'),
                'candidate': str(folder / 'candidate'), 'validation': manifest['validation'],
                'conflicts': manifest.get('conflicts', [])}
        if manifest.get('candidate_id'):
            result['candidate_id'] = manifest['candidate_id']
        return result
