"""Read dependency evidence from a verified local engine, never execute the PE.

Layout reference: sc2-arcade-watcher/sc2-file-format-docs/archive-system.md,
locale dependency chains. Independently checked against the active local binary
and SC2EditorTool/utils/data/builtin_dependencies.py. Unknown builds fail closed.
Core uses an independent documented SC2 base rule. Table origin and component
path-validation semantics remain separate; XML field merging is not inferred.
"""
import hashlib
import re
import struct
from pathlib import Path

# Only the inspected binary/layout is supported; no guessed offsets across builds.
VERIFIED = {'c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222':
            {'table_offset': 62799664, 'stacking_offset': 62799392, 'row_count': 21}}

# Reviewed code/config loading chains only, keyed by the complete engine hash.
# Optional binary call-chain profiles, independent of the documented Core base rule.
# Never populate these from user manifests or NativeLib existence.
BOOTSTRAP_PROFILES = {}
CORE_BASE_SOURCE = 'https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#core-always-first'
DEPENDENCY_CHAIN_SOURCE = 'https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#modpath-validation-algorithm'


def dependency_chain_rule(engine: dict) -> dict | None:
    """Documented path validation consumes this table beyond locale discovery.

    The table's origin stays visible; this does not fabricate DocumentInfo or
    generalize its built-in paths to arbitrary custom/network dependencies.
    """
    if (engine.get('sha256') not in VERIFIED
            or engine.get('table_offset') != VERIFIED[engine['sha256']]['table_offset']):
        return None
    return {'kind': 'sc2_builtin_dependency_chain', 'rule_version': 1,
            'context': 'builtin_component_path_validation', 'source': DEPENDENCY_CHAIN_SOURCE,
            'engine_sha256': engine['sha256'], 'table_offset': engine['table_offset'],
            'table_sha256': '2402c499fb3fde217e8ba8dff80fb4a0c1a0bf48613e95a42021c9333743f4ce',
            'configuration_registration': {'offset': 20772726, 'length': 31,
                'sha256': 'd0316c6cd52e683149b6df3790432cf13ff3990fe2174518dacb10213b10e750'},
            'excluded_components': ['mods/' + n + '.sc2mod' for n in
                                    ('libertymulti', 'swarmmulti', 'voidmulti', 'balancemulti')]}

# Registration evidence only: these paths are not an active component load list.
CATALOG_REGISTRATIONS = {
    'c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222': {
        'table': {'offset': 62494528, 'length': 2640,
                  'sha256': '43e9c195c166e1d6b6ff8faa4a51a79d6e2ef9a603e92b0e183f03dbd9096a50'},
        'xrefs': [
            {'offset': 1958802, 'length': 7, 'sha256': 'df2804fb8c03811c8ea339e6110344f1761c5d9b6e5b148455d9b4cf0a809de5'},
            {'offset': 14245900, 'length': 7, 'sha256': 'f7757886aad543ec30e6d9199f0edea662893190ab5634b798c23e196f139705'}]}}

CATALOG_SOURCE_COLLECTION = {
    'c68202849f8e64ed20d15bea0fb89f2c5b94028d075d9848e124a8264d130222': [
        {'offset': 1958788, 'length': 924, 'sha256': 'a43f7b14752ef6de868e16ab4c3bd7d8d7fd69ad37c8ee6edae712cbd437101d'},
        {'offset': 14240336, 'length': 690, 'sha256': '1ee553a2f9fce4457e58323c412516f60167040e1171002968df968fbe6f11e4'},
        {'offset': 14245536, 'length': 443, 'sha256': 'e18401de72d6342f697a06caa21134d3a02de0db3cf9f205c6131498447b3040'},
        {'offset': 14251168, 'length': 69, 'sha256': 'ae75d8f6a7576dad5fa5130af1dcbd6e6444baec3712d8735c3b09651535318d'},
        {'offset': 14252128, 'length': 45, 'sha256': '8e58c4d966686e80c8df3181ac459684c894c5217dc7cda93634d1ac8e820244'}]}
STANDARD_SPACES_SOURCE = 'https://sc2mapster.github.io/mkdocs/setup/#41-basesc2datagamedata'


def parse_catalog_registration(blob: bytes, profile: dict) -> list[str]:
    """Verify a bounded x64 path registry; no loading/override inference."""
    if len(blob) < 64 or blob[:2] != b'MZ':
        raise ValueError('Invalid catalog registration PE')
    pe = struct.unpack_from('<I', blob, 60)[0]
    if blob[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', blob, pe + 24)[0] != 0x20b:
        raise ValueError('Unsupported catalog registration PE')
    base = struct.unpack_from('<Q', blob, pe + 48)[0]
    count, size = struct.unpack_from('<H', blob, pe + 6)[0], struct.unpack_from('<H', blob, pe + 20)[0]
    if not 1 <= count <= 96:
        raise ValueError('Invalid catalog registration sections')
    sections = [struct.unpack_from('<IIII', blob, pe + 24 + size + i * 40 + 8) for i in range(count)]
    if any(raw + length > len(blob) for _, _, length, raw in sections):
        raise ValueError('Truncated catalog registration section')
    for loc in [profile['table'], *profile['xrefs']]:
        start, length = loc['offset'], loc['length']
        if start < 0 or length <= 0 or start + length > len(blob) or hashlib.sha256(blob[start:start + length]).hexdigest() != loc['sha256']:
            raise ValueError('Catalog registration evidence changed')
    table = profile['table']
    if table['length'] % 24:
        raise ValueError('Invalid catalog registration stride')
    paths = []
    for at in range(table['offset'], table['offset'] + table['length'], 24):
        pointer, length, a, b, c = struct.unpack_from('<QIIII', blob, at)
        if (a, b, c) != (0xffffffff,) * 3 or not 1 <= length < 260:
            raise ValueError('Invalid catalog registration row')
        rva = pointer - base
        raw = next((offset + rva - virtual for _, virtual, size, offset in sections
                    if virtual <= rva and rva + length + 1 <= virtual + size), None)
        if raw is None or blob[raw + length] != 0:
            raise ValueError('Invalid catalog registration pointer')
        name = blob[raw:raw + length].decode('ascii')
        if not re.fullmatch(r'GameData/[A-Za-z0-9_]+\.(?:xml|txt)', name) or name.lower() in paths:
            raise ValueError('Invalid/duplicate catalog registration path')
        paths.append(name.lower())
    return paths


def catalog_registration(install: Path, info: dict, engine: dict) -> dict | None:
    profile = CATALOG_REGISTRATIONS.get(engine.get('sha256'))
    if profile is None:
        return None
    path = install / 'Versions' / ('Base' + info['version'].rsplit('.', 1)[-1]) / 'SC2_x64.exe'
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != engine['sha256']:
        raise ValueError('Catalog registration engine changed')
    paths = parse_catalog_registration(blob, profile)
    collection = CATALOG_SOURCE_COLLECTION.get(engine['sha256'], [])
    for loc in collection:
        if hashlib.sha256(blob[loc['offset']:loc['offset'] + loc['length']]).hexdigest() != loc['sha256']:
            raise ValueError('Catalog source collection evidence changed')
    return {'kind': 'engine_catalog_registration', 'context': 'catalog_registration',
            'engine_sha256': engine['sha256'], 'build_key': info['build_key'],
            'source': str(path.resolve()), 'activity': 'unconfirmed', **profile,
            'source_scope': 'confirmed' if collection else 'unconfirmed',
            'collection_evidence': collection, 'standard_space_contract': STANDARD_SPACES_SOURCE,
            'file_merge_order': 'unconfirmed',
            'catalogs': ['base.sc2data/' + p for p in paths if p.endswith('.xml')],
            'auxiliary': [p for p in paths if not p.endswith('.xml')]}


def bootstrap_registry(install: Path, info: dict, engine: dict) -> dict | None:
    """Revalidate a reviewed, build/context-bound bootstrap profile, if available."""
    profile = BOOTSTRAP_PROFILES.get(engine.get('sha256'))
    if profile is None:
        # Core is SC2's built-in base, not an optional DocumentInfo dependency.
        # Binding a known engine scopes the contract; it does not claim a new
        # binary call-chain discovery or fabricate instruction locations.
        if engine.get('sha256') not in VERIFIED or engine.get('version') != info.get('version'):
            return None
        return {'kind': 'sc2_core_base', 'rule_version': 1, 'source': CORE_BASE_SOURCE,
                'engine_sha256': engine['sha256'], 'build_key': info['build_key'],
                'version': info['version'], 'context': 'component_dependencies',
                'order': 'before_component_dependencies', 'roots': ['mods/core.sc2mod'],
                'dependencies': {'mods/core.sc2mod': []},
                'review': 'Documented SC2 implicit base; user-confirmed architecture'}
    path = install / 'Versions' / ('Base' + info['version'].rsplit('.', 1)[-1]) / 'SC2_x64.exe'
    blob = path.read_bytes()
    if (hashlib.sha256(blob).hexdigest() != engine['sha256']
            or profile['build_key'] != info['build_key'] or profile['version'] != info['version']
            or profile['context'] != 'component_dependencies'
            or profile['order'] != 'before_component_dependencies'
            or not profile['review'] or not profile['locations'] or not profile['roots']):
        raise ValueError('Core/bootstrap evidence does not match this build/context')
    for location in profile['locations']:
        start, length = location['offset'], location['length']
        if (start < 0 or length <= 0 or start + length > len(blob)
                or hashlib.sha256(blob[start:start + length]).hexdigest() != location['sha256']):
            raise ValueError('Core/bootstrap source range changed')
    roots = profile['roots']
    if (len(set(roots)) != len(roots) or any(not re.fullmatch(r'mods/[a-z0-9_/]+\.sc2mod', r) for r in roots)
            or set(profile['dependencies']) != set(roots)
            or any(not isinstance(v, list) or any(p not in roots[:roots.index(r)] for p in v)
                   for r, v in profile['dependencies'].items())):
        raise ValueError('Invalid bootstrap roots')
    return {'kind': 'engine_bootstrap', 'engine_sha256': engine['sha256'],
            'build_key': info['build_key'], 'source': str(path.resolve()), **profile}


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
