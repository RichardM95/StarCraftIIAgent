"""Portable official-data observations, not a substitute for a map's Catalog.

The bundled index carries virtual source names and hashes only. It never opens
an installation, modifies a map, or treats skin display models as Unit IDs.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re

from .errors import SC2Error

INDEX = Path(__file__).with_name('knowledge') / 'official-assets.json.gz'
_TOKEN = re.compile(r'##([A-Za-z_][A-Za-z_0-9]*)##')
_LIMITATIONS = [
    '这是指定官方构建的静态知识快照，不是当前地图已加载的依赖。',
    '模板参数仅作显式字符串替换；数组执行、EffectArray、Actor宏及引擎默认值没有被模拟。',
    '模型路径观察不证明本机资源可读；需用当前 SourceContext 和资源解析工具复核。',
    '未提供编辑器、游戏运行或人工视觉验收。',
]


@lru_cache(maxsize=1)
def _load():
    if not INDEX.is_file():
        raise SC2Error('official_index_missing', '官方资源知识索引未安装。')
    with gzip.open(INDEX, 'rt', encoding='utf-8') as stream:
        data = json.load(stream)
    if data.get('schema') != 'official-assets-1':
        raise SC2Error('official_index_schema', '不支持的官方资源索引版本。')
    return data


def _tables(data):
    return {(r['component'], r['catalog'], r['id']): r for r in data['records']}


def _chain(table, component, catalog, object_id, active=()):
    key = (component, catalog, object_id)
    if key in active:
        return [], [{'code': 'parent_cycle', 'id': object_id}]
    record = table.get(key)
    if record is None:
        core = table.get(('mods/core.sc2mod', catalog, object_id))
        if component != 'mods/core.sc2mod' and core is not None and core['template']:
            definitions, issues = _chain(table, 'mods/core.sc2mod', catalog, object_id, (*active, key))
            return definitions, [*issues, {'code': 'core_template_observation', 'id': object_id,
                                           'map_dependency_status': 'not_checked'}]
        return [], [{'code': 'parent_not_in_component_snapshot', 'catalog': catalog, 'id': object_id}]
    definitions = record['definitions']
    parents = {d['attributes']['parent'] for d in definitions if d['attributes'].get('parent')}
    if len(parents) > 1:
        return definitions, [{'code': 'multiple_parent_declarations', 'id': object_id}]
    parent = next(iter(parents), None)
    inherited, issues = _chain(table, component, catalog, parent, (*active, key)) if parent else ([], [])
    return [*inherited, *definitions], issues


def _context(definitions, object_id):
    tokens = {}
    declared = set()
    for definition in definitions:
        for token in definition['tokens']:
            declared.add(token['id'])
            if 'value' in token:
                tokens[token['id']] = token['value']
        # Token attributes on the most-derived object override template defaults.
        for key, value in definition['attributes'].items():
            if key in declared:
                tokens[key] = value
    tokens['id'] = object_id
    return tokens


def _expand(value, tokens):
    seen = set()
    for _ in range(20):
        if value in seen:
            break
        seen.add(value)
        replaced = _TOKEN.sub(lambda m: tokens.get(m[1], m[0]), value)
        if replaced == value:
            break
        value = replaced
    return value


def _fields(nodes, source, tokens, prefix=''):
    result = []
    for node in nodes:
        tag = node['tag']
        attributes = node['attributes']
        path = f'{prefix}.{tag}' if prefix else tag
        if 'index' in attributes:
            path += '[' + attributes['index'] + ']'
        result.append({'field': path, 'attributes': dict(attributes),
                       'expanded': {k: _expand(v, tokens) for k, v in attributes.items()},
                       'source': source})
        result.extend(_fields(node.get('children', []), source, tokens, path))
    return result


def _observations(table, record):
    definitions, issues = _chain(table, record['component'], record['catalog'], record['id'])
    tokens = _context(definitions, record['id'])
    fields = []
    for definition in definitions:
        fields.extend(_fields(definition['fields'], definition['source'], tokens))
    return definitions, tokens, fields, issues


def _path_rows(fields):
    rows = []
    for item in fields:
        for attr, value in item['expanded'].items():
            if re.search(r'\.(?:m3|m3a|dds|tga|ogg|wav|mp3|flac)(?:$|[; ])', value, re.I):
                rows.append({'field': item['field'], 'attribute': attr, 'reference': value,
                             'source': item['source'], 'unresolved_token': '##' in value})
    model_rows = [i for i, row in enumerate(rows) if row['field'] == 'Model' and row['attribute'] == 'value']
    for i in model_rows:
        rows[i]['overridden_by_later_scalar'] = i != model_rows[-1]
    return rows


def summary():
    data = _load()
    return deepcopy({k: data[k] for k in ('schema', 'build', 'coverage', 'source_files')}) | {
        'limitations': list(_LIMITATIONS), 'static': 'source_hash_verified_snapshot',
        'editor': 'not_tested', 'runtime': 'not_tested', 'visual': 'not_reviewed'}


def search(query='', catalog=None, component=None, offset=0, limit=30, source_context=None):
    data = _load()
    if not isinstance(query, str) or len(query) > 500:
        raise SC2Error('invalid_official_query', '查询必须为不超过500字符的文本。')
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise SC2Error('invalid_range', 'offset需非负，limit范围为1至200。')
    catalogs = data['coverage']['catalogs']
    if catalog is not None and catalog not in catalogs:
        raise SC2Error('invalid_official_catalog', '索引不包含该Catalog。', supported=list(catalogs))
    if component is not None and component not in data['coverage']['components']:
        raise SC2Error('invalid_official_component', '索引不包含该官方组件。')
    words = query.casefold().replace('\\', '/').split()
    matches = []
    for record in data['records']:
        if catalog is not None and record['catalog'] != catalog:
            continue
        if component is not None and record['component'] != component:
            continue
        category_words = {'Skin': '皮肤', 'SkinPack': '皮肤系列包', 'WarChest': '战争宝箱',
                          'WarChestSeason': '战争宝箱赛季', 'Model': '模型', 'Actor': '演员 表现',
                          'Sound': '声音 音效', 'Texture': '贴图 纹理', 'Unit': '单位',
                          'Button': '按钮 图标', 'Light': '光照 灯光', 'Reward': '奖励',
                          'Abil': '能力 技能', 'Behavior': '行为 增益 减益', 'Effect': '效果',
                          'Weapon': '武器', 'Upgrade': '升级 科技', 'Validator': '验证器 条件',
                          'Requirement': '需求 前置', 'Campaign': '战役', 'Terrain': '地形',
                          'TerrainTex': '地形纹理'}
        text = record['search_text'] + ' ' + category_words.get(record['catalog'], '')
        if all(word in text for word in words):
            matches.append(record)
    # An exact ID precedes substring hits; stable order makes pagination useful.
    matches.sort(key=lambda r: (r['id'].casefold() != query.casefold(), r['catalog'], r['id'], r['component']))
    items = [{k: deepcopy(r[k]) for k in ('catalog', 'id', 'class', 'component', 'names', 'template')}
             for r in matches[offset:offset + limit]]
    return {'build': deepcopy(data['build']), 'count': len(matches), 'items': items,
            'next_offset': offset + limit if offset + limit < len(matches) else None,
            'scope': 'bundled_official_snapshot', 'index_status': 'passed',
            'knowledge_status': 'passed' if matches else 'missing',
            'official_source_status': 'bundled_snapshot_readable',
            'asset_readability': 'not_checked',
            'map_dependency_status': ('not_checked' if source_context is None else
                                      _dependency_summary(source_context, {r['component'] for r in matches})),
            'editor': 'not_tested', 'runtime': 'not_tested', 'visual': 'not_reviewed',
            'limitations': list(_LIMITATIONS)}


def explain(catalog, object_id, component=None, source_context=None):
    data = _load()
    candidates = [r for r in data['records'] if r['catalog'] == catalog and r['id'] == object_id
                  and (component is None or r['component'] == component)]
    if not candidates:
        raise SC2Error('official_object_not_indexed', '快照中没有此对象；不能据此断言游戏中不存在。', catalog=catalog, object_id=object_id)
    if len(candidates) > 1:
        raise SC2Error('official_source_ambiguous', '同ID有多个官方组件定义，请明确component；不能当作当前地图合并值。',
                       components=[r['component'] for r in candidates])
    record = candidates[0]
    table = _tables(data)
    definitions, tokens, fields, issues = _observations(table, record)
    replacements = [f for f in fields if f['field'].split('[')[0] == 'ReplacementArray']
    effects = [f for f in fields if f['field'].split('[')[0] == 'EffectArray']
    models = []
    for item in replacements:
        row = item['expanded']
        if row.get('Catalog') != 'Model' or 'To' not in row:
            continue
        target = row['To']
        model = table.get((record['component'], 'Model', target))
        if model is None:
            models.append({'model_id': target, 'status': 'not_in_component_snapshot', 'paths': []})
        else:
            _, _, mf, mi = _observations(table, model)
            paths = _path_rows(mf)
            models.append({'model_id': target, 'status': 'static_path_observations',
                           'paths': paths,
                           'model_path_candidates': [p['reference'] for p in paths if p['field'] == 'Model'
                                                     and not p.get('overridden_by_later_scalar')],
                           'issues': mi})
    unresolved = sorted({v for f in fields for v in f['expanded'].values() if '##' in v})
    used_sources = {d['source'] for d in definitions}
    used_sources.update(n['source'] for n in record['names'])
    used_sources.update(p['source'] for m in models for p in m['paths'])
    return {'build': deepcopy(data['build']), 'catalog': catalog, 'id': object_id,
            'component': record['component'], 'names': deepcopy(record['names']),
            'source_files': deepcopy([s for s in data['source_files'] if s['path'] in used_sources]),
            'template': record['template'], 'definitions': deepcopy(definitions),
            'tokens': tokens, 'field_observations': fields, 'replacement_observations': replacements,
            'effect_observations': effects, 'target_models': models, 'paths': _path_rows(fields),
            'unresolved_tokens': unresolved, 'issues': issues,
            'array_semantics': 'ordered_declarations_only_not_engine_evaluated',
            'index_status': 'passed', 'knowledge_status': 'passed',
            'official_source_status': 'bundled_snapshot_readable',
            'asset_readability': 'not_checked',
            'map_dependency_status': ('not_checked' if source_context is None else
                                      _dependency_summary(source_context, {record['component']})),
            'static': 'source_hash_verified_snapshot',
            'editor': 'not_tested', 'runtime': 'not_tested', 'visual': 'not_reviewed',
            'next_steps': ['用当前地图SourceContext检查Skin/Actor/Model定义及依赖。',
                           '按replacement_observations逐项核对死亡、变形、建造与附属链；EffectArray另行审计。',
                           '用sc2_assets_resolve核验真实资源及M3贴图/动画闭包；不可仅使用预览模型。',
                           '地图改动仍须经过现有候选事务，并分别完成编辑器、运行时和视觉验收。'],
            'limitations': list(_LIMITATIONS)}


def _component_matches(source_context: dict, component: str) -> list[dict]:
    """Match a virtual official component against SourceContext nodes.

    Only the component identity is returned.  Physical installation paths
    stay inside the service's source context and are never copied into the
    portable official knowledge result.
    """
    wanted = component.replace('\\', '/').casefold().rstrip('/')
    basename = wanted.rsplit('/', 1)[-1]
    nodes = source_context.get('dependency_report', {}).get('nodes', [])
    return [node for node in nodes
            if str(node.get('name', '')).replace('\\', '/').casefold() == basename
            or str(node.get('name', '')).replace('\\', '/').casefold() == wanted
            or str(node.get('virtual_name', '')).replace('\\', '/').casefold() == wanted]


def _dependency_summary(source_context: dict | None, components: set[str]) -> dict:
    if source_context is None:
        return {'status': 'not_checked', 'reason': 'source_context_not_provided'}
    graph = source_context.get('dependency_report', {})
    missing = list(graph.get('missing', []))
    cycles = list(graph.get('cycles', []))
    incomplete = list(graph.get('incomplete', []))
    loaded = {component: bool(_component_matches(source_context, component)) for component in components}
    absent = sorted(component for component, present in loaded.items() if not present)
    unresolved_bnet = sum(item.get('kind') == 'bnet' for item in missing)
    if absent:
        status = 'blocked'
        reason = 'one_or_more_official_components_not_in_map_dependency_closure'
    elif missing or cycles or incomplete or not source_context.get('complete', False):
        status = 'partial'
        reason = 'dependency_closure_incomplete_or_unresolved'
    else:
        status = 'passed'
        reason = 'all_official_components_in_resolved_map_dependency_closure'
    return {'status': status, 'loaded_components': loaded, 'absent_components': absent,
            'dependency_graph_complete': bool(graph.get('complete', False)),
            'missing_count': len(missing), 'unresolved_bnet_count': unresolved_bnet,
            'cycle_count': len(cycles), 'incomplete_count': len(incomplete), 'reason': reason}


def audit(catalog, object_id, component=None, source_context=None, asset_readability=None):
    """Return five-layer evidence for one official object.

    This function deliberately accepts a prepared SourceContext rather than
    resolving a caller-supplied installation itself.  It can therefore never
    confuse an explicitly queried official pack with a dependency actually
    loaded by the current map.
    """
    explanation = explain(catalog, object_id, component)
    unresolved = list(explanation.get('unresolved_tokens', []))
    issues = list(explanation.get('issues', []))
    referenced_paths = [row.get('reference') for row in explanation.get('paths', [])
                        if row.get('reference')]
    for model in explanation.get('target_models', []):
        referenced_paths.extend(model.get('model_path_candidates', []))
        unresolved.extend(row.get('reference') for row in model.get('paths', [])
                          if row.get('unresolved_token'))
        issues.extend(model.get('issues', []))
    unresolved = sorted({value for value in unresolved if value})

    if unresolved:
        closure_status = 'partial'
    elif issues:
        closure_status = 'unknown'
    else:
        closure_status = 'passed'
    reference_closure = {
        'status': closure_status,
        'referenced_path_count': len(set(referenced_paths)),
        'unresolved_tokens': unresolved,
        'issues': issues,
        'engine_merge': 'unknown',
    }

    if source_context is None:
        dependency = {
            'status': 'not_checked',
            'component': explanation.get('component'),
            'reason': 'source_context_not_provided',
        }
    else:
        graph = source_context.get('dependency_report', {})
        missing = list(graph.get('missing', []))
        cycles = list(graph.get('cycles', []))
        incomplete = list(graph.get('incomplete', []))
        component_rows = _component_matches(source_context, explanation['component']) if explanation.get('component') else []
        unresolved_bnet = [item for item in missing if item.get('kind') == 'bnet']
        if not component_rows:
            status = 'blocked'
            reason = 'official_component_not_in_map_dependency_closure'
        elif unresolved_bnet or missing or cycles or incomplete or not source_context.get('complete', False):
            status = 'partial' if component_rows else 'blocked'
            reason = 'dependency_closure_incomplete_or_unresolved'
        else:
            status = 'passed'
            reason = 'component_present_in_resolved_map_dependency_closure'
        dependency = {
            'status': status,
            'component': explanation.get('component'),
            'reason': reason,
            'component_loaded': bool(component_rows),
            'dependency_graph_complete': bool(graph.get('complete', False)),
            'unresolved_bnet_count': len(unresolved_bnet),
            'missing_count': len(missing),
            'cycle_count': len(cycles),
            'incomplete_count': len(incomplete),
        }

    if asset_readability is None:
        asset = {'status': 'not_checked', 'reason': 'asset_materialization_not_provided'}
    else:
        asset = dict(asset_readability)
        asset.setdefault('status', 'unknown')
        # Keep the result portable even if a lower layer supplied paths.
        for key in ('nodes', 'edges', 'roots', 'asset_sources'):
            asset.pop(key, None)

    blocked = []
    missing = []
    unknown = []
    partial = []
    for name, row in [('map_dependency_status', dependency), ('asset_readability', asset),
                      ('reference_closure', reference_closure)]:
        status = row.get('status')
        if status == 'blocked':
            blocked.append({'layer': name, 'reason': row.get('reason', 'blocked')})
        elif status == 'missing':
            missing.append({'layer': name, 'reason': row.get('reason', 'missing')})
        elif status == 'unknown' or status == 'not_checked':
            unknown.append({'layer': name, 'reason': row.get('reason', 'unknown')})
        elif status == 'partial':
            partial.append({'layer': name, 'reason': row.get('reason', 'partial')})

    return {
        'schema': 'official-asset-audit/1',
        'catalog': catalog,
        'id': object_id,
        'component': explanation.get('component'),
        'build': deepcopy(explanation.get('build')),
        'knowledge_status': 'passed',
        'asset_readability': asset,
        'map_dependency_status': dependency,
        'reference_closure': reference_closure,
        'editor': 'not_tested',
        'runtime': 'not_tested',
        'visual': 'not_reviewed',
        'missing': missing,
        'unknown': unknown,
        'partial': partial,
        'blocked': blocked,
        'explanation': explanation,
        'limitations': [
            '官方索引存在不等于当前地图加载；需要 SourceContext 才能核对地图依赖。',
            '资源可读性需要当前构建的 CASC 物化证据；本审计不猜测物理路径。',
            '编辑器、游戏运行和视觉层级必须由独立证据记录。',
        ],
    }
