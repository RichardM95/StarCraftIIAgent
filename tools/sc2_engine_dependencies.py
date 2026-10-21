"""Read dependency evidence from a verified local engine, never execute the PE.

Layout reference: sc2-arcade-watcher/sc2-file-format-docs/archive-system.md,
locale dependency chains. Independently checked against the active local binary
and SC2EditorTool/utils/data/builtin_dependencies.py. Unknown builds fail closed.
This table does NOT establish Core/bootstrap loading.
"""
import hashlib
import re
import struct
from pathlib import Path

# Only the inspected binary/layout is supported; no guessed offsets across builds.
VERIFIED = {'c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222':
            {'table_offset': 62799664, 'stacking_offset': 62799392, 'row_count': 21}}


def parse_table(blob: bytes, offset: int, stacking: int, row_count: int) -> dict:
    if blob[:2] != b'MZ' or len(blob) < 64:
        raise ValueError('Invalid engine PE')
    pe = struct.unpack_from('<I', blob, 60)[0]
    if blob[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', blob, pe + 24)[0] != 0x20b:
        raise ValueError('Unsupported engine PE')
    base = struct.unpack_from('<Q', blob, pe + 48)[0]
    count, size = struct.unpack_from('<H', blob, pe + 6)[0], struct.unpack_from('<H', blob, pe + 20)[0]
    if not 1 <= count <= 96:
        raise ValueError('Invalid engine sections')
    sections = [struct.unpack_from('<IIII', blob, pe + 24 + size + i * 40 + 8) for i in range(count)]
    if any(raw + length > len(blob) for _, _, length, raw in sections):
        raise ValueError('Truncated engine section')
    def name(pointer):
        for _, rva, length, raw in sections:
            at = pointer - base - rva + raw
            if raw <= at < raw + length:
                end = blob.find(b'\0', at, min(at + 260, raw + length))
                text = blob[at:end].decode('ascii') if end >= at else ''
                if re.fullmatch(r'(?:Mods|Campaigns)[/\\][A-Za-z0-9_/\\]+\.SC2(?:Mod|Campaign)', text):
                    return text.replace('\\', '/').lower()
        return None
    rows, evidence = {}, {}
    if not 10 <= row_count <= 64:
        raise ValueError('Unsupported dependency row count')
    for i in range(row_count):
        at = offset + i * 40
        values = struct.unpack_from('<5Q', blob, at)
        own = name(values[0])
        if not own:
            raise ValueError('Truncated dependency rows')
        parents = [name(p) for p in values[1:] if p]
        if own in rows or any(p not in rows for p in parents):
            raise ValueError('Invalid dependency table ordering/pointer')
        if any(values[j] == 0 and values[j + 1] != 0 for j in range(1, 4)):
            raise ValueError('Invalid dependency table termination')
        rows[own], evidence[own] = parents, at
    if len(rows) < 10 or 'campaigns/void.sc2campaign' not in rows:
        raise ValueError('Incomplete engine dependency table')
    pairs = [struct.unpack_from('<2Q', blob, stacking + i * 16) for i in range(4)]
    multi = [name(p) for p, _ in pairs]
    if (multi != ['mods/libertymulti.sc2mod', 'mods/swarmmulti.sc2mod',
                  'mods/voidmulti.sc2mod', 'mods/balancemulti.sc2mod']
            or [flag for _, flag in pairs] != [0, 1, 1, 1]):
        raise ValueError('Unsupported multiplayer stacking table')
    for parent, child in zip(multi, multi[1:]):
        rows[child] = list(dict.fromkeys([parent, *rows[child]]))
    return {'dependencies': rows, 'rows': evidence, 'table_offset': offset,
            'stacking_offset': stacking, 'row_count': row_count}


def engine_registry(install: Path, version: str) -> dict:
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version):
        raise ValueError('Unrecognized engine version')
    path = install / 'Versions' / ('Base' + version.rsplit('.', 1)[-1]) / 'SC2_x64.exe'
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('Oversized engine')
    blob = path.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    if sha not in VERIFIED:
        raise ValueError('Engine dependency layout has not been verified for this binary')
    return {**parse_table(blob, **{'offset': VERIFIED[sha]['table_offset'],
                                 'stacking': VERIFIED[sha]['stacking_offset'],
                                 'row_count': VERIFIED[sha]['row_count']}),
            'path': str(path.resolve()), 'sha256': sha, 'version': version}
