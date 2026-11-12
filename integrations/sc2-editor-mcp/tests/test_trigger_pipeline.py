from pathlib import Path
import hashlib
import pytest
from sc2_mcp.trigger_writer import plan_write
from sc2_mcp.errors import SC2Error
from sc2_mcp.galaxy_frontend import check_files
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
import os


def test_editor_saved_binding_sample_matches_offline_types_and_power_arguments(tmp_path):
    import json
    from xml.etree import ElementTree as ET
    fixtures=Path(__file__).parent/'fixtures/trigger-pipeline'
    saved=json.loads((fixtures/'editor-98370-binding.json').read_text('utf-8'))
    link=json.loads((fixtures/'editor-98370-modlink.json').read_text('utf-8'))
    root,mods=gui_target(tmp_path)
    lib=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs'
    tree=ET.parse(fixtures/'matrix-native.TriggerLib')
    existing={(e.get('Type'),e.get('Id')) for e in tree.getroot().findall('Element')}
    for element in ET.parse(fixtures/'binding-native.TriggerLib').getroot().findall('Element'):
        if (element.get('Type'),element.get('Id')) not in existing:tree.getroot().append(element)
    tree.write(lib/'NativeLib.TriggerLib',encoding='utf-8')
    header=(lib/'natives.galaxy').read_text()+'\nnative point Point(fixed x, fixed y);\nnative int PowerLevel(int player, point position, string powerType);\n'
    (lib/'natives.galaxy').write_text(header)
    (root/'Triggers').write_text(saved['pre_editor_triggers_xml'],encoding='utf-8')
    (root/'DocumentInfo').write_text(saved['map_document_info'],encoding='utf-8')
    mod=mods/'CodexGuiLinkAcceptanceV2.SC2Mod'
    mod.mkdir()
    (mod/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Core.SC2Mod</Value></Dependencies></DocInfo>')
    (mod/'Triggers').write_text(link['mod_triggers_xml'],encoding='utf-8')
    generated=Generator(target_for(root,str(mods))).generate()
    for source in (generated['source'],saved['editor_galaxy']):
        assert source.count(saved['matching_power_expression'])==2
        assert 'bool gv_PresetReady;' in source
        assert 'TriggerAddEventMapInit(gt_BindingCorrectness);' in source
    assert 'bool gf_PresetIdentity(bool lp_Input)' in generated['source']
    assert 'bool gv_LocalPreset;' in generated['source']
    checked=check_files({'test.galaxy':header+generated['source']},'test.galaxy')
    assert checked['status']=='static validation passed',checked
    assert any(m.get('kind')=='GUI compatibility body' for m in generated['used_mappings'])


@pytest.mark.parametrize('base_type',['bool','string','fixed'])
def test_bindings_closure_types_cache_and_return_discard(tmp_path,base_type):
    from sc2_mcp.trigger_bindings import Bindings
    from xml.etree import ElementTree as ET
    root,mods=gui_target(tmp_path)
    target=target_for(root,str(mods))
    files={'entry.galaxy':'/*\ninclude "absent"\n*/\ninclude "types"', 'types.galaxy':'native int NativeAction(int x);',
           'unused.galaxy':'native bool Invisible();'}
    mapping=Bindings(target,files,['entry.galaxy'])
    d=next(d for d in target.documents if not d.standard)
    key=('', 'FunctionCall','10000003')
    assert mapping.bind('NativeAction','void',['int'],['1'],True,d,key,('Ntve','FunctionDef','1'))=='NativeAction(1)'
    with pytest.raises(SC2Error,match='signature'):
        mapping.bind('NativeAction','void',['int'],['1'],False,d,key,('Ntve','FunctionDef','1'))
    with pytest.raises(SC2Error) as missing:
        mapping.bind('Invisible','bool',[],[],False,d,key,('Ntve','FunctionDef','2'))
    assert missing.value.details['node']==list(key)
    files['types.galaxy']='native bool NativeAction(bool x);'
    updated=Bindings(target,files,['entry.galaxy'])
    assert mapping.candidates('NativeAction')[0]['return']=='int'
    assert updated.candidates('NativeAction')[0]['return']=='bool'
    preset=ET.fromstring(f'<Element><BaseType Value="{base_type}"/></Element>')
    d.elements[('', 'Preset','AA000001')]=preset
    variable=ET.fromstring('<Element><VariableType><Type Value="preset"/><TypeElement Type="Preset" Id="AA000001"/></VariableType></Element>')
    target.providers[(str(d.path),'','Preset','AA000001')]=[(d,preset)]
    assert Generator(target,bindings=mapping).typ(variable,d,('', 'Variable','AA000002'),'VariableType')==base_type
    argument=ET.fromstring('<Element><ParameterType><Type Value="control"/></ParameterType></Element>')
    function=ET.fromstring('<Element><Identifier>ControlBinding</Identifier><FlagNative/><Parameter Type="ParamDef" Id="AA000004"/></Element>')
    d.elements[('', 'FunctionDef','AA000003')]=function
    d.elements[('', 'ParamDef','AA000004')]=argument
    target.providers[(str(d.path),'','ParamDef','AA000004')]=[(d,argument)]
    files['types.galaxy']+='\nnative void ControlBinding(int control);'
    alias_mapping=Bindings(target,files,['entry.galaxy'])
    assert Generator(target,bindings=alias_mapping).typ(argument,d,('', 'ParamDef','AA000004'),'ParameterType')=='int'


def test_event_reference_conversion_requires_explicit_trigger(tmp_path):
    from xml.etree import ElementTree as ET
    from sc2_mcp.trigger_bindings import Bindings
    root,mods=gui_target(tmp_path)
    path=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree=ET.parse(path)
    tree.getroot().extend(ET.fromstring('''<X>
    <Element Type="FunctionDef" Id="AB000001"><Identifier>Register</Identifier><FlagNative/><FlagEvent/><Parameter Type="ParamDef" Library="Ntve" Id="AB000002"/></Element>
    <Element Type="ParamDef" Id="AB000002"><ParameterType><Type Value="unit"/></ParameterType><ParamFlagReference/></Element></X>'''))
    tree.write(path,encoding='utf-8')
    target=target_for(root,str(mods))
    mapping=Bindings(target,{'n.galaxy':'native void Register(trigger t, unitref u);\nnative unitref UnitRefFromUnit(unit u);'},['n.galaxy'])
    d=next(d for d in target.documents if not d.standard)
    variable=ET.fromstring('<Element><VariableType><Type Value="unit"/></VariableType></Element>')
    param=ET.fromstring('<Element><ParameterDef Type="ParamDef" Library="Ntve" Id="AB000002"/><Variable Type="Variable" Id="AB000003"/></Element>')
    for typ,ident,el in [('Variable','AB000003',variable),('Param','AB000004',param)]:
        d.elements[('',typ,ident)]=el
        target.providers[(str(d.path),'',typ,ident)]=[(d,el)]
    call=ET.fromstring('<Element><FunctionDef Type="FunctionDef" Library="Ntve" Id="AB000001"/><Parameter Type="Param" Id="AB000004"/></Element>')
    generator=Generator(target,bindings=mapping)
    for trigger in ['gt_First','gt_Second']:
        code=generator.call(d,('', 'FunctionCall','AB000005'),call,event_trigger=trigger)
        assert code==f'Register({trigger}, UnitRefFromUnit(gv_AB000003));'
    with pytest.raises(SC2Error,match='explicit registration'):
        generator.call(d,('', 'FunctionCall','AB000005'),call)


def test_compatibility_body_substitutes_parameters_and_blocks_unknown_template(tmp_path):
    from xml.etree import ElementTree as ET
    root,mods=gui_target(tmp_path)
    library=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree=ET.parse(library);x=tree.getroot()
    fragment='''<X>
    <Element Type="FunctionDef" Id="AA000001"><Identifier>Legacy</Identifier><FlagNative/><FlagCall/><ReturnType><Type Value="int"/></ReturnType><Parameter Type="ParamDef" Library="Ntve" Id="AA000002"/><FunctionCall Type="FunctionCall" Library="Ntve" Id="AA000003"/></Element>
    <Element Type="ParamDef" Id="AA000002"><Identifier>Input</Identifier><ParameterType><Type Value="int"/></ParameterType></Element>
    <Element Type="FunctionCall" Id="AA000003"><FunctionDef Type="FunctionDef" Library="Ntve" Id="AA000006"/><Parameter Type="Param" Library="Ntve" Id="AA000004"/><Parameter Type="Param" Library="Ntve" Id="AA000005"/></Element>
    <Element Type="Param" Id="AA000004"><ParameterDef Type="ParamDef" Library="Ntve" Id="AA000007"/><Parameter Type="ParamDef" Library="Ntve" Id="AA000002"/></Element>
    <Element Type="Param" Id="AA000005"><ParameterDef Type="ParamDef" Library="Ntve" Id="AA000008"/><Value>PowerSource</Value><ValueType Type="string"/></Element>
    <Element Type="FunctionDef" Id="AA000006"><Identifier>Modern</Identifier><FlagNative/><FlagCall/><ReturnType><Type Value="int"/></ReturnType><Parameter Type="ParamDef" Library="Ntve" Id="AA000007"/><Parameter Type="ParamDef" Library="Ntve" Id="AA000008"/></Element>
    <Element Type="ParamDef" Id="AA000007"><ParameterType><Type Value="int"/></ParameterType></Element>
    <Element Type="ParamDef" Id="AA000008"><ParameterType><Type Value="string"/></ParameterType></Element>
    </X>'''
    x.extend(ET.fromstring(fragment));tree.write(library,encoding='utf-8')
    natives=library.with_name('natives.galaxy')
    natives.write_text(natives.read_text()+'\nnative int Modern(int p, string link);\n')
    target=target_for(root,str(mods));gen=Generator(target)
    d=next(d for d in target.documents if not d.standard)
    d.elements[('', 'Param','AA000010')]=ET.fromstring('<Element><ParameterDef Type="ParamDef" Library="Ntve" Id="AA000002"/><Value>7</Value><ValueType Type="int"/></Element>')
    target.providers[(str(d.path),'','Param','AA000010')]=[(d,d.elements[('', 'Param','AA000010')])]
    call=ET.fromstring('<Element><FunctionDef Type="FunctionDef" Library="Ntve" Id="AA000001"/><Parameter Type="Param" Id="AA000010"/></Element>')
    assert gen.call(d,('', 'FunctionCall','AA000011'),call,False)=='Modern(7, "PowerSource")'
    nd=next(d for d in target.documents if d.standard=='Ntve')
    ET.SubElement(nd.elements[('Ntve','FunctionDef','AA000001')],'FutureTemplate')
    with pytest.raises(SC2Error) as unsupported:gen.call(d,('', 'FunctionCall','AA000011'),call,False)
    assert unsupported.value.details['call_site']['node']==['','FunctionCall','AA000011']


def test_writer_preserves_unknown_and_hash(tmp_path):
    root = tmp_path / 'Test.SC2Map'; root.mkdir()
    raw = b'<TriggerData>\r\n<Root/>\r\n<!-- keep --><Mystery x="1"/>\r\n</TriggerData>'
    (root/'Triggers').write_bytes(raw)
    changes = plan_write(root, [{'type':'Category','id':'ABCD0001','name':'Test','children':[]}],
                         hashlib.sha256(raw).hexdigest())
    assert b'<!-- keep --><Mystery x="1"/>' in changes['Triggers']
    assert b'<Item Type="Category" Id="ABCD0001"' in changes['Triggers']
    assert (root/'Triggers').read_bytes() == raw
    with pytest.raises(SC2Error, match='fingerprint'):
        plan_write(root, [], 'bad')


def test_writer_rejects_duplicate_and_unsafe_type(tmp_path):
    root=tmp_path/'Test.SC2Map'; root.mkdir()
    (root/'Triggers').write_text('<TriggerData><Root/></TriggerData>')
    with pytest.raises(SC2Error):
        plan_write(root,[{'type':'Structure','id':'ABCD0001'}])
    with pytest.raises(SC2Error):
        plan_write(root,[{'type':'Category','id':'ABCD0001'}, {'type':'Category','id':'ABCD0001'}])


def gui_target(tmp_path):
    import shutil
    root=tmp_path/'Test.SC2Map';root.mkdir()
    mods=tmp_path/'Mods';core=mods/'Core.SC2Mod'; lib=core/'Base.SC2Data/TriggerLibs';lib.mkdir(parents=True)
    (core/'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>')
    (lib/'LibraryList.xml').write_text('<TriggerData><library external="TriggerLibs/NativeLib"/></TriggerData>')
    shutil.copyfile(Path(__file__).parent/'fixtures/trigger-pipeline/NativeLib.TriggerLib',lib/'NativeLib.TriggerLib')
    (lib/'natives.galaxy').write_text('''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringExternal(string key);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
''')
    (root/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Core.SC2Mod</Value></Dependencies></DocInfo>')
    (root/'Triggers').write_text('''<TriggerData><Root><Item Type="Trigger" Id="10000001"/></Root>
    <Element Type="Trigger" Id="10000001"><Identifier>Start</Identifier><Event Type="FunctionCall" Id="10000002"/><Action Type="FunctionCall" Id="10000003"/></Element>
    <Element Type="FunctionCall" Id="10000003"><FunctionDef Type="FunctionDef" Library="Ntve" Id="00000123"/><ScriptCode>// test</ScriptCode></Element>
    <Element Type="FunctionCall" Id="10000002"><FunctionDef Type="FunctionDef" Library="Ntve" Id="00000120"/></Element></TriggerData>''')
    return root,mods


def test_generate_real_dependency_check(tmp_path):
    root,mods=gui_target(tmp_path)
    result=Generator(target_for(root,str(mods))).generate()
    assert 'TriggerCreate("gt_Start_Func")' in result['source']
    assert 'TriggerAddEventMapInit(gt_Start);' in result['source']
    assert result['complete']


def test_unknown_executable_fails(tmp_path):
    root,mods=gui_target(tmp_path)
    p=root/'Triggers';p.write_text(p.read_text().replace('<Identifier>Start</Identifier>','<Identifier>Start</Identifier><FutureAction/>'))
    with pytest.raises(SC2Error,match='unsupported executable'):
        Generator(target_for(root,str(mods))).generate()


@pytest.mark.parametrize('source,passed',[
    ('void InitMap() {}',True),
    ('void InitMap() { int x; x = true; }',False),
    ('void InitMap() { Missing(); }',False),
    ('include "absent"\nvoid InitMap() {}',False),
    ('void InitMap( {',False),
])
def test_real_frontend(source,passed):
    result=check_files({'test.galaxy':source},'test.galaxy')
    assert (result['status']=='static validation passed') is passed


def test_compile_generated_event(tmp_path):
    root,mods=gui_target(tmp_path)
    result=Generator(target_for(root,str(mods))).generate()
    source='native trigger TriggerCreate(string func);\nnative void TriggerAddEventMapInit(trigger t);\n'+result['source']
    checked=check_files({'test.galaxy':source},'test.galaxy')
    assert checked['status']=='static validation passed',checked


def test_frontend_cycle_and_source_map():
    result=check_files({'a.galaxy':'include "b"\nvoid A() { Missing(); }','b.galaxy':'include "a"'},'a.galaxy',
                       [{'start':2,'end':2,'node':['','FunctionCall','1']}])
    assert result['status']=='failed'
    assert any(d.get('gui') for d in result['diagnostics'])


def test_unrelated_source_does_not_pollute_frontend():
    result=check_files({'a.galaxy':'void InitMap() {}','unused.galaxy':'void InitMap() { Missing(); }'},'a.galaxy')
    assert result['status']=='static validation passed'
    assert result['files']==['a.galaxy']


def test_writer_repeat_is_noop(tmp_path):
    root,mods=gui_target(tmp_path)
    op={'type':'Category','id':'ABCD0001','name':'Hello'}
    changes=plan_write(root,[op])
    for p,raw in changes.items():
        dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    assert plan_write(root,[op])=={}


def test_missing_dependency_blocks_generate(tmp_path):
    root,mods=gui_target(tmp_path)
    (root/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Missing.SC2Mod</Value></Dependencies></DocInfo>')
    with pytest.raises(SC2Error):Generator(target_for(root,str(mods))).generate()


def test_shared_operations_are_exposed(tmp_path):
    from sc2_mcp.dispatch import Dispatcher
    d=Dispatcher(tmp_path/'state')
    try:
        assert {'sc2_trigger_write','sc2_trigger_generate','sc2_galaxy_check','sc2_trigger_package'}<=set(d.operations)
    finally:d.close()


def test_pipeline_build_and_stale_guard(tmp_path,monkeypatch):
    from sc2_mcp import trigger_pipeline as pipeline
    root,mods=gui_target(tmp_path)
    lib=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs'
    (lib/'natives.galaxy').write_text('native trigger TriggerCreate(string func);\nnative void TriggerAddEventMapInit(trigger t);\n')
    (lib/'NativeLib.galaxy').write_text('include "TriggerLibs/natives"\nvoid libNtve_InitLib() {}\n')
    class Service:
        def record(self,pid):return {},root
    monkeypatch.setattr(pipeline,'project_runtime',lambda root:tmp_path/'runtime')
    generated=pipeline.generate(Service(),'test',str(mods))
    assert pipeline.check_build(Service(),'test',generated['build_id'])['status']=='static validation passed'
    (root/'Triggers').write_text((root/'Triggers').read_text()+'\n')
    with pytest.raises(SC2Error,match='input changed'):
        pipeline.check_build(Service(),'test',generated['build_id'])


def test_offline_package_proves_exact_generated_entry_without_reading_editor_outputs(tmp_path,monkeypatch):
    import json
    from sc2_mcp import trigger_pipeline as pipeline,trigger_package as package,archives
    root,mods=gui_target(tmp_path)
    from test_shell import make_header
    (root/'DocumentHeader').write_bytes(make_header(['file:Mods/Core.SC2Mod']))
    lib=mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs'
    (lib/'NativeLib.galaxy').write_text('''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringToText(string s);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
void libNtve_InitLib() {}
void UnusedOfficialWrapper(unit u, string key, text tooltip) { UnitSetInfoButtonTooltip(u, key, tooltip); }
''')
    monkeypatch.setattr(pipeline,'native_supplement',lambda target,files:(
        'native void UnitSetInfoButtonTooltip(unit u, string key, text tooltip);\n',
        [{'name':'UnitSetInfoButtonTooltip','scope':'GUI-derived static typing only; engine ABI unverified'}]))
    original=b'// original editor output, must remain untouched'
    (root/'MapScript.galaxy').write_bytes(original)
    denied=mods/'Core.SC2Mod/Base.SC2Data/LibAC040001.galaxy'
    denied.write_text('// inaccessible generated dependency output')
    read_bytes=Path.read_bytes
    def restricted(path):
        if path==denied:raise PermissionError('simulated Win32 5')
        return read_bytes(path)
    monkeypatch.setattr(Path,'read_bytes',restricted)
    class Service:
        def record(self,pid):return {},root
    for module in (pipeline,package):
        monkeypatch.setattr(module,'project_runtime',lambda root:tmp_path/'runtime')
    ordinary=pipeline.generate(Service(),'test',str(mods))
    with pytest.raises(SC2Error,match='runtime_probe'):
        package.package_build(Service(),'test',ordinary['build_id'])
    generated=pipeline.generate(Service(),'test',str(mods),runtime_probe=True)
    manifest=json.loads(Path(generated['manifest']).read_text('utf-8'))
    assert 'agent_native_supplement' not in manifest['files'][manifest['entry']]
    legacy={**manifest,'compile_only_files':[]}
    Path(generated['manifest']).write_text(json.dumps(legacy),encoding='utf-8')
    with pytest.raises(SC2Error,match='legacy build'):
        package.package_build(Service(),'test',generated['build_id'])
    Path(generated['manifest']).write_text(json.dumps(manifest),encoding='utf-8')
    result=package.package_build(Service(),'test',generated['build_id'])
    with archives._managed_reader(Path(result['archive'])) as reader:
        archived=reader.read('MapScript.galaxy')
    assert archived==manifest['files'][manifest['entry']].encode('utf-8')
    assert generated['runtime_marker'].encode() in archived
    assert generated['runtime_marker'] not in (root/'Triggers').read_text()
    assert (root/'MapScript.galaxy').read_bytes()==original
    assert result['verified_archive']['verified']
    assert not any('agent_native_supplement' in f['path'] for f in result['verified_archive']['files'])
    assert result['compile_only_files']==['agent_native_supplement.galaxy']
    assert not result['packaged_runtime_passed']
    (root/'DocumentHeader').write_bytes(make_header(['file:Mods/Stale.SC2Mod']))
    with pytest.raises(SC2Error,match='DocumentHeader'):
        package.package_build(Service(),'test',generated['build_id'])
    (root/'DocumentHeader').write_bytes(make_header(['file:Mods/Core.SC2Mod']))
    (lib/'NativeLib.galaxy').write_text('// concurrent change')
    with pytest.raises(SC2Error,match='input changed'):
        package.package_build(Service(),'test',generated['build_id'])


def test_compile_only_context_preserves_real_diagnostics_and_gui_mapping():
    files={'main.galaxy':'void F() {\n Known(true); Missing();\n}',
           'typing.galaxy':'native void Known(int value);'}
    result=check_files(files,'main.galaxy',[{'start':2,'end':2,'node':['','FunctionCall','1']}],
                       declarations=['typing.galaxy'])
    assert result['status']=='failed'
    assert any(d.get('gui') and 'Missing' in d['message'] for d in result['diagnostics'])
    assert any('type' in d['message'].lower() for d in result['diagnostics'])
    assert result['static_context']['engine_abi_verified'] is False


def test_cross_library_function_return_and_global_initializer(tmp_path):
    root,mods=gui_target(tmp_path)
    helper=mods/'Helper.SC2Mod';helper.mkdir()
    (helper/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Core.SC2Mod</Value></Dependencies></DocInfo>')
    (helper/'Triggers').write_text('''<TriggerData><Library Id="ABCD1234"><Root><Item Type="FunctionDef" Library="ABCD1234" Id="20000001"/></Root>
    <Element Type="FunctionDef" Id="20000001"><Identifier>Identity</Identifier><FlagCall/><ReturnType><Type Value="int"/></ReturnType><Parameter Type="ParamDef" Id="20000002"/><FunctionCall Type="FunctionCall" Id="20000003"/></Element>
    <Element Type="ParamDef" Id="20000002"><Identifier>Input</Identifier><ParameterType><Type Value="int"/></ParameterType></Element>
    <Element Type="FunctionCall" Id="20000003"><FunctionDef Type="FunctionDef" Library="Ntve" Id="00000097"/><Parameter Type="Param" Id="20000004"/></Element>
    <Element Type="Param" Id="20000004"><ParameterDef Type="ParamDef" Library="Ntve" Id="00000488"/><Parameter Type="ParamDef" Id="20000002"/></Element>
    </Library></TriggerData>''')
    p=root/'DocumentInfo';p.write_text(p.read_text().replace('Core.SC2Mod','Helper.SC2Mod'))
    p=root/'Triggers';s=p.read_text().replace('</Root>','<Item Type="Variable" Id="30000001"/></Root>')
    s=s.replace('</TriggerData>','''<Element Type="Variable" Id="30000001"><Identifier>Result</Identifier><VariableType><Type Value="int"/></VariableType><Value Type="Param" Id="30000002"/></Element>
    <Element Type="Param" Id="30000002"><FunctionCall Type="FunctionCall" Id="30000003"/></Element>
    <Element Type="FunctionCall" Id="30000003"><FunctionDef Type="FunctionDef" Library="ABCD1234" Id="20000001"/><Parameter Type="Param" Id="30000004"/></Element>
    <Element Type="Param" Id="30000004"><ParameterDef Type="ParamDef" Library="ABCD1234" Id="20000002"/><Value>7</Value><ValueType Type="int"/></Element></TriggerData>''');p.write_text(s)
    generated=Generator(target_for(root,str(mods))).generate()
    assert 'libABCD1234_gf_Identity(7)' in generated['source']
    assert 'int libABCD1234_gf_Identity(int lp_Input)' in generated['source']
    assert 'return lp_Input;' in generated['source']
    assert 'libABCD1234_lp_Input' not in generated['source']
    source='native trigger TriggerCreate(string func);\nnative void TriggerAddEventMapInit(trigger t);\n'+generated['source']
    checked=check_files({'test.galaxy':source},'test.galaxy')
    assert checked['status']=='static validation passed',checked


@pytest.mark.parametrize('function,subtype,expected',[
    ('00000137','00000004','if (true)'),
    ('71596144','A1B37466','while (true)'),
    ('CEDAB9C3','4945FAA8','while (true)'),
])
def test_control_flow_and_local_declarations(tmp_path,function,subtype,expected):
    root,mods=gui_target(tmp_path)
    p=root/'Triggers';s=p.read_text().replace('<Action Type="FunctionCall" Id="10000003"/>','<Variable Type="Variable" Id="40000001"/><Action Type="FunctionCall" Id="40000002"/>')
    s=s.replace('<ScriptCode>// test</ScriptCode>','<SubFunctionType Type="SubFuncType" Library="Ntve" Id="'+subtype+'"/><ScriptCode>// test</ScriptCode>')
    s=s.replace('</TriggerData>','''<Element Type="Variable" Id="40000001"><Identifier>Local</Identifier><VariableType><Type Value="int"/></VariableType></Element>
    <Element Type="FunctionCall" Id="40000002"><FunctionDef Type="FunctionDef" Library="Ntve" Id="'''+function+'''"/><FunctionCall Type="FunctionCall" Id="10000003"/></Element></TriggerData>''')
    p.write_text(s)
    generated=Generator(target_for(root,str(mods))).generate()
    assert expected in generated['source']
    source='native trigger TriggerCreate(string func);\nnative void TriggerAddEventMapInit(trigger t);\n'+generated['source']
    checked=check_files({'test.galaxy':source},'test.galaxy')
    assert checked['status']=='static validation passed',checked


def test_writer_transaction_and_conflict(tmp_path,monkeypatch):
    from sc2_mcp.service import Service
    from sc2_mcp.trigger_pipeline import write
    root,mods=gui_target(tmp_path)
    service=Service(tmp_path/'state');monkeypatch.setattr(service,'editor_conflict',lambda:False)
    project=service.projects.open(str(root),True,search_roots=[str(mods)])['project_id']
    before=(root/'Triggers').read_bytes()
    candidate=write(service,project,[{'type':'Category','id':'AA000001','name':'New'}],mods_dir=str(mods))
    assert candidate['state']=='prepared'
    assert (root/'Triggers').read_bytes()==before
    (root/'Triggers').write_bytes(before+b'\n')
    with pytest.raises(SC2Error):service.apply_candidate(project,candidate['change_id'])


def test_player_strings_and_unavailable_frontend(tmp_path,monkeypatch):
    root,mods=gui_target(tmp_path)
    changes=plan_write(root,[{'type':'Category','id':'AA000001','strings':{'Param/Value/AA000002':'Hello'}}])
    assert b'Param/Value/AA000002=Hello' in changes['zhCN.SC2Data/LocalizedData/GameStrings.txt']
    monkeypatch.setenv('SC2_GALAXY_NODE',str(tmp_path/'missing-node'))
    with pytest.raises(SC2Error) as caught:check_files({'a.galaxy':'void F() {}'},'a.galaxy')
    assert caught.value.code=='galaxy_frontend_unavailable'


def test_saved_editor_event_shape(tmp_path):
    import json,re
    saved=json.loads((Path(__file__).parent/'fixtures/trigger-pipeline/saved-editor-shapes.json').read_text())
    root,mods=gui_target(tmp_path)
    generated=Generator(target_for(root,str(mods))).generate()['source']
    # Same registration ordering as the upstream saved editor fixture, with
    # different map-local symbols and deliberately different formatting.
    for source in (saved['trigger_init'],generated):
        calls=re.findall(r'\b(TriggerCreate|TriggerAddEventMapInit)\s*\(',source)
        assert calls==['TriggerCreate','TriggerAddEventMapInit']


def test_loading_order_object_is_respected(tmp_path):
    root,mods=gui_target(tmp_path)
    target=target_for(root,str(mods))
    assert isinstance(target.graph['loading_order'],dict)
    assert Generator(target).generate()['complete']


def test_return_call_is_not_a_native_declaration():
    from types import SimpleNamespace
    from xml.etree import ElementTree as ET
    from sc2_mcp.trigger_pipeline import native_supplement
    element=ET.fromstring('<Element><Identifier>DataTableInstanceGetInt</Identifier><FlagNative/><ReturnType><Type Value="int"/></ReturnType></Element>')
    doc=SimpleNamespace(standard='Ntve',elements={('Ntve','FunctionDef','256B019E'):element},path=Path('NativeLib.TriggerLib'),sha256='fixture')
    source,evidence=native_supplement(SimpleNamespace(documents=[doc]),{'a.galaxy':'int F() {\n return DataTableInstanceGetInt();\n}'})
    assert 'native int DataTableInstanceGetInt(' in source
    assert len(evidence)==1


def test_editor_saved_text_parameter_without_value(tmp_path):
    from xml.etree import ElementTree as ET
    from sc2_triggers import Document
    root,mods=gui_target(tmp_path)
    d=Document(root/'Triggers')
    e=ET.fromstring('<Element Type="Param" Id="AC010008"><ValueType Type="text"/></Element>')
    value=Generator(target_for(root,str(mods))).expr(d,('', 'Param','AC010008'),e)
    assert value=='StringExternal("Param/Value/AC010008")'


def test_actual_editor_smoke_fixture_text_readback(tmp_path):
    import json
    from xml.etree import ElementTree as ET
    from sc2_triggers import Document
    saved=json.loads((Path(__file__).parent/'fixtures/trigger-pipeline/editor-98370-smoke.json').read_text(encoding='utf-8'))
    root,mods=gui_target(tmp_path)
    d=Document(root/'Triggers')
    e=ET.fromstring(saved['triggers_xml']).find("Element[@Type='Param'][@Id='AC010008']")
    assert e.find('Value') is None
    expression=Generator(target_for(root,str(mods))).expr(d,('', 'Param','AC010008'),e)
    assert expression in saved['editor_galaxy']
    for statement in saved['matching_statements']:
        assert statement in saved['editor_galaxy']


def test_gui_acceptance_matrix_compiles_with_real_native_definitions(tmp_path):
    import importlib.util,shutil
    from xml.etree import ElementTree as ET
    module=Path(__file__).parent/'acceptance/gui_matrix.py'
    spec=importlib.util.spec_from_file_location('gui_matrix_acceptance',module)
    matrix_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix_module)
    root,mods=gui_target(tmp_path)
    shutil.copyfile(Path(__file__).parent/'fixtures/trigger-pipeline/matrix-native.TriggerLib',
                    mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib')
    matrix=matrix_module.Matrix(target_for(root,str(mods)));ops=matrix.build()
    tree=ET.Element('TriggerData')
    library=ET.SubElement(tree,'Library',{'Id':matrix_module.LIB});ET.SubElement(library,'Root')
    ET.SubElement(tree,'Root')
    (root/'Triggers').write_bytes(ET.tostring(tree))
    for relative,raw in plan_write(root,ops,locale='enUS').items():
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    source=Generator(target_for(root,str(mods))).generate()['source']
    assert 'while ((gv_LoopIndex < 3))' in source
    assert 'gv_MatrixScore = -999;' not in source
    assert 'libAC030001_gf_AddFiveAndStore(gv_MatrixScore)' in source
    declarations='''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringExternal(string key);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
'''
    checked=check_files({'matrix.galaxy':declarations+source},'matrix.galaxy')
    assert checked['status']=='static validation passed',checked
    assert len([s for s in matrix.messages if s.endswith('_PASS')])==6


def test_writer_library_root_registration_is_explicit(tmp_path):
    from xml.etree import ElementTree as ET
    root=tmp_path/'Test.SC2Map';root.mkdir()
    (root/'Triggers').write_text('<TriggerData><Root/><Library Id="AC030001"><Root/></Library></TriggerData>')
    op={'type':'FunctionDef','id':'AC020003','library':'AC030001','children':[{'tag':'FlagAction'}]}
    result=plan_write(root,[op])
    tree=ET.fromstring(result['Triggers'])
    item=tree.find('Library/Root/Item')
    assert item.get('Library')=='AC030001'
    (root/'Triggers').write_bytes(result['Triggers'])
    assert plan_write(root,[op])=={}


def test_writer_repairs_unqualified_library_membership(tmp_path):
    from xml.etree import ElementTree as ET
    root=tmp_path/'Test.SC2Map';root.mkdir()
    (root/'Triggers').write_text('<TriggerData><Root/><Library Id="AC030001"><Root><Item Type="Variable" Id="AC020008"/></Root><Element Type="Variable" Id="AC020008"/></Library></TriggerData>')
    result=plan_write(root,[{'type':'Variable','id':'AC020008','library':'AC030001'}])
    assert ET.fromstring(result['Triggers']).find('Library/Root/Item').get('Library')=='AC030001'


@pytest.mark.parametrize('xml',[
    '<TriggerData><Root/><Library Id="AC030001"><Root/></Library></TriggerData>',
    '<TriggerData><Library Id="AC030001"><Root><Item Type="Variable" Id="AC020008"/></Root></Library><Root/></TriggerData>',
])
def test_unsupported_editor_library_layout_is_not_compiler_success(xml):
    from xml.etree import ElementTree as ET
    from sc2_mcp.trigger_writer import validate_editor_library_layout
    with pytest.raises(SC2Error,match='unsupported Editor library'):
        validate_editor_library_layout(ET.fromstring(xml))


def test_editor_saved_matrix_regenerates_and_typechecks(tmp_path):
    import json,shutil
    fixtures=Path(__file__).parent/'fixtures/trigger-pipeline'
    saved=json.loads((fixtures/'editor-98370-matrix.json').read_text(encoding='utf-8'))
    root,mods=gui_target(tmp_path)
    shutil.copyfile(fixtures/'matrix-native.TriggerLib',mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib')
    (root/'Triggers').write_text(saved['triggers_xml'],encoding='utf-8')
    source=Generator(target_for(root,str(mods))).generate()['source']
    declarations='''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringExternal(string key);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
'''
    result=check_files({'matrix.galaxy':declarations+source},'matrix.galaxy')
    assert result['status']=='static validation passed',result
    assert 'libAC030001_gf_AddFiveAndStore(gv_MatrixScore);' in source
    assert 'gv_MatrixScore = -999;' not in source


def test_independent_mod_link_pair_resolves_and_compiles(tmp_path,monkeypatch):
    import importlib.util,json,shutil
    fixtures=Path(__file__).parent/'fixtures/trigger-pipeline'
    source,mods=gui_target(tmp_path)
    shutil.copyfile(fixtures/'matrix-native.TriggerLib',mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib')
    saved=json.loads((fixtures/'editor-98370-matrix.json').read_text(encoding='utf-8'))
    (source/'Triggers').write_text(saved['triggers_xml'],encoding='utf-8')
    path=Path(__file__).parent/'acceptance/mod_link.py'
    spec=importlib.util.spec_from_file_location('mod_link_acceptance',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'WORKSPACE',tmp_path)
    shell=tmp_path/'NativeShell.SC2Mod';shell.mkdir()
    (shell/'DocumentHeader').write_bytes(b'opaque native shell header fixture')
    (shell/'DocumentInfo').write_bytes((source/'DocumentInfo').read_bytes())
    (shell/'Triggers').write_text('<TriggerData/>')
    (shell/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent><DataComponent Type="trig">Triggers</DataComponent><DataComponent Type="text" Locale="enUS">GameText</DataComponent></Components>')
    (shell/'enUS.SC2Data/LocalizedData').mkdir(parents=True)
    for name in ['DocumentInfo.version','Triggers.version','GameText.version']:
        (shell/name).write_bytes(b'opaque native version fixture')
    result=module.prepare(source,tmp_path/'pair',shell)
    staged=Path(result['staged_mod'])
    # Use one explicit local dependency root for the reference Core and test Mod.
    shutil.copytree(mods/'Core.SC2Mod',staged.parent/'Core.SC2Mod')
    from sc2_triggers import Target
    target=Target(Path(result['map']),staged.parent,None)
    generated=Generator(target).generate()['source']
    assert 'libAC040001_gf_AddFiveAndStore(gv_MatrixScore);' in generated
    assert 'void libAC040001_gf_AddFiveAndStore(' in generated
    for name in ['DocumentHeader','ComponentList.SC2Components','DocumentInfo','DocumentInfo.version','Triggers.version','GameText.version']:
        assert (staged/name).read_bytes()==(shell/name).read_bytes()
    declarations='''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringExternal(string key);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
'''
    checked=check_files({'modlink.galaxy':declarations+generated},'modlink.galaxy')
    assert checked['status']=='static validation passed',checked
    with pytest.raises(ValueError,match='NEW workspace directory'):
        module.prepare(source,tmp_path/'pair',shell)
    incomplete=tmp_path/'Incomplete.SC2Mod';incomplete.mkdir()
    with pytest.raises(ValueError,match='native Mod shell incomplete'):
        module.prepare(source,tmp_path/'bad-pair',incomplete)
    assert not (tmp_path/'bad-pair').exists()


def test_editor_saved_independent_mod_pair_regenerates(tmp_path):
    import json,shutil
    fixtures=Path(__file__).parent/'fixtures/trigger-pipeline'
    saved=json.loads((fixtures/'editor-98370-modlink.json').read_text(encoding='utf-8'))
    root,mods=gui_target(tmp_path)
    shutil.copyfile(fixtures/'matrix-native.TriggerLib',mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib')
    (root/'Triggers').write_text(saved['map_triggers_xml'],encoding='utf-8')
    (root/'DocumentInfo').write_text(saved['map_document_info'],encoding='utf-8')
    mod=mods/'CodexGuiLinkAcceptanceV2.SC2Mod';mod.mkdir()
    (mod/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Core.SC2Mod</Value></Dependencies></DocInfo>')
    (mod/'Triggers').write_text(saved['mod_triggers_xml'],encoding='utf-8')
    from sc2_triggers import Target
    source=Generator(Target(root,mods,None)).generate()['source']
    assert 'libAC040001_gf_AddFiveAndStore(gv_MatrixScore);' in source
    declarations='''native trigger TriggerCreate(string func);
native void TriggerAddEventMapInit(trigger t);
native playergroup PlayerGroupAll();
native text StringExternal(string key);
native void UIDisplayMessage(playergroup p, int area, text message);
const int c_messageAreaChat = 0;
'''
    result=check_files({'modlink.galaxy':declarations+source},'modlink.galaxy')
    assert result['status']=='static validation passed',result
    import re
    body=saved['generated_mod_library']['snapshot']
    header=saved['generated_mod_header']['snapshot']
    assert hashlib.sha256(body.encode('utf-8')).hexdigest()==saved['generated_mod_library']['sha256']
    assert hashlib.sha256(header.encode('utf-8')).hexdigest()==saved['generated_mod_header']['sha256']
    for code in (body,source.replace('libAC040001_lp_Input','lp_Input')):
        assert 'libAC040001_gv_CrossLibraryResult = (lp_Input + 5);' in code
        assert re.search(r'void libAC040001_gf_AddFiveAndStore\s*\(int lp_Input\)',code)
    assert 'int libAC040001_gv_CrossLibraryResult;' in header
    assert body.index('libAC040001_InitLibraries();')<body.index('libAC040001_InitVariables();')
    official=re.sub(r'^include .*$', '',header+'\n'+body,flags=re.M)
    checked=check_files({'official.galaxy':'void libNtve_InitVariables() {}\n'+official},'official.galaxy')
    assert checked['status']=='static validation passed',checked
