from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import pytest

from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree

ID = ('Ntve', 'FunctionDef', '86E40471')
SLOTS = ['174E8B8C', 'BD48D330']


class Mapping:
    def raw_type(self, element, document, key, tag):
        t = element.find(tag + '/Type')
        return t.get('Value') if t is not None else None


def setup():
    t = Tree()
    t.generator.bindings = Mapping()
    for element in E.parse(Path(__file__).parent / 'fixtures' / 'combine_text_native.xml').getroot():
        t.nodes[('Ntve', element.get('Type'), element.get('Id'))] = deepcopy(element)
    return t


def combine(t, left='Test/Prefix', right='Test/Base'):
    c = t.call(ID)
    for slot, value in zip(SLOTS, [left, right]):
        p = t.put('Param')
        t.ref(t.nodes[p], 'ParameterDef', ('Ntve', 'ParamDef', slot))
        if isinstance(value, tuple):
            t.ref(t.nodes[p], 'FunctionCall', value)
        else:
            E.SubElement(t.nodes[p], 'ValueType', Type='text')
            E.SubElement(t.nodes[p], 'Value').text = value
        t.ref(t.nodes[c], 'Parameter', p)
    return c


def test_text_handles_remain_text_expressions():
    t = setup()
    c = combine(t)
    assert t.generator.call(t.doc, c, t.nodes[c], False) == '(StringExternal("Test/Prefix") + StringExternal("Test/Base"))'


def test_nested_composition_and_argument_binding_order():
    t = setup()
    c = combine(t, right=combine(t, 'Test/Inner', 'Test/Base'))
    ref = t.nodes[c].findall('Parameter')[0]
    t.nodes[c].remove(ref)
    t.nodes[c].append(ref)
    code = t.generator.call(t.doc, c, t.nodes[c], False)
    assert code == '(StringExternal("Test/Prefix") + (StringExternal("Test/Inner") + StringExternal("Test/Base")))'


@pytest.mark.parametrize('mutation', ['template', 'name', 'return', 'paramtype', 'paramname', 'paramid', 'operatorflag', 'callflag', 'nativeflag', 'statement', 'foreign'])
def test_unverified_text_templates_fail_closed(mutation):
    t = setup()
    c = combine(t)
    f = t.nodes[ID]
    if mutation == 'template': f.find('ScriptCode').text = '(#PARAM(text1) - #PARAM(text2))'
    elif mutation == 'name': f.find('Identifier').text = 'CombineSomething'
    elif mutation == 'return': f.find('ReturnType/Type').set('Value', 'string')
    elif mutation == 'paramtype': t.nodes[('Ntve', 'ParamDef', SLOTS[0])].find('ParameterType/Type').set('Value', 'string')
    elif mutation == 'paramname': t.nodes[('Ntve', 'ParamDef', SLOTS[0])].find('Identifier').text = 'other'
    elif mutation == 'paramid':
        original = ('Ntve', 'ParamDef', SLOTS[0])
        target = ('Ntve', 'ParamDef', 'CA630001')
        t.nodes[target] = deepcopy(t.nodes[original])
        f.findall('Parameter')[0].set('Id', target[2])
        for key, node in t.nodes.items():
            if key[1] == 'Param' and node.find('ParameterDef') is not None and node.find('ParameterDef').get('Id') == SLOTS[0]: node.find('ParameterDef').set('Id', target[2])
    elif mutation in ['operatorflag', 'callflag']: f.remove(f.find('FlagOperator' if mutation == 'operatorflag' else 'FlagCall'))
    elif mutation == 'nativeflag': E.SubElement(f, 'FlagNative')
    elif mutation == 'foreign':
        foreign = ('Else', 'FunctionDef', ID[2])
        t.nodes[foreign] = deepcopy(f)
        t.nodes[c].find('FunctionDef').set('Library', 'Else')
    with pytest.raises(SC2Error):
        t.generator.call(t.doc, c, t.nodes[c], mutation == 'statement')
