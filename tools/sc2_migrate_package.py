"""Verified migration packages and staged, reversible component publication."""
from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

from sc2_archive import scan, no_links, allowed_target
from sc2_components import component_path, require_editable
from sc2_publication import staged_directory, publish_component
from sc2_migrate_catalog import digest, elements, semantic_index, render_node, encode_node, Catalog, semantic_node
from sc2_migrate_links import links, TEXT_REF, DATA_REF
from sc2_migrate import (VERSION, safe_relative, locate, decode, Resources, component_listing,
                         ComponentLoader, Context)

MANIFEST = 'migration-manifest.json'


def verify_inputs(plan, *, skip_target=False):
    target=Path(plan['target']['path']).resolve()
    for root,expected in plan.get('inventories',{}).items():
        if skip_target and Path(root).resolve()==target:
            continue
        if component_listing(root)!=expected:
            raise ValueError('Migration input inventory changed: '+root)
    for row in plan['inputs']:
        if skip_target and Path(row['path']).resolve().is_relative_to(target):
            continue
        path = component_path(row['path'])
        if not path.is_file() or digest(path.read_bytes()) != row['sha256']:
            raise ValueError('Migration input changed: ' + row['path'])


def check_plan(plan):
    if plan.get('schema_version') != VERSION or plan.get('kind') != 'sc2_unit_migration_plan':
        raise ValueError('Unsupported migration plan')
    unsigned = {k:v for k,v in plan.items() if k != 'plan_id'}
    if digest(unsigned) != plan.get('plan_id'):
        raise ValueError('Plan integrity mismatch; rerun analysis')
    chosen = [c for c in plan['candidates'] if c['selected']]
    if not chosen:
        raise ValueError('No selected units')
    if any(not c['chain']['executable'] for c in chosen):
        raise ValueError('Selected units have unresolved migration issues')
    return chosen


def lookup_node(node, path):
    parts = path.strip('|').split('|') if path else []
    current, i = node, 0
    while i < len(parts):
        tag = parts[i]
        if tag.startswith('@') or not tag:
            break
        candidates = [c for c in elements(current) if c['@tag']==tag]
        if not candidates:
            raise ValueError('Reference path no longer exists: ' + path)
        array = len(candidates)>1 or tag.endswith('Array') or any(semantic_index(c) is not None for c in candidates)
        i += 1
        if array:
            if i >= len(parts):
                raise ValueError('Missing array position: ' + path)
            index = parts[i]; i+=1
            current = next((c for n,c in enumerate(candidates) if (semantic_index(c) or str(n))==index), None)
            if current is None:
                raise ValueError('Reference index no longer exists: ' + path)
        else:
            current = candidates[0]
    attr = parts[i][1:] if i<len(parts) and parts[i].startswith('@') else None
    return current, attr


def rewrite_node(node, identity, mapping, text_mapping):
    """Edit typed link locations only, using the effective array lookup paths."""
    result = copy.deepcopy(node)
    result['attributes']['id'] = mapping[':'.join(identity)]
    result['attributes'].pop('parent',None)
    rows, diagnostics = links(result,*identity)
    if diagnostics:
        raise ValueError('Dynamic references cannot be renamed: ' + str(diagnostics))
    handled = set()
    for row in rows:
        key = row['target']
        new = text_mapping.get(key[5:]) if key.startswith('text:') else mapping.get(key)
        if not new or row.get('role')=='parent':
            continue
        parent, attr = lookup_node(result,row.get('lookup',''))
        attrs = parent['attributes']
        attr = attr or next((a for a in ('Link','value','Value') if a in attrs),None)
        if attr is None:
            raise ValueError('Cannot locate reference attribute: ' + str(row))
        old = key.split(':',1)[1]
        value = attrs[attr]
        if value == old:
            attrs[attr] = new
        else:
            attrs[attr] = re.sub(r'(?<![A-Za-z0-9_])'+re.escape(old)+r'(?![A-Za-z0-9_])',lambda _:new,value)
        handled.add((id(parent),attr))
    # Reject catalog IDs in unknown literal positions instead of silently leaving
    # source references behind. Editor labels and generated target IDs are excluded.
    old_ids = {key.split(':',1)[1] for key,new in mapping.items() if key.split(':',1)[1]!=new}
    def audit(current):
        for attr,value in current.get('attributes',{}).items():
            if attr not in {'id','parent','index'} and value in old_ids and (id(current),attr) not in handled:
                raise ValueError('Unclassified reference requires review: '+current['@tag']+'/@'+attr+'='+value)
            if '##' in value or '$' in value:
                raise ValueError('Unexpanded token/expression: '+value)
            if attr in {'Send','Terms','Target','Subject'} and set(re.findall(r'[A-Za-z0-9_]+',value)) & old_ids:
                raise ValueError('Unclassified actor message reference: '+value)
        for child in elements(current):
            audit(child)
    audit(result)
    return result


def rewrite_text(value, mapping, text_mapping):
    def data(match):
        raw=match.group(0);parts=match.group(1).split(',',2)
        if len(parts)>=2:
            new=mapping.get(parts[0]+':'+parts[1])
            if new:
                raw=raw.replace(match.group(1),','.join([parts[0],new,*parts[2:]]),1)
        return raw
    value=DATA_REF.sub(data,value)
    def text(match):
        old=match.group(1);new=text_mapping.get(old)
        return match.group(0).replace(old,new,1) if new else match.group(0)
    return TEXT_REF.sub(text,value)


@lru_cache(maxsize=1)
def catalog_schema():
    from lxml import etree
    return etree.XMLSchema(etree.parse(str(Path(__file__).with_name('schemas')/'sc2-xsd/Catalog.xsd')))


def validate_payloads(files):
    """Validate generated Catalog XML with the existing formal workspace schema."""
    from lxml import etree
    schema=catalog_schema()
    for relative,raw in files.items():
        if relative.lower().startswith('base.sc2data/gamedata/') and relative.lower().endswith('.xml'):
            document=etree.fromstring(raw)
            if not schema.validate(document):
                raise ValueError('Generated Catalog XSD validation failed: '+relative+': '+str(schema.error_log.last_error))
            for element in document.iter():
                if not isinstance(element.tag,str):
                    continue
                if any(not value.isascii() for value in element.attrib.values()):
                    raise ValueError('Non-ASCII XML attribute in '+relative)


def validate_target_semantics(manifest,files):
    """Re-resolve exported records under the actual target defaults/dependencies."""
    target=Context(Path(manifest['target']['path']),**manifest['target'].get('context',{}))
    if not target.complete:
        raise ValueError('Target dependencies are incomplete')
    additions=[]
    desired={}
    for relative,raw in files.items():
        if relative.startswith('Base.SC2Data/GameData/') and relative.endswith('.xml'):
            root=encode_node(ET.fromstring(raw))
            for node in elements(root):
                desired[(family_name(node['@tag']),node['attributes']['id'])]=node
            additions.append({'source_id':'migration:generated','path':relative,'nodes':[root]})
    existing_files=[]
    # Remove prior copies of these exact IDs when verifying an idempotent replay.
    for record in target.catalog.files:
        record=copy.deepcopy(record)
        root=record['nodes'][0]
        root['children']=[n for n in root.get('children',[]) if '@tag' not in n or
                          (family_name(n['@tag']),n.get('attributes',{}).get('id')) not in desired]
        existing_files.append(record)
    generated={'id':'migration:generated','name':'Generated','fingerprint':digest(sorted(desired))}
    resolved=Catalog([*target.sources,generated],existing_files+additions)
    for identity,wanted in desired.items():
        if semantic_node(resolved.effective(*identity))!=semantic_node(wanted):
            raise ValueError('Target default semantics differ for '+':'.join(identity))


def export_package(plan, output, *, casc=None):
    chosen=check_plan(plan)
    verify_inputs(plan)
    target=Path(plan['target']['path']).resolve()
    output=Path(output).resolve()
    no_links(output)
    if output.exists() or any(output==p or output.is_relative_to(p) or p.is_relative_to(output)
                              for p in [target,*[Path(s['path']).resolve() for s in plan['sources']]]):
        raise ValueError('Package output must be new and disjoint from all components')
    mapping_by_source, objects_by_source = {}, {}
    files, resources, texts, target_objects = {}, {}, {}, {}
    for candidate in chosen:
        sid=candidate['source'];chain=candidate['chain']
        mapping=mapping_by_source.setdefault(sid,{})
        objects=objects_by_source.setdefault(sid,{})
        for key,obj in chain['objects'].items():
            obj={**plan.get('object_evidence',{}).get(sid,{}).get(key,{}),**obj}
            # The most conservative action wins when multiple roots share a node.
            old=objects.get(key)
            if old is None or obj['action']=='copy':
                objects[key]=obj
            mapping[key]=objects[key]['id']
    for sid,objects in objects_by_source.items():
        mapping=mapping_by_source[sid]
        # A copied descendant requires its referencing ancestors to be copied too.
        all_edges=[e for c in chosen if c['source']==sid for e in c['chain']['edges']]
        changed=True
        while changed:
            changed=False
            for edge in all_edges:
                src,dst=objects.get(edge.get('source')),objects.get(edge.get('target'))
                if src and src['action']=='reuse' and dst and dst['action']=='copy':
                    raise ValueError('Combined selection changes reuse semantics; reanalyze selected roots')
        owned_texts={k:v for c in chosen if c['source']==sid for k,v in c['chain']['texts'].items()}
        text_mapping={}
        for record in owned_texts.values():
            key=record['key'];parts=key.split('/',2)
            canonical_id=mapping.get(parts[0]+':'+parts[2]) if len(parts)==3 else None
            if canonical_id and parts[1] in {'Name','Tooltip','EditorPrefix','EditorSuffix','Hotkey'}:
                text_mapping[key]=parts[0]+'/'+parts[1]+'/'+canonical_id
            else:
                text_mapping[key]='Migration/'+plan['prefix']+Path(sid).stem+'/'+key
        for key,obj in objects.items():
            if obj['action']!='copy':
                continue
            identity=tuple(key.split(':',1))
            parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,insert_pis=True))
            node=encode_node(ET.fromstring(obj['effective_xml'],parser=parser))
            renamed=rewrite_node(node,identity,mapping,text_mapping)
            full_key=identity[0]+':'+obj['id']
            if full_key in target_objects and target_objects[full_key]!=renamed:
                raise ValueError('Generated ID collision: '+full_key)
            target_objects[full_key]=renamed
        for record in owned_texts.values():
            relative=record['locale']+'.SC2Data/LocalizedData/'+record['file']
            key=text_mapping[record['key']]
            value=rewrite_text(record['value'],mapping,text_mapping)
            texts.setdefault(relative,{})[key]=value
        for candidate in chosen:
            if candidate['source']!=sid:
                continue
            for row in candidate['chain']['resources'].values():
                if row['action']=='reuse':
                    continue
                evidence=row['evidence']
                if 'path' in evidence:
                    raw=component_path(evidence['path']).read_bytes()
                elif casc and 'casc_path' in evidence:
                    raw=casc.read(evidence['casc_path'])
                else:
                    raise ValueError('Explicit CASC reader required to export '+row['path'])
                if raw is None or digest(raw)!=row['sha256']:
                    raise ValueError('Resource changed since analysis: '+row['path'])
                relative=(row['locale']+'.SC2Assets/' if row.get('locale') else 'Base.SC2Assets/')+row['path']
                if relative in resources and resources[relative]!=raw:
                    raise ValueError('Cross-source resource conflict: '+relative)
                resources[relative]=raw
    grouped={}
    for key,node in sorted(target_objects.items()):
        fam=key.split(':',1)[0]
        grouped.setdefault(fam,[]).append(render_node(node))
    for fam,nodes in grouped.items():
        files['Base.SC2Data/GameData/'+fam+'Data.xml']=('<?xml version="1.0" encoding="utf-8"?>\n<Catalog>\n'+'\n'.join(nodes)+'\n</Catalog>\n').encode()
    for relative,values in texts.items():
        # Preserve one source encoding per language/file; no replacement decoding.
        record=next(v for c in chosen for v in c['chain']['texts'].values()
                    if relative==v['locale']+'.SC2Data/LocalizedData/'+v['file'])
        files[relative]=bytes.fromhex(record['bom'])+''.join(k+'='+v+'\n' for k,v in sorted(values.items())).encode(record['encoding'])
    files.update(resources)
    validate_payloads(files)
    validate_target_semantics(plan,files)
    verify_inputs(plan)
    manifest={'schema_version':VERSION,'kind':'sc2_unit_migration_package','plan_id':plan['plan_id'],
              'target':plan['target'],'sources':plan['sources'],'selection':plan['selection'],
              'inputs':plan['inputs'],'inventories':plan['inventories'],
              'target_inventory':plan['target_inventory'],'id_mapping':mapping_by_source,
              'unit_roots':[{'source':c['source'],'id':c['id']} for c in chosen],
              'chains':[{'source':c['source'],'root':c['chain']['root'],
                         'references':c['chain']['edges'],'resources':c['chain']['resources'],
                         'texts':c['chain']['texts'],'objects':c['chain']['objects']} for c in chosen],
              'object_evidence':{sid:{key:plan['object_evidence'][sid][key] for key in objects
                                      if key in plan.get('object_evidence',{}).get(sid,{})}
                                 for sid,objects in objects_by_source.items()},
              'files':{name:{'sha256':digest(raw),'size':len(raw)} for name,raw in files.items()}}
    manifest['package_id']=digest(manifest)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.migration-package-',dir=output.parent) as stage:
        stage=Path(stage)
        for relative,raw in files.items():
            path=stage/str(safe_relative(relative));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        (stage/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        no_links(output)
        if output.exists():
            raise ValueError('Package output appeared during export')
        stage.rename(output)
    return manifest


def read_package(package):
    root=Path(package).resolve();no_links(root)
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('schema_version')!=VERSION or manifest.get('kind')!='sc2_unit_migration_package':
        raise ValueError('Unsupported migration package')
    if digest({k:v for k,v in manifest.items() if k!='package_id'})!=manifest.get('package_id'):
        raise ValueError('Package manifest integrity mismatch')
    files={}
    for relative,expected in manifest['files'].items():
        allowed=(re.fullmatch(r'Base\.SC2Data/GameData/[^/]+\.xml',relative)
                 or re.fullmatch(r'[A-Za-z]{4}\.SC2Data/LocalizedData/(?:GameStrings|ObjectStrings|GameHotkeys)\.txt',relative)
                 or re.fullmatch(r'(?:Base|[A-Za-z]{4})\.SC2Assets/.+',relative))
        if not allowed:
            safe_relative(relative)
            raise ValueError('Unsupported package content: '+relative)
        path=root/str(safe_relative(relative));no_links(path)
        raw=path.read_bytes()
        if len(raw)!=expected['size'] or digest(raw)!=expected['sha256']:
            raise ValueError('Package payload changed: '+relative)
        files[relative]=raw
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual!=set(files)|{MANIFEST}:
        raise ValueError('Package contains unlisted files')
    validate_payloads(files)
    return manifest,files


def preview_import(package,target=None):
    manifest,files=read_package(package)
    target=Path(target or manifest['target']['path']).resolve()
    require_editable(target);allowed_target(target)
    if target!=Path(manifest['target']['path']).resolve():
        raise ValueError('Package is bound to its analyzed target; reanalyze another target')
    if not target.is_dir():
        raise ValueError('Target must be an existing Components directory')
    from sc2_paths import load_project_config,project_identity_path,find_project_mods
    workspace=Path(__file__).resolve().parents[1]
    config=load_project_config(workspace)
    if config.get('project',{}).get('source_mode')=='workspace_copy' and project_identity_path(workspace,config)==target:
        actual=find_project_mods(workspace,config=config)
        if not actual or actual[0].resolve()!=target:
            raise ValueError('Target is the deployed copy; analyze the configured workspace source instead')
    expected=scan(target)
    receipt=target/'.sc2-migration'/(manifest['package_id']+'.json')
    replay=False
    if expected!=manifest['target_inventory']:
        if not receipt.is_file():
            raise ValueError('Target changed since analysis; reanalyze it')
        recorded=json.loads(receipt.read_text(encoding='utf-8'))
        if recorded.get('package_id')!=manifest['package_id'] or without_receipts(expected)!=recorded.get('target_inventory'):
            raise ValueError('Target differs from verified previous import')
        replay=True
    # Dependencies and original sources remain immutable even during replay.
    verify_inputs(manifest,skip_target=replay)
    validate_target_semantics(manifest,files)
    outputs,conflicts={},[]
    for relative,raw in files.items():
        current=locate(target,relative)
        actual_relative=Path(current).relative_to(target).as_posix()
        if not current.is_file():
            outputs[actual_relative]=raw
            continue
        old=current.read_bytes()
        if old==raw:
            continue
        if relative.lower().startswith('base.sc2data/gamedata/') and relative.lower().endswith('.xml'):
            tree=ET.fromstring(old);addition=ET.fromstring(raw)
            existing={(family_name(n.tag),n.get('id')):n for n in tree if isinstance(n.tag,str)}
            for node in addition:
                key=(family_name(node.tag),node.get('id'))
                if key in existing:
                    if canonical(existing[key])!=canonical(node):
                        conflicts.append({'code':'target_object_conflict','file':relative,'id':key[1]})
                else:
                    tree.append(node)
            merged=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
            if merged!=old:
                outputs[actual_relative]=merged
        elif relative.endswith('.txt'):
            text,encoding,bom=decode(old);added=decode(raw)[0]
            values=dict(line.split('=',1) for line in text.splitlines() if '=' in line and not line.lstrip().startswith(('//','#')))
            append=[]
            for line in added.splitlines():
                key,value=line.split('=',1)
                if key in values and values[key]!=value:
                    conflicts.append({'code':'target_text_conflict','file':relative,'key':key})
                elif key not in values:
                    append.append(line)
            if append:
                newline='\r\n' if '\r\n' in text else '\n'
                outputs[actual_relative]=bytes.fromhex(bom)+(text+(newline if text and not text.endswith(('\r','\n')) else '')+newline.join(append)+newline).encode(encoding)
        else:
            conflicts.append({'code':'target_resource_conflict','file':relative})
    # A same ID in a different catalog file is still a conflict.
    ids={}
    for path in (target/'Base.SC2Data/GameData').glob('*.xml'):
        for node in parse_xml_safe(path):
            if isinstance(node.tag,str) and node.get('id'):
                ids.setdefault((family_name(node.tag),node.get('id')),[]).append(path.relative_to(target).as_posix())
    for relative,raw in files.items():
        if relative.startswith('Base.SC2Data/GameData/') and relative.endswith('.xml'):
            for node in ET.fromstring(raw):
                other=[p for p in ids.get((family_name(node.tag),node.get('id')),[]) if p.casefold()!=relative.casefold()]
                if other:
                    conflicts.append({'code':'duplicate_target_id','id':node.get('id'),'files':other})
    validate_payloads(outputs)
    locales={relative.split('.')[0] for relative in files if re.match(r'[A-Za-z]{4}\.SC2Data/',relative)}
    registration=locate(target,'ComponentList.SC2Components')
    if locales:
        if not registration.is_file():
            raise ValueError('Target text component registration is missing')
        root=ET.fromstring(registration.read_bytes())
        present={n.get('Locale','').casefold() for n in root if n.get('Type')=='text'}
        missing=sorted(loc for loc in locales if loc.casefold() not in present)
        for locale in missing:
            ET.SubElement(root,'DataComponent',{'Type':'text','Locale':locale}).text='GameText'
        if missing:
            outputs[registration.relative_to(target).as_posix()]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    return {'package':str(Path(package).resolve()),'package_id':manifest['package_id'],
            'target':str(target),'expected':expected,'outputs':outputs,'conflicts':conflicts,
            'changed_files':list(outputs),'executable':not conflicts,'manifest':manifest,'replay':replay}


def without_receipts(inventory):
    return {**inventory,'entries':{k:v for k,v in inventory['entries'].items()
                                  if k!='.sc2-migration' and not k.startswith('.sc2-migration/')}}


def family_name(tag):
    from sc2_migrate_catalog import family
    return family(tag)


def canonical(node):
    return (node.tag,tuple(sorted(node.attrib.items())),(node.text or '').strip(),
            tuple(canonical(n) for n in node if isinstance(n.tag,str)))


def parse_xml_safe(path):
    return ET.parse(path).getroot()


def apply_import(preview, *, apply=False, before_publish=None):
    if not apply:
        return {'applied':False,'changed_files':preview['changed_files'],'conflicts':preview['conflicts']}
    if preview['conflicts']:
        raise ValueError('Unresolved import conflicts')
    # Never trust mutable in-memory payloads from a previous preview.
    fresh=preview_import(preview['package'],preview['target'])
    if (fresh['package_id']!=preview['package_id'] or fresh['expected']!=preview['expected']
            or fresh['outputs']!=preview['outputs'] or fresh['conflicts']):
        raise ValueError('Preview is stale; regenerate it')
    target=Path(preview['target'])
    if not fresh['outputs']:
        return {'applied':False,'unchanged':True,'changed_files':[]}
    with staged_directory(target) as stage:
        staged=stage/target.name
        shutil.copytree(target,staged)
        for relative,raw in fresh['outputs'].items():
            path=staged/str(safe_relative(relative));path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        validate_payloads({p.relative_to(staged).as_posix():p.read_bytes() for p in (staged/'Base.SC2Data/GameData').glob('*.xml')})
        if before_publish:
            before_publish(staged)
        receipt=staged/'.sc2-migration'/(fresh['package_id']+'.json')
        inventory=without_receipts(scan(staged))
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps({'package_id':fresh['package_id'],'target_inventory':inventory},indent=2),encoding='utf-8')
        read_package(fresh['package']);verify_inputs(fresh['manifest'],skip_target=fresh['replay'])
        if scan(target)!=fresh['expected']:
            raise ValueError('Target changed before publication')
        backup=publish_component(staged,target,expected=fresh['expected'],fingerprint=scan)
    return {'applied':True,'changed_files':fresh['changed_files'],'backup':str(backup)}
