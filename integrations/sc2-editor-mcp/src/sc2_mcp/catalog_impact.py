"""Static before/candidate Catalog changes; never write maps or infer runtime."""
from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal, InvalidOperation
import hashlib
import json

from .catalog import _catalog_name, _trace
from .errors import SC2Error


def _identity(source):
    # A changed document hash alone is not a change of field ownership.
    return {key: value for key, value in (source or {}).items() if key != 'sha256'}


def _number(value):
    try:
        number = Decimal(value)
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _object(library, key):
    if key not in library.objects:
        return None
    try:
        inspected = library.inspect(*key)
        tree = library._effective(key, [], [])[0]
        shape = []
        def walk(node, prefix):
            for child in node.children:
                name = child.tag + ('[' + child.index + ']' if child.index is not None else '')
                path = prefix + '.' + name if prefix else name
                shape.append({'path': path, 'removed': child.removed})
                walk(child, path)
        walk(tree, '')
        return {**inspected, 'node_shape': shape}
    except SC2Error as exc:
        return {'unknown': exc.as_dict(), 'fields': {}}


def _inherited_targets(libraries, targets):
    children = defaultdict(set)
    for library in libraries:
        for key, patches in library.objects.items():
            parent = None
            for patch in patches:
                if 'parent' in patch.node.attrib:
                    parent = patch.node.get('parent')
            if parent:
                children[(key[0], parent)].add(key)
    found, pending = set(targets), deque(targets)
    while pending:
        for child in children[pending.popleft()]:
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def _graph(library):
    if not library.objects:
        return [], [], []
    # Reuse the existing typed-field/exact-ID graph and its explicit limits.
    issues = []
    for first in library.objects:
        try:
            trace = _trace(library, *first)
            break
        except SC2Error as exc:
            issues.append(exc.as_dict())
    else:
        return [], ['引用图未完整解析；不能据空边集合推定没有影响'], issues
    edges, missing, warnings = library._reference_cache
    return ([{**edge, 'resolved': True} for edge in edges] +
            [{**edge, 'resolved': False} for edge in missing]), trace['limitations'], issues + warnings


def _edge_key(edge):
    return json.dumps({key: edge[key] for key in ('from', 'field', 'to', 'confidence', 'resolved')}, sort_keys=True)


def inspect_patch_impact(before, after, operations, changes, context=None):
    targets = {(_catalog_name(op['catalog']), op['object_id']) for op in operations}
    affected = _inherited_targets([before, after], targets)
    objects, values, numeric, structural, sources, unknown = [], [], [], [], [], []
    changed = set()
    for key in sorted(affected):
        left, right = _object(before, key), _object(after, key)
        owner = {'catalog': key[0], 'object_id': key[1]}
        counts = {name: 0 for name in ('value_changes', 'structural_changes', 'source_only_changes')}
        for side, data in [('before', left), ('after', right)]:
            if data and data.get('unknown'):
                unknown.append({**owner, 'side': side, 'error': data['unknown']})
            elif data and data.get('warnings'):
                unknown.extend({**owner, 'side': side, 'warning': row} for row in data['warnings'])
        if any(data and data.get('unknown') for data in (left, right)):
            objects.append({**owner, 'status': 'unknown', 'counts': counts})
            continue
        for name in ('exists', 'class', 'inheritance', 'node_shape'):
            old = bool(left) if name == 'exists' else left.get(name) if left else None
            new = bool(right) if name == 'exists' else right.get(name) if right else None
            if old != new:
                structural.append({**owner, 'kind': name, 'before': old, 'after': new})
                counts['structural_changes'] += 1
        old_fields, new_fields = (left or {}).get('fields', {}), (right or {}).get('fields', {})
        for field in sorted(set(old_fields) | set(new_fields)):
            old, new = old_fields.get(field), new_fields.get(field)
            row = {**owner, 'field': field, 'before': old, 'after': new}
            if old is None or new is None:
                structural.append({**row, 'kind': 'field_added' if old is None else 'field_removed'})
                counts['structural_changes'] += 1
            elif old['value'] != new['value']:
                a, b = _number(old['value']), _number(new['value'])
                row['value_type'] = 'numeric' if a is not None and b is not None else 'literal'
                if row['value_type'] == 'numeric':
                    row['numeric_equal'] = a == b
                    numeric.append(row)
                values.append(row)
                counts['value_changes'] += 1
            elif _identity(old.get('source')) != _identity(new.get('source')):
                sources.append(row)
                counts['source_only_changes'] += 1
        if any(counts.values()):
            changed.add(key)
        objects.append({**owner, 'status': 'changed_static' if any(counts.values()) else 'unchanged_static',
                        'counts': counts, 'requested': key in targets})
    old_edges, limits, old_issues = _graph(before)
    new_edges, new_limits, new_issues = _graph(after)
    unknown.extend({'scope': 'reference_graph', 'side': side, 'detail': issue}
                   for side, issues in [('before', old_issues), ('after', new_issues)] for issue in issues)
    old_index, new_index = {_edge_key(row): row for row in old_edges}, {_edge_key(row): row for row in new_edges}
    references = {'added': [new_index[key] for key in sorted(new_index.keys() - old_index.keys())],
                  'removed': [old_index[key] for key in sorted(old_index.keys() - new_index.keys())],
                  'source_only': [{'before': old_index[key], 'after': new_index[key]}
                                  for key in sorted(old_index.keys() & new_index.keys())
                                  if _identity(old_index[key]['source']) != _identity(new_index[key]['source'])]}
    reverse = defaultdict(set)
    for edge in old_edges + new_edges:
        if edge['resolved']:
            reverse[(edge['to']['catalog'], edge['to']['object_id'])].add((edge['from']['catalog'], edge['from']['object_id']))
    impacted, pending = set(changed), deque(changed)
    while pending:
        for owner in reverse[pending.popleft()]:
            if owner not in impacted:
                impacted.add(owner)
                pending.append(owner)
    return {'version': 'catalog-impact-1', 'validation': 'static', 'engine_parity': False,
            'source_context_id': context.get('source_context_id') if context else None,
            'source_complete': context.get('complete') if context else None,
            'objects': objects, 'value_changes': values, 'numeric_changes': numeric,
            'structural_changes': structural, 'source_only_changes': sources, 'reference_changes': references,
            'unresolved_references': {'before': [row for row in old_edges if not row['resolved']],
                                      'after': [row for row in new_edges if not row['resolved']]},
            'potentially_impacted_objects': [{'catalog': kind, 'object_id': ident,
                                            'changed_effective_fields': (kind, ident) in changed}
                                           for kind, ident in sorted(impacted)],
            'unknown': unknown,
            'candidate_files': {path: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for path, raw in changes.items()},
            'limitations': sorted(set(limits + new_limits + ['反向引用表示潜在影响，不能证明运行时行为改变',
                '只审计当前静态Catalog；不解释动态Galaxy、Actor事件、未知默认值或未加载依赖']))}
