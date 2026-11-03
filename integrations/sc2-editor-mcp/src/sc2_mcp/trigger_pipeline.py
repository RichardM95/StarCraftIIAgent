"""Shared CLI/MCP orchestration; generated artifacts never enter source transactions."""
from __future__ import annotations
import json
from pathlib import Path
import re
import uuid
from .agent_bridge import root as workspace, project_runtime
from .errors import SC2Error
from .storage import safe_path, digest, write_json, guard_absolute_path
from .trigger_writer import plan_write, validate_editor_library_layout
from .trigger_codegen import Generator
from .galaxy_frontend import check_files


def target_for(root, mods_dir=None):
    from sc2_paths import load_project_config, resolve_configured_path
    from sc2_triggers import Target
    config=load_project_config(workspace)
    paths=config.get('paths',{})
    mods=Path(mods_dir) if mods_dir else resolve_configured_path(workspace,paths['mods_dir'])
    install=resolve_configured_path(workspace,paths['sc2_install_dir']) if paths.get('sc2_install_dir') else None
    return Target(root,mods,install/'Campaigns' if install else None)


def write(service,project_id,operations,expected_sha256=None,locale='zhCN',mods_dir=None):
    def plan(root,roots,context):
        from sc2_triggers import Document, check
        changes=plan_write(root,operations,expected_sha256,locale)
        if not changes:return {}
        target=target_for(root,mods_dir)
        # Overlay the candidate in the same dependency-aware checker, without disk writes.
        old=next((d for d in target.documents if d.path==root/'Triggers'),None)
        if old is None:raise SC2Error('trigger_source_missing','registered Triggers source required')
        new=Document(old.path,raw=changes.get('Triggers',old.path.read_bytes()))
        validate_editor_library_layout(new.root)
        target.documents=[new if d is old else d for d in target.documents]
        for key,providers in list(target.providers.items()):
            target.providers[key]=[(d,e) for d,e in providers if d is not old]
        for key,e in new.elements.items():
            target.providers[('' if key[0] else str(new.path),*key)].append((new,e))
        report=check(target)
        if report['errors']:raise SC2Error('trigger_validation_failed','candidate GUI validation failed',diagnostics=report['errors'])
        return changes
    return service.prepare_domain(project_id,'trigger_write',plan)


def controlled_files(target, skip_generated=False):
    """SC2 virtual script namespace, target overrides dependencies in declared order."""
    files={}; sources={}
    components=[target.path]+[Path(n['path']) for n in target.graph['nodes'].values() if Path(n['path'])!=target.path]
    from sc2_components import component_path
    for component in components:
        component=component_path(component)
        for path in sorted(component.rglob('*.galaxy')):
            relative=path.relative_to(component).as_posix()
            if skip_generated and (path.name.casefold()=='mapscript.galaxy' or re.fullmatch(r'Lib[0-9A-Fa-f]{8}(?:_h)?\.galaxy',path.name,re.I)):
                continue
            if relative.casefold().startswith('base.sc2data/'):relative=relative[len('Base.SC2Data/'):]
            if any(p.casefold() in {'publish','_codex_backups','.git'} for p in Path(relative).parts):continue
            virtual=relative.lower()
            if virtual not in files:
                raw=path.read_bytes();files[virtual]=raw.decode('utf-8-sig');sources[virtual]={'path':str(path),'sha256':digest(raw)}
    return files,sources


def native_supplement(target, files):
    """GUI-derived typing for known gaps, ONLY for static analysis.

    DataTableInstance is int in the same build's generated NativeLib wrappers.
    GUI types do not establish engine ABI. Never emit these into a runtime entry.
    No unknown symbol or arbitrary GUI native is synthesized into a declaration.
    """
    names={'DataTableInstanceSetInt','DataTableInstanceGetInt','UnitSetInfoButtonTooltip',
           'UnitClearInfoButtonTooltip','StringToDateTime','UnitLootDropPoint'}
    from .script import _strip_comments_strings
    declared=set()
    for text in files.values():
        masked,_=_strip_comments_strings(text)
        declared.update(re.findall(r'(?m)^\s*(?!return\b)(?:native\s+)?\w+\s+(\w+)\s*\(',masked))
    lines=[];evidence=[]
    def typ(element,tag,default=None):
        child=element.find(tag+'/Type');value=child.get('Value') if child is not None else default
        value={'gamelink':'string','datatable':'int'}.get(value,value)
        if value not in {'void','int','string','text','unit','point','datetime'}:
            raise SC2Error('native_supplement_unsupported','unsupported official native signature',type=value)
        return value
    for d in target.documents:
        if d.standard!='Ntve':continue
        for key,e in d.elements.items():
            name=e.findtext('Identifier')
            if key[1]!='FunctionDef' or name not in names or name in declared:continue
            if e.find('FlagNative') is None:raise SC2Error('native_supplement_unsupported','official binding is not native')
            args=[]
            for i,ref in enumerate(e.findall('Parameter')):
                pd,p=target.resolve((ref.get('Library',key[0]),ref.get('Type'),ref.get('Id')),d)
                args.append(typ(p,'ParameterType')+' p'+str(i))
            lines.append('native '+typ(e,'ReturnType','void')+' '+name+'('+', '.join(args)+');')
            evidence.append({'path':str(d.path),'sha256':d.sha256,'node':list(key),'name':name,
                             'scope':'GUI-derived static typing only; engine ABI unverified'})
    return '\n'.join(lines)+'\n',evidence


def generate(service,project_id,mods_dir=None,runtime_probe=False):
    _,root=service.record(project_id)
    target=target_for(root,mods_dir)
    files,sources=controlled_files(target,skip_generated=True)
    external=[];official_headers=[];official_init=[]
    loading=target.graph.get('loading_order',{})
    ordered=loading.get('components',[]) if isinstance(loading,dict) else loading
    order={str(p).casefold():i for i,p in enumerate(ordered)}
    for d in sorted(target.documents,key=lambda d:order.get(str(d.component).casefold(),0)):
        meta=target.graph['nodes'].get(str(d.component).casefold(),{})
        if d.standard and d.standard!='Ntve' and meta.get('origin')=='casc':
            relative=d.path.relative_to(d.component).as_posix().lower()
            if relative.startswith('base.sc2data/'):relative=relative[len('base.sc2data/'):]
            script=str(Path(relative).with_suffix('.galaxy')).replace('\\','/')
            if script not in files:raise SC2Error('trigger_official_script_missing','official GUI library requires matching generated Galaxy',library=d.standard)
            external.append(d.standard);official_headers.append(script)
            official_init.append('lib'+d.standard+'_InitLib();')
    proof_token=uuid.uuid4().hex[:12] if runtime_probe else None
    entry='agentgenerated.galaxy'
    # Core natives are engine-provided declarations, not GUI-generated wrappers.
    headers=[p for p in ('triggerlibs/natives_missing.galaxy','triggerlibs/nativelib.galaxy') if p in files]+official_headers
    from .trigger_bindings import Bindings
    bindings=Bindings(target,files,headers)
    generated=Generator(target,external,bindings).generate(proof_token=proof_token)
    supplement,evidence=native_supplement(target,files)
    if evidence:
        files['agent_native_supplement.galaxy']=supplement
    prefix=''.join('include '+json.dumps(p[:-7])+'\n' for p in headers)
    if 'triggerlibs/nativelib.galaxy' in headers:
        generated['source']=generated['source'].replace('void InitMap() {','void InitMap() {\n'+'\n'.join(['libNtve_InitLib();']+official_init),1)
    offset=len(headers)
    for m in generated['source_map']:m['start']+=offset;m['end']+=offset
    files[entry]=prefix+generated['source']
    target.refresh()
    if target.problems:raise SC2Error('trigger_inputs_changed','dependency inputs incomplete or changed',diagnostics=target.problems)
    folder=guard_absolute_path((getattr(service,'runtime_root',None) or project_runtime(root))/'galaxy-builds'/uuid.uuid4().hex)
    if folder.is_relative_to(root):raise SC2Error('unsafe_build_root','build artifacts cannot be in source')
    folder.mkdir(parents=True,exist_ok=False)
    manifest={'schema':1,'project_id':project_id,'root':str(root),'entry':entry,'complete':True,'mods_dir':str(target.graph['mods_dir']),
              'inputs':target.inputs,'scripts':sources,'source_map':generated['source_map'],'resources':generated['resource_inputs'],
              'files':files,'native_supplements':evidence,'script_collection':'gui_inputs',
              'used_mappings':generated['used_mappings'],
              'mapping_inventory':{'declared_names':len(bindings.index),'active_files':sorted(bindings.active),
                                   'aliases':bindings.aliases,'unresolved_definitions':bindings.unresolved},
              'compile_only_files':['agent_native_supplement.galaxy'] if evidence else [],
              'runtime_marker':'GUI_OFFLINE_EXEC_'+proof_token if proof_token else None,
              'status':'generated; compiler check pending'}
    write_json(folder/'manifest.json',manifest)
    (folder/'AgentGenerated.galaxy').write_text(files[entry],encoding='utf-8')
    return {'build_id':folder.name,'manifest':str(folder/'manifest.json'),'complete':True,'status':manifest['status'],'runtime_marker':manifest['runtime_marker']}


def check_build(service,project_id,build_id):
    _,root=service.record(project_id)
    if not re.fullmatch('[0-9a-f]{32}',build_id):raise SC2Error('galaxy_build_invalid','invalid build ID')
    p=guard_absolute_path((getattr(service,'runtime_root',None) or project_runtime(root))/'galaxy-builds'/build_id/'manifest.json')
    manifest=json.loads(p.read_text('utf-8'))
    if manifest['root']!=str(root) or not manifest['complete']:raise SC2Error('galaxy_build_invalid','incomplete or foreign build')
    for path,record in manifest.get('resources',{}).items():
        if not Path(path).is_file() or digest(Path(path).read_bytes())!=record['sha256']:
            raise SC2Error('galaxy_build_stale','resource input changed',path=path)
    for path,record in manifest['inputs'].items():
        if digest(Path(path).read_bytes())!=record['sha256']:raise SC2Error('galaxy_build_stale','GUI input changed',path=path)
    for record in manifest['scripts'].values():
        if digest(Path(record['path']).read_bytes())!=record['sha256']:raise SC2Error('galaxy_build_stale','script input changed',path=record['path'])
    current=target_for(root,manifest['mods_dir'])
    _,sources=controlled_files(current,skip_generated=manifest.get('script_collection')=='gui_inputs')
    if current.problems or current.inputs!=manifest['inputs'] or sources!=manifest['scripts']:
        raise SC2Error('galaxy_build_stale','dependency or script inventory changed')
    result=check_files(manifest['files'],manifest['entry'],manifest['source_map'],
                       declarations=manifest.get('compile_only_files',()))
    current.refresh()
    for path,record in manifest.get('resources',{}).items():
        if not Path(path).is_file() or digest(Path(path).read_bytes())!=record['sha256']:
            raise SC2Error('galaxy_build_stale','resource input changed during check',path=path)
    _,after=controlled_files(current,skip_generated=manifest.get('script_collection')=='gui_inputs')
    if current.problems or after!=manifest['scripts']:raise SC2Error('galaxy_build_stale','input changed during check')
    write_json(p.parent/'check.json',result)
    return result


def check_source(service,project_id,entry,mods_dir=None):
    _,root=service.record(project_id)
    path=safe_path(root,entry)
    if path.suffix.lower()!='.galaxy' or not path.is_file():raise SC2Error('galaxy_entry_missing','entry must be a project Galaxy file')
    target=target_for(root,mods_dir)
    if target.problems:raise SC2Error('galaxy_dependencies_incomplete','dependency evidence incomplete',diagnostics=target.problems)
    files,sources=controlled_files(target)
    virtual=path.relative_to(root).as_posix().lower()
    if virtual.startswith('base.sc2data/'):virtual=virtual[len('base.sc2data/'):]
    result=check_files(files,virtual)
    target.refresh()
    _,after=controlled_files(target)
    if target.problems or sources!=after:raise SC2Error('galaxy_build_stale','input changed during check')
    return result
