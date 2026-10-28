"""Remove imported official-ID overrides outside custom-unit ownership chains."""
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

from sc2_archive import no_links, scan
from sc2_migrate import Context, ComponentLoader
from sc2_migrate_catalog import Catalog, digest, default_types
from sc2_migrate_links import links
from sc2_mod_layers import catalog_rows, component_validation


GLOBAL_CONTEXT = {'Race', 'Campaign', 'Commander', 'GameUI', 'Config',
                  'ScoreValue', 'ScoreResult', 'ArmyCategory', 'ArmyUpgrade',
                  'Conversation', 'Location', 'Map', 'Objective'}


def ownership_link(edge, node):
    """Identity tests, upgrade targets and actor guards do not own units."""
    if edge.get('role') in {'runtime_alias', 'modifies_field'}:
        return False
    if edge.get('role') == 'actor_event' and '/@Terms' in edge['field']:
        # Event sources own the presentation actor, not the other way around.
        return edge['target'].startswith('Validator:')
    if edge.get('optional_condition'):
        return edge['target'].startswith('Validator:')
    if edge['target'].startswith(('asset:', 'text:')):
        return False
    if edge['target'].startswith('Unit:') and edge.get('role') != 'parent':
        return (any(word in edge['field'] for word in ('SpawnUnit', 'AmmoUnit', 'MorphUnit'))
                or ('InfoArray' in edge['field'] and node['@tag'] in
                    {'CAbilMorph', 'CAbilArmMagazine', 'CAbilMerge'})
                or (node['@tag'] == 'CEffectCreateUnit' and '/Unit' in edge['field']))
    return True


def select_overrides(records, catalogs, providers, official):
    """Keep every custom entry, but qualify official exceptions from unit roots."""
    roots = sorted(k for k in records if k[0] == 'Unit' and k not in official
                   and not k[1].startswith('@'))
    incoming = defaultdict(list)
    cache = {}
    diagnostics = []

    def inspect(source, key):
        identity = source, key
        if identity not in cache:
            node = catalogs[source]._effective_node(*key)
            edges, issues = links(node, *key) if node else ([], [])
            cache[identity] = node, edges
            diagnostics.extend(issues)
        return cache[identity]

    # Only the local presentation layer can require an imported actor override.
    for key in sorted(records):
        if key[0] != 'Actor' or key[1].startswith('@'):
            continue
        source = providers[key]
        node, edges = inspect(source, key)
        for edge in edges:
            if (edge.get('role') in {'binding', 'actor_event'}
                    and not edge.get('optional_condition')):
                if node['@tag'] not in {'CActorUnit', 'CActorMissile'} or edge['field'].endswith('/@unitName'):
                    incoming[edge['target']].append((source, key, edge))
        if node['@tag'] in {'CActorUnit', 'CActorMissile'} and ('Unit', key[1]) in records:
            incoming['Unit:'+key[1]].append((source, key, {'field': 'implicit same-ID unit actor'}))

    pending = deque((providers[k], k, k, None, True) for k in roots)
    seen = set()
    reasons = {}
    identity_only = []
    while pending:
        source, key, root, via, expand = pending.popleft()
        source = providers.get(key, source)
        if (source, key, expand) in seen:
            continue
        seen.add((source, key, expand))
        node, edges = inspect(source, key)
        if key in records:
            reasons.setdefault(key, {'root': ':'.join(root), 'via': via})
        if not node or key[0] in GLOBAL_CONTEXT:
            continue
        for tag in default_types(node['@tag']):
            default = (key[0], '@default:'+tag)
            if default in records:
                reasons.setdefault(default, {'root': ':'.join(root), 'via': {'source': ':'.join(key), 'field': 'type default'}})
        for edge in edges:
            if not expand and edge.get('role') != 'parent':
                continue
            if ownership_link(edge, node):
                dst = tuple(edge['target'].split(':', 1))
                # The child already contains effective inherited links. Walking
                # the parent's fields again resurrects arrays deleted by the child.
                pending.append((source, dst, root, {'source': ':'.join(key), 'field': edge['field']}, edge.get('role') != 'parent'))
            elif not edge['target'].startswith(('asset:', 'text:')):
                identity_only.append(edge)
        if expand:
            for actor_source, actor, edge in incoming.get(':'.join(key), []):
                pending.append((actor_source, actor, root, {'source': ':'.join(key), 'field': edge['field'], 'reverse_actor': True}, True))
    removed = {k for k in records if k in official and k not in reasons}
    # A source-wide default is an override, not a newly authored object.
    removed.update(k for k in records if k[1].startswith('@default:') and k not in reasons)
    return removed, reasons, {'roots': [':'.join(k) for k in roots],
                              'diagnostics': diagnostics, 'identity_only_links': identity_only}


def build_prune_plan(previous, source_caches, work_dir):
    """Prepare a checked removal on the current target, using the prior merge provenance."""
    previous = Path(previous).resolve()
    old = json.loads(previous.read_text(encoding='utf-8'))
    if old.get('kind') != 'sc2_mod_layer_merge' or digest({k:v for k,v in old.items() if k != 'plan_id'}) != old.get('plan_id'):
        raise ValueError('Invalid original merge plan')
    applied = json.loads((previous.parent/'applied.json').read_text(encoding='utf-8'))
    if not applied.get('applied') or applied.get('plan_id') != old['plan_id']:
        raise ValueError('Original merge was not published')
    target = Path(old['target']); work_dir = Path(work_dir).resolve()
    backup = Path(applied['backup'])
    if scan(backup) != old['snapshots'][str(target)]:
        raise ValueError('Original backup changed')
    if work_dir.exists():
        raise FileExistsError('Work directory must be new')
    for root in [target, backup, *map(Path, old['sources'])]:
        no_links(root)
        if work_dir == root or work_dir.is_relative_to(root) or root.is_relative_to(work_dir):
            raise ValueError('Work directory must be disjoint from components')
    snapshots = {str(root):scan(root) for root in [target, backup, *map(Path, old['sources'])]}
    records, _ = catalog_rows(target)
    original, _ = catalog_rows(backup)
    # Preserve records authored in the target before this migration.
    imported = {k:v for k,v in records.items() if k not in original and ':'.join(k) in old['catalog_providers']}
    provider = {k:old['catalog_providers'][':'.join(k)]['source'] for k in imported}
    loader = ComponentLoader()
    local_source, local_files, _, _ = loader.read(target)
    catalogs = {}; official = set(); coverage = []
    for source in old['sources']:
        if source not in source_caches:
            raise ValueError('Missing --source-cache for '+source)
        cache = Path(source_caches[source]).resolve()
        metadata = json.loads((cache/'official-cache.json').read_text(encoding='utf-8'))
        if metadata.get('status') != 'complete':
            raise ValueError('Complete official baseline required: '+str(cache))
        snapshots[str(cache)] = scan(cache)
        context = Context(source, mods_dir=target.parent, official_cache=cache, loader=loader)
        if not context.complete:
            raise ValueError('Incomplete source baseline: '+source+': '+str(context.state['problems']))
        official.update(context.official_ids)
        sources = [s for s in context.sources if s['id'] in context.official_sources]
        files = [f for s in sources for f in loader.read(context.source_roots[s['id']])[1]]
        catalogs[source] = Catalog([*sources, local_source], [*files, *local_files])
        coverage.append({'source':source, 'official_cache':str(cache), 'official_ids':len(context.official_ids),
                         'components':context.summary()['official_components'], 'component_issues':context.component_issues})
    removed, reasons, evidence = select_overrides(imported, catalogs, provider, official)
    work_dir.mkdir(parents=True)
    stage = work_dir/'component.SC2Mod'; shutil.copytree(target, stage)
    # Change only the catalogs containing removals. Retained nodes keep raw operations.
    affected = defaultdict(set)
    for key in removed:
        affected[records[key]['file']].add(key)
    from sc2_mod_layers import xml_root
    from sc2_migrate_catalog import family
    for relative, keys in affected.items():
        path = stage/relative; doc = xml_root(path)
        for node in list(doc):
            if not isinstance(node.tag, str):
                continue
            oid = node.get('id', '@default:'+node.tag)
            if (family(node.tag), oid) in keys:
                doc.remove(node)
        if not any(isinstance(n.tag, str) for n in doc):
            path.unlink()
        else:
            path.write_bytes(ET.tostring(doc, encoding='utf-8', xml_declaration=True)+b'\n')
    validation = component_validation(stage)
    if not validation['passed']:
        raise ValueError('Pruned Catalog validation failed: '+str(validation['issues'][:8]))
    retained = {k:v for k,v in reasons.items() if k in official}
    plan = {'schema_version':1, 'kind':'sc2_mod_layer_merge', 'operation':'prune_official_overrides',
            'target':str(target), 'stage':str(stage), 'sources':old['sources'], 'snapshots':snapshots,
            'previous_plan':str(previous), 'official_baselines':coverage, 'validation':validation,
            'summary':{'removed_official_entries':len(removed), 'retained_linked_official_entries':len(retained),
                       'custom_unit_roots':len(evidence['roots']), 'remaining_catalog_entries':len(records)-len(removed)},
            'removed':sorted(':'.join(k) for k in removed),
            'removed_by_family':dict(Counter(k[0] for k in removed)),
            'retained_official':{':'.join(k):v for k,v in retained.items()}, 'chain_evidence':evidence,
            'official_dependency_payload_copied':False, 'dependency_policy':old['dependency_policy']}
    if (stage/'DocumentInfo').read_bytes() != (target/'DocumentInfo').read_bytes():
        raise ValueError('Dependency declaration changed')
    plan['stage_snapshot'] = scan(stage)
    for root, expected in snapshots.items():
        if scan(Path(root)) != expected:
            raise ValueError('Input changed while preparing prune: '+root)
    plan['plan_id'] = digest(plan)
    (work_dir/'layer-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return plan
