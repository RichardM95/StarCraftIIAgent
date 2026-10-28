"""Dependency-aware unit migration analysis. Real projects are read-only here."""
from __future__ import annotations

import copy
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from sc2_components import component_path, provenance, parse_xml
from sc2_dependencies import build_dependency_graph, dependency_state
from sc2_official import catalog_paths, cache_manifest
from sc2_migrate_catalog import (Catalog, encode_node, render_node, digest, family,
                                elements, flatten, semantic_node, merge_node, tokens_from, default_types)
from sc2_migrate_links import links, TEXT_REF, text_data_links, ASSET

VERSION = 1
TEXT_FILES = ('GameStrings.txt', 'ObjectStrings.txt', 'GameHotkeys.txt')


def component_listing(root):
    anchor=Path(root)
    return sorted(p.relative_to(anchor).as_posix() for p in component_path(root).rglob('*') if p.is_file())


def safe_relative(value):
    value = str(value).replace('\\', '/')
    path = PurePosixPath(value)
    if (not path.parts or path.is_absolute() or any(p in {'..', '.'} for p in value.split('/'))
            or ':' in value or '\x00' in value or any(p.endswith((' ', '.')) for p in path.parts)):
        raise ValueError('Unsafe relative path: ' + value)
    return path


def locate(root, relative):
    """Use the shared archive reader and preserve case-insensitive virtual paths."""
    current = component_path(root)
    anchor = Path(root).absolute()
    for part in safe_relative(relative).parts:
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()] if current.is_dir() else []
        if len(matches) > 1:
            raise ValueError('Case-conflicting path: ' + str(current / part))
        current = matches[0] if matches else current / part
    if not Path(current).resolve().is_relative_to(anchor.resolve()):
        raise ValueError('Path escapes component: ' + str(current))
    return current


def decode(raw):
    if raw.startswith(b'\xff\xfe'):
        return raw[2:].decode('utf-16-le'), 'utf-16-le', 'fffe'
    if raw.startswith(b'\xfe\xff'):
        return raw[2:].decode('utf-16-be'), 'utf-16-be', 'feff'
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw[3:].decode('utf-8'), 'utf-8', 'efbbbf'
    return raw.decode('utf-8'), 'utf-8', ''


def evidence_file(path, raw):
    return {'path': str(path), 'sha256': digest(raw), 'archive': provenance(path, member_sha256=digest(raw))}


class ComponentLoader:
    """One invocation owns parsed sources; no persistent database or trust cache."""
    def __init__(self):
        self.components = {}
        self.parsed_catalogs = {}

    def read(self, root):
        key = str(Path(root).resolve())
        if key in self.components:
            return self.components[key]
        source_id = key.casefold()
        records, inputs, texts = [], [], {}
        paths = list(catalog_paths(Path(root)))
        # Local Includes may register catalogs outside the conventional folder.
        pending = list(paths)
        for name in ('Base.SC2Data/GameData.xml',):
            entry = locate(root, name)
            if entry.is_file():
                pending.append(entry)
        seen, visiting = set(), set()

        def read_xml(path):
            identity = str(path).casefold()
            if identity in visiting:
                raise ValueError('Cyclic GameData include: ' + str(path))
            if identity in seen:
                return
            visiting.add(identity)
            raw = path.read_bytes()
            checksum=digest(raw)
            inputs.append(evidence_file(path, raw))
            relative = Path(path).relative_to(Path(root)).as_posix()
            if checksum in self.parsed_catalogs:
                encoded,raw_text=self.parsed_catalogs[checksum]
                records.append({'source_id':source_id,'path':relative,'nodes':[encoded],
                                'raw_xml':raw_text,'sha256':checksum})
                visiting.remove(identity);seen.add(identity)
                return
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
            node = ET.fromstring(raw, parser=parser)
            if node.tag == 'Includes':
                for child in node:
                    if child.tag is ET.Comment:
                        continue
                    ref = child.get('path')
                    if child.tag != 'Catalog' or not ref:
                        raise ValueError('Unsupported GameData include: ' + str(path))
                    # Includes are relative to the file containing them.
                    target = locate(path.parent, ref)
                    if not Path(target).resolve().is_relative_to(Path(root).resolve()):
                        raise ValueError('Include escapes component: ' + ref)
                    read_xml(target)
            elif node.tag == 'Catalog':
                encoded=encode_node(node);raw_text=decode(raw)[0]
                self.parsed_catalogs[checksum]=(encoded,raw_text)
                records.append({'source_id':source_id,'path':relative,'nodes':[encoded],
                                'raw_xml':raw_text,'sha256':checksum})
            else:
                raise ValueError('Unsupported catalog root: ' + str(path))
            visiting.remove(identity)
            seen.add(identity)

        for path in pending:
            read_xml(path)
        root_path = component_path(root)
        locales = [p for p in root_path.iterdir() if p.is_dir() and re.fullmatch(r'[a-zA-Z]{4}\.SC2Data', p.name)]
        for locale in locales:
            for name in TEXT_FILES:
                path = locate(locale, 'LocalizedData/' + name)
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                text, encoding, bom = decode(raw)
                inputs.append(evidence_file(path, raw))
                for line in text.splitlines():
                    if not line.strip() or line.lstrip().startswith(('//', '#')) or '=' not in line:
                        continue
                    k, value = line.split('=', 1)
                    identity = (locale.name[:4], name, k.strip())
                    if identity in texts and texts[identity]['value'] != value:
                        raise ValueError('Conflicting text key: ' + str(identity))
                    texts[identity] = {'value': value, 'source_id': source_id, 'file': str(path),
                                       'encoding': encoding, 'bom': bom}
        for name in ('ComponentList.SC2Components', 'DocumentInfo', 'Base.SC2Data/DocumentInfo'):
            path = locate(root, name)
            if path.is_file():
                inputs.append(evidence_file(path, path.read_bytes()))
        source = {'id': source_id, 'name': Path(root).name, 'root': str(root),
                  'fingerprint': digest(inputs)}
        self.components[key] = (source, records, texts, inputs)
        return self.components[key]


class Context:
    def __init__(self, path, *, mods_dir=None, campaigns_dir=None, official_cache=None, loader=None,
                 graph=None):
        self.path = Path(path).resolve()
        mods = Path(mods_dir) if mods_dir else next((p for p in self.path.parents if p.name.casefold() == 'mods'), self.path.parent)
        self.graph = graph if graph is not None else build_dependency_graph(
            self.path, mods, campaigns_dir=Path(campaigns_dir) if campaigns_dir else None,
            official_cache=official_cache)
        self.state = dependency_state(self.graph)
        self.loader = loader or ComponentLoader()
        self.sources, records, self.texts, self.inputs = [], [], {}, []
        self.official_ids, self.local_ids = set(), set()
        self.official_sources = set()
        self.source_roots = {}
        self.component_issues = []
        self.inventories = {}
        ordered = self.graph.get('traversal_order', [])
        for key in ordered:
            node = self.graph['nodes'][key]
            root = Path(node['path'])
            try:
                source, files, texts, inputs = self.loader.read(root)
            except (ValueError, OSError, ET.ParseError) as exc:
                self.component_issues.append({'code': 'component_read_error', 'path': str(root), 'detail': str(exc)})
                continue
            self.sources.append(source)
            records.extend(files)
            self.texts.update(texts)  # Same locale only; later component wins.
            self.inputs.extend(inputs)
            self.source_roots[source['id']] = root
            self.inventories[str(root)] = component_listing(root)
            ids = {(family(n['@tag']), n.get('attributes', {}).get('id')) for r in files
                   for n in elements(r['nodes'][0]) if n['@tag'].startswith('C') and n.get('attributes', {}).get('id')}
            if node.get('origin') == 'casc' or node.get('official') is True:
                self.official_ids.update(ids)
                self.official_sources.add(source['id'])
            if root.resolve() == self.path:
                self.local_ids.update(ids)
            info=node.get('info_component')
            if info:
                registered=locate(root,info)
                if registered.is_file() and not any(r['path']==str(registered) for r in self.inputs):
                    self.inputs.append(evidence_file(registered,registered.read_bytes()))
            manifest=cache_manifest(root)
            if manifest and not any(r['path']==str(manifest) for r in self.inputs):
                self.inputs.append(evidence_file(manifest,manifest.read_bytes()))
                metadata=json.loads(manifest.read_text(encoding='utf-8'))
                build=Path(metadata['identity']['install'])/'.build.info'
                if build.is_file():
                    self.inputs.append(evidence_file(build,build.read_bytes()))
        self.catalog = Catalog(self.sources, records)
        self.definition_index = {(d['source_id'],d['file'],d['ordinal']):d for d in self.catalog.definitions}
        self.text_index = defaultdict(list)
        for (locale,name,key),value in self.texts.items():
            self.text_index[key].append((locale,name,value))
        self.primary_id = str(self.path).casefold()
        self.known_ids={oid for _,oid in self.catalog.objects}
        self.incoming = None
        self._links = {}
        self._evidence = {}
        self._compatible = {}
        self.external_inputs = []
        self.external_hits = defaultdict(list)
        self.external_unknown = []
        self._scan_external()
        # Defaults/const conflicts within a component cannot be ordered by filename.
        grouped = defaultdict(list)
        for d in self.catalog.definitions:
            if d['default']:
                grouped[d['source_id'], d['tag']].append(d)
        for (sid, tag), ds in grouped.items():
            if len({d['file'] for d in ds}) > 1:
                for n,left in enumerate(ds):
                    for right in ds[n+1:]:
                        if left['file']==right['file']:
                            continue
                        a,b=left['node'],right['node'];empty={'@tag':tag,'attributes':{},'children':[]}
                        ab=merge_node(merge_node(empty,a),b);ba=merge_node(merge_node(empty,b),a)
                        append=any(c['@tag'].endswith('Array') and 'index' not in c['attributes']
                                   for node in (a,b) for c in self._descendants(node))
                        if (append or flatten(ab)!=flatten(ba) or ab['attributes']!=ba['attributes']
                                or {**tokens_from(a),**tokens_from(b)}!={**tokens_from(b),**tokens_from(a)}):
                            self.component_issues.append({'code':'ambiguous_default_order','source_id':sid,
                                                          'tag':tag,'files':[left['file'],right['file']]})
        self.fingerprint = digest(self.inputs + self.external_inputs)

    @property
    def complete(self):
        return self.state['status'] == 'complete' and not any(
            i['code']!='ambiguous_default_order' for i in self.component_issues)

    def _scan_external(self):
        """Index exact ID evidence; arbitrary scripts remain an explicit unknown."""
        root = component_path(self.path)
        paths = [p for p in root.rglob('*') if p.is_file() and
                 (p.name == 'Triggers' or p.suffix.casefold() in {'.galaxy', '.sc2layout'})]
        local_tokens = {oid for _, oid in self.local_ids}
        seen = set()
        for path in paths:
            raw = path.read_bytes()
            self.external_inputs.append(evidence_file(path, raw))
            try:
                text = decode(raw)[0]
            except UnicodeError:
                self.external_unknown.append({'code': 'external_encoding_unknown', 'file': str(path)})
                continue
            for token in set(re.findall(r'[A-Za-z0-9_]+', text)) & local_tokens:
                self.external_hits[token].append({'file': str(path), 'kind': 'ui' if path.suffix.casefold() == '.sc2layout' else 'script'})
            # Generated Galaxy is evidence only. No editing or compilation here.
            if (path.suffix.casefold() == '.galaxy' and path.name not in {'MapScript.galaxy'}
                    and not re.fullmatch(r'Lib\w+(?:_h)?\.galaxy', path.name)):
                seen.add(str(path))
        self.external_unknown.extend({'code': 'script_semantics_unverified', 'file': p} for p in sorted(seen))

    def object_links(self, identity):
        if identity in self._links:
            return self._links[identity]
        node = self.catalog._effective_node(*identity)
        if node is None:
            return [], []
        rows, issues = links(node, *identity)
        rows=[row for row in rows if row.get('role')!='runtime_alias' or
              tuple(row['target'].split(':',1)) in self.catalog.objects]
        if identity[0]=='Actor':
            known_targets={r['target'].split(':',1)[1] for r in rows}
            for child in [node,*self._descendants(node)]:
                for attr in ('Terms','Send','Target','Subject'):
                    value=child.get('attributes',{}).get(attr,'')
                    unknown=(set(re.findall(r'[A-Za-z0-9_]+',value)) & self.known_ids)-known_targets
                    if unknown:
                        issues.append({'code':'unclassified_actor_reference','source':':'.join(identity),
                                       'attribute':attr,'value':value,'possible_ids':sorted(unknown)})
        fields = self.catalog.explain_fields(*identity)
        defs = self.definition_index
        for row in rows:
            origin = fields.get(row.get('lookup'), {}).get('source')
            if origin:
                row['provenance'] = origin
                definition = defs.get((origin['source_id'], origin['file'], origin['ordinal']))
                if definition:
                    row['inherited'] = definition['id'] != identity[1]
                    row['default'] = definition['default']
        self._links[identity] = rows, issues
        return rows, issues

    def object_evidence(self,identity):
        if identity not in self._evidence:
            node=self.catalog._effective_node(*identity)
            self._evidence[identity]={
                'fields':self.catalog.explain_fields(*identity),
                'definitions':[{k:d[k] for k in ('source_id','file','ordinal','parent','tag')}
                               for d in self.catalog.objects[identity]],
                'original_xml':[render_node(d['node']) for d in self.catalog.objects[identity]],
                'effective_xml':render_node(node)}
        return self._evidence[identity]

    def equivalent(self,target,identity):
        key=(id(target),identity)
        if key not in self._compatible:
            self._compatible[key]=semantic_node(self.catalog._effective_node(*identity))==semantic_node(target.catalog._effective_node(*identity))
        return self._compatible[key]

    @staticmethod
    def _descendants(node):
        for child in elements(node):
            yield child
            yield from Context._descendants(child)

    def reverse_links(self):
        if self.incoming is not None:
            return self.incoming
        incoming = defaultdict(list)
        seen=set()
        for definition in self.catalog.definitions:
            # Index literal candidates cheaply; evaluate overridden/inherited
            # semantics only for backlinks actually reached by this migration.
            if definition['family'] not in {'Actor', 'Abil', 'Upgrade', 'Unit', 'Effect'} or not definition['id']:
                continue
            rows, _ = links(definition['node'],definition['family'],definition['id'])
            for row in rows:
                identity=(row['source'],row['target'],row['field'])
                if identity not in seen:
                    incoming[row['target']].append(row);seen.add(identity)
        self.incoming = incoming
        return incoming

    def incoming_for(self,key,*,include_gameplay=False):
        origins={row['source'] for row in self.reverse_links().get(key,[]) if row.get('role')!='parent' and
                 ((row['source'].startswith('Actor:') and row.get('role') in {'binding','actor_event'}
                   and not row.get('optional_condition')) or
                  (include_gameplay and row['source'].split(':',1)[0] in {'Abil','Unit','Upgrade','Effect'}))}
        return [row for origin in sorted(origins) for row in self.object_links(tuple(origin.split(':',1)))[0]
                if row['target']==key]

    def summary(self):
        return {'path': str(self.path), 'fingerprint': self.fingerprint,
                'dependency_status': self.state['status'], 'dependency_problems': self.state['problems'],
                'component_issues': self.component_issues, 'complete': self.complete,
                'official_components': [s['name'] for s in self.sources if s['id'] in self.official_sources],
                'external_unknown': self.external_unknown,
                'context':{'mods_dir':self.state.get('mods_dir'),'campaigns_dir':self.state.get('campaigns_dir'),
                           'official_cache':(self.state.get('official_cache') or {}).get('root',False)}}


def classification(context, identity):
    node = context.catalog._effective_node(*identity)
    fields = flatten(node)
    rows, _ = context.object_links(identity)
    actor = any(e['source'].startswith('Actor:') and e.get('role') == 'binding'
                for e in context.incoming_for(':'.join(identity),include_gameplay=True))
    producing = any(e['source'].startswith('Abil:') and any(t in e['field'] for t in ('InfoArray', 'SpawnUnit', 'AmmoUnit', 'MorphUnit'))
                    for e in context.incoming_for(':'.join(identity),include_gameplay=True))
    flags = {p: v for p,v in fields.items() if p.startswith(('FlagArray|', 'Flags|', 'EditorFlags|'))}
    helper = [p for p,v in flags.items() if v == '1' and any(t in p for t in ('Missile', 'Dummy', 'NoDraw', 'EditorHidden'))]
    abilities = [e for e in rows if e['target'].startswith('Abil:')]
    weapons = [e for e in rows if e['target'].startswith('Weapon:')]
    cards = any(p.startswith('CardLayouts') for p in fields)
    if helper:
        kind = 'auxiliary'
    elif actor and (abilities or weapons or cards or producing or any('Structure' in p and v=='1' for p,v in flags.items())):
        kind = 'playable'
    else:
        kind = 'needs_selection'
    return {'kind': kind, 'evidence': {'actor_binding': actor, 'production_reference': producing,
            'abilities': len(abilities), 'weapons': len(weapons), 'command_card': cards, 'helper_flags': helper}}


def source_key(path):
    """Stable ASCII namespace, independent of absolute installation path."""
    stem = Path(path).stem
    name = re.sub(r'[^A-Za-z0-9_]', '_', stem)
    return (name if name and name[0].isalpha() else 'Source_' + name) + '_' + digest(stem.encode())[:6]


def mapped_id(prefix, context, identity):
    old = identity[1]
    clean = re.sub(r'[^A-Za-z0-9_]', '_', old)
    suffix = '_' + digest(old.encode())[:8] if clean != old else ''
    return prefix + source_key(context.path) + '_' + clean + suffix


def model_asset_paths(payload):
    """Bounded M3 CHAR extraction, adapted from SC2EditorTool (MIT)."""
    import struct
    if len(payload) < 12 or payload[:4] != b'43DM':
        raise ValueError('Unsupported or corrupt M3 header')
    offset, count = struct.unpack_from('<II', payload, 4)
    if offset < 12 or offset > len(payload) or count > (len(payload) - offset) // 16:
        raise ValueError('Corrupt M3 section table')
    result = set()
    for i in range(count):
        tag, start, size, _ = struct.unpack_from('<4sIII', payload, offset + i * 16)
        if tag != b'RAHC':
            continue
        if start > len(payload) or size > len(payload) - start:
            raise ValueError('Corrupt M3 CHAR section')
        for raw in payload[start:start+size].split(b'\0'):
            try:
                path = raw.decode('utf-8')
            except UnicodeError:
                continue
            if ASSET.search(path):
                result.add(str(safe_relative(path)))
    return sorted(result)


class Resources:
    def __init__(self, context, *, casc=None):
        self.context, self.casc, self.cache = context, casc, {}
        self.models={}

    def read(self, path, locale=None):
        path = str(safe_relative(path))
        key = (locale, path.casefold())
        if key in self.cache:
            return self.cache[key]
        for source in reversed(self.context.sources):
            prefixes = (locale + '.SC2Assets', locale + '.SC2Data') if locale else ('Base.SC2Assets', 'Base.SC2Data', '')
            for prefix in prefixes:
                full = locate(source['root'], (prefix + '/' if prefix else '') + path)
                if full.is_file():
                    raw = full.read_bytes()
                    row = {'path': path, 'locale': locale, 'sha256': digest(raw),
                           'source_id': source['id'], 'evidence': evidence_file(full, raw)}
                    self.cache[key] = row
                    return row
            if self.casc and source['id'] in self.context.official_sources:
                manifest = cache_manifest(Path(source['root']))
                logical = Path(source['root']).relative_to(manifest.parent).as_posix()
                for prefix in prefixes:
                    name = logical + '/' + (prefix + '/' if prefix else '') + path
                    raw = self.casc.read(name)
                    if raw is not None:
                        row = {'path': path, 'locale': locale, 'sha256': digest(raw), 'source_id': source['id'],
                               'evidence': {'casc_path': name, 'sha256': digest(raw),
                                            'manifest': str(manifest)}}
                        self.cache[key] = row
                        return row
        self.cache[key] = None
        return None

    def model_references(self,row):
        checksum=row['sha256']
        if checksum not in self.models:
            evidence=row['evidence']
            raw=component_path(evidence['path']).read_bytes() if evidence.get('path') else self.casc.read(evidence['casc_path'])
            if raw is None or digest(raw)!=checksum:
                raise ValueError('Model changed during analysis')
            self.models[checksum]=model_asset_paths(raw)
        return self.models[checksum]


def closure(context, root, target, prefix, *, casc=None, max_objects=2000):
    pending, objects, edges, issues, optional = deque([root]), {}, [], [], []
    assets, textkeys = set(), set()
    identity_references,upgrade_mutations=[],[]
    text_unit_refs=set()
    incoming = context.reverse_links()
    def include_text(key):
        if key in textkeys:
            return
        textkeys.add(key)
        for _,_,record in context.text_index.get(key,[]):
            for child in TEXT_REF.findall(record['value']):
                include_text(child)
            for ref in text_data_links(record['value']):
                referenced=tuple(ref.split(':',1))
                if referenced[0]=='Unit' and referenced!=root:
                    text_unit_refs.add(ref)
                else:
                    pending.append(referenced)
    while pending:
        identity = pending.popleft()
        key = ':'.join(identity)
        if key in objects:
            continue
        if len(objects)>=max_objects:
            issues.append({'code':'object_budget_exceeded','limit':max_objects,'remaining':len(pending)+1})
            break
        node = context.catalog._effective_node(*identity)
        if node is None:
            issues.append({'code': 'missing_object', 'object': key})
            objects[key] = {'action': 'missing', 'id': identity[1]}
            continue
        rows, diagnostics = context.object_links(identity)
        issues.extend(diagnostics)
        target_node = target.catalog._effective_node(*identity)
        # Reuse is only permitted when all reached outgoing semantics also agree.
        same = target_node is not None and context.equivalent(target,identity)
        implicit={identity[0]+'/'+part+'/'+identity[1] for part in ('Name','Tooltip','EditorPrefix','EditorSuffix','Hotkey')}
        referenced={r['target'][5:] for r in rows if r['target'].startswith('text:')}|implicit
        if same:
            same=all(target.texts.get((loc,name,key),{}).get('value')==value['value']
                     for key in referenced for loc,name,value in context.text_index.get(key,[]))
        primary_owned = any(d['source_id'] == context.primary_id for d in context.catalog.objects[identity])
        action = 'reuse_candidate' if same and not primary_owned else 'copy'
        objects[key] = {'action': action, 'id': mapped_id(prefix, context, identity),
                        'tag': node['@tag'],**context.object_evidence(identity)}
        if identity[0] in {'Race','Campaign','Commander','GameUI','Config','ScoreValue','ScoreResult'}:
            # These are global context bindings, not ownership of their starting
            # units, UI registries or entire faction tech trees. Crossing this seam
            # needs a separate project decision when the target context differs.
            objects[key]['action']='reuse' if same else 'missing'
            objects[key]['id']=identity[1]
            if not same:
                issues.append({'code':'global_context_incompatible','object':key})
            continue
        for row in rows:
            if row.get('role') == 'parent':
                # Materialized fields carry parent semantics; retain parent evidence.
                edges.append(dict(row, materialized_parent=True))
                continue
            if row.get('role')=='modifies_field':
                # An upgrade's mutation list is not ownership of every affected
                # faction object. Keep the operation, but require its destination
                # to belong to this migrated gameplay chain before export.
                upgrade_mutations.append(row);edges.append(row);optional.append(row)
                continue
            if row['target'].startswith('Unit:') and row['target']!=':'.join(root):
                gameplay=(any(word in row['field'] for word in ('SpawnUnit','AmmoUnit','MorphUnit','InfoArray'))
                          or (node['@tag']=='CEffectCreateUnit' and '/Unit' in row['field']))
                if not gameplay:
                    identity_references.append(row);edges.append(dict(row,identity_reference=True))
                    continue
            if row.get('optional_condition') or row.get('role') == 'modifies_field':
                optional.append(row)
                if row.get('role') == 'modifies_field':
                    # Upgrade effects mutate fields and need their referenced object.
                    pending.append(tuple(row['target'].split(':', 1)))
                else:
                    guarded=tuple(row['target'].split(':',1))
                    # Validators constrain the kept actor. Broad lifecycle unit
                    # guards do not import unrelated units as additional roots.
                    if guarded[0]=='Validator' or guarded==root:
                        pending.append(tuple(row['target'].split(':', 1)))
                    elif not context.equivalent(target,guarded):
                        issues.append({'code': 'optional_condition_unresolved', 'edge': row})
                edges.append(row)
                continue
            target_key = row['target']
            edges.append(row)
            if target_key.startswith('asset:'):
                assets.add(target_key[6:])
            elif target_key.startswith('text:'):
                include_text(target_key[5:])
            elif row.get('default') and tuple(target_key.split(':',1)) not in context.catalog.objects:
                issues.append({'code': 'default_reference_unresolved', 'edge': row})
            elif row.get('conditional') and tuple(target_key.split(':',1)) not in context.catalog.objects:
                issues.append({'code': 'runtime_reference_unresolved', 'edge': row})
            else:
                pending.append(tuple(target_key.split(':', 1)))
        for row in context.incoming_for(key,include_gameplay=identity==root):
            origin = tuple(row['source'].split(':',1))
            if (origin[0] == 'Actor' and not row.get('inherited') and not row.get('default')
                    and row.get('role') in {'binding','actor_event'} and not row.get('optional_condition')):
                defs = context.catalog.objects.get(origin, [])
                unit_actor = defs and defs[-1]['tag'] in {'CActorUnit','CActorMissile'}
                if not unit_actor or row['field'].endswith('/@unitName'):
                    pending.append(origin)
                    edges.append(dict(row, reverse=True))
            elif identity == root and origin[0] in {'Abil','Unit','Upgrade'}:
                optional.append(dict(row, reverse=True))
        # Standard implicit names are real localization anchors too.
        for part in ('Name','Tooltip','EditorPrefix','EditorSuffix','Hotkey'):
            textkey=identity[0]+'/'+part+'/'+identity[1]
            if textkey in context.text_index:
                include_text(textkey)
        for hit in context.external_hits.get(identity[1], []):
            issues.append({'code': 'external_mechanism_reference', 'object': key, **hit})
        if any(p.startswith(('CustomUnitStatusFrame', 'StatusBarOn|Custom')) for p in flatten(node)):
            issues.append({'code': 'custom_ui_dependency', 'object': key})
    # Text references can reach additional catalog records; handle through a second closure
    # at the caller, never treat their embedded IDs as free-form replacements.
    texts, text_pending = {}, deque(textkeys)
    for row in identity_references:
        if row['target'] not in objects and target.catalog._effective_node(*row['target'].split(':',1)) is None:
            issues.append({'code':'referenced_unit_requires_selection','edge':row})
    for row in upgrade_mutations:
        if row['target'] not in objects:
            issues.append({'code':'upgrade_mutation_outside_chain','edge':row})
    for ref in text_unit_refs:
        if ref not in objects and not context.equivalent(target,tuple(ref.split(':',1))):
            issues.append({'code':'text_unit_value_requires_review','object':ref})
    seen = set()
    while text_pending:
        key = text_pending.popleft()
        if key in seen:
            continue
        seen.add(key)
        found = False
        for locale,name,value in context.text_index.get(key,[]):
            found = True
            texts[locale + ':' + name + ':' + key] = {**value,'origin_file':value['file'],
                                                     'locale':locale,'file':name,'key':key}
            text_pending.extend(TEXT_REF.findall(value['value']))
            for ref in text_data_links(value['value']):
                if ref not in objects and not context.equivalent(target,tuple(ref.split(':',1))):
                    issues.append({'code':'text_catalog_dependency', 'object':ref, 'text':key})
        if not found:
            issues.append({'code':'missing_text', 'key':key})
    resources, asset_pending = {}, deque(assets)
    if not hasattr(context,'resource_reader') or context.resource_reader.casc is not casc:
        context.resource_reader=Resources(context,casc=casc)
    if not hasattr(target,'resource_reader') or target.resource_reader.casc is not casc:
        target.resource_reader=Resources(target,casc=casc)
    reader,target_reader=context.resource_reader,target.resource_reader
    while asset_pending:
        path = asset_pending.popleft()
        locales = sorted({k[0] for k in context.texts}) if path.lower().startswith('localizeddata/') else [None]
        for locale in locales:
            resource_key = (locale or '') + ':' + path.casefold()
            if resource_key in resources:
                continue
            row = reader.read(path,locale)
            existing = target_reader.read(path,locale)
            if row is None:
                resources[resource_key] = {'path':path,'locale':locale,'action':'unverified',
                                            'target_present':existing is not None}
                issues.append({'code':'asset_unverified','path':path,'locale':locale,
                               'reason':'not_in_readable_components_or_casc_not_requested'})
                continue
            action = 'reuse' if existing and existing['sha256']==row['sha256'] else 'copy'
            if existing and existing['sha256'] != row['sha256']:
                action = 'conflict'
                issues.append({'code':'resource_conflict','path':path,'locale':locale})
            resources[resource_key] = {k:v for k,v in row.items() if k != 'payload'} | {'action':action}
            if path.lower().endswith('.m3'):
                try:
                    for child in reader.model_references(row):
                        asset_pending.append(child)
                        edges.append({'source':'asset:'+path,'target':'asset:'+child,'role':'model_asset'})
                except ValueError as exc:
                    issues.append({'code':'corrupt_model','path':path,'detail':str(exc)})
    # A parent's absence/cycle is diagnosed while materializing its child.
    related = {tuple(k.split(':',1)) for k in objects}
    ancestors=list(related)
    while ancestors:
        identity=ancestors.pop()
        for definition in context.catalog.objects.get(identity,[]):
            parent=(identity[0],definition['parent'])
            if parent[1] and parent not in related:
                related.add(parent);ancestors.append(parent)
    for issue in context.catalog.diagnostics:
        if not issue.get('family') or (issue['family'],issue.get('id')) in related:
            issues.append(issue)
    # Equal local fields do not establish equal descendant semantics. Promote ancestors
    # to private copies until the reuse subgraph is closed (cycles use a fixed point).
    changed = True
    while changed:
        changed = False
        for edge in edges:
            src, dst = objects.get(edge.get('source')), objects.get(edge.get('target'))
            if src and src['action']=='reuse_candidate' and dst and dst['action'] not in {'reuse_candidate','reuse'}:
                src['action']='copy'; changed=True
    for key,obj in objects.items():
        if obj['action']=='reuse_candidate':
            obj['action']='reuse';obj['id']=key.split(':',1)[1]
    reached_types={base for obj in objects.values() if obj.get('tag') for base in default_types(obj['tag'])}
    issues.extend(i for i in context.component_issues if i['code']!='ambiguous_default_order' or i['tag'] in reached_types)
    issues.extend(i for i in target.component_issues if i['code']=='ambiguous_default_order' and i['tag'] in reached_types)
    if not context.complete:
        issues.append({'code':'source_dependency_incomplete','problems':context.state['problems']})
    if not target.complete:
        issues.append({'code':'target_dependency_incomplete','problems':target.state['problems']})
    if context.external_unknown:
        issues.append({'code':'external_semantics_unverified','evidence':context.external_unknown})
    issues = list({json.dumps(v,sort_keys=True):v for v in issues}.values())
    return {'root':':'.join(root),'source':str(context.path),'objects':objects,'edges':edges,
            'optional_connections':optional,'resources':resources,'texts':texts,
            'issues':issues,'executable':not issues,'next_step':'resolve_reported_issues' if issues else 'export_and_preview'}


def analyze(sources, target, *, prefix='AmithImported_', selection=None, mods_dir=None,
            campaigns_dir=None, official_cache=None, source_caches=None, casc=None, progress=None, contexts=None,
            max_objects=2000):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',prefix):
        raise ValueError('Prefix must be an ASCII catalog identifier')
    if max_objects<1:
        raise ValueError('Object budget must be positive')
    implementation=[evidence_file(path,path.read_bytes()) for path in Path(__file__).parent.glob('sc2*migrat*.py')]
    loader = ComponentLoader()
    options = {'mods_dir':mods_dir,'campaigns_dir':campaigns_dir,'official_cache':official_cache,'loader':loader}
    target_context = contexts[-1] if contexts else Context(target,**options)
    source_contexts = contexts[:-1] if contexts else (Context(path,**{**options,
        'official_cache':(source_caches or {}).get(Path(path).name,official_cache)}) for path in sources)
    if len({source_key(p) for p in sources}) != len(sources):
        raise ValueError('Source namespaces collide; use distinct component names')
    selection = selection or {}
    selected = selection.get('units',{})
    excluded = set(selection.get('exclude',[]))
    candidates, excluded_official, by_id = [], [], defaultdict(list)
    source_summaries=[];inputs=list(target_context.inputs+target_context.external_inputs)
    inventories=dict(target_context.inventories)
    for context in source_contexts:
        if progress:
            progress('Classifying ' + context.path.name)
        for identity in sorted(context.local_ids):
            if identity[0]!='Unit':
                continue
            if identity in context.official_ids:
                excluded_official.append({'source':str(context.path),'id':identity[1],'reason':'official_id_in_source_dependencies'})
                continue
            row = {'source':str(context.path),'source_key':source_key(context.path),'id':identity[1],
                   'official_status':'custom' if context.complete else 'unconfirmed',
                   **classification(context,identity)}
            candidates.append(row);by_id[identity[1]].append(row)
        source_summaries.append(context.summary())
        inputs.extend(context.inputs+context.external_inputs)
        inventories.update(context.inventories)
        owned=[c for c in candidates if c['source']==str(context.path)]
        for n,candidate in enumerate(owned):
            oid=candidate['id']
            if progress:
                progress(f"Tracing {context.path.name}: {n+1}/{len(owned)} {oid}")
            candidate['chain']=closure(context,('Unit',oid),target_context,prefix,casc=casc,max_objects=max_objects)
            if candidate['official_status']!='custom':
                candidate['chain']['issues'].append({'code':'official_baseline_incomplete','id':oid})
            if progress:
                progress(f"  {len(candidate['chain']['objects'])} objects; {len(candidate['chain']['issues'])} issues")
        # Source resolution caches are not shared between independent mods.
        del context
    if set(selected)-set(by_id) or excluded-set(by_id):
        raise ValueError('Selection contains IDs outside the candidate inventory')
    for candidate in candidates:
        oid=candidate['id'];variants=by_id[oid];choice=selected.get(oid)
        valid=choice in {candidate['source_key'],candidate['source'],Path(candidate['source']).name}
        candidate['selected']=oid not in excluded and (valid or (choice is None and len(variants)==1 and candidate['kind']=='playable'))
        candidate['selection_required']=len(variants)>1 and choice is None
        if choice is not None and not any(choice in {r['source_key'],r['source'],Path(r['source']).name} for r in variants):
            raise ValueError('Invalid selected source for unit: '+oid)
        if candidate['selection_required']:
            candidate['chain']['issues'].append({'code':'unit_source_choice_required','id':oid})
        candidate['chain']['executable']=candidate['selected'] and not candidate['chain']['issues']
    for candidate in candidates:
        for oid,choice in selected.items():
            if choice is not None and 'Unit:'+oid in candidate['chain']['objects'] and choice not in {
                    candidate['source_key'],candidate['source'],Path(candidate['source']).name}:
                candidate['chain']['issues'].append({'code':'chain_requires_other_selected_unit_version','id':oid,'selected_source':choice})
                candidate['chain']['executable']=False
    collisions = [{'id':oid,'choices':[{'source_key':r['source_key'],'source':r['source'],
                                     'fields':r['chain']['objects'].get('Unit:'+oid,{}).get('fields',{})} for r in rows],
                   'selected_source':selected.get(oid)} for oid,rows in sorted(by_id.items()) if len(rows)>1]
    result = {'schema_version':VERSION,'kind':'sc2_unit_migration_plan','prefix':prefix,
              'target':target_context.summary(),'sources':source_summaries,
              'selection':selection,'candidates':candidates,'excluded_official':excluded_official,
              'collisions':collisions,'inputs':list({r['path']:r for r in inputs}.values()),
              'inventories':inventories,
              'summary':{'candidates':len(candidates),'selected':sum(c['selected'] for c in candidates),
                         'executable':sum(c['chain']['executable'] for c in candidates),
                         'excluded_official':len(excluded_official),'collisions':len(collisions)}}
    # Store large field/source evidence once per source/object, with lightweight
    # per-root actions. This keeps whole-mod reports inspectable and bounded.
    evidence={}
    for candidate in candidates:
        source_evidence=evidence.setdefault(candidate['source'],{})
        for key,obj in candidate['chain']['objects'].items():
            details={k:v for k,v in obj.items() if k not in {'id','action','tag'}}
            if details:
                source_evidence[key]=details
            for field in details:
                obj.pop(field,None)
    result['object_evidence']=evidence
    resources=[r['evidence'] for c in candidates for r in c['chain']['resources'].values()
               if r.get('evidence',{}).get('path')]
    result['inputs']=list({row['path']:row for row in [*result['inputs'],*implementation,*resources]}.values())
    from sc2_archive import scan
    result['target_inventory']=scan(target_context.path)
    for row in result['inputs']:
        if digest(component_path(row['path']).read_bytes())!=row['sha256']:
            raise ValueError('Input changed during analysis: '+row['path'])
    result['plan_id']=digest(result)
    return result


def report_markdown(plan):
    lines = ['# 单位数据链迁移预检','', '此报告是静态预检；没有写入目标模组。','',
             '| 来源 | 官方依赖 | 候选 | 可执行 |','|---|---|---:|---:|']
    for source in plan['sources']:
        rows=[c for c in plan['candidates'] if c['source']==source['path']]
        lines.append(f"| {Path(source['path']).name} | {source['dependency_status']} | {len(rows)} | {sum(c['chain']['executable'] for c in rows)} |")
    lines += ['', '## 依赖与证据缺口','']
    for source in [*plan['sources'],plan['target']]:
        for problem in source['dependency_problems']+source['component_issues']:
            lines.append('- '+Path(source['path']).name+': '+str(problem))
    lines += ['', '## 候选单位','', '| 来源 | ID | 分类 | 官方判定 | 已选 | 问题数 |','|---|---|---|---|---|---:|']
    for row in plan['candidates']:
        lines.append(f"| {Path(row['source']).stem} | {row['id']} | {row['kind']} | {row['official_status']} | {row['selected']} | {len(row['chain']['issues'])} |")
    lines += ['', '## 同名来源选择','']
    for row in plan['collisions']:
        lines.append('- `'+row['id']+'`: '+', '.join(Path(c['source']).stem for c in row['choices']))
    counts=Counter(i['code'] for c in plan['candidates'] for i in c['chain']['issues'])
    lines += ['', '## 问题统计',''] + ['- '+k+': '+str(v) for k,v in counts.most_common()]
    lines += ['', '完整对象、字段来源、原始定义、资源、文本与 ID 映射见同目录 JSON。',
              '下一步：补齐官方证据，选择同名来源和待确认主单位，处理脚本/UI及资源问题后重新分析。','']
    return '\n'.join(lines)
