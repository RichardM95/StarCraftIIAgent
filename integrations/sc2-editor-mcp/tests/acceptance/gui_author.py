"""Independent terrain-backed GUI author acceptance, including an intentionally broken version.

Run with explicit --terrain (a saved map), --shell (saved Liberty-only component
DocumentInfo donor), and a NEW --destination. Originals and generated scripts
are read-only. No Editor/game process is launched.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET
from sc2_mcp.trigger_pipeline import target_for,generate
from sc2_mcp.trigger_context import fingerprint,definition
from sc2_mcp.trigger_author import author,plan_author
from sc2_mcp.trigger_package import package_build
from sc2_mcp.service import Service
from sc2_mcp.storage import digest,write_json
from sc2_mcp.archives import _collect_export_members


def request(root):
    t=target_for(root);d=next(d for d in t.documents if d.path==root/'Triggers')
    def call(function,**args):return {'call':list(definition(t,d,function)[1]),'arguments':args}
    def preset(ident):return {'preset':['Ntve','PresetValue',ident]}
    def var(key):return {'var':key}
    def text(value):return {'literal':value,'type':'text'}
    def point(x,y):return call('Point',x=x,y=y)
    def compare(a,b,op='=='):return {'compare':op,'left':a,'right':b}
    def message(value):return call('UIDisplayMessage',players=call('PlayerGroupAll'),messageArea=preset('89CC0A21'),message=text(value))
    def check(condition,label):return {'if':condition,'then':[message('GUI_EVAC_'+label+'_PASS')],
        'else':[{'set':'evacAllPassed','value':False},message('GUI_EVAC_'+label+'_FAIL')]}
    def move(unit,x,y):return call('UnitSetPosition',u=var(unit),p=point(x,y),blend=preset('0EA75E11'))
    def wait():return call('Wait',t=1.0,timeType=preset('00000013'))
    active=preset('24E7961A');complete=preset('00000559')
    create=lambda name:call('ObjectiveCreate',name=text(name),description=text('Player 1 first entry only'),state=active,primary=preset('0801604A'))
    declarations=[{'kind':'category','key':'Evacuation'},{'kind':'category','key':'Reviewed'},
        {'kind':'variable','key':'evacCompleted','type':'bool','initial':False},
        {'kind':'variable','key':'evacCount','type':'int','initial':0},
        {'kind':'variable','key':'evacAllPassed','type':'bool','initial':True},
        {'kind':'variable','key':'evacObjective','type':'objective'},
        {'kind':'variable','key':'decoyObjective','type':'objective'},
        {'kind':'variable','key':'enemyUnit','type':'unit'},
        {'kind':'variable','key':'playerUnit','type':'unit'}]
    # The accepted native MarSara sample has a flat, clear strip at x=50..60,y=80..84.
    actions=[create('Evacuation'),{'set':'evacObjective','value':call('ObjectiveLastCreated')},
        create('Decoy: must stay active'),{'set':'decoyObjective','value':call('ObjectiveLastCreated')}]
    for player,name,y in [(2,'enemyUnit',80),(1,'playerUnit',84)]:
        actions += [call('UnitCreate',count=1,type={'literal':'Marine','type':'gamelink','game_type':'Unit'},
            flags=preset('7491C9A8'),player=player,pos=point(50,y),angle=0.0),
            {'set':name,'value':call('UnitLastCreated')},
            check(compare(call('UnitGetOwner',u=var(name)),player),'OWNER_'+str(player))]
    actions += [wait(),move('enemyUnit',58,82),wait(),check(compare(var('evacCount'),0),'COUNT_0'),
        move('enemyUnit',50,80),move('playerUnit',58,82),wait(),check(compare(var('evacCount'),1),'COUNT_1'),
        check(compare(call('ObjectiveGetState',objective=var('evacObjective')),complete),'SAVED_OBJECTIVE'),
        check(compare(call('ObjectiveGetState',objective=var('decoyObjective')),active),'DECOY_ACTIVE'),
        move('playerUnit',50,84),wait(),move('playerUnit',58,82),wait(),check(compare(var('evacCount'),1),'REENTRY_1'),
        {'if':compare(var('evacAllPassed'),True),'then':[message('GUI_EVAC_ALL_PASS')],'else':[message('GUI_EVAC_ALL_FAIL')]}]
    on_entry={'key':'EvacFirstEntry','category':'Evacuation',
        'events':[call('TriggerAddEventUnitRegion',u=preset('C84C7A78'),r={'region':'EvacZone'},state=preset('00000145'))],
        'conditions':[compare(call('UnitGetOwner',u=call('EventUnit')),1),compare(var('evacCompleted'),False)],
        'actions':[{'set':'evacCompleted','value':True},call('ObjectiveSetState',objective=var('evacObjective'),state=complete),
                   {'set':'evacCount','value':{'arithmetic':'+','left':var('evacCount'),'right':1}}]}
    return {'version':1,'request_id':'evacuation-correct-v1','expected_fingerprint':fingerprint(t),
        'declarations':declarations,'triggers':[{'key':'EvacAcceptance','category':'Evacuation',
            'events':[call('TriggerAddEventMapInit')],'actions':actions},on_entry],
        'acceptance':['non-player-1 entry: count 0','player-1 entry: count 1',
                      'leave and reenter: count 1','saved objective completed; decoy remains active']}


def install(changes,root):
    for relative,raw in changes.items():
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)


def prepare(terrain,shell,base,package=False):
    from sc2_terrain_ops import Edit
    base=base.resolve();workspace=Path(__file__).resolve().parents[4]
    if base.exists() or not base.is_relative_to(workspace):raise ValueError('destination must be a NEW workspace directory')
    base.mkdir(parents=True)
    os.environ['SC2_AGENT_RUNTIME_ROOT']=str(base/'runtime')
    seed=base/'Seed.SC2Map';seed.mkdir()
    members,_=_collect_export_members(terrain)
    retained={}
    for relative,source in members:
        if source.suffix.lower()=='.galaxy' or relative in {'Triggers','DocumentInfo','BankList.xml','Preload.xml','PreloadAssetDB.txt'}:continue
        if relative.lower().endswith('/gamedata/unitdata.xml'):continue
        p=seed/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)
        retained[relative]=digest(source.read_bytes())
    # Native manifest/terrain companions are copied as a unit. No manifest is synthesized or patched.
    from sc2_mcp.dependencies import decode_declarations
    from sc2_mcp.shell import header_dependencies,replace_header_dependencies
    native_header=(seed/'DocumentHeader').read_bytes()
    new_info=(shell/'DocumentInfo').read_bytes()
    (seed/'DocumentHeader').write_bytes(replace_header_dependencies(native_header,header_dependencies(native_header)['values'],decode_declarations(new_info)))
    (seed/'DocumentInfo').write_bytes(new_info)
    (seed/'Triggers').write_bytes(b'<?xml version="1.0" encoding="utf-8"?><TriggerData><Root/></TriggerData>')
    edit=Edit(seed)
    for kind in ['unit','doodad']:
        if ET.parse(seed/'Objects').getroot().find('ObjectUnit' if kind=='unit' else 'ObjectDoodad') is not None:
            edit.objects({'op':'objects','mode':'delete','selector':{'kind':kind}})
    edit.regions({'op':'regions','mode':'add','name':'EvacZone','shapes':[{'type':'rect','rect':[56,80,60,84]}]})
    install(edit.changes,seed)
    write_json(base/'shell-provenance.json',{'terrain_donor':str(terrain),'dependency_donor':str(shell),
        'retained_hashes':retained,'terrain_unchanged':all((seed/rel).read_bytes()==(terrain/rel).read_bytes() for rel in retained if rel.startswith('t3')),
        'manifest_unchanged':(seed/'ComponentList.SC2Components').read_bytes()==(terrain/'ComponentList.SC2Components').read_bytes(),
        'scene_operations':edit.notes,'status':'source fixed','editor_accepted':False})
    return complete(base,package)


def complete(base,package=False):
    base=base.resolve();workspace=Path(__file__).resolve().parents[4]
    os.environ['SC2_AGENT_RUNTIME_ROOT']=str(base/'runtime')
    seed=base/'Seed.SC2Map';correct=base/'GuiEvac.SC2Map'
    if not correct.exists():shutil.copytree(seed,correct)
    elif (correct/'Triggers').read_bytes()!=(seed/'Triggers').read_bytes():raise ValueError('partial source differs from clean seed; inspect previous transaction')
    service=Service(base/'state');pid=service.projects.open(str(correct),True)['project_id']
    spec=request(correct);write_json(base/'author-request.json',spec)
    result=author(service,pid,spec,'candidate')
    # Keep the normal transaction guard. The operator must close Editor before apply.
    if service.editor_conflict():
        write_json(base/'pending.json',{'project_id':pid,'candidate':result});return {'state':'candidate; close Editor before apply','candidate':result}
    committed=service.apply_candidate(pid,result['change_id']);write_json(base/'candidate.json',result)
    write_json(base/'committed.json',committed)
    # Build a genuinely flawed old source, then repair by selecting only its condition branch/order/category.
    flawed=base/'GuiEvacLegacy.SC2Map';shutil.copytree(seed,flawed)
    legacy=copy.deepcopy(spec);legacy['request_id']='evacuation-legacy-v1';legacy['expected_fingerprint']=fingerprint(target_for(flawed))
    legacy['triggers'][1]['conditions']=[]
    legacy['triggers'][1]['actions']=[legacy['triggers'][1]['actions'][1],legacy['triggers'][1]['actions'][2],legacy['triggers'][1]['actions'][0]]
    old=plan_author(flawed,legacy);install(old['changes'],flawed);mapping=old['node_map']
    var_refs={item['key']:mapping[f'declarations[{i}]'] for i,item in enumerate(legacy['declarations'])}
    def bind_existing(value):
        if isinstance(value,list):return [bind_existing(v) for v in value]
        if isinstance(value,dict):return {k:var_refs[v] if k=='var' and isinstance(v,str) else bind_existing(v) for k,v in value.items()}
        return value
    repair={'version':1,'request_id':'evacuation-repair-v1','expected_fingerprint':fingerprint(target_for(flawed)),
        'edits':[{'op':'replace_branch','parent':mapping['triggers[1]'],'role':'conditions','behaviors':bind_existing(spec['triggers'][1]['conditions'])},
            {'op':'reorder','parent':mapping['triggers[1]'],'role':'actions','order':[mapping['triggers[1].actions[2]'],mapping['triggers[1].actions[0]'],mapping['triggers[1].actions[1]']]},
            {'op':'move','target':mapping['triggers[1]'],'parent':mapping['declarations[1]'],'role':'items'}],
        'acceptance':spec['acceptance']}
    legacy_pid=service.projects.open(str(flawed),True)['project_id']
    write_json(base/'repair-request.json',repair)
    repaired=author(service,legacy_pid,repair,'candidate');write_json(base/'repair-candidate.json',repaired)
    write_json(base/'repair-committed.json',service.apply_candidate(legacy_pid,repaired['change_id']))
    built=generate(service,pid,runtime_probe=True);write_json(base/'generated.json',built)
    manifest=json.loads(Path(built['manifest']).read_text('utf-8'))
    (base/'offline-input-Triggers.xml').write_bytes((correct/'Triggers').read_bytes())
    (base/'offline-generated.galaxy.txt').write_text(manifest['files'][manifest['entry']],encoding='utf-8')
    output={'map':str(correct),'legacy_repaired_map':str(flawed),'project_id':pid,'build':built,
            'status':'static validation passed','editor':'not_run','runtime':'not_run','efficiency':result['efficiency']}
    if package:
        from sc2_paths import load_project_config,resolve_configured_path
        installation=resolve_configured_path(workspace,load_project_config(workspace)['paths']['sc2_install_dir'])
        packaged=package_build(service,pid,built['build_id'],str(installation));write_json(base/'package.json',packaged)
        shutil.copyfile(packaged['launcher'],base/'RunEvacTest.cmd');output['runtime_marker']=packaged['runtime_marker']
    write_json(base/'acceptance.json',output)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--terrain',type=Path)
    parser.add_argument('--shell',type=Path)
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--package',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    result=complete(args.destination,args.package) if args.resume else prepare(args.terrain.resolve(),args.shell.resolve(),args.destination,args.package)
    print(json.dumps(result,indent=2,ensure_ascii=False))
