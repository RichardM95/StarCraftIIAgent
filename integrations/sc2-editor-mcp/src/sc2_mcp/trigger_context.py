"""Bounded GUI context over the existing dependency-aware trigger model."""
import json
from pathlib import Path
from .agent_bridge import root as workspace
from .errors import SC2Error
from .storage import digest
from .trigger_pipeline import target_for, controlled_files


def inputs(target):
    result = {p: v['sha256'] for p, v in target.inputs.items()}
    for component in [target.path, *[Path(n['path']) for n in target.graph['nodes'].values()]]:
        for pattern in ['*SC2Data/LocalizedData/*Strings.txt', 'Regions', 'Objects']:
            for path in component.glob(pattern):
                result[path.as_posix()] = digest(path.read_bytes())
    _, scripts = controlled_files(target, skip_generated=True)
    result.update({v['path']:v['sha256'] for v in scripts.values()})
    return result


def fingerprint(target):
    return digest(json.dumps(inputs(target), sort_keys=True).encode())


def local_document(target):
    found = [d for d in target.documents if d.path == target.path / 'Triggers']
    if len(found) != 1:
        raise SC2Error('trigger_context_missing', 'one registered local Triggers source is required')
    return found[0]


def definition(target, document, reference, kind='FunctionDef'):
    if isinstance(reference, list) and len(reference) == 3:
        key = tuple(reference)
        if key[1] != kind:
            raise SC2Error('trigger_reference_type', 'wrong reference type', expected=kind, actual=list(key))
        d, element = target.resolve(key, document)
        return d, key, element
    matches = [(d, k, e) for d in target.documents for k, e in d.elements.items()
               if k[1] == kind and reference in [e.findtext('Identifier'), d.name(k)]]
    if len(matches) != 1:
        raise SC2Error('trigger_definition_ambiguous', 'select one exact definition', query=reference,
                       candidates=[{'reference': list(k), 'source': str(d.path)} for d, k, _ in matches])
    return matches[0]


def describe_definition(target,d,key,limit):
    """Expose slot/type/role metadata directly; callers need no XML knowledge."""
    from sc2_triggers import ref_key
    from .trigger_bindings import Bindings
    e=d.elements[key]
    # Only type resolution is needed here, not an inventory of native signatures.
    types=Bindings(target,{},[])
    def typ(element,document,owner,tag):
        raw=element.find(tag+'/Type');ref=element.find(tag+'/TypeElement')
        return {'gui':raw.get('Value') if raw is not None else 'void',
                'base_type':types.raw_type(element,document,owner,tag),
                'type_element':list(ref_key(ref,owner)) if ref is not None else None}
    result={'reference':list(key),'name':d.name(key),'names':d.aliases(key),'source':str(d.path),'sha256':d.sha256,
            'flags':[c.tag for c in e if c.tag.startswith('Flag')],
            'return_type':typ(e,d,key,'ReturnType'),'parameters':[],'branches':[]}
    for ref in e.findall('Parameter'):
        if ref.get('Type')!='ParamDef':continue
        pk=ref_key(ref,key);pd,pe=target.resolve(pk,d)
        item={'reference':list(pk),'name':pd.name(pk),'type':typ(pe,pd,pk,'ParameterType'),
              'default':list(ref_key(pe.find('Default'),pk)) if pe.find('Default') is not None else None,
              'source':str(pd.path)}
        te=pe.find('ParameterType/TypeElement')
        if te is not None and te.get('Type')=='Preset':
            sk=ref_key(te,pk);sd,se=target.resolve(sk,pd);values=[]
            for c in se.findall('Item'):
                vk=ref_key(c,sk);vd,ve=target.resolve(vk,sd)
                values.append({'reference':list(vk),'name':vd.name(vk),'value':ve.findtext('Value')})
            item.update(preset_values=values[:limit],preset_values_total=len(values))
        result['parameters'].append(item)
    for ref in e.findall('SubFunctionType'):
        sk=ref_key(ref,key);_,se=target.resolve(sk,d)
        result['branches'].append({'reference':list(sk),'role':se.findtext('Identifier'),
                                  'kind':'condition' if se.find('Condition') is not None else 'action'})
    if key[1]=='Preset':result['base_type']=e.find('BaseType').get('Value') if e.find('BaseType') is not None else None
    return result


def context(service, project_id, selection=None, query=None, topic=None, depth=1, limit=40, mods_dir=None, library=None):
    from sc2_triggers import ref_key, references
    if not 0 <= depth <= 8 or not 1 <= limit <= 200:
        raise SC2Error('trigger_context_bounds', 'depth must be 0..8 and limit 1..200')
    _, root = service.record(project_id)
    target = target_for(root, mods_dir)
    if target.problems:
        raise SC2Error('trigger_dependency_incomplete', 'dependency context incomplete', diagnostics=target.problems)
    document = local_document(target)
    before = inputs(target)
    from .spatial import inspect_spatial
    resources=inspect_spatial(root,'regions')
    region_names={r['id']:next((c['attributes'].get('value') for c in r['children'] if c['kind']=='name'),None) for r in resources['regions']}
    referenced_regions=set()
    from .trigger_bindings import Bindings
    types=Bindings(target,{},[])
    def type_info(d,key,e,tag):
        raw=e.find(tag+'/Type');typed=e.find(tag+'/TypeElement')
        return {'gui':raw.get('Value') if raw is not None else None,'base_type':types.raw_type(e,d,key,tag),
                'type_element':list(ref_key(typed,key)) if typed is not None else None}
    if library is not None and library not in {'',*[k[0] for d in target.documents for k in d.elements]}:
        raise SC2Error('trigger_library_missing','library is not in the active dependency closure',library=library)
    game_strings={}
    def strings(d,key,element):
        component=str(d.component)
        if component not in game_strings:
            values={}
            for path in d.component.glob('*SC2Data/LocalizedData/GameStrings.txt'):
                for line in path.read_text('utf-8-sig').splitlines():
                    if '=' in line:
                        anchor,value=line.split('=',1)
                        values.setdefault(anchor,[]).append({'value':value,'source':str(path)})
            game_strings[component]=values
        anchors={v.text for v in element.findall('Value') if v.text}
        anchors.add('Param/Value/'+(f'lib_{key[0]}_' if key[0] else '')+key[2])
        return {**{a:v for a,v in d.names.items() if key[2] in a},
                **{a:v for a,v in game_strings[component].items() if a in anchors}}
    memberships = {}
    for key, element in document.elements.items():
        for child in element:
            if child.tag in {'Item','Event','Condition','Action','FunctionCall','Variable','Parameter','Value'} and child.get('Id'):
                memberships.setdefault(ref_key(child,key), []).append({'parent':list(key),'role':child.tag,
                                                                       'index':list(element).index(child)})
    roots=[(document.standard,document.root.find('Root'))]+[(lib.get('Id'),lib.find('Root')) for lib in document.root.findall('Library')]
    for lib,root_node in roots:
        if root_node is not None:
            for i,child in enumerate(root_node):
                if child.get('Type') and child.get('Id'):
                    memberships.setdefault(ref_key(child,(lib,'Root','')),[]).append({'parent':[lib,'Root',''],'role':child.tag,'index':i})
    def lineage(key, seen=None):
        seen = seen or set()
        if key in seen: return []
        parent = next((tuple(p['parent']) for p in memberships.get(key,[]) if p['role']=='Item'),None)
        return lineage(parent,seen|{key})+[{'reference':list(parent),'name':document.name(parent)}] if parent and parent[1]!='Root' else []
    def scope(key, seen=None):
        seen = seen or set()
        if key in seen:return None
        if key[1] in {'Trigger','FunctionDef'}:return list(key)
        if key[1] in {'Variable','ParamDef'}:
            return next((p['parent'] for p in memberships.get(key,[]) if p['parent'][1] in {'Trigger','FunctionDef'} and
                         p['role']==('Variable' if key[1]=='Variable' else 'Parameter')),None)
        return next((s for p in memberships.get(key,[]) if (s:=scope(tuple(p['parent']),seen|{key})) is not None),None)
    def summary(d, key, remaining, seen):
        element = d.elements[key]
        result = {'reference':list(key),'name':d.name(key),'source':str(d.path),
                  'disabled':element.find('Disabled') is not None,'parents':memberships.get(key,[]),
                  'scope':scope(key) if d is document else None,
                  'category_path':lineage(key) if d is document else [],
                  'strings':strings(d,key,element)}
        definition_ref=element.find('FunctionDef')
        if definition_ref is not None:
            dd, definition_element=target.resolve(ref_key(definition_ref,key),d)
            result['definition']={'reference':list(ref_key(definition_ref,key)),'name':definition_element.findtext('Identifier')}
            result['name']=result['name'] or result['definition']['name']
        for tag,field in [('VariableType','variable_type'),('ParameterType','parameter_type'),('ReturnType','return_type')]:
            if element.find(tag) is not None:result[field]=type_info(d,key,element,tag)
        value=element.find('Value');value_type=element.find('ValueType');value_id=element.find('ValueId')
        if value_type is not None and value is not None:
            typ=value_type.get('Type');text=value.text or ''
            parsed=(text=='true') if typ=='bool' and text in {'true','false'} else int(text) if typ=='int' and text.lstrip('-').isdigit() else text
            result['value']={'kind':'literal','type':typ,'value':parsed}
        elif value_type is not None and value_id is not None:
            result['value']={'kind':'resource','type':value_type.get('Type'),'id':value_id.get('Id')}
            if value_type.get('Type')=='region':
                result['value']['name']=region_names.get(value_id.get('Id'));referenced_regions.add(value_id.get('Id'))
        for tag,kind in [('Preset','preset'),('Variable','variable'),('Parameter','parameter'),('FunctionCall','call')]:
            ref=element.find(tag)
            if key[1]=='Param' and ref is not None:
                vk=ref_key(ref,key);vd,ve=target.resolve(vk,d)
                result['value']={'kind':kind,'reference':list(vk),'name':vd.name(vk)}
                if kind=='preset':result['value']['value']=ve.findtext('Value')
        slot=element.find('ParameterDef')
        if slot is not None:
            sk=ref_key(slot,key);sd,se=target.resolve(sk,d)
            result['parameter_slot']={'reference':list(sk),'name':sd.name(sk),'type':type_info(sd,sk,se,'ParameterType')}
        if element.find('ScriptCode') is not None:
            text=element.findtext('ScriptCode') or ''
            result.update(custom_script=text[:2000],custom_script_truncated=len(text)>2000)
        branch=element.find('SubFunctionType')
        if branch is not None:
            _, subtype=target.resolve(ref_key(branch,key),d)
            result['branch_role']=subtype.findtext('Identifier')
        if remaining and (str(d.path),key) not in seen:
            children=[]
            for child in element:
                if child.get('Type') and child.get('Id') and child.tag not in {'FunctionDef','ParameterDef','SubFunctionType'}:
                    ck=ref_key(child,key)
                    try:
                        cd, _ = target.resolve(ck,d)
                        children.append({'role':child.tag, **summary(cd,ck,remaining-1,seen|{(str(d.path),key)})})
                    except ValueError as exc:
                        children.append({'role':child.tag,'reference':list(ck),'error':str(exc)})
            result['children']=children[:limit]
            result['children_total']=len(children)
        return result
    if selection is not None and (not isinstance(selection,list) or len(selection)!=3):
        raise SC2Error('trigger_reference_invalid','selection must be [Library, Type, Id]')
    keys = [tuple(selection)] if selection else [k for d in target.documents for k in d.elements
        if (d is document if library in {None,''} else k[0]==library) and k[1] in {'Category','Trigger','FunctionDef','Variable'}]
    nodes=[]
    for key in keys[:limit]:
        d, _=target.resolve(key,document)
        nodes.append(summary(d,key,depth,set()))
    definitions=[]
    if query:
        matches=[(d,k) for d in target.documents for k,e in d.elements.items()
                 if k[1] in {'FunctionDef','Preset'} and (library is None or k[0]==library) and d.matches(k,query)]
        for d,key in matches[:limit]:
            definitions.append(describe_definition(target,d,key,limit))
    elif selection and selection[1] in {'FunctionDef','Preset'}:
        d,_=target.resolve(tuple(selection),document)
        definitions.append(describe_definition(target,d,tuple(selection),limit))
    incoming=[]
    if selection:
        wanted=tuple(selection)
        selected_doc,_=target.resolve(wanted,document)
        for d in target.documents:
            for key,element in d.elements.items():
                for ref in references(element,key):
                    if ref==wanted and (wanted[0] or d.path==selected_doc.path):
                        entry={'source':str(d.path),'reference':list(key)}
                        if entry not in incoming:incoming.append(entry)
    examples=[]
    if topic:
        cases=json.loads((workspace/'wiki/reference/trigger-cases.json').read_text('utf-8'))
        examples=[{**c,'local_graph':c.get('local_graph',[])[:limit],
                   'local_graph_total':len(c.get('local_graph',[])),
                   'compatibility':'resource rebinding and active dependency validation required'}
                  for c in cases['cases'] if c['mechanism']==topic][:limit]
    target.refresh()
    if target.problems:
        raise SC2Error('trigger_context_stale','source changed while reading',diagnostics=target.problems)
    if before!=inputs(target):
        raise SC2Error('trigger_context_stale','source changed while reading; reread selected nodes')
    library_report=target.libraries()
    library_summary={'status':library_report['status'],'problems':library_report['problems'],
        'libraries':[{k:v for k,v in item.items() if k in {'library','source','sha256','source_class','origin'}}
                     for item in library_report['libraries']]}
    dependency_fingerprints=[]
    for node in target.graph['nodes'].values():
        component=Path(node['path'])
        rows={p:sha for p,sha in before.items() if Path(p).is_relative_to(component)}
        if component!=target.path:dependency_fingerprints.append({'component':str(component),'files':len(rows),
            'sha256':digest(json.dumps(rows,sort_keys=True).encode())})
    source_inputs={p:sha for p,sha in before.items() if Path(p).is_relative_to(root)}
    shown_regions=sorted(resources['regions'],key=lambda r:r['id'] not in referenced_regions)
    if query:shown_regions=[r for r in shown_regions if query.casefold() in (region_names.get(r['id']) or '').casefold() or query==r['id']]
    return {'project_id':project_id,'fingerprint':digest(json.dumps(before,sort_keys=True).encode()),'inputs':source_inputs,'input_count':len(before),
            'dependency_fingerprints':dependency_fingerprints,'libraries':library_summary,
            'nodes':nodes,'nodes_total':len(keys),'definitions':definitions,'examples':examples,
            'incoming':incoming[:limit],'incoming_total':len(incoming),'display_truncated':len(keys)>limit or len(incoming)>limit or len(shown_regions)>limit,
            'resources':{'regions':[{'id':r['id'],'name':region_names.get(r['id']),'source':r['source'],'line':r['line'],
                                     'shape_count':sum(c['kind']=='shape' for c in r['children'])} for r in shown_regions[:limit]],
                         'diagnostics':resources['diagnostics'],'regions_total':len(resources['regions'])}}
