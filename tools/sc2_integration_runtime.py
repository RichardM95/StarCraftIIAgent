"""Shared paths, process locks and source boundaries for SC2 integration adapters."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import time
import subprocess
import sys

WORKSPACE = Path(__file__).resolve().parents[1]


def user_config_path():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.config'))
    return Path(os.environ.get('SC2_AGENT_INTEGRATION_CONFIG', base / 'StarCraftIIAgent/integrations.json'))


def user_config():
    path = user_config_path()
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def runtime_base():
    override = os.environ.get('SC2_AGENT_RUNTIME_ROOT')
    # Keep neutral routing/slot metadata with the tool installation. Windows
    # packaged Python may redirect LOCALAPPDATA writes into a protected cache.
    return Path(override).resolve() if override else WORKSPACE / '.runtime/integrations'


def project_runtime(target):
    target = Path(target).resolve()
    key = hashlib.sha256(str(target).casefold().encode()).hexdigest()[:20]
    if os.environ.get('SC2_AGENT_RUNTIME_ROOT'):
        return runtime_base() / 'projects' / key
    from sc2_paths import project_data_dir, load_project_config, ensure_project_data
    if target.is_relative_to(WORKSPACE):
        data = WORKSPACE.with_name(WORKSPACE.name + '-data') / 'projects' / key
    else:
        data = project_data_dir(WORKSPACE, load_project_config(WORKSPACE), primary=target)
    if data is None:
        raise ValueError('An explicit Components project is required')
    ensure_project_data(data)
    return data / 'runtime/integrations'


def guard_source_changes(root, paths):
    """One policy for transactions, imported candidates and worker integration."""
    root = Path(root).absolute()
    if any(p.casefold() == 'publish' for p in root.parts):
        raise ValueError('publish/ is not an editing target')
    for name in paths:
        relative = str(name).replace('\\', '/')
        parts = relative.split('/')
        if any(p.casefold() == 'publish' for p in parts):
            raise ValueError('publish/ is not an editing target')
        leaf = parts[-1]
        if leaf.casefold() == 'mapscript.galaxy' or re.fullmatch(r'Lib.*\.galaxy', leaf, flags=re.I):
            raise ValueError('Generated Galaxy is read-only; edit the hand-authored source referenced by Triggers: ' + relative)


def run_module(package, module, arguments):
    python = WORKSPACE / 'integrations' / package / '.venv/Scripts/python.exe'
    if not python.is_file():
        print(json.dumps({'ok': False, 'error': {'code': 'runtime_missing',
            'message': 'Run the workspace integration installer first', 'path': str(python)}}))
        return 2
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
           'SC2_AGENT_WORKSPACE': str(WORKSPACE)}
    return subprocess.call(runtime_command(package, module, arguments), env=env)


def runtime_command(package, module, arguments):
    python = user_config().get('base_python', getattr(sys, '_base_executable', sys.executable))
    environment = WORKSPACE / 'integrations' / package / '.venv'
    return [str(python), '-E', '-S', '-X', 'utf8', str(WORKSPACE / 'tools/sc2_integration_bootstrap.py'),
            '--environment', str(environment), '-m', module, *arguments]


@contextmanager
def process_lock(path, *, timeout=0):
    """OS-owned lock: released on crash, with no stale PID file deletion."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'\0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise BlockingIOError('Integration resource is busy: ' + str(path)) from exc
                time.sleep(0.025)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
