#!/usr/bin/env python3
"""Audit component-map dependency metadata; optionally replace one legacy mod.

Only H2CS v8 headers with a fully framed dependency/localization block are
supported. Other header fields and localized records are preserved byte-for-byte.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from sc2_dependencies import find_info_component, extract_dependency_refs

OLD = 'LegacyofthePurifiers.SC2Mod'
NEW = 'AeonOfIhanrii.SC2Mod'


def parse_header(data):
    if len(data) < 52 or data[:8] != b'H2CS\x08\0\0\0':
        raise ValueError('unsupported DocumentHeader format')
    count = struct.unpack_from('<I', data, 44)[0]
    if count > 256:
        raise ValueError('invalid dependency count')
    offset, dependencies = 48, []
    for _ in range(count):
        end = data.index(b'\0', offset)
        value = data[offset:end].decode('utf-8')
        if not value.startswith(('file:', 'bnet:')):
            raise ValueError('invalid dependency record')
        dependencies.append(value)
        offset = end + 1
    tail = offset
    records = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    for _ in range(records):
        length = struct.unpack_from('<H', data, offset)[0]
        offset += 2 + length + 4  # key bytes, then four-byte locale
        length = struct.unpack_from('<H', data, offset)[0]
        offset += 2 + length
        if offset > len(data):
            raise ValueError('truncated localized record')
    if offset != len(data):
        raise ValueError('unexpected DocumentHeader trailing bytes')
    return dependencies, tail


def build_header(data, values, tail):
    return (data[:44] + struct.pack('<I', len(values))
            + b''.join(v.encode('utf-8') + b'\0' for v in values) + data[tail:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    if args.apply and args.backup_dir is None:
        parser.error('--apply requires --backup-dir')
    rows, edits, errors = [], [], []
    for root in args.roots:
        if not root.is_dir():
            errors.append(f'missing root: {root}')
            continue
        for map_dir in sorted(root.rglob('*.SC2Map')):
            try:
                info, problems = find_info_component(map_dir)
                if problems:
                    raise ValueError('; '.join(problems))
                source = info.read_bytes()
                xml = ET.fromstring(source)
                values = [v.text.strip() for v in xml.findall('./Dependencies/Value')]
                header_path = map_dir / 'DocumentHeader'
                header = header_path.read_bytes()
                refs, tail = parse_header(header)
                if build_header(header, refs, tail) != header:
                    raise ValueError('header roundtrip differs')
                intended = [v.replace(OLD, NEW) for v in values]
                # Refuse unrelated disagreements instead of guessing dependencies.
                if [v.replace(OLD, NEW) for v in refs] != intended:
                    raise ValueError('unrelated dependency disagreement')
                for value in intended:
                    for ref in extract_dependency_refs(value):
                        # Blizzard's prologue mod is supplied by game archives;
                        # it need not be an unpacked Components directory.
                        bundled = ref['file_path'].casefold() == 'mods/voidprologue.sc2mod'
                        if ref['is_local_mod'] and not ref['is_network'] and not bundled:
                            target = root.parent.parent.parent / ref['file_path']
                            if not target.is_dir():
                                raise ValueError(f'missing local dependency: {target}')
                row = dict(map=str(map_dir), info_dependencies=values,
                           header_dependencies=refs, intended_dependencies=intended)
                rows.append(row)
                if source.count(OLD.encode()) != sum(OLD in v for v in values):
                    raise ValueError('legacy name outside info dependency values')
                if source != source.replace(OLD.encode(), NEW.encode()):
                    edits.append((info, source, source.replace(OLD.encode(), NEW.encode()), root))
                if refs != intended:
                    updated = build_header(header, intended, tail)
                    parsed, new_tail = parse_header(updated)
                    if parsed != intended or updated[new_tail:] != header[tail:]:
                        raise ValueError('updated header verification failed')
                    edits.append((header_path, header, updated, root))
            except (ValueError, OSError, ET.ParseError, struct.error) as exc:
                errors.append(f'{map_dir}: {exc}')
    changes = []
    if args.apply and not errors:
        for path, before, after, root in edits:
            backup = args.backup_dir / root.name / path.relative_to(root)
            if path.read_bytes() != before or backup.exists():
                raise ValueError(f'source changed or backup already exists: {path}')
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(before)
            path.write_bytes(after)
            if path.read_bytes() != after:
                raise ValueError(f'write verification failed: {path}')
            changes.append(dict(path=str(path), backup=str(backup),
                                before_sha256=hashlib.sha256(before).hexdigest(),
                                after_sha256=hashlib.sha256(after).hexdigest()))
    report = dict(maps_checked=len(rows), pending_files=len(edits), errors=errors,
                  applied=changes, maps=rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'maps'}, ensure_ascii=True))
    return 1 if errors or (edits and not args.apply) else 0


if __name__ == '__main__':
    raise SystemExit(main())
