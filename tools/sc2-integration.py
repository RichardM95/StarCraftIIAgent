"""Install, configure, diagnose and register the shared local/MCP integration."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from sc2_integration_runtime import WORKSPACE, user_config_path, user_config, runtime_base, process_lock, runtime_command
from sc2_i18n import UIArgumentParser


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(data)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_settings(value):
    atomic(user_config_path(), (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def package_python(name):
    return WORKSPACE / 'integrations' / name / '.venv/Scripts/python.exe'


def configure(args):
    exe = Path(args.harness_exe) if args.harness_exe else None
    if exe is None and os.name == 'nt':
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Uninstall')
        for number in range(winreg.QueryInfoKey(key)[0]):
            with winreg.OpenKey(key, winreg.EnumKey(key, number)) as child:
                try:
                    name = winreg.QueryValueEx(child, 'DisplayName')[0]
                    if 'DeepSeek Harness' in name:
                        exe = Path(winreg.QueryValueEx(child, 'InstallLocation')[0]) / 'DeepSeek Harness.exe'
                        break
                except FileNotFoundError:
                    continue
        key.Close()
    if exe is None or not exe.is_file():
        raise ValueError('DeepSeek Harness not found; pass --harness-exe')
    cli = Path(args.harness_cli) if args.harness_cli else exe.parent / 'resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-desktop-host/lib/cli.js'
    archive = exe.parent / 'resources/app.asar'
    if not cli.is_file() and not archive.is_file():
        raise ValueError('Harness CLI not found; pass --harness-cli')
    settings = user_config()
    settings.update({'schema_version': 1, 'workspace': str(WORKSPACE),
                     'base_python': str(Path(getattr(sys, '_base_executable', sys.executable)).resolve()),
                     'sc2_python': str(package_python('sc2-editor-mcp')),
                     'deepseek_python': str(package_python('deepseek-supervisor'))})
    profile = user_config_path().parent / 'deepseek-base.patch.yml'
    existing = settings.get('deepseek', {})
    credentials = Path(args.credentials_file or existing.get('credential_file', Path.home() / '.dsh/.credentials.yaml')).expanduser().resolve()
    template = (WORKSPACE / 'integrations/deepseek-supervisor/profiles/base.patch.template.yml').read_text('utf-8')
    # YAML paths are quoted, including when the user profile contains punctuation.
    template = template.replace('<DEEPSEEK_CREDENTIALS_FILE>', json.dumps(credentials.as_posix()))
    atomic(profile, template.encode('utf-8'))
    settings['deepseek'] = {**{'provider': 'deepseek-official', 'model': 'deepseek-flash',
        'reasoning_effort': 'high', 'concurrency': 4, 'timeout_seconds': 1200,
        'max_tool_calls': 200, 'max_tokens': 16384}, **existing,
        'harness_exe': str(exe.resolve()), 'harness_cli': str(cli), 'profile_path': str(profile),
        'credential_file': str(credentials)}
    if args.provider_config:
        settings['deepseek']['provider_config'] = str(Path(args.provider_config).expanduser().resolve())
    for field in ('provider', 'model'):
        if getattr(args, field):
            settings['deepseek'][field] = getattr(args, field)
    with process_lock(user_config_path().with_suffix('.lock'), timeout=2):
        save_settings(settings)
    return {'configured': True, 'config': str(user_config_path()), 'credential_contents_read': False}


def install(args):
    if sys.version_info < (3, 12):
        raise ValueError('Python 3.12 or newer is required')
    env = {**os.environ, 'PYTHONUTF8': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    uv = shutil.which('uv')
    for name in ('sc2-editor-mcp', 'deepseek-supervisor'):
        root = WORKSPACE / 'integrations' / name
        python = package_python(name)
        if not python.exists():
            subprocess.run([sys.executable, '-m', 'venv', str(root / '.venv')], env=env, check=True)
        pip = [uv, 'pip', 'install', '--python', str(python)] if uv else [str(python), '-m', 'pip', 'install']
        if args.index_url:
            pip += ['--index-url', args.index_url]
        if args.wheelhouse:
            pip += ['--find-links', str(Path(args.wheelhouse).resolve())]
        if args.offline:
            pip += ['--offline'] if uv else ['--no-index']
        if name == 'sc2-editor-mcp':
            subprocess.run([*pip, '-r', str(root / 'requirements.agent.lock')], env=env, check=True)
        else:
            # The same locked SDK/runtime versions are used by both adapters.
            subprocess.run([*pip, '-r', str(root / 'requirements.agent.lock')], env=env, check=True)
        builds = WORKSPACE / 'temp/integration-editable-builds' / name
        builds.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(python), '-X', 'utf8', '-c',
            'import setuptools.build_meta as b,sys; b.build_editable(sys.argv[1])', str(builds)],
            cwd=root, env=env, check=True)
        wheels = list(builds.glob('*.whl'))
        if len(wheels) != 1:
            raise ValueError('Expected one editable wheel; inspect ' + str(builds))
        subprocess.run([*pip, '--no-deps', str(wheels[0])], env=env, check=True)
    return {'installed': True, 'runtimes': [str(package_python(n)) for n in ('sc2-editor-mcp', 'deepseek-supervisor')]}


def expected_servers():
    env = {'SC2_AGENT_WORKSPACE': str(WORKSPACE), 'PYTHONUTF8': '1',
           'SC2_EDITOR_MCP_PYTHON': str(package_python('sc2-editor-mcp'))}
    sc2 = runtime_command('sc2-editor-mcp', 'sc2_mcp', ['--project-states', '--ui-language', 'zh-CN'])
    ds = runtime_command('deepseek-supervisor', 'supervisor.cli', ['--ui-language', 'zh-CN', 'serve'])
    return {'sc2-editor': {'command': sc2[0],
        'args': sc2[1:],
        'env': env, 'enabled': True, 'startup_timeout_sec': 30, 'tool_timeout_sec': 300},
        'deepseek-supervisor': {'command': ds[0],
        'args': ds[1:],
        'env': env, 'enabled': True, 'startup_timeout_sec': 60, 'tool_timeout_sec': 300}}


def global_skill():
    return '''---
name: sc2-agent-tools
description: Use StarCraftIIAgent local tools and MCP for SC2 map terrain and scene editing, assets, diagnostics, transactional candidates, or bounded SC2 tasks through Harness-configured local and remote models.
---

Read `%LOCALAPPDATA%/StarCraftIIAgent/integrations.json` (or `SC2_AGENT_INTEGRATION_CONFIG`) to locate `workspace`.
Load that workspace's AGENTS.md and skills/sc2-project-entry/SKILL.md. For map terrain, expansion or scene composition, load skills/sc2-terrain-editing/SKILL.md; route mission objects and GUI organization through skills/sc2-map-triggers/SKILL.md. Other shared-tool tasks route through skills/sc2-shared-tools/SKILL.md.
An explicitly supplied map is the terrain target; do not substitute the selected mod. Use only the explicitly selected project; this entry does not change any existing Hub's project ownership.
The workspace maintains the tools and detailed skills. MCP and CLI share their implementation and state.
Automatic model delegation is limited to bounded sub-tasks in authorized SC2 work. Select provider/model through the workspace model registry; other domains need an explicit request.
'''


def register(remove=False):
    import tomlkit
    settings = user_config()
    if not settings or settings.get('workspace') != str(WORKSPACE):
        raise ValueError('Configure this workspace before registering')
    home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    config = home / 'config.toml'
    home.mkdir(parents=True, exist_ok=True)
    expected = expected_servers()
    registration = settings.get('registration', {})
    owned = registration.get('servers', {})
    managed = dict(owned)
    skill = home / 'skills/sc2-agent-tools/SKILL.md'
    text = global_skill().encode('utf-8')
    skill_owned = registration.get('skill_owned', bool(registration.get('skill_sha256')))
    actual_skill_hash = hashlib.sha256(skill.read_bytes()).hexdigest() if skill.exists() else None
    # A changed user skill is never silently overwritten or removed.
    if (skill.exists() and skill.read_bytes() != text and (not remove or skill_owned)
            and not (skill_owned and actual_skill_hash == registration.get('skill_sha256'))):
        raise ValueError('Global skill name is already used by different content: ' + str(skill))
    with process_lock(home / 'sc2-agent-registration.lock', timeout=2):
        before = config.read_bytes() if config.exists() else b''
        parsed = tomlkit.parse(before.decode('utf-8-sig'))
        servers = parsed.setdefault('mcp_servers', tomlkit.table())
        for name, value in expected.items():
            current = servers[name].unwrap() if name in servers else None
            if remove:
                if current is not None and name in owned:
                    if current != owned[name]:
                        raise ValueError('Registered server changed; inspect before removing: ' + name)
                    del servers[name]
            else:
                if current is not None and current != value and current != owned.get(name):
                    raise ValueError('MCP name is already in use: ' + name)
                if current is None or name in owned:
                    managed[name] = value
                servers[name] = value
        after = tomlkit.dumps(parsed).encode('utf-8')
        if before != after:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = home / ('config.toml.sc2-agent-' + stamp + '.bak')
            with backup.open('xb') as stream:
                stream.write(before)
            if (config.read_bytes() if config.exists() else b'') != before:
                raise ValueError('Codex configuration changed concurrently')
            atomic(config, after)
        if remove:
            if skill_owned and registration.get('skill_sha256') == actual_skill_hash and skill.exists():
                skill.unlink()
            settings.pop('registration', None)
        else:
            skill_owned = skill_owned or not skill.exists()
            atomic(skill, text)
            settings['registration'] = {'servers': managed, 'skill_sha256': hashlib.sha256(text).hexdigest(),
                                        'skill_owned': skill_owned}
        save_settings(settings)
    return {'state': 'unregistered' if remove else 'registered', 'config': str(config),
            'changed': before != after, 'current_chat_connection': 'not_verified'}


def stage_registration():
    import tomlkit
    destination = WORKSPACE / 'temp/sc2-global-registration'
    document = tomlkit.document()
    document['mcp_servers'] = expected_servers()
    atomic(destination / 'mcp.toml', tomlkit.dumps(document).encode('utf-8'))
    atomic(destination / 'sc2-agent-tools/SKILL.md', global_skill().encode('utf-8'))
    return {'state': 'ready_for_registration', 'directory': str(destination),
            'command': 'python "' + str(WORKSPACE / 'tools/sc2-integration.py') + '" --ui-language zh-CN register',
            'global_configuration_written': False}


def diagnose():
    results = {}
    for name, module in (('sc2-editor-mcp', 'sc2_mcp.local_cli'), ('deepseek-supervisor', 'supervisor.cli')):
        python = package_python(name)
        if not python.is_file():
            results[name] = {'ok': False, 'error': 'runtime_missing'}
            continue
        command = 'capabilities' if name == 'sc2-editor-mcp' else 'diagnose'
        proc = subprocess.run(runtime_command(name, module, ['--ui-language', 'zh-CN', command]),
                              capture_output=True, text=True, encoding='utf-8', timeout=60)
        results[name] = {'ok': proc.returncode == 0, 'exit_code': proc.returncode}
        if proc.returncode:
            results[name]['diagnostic'] = (proc.stdout + proc.stderr)[-4000:]
    return {'ok': all(v['ok'] for v in results.values()), 'runtimes': results}


def main():
    parser = UIArgumentParser(description='Install, configure, diagnose and register the shared local/MCP integration.')
    commands = parser.add_subparsers(dest='command', required=True)
    installer = commands.add_parser('install')
    installer.add_argument('--index-url')
    installer.add_argument('--wheelhouse', type=Path)
    installer.add_argument('--offline', action='store_true')
    config = commands.add_parser('configure')
    config.add_argument('--harness-exe')
    config.add_argument('--harness-cli')
    config.add_argument('--credentials-file')
    config.add_argument('--provider')
    config.add_argument('--model')
    config.add_argument('--provider-config')
    for name in ('register', 'unregister', 'diagnose', 'stage-registration'):
        commands.add_parser(name)
    smoke = commands.add_parser('smoke')
    smoke.add_argument('--with-deepseek', action='store_true')
    args = parser.parse_args()
    if args.command == 'smoke':
        return subprocess.call(runtime_command('sc2-editor-mcp', 'sc2_integration_smoke',
            ['--with-deepseek'] if args.with_deepseek else []))
    if args.command in ('register', 'unregister', 'stage-registration') and importlib.util.find_spec('tomlkit') is None:
        # Keep the caller's Windows process identity when editing Codex settings.
        # Only the pure-Python TOML library is needed from the isolated runtime.
        sys.path.insert(0, str(package_python('sc2-editor-mcp').parents[1] / 'Lib/site-packages'))
    try:
        result = {'install': lambda: install(args), 'configure': lambda: configure(args),
                  'register': register, 'unregister': lambda: register(True), 'diagnose': diagnose,
                  'stage-registration': stage_registration}[args.command]()
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
        return 1 if result.get('ok') is False else 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'setup_failed', 'message': str(exc)}}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
