"""Actual one-dimensional global int array shapes; emitter/GUI validation, not gameplay."""
import xml.etree.ElementTree as E
import pytest
from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from sc2_mcp.galaxy_frontend import check_files
from test_trigger_pipeline import gui_target


def fixture(tmp_path, mutate=None):
    root, mods = gui_target(tmp_path)
    tree = E.parse(root/'Triggers')
    lib = E.SubElement(tree.getroot(),'Library',Id='A431EF10')
    tree.getroot().remove(lib)
    tree.getroot().insert(0,lib)
    registry = E.SubElement(lib,'Root')
    elements = [E.fromstring(x) for x in ['<Element Type="Variable" Id="35A83956">\n            <VariableType>\n                <Type Value="int" />\n                <ArraySize Dim="0" Value="10" />\n            </VariableType>\n            <Value Type="Param" Library="A431EF10" Id="7B6C6E32" />\n        </Element>\n        ', '<Element Type="Variable" Id="7959C8A9">\n            <VariableType>\n                <Type Value="int" />\n                <ArraySize Dim="0" Type="Variable" Library="A431EF10" Id="03F18ABA" />\n            </VariableType>\n            <Value Type="Param" Library="A431EF10" Id="BA2A88F0" />\n        </Element>\n        ']]
    elements += list(E.fromstring('<X><Element Type="Variable" Id="03F18ABA">\n            <VariableType>\n                <Type Value="int" />\n                <Constant />\n            </VariableType>\n            <Value Type="Param" Library="A431EF10" Id="26589CCC" />\n        </Element>\n        \n<Element Type="Param" Id="26589CCC">\n            <Value>10</Value>\n            <ValueType Type="int" />\n        </Element>\n        \n<Element Type="Param" Id="7B6C6E32">\n            <Value>0</Value>\n            <ValueType Type="int" />\n        </Element>\n        \n<Element Type="Param" Id="BA2A88F0">\n            <Value>0</Value>\n            <ValueType Type="int" />\n        </Element>\n        </X>'))
    names = {'35A83956':'Offered','7959C8A9':'Shop','03F18ABA':'Slots'}
    for node in elements:
        lib.append(node)
        if node.get('Type') == 'Variable':
            E.SubElement(node,'Identifier').text = names[node.get('Id')]
            E.SubElement(registry,'Item',Type='Variable',Library='A431EF10',Id=node.get('Id'))
    if mutate:
        mutate(lib)
    # Read/write both boundary slots; no substitute default initialization.
    tree.getroot().find("Element[@Id='10000003']/ScriptCode").text = 'libA431EF10_gv_Offered[0] = 23;\nlibA431EF10_gv_Shop[10] = libA431EF10_gv_Offered[0];'
    tree.write(root/'Triggers',encoding='utf-8')
    return root, mods, lib

def test_actual_two_globals_and_forward_constant_declare_once(tmp_path):
    root, mods, _ = fixture(tmp_path)
    out = Generator(target_for(root,str(mods))).generate()
    source = out['source']
    for symbol in ('Offered','Shop'):
        assert source.count('int[11] libA431EF10_gv_'+symbol+';') == 1
        assert 'libA431EF10_gv_'+symbol+' = ' not in source
    assert source.count('const int libA431EF10_gv_Slots = 10;') == 1
    assert source.index('const int libA431EF10_gv_Slots = 10;') < source.index('bool gt_Start_Func')
    assert 'libA431EF10_gv_Slots =' not in source[source.index('void InitMap()'):]
    header = (mods/'Core.SC2Mod/Base.SC2Data/TriggerLibs/natives.galaxy').read_text()
    checked = check_files({'test.galaxy':header+source},'test.galaxy')
    assert checked['status'] == 'static validation passed', checked
    assert all(1 <= m['start'] <= m['end'] <= len(source.splitlines()) for m in out['source_map'])

def test_existing_scalar_initializer_keeps_original_initmap_order(tmp_path):
    def add_scalar(lib):
        n=E.SubElement(lib,'Element',Type='Variable',Id='E0509001')
        E.SubElement(n,'Identifier').text='ExistingScalar'
        E.SubElement(E.SubElement(n,'VariableType'),'Type',Value='int')
        E.SubElement(n,'Value',Type='Param',Library='A431EF10',Id='E0509002')
        p=E.SubElement(lib,'Element',Type='Param',Id='E0509002')
        E.SubElement(p,'ValueType',Type='int')
        E.SubElement(p,'Value').text='7'
        E.SubElement(lib.find('Root'),'Item',Type='Variable',Library='A431EF10',Id='E0509001')
    root,mods,_=fixture(tmp_path,add_scalar)
    source=Generator(target_for(root,str(mods))).generate()['source']
    init=source[source.index('void InitMap()'):]
    assert init.count('libA431EF10_gv_ExistingScalar = 7;')==1
    assert source.count('int libA431EF10_gv_ExistingScalar;')==1

def test_absent_array_defaults_remain_natural_zero(tmp_path):
    def remove_defaults(lib):
        for ident in ('35A83956','7959C8A9'):
            node=lib.find(f"Element[@Id='{ident}']")
            node.remove(node.find('Value'))
    root,mods,_=fixture(tmp_path,remove_defaults)
    source=Generator(target_for(root,str(mods))).generate()['source']
    assert 'int[11] libA431EF10_gv_Offered;' in source
    assert 'int[11] libA431EF10_gv_Shop;' in source
    assert 'gv_Offered = ' not in source and 'gv_Shop = ' not in source

@pytest.mark.parametrize('maximum',[0,8191])
def test_global_literal_and_constant_maximum_boundaries(tmp_path,maximum):
    def change(lib):
        lib.find("Element[@Id='35A83956']/VariableType/ArraySize").set('Value',str(maximum))
        lib.find("Element[@Id='26589CCC']/Value").text=str(maximum)
    root,mods,_=fixture(tmp_path,change)
    source=Generator(target_for(root,str(mods))).generate()['source']
    assert 'int['+str(maximum+1)+'] libA431EF10_gv_Offered;' in source
    assert 'int['+str(maximum+1)+'] libA431EF10_gv_Shop;' in source

@pytest.mark.parametrize('bad',['-1','8192','1.5'])
def test_constant_maximum_must_be_bounded_integer_literal(tmp_path,bad):
    def change(lib):lib.find("Element[@Id='26589CCC']/Value").text=bad
    root,mods,_=fixture(tmp_path,change)
    with pytest.raises(SC2Error):Generator(target_for(root,str(mods))).generate()

def test_registered_arrays_keep_literal_and_dynamic_index_and_registration(tmp_path):
    root,mods,_=fixture(tmp_path)
    gen=Generator(target_for(root,str(mods)))
    gen.generate()
    d=next(d for d in gen.target.documents if ('A431EF10','Variable','35A83956') in d.elements)
    for index in ('0','10'):
        ik=('A431EF10','Param','E0509021')
        ie=E.fromstring(f'<Element Type="Param" Id="E0509021"><ValueType Type="int"/><Value>{index}</Value></Element>')
        d.elements[ik]=ie
        gen.target.providers[('',*ik)]=[(d,ie)]
        p=E.fromstring('<Element><Variable Type="Variable" Library="A431EF10" Id="35A83956"/><Array Type="Param" Library="A431EF10" Id="E0509021"/></Element>')
        assert gen.expr(d,('A431EF10','Param','E0509022'),p)==f'libA431EF10_gv_Offered[{index}]'
        assert (str(d.path),('A431EF10','Variable','35A83956')) in gen.global_variables
    vk=('A431EF10','Variable','E0509030')
    ve=E.fromstring('<Element Type="Variable" Id="E0509030"><Identifier>LoopIndex</Identifier><VariableType><Type Value="int"/></VariableType></Element>')
    d.elements[vk]=ve
    gen.target.providers[('',*vk)]=[(d,ve)]
    d.elements[ik]=E.fromstring('<Element Type="Param" Id="E0509021"><Variable Type="Variable" Library="A431EF10" Id="E0509030"/></Element>')
    gen.target.providers[('',*ik)]=[(d,d.elements[ik])]
    assert gen.expr(d,('A431EF10','Param','E0509022'),p)=='libA431EF10_gv_Offered[libA431EF10_gv_LoopIndex]'

@pytest.mark.parametrize('corruption',['nonzero','expression','dynamic-bound','negative','oversize','dimension','global-string','const-nonliteral'])
def test_actual_global_array_unsupported_shapes_fail(tmp_path,corruption):
    def corrupt(lib):
        first=lib.find("Element[@Id='35A83956']")
        second=lib.find("Element[@Id='7959C8A9']")
        param=lib.find("Element[@Id='7B6C6E32']")
        bound=second.find('VariableType/ArraySize')
        if corruption=='nonzero':param.find('Value').text='1'
        elif corruption=='expression':
            param.remove(param.find('Value'))
            E.SubElement(param,'Variable',Type='Variable',Library='A431EF10',Id='03F18ABA')
        elif corruption=='dynamic-bound':
            v=lib.find("Element[@Id='03F18ABA']/VariableType")
            v.remove(v.find('Constant'))
        elif corruption=='negative':first.find('VariableType/ArraySize').set('Value','-1')
        elif corruption=='oversize':first.find('VariableType/ArraySize').set('Value','8192')
        elif corruption=='dimension':bound.set('Dim','1')
        elif corruption=='global-string':first.find('VariableType/Type').set('Value','string')
        elif corruption=='const-nonliteral':lib.find("Element[@Id='26589CCC']/ValueType").set('Type','fixed')
    root,mods,_=fixture(tmp_path,corrupt)
    with pytest.raises(SC2Error):Generator(target_for(root,str(mods))).generate()
