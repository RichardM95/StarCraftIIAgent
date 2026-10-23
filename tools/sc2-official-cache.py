#!/usr/bin/env python3
"""Probe local CASC or preview/publish an official dependency snapshot."""
import argparse
import json
import sys
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_casc import CascProcess
from sc2_official import identity, default_cache, probe, snapshot, publish_snapshot
from sc2_paths import load_project_config, resolve_configured_path, find_project_mods
from sc2_dependencies import resolve_dependency_root

from sc2_i18n import UIArgumentParser, run_cli

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    p = UIArgumentParser(description=__doc__)
    p.add_argument('command', choices=('probe', 'sync'))
    p.add_argument('--sc2-install-dir', type=Path)
    p.add_argument('--casc-dll', type=Path, required=True)
    p.add_argument('--target', type=Path)
    p.add_argument('--mods-dir')
    p.add_argument('--official-cache', type=Path)
    p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--allow-partial', action='store_true', help='Extract/publish an explicitly incomplete research cache; never certifies loading')
    args = p.parse_args(argv)
    try:
        config = load_project_config(ROOT)
        install = args.sc2_install_dir
        if install is None:
            value = config.get('paths', {}).get('sc2_install_dir')
            if not value:
                raise ValueError('Pass --sc2-install-dir or configure an installation')
            install = resolve_configured_path(ROOT, value)
        install = install.resolve()
        if (args.apply or args.allow_partial) and args.command != 'sync':
            raise ValueError('--apply and --allow-partial are only supported by sync')
        result = probe(install, args.casc_dll.resolve(), args.timeout)
        if result['status'] != 'read_verified' or args.command == 'probe':
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return int(result['status'] != 'read_verified')
        targets = find_project_mods(ROOT, str(args.target) if args.target else None, config=config)
        if not targets:
            raise ValueError('No target; pass --target')
        mods = resolve_dependency_root(ROOT, targets[0], config, args.mods_dir)
        if mods.parent.resolve() != install:
            raise ValueError('Dependency installation differs from --sc2-install-dir')
        with CascProcess(args.casc_dll.resolve(), install, result['encoding'], args.timeout) as reader:
            contents, files = snapshot(reader, targets[0], mods, allow_partial=args.allow_partial)
        destination = args.official_cache or default_cache(install)
        if not args.official_cache and contents['status'] == 'partial' and args.allow_partial:
            destination = destination.with_name(destination.name + '-partial')
        summary = {**contents, 'identity': result['identity'], 'destination': str(destination),
                   'probe': result, 'files': len(files), 'bytes': sum(map(len, files.values())), 'applied': False}
        if args.apply and contents['problems'] and not args.allow_partial:
            summary['apply_blocked'] = 'Incomplete metadata; previous cache preserved'
        elif args.apply:
            publish_snapshot(destination, result['identity'], args.casc_dll, contents, files, allow_partial=args.allow_partial)
            summary['applied'] = True
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return int(bool(contents['problems']))
    except (OSError, ValueError, ET.ParseError, struct.error, RuntimeError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(run_cli(main))
