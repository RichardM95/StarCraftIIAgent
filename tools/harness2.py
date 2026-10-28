"""Run the project-local Harness2 installation in Linux or WSL."""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

from sc2_i18n import UIArgumentParser, run_cli

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'integrations/harness2'
MODULES = {
    'demo': 'harness2.cli.demo',
    'run': 'harness2.cli.run_sweep',
    'setup': 'harness2.cli.setup',
    'check': 'harness2.cli.check',
    'judge': 'harness2.cli.judge',
    'report': 'harness2.cli.report',
    'bridge': 'harness2.cli.bridge',
    'test': 'unittest',
    'codex-configure': None,
    'codex-probe': None,
    'sc2-optimize': None,
    'sc2-finalize': None,
    'sc2-apply': None,
    'sc2-restore': None,
}


def linux_path(path: Path) -> str:
    if os.name != 'nt':
        return str(path)
    return str(PurePosixPath('/mnt', path.drive[0].lower(), *path.parts[1:]))


def main() -> int:
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument('--distro', default='Ubuntu-22.04', help='WSL distribution')
    parser.add_argument('command', choices=MODULES)
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help='Arguments passed to upstream')
    args = parser.parse_args()
    arguments = args.arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    if args.command in ('codex-configure', 'codex-probe'):
        import json
        from harness2_codex import configure, invoke
        if arguments:
            parser.error('This command does not accept additional arguments.')
        result = configure() if args.command == 'codex-configure' else invoke(
            'Return answer exactly HARNESS2_CODEX_CONNECTED and an empty files array. Do not use any tools.', label='connectivity')[0]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    python = SOURCE / '.venv-linux/bin/python'
    if not (SOURCE / '.venv-linux/pyvenv.cfg').is_file():
        parser.error('Harness2 Linux environment is missing; see wiki/guides/harness2.md')
    if args.command == 'demo' and not any(a == '--output' or a.startswith('--output=') for a in arguments):
        arguments = ['--output', linux_path(ROOT / '.runtime/harness2/demo'), *arguments]
    if args.command == 'test':
        arguments = ['discover', '-s', 'tests', '-p', 'test_*.py', *arguments]
    if args.command.startswith('sc2-'):
        converted = []
        value_for = None
        for item in arguments:
            if item.startswith('--batch='):
                converted.append('--batch=' + linux_path(Path(item.split('=', 1)[1]).resolve()))
            elif item.startswith('--skill=') or item.startswith('-') and item not in ('--skill', '--batch'):
                converted.append(item)
            elif item in ('--skill', '--batch'):
                value_for = item
                converted.append(item)
            elif value_for == '--skill':
                converted.append(item)
                value_for = None
            else:
                converted.append(linux_path(Path(item).resolve()))
                value_for = None
        command = [linux_path(python), linux_path(ROOT / 'tools/harness2_sc2.py'), args.command[4:], *converted]
    else:
        command = [linux_path(python), '-m', MODULES[args.command], *arguments]
    if os.name == 'nt':
        command = ['wsl', '-d', args.distro, '--cd', linux_path(SOURCE), '--exec',
                   '/usr/bin/env', 'PYTHONUTF8=1',
                   'HARNESS2_RUNS_DIR=' + linux_path(ROOT / '.runtime/harness2/runs'), *command]
    return subprocess.call(command, cwd=SOURCE, env={**os.environ, 'PYTHONUTF8': '1',
        'HARNESS2_RUNS_DIR': os.environ.get('HARNESS2_RUNS_DIR', str(ROOT / '.runtime/harness2/runs'))})


if __name__ == '__main__':
    sys.exit(run_cli(main))
