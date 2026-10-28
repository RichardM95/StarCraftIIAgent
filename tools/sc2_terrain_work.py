"""Isolated map editing, durable history and Editor-pair comparison."""
from __future__ import annotations

import json
import os
import shutil
import stat
import uuid
from pathlib import Path

from sc2_publication import confined, publish_component, staged_directory
from sc2_terrain import CELL_ATTRIBUTE_FILES, TERRAIN_FILES, TerrainMap, sha
from sc2_terrain_ops import Edit

REPO = Path(__file__).resolve().parent.parent
SKIP = {'.git', '.hg', '.svn', '.sc2editortool'}
WATER_CONFIG = 'Base.SC2Data/GameData/WaterData.xml'


def files(root):
    """Reject links before traversing. Never follow a map's junction into a source."""
    root = Path(root)
    if root.is_symlink() or getattr(root.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
        raise ValueError('Component root must not be a link/junction')
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in list(dirs) + names:
            path = Path(parent) / name
            if name in SKIP:
                if name in dirs:
                    dirs.remove(name)
                continue
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
                raise ValueError('Component contains link/junction: ' + str(path))
        for name in sorted(names):
            if name not in SKIP:
                path = Path(parent) / name
                yield path.relative_to(root).as_posix(), path


def inventory_files(root, *, allow_unreadable=False):
    result = {}
    for name, path in files(root):
        try:
            result[name] = {'size': path.stat().st_size, 'sha256': sha(path.read_bytes())}
        except PermissionError as exc:
            if not allow_unreadable:
                raise
            result[name] = {'size': path.stat().st_size, 'unreadable': str(exc)}
    return result


def fingerprint(root):
    return sha(json.dumps(inventory_files(root), sort_keys=True, separators=(',', ':')).encode())


def different(before, after):
    return [{'file': name, 'before': before.get(name), 'after': after.get(name)}
            for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def output_path(path, source=None):
    original = Path(path).absolute()
    if original.exists():
        confined(original, original.parent)
    path = original.resolve()
    if path.suffix.casefold() != '.sc2map' or 'publish' in {p.casefold() for p in path.parts}:
        raise ValueError('Output must be a .SC2Map outside publish/')
    if not path.is_relative_to(REPO) or path == REPO:
        raise ValueError('Terrain experiments must be inside this workspace')
    if source:
        source = Path(source).resolve()
        if path == source or path.is_relative_to(source) or source.is_relative_to(path):
            raise ValueError('Output and source must be separate, nonoverlapping directories')
    if not path.parent.is_dir():
        raise ValueError('Create the explicit output parent directory first')
    return path


def validate_changed(path, names):
    """Reopen the real staged components. This is static validation only."""
    from sc2_terrain import CellAttribute, Grid, HardTiles, Foliage, LightingMap, MapInfo, Masks, SyncTextures, Water
    import xml.etree.ElementTree as ET
    terrain = TerrainMap(path)
    terrain.height_grid()
    readers = {'t3TextureMasks': Masks, 't3SyncTextureInfo': SyncTextures, 't3Water': Water,
               't3FluffDoodad': Foliage, 't3HardTile': HardTiles, 'MapInfo': MapInfo,
               'LightingMap.tga': LightingMap}
    for name in names:
        data = (path / name).read_bytes()
        if name in readers:
            if readers[name](data).encode() != data:
                raise ValueError('Lossless roundtrip failed: ' + name)
        elif name in CELL_ATTRIBUTE_FILES:
            layer = CellAttribute(data)
            if layer.bits != (terrain.dim[0] - 1) * (terrain.dim[1] - 1) * 8:
                raise ValueError('Cell attribute dimensions do not match terrain')
        elif name in ('Objects', 'Regions', 't3Terrain.xml', WATER_CONFIG):
            ET.fromstring(data)
        elif name == 't3SyncHeightMap':
            Grid(data, b'SMAP', {102}, 64, '<hH')
        elif name == 't3SyncCliffLevel':
            Grid(data, b'CLIF', {100}, 32, '<H')
        elif name == 't3CellFlags':
            Grid(data, b'LFCT', {101,102}, 32, '<B', 24)
        if name in ('Objects',WATER_CONFIG):
            try:
                from lxml import etree
            except ImportError as exc:
                raise ValueError('Changed Objects/catalog files require the existing lxml XSD backend') from exc
            schema_name='Objects.xsd' if name=='Objects' else 'Catalog.xsd'
            try:
                parser=etree.XMLParser(resolve_entities=False,no_network=True)
                schema=etree.XMLSchema(etree.parse(str(Path(__file__).parent/'schemas/sc2-xsd'/schema_name),parser))
                document=etree.fromstring(data,parser)
                if not schema.validate(document):
                    raise ValueError('XSD validation failed for '+name+': '+str(schema.error_log.last_error))
            except etree.LxmlError as exc:
                raise ValueError('XSD validation failed for '+name+': '+str(exc)) from exc


def prepare(source, operations, expected=None):
    source = Path(source).resolve()
    if not source.is_dir() or source.suffix.casefold() != '.sc2map':
        raise ValueError('Editing requires a Components .SC2Map directory')
    current = fingerprint(source)
    if expected is not None and current != expected:
        raise ValueError('Map changed since the plan was created; make a new plan')
    blockers = None
    if metadata_path(source).exists():
        meta, state = load_history(source)
        cursor, revisions = state['cursor'], state['revisions']
        if not isinstance(cursor, int) or not 0 <= cursor <= len(revisions):
            raise ValueError('Invalid terrain history cursor')
        blockers = state.get('initial_blockers')
        if cursor:
            revision_dir = meta / revisions[cursor - 1]
            confined(revision_dir, meta)
            revision = revision_dir / 'record.json'
            confined(revision, revision_dir)
            blockers = json.loads(revision.read_text(encoding='utf-8')).get('blockers_after')
    edit = Edit(source, blockers=blockers)
    changes = edit.apply(operations)
    if fingerprint(source) != current:
        raise ValueError('Source changed during planning')
    return current, edit, changes


def make_plan(source, operations):
    current, edit, changes = prepare(source, operations)
    return {'schema_version': 1, 'source': str(Path(source).resolve()), 'source_sha256': current,
            'operations': operations, 'changed_components': [
                {'file': n, 'before_sha256': sha(original) if (original := edit.original(n)) is not None else None,
                 'after_sha256': sha(b), 'size': len(b)}
                for n, b in sorted(changes.items())], 'notes': edit.notes, 'blockers_after': edit.blockers,
            'validation': {'static': 'pending', 'editor': 'not_run', 'runtime': 'not_run'}}


def metadata_path(target):
    return target.with_name(target.name + '.terrain-work')


def load_history(target):
    meta = metadata_path(target)
    confined(meta, target.parent)
    state = json.loads((meta / 'state.json').read_text(encoding='utf-8'))
    if state.get('tool') != 'sc2-terrain' or state.get('target') != str(target):
        raise ValueError('Unowned terrain history')
    return meta, state


def save_state(meta, state):
    temporary = meta / 'state.pending.json'
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(meta / 'state.json')


def apply_plan(plan, output, apply=False):
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported edit plan version')
    source = Path(plan['source']).resolve()
    target = output_path(output, source if Path(output).resolve() != source else None)
    current, edit, changes = prepare(source, plan['operations'], plan['source_sha256'])
    recorded = {e['file']: e['after_sha256'] for e in plan['changed_components']}
    if recorded != {n: sha(b) for n, b in changes.items()}:
        raise ValueError('Plan/tool result changed; regenerate the plan')
    if plan.get('blockers_after') != edit.blockers:
        raise ValueError('Blocker ownership changed; regenerate the plan')
    existing = target.exists()
    if existing:
        if target != source:
            raise FileExistsError('Output already exists; choose a new copy or plan against the owned working map')
        meta, state = load_history(target)
        if state['fingerprint'] != current:
            raise ValueError('Working map changed outside terrain tools; preserve it and create a new working copy')
    else:
        if target == source:
            raise ValueError('Source missing')
        meta = metadata_path(target)
        if meta.exists():
            raise FileExistsError('History path already exists: ' + str(meta))
        state = {'tool': 'sc2-terrain', 'target': str(target), 'source': str(source),
                 'fingerprint': current, 'cursor': 0, 'revisions': [],
                 'initial_blockers': edit.initial_blockers}
    result = {'output': str(target), 'apply': apply, 'changed_components': sorted(changes),
              'notes': edit.notes, 'status': 'preview', 'editor': 'not_run', 'runtime': 'not_run'}
    if not apply:
        return result
    # A new revision is journaled before publishing the map. If publication fails,
    # unreferenced revision directories are harmless and retained for diagnosis.
    lock = target.with_name('.' + target.name + '.terrain.lock')
    confined(lock, target.parent)
    lock.mkdir()
    try:
        if existing:
            meta, latest = load_history(target)
            if latest != state:
                raise ValueError('History changed concurrently')
        else:
            meta.mkdir()
        revision_id = uuid.uuid4().hex
        revision = meta / revision_id
        revision.mkdir()
        before, after = {}, {}
        for name, data in changes.items():
            original = edit.original(name)
            before[name] = sha(original) if original is not None else None
            after[name] = sha(data)
            for label, payload in [('before', original), ('after', data)]:
                if payload is None:
                    continue
                dest = revision / label / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(payload)
        record = {'id': revision_id, 'before': before, 'after': after, 'plan': plan,
                  'blockers_after': edit.blockers,
                  'before_fingerprint': current}
        (revision / 'record.json').write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
        with staged_directory(target) as stage:
            candidate = stage / target.name
            # files() rejects links; copy2 never gets an unchecked source path.
            for name, file in files(source):
                dest = candidate / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
            if fingerprint(source) != current or fingerprint(candidate) != current:
                raise ValueError('Source changed during staging')
            for name, data in changes.items():
                dest = candidate / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            validate_changed(candidate, changes)
            new_fingerprint = fingerprint(candidate)
            record['after_fingerprint'] = new_fingerprint
            (revision / 'record.json').write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding='utf-8')
            if fingerprint(source) != current:
                raise ValueError('Source changed before publication')
            publish_component(candidate, target, expected=current if existing else None, fingerprint=fingerprint)
        state['revisions'] = state['revisions'][:state['cursor']] + [revision_id]
        state['cursor'] += 1
        state['fingerprint'] = new_fingerprint
        save_state(meta, state)
        result['status'] = 'static validation passed'
        result['history'] = str(meta)
        return result
    finally:
        lock.rmdir()


def history_move(target, redo=False, apply=False):
    target = output_path(target)
    meta, state = load_history(target)
    cursor = state['cursor']
    index = cursor if redo else cursor - 1
    if not 0 <= index < len(state['revisions']):
        raise ValueError('Nothing to redo' if redo else 'Nothing to undo')
    revision = meta / state['revisions'][index]
    confined(revision, meta)
    record = json.loads((revision / 'record.json').read_text(encoding='utf-8'))
    label = 'after' if redo else 'before'
    current = fingerprint(target)
    expected = record['before_fingerprint'] if redo else record['after_fingerprint']
    if current != expected or current != state['fingerprint']:
        raise ValueError('Working map changed outside terrain tools; refusing to overwrite it')
    result = {'output': str(target), 'action': 'redo' if redo else 'undo', 'apply': apply,
              'components': sorted(record[label]), 'status': 'preview'}
    if not apply:
        return result
    lock = target.with_name('.' + target.name + '.terrain.lock')
    confined(lock, target.parent)
    lock.mkdir()
    try:
        if load_history(target)[1] != state:
            raise ValueError('History changed concurrently')
        with staged_directory(target) as stage:
            candidate = stage / target.name
            for name, file in files(target):
                dest = candidate / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
            for name, expected_hash in record[label].items():
                if name not in TERRAIN_FILES + CELL_ATTRIBUTE_FILES + ('Objects', 'Regions', 'MapInfo', WATER_CONFIG):
                    raise ValueError('Invalid history component')
                if expected_hash is None:
                    (candidate / name).unlink(missing_ok=True)
                    continue
                data = (revision / label / name).read_bytes()
                if sha(data) != expected_hash:
                    raise ValueError('History snapshot hash mismatch')
                dest = candidate / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            restored = fingerprint(candidate)
            if restored != record[label + '_fingerprint']:
                raise ValueError('History restoration fingerprint mismatch')
            publish_component(candidate, target, expected=current, fingerprint=fingerprint)
        state['cursor'] += 1 if redo else -1
        state['fingerprint'] = restored
        save_state(meta, state)
        result['status'] = 'static validation passed'
        return result
    finally:
        lock.rmdir()


def compare(before, after, byte_limit=64, *, allow_unreadable=False):
    first = inventory_files(before, allow_unreadable=allow_unreadable)
    second = inventory_files(after, allow_unreadable=allow_unreadable)
    changes = different(first, second)
    unreadable = [str(Path(root) / name) for root, listing in ((before, first), (after, second))
                  for name, entry in listing.items() if 'unreadable' in entry]
    for change in changes:
        name = change['file']
        if any('unreadable' in e for e in (change['before'], change['after']) if e):
            change['comparison'] = 'unreadable'
            continue
        a = (Path(before) / name).read_bytes() if name in first else b''
        b = (Path(after) / name).read_bytes() if name in second else b''
        offsets = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        change['different_common_bytes'] = len(offsets)
        change['first_byte_offsets'] = offsets[:byte_limit]
        change['size_delta'] = len(b) - len(a)
    return {'before': str(Path(before).resolve()), 'after': str(Path(after).resolve()),
            'changed_files': changes, 'unreadable_files': unreadable,
            'status': 'partial_comparison' if unreadable else 'comparison_only'}
