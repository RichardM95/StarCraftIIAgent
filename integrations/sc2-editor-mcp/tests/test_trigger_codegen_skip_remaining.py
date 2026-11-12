from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.storage import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def skip_case(tmp_path, *, template='\n            return #DEFRETURN;\n        ', shadow=False):
    root, mods = gui_target(tmp_path)
    native = mods / 'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree = ET.parse(native)
    definition = ET.fromstring('''<Element Type="FunctionDef" Id="00000139">
      <Identifier>SkipRemaining</Identifier><FlagAction/><FlagOperator/>
      <ScriptCode>return #DEFRETURN;</ScriptCode>
    </Element>''')
    definition.find('ScriptCode').text = template
    tree.getroot().append(definition)
    tree.write(native, encoding='utf-8')
    target = target_for(root, str(mods))
    doc = next(d for d in target.documents if not d.standard)
    if shadow:
        key = ('', 'FunctionDef', 'CA330010')
        doc.elements[key] = definition
        target.providers[(str(doc.path), *key)] = [(doc, definition)]
        ref = {'Type': 'FunctionDef', 'Id': key[2]}
    else:
        ref = {'Type': 'FunctionDef', 'Library': 'Ntve', 'Id': '00000139'}
    call = ET.Element('Element', Type='FunctionCall', Id='CA330011')
    ET.SubElement(call, 'FunctionDef', ref)
    key = ('', 'FunctionCall', 'CA330011')
    doc.elements[key] = call
    target.providers[(str(doc.path), *key)] = [(doc, call)]
    return Generator(target), doc, key, call


def executable(kind='FunctionDef', returns=None):
    node = ET.Element('Element', Type=kind, Id='CA330012')
    ET.SubElement(node, 'Identifier').text = 'Caller'
    if returns is not None:
        ET.SubElement(ET.SubElement(node, 'ReturnType'), 'Type', Value=returns)
    ET.SubElement(node, 'Action' if kind == 'Trigger' else 'FunctionCall',
                  Type='FunctionCall', Id='CA330011')
    return ('', kind, 'CA330012'), node


@pytest.mark.parametrize('returns', [None, 'void'])
def test_skip_remaining_emits_plain_return_only_in_void_function(tmp_path, returns):
    generator, doc, _, _ = skip_case(tmp_path)
    key, caller = executable(returns=returns)
    assert generator.body(doc, key, caller) == 'return;'
    assert not getattr(generator, 'void_action_scope', False)


@pytest.mark.parametrize('kind,returns', [('FunctionDef', 'bool'), ('FunctionDef', 'int'), ('Trigger', None)])
def test_skip_remaining_does_not_guess_value_or_trigger_default_return(tmp_path, kind, returns):
    generator, doc, _, _ = skip_case(tmp_path)
    key, caller = executable(kind, returns)
    with pytest.raises(SC2Error, match='unsupported expression template'):
        generator.body(doc, key, caller)
    assert not getattr(generator, 'void_action_scope', False)


@pytest.mark.parametrize('kwargs', [{'template': 'return true;'}, {'shadow': True}])
def test_skip_remaining_rejects_unverified_template_or_library(tmp_path, kwargs):
    generator, doc, _, _ = skip_case(tmp_path, **kwargs)
    key, caller = executable()
    with pytest.raises(SC2Error, match='unsupported expression template'):
        generator.body(doc, key, caller)


def test_skip_remaining_scope_does_not_leak_to_another_body(tmp_path):
    generator, doc, _, _ = skip_case(tmp_path)
    key, caller = executable()
    assert generator.body(doc, key, caller) == 'return;'
    key, caller = executable(returns='bool')
    with pytest.raises(SC2Error, match='unsupported expression template'):
        generator.body(doc, key, caller)


def test_skip_remaining_is_not_an_expression_or_unscoped_statement(tmp_path):
    generator, doc, key, call = skip_case(tmp_path)
    for statement in (False, True):
        with pytest.raises(SC2Error, match='unsupported expression template'):
            generator.call(doc, key, call, statement)
