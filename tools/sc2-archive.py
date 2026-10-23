#!/usr/bin/env python3
"""Read MPQ diagnostics or explicitly convert SC2 archives and Components."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_archive import convert, probe, restore
from sc2_components import close_components

from sc2_i18n import UIArgumentParser, run_cli


def main(argv=None):
    parser = UIArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('probe', help='Read-only container/DLL/component diagnostics')
    p.add_argument('source', type=Path)
    for command in ('pack', 'unpack', 'restore'):
        p = sub.add_parser(command, help='Preview by default; --apply writes verified output')
        p.add_argument('source', type=Path)
        p.add_argument('--apply', action='store_true')
        p.add_argument('--timeout', type=float, default=1800)
        if command != 'restore':
            mode = p.add_mutually_exclusive_group(required=True)
            mode.add_argument('--output', type=Path)
            mode.add_argument('--in-place', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'probe':
            result = probe(args.source)
        elif args.command == 'restore':
            result = restore(args.source, apply=args.apply, timeout=args.timeout)
        else:
            result = convert(args.command, args.source, output=args.output, in_place=args.in_place,
                             apply=args.apply, timeout=args.timeout)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        close_components()


if __name__ == '__main__':
    raise SystemExit(run_cli(main))
