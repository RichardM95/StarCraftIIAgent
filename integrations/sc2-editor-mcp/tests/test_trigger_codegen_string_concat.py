import json
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.storage import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def concat_case(tmp_path, values, *, template=None, shadow=False, wrong_type=False):
    root, mods = gui_target(tmp_path)
    native = mods / 'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree = ET.parse(native)
    definition = ET.fromstring('''<Element Type="FunctionDef" Id="00000131">
      <Identifier>CombineStrings</Identifier><FlagCall/><FlagOperator/>
      <ReturnType><Type Value="string"/></ReturnType>
      <Parameter Type="ParamDef" Library="Ntve" Id="00000212"/>
      <Parameter Type="ParamDef" Library="Ntve" Id="00000213"/>
      <ScriptCode>(#PARAM(str1) + #PARAM(str2))</ScriptCode>
    </Element>''')
    if template is not None:
        definition.find('ScriptCode').text = template
    tree.getroot().append(definition)
    for ident, name in [('00000212', 'str1'), ('00000213', 'str2')]:
        tree.getroot().append(ET.fromstring(
            f'<Element Type="ParamDef" Id="{ident}"><Identifier>{name}</Identifier>'
            '<ParameterType><Type Value="string"/></ParameterType></Element>'))
    if wrong_type:
        definition.find('ReturnType/Type').set('Value', 'int')
    tree.write(native, encoding='utf-8')
    target = target_for(root, str(mods))
    doc = next(d for d in target.documents if not d.standard)
    serial = 0

    def local(kind, element):
        nonlocal serial
        serial += 1
        ident = f'{0xCA180000 + serial:08X}'
        key = ('', kind, ident)
        doc.elements[key] = element
        target.providers[(str(doc.path), *key)] = [(doc, element)]
        return ident

    if shadow:
        shadow_id = local('FunctionDef', ET.fromstring(ET.tostring(definition)))
        definition_ref = {'Type': 'FunctionDef', 'Id': shadow_id}
    else:
        definition_ref = {'Type': 'FunctionDef', 'Library': 'Ntve', 'Id': '00000131'}

    def expression(pair):
        call = ET.Element('Element')
        ET.SubElement(call, 'FunctionDef', definition_ref)
        for slot, value in zip(['00000212', '00000213'], pair):
            param = ET.Element('Element')
            ET.SubElement(param, 'ParameterDef', {'Type': 'ParamDef', 'Library': 'Ntve', 'Id': slot})
            if isinstance(value, tuple):
                child_id, _ = expression(value)
                ET.SubElement(param, 'FunctionCall', {'Type': 'FunctionCall', 'Id': child_id})
            else:
                ET.SubElement(param, 'Value').text = value
                ET.SubElement(param, 'ValueType', {'Type': 'string'})
            param_id = local('Param', param)
            ET.SubElement(call, 'Parameter', {'Type': 'Param', 'Id': param_id})
        ident = local('FunctionCall', call)
        return ident, call

    ident, call = expression(values)
    return Generator(target), doc, ('', 'FunctionCall', ident), call


@pytest.mark.parametrize('values', [('', '42'), ('KRStukovWave.', '42'), ('寒冰"', '\n.timer')])
def test_official_string_concat_preserves_literal_escaping(tmp_path, values):
    generator, doc, key, call = concat_case(tmp_path, values)
    expected = '(' + json.dumps(values[0], ensure_ascii=True) + ' + ' + json.dumps(values[1], ensure_ascii=True) + ')'
    assert generator.call(doc, key, call, False) == expected


def test_nested_string_concat_preserves_grouping(tmp_path):
    generator, doc, key, call = concat_case(tmp_path, ('KRStukovWave.', ('42', '.timer')))
    assert generator.call(doc, key, call, False) == '("KRStukovWave." + ("42" + ".timer"))'


@pytest.mark.parametrize('kwargs', [
    {'template': '(#PARAM(str1) - #PARAM(str2))'},
    {'shadow': True},
    {'wrong_type': True},
])
def test_string_concat_rejects_unverified_templates_and_signatures(tmp_path, kwargs):
    generator, doc, key, call = concat_case(tmp_path, ('a', 'b'), **kwargs)
    with pytest.raises(SC2Error, match='unsupported expression template'):
        generator.call(doc, key, call, False)
