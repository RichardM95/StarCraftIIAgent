"""Content-bound reference results; structural/commit guards always run anew."""
import hashlib
import json
import sys
import time
from pathlib import Path

from .storage import atomic_write, digest, file_lock, guard_absolute_path


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def implementation():
    from .agent_bridge import WORKSPACE
    roots = [Path(__file__).parent, WORKSPACE / 'tools']
    files = [p for root in roots for p in root.rglob('*')
             if p.is_file() and p.suffix in {'.py', '.xsd', '.gz'} and '.venv' not in p.parts]
    return digest(canonical({str(p): digest(p.read_bytes()) for p in sorted(files)}))


def reference_validation(state, record, changes, before, after, compute):
    started = time.monotonic()
    binding = {'version': 1, 'implementation': implementation(), 'python': sys.version,
               'project': (record.get('root') or before['root']), 'profile': record['profile'],
               'before': before['source_context_id'], 'after': after['source_context_id'],
               'changes': {p: digest(v) if v is not None else None for p, v in changes.items()}}
    key = digest(canonical(binding))
    directory = guard_absolute_path(Path(state) / 'reference-receipts')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (key + '.json')
    with file_lock(directory / (key + '.lock')):
        if path.is_file():
            try:
                receipt = json.loads(path.read_text('utf-8'))
                report = receipt['report']
                if (receipt['binding'] == binding and digest(canonical(report)) == receipt['report_sha256']
                        and report['static'] == 'passed' and not report['new_missing']):
                    return {**report, 'reuse': {'hit': True, 'receipt': str(path), 'seconds': time.monotonic()-started}}
            except (OSError, ValueError, KeyError, TypeError):
                pass  # A damaged receipt never waives a fresh validation.
        report = compute()
        if report.get('static') == 'passed' and not report.get('new_missing'):
            atomic_write(path, canonical({'binding': binding, 'report': report,
                                         'report_sha256': digest(canonical(report))}))
        return {**report, 'reuse': {'hit': False, 'receipt': str(path), 'seconds': time.monotonic()-started}}
