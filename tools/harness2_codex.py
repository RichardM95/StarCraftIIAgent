"""Restricted Codex transport for the project-local Harness2 experiments."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime/harness2'
SETTINGS = STATE / 'codex.json'
DISABLED = ('shell_tool', 'hooks', 'plugins', 'apps', 'multi_agent',
            'browser_use', 'in_app_browser', 'computer_use', 'image_generation')


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        for attempt in range(25):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if os.name != 'nt' or attempt == 24:
                    raise
                # Windows readers may briefly deny replacement while sharing reads.
                time.sleep(.01)
    finally:
        temporary.unlink(missing_ok=True)


def configure():
    if os.name != 'nt':
        raise ValueError('Configure from Windows to reuse the installed Codex login.')
    executable = shutil.which('codex')
    if not executable:
        raise ValueError('Codex CLI is not installed.')
    auth_home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).resolve()
    config = tomllib.loads((auth_home / 'config.toml').read_text(encoding='utf-8'))
    if config.get('model_provider') not in (None, 'openai'):
        raise ValueError('A custom provider needs an explicit endpoint configuration; no credentials were copied.')
    login = subprocess.run([executable, 'login', 'status'], capture_output=True, text=True,
                           encoding='utf-8', timeout=30)
    if login.returncode or 'ChatGPT' not in login.stdout + login.stderr:
        raise ValueError('Log in to the installed Codex CLI using ChatGPT first.')
    settings = {
        'schema_version': 1, 'codex': executable, 'python': sys.executable,
        'auth_home': str(auth_home), 'authentication': 'existing_chatgpt_login',
        'endpoint': 'codex_managed_chatgpt', 'model': config.get('model', 'gpt-6.1-sol'),
        'effort': config.get('model_reasoning_effort', 'high'), 'timeout_seconds': 600,
        'sandbox': 'read-only', 'approval_policy': 'on-request',
        'user_config_loaded': False, 'disabled_features': list(DISABLED),
        'cli_version': subprocess.check_output([executable, '--version'], text=True).strip(),
    }
    save(SETTINGS, settings)
    return settings


def winpath(path: Path) -> str:
    value = str(path.resolve())
    if os.name == 'nt':
        return value
    if value.startswith('/mnt/') and len(value) > 7 and value[6] == '/':
        return value[5].upper() + ':\\' + value[7:].replace('/', '\\')
    raise ValueError('Codex contexts must be inside the Windows-mounted project runtime.')


def linuxpath(value: str) -> str:
    if len(value) > 2 and value[1:3] in (':\\', ':/'):
        return '/mnt/' + value[0].lower() + '/' + value[3:].replace('\\', '/')
    raise ValueError('Expected an absolute Windows executable path.')


def settings():
    return json.loads(SETTINGS.read_text(encoding='utf-8'))


def argv(config, directory: Path):
    command = [config['codex'], '--ask-for-approval', 'on-request', 'exec',
               '--ignore-user-config', '--sandbox', 'read-only', '--skip-git-repo-check',
               '--ephemeral', '--json', '--model', config['model'],
               '-c', 'model_reasoning_effort=' + json.dumps(config['effort']),
               '-c', 'web_search="disabled"', '--cd', str(directory),
               '--output-schema', str(directory / 'schema.json'),
               '--output-last-message', str(directory / 'response.json')]
    for feature in DISABLED:
        command += ['--disable', feature]
    return [*command, '-']


@contextmanager
def model_slot():
    """Two OS-owned slots shared by every native experiment process."""
    from sc2_integration_runtime import process_lock
    deadline = time.monotonic() + 600
    with ExitStack() as stack:
        while True:
            for slot in range(2):
                try:
                    stack.enter_context(process_lock(STATE / f'codex-slot-{slot}.lock'))
                except BlockingIOError:
                    continue
                yield
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Both Codex slots remained busy; no model request was submitted.')
            time.sleep(.1)


def native_request(request_path: Path):
    """Native Windows owns the model process, its deadline and process-tree cleanup."""
    from sc2_integration_runtime import process_lock
    directory = request_path.resolve().parent
    if not directory.is_relative_to((STATE / 'codex-calls').resolve()):
        raise ValueError('Request is outside the integration runtime.')
    config = settings()
    request = json.loads(request_path.read_text(encoding='utf-8'))
    effort = request.get('effort', config['effort'])
    if effort not in ('low', 'medium', 'high', 'xhigh'):
        raise ValueError('Unsupported experiment reasoning effort.')
    config['effort'] = effort
    state = directory / 'state.json'
    with process_lock(directory / 'owner.lock', timeout=config['timeout_seconds'] + 45), model_slot():
        if state.exists():
            previous = json.loads(state.read_text(encoding='utf-8'))
            if previous['status'] == 'completed':
                return previous
            # Unknown/failed submissions require inspection, never an automatic resubmit.
            raise RuntimeError('Existing Codex submission: ' + previous['status'])
        save(state, {'status': 'starting', 'model': config['model']})
        env = {**os.environ, 'CODEX_HOME': config['auth_home'], 'PYTHONUTF8': '1'}
        env.pop('CODEX_THREAD_ID', None)
        started = time.monotonic()
        with (directory / 'events.jsonl').open('wb') as stdout, (directory / 'stderr.txt').open('wb') as stderr:
            process = subprocess.Popen(argv(config, directory), stdin=subprocess.PIPE,
                                       stdout=stdout, stderr=stderr, env=env, cwd=directory)
            save(state, {'status': 'running', 'pid': process.pid, 'model': config['model']})
            try:
                process.communicate(request['prompt'].encode('utf-8'), timeout=config['timeout_seconds'])
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                process.wait(timeout=20)
                save(state, {'status': 'timed_out', 'model': config['model']})
                raise RuntimeError('Codex timed out; the owned process tree was stopped.') from None
        response = directory / 'response.json'
        if process.returncode or not response.is_file():
            save(state, {'status': 'failed', 'exit_code': process.returncode, 'model': config['model']})
            raise RuntimeError('Codex failed; inspect ' + str(directory / 'stderr.txt'))
        value = json.loads(response.read_text(encoding='utf-8-sig'))
        if set(value) != {'answer', 'files'} or not isinstance(value['answer'], str) or not isinstance(value['files'], list):
            raise ValueError('Invalid Codex response envelope.')
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.startswith('{')]
        forbidden = [e for e in events if e.get('item', {}).get('type') in
                     ('command_execution', 'mcp_tool_call', 'web_search', 'file_change')]
        if forbidden:
            save(state, {'status': 'rejected_tool_use', 'model': config['model']})
            raise RuntimeError('The model attempted a tool outside the structured-output contract.')
        result = {'status': 'completed', 'model': config['model'], 'wall_seconds': round(time.monotonic() - started, 2),
                  'effort': config['effort'],
                  'sandbox': 'read-only', 'tool_events': 0,
                  'usage': next((e.get('usage') for e in reversed(events) if e.get('type') == 'turn.completed'), None)}
        save(state, result)
        return result


def invoke(prompt: str, allowed_files=(), *, label='call', effort=None):
    config = settings()
    if effort is not None:
        if effort not in ('low', 'medium', 'high', 'xhigh'):
            raise ValueError('Unsupported experiment reasoning effort.')
        config['effort'] = effort
    schema = {'type': 'object', 'additionalProperties': False,
              'required': ['answer', 'files'], 'properties': {
                  'answer': {'type': 'string'}, 'files': {'type': 'array', 'items': {
                      'type': 'object', 'additionalProperties': False, 'required': ['path', 'content'],
                      'properties': {'path': {'type': 'string', 'enum': list(allowed_files) or ['__no_file_changes__']},
                                     'content': {'type': 'string'}}}}}}
    identity = hashlib.sha256(json.dumps([config, prompt, schema], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    directory = STATE / 'codex-calls' / identity
    directory.mkdir(parents=True, exist_ok=True)
    request = directory / 'request.json'
    from sc2_integration_runtime import process_lock
    with process_lock(directory / 'initialize.lock', timeout=10):
        if not (directory / 'schema.json').exists():
            save(directory / 'schema.json', schema)
        if not request.exists():
            save(request, {'prompt': prompt, 'label': label, 'effort': config['effort']})
    state = directory / 'state.json'
    pending = state.exists() and json.loads(state.read_text(encoding='utf-8')).get('status') in ('starting', 'running')
    if not state.exists() or pending:
        if os.name == 'nt':
            native_request(request)
        else:
            subprocess.run([linuxpath(config['python']), winpath(Path(__file__)), '--request', winpath(request)],
                           check=True, timeout=config['timeout_seconds'] + 45)
    record = json.loads(state.read_text(encoding='utf-8'))
    if record['status'] != 'completed':
        raise RuntimeError('Codex submission needs inspection: ' + record['status'])
    value = json.loads((directory / 'response.json').read_text(encoding='utf-8-sig'))
    seen = set()
    for item in value['files']:
        if set(item) != {'path', 'content'} or item['path'] not in allowed_files or item['path'] in seen:
            raise ValueError('Codex proposed a file outside the allowed Skill surface.')
        if not isinstance(item['content'], str) or len(item['content']) > 50_000:
            raise ValueError('Invalid Skill content.')
        seen.add(item['path'])
    return value, directory


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--request':
        native_request(Path(sys.argv[2]))
    elif sys.argv[1:] == ['configure']:
        print(json.dumps(configure(), ensure_ascii=False, indent=2))
    elif sys.argv[1:] == ['probe']:
        print(json.dumps(invoke('Return answer exactly HARNESS2_CODEX_CONNECTED and an empty files array. Do not use any tools.', label='connectivity')[0]))
    else:
        raise SystemExit('Use configure or probe.')
