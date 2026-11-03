import json
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest
from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_context import context, fingerprint
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def setup(tmp_path):
    root, mods = gui_target(tmp_path)
    fixtures = Path(__file__).parent/'fixtures/trigger-pipeline'
    lib = mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs'
    tree=ET.parse(fixtures/'matrix-native.TriggerLib')
    seen={(e.get('Type'),e.get('Id')) for e in tree.getroot().findall('Element')}
    tree.getroot().extend(e for e in ET.parse(lib/'NativeLib.TriggerLib').getroot().findall('Element') if (e.get('Type'),e.get('Id')) not in seen)
    seen={(e.get('Type'),e.get('Id')) for e in tree.getroot().findall('Element')}
    tree.getroot().extend(e for e in ET.parse(fixtures/'author-controlflow.TriggerLib').getroot().findall('Element') if (e.get('Type'),e.get('Id')) not in seen)
    tree.write(lib/'NativeLib.TriggerLib',encoding='utf-8')
    (lib/'NativeLib.galaxy').write_text('include "TriggerLibs/natives"\nvoid libNtve_InitLib() {}')
    class Service:
        def record(self, pid, write=False): return {}, root
    return Service(), root, mods


def spec(root, mods):
    return {'version':1, 'request_id':'first-feature',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'declarations':[{'kind':'variable','key':'done','type':'bool','initial':False},
                        {'kind':'category','key':'mission'}],
        'triggers':[{'key':'Evacuate','category':'mission','events':[{'call':'TriggerAddEventMapInit'}],
            'actions':[{'set':'done','value':True}]}]}


def test_context_reports_local_order_scope_strings_and_sources(tmp_path):
    service,root,mods=setup(tmp_path)
    result=context(service,'test',selection=['','Trigger','10000001'],depth=3,mods_dir=str(mods))
    assert result['nodes'][0]['category_path']==[]
    assert result['nodes'][0]['children'][0]['role']=='Event'
    assert result['inputs'] and result['fingerprint']
    assert 'scope' in result['nodes'][0]
    assert result['input_count']>len(result['inputs'])
    assert result['dependency_fingerprints']


def test_highlevel_generates_independent_typed_gui_without_ids(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    service,root,mods=setup(tmp_path)
    request=spec(root,mods)
    result=plan_author(root,request,str(mods))
    assert result['changes']==plan_author(root,request,str(mods))['changes']
    tree=ET.fromstring(result['changes']['Triggers'])
    ids=[e.get('Id') for e in tree.findall('Element')]
    assert len(ids)==len(set(ids))
    assert result['node_map']['triggers[0].actions[0]'][1]=='FunctionCall'
    assert b'FlagAction' not in result['changes']['Triggers'] # assigning uses existing GUI definition
    bad=json.loads(json.dumps(request));bad['triggers'][0]['actions'][0]['value']=42
    with pytest.raises(SC2Error) as error: plan_author(root,bad,str(mods))
    assert error.value.details['spec_path']=='triggers[0].actions[0].value'
    assert error.value.details['expected']=='bool'


def test_stale_resource_or_localization_blocks_plan(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    (root/'Regions').write_text('<regions/>')
    with pytest.raises(SC2Error,match='重新读取'):plan_author(root,request,str(mods))


def test_missing_region_points_to_argument(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['events']=[{'call':'TriggerAddEventUnitRegion','arguments':{
        'u':{'preset':['Ntve','PresetValue','C84C7A78']},
        'r':{'region':'EvacZone'},'state':{'preset':['Ntve','PresetValue','00000145']}}}]
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']=='triggers[0].events[0].arguments.r'


def install(root,changes):
    for name,raw in changes.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)


def test_reorder_replace_branch_move_and_delete_preserve_other_bytes(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'category','key':'final'})
    request['triggers'][0]['actions']=[{'if':{'compare':'==','left':{'var':'done'},'right':False},
        'then':[{'set':'done','value':True}],'else':[{'set':'done','value':False}]},
        {'set':'done','value':False}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    untouched=b'<Element Type="FunctionCall" Id="10000003"><FunctionDef Type="FunctionDef" Library="Ntve" Id="00000123"/><ScriptCode>// test</ScriptCode></Element>'
    assert untouched in (root/'Triggers').read_bytes()
    mapping=first['node_map'];branch=mapping['triggers[0].actions[0]'];second=mapping['triggers[0].actions[1]']
    trigger=mapping['triggers[0]'];done=mapping['declarations[0]'];category=mapping['declarations[2]']
    edit={'version':1,'request_id':'repair','expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace_branch','parent':branch,'role':'then','behaviors':[{'set':done,'value':False}]},
                 {'op':'reorder','parent':trigger,'role':'actions','order':[second,branch]},
                 {'op':'move','target':trigger,'parent':category,'role':'items'}]}
    repaired=plan_author(root,edit,str(mods));install(root,repaired['changes'])
    assert untouched in repaired['changes']['Triggers']
    tree=ET.parse(root/'Triggers');t=tree.find(f"Element[@Id='{trigger[2]}']")
    assert [c.get('Id') for c in t.findall('Action')]==[second[2],branch[2]]
    cat=tree.find(f"Element[@Id='{category[2]}']")
    assert cat.find('Item').get('Id')==trigger[2]
    edit.update(request_id='delete-live',expected_fingerprint=fingerprint(target_for(root,str(mods))))
    edit['edits']=[{'op':'delete','target':done}]
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['references']


def test_author_validates_exact_candidate_and_reuses_transaction(tmp_path,monkeypatch):
    from sc2_mcp.trigger_author import author
    from sc2_mcp.service import Service
    _,root,mods=setup(tmp_path)
    service=Service(tmp_path/'state')
    record=service.projects.open(str(root),True,search_roots=[str(mods)])
    pid=record['project_id'];request=spec(root,mods)
    result=author(service,pid,request,mode='candidate',mods_dir=str(mods))
    assert result['validation']['status']=='static validation passed'
    assert result['candidate_fingerprint']
    assert (root/'Triggers').read_bytes()!=Path(result['validation']['copy']) .joinpath('Triggers').read_bytes()
    again=author(service,pid,request,mode='candidate',mods_dir=str(mods))
    assert again['change_id']==result['change_id']
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    applied=service.apply_candidate(pid,result['change_id'])
    assert applied['state']=='committed'
    assert author(service,pid,request,mode='candidate',mods_dir=str(mods))['application']['change_id']==applied['change_id']
    assert service.apply_candidate(pid,result['change_id'])['change_id']==applied['change_id']
    service.transactions.rollback(applied['change_id'],root)
    assert b'Evacuate' not in (root/'Triggers').read_bytes()


def test_custom_function_forward_call_local_type_and_scope(tmp_path):
    from sc2_mcp.trigger_author import plan_author,validate_candidate
    service,root,mods=setup(tmp_path)
    service.state=tmp_path/'state'
    request=spec(root,mods)
    request['declarations'] += [
        {'kind':'function','key':'double','returns':'int','parameters':[{'key':'x','type':'int'}],
         'actions':[{'return':{'call':'identity','arguments':{'y':{'arithmetic':'+','left':{'parameter':'x'},'right':{'parameter':'x'}}}}}]},
        {'kind':'function','key':'identity','returns':'int','parameters':[{'key':'y','type':'int'}],
         'locals':[{'key':'local','type':'int'}], 'actions':[{'set':'local','value':{'parameter':'y'}},{'return':{'var':'local'}}]}]
    planned=plan_author(root,request,str(mods))
    result=validate_candidate(service,'test',root,planned,str(mods))
    assert result['status']=='static validation passed'
    request['triggers'][0]['actions']=[{'set':'done','value':{'var':'local'}}]
    with pytest.raises(SC2Error):plan_author(root,request,str(mods))


def test_dependency_ambiguity_and_unknown_branch_fail_closed(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['actions']=[{'call':'IfThenElse','branches':{'future':[]}}]
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path'].endswith('.branches.future')
    native=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree=ET.parse(native);duplicate=ET.fromstring('<Element Type="FunctionDef" Id="FFFFFFFF"><Identifier>TriggerAddEventMapInit</Identifier><FlagEvent/></Element>')
    tree.getroot().append(duplicate);tree.write(native,encoding='utf-8')
    request=spec(root,mods)
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert len(error.value.details['candidates'])==2
    (root/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Missing.SC2Mod</Value></Dependencies></DocInfo>')
    with pytest.raises(SC2Error,match='dependency'):plan_author(root,request,str(mods))


def test_named_region_uses_official_valueid_and_build_detects_region_change(tmp_path):
    from sc2_mcp.trigger_author import plan_author,validate_candidate
    from sc2_mcp.trigger_codegen import Generator
    from sc2_mcp.trigger_pipeline import check_build
    service,root,mods=setup(tmp_path);service.state=tmp_path/'state'
    (root/'Regions').write_text('<Regions><region id="7"><name value="EvacZone"/><shape type="rect"><quad value="10,10,20,20"/></shape></region></Regions>')
    native=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/natives.galaxy'
    native.write_text(native.read_text()+'\nnative region RegionFromId(int id);\nnative unitref UnitRefFromUnit(unit u);\nnative void TriggerAddEventUnitRegion(trigger t, unitref u, region r, bool state);')
    request=spec(root,mods)
    request['triggers'][0]['events']=[{'call':'TriggerAddEventUnitRegion','arguments':{
        'u':{'preset':['Ntve','PresetValue','C84C7A78']},'r':{'region':'EvacZone'},'state':{'preset':['Ntve','PresetValue','00000145']}}}]
    plan=plan_author(root,request,str(mods));install(root,plan['changes'])
    assert b'<ValueId Id="7"' in plan['changes']['Triggers']
    region_context=context(service,'test',selection=plan['node_map']['triggers[0].events[0].arguments.r'],mods_dir=str(mods))
    assert region_context['nodes'][0]['value']['name']=='EvacZone'
    generated=Generator(target_for(root,str(mods))).generate()
    assert 'RegionFromId(7)' in generated['source']
    assert 'UnitRefFromUnit(null)' not in generated['source'] # official B98370 AnyUnit registration emits null directly
    validation=validate_candidate(service,'test',root,plan,str(mods))
    folder=Path(validation['copy'])
    class CopyService:
        runtime_root=folder.parent/'runtime'
        def record(self,pid):return {},folder
    (folder/'Regions').write_text('<Regions/>')
    with pytest.raises(SC2Error,match='resource'):check_build(CopyService(),'test',validation['build']['build_id'])


def test_selected_parent_keeps_unknown_children_comments_and_quote_style(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path)
    p=root/'Triggers';p.write_bytes(p.read_bytes().replace(b'<Identifier>Start</Identifier>',b"<Identifier>Start</Identifier><!--keep--><Future field='raw'/ >".replace(b'/ >',b'/>')))
    request={'version':1,'request_id':'insert','expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'insert','parent':['','Trigger','10000001'],'role':'actions','index':0,
                  'behaviors':[{'call':'UIDisplayMessage','arguments':{'players':{'call':'PlayerGroupAll'},
                    'messageArea':{'preset':['Ntve','PresetValue','89CC0A21']},'message':{'literal':'Test','type':'text'}}}]}]}
    planned=plan_author(root,request,str(mods))
    assert b"<!--keep--><Future field='raw'/>" in planned['changes']['Triggers']


def test_move_local_scope_and_unknown_selected_instance_are_blocked(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'] += [
        {'kind':'action','key':'First','locals':[{'key':'flag','type':'bool'}], 'actions':[{'set':'flag','value':True}]},
        {'kind':'action','key':'Second','actions':[]}]
    first=plan_author(root,request,str(mods));install(root,first['changes']);mapping=first['node_map']
    edit={'version':1,'request_id':'move-scope','expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'move','target':mapping['declarations[2].actions[0]'],'parent':mapping['declarations[3]'],'role':'actions'}]}
    with pytest.raises(SC2Error,match='scope'):plan_author(root,edit,str(mods))
    key=mapping['declarations[2].actions[0]'];p=root/'Triggers'
    tree=ET.parse(p);ET.SubElement(tree.find(f"Element[@Id='{key[2]}']"),'Future')
    tree.write(p,encoding='utf-8')
    edit.update(expected_fingerprint=fingerprint(target_for(root,str(mods))))
    edit['edits']=[{'op':'replace','target':key,'behavior':{'set':mapping['declarations[0]'],'value':True}}]
    with pytest.raises(SC2Error,match='unknown XML'):plan_author(root,edit,str(mods))


def test_dependency_save_after_validation_refuses_candidate_apply(tmp_path,monkeypatch):
    from sc2_mcp.trigger_author import author
    from sc2_mcp.service import Service
    _,root,mods=setup(tmp_path);service=Service(tmp_path/'state')
    pid=service.projects.open(str(root),True,search_roots=[str(mods)])['project_id']
    result=author(service,pid,spec(root,mods),'candidate',str(mods))
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    before=(root/'Triggers').read_bytes()
    header=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/natives.galaxy'
    header.write_text(header.read_text()+'\n// changed dependency')
    with pytest.raises(SC2Error):service.apply_candidate(pid,result['change_id'])
    assert (root/'Triggers').read_bytes()==before


def test_reported_lowlevel_baseline_is_executable_and_matches_behavior(tmp_path):
    import shutil
    from sc2_mcp.trigger_author import plan_author
    from sc2_mcp.trigger_writer import plan_write
    from sc2_mcp.trigger_codegen import Generator
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    planned=plan_author(root,request,str(mods))
    low=tmp_path/'Low.SC2Map';shutil.copytree(root,low)
    install(root,planned['changes'])
    install(low,plan_write(low,planned['operations']))
    assert Generator(target_for(low,str(mods))).generate()['source']==Generator(target_for(root,str(mods))).generate()['source']


def evacuation_fixture(tmp_path):
    service,root,mods=setup(tmp_path)
    fixtures=Path(__file__).parent/'fixtures/trigger-pipeline'
    saved=json.loads((fixtures/'editor-98370-author.json').read_text('utf-8'))
    lib=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs'
    tree=ET.parse(lib/'NativeLib.TriggerLib');existing={(e.get('Type'),e.get('Id')) for e in tree.getroot().findall('Element')}
    tree.getroot().extend(e for e in ET.parse(fixtures/'author-native.TriggerLib').getroot().findall('Element') if (e.get('Type'),e.get('Id')) not in existing)
    tree.write(lib/'NativeLib.TriggerLib',encoding='utf-8')
    (lib/'natives.galaxy').write_bytes((fixtures/'author-natives.galaxy.txt').read_bytes())
    (root/'Regions').write_text(saved['regions_xml'],encoding='utf-8')
    return service,root,mods,saved


def test_actual_editor_evacuation_fixture_regenerates_and_matches_order(tmp_path):
    from sc2_mcp.trigger_codegen import Generator
    from sc2_mcp.galaxy_frontend import check_files
    _,root,mods,saved=evacuation_fixture(tmp_path)
    (root/'Triggers').write_text(saved['pre_editor_triggers_xml'],encoding='utf-8')
    result=Generator(target_for(root,str(mods))).generate()
    import re
    norm=lambda s:re.sub(r'\s+','',s)
    for code in [result['source'],saved['editor_galaxy'],saved['offline_galaxy']]:
        code=norm(code)
        ordered=['gv_evacCompleted=true;','ObjectiveSetState(gv_evacObjective,c_objectiveStateCompleted);','gv_evacCount=(gv_evacCount+1);']
        assert [code.index(v) for v in ordered]==sorted(code.index(v) for v in ordered)
        assert 'TriggerAddEventUnitRegion(gt_EvacFirstEntry,null,RegionFromId(97),true);' in code
    header=(mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/natives.galaxy').read_text()
    checked=check_files({'test.galaxy':header+result['source']},'test.galaxy')
    assert checked['status']=='static validation passed',checked['diagnostics']


def test_evacuation_high_and_lowlevel_workflow_efficiency(tmp_path,monkeypatch):
    from sc2_mcp.trigger_author import author,plan_author
    from sc2_mcp.trigger_pipeline import write,generate,check_build
    from sc2_mcp.service import Service
    import copy,shutil
    _,root,mods,saved=evacuation_fixture(tmp_path)
    (root/'Triggers').write_text('<TriggerData><Root/></TriggerData>')
    low=tmp_path/'Low.SC2Map';shutil.copytree(root,low)
    service=Service(tmp_path/'state');service.runtime_root=tmp_path/'runtime'
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    counts={'high':0,'low':0}
    def invoke(side,fn,*args,**kwargs):
        counts[side]+=1
        return fn(*args,**kwargs)
    high_id=service.projects.open(str(root),True,search_roots=[str(mods)])['project_id']
    low_id=service.projects.open(str(low),True,search_roots=[str(mods)])['project_id']
    request=copy.deepcopy(saved['author_spec']);request['expected_fingerprint']=invoke('high',context,service,high_id,mods_dir=str(mods))['fingerprint']
    planned=plan_author(root,request,str(mods))
    high=invoke('high',author,service,high_id,request,'candidate',str(mods))
    invoke('high',service.apply_candidate,high_id,high['change_id'])
    old_context=invoke('low',context,service,low_id,mods_dir=str(mods))
    before=(low/'Triggers').read_bytes()
    candidate=invoke('low',write,service,low_id,planned['operations'],mods_dir=str(mods))
    invoke('low',service.apply_candidate,low_id,candidate['change_id'])
    build=invoke('low',generate,service,low_id,str(mods))
    checked=invoke('low',check_build,service,low_id,build['build_id'])
    assert checked['status']=='static validation passed'
    assert counts=={'high':3,'low':5}
    report={'scope':'same evacuation requirement through source application and static validation; preopened isolated fixture projects',
        'measurement':'automated shared-operation harness, not inferred AI conversation calls',
        'tool_calls':counts,'high_level_bytes':high['efficiency']['request_bytes'],
        'low_level_bytes':high['efficiency']['low_level_bytes'],
        'allocated_internal_ids':high['efficiency']['allocated_internal_ids'],
        'high_level_explicit_new_instance_ids':0,'low_level_explicit_new_instance_ids':len(planned['operations'])}
    (tmp_path/'efficiency.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['high_level_bytes']<report['low_level_bytes']


def test_official_empty_text_default_gets_its_own_string_anchor(tmp_path):
    import copy
    from sc2_mcp.trigger_author import plan_author
    _,root,mods,saved=evacuation_fixture(tmp_path)
    request=copy.deepcopy(saved['author_spec']);request['expected_fingerprint']=fingerprint(target_for(root,str(mods)))
    del request['triggers'][0]['actions'][0]['arguments']['description']
    planned=plan_author(root,request,str(mods))
    key=planned['node_map']['triggers[0].actions[0].defaults.064A402E']
    anchor='Param/Value/'+key[2]
    assert (anchor+'=\r\n').encode() in planned['changes']['zhCN.SC2Data/LocalizedData/GameStrings.txt']


def test_nested_expression_mapping_keeps_all_instances_and_public_request_paths(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['actions'][0]['value']={'compare':'==','left':1,'right':1}
    result=plan_author(root,request,str(mods))
    path='triggers[0].actions[0].value'
    assert result['node_map'][path][1]=='Param'
    assert {r[1] for r in result['instances'][path]}=={'Param','FunctionCall'}
    assert result['allocated_internal_ids']==len(result['operations'])
    request['triggers'][0]['actions'][0]['value']={'compare':'==','left':1,'right':True}
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']==path+'.right'


def test_context_global_use_does_not_become_local_scope(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    service,root,mods=setup(tmp_path)
    planned=plan_author(root,spec(root,mods),str(mods));install(root,planned['changes'])
    var=planned['node_map']['declarations[0]']
    result=context(service,'test',selection=var,depth=1,mods_dir=str(mods))
    assert result['nodes'][0]['scope'] is None
    assert any(p['parent']==['','Root',''] for p in result['nodes'][0]['parents'])
    assert result['nodes'][0]['variable_type']['base_type']=='bool'
    assert result['nodes'][0]['children'][0]['value']['value'] is False


@pytest.mark.parametrize('operation',['move','delete'])
@pytest.mark.parametrize('selected_library',['','AC100001'])
def test_edit_ownership_uses_library_type_and_id(tmp_path,operation,selected_library):
    from sc2_mcp.trigger_author import plan_author,validate_candidate
    import copy
    service,root,mods=setup(tmp_path);service.state=tmp_path/'state'
    first=plan_author(root,spec(root,mods),str(mods));install(root,first['changes'])
    tree=ET.parse(root/'Triggers');doc=tree.getroot()
    library=ET.Element('Library',Id='AC100001')
    library.extend(copy.deepcopy(c) for c in doc)
    for item in library.findall('Root/Item'):item.set('Library','AC100001')
    doc.insert(0,library);tree.write(root/'Triggers',encoding='utf-8')
    other=doc if selected_library else library
    before=[ET.tostring(c) for c in other if c.tag!='Library']
    target=[selected_library,*first['node_map']['triggers[0]'][1:]]
    edit={'op':operation,'target':target}
    if operation=='move':edit.update(parent=[selected_library,'Root',''],role='items')
    request={'version':1,'request_id':'exact-owner-'+operation,
        'library':selected_library,'expected_fingerprint':fingerprint(target_for(root,str(mods))),'edits':[edit]}
    result=plan_author(root,request,str(mods))
    after=ET.fromstring(result['changes']['Triggers'])
    other_after=after if selected_library else after.find("Library[@Id='AC100001']")
    assert [ET.tostring(c) for c in other_after if c.tag!='Library']==before
    selected=after.find("Library[@Id='AC100001']") if selected_library else after
    assert (selected.find(f"Element[@Type='Trigger'][@Id='{target[2]}']") is not None)==(operation=='move')
    assert validate_candidate(service,'test',root,result,str(mods))['status']=='static validation passed'


def test_delete_unused_local_detaches_only_its_declaration(tmp_path):
    from sc2_mcp.trigger_author import plan_author, validate_candidate
    service,root,mods=setup(tmp_path);service.state=tmp_path/'state'
    request=spec(root,mods)
    request['triggers'][0]['locals']=[{'key':'unused','type':'int','initial':7}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    local=first['node_map']['triggers[0].locals[0]']
    edit={'version':1,'request_id':'remove-local',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'delete','target':local}]}
    result=plan_author(root,edit,str(mods))
    tree=ET.fromstring(result['changes']['Triggers'])
    assert tree.find(f"Element[@Id='{local[2]}']") is None
    assert tree.find(f"Element/Variable[@Id='{local[2]}']") is None
    assert validate_candidate(service,'test',root,result,str(mods))['status']=='static validation passed'


def test_replace_event_and_condition_respects_existing_role(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['conditions']=[{'compare':'==','left':1,'right':1}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edit={'version':1,'request_id':'replace-event',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':first['node_map']['triggers[0].events[0]'],
                  'behavior':{'call':'TriggerAddEventMapInit'}}]}
    result=plan_author(root,edit,str(mods))
    # Replacement preserves the event ID and reports that live node for subsequent edits.
    target=edit['edits'][0]['target']
    assert result['node_map']['edits[0].behavior']==target
    assert target in result['instances']['edits[0].behavior']
    edit['edits']=[{'op':'replace','target':first['node_map']['triggers[0].conditions[0]'],
                   'behavior':{'set':first['node_map']['declarations[0]'],'value':True}}]
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].behavior'


@pytest.mark.parametrize('role',['events','conditions'])
def test_function_definition_rejects_trigger_only_roles(tmp_path,role):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'action','key':'Action','actions':[]})
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edit={'version':1,'request_id':'wrong-function-role',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'insert','parent':first['node_map']['declarations[2]'],
                  'role':role,'behaviors':[]}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].role'


@pytest.mark.parametrize('location',['assignment','initial','return','nested_call'])
def test_expression_replacement_checks_surrounding_type(tmp_path,location):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'function','key':'boolResult','returns':'bool',
                                    'actions':[{'return':True}]})
    request['triggers'][0]['actions'][0]['value']={'call':'boolResult'}
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    paths={'assignment':'triggers[0].actions[0].value','initial':'declarations[0].initial',
           'return':'declarations[2].actions[0].return','nested_call':'triggers[0].actions[0].value'}
    refs=first['instances'][paths[location]]
    target=next(ref for ref in refs if ref[1]==('FunctionCall' if location=='nested_call' else 'Param'))
    # A valid integer expression, but invalid for each of these boolean contexts.
    behavior={'arithmetic':'+','left':1,'right':2}
    replacement={'behavior':behavior} if location=='nested_call' else {'expression':3}
    edit={'version':1,'request_id':'wrong-replacement-'+location,
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':target,**replacement}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['expected']=='bool'
    assert error.value.details['actual']=='int'
    assert error.value.details['spec_path']=='edits[0].'+('behavior' if location=='nested_call' else 'expression')


def test_replaced_text_uses_preserved_param_id_and_live_mapping(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'message','type':'text',
                                     'initial':{'literal':'Before','type':'text'}})
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    target=first['node_map']['declarations[2].initial']
    edit={'version':1,'request_id':'replace-text',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':target,'expression':{'literal':'After','type':'text'}}]}
    result=plan_author(root,edit,str(mods))
    tree=ET.fromstring(result['changes'].get('Triggers',(root/'Triggers').read_bytes()));anchor='Param/Value/'+target[2]
    assert tree.find(f"Element[@Id='{target[2]}']/Value").text==anchor
    assert anchor+'=After' in result['changes']['zhCN.SC2Data/LocalizedData/GameStrings.txt'].decode()
    assert result['instances']['edits[0].expression']==[target]
    assert result['allocated_internal_ids']==0


def test_deleting_used_local_keeps_source_and_reports_real_reference(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['locals']=[{'key':'localDone','type':'bool'}]
    request['triggers'][0]['actions']=[{'set':'localDone','value':True}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    original=(root/'Triggers').read_bytes();target=first['node_map']['triggers[0].locals[0]']
    edit={'version':1,'request_id':'delete-used-local',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'delete','target':target}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0]'
    assert any(r['reference'][1]=='Param' and r['target']==target for r in error.value.details['references'])
    assert (root/'Triggers').read_bytes()==original


def test_move_return_checks_destination_return_type(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'] += [
        {'kind':'function','key':'Source','returns':'bool','actions':[{'return':True}]},
        {'kind':'function','key':'Destination','returns':'int','actions':[{'return':0}]}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edit={'version':1,'request_id':'move-return',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'move','target':first['node_map']['declarations[2].actions[0]'],
                  'parent':first['node_map']['declarations[3]'],'role':'actions'}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0]'
    assert error.value.details['expected']=='int'
    assert error.value.details['actual']=='bool'


def test_combined_create_and_edit_returns_only_live_request_nodes(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['edits']=[{'op':'replace_branch','parent':'Evacuate','role':'actions',
                       'behaviors':[{'set':'done','value':False}]}]
    result=plan_author(root,request,str(mods));tree=ET.fromstring(result['changes']['Triggers'])
    live={(e.get('Type'),e.get('Id')) for e in tree.findall('Element')}
    assert all(tuple(ref[1:]) in live for ref in result['node_map'].values())
    assert all(refs and all(tuple(ref[1:]) in live for ref in refs) for refs in result['instances'].values())
    assert 'edits[0].behaviors[0]' in result['node_map']


@pytest.mark.parametrize('operation,missing',[('insert','behaviors'),('replace_branch','behaviors'),('reorder','order')])
def test_edit_requires_explicit_payload_before_touching_branch(tmp_path,operation,missing):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path)
    first=plan_author(root,spec(root,mods),str(mods));install(root,first['changes'])
    original=(root/'Triggers').read_bytes()
    request={'version':1,'request_id':'missing-payload',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':operation,'parent':first['node_map']['triggers[0]'],'role':'actions'}]}
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']=='edits[0].'+missing
    assert (root/'Triggers').read_bytes()==original


@pytest.mark.parametrize('fields,path',[
    ({'op':'delete','behaviors':[]},'edits[0].behaviors'),
    ({'op':'move','parent':['','Root',''],'role':'items','index':True},'edits[0].index'),
    ({'op':'replace','expression':True},'edits[0].behavior')])
def test_edit_rejects_ignored_or_incompatible_fields(tmp_path,fields,path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path)
    first=plan_author(root,spec(root,mods),str(mods));install(root,first['changes'])
    target=first['node_map']['triggers[0].actions[0]'] if fields['op']=='replace' else first['node_map']['triggers[0]']
    request={'version':1,'request_id':'invalid-edit-fields',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'target':target,**fields}]}
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']==path


def test_removed_new_text_does_not_leave_orphan_anchors(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path)
    strings=root/'zhCN.SC2Data/LocalizedData/GameStrings.txt'
    strings.parent.mkdir(parents=True,exist_ok=True)
    strings.write_text('Unknown/Keep=Existing source text\n',encoding='utf-8')
    request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'temporaryText','type':'text',
                                     'initial':{'literal':'Discard me','type':'text'}})
    request['edits']=[{'op':'delete','target':'temporaryText'}]
    result=plan_author(root,request,str(mods))
    assert 'zhCN.SC2Data/LocalizedData/GameStrings.txt' not in result['changes']
    assert all('Discard me' not in raw.decode('utf-8-sig') for raw in result['changes'].values())
    assert strings.read_text(encoding='utf-8')=='Unknown/Keep=Existing source text\n'


def test_replacing_assignment_target_rechecks_dependent_value(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'score','type':'int','initial':0})
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edit={'version':1,'request_id':'change-target-only',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':first['node_map']['triggers[0].actions[0].set'],
                  'expression':{'var':first['node_map']['declarations[2]']}}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].expression'
    assert error.value.details['expected']=='int'
    assert error.value.details['actual']=='bool'


@pytest.mark.parametrize('value_first',[False,True])
def test_atomic_assignment_type_change_accepts_either_edit_order(tmp_path,value_first):
    from sc2_mcp.trigger_author import plan_author,validate_candidate
    service,root,mods=setup(tmp_path);service.state=tmp_path/'state'
    request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'score','type':'int','initial':0})
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edits=[{'op':'replace','target':first['node_map']['triggers[0].actions[0].set'],
            'expression':{'var':first['node_map']['declarations[2]']}},
           {'op':'replace','target':first['node_map']['triggers[0].actions[0].value'],'expression':42}]
    if value_first:edits.reverse()
    request={'version':1,'request_id':'change-target-and-value',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),'edits':edits}
    result=plan_author(root,request,str(mods))
    assert validate_candidate(service,'test',root,result,str(mods))['status']=='static validation passed'


def test_parameter_replacement_preserves_game_link_catalog_constraint(tmp_path):
    import copy
    from sc2_mcp.trigger_author import plan_author
    _,root,mods,saved=evacuation_fixture(tmp_path)
    unit_create=next(copy.deepcopy(a) for a in saved['author_spec']['triggers'][0]['actions']
                     if a.get('arguments',{}).get('type',{}).get('literal')=='Marine')
    request=spec(root,mods);request['triggers'][0]['actions']=[unit_create]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    edit={'version':1,'request_id':'wrong-catalog',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':first['node_map']['triggers[0].actions[0].arguments.type'],
                  'expression':{'literal':'Stimpack','type':'gamelink','game_type':'Abil'}}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].expression.game_type'
    assert error.value.details['expected']=='Unit'
    assert error.value.details['actual']=='Abil'


def test_void_call_cannot_replace_nested_anycompare_expression(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'function','key':'Number','returns':'int','actions':[{'return':1}]})
    request['triggers'][0]['conditions']=[{'compare':'==','left':{'call':'Number'},'right':1}]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    target=next(r for r in first['instances']['triggers[0].conditions[0].left'] if r[1]=='FunctionCall')
    edit={'version':1,'request_id':'void-nested',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'replace','target':target,'behavior':{'set':first['node_map']['declarations[0]'],'value':True}}]}
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].behavior'


@pytest.mark.parametrize('new_declaration',[False,True])
def test_deleted_reference_is_not_resolved_from_stale_original(tmp_path,new_declaration):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'temporary','type':'bool','initial':False})
    if new_declaration:
        deleted='temporary';done='done'
    else:
        first=plan_author(root,request,str(mods));install(root,first['changes'])
        deleted=first['node_map']['declarations[2]'];done=first['node_map']['declarations[0]']
        request={'version':1,'request_id':'deleted-source',
                 'expected_fingerprint':fingerprint(target_for(root,str(mods)))}
    request['edits']=[{'op':'delete','target':deleted},
        {'op':'insert','parent':'Evacuate' if new_declaration else first['node_map']['triggers[0]'],
         'role':'actions','behaviors':[{'set':done,'value':{'var':deleted}}]}]
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']=='edits[1].behaviors[0].value'
    assert 'deleted' in str(error.value)


def test_review_impacts_explain_condition_order_and_category_changes(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods,saved=evacuation_fixture(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'category','key':'Reviewed'})
    request['triggers'][0]['actions'].append({'set':'done','value':False})
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    nodes=first['node_map'];trigger=nodes['triggers[0]']
    actions=[nodes['triggers[0].actions[0]'],nodes['triggers[0].actions[1]']]
    request={'version':1,'request_id':'review-modification',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[
            {'op':'replace_branch','parent':trigger,'role':'conditions','behaviors':[
                {'compare':'==','left':{'call':'UnitGetOwner','arguments':{'u':{'call':'EventUnit'}}},'right':1}]},
            {'op':'reorder','parent':trigger,'role':'actions','order':actions[::-1]},
            {'op':'move','target':trigger,'parent':nodes['declarations[2]'],'role':'items'}]}
    result=plan_author(root,request,str(mods));conditions,order,move=result['impacts']
    assert conditions['role']=='conditions' and conditions['before']==[]
    assert all(term in conditions['after'][0]['summary'] for term in ['UnitGetOwner','EventUnit','1'])
    assert [r['reference'] for r in order['before']]==actions
    assert [r['reference'] for r in order['after']]==actions[::-1]
    assert order['id_policy']=='preserved'
    assert 'done' in order['before'][0]['summary'] and 'true' in order['before'][0]['summary']
    assert move['from_parent']['reference']==nodes['declarations[1]']
    assert move['to_parent']['reference']==nodes['declarations[2]']
    assert move['to_parent']['summary']=='Reviewed'
    assert move['id_policy']=='preserved'


def test_review_truncation_does_not_truncate_order_integrity_checks(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path);request=spec(root,mods)
    request['triggers'][0]['actions']=[{'set':'done','value':bool(i%2)} for i in range(45)]
    first=plan_author(root,request,str(mods));install(root,first['changes'])
    order=[first['node_map'][f'triggers[0].actions[{i}]'] for i in range(45)]
    edit={'version':1,'request_id':'bounded-review',
        'expected_fingerprint':fingerprint(target_for(root,str(mods))),
        'edits':[{'op':'reorder','parent':first['node_map']['triggers[0]'],'role':'actions','order':order[::-1]}]}
    impact=plan_author(root,edit,str(mods))['impacts'][0]
    assert impact['before_count']==45 and impact['before_truncated']
    assert impact['after_count']==45 and impact['after_truncated']
    assert 0<len(impact['after'])<45
    edit['edits'][0]['order']=order[:-1]
    with pytest.raises(SC2Error) as error:plan_author(root,edit,str(mods))
    assert error.value.details['spec_path']=='edits[0].order'


def test_readonly_review_handles_cyclic_unknown_expression_without_recursing(tmp_path):
    from sc2_mcp.trigger_author import Author
    _,root,mods=setup(tmp_path)
    tree=ET.parse(root/'Triggers');doc=tree.getroot()
    for key,child in [('AC111111','AC222222'),('AC222222','AC111111')]:
        e=ET.SubElement(doc,'Element',Type='Param',Id=key)
        ET.SubElement(e,'Parameter',Type='Param',Id=child)
    tree.write(root/'Triggers',encoding='utf-8')
    review=Author(root,target_for(root,str(mods)),spec(root,mods)).review_node(('','Param','AC111111'))
    assert review['summary_truncated']


def test_new_feature_review_names_events_actions_and_variable_initial_value(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods=setup(tmp_path)
    result=plan_author(root,spec(root,mods),str(mods))
    created={r['spec_path']:r for r in result['impacts'] if r['operation']=='create'}
    variable=created['declarations[0]'];trigger=created['triggers[0]']
    assert variable['type']=='bool' and variable['initial']['summary']=='false'
    assert trigger['parent']['reference']==result['node_map']['declarations[1]']
    assert 'TriggerAddEventMapInit' in trigger['roles']['events']['nodes'][0]['summary']
    assert all(term in trigger['roles']['actions']['nodes'][0]['summary'] for term in ['SetVariable','done','true'])
    assert trigger['roles']['actions']['count']==1 and not trigger['roles']['actions']['truncated']
    assert trigger['id_policy']=='allocated'


@pytest.mark.parametrize('multiple_conditions',[False,True])
def test_highlevel_while_uses_official_roles_and_hoists_local_counter(tmp_path,multiple_conditions):
    from sc2_mcp.trigger_author import plan_author,validate_candidate
    service,root,mods=setup(tmp_path);service.state=tmp_path/'state'
    request=spec(root,mods)
    condition={'compare':'<','left':{'var':'step'},'right':3}
    request['triggers'][0]['locals']=[{'key':'step','type':'int','initial':0}]
    request['triggers'][0]['actions']=[{'while':[condition,{'compare':'==','left':{'var':'done'},'right':False}]
        if multiple_conditions else condition,
        'actions':[{'set':'step','value':{'arithmetic':'+','left':{'var':'step'},'right':1}}]}]
    result=plan_author(root,request,str(mods));tree=ET.fromstring(result['changes']['Triggers'])
    call=result['node_map']['triggers[0].actions[0]']
    loop=tree.find(f"Element[@Id='{call[2]}']")
    assert loop.find('FunctionDef').get('Id')=='71596144'
    subtypes=[tree.find(f"Element[@Id='{c.get('Id')}']/SubFunctionType").get('Id') for c in loop.findall('FunctionCall')]
    assert subtypes==(['20298AEC']*(2 if multiple_conditions else 1))+['A1B37466']
    validation=validate_candidate(service,'test',root,result,str(mods))
    assert validation['status']=='static validation passed'
    source=(Path(validation['build']['manifest']).parent/'AgentGenerated.galaxy').read_text(encoding='utf-8')
    source=source.split('bool gt_Evacuate_Func(bool testConds, bool runActions) {',1)[1]
    assert source.index('int gv_step;')<source.index('if (testConds')<source.index('gv_step = 0;')<source.index('while (')
    assert 'gv_step = (gv_step + 1);' in source
    assert (' && ' in source[source.index('while ('):source.index('while (')+100])==multiple_conditions
    request['triggers'][0]['actions'][0]['while']=0
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']=='triggers[0].actions[0].while'


def test_objective_handle_does_not_accept_unit_even_with_integer_backing(tmp_path):
    from sc2_mcp.trigger_author import plan_author
    _,root,mods,saved=evacuation_fixture(tmp_path);request=spec(root,mods)
    request['declarations'].append({'kind':'variable','key':'targetUnit','type':'unit'})
    request['triggers'][0]['actions']=[{'call':'ObjectiveSetState','arguments':{
        'objective':{'var':'targetUnit'},'state':{'preset':['Ntve','PresetValue','00000559']}}}]
    with pytest.raises(SC2Error) as error:plan_author(root,request,str(mods))
    assert error.value.details['spec_path']=='triggers[0].actions[0].arguments.objective'
    assert error.value.details['expected']=='objective' and error.value.details['actual']=='unit'


def test_editor_accepted_repair_retains_identity_order_and_offline_behavior(tmp_path):
    import re
    from sc2_mcp.trigger_codegen import Generator
    from sc2_mcp.galaxy_frontend import check_files
    _,root,mods,_=evacuation_fixture(tmp_path)
    fixture=Path(__file__).parent/'fixtures/trigger-pipeline/editor-98370-author-repair.json'
    accepted=json.loads(fixture.read_text('utf-8'))
    assert accepted['status']=='packaged runtime passed' and accepted['editor_status']=='Editor accepted'
    assert accepted['current_author_replay_matches_tested_candidate']
    request=accepted['repair_request'];trigger=request['edits'][0]['parent'];category=request['edits'][2]['parent']
    expected=[r[2] for r in request['edits'][1]['order']]
    flawed=ET.fromstring(accepted['flawed_triggers_xml']).find(f"Element[@Id='{trigger[2]}']")
    assert flawed.findall('Condition')==[]
    assert [r.get('Id') for r in flawed.findall('Action')]!=expected
    for field in ['offline_triggers_xml','editor_triggers_xml']:
        doc=ET.fromstring(accepted[field]);after=doc.find(f"Element[@Id='{trigger[2]}']")
        assert len(after.findall('Condition'))==2
        assert [r.get('Id') for r in after.findall('Action')]==expected
        assert doc.find(f"Element[@Id='{category[2]}']/Item[@Id='{trigger[2]}']") is not None
    (root/'Triggers').write_text(accepted['offline_triggers_xml'],encoding='utf-8')
    regenerated=Generator(target_for(root,str(mods))).generate()['source']
    for source in [regenerated,accepted['editor_galaxy'],accepted['offline_galaxy']]:
        norm=re.sub(r'\s+','',source)
        sequence=['gv_evacCompleted=true;','ObjectiveSetState(gv_evacObjective,c_objectiveStateCompleted);','gv_evacCount=(gv_evacCount+1);']
        assert [norm.index(s) for s in sequence]==sorted(norm.index(s) for s in sequence)
        assert 'UnitGetOwner(EventUnit())==1' in norm and 'gv_evacCompleted==false' in norm
        assert 'TriggerAddEventUnitRegion(gt_EvacFirstEntry,null,RegionFromId(97),true);' in norm
    header=(mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/natives.galaxy').read_text()
    checked=check_files({'test.galaxy':header+regenerated},'test.galaxy')
    assert checked['status']=='static validation passed',checked['diagnostics']



def test_context_fingerprint_uses_verified_second_scan(tmp_path, monkeypatch):
    from sc2_mcp import trigger_context
    service, root, mods = setup(tmp_path)
    scan = trigger_context.inputs
    scans = []
    def measured(target):
        result = scan(target)
        scans.append(result)
        return result
    monkeypatch.setattr(trigger_context, "inputs", measured)
    report = context(service,"test",mods_dir=str(mods))
    assert len(scans) == 2 and scans[0] == scans[1]
    assert report["fingerprint"] == trigger_context.digest(json.dumps(scans[-1],sort_keys=True).encode())
