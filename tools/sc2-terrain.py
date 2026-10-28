#!/usr/bin/env python3
"""SC2 Components terrain inspection, experimental editing and Editor evidence."""
from __future__ import annotations

import json
import math
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_components import close_components, component_path, parse_xml
from sc2_dependencies import build_dependency_graph, dependency_state
from sc2_i18n import UIArgumentParser, run_cli
from sc2_publication import publish_component, staged_directory
from sc2_terrain import (CellAttribute, Foliage, Grid, HardTiles, LightingMap, MapInfo, Masks, SyncTextures, VertexColors,
                         TERRAIN_FILES, TerrainMap, Water, number, sha, terrain_difference, object_contract)
from sc2_terrain_capabilities import capabilities
from sc2_terrain_ops import selected
from sc2_terrain_preview import render
from sc2_terrain_work import (REPO, apply_plan, compare, files, fingerprint,
                              history_move, inventory_files, make_plan)


def artifact_path(path, suffix=None):
    path = Path(path).resolve()
    if not path.is_relative_to(REPO) or any(p.suffix.casefold() == '.sc2map' for p in (path, *path.parents)):
        raise ValueError('Reports must be inside the workspace, outside map component directories')
    if 'publish' in {p.casefold() for p in path.parts}:
        raise ValueError('Reports must not target publish/')
    if suffix and path.suffix.casefold() != suffix:
        raise ValueError('Expected output suffix ' + suffix)
    if path.exists():
        raise FileExistsError('Output already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_result(result, output=None):
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if output:
        path = artifact_path(output, '.json')
        with path.open('x', encoding='utf-8') as stream:
            stream.write(text + '\n')
        print(json.dumps({'output': str(path)}, ensure_ascii=False))
    else:
        print(text)


def audit(path):
    terrain = TerrainMap(path)
    readers = {'t3Water': Water, 't3FluffDoodad': Foliage, 't3HardTile': HardTiles,
               't3TextureMasks': Masks, 't3SyncTextureInfo': SyncTextures, 'MapInfo': MapInfo,
               't3VertCol': VertexColors}
    readers.update({p.name: CellAttribute for p in terrain.path.glob('CellAttribute_*')})
    if (terrain.path / 'LightingMap.tga').exists():
        readers['LightingMap.tga'] = LightingMap
    results = []
    for name, reader in readers.items():
        try:
            data = terrain.read(name)
            if reader(data).encode() != data:
                raise ValueError('Roundtrip changed bytes')
            results.append({'component': name, 'status': 'lossless_roundtrip_passed', 'sha256': sha(data)})
        except (ValueError, OSError) as exc:
            results.append({'component': name, 'status': 'failed', 'error': str(exc)})
    for name, magic, versions, offset, pattern, dims_at in [
        ('t3HeightMap', b'HMAP', {101}, 32, '<HHH', 8),
        ('t3SyncHeightMap', b'SMAP', {102}, 64, '<hH', 8),
        ('t3SyncCliffLevel', b'CLIF', {100}, 32, '<H', 8),
        ('t3CellFlags', b'LFCT', {101, 102}, 32, '<B', 24),
    ]:
        try:
            data = terrain.read(name)
            grid = Grid(data, magic, versions, offset, pattern, dims_at)
            expected = terrain.dim if name in ('t3HeightMap', 't3SyncHeightMap') else tuple(d - 1 for d in terrain.dim)
            if (grid.width, grid.height) != expected or grid.encode() != data:
                raise ValueError('Grid dimensions/roundtrip mismatch')
            results.append({'component': name, 'status': 'lossless_roundtrip_passed', 'sha256': sha(data)})
        except (ValueError, OSError) as exc:
            results.append({'component': name, 'status': 'failed', 'error': str(exc)})
    return {'map': str(Path(path).resolve()), 'components': results,
            'status': 'static validation passed' if all(r['status'] != 'failed' for r in results) else 'failed',
            'editor': 'not_run', 'runtime': 'not_run'}


def scan(root, audit_components=False):
    root = Path(root).resolve()
    maps, errors = [], []
    for path in sorted(root.rglob('*.SC2Map')):
        entry = {'path': str(path), 'relative_path': path.relative_to(root).as_posix(),
                 'container': 'components' if path.is_dir() else 'archive',
                 'provenance': 'user_supplied_modified_campaign_reference'}
        if not (component_path(path)/'t3Terrain.xml').exists():
            entry['has_terrain']=False
            maps.append(entry)
            continue
        try:
            summary = TerrainMap(path).summary()
            entry.update(summary)
            entry['has_terrain'] = True
            if audit_components:
                entry['audit'] = audit(path)
                if entry['audit']['status'] == 'failed':
                    errors.append(str(path))
        except (ValueError, OSError, ET.ParseError) as exc:
            entry['error'] = str(exc)
            errors.append(str(path))
        maps.append(entry)
    return {'root': str(root), 'count': len(maps), 'terrain_count': sum(e.get('has_terrain', False) for e in maps),
            'maps': maps, 'errors': errors}


def experiment(source, output, feature, rect):
    features = {f['id'] for f in capabilities()['features']}
    if feature not in features:
        raise ValueError('Unknown feature ID; use capabilities')
    output = artifact_path(output)
    before_hash = fingerprint(source)
    with staged_directory(output) as stage:
        candidate = stage / output.name
        candidate.mkdir()
        for label in ('before', 'after'):
            dest_root = candidate / label / 'Probe.SC2Map'
            for name, file in files(source):
                dest = dest_root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
            if fingerprint(dest_root) != before_hash:
                raise ValueError('Experiment copy verification failed')
        instructions = {
            'schema_version': 1, 'feature': feature, 'source': str(Path(source).resolve()),
            'baseline_sha256': before_hash, 'rect': rect,
            'before': str(output / 'before/Probe.SC2Map'), 'after': str(output / 'after/Probe.SC2Map'),
            'steps_zh': [
                '关闭项目外部 override；只打开 after/Probe.SC2Map。',
                '第一次不做功能编辑，只保存为 Components，关闭编辑器。',
                '运行 experiment-baseline 记录编辑器空保存规范化结果；before 副本保持只读。',
                f'重新打开 after/Probe.SC2Map，只执行一项操作 {feature}，范围 {rect}；记录所有笔刷/属性参数。',
                '保存为 Components，关闭并重新打开，检查结果；有游戏行为时执行最小运行验证。',
                '运行 experiment-compare，保留操作参数、打开/保存/重开结果、截图与运行步骤。',
            ],
            'editor': 'not_run', 'runtime': 'not_run',
        }
        (candidate / 'experiment.json').write_text(json.dumps(instructions, indent=2, ensure_ascii=False), encoding='utf-8')
        (candidate / 'steps.txt').write_text('\n'.join(instructions['steps_zh']), encoding='utf-8')
        if fingerprint(source) != before_hash:
            raise ValueError('Source changed while making experiment')
        publish_component(candidate, output, fingerprint=fingerprint)
    return {'experiment': str(output), 'feature': feature, 'status': 'awaiting_editor_baseline',
            'after': str(output / 'after/Probe.SC2Map')}


def experiment_baseline(path):
    path = Path(path).resolve()
    if not path.is_relative_to(REPO):
        raise ValueError('Experiment must be inside workspace')
    data = json.loads((path / 'experiment.json').read_text(encoding='utf-8'))
    baseline = path / 'normalized/Probe.SC2Map'
    if baseline.exists():
        raise FileExistsError('Normalized baseline already exists')
    working = path / 'after/Probe.SC2Map'
    old = path / 'before/Probe.SC2Map'
    if fingerprint(old) != data['baseline_sha256']:
        raise ValueError('Original baseline was changed')
    baseline.parent.mkdir()
    current = fingerprint(working)
    for name, file in files(working):
        dest = baseline / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest)
    if fingerprint(working) != current or fingerprint(baseline) != current:
        raise ValueError('Editor baseline changed during capture')
    return {'experiment': str(path), 'normalized_sha256': current,
            'normalization': compare(old, baseline), 'status': 'awaiting_single_editor_operation'}


def main(argv=None):
    parser = UIArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('capabilities', help='Full requirement ledger; incomplete features remain visible')
    p.add_argument('--pending-only', action='store_true')
    p.add_argument('--basic-only', action='store_true', help='Show active basic drawing requirements only')
    p.add_argument('--output', type=Path)
    p = commands.add_parser('scan', help='Index reference maps without modifying them')
    p.add_argument('root', type=Path)
    p.add_argument('--audit', action='store_true')
    p.add_argument('--output', type=Path)
    for cmd in ('inspect', 'audit'):
        p = commands.add_parser(cmd)
        p.add_argument('map', type=Path)
        p.add_argument('--output', type=Path)
    p = commands.add_parser('dependencies', help='Resolve the actual map graph using shared dependency tools')
    p.add_argument('map', type=Path)
    p.add_argument('--mods-dir', required=True, type=Path)
    p.add_argument('--campaigns-dir', type=Path)
    p.add_argument('--official-cache', type=Path)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('select')
    p.add_argument('map', type=Path)
    p.add_argument('--component', choices=('Objects', 'Regions'), default='Objects')
    p.add_argument('--selector', required=True, help='JSON selector')
    p.add_argument('--output', type=Path)
    p = commands.add_parser('object-schema')
    p.add_argument('--kind',required=True,choices=('unit','doodad','point','camera','group'))
    p.add_argument('--output',type=Path)
    p = commands.add_parser('render')
    p.add_argument('map', type=Path)
    p.add_argument('--layers', default='height,water,point,regions,grid')
    p.add_argument('--step', type=int, default=2)
    p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('measure')
    p.add_argument('--from', dest='start', nargs=3, required=True, type=float)
    p.add_argument('--to', dest='end', nargs=3, required=True, type=float)
    p = commands.add_parser('plan', help='Calculate and hash an edit without changing a map')
    p.add_argument('map', type=Path)
    p.add_argument('--operations', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('apply', help='Preview by default; --apply publishes a working copy')
    p.add_argument('plan', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--apply', action='store_true')
    for cmd in ('undo', 'redo'):
        p = commands.add_parser(cmd)
        p.add_argument('map', type=Path)
        p.add_argument('--apply', action='store_true')
    p = commands.add_parser('diff')
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--output', type=Path)
    p = commands.add_parser('experiment')
    p.add_argument('map', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--feature', required=True)
    p.add_argument('--rect', nargs=4, required=True, type=float)
    for cmd in ('experiment-baseline', 'experiment-compare'):
        p = commands.add_parser(cmd)
        p.add_argument('directory', type=Path)
        if cmd.endswith('compare'):
            p.add_argument('--output', type=Path)
            p.add_argument('--allow-unreadable', action='store_true', help='Read-only partial comparison; list every unreadable component')
    args = parser.parse_args(argv)
    try:
        command = args.command
        if command == 'capabilities':
            result = capabilities()
            if args.basic_only:
                result['features'] = [f for f in result['features'] if f['active_requirement']]
            if args.pending_only:
                result['features'] = [f for f in result['features'] if f['implementation'] in ('needs_editor_pair', 'editor_issue_reported')]
        elif command == 'scan':
            result = scan(args.root, args.audit)
        elif command == 'inspect':
            result = TerrainMap(args.map).summary(details=True)
            try:
                info = MapInfo(TerrainMap(args.map).read('MapInfo'))
                result['map_info'] = {'version': info.version, 'size': [info.width, info.height], 'bounds': info.bounds}
            except ValueError as exc:
                result['map_info_error'] = str(exc)
        elif command == 'audit':
            result = audit(args.map)
        elif command == 'dependencies':
            result = dependency_state(build_dependency_graph(args.map, args.mods_dir, campaigns_dir=args.campaigns_dir,
                                                             official_cache=args.official_cache))
        elif command == 'select':
            root = parse_xml(args.map / args.component).getroot()
            result = [{'tag': e.tag, 'attributes': dict(e.attrib), 'xml': ET.tostring(e, encoding='unicode')}
                      for e in selected(root, json.loads(args.selector))]
        elif command == 'object-schema':
            result=object_contract(args.kind)
        elif command == 'render':
            content = render(args.map, args.layers.split(','), args.step)
            path = artifact_path(args.output, '.svg')
            path.write_text(content, encoding='utf-8')
            print(json.dumps({'output': str(path), 'kind': 'diagnostic_preview'}, ensure_ascii=False))
            return 0
        elif command == 'measure':
            start, end = [number(v) for v in args.start], [number(v) for v in args.end]
            result = {'from': start, 'to': end, 'distance': number(math.dist(start, end)), 'xy_distance': number(math.dist(start[:2], end[:2]))}
        elif command == 'plan':
            operations = json.loads(args.operations.read_text(encoding='utf-8-sig'))
            result = make_plan(args.map, operations)
        elif command == 'apply':
            result = apply_plan(json.loads(args.plan.read_text(encoding='utf-8-sig')), args.output, args.apply)
            write_result(result)
            return 0
        elif command in ('undo', 'redo'):
            result = history_move(args.map, redo=command == 'redo', apply=args.apply)
        elif command == 'diff':
            result = compare(args.before, args.after)
        elif command == 'experiment':
            result = experiment(args.map, args.output, args.feature, args.rect)
            write_result(result)
            return 0
        elif command == 'experiment-baseline':
            result = experiment_baseline(args.directory)
        elif command == 'experiment-compare':
            root = args.directory.resolve()
            metadata = json.loads((root / 'experiment.json').read_text(encoding='utf-8'))
            baseline = root / 'normalized/Probe.SC2Map'
            if not baseline.is_dir():
                raise ValueError('Capture the no-operation Editor baseline before comparing a single edit')
            result = compare(baseline, root / 'after/Probe.SC2Map', allow_unreadable=args.allow_unreadable)
            result['terrain_analysis'] = terrain_difference(baseline, root / 'after/Probe.SC2Map')
            result['feature'] = metadata['feature']
            result['editor_acceptance'] = 'requires_explicit_user_open_save_reopen_evidence'
        write_result(result, getattr(args, 'output', None))
        return 1 if isinstance(result, dict) and (result.get('status') == 'failed' or result.get('errors')) else 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        close_components()


if __name__ == '__main__':
    raise SystemExit(run_cli(main))
