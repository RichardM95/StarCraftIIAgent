from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.storage import SC2Error
from sc2_mcp.trigger_pipeline import native_supplement


def official_target(name, parameters, *, native=True, library='Ntve'):
    elements = {}
    definition = ET.Element('Element', Type='FunctionDef', Id='F0000000')
    ET.SubElement(definition, 'Identifier').text = name
    if native:
        ET.SubElement(definition, 'FlagNative')
    elements[(library, 'FunctionDef', 'F0000000')] = definition
    for i, kind in enumerate(parameters):
        ident = f'F100000{i}'
        param = ET.Element('Element', Type='ParamDef', Id=ident)
        container = ET.SubElement(param, 'ParameterType')
        if isinstance(kind, tuple):
            ET.SubElement(container, 'Type', Value='preset')
            preset_id = f'F200000{i}'
            ET.SubElement(container, 'TypeElement', Type='Preset', Library=library, Id=preset_id)
            preset = ET.Element('Element', Type='Preset', Id=preset_id)
            if kind[0] is not None:
                ET.SubElement(preset, 'BaseType', Value=kind[0])
            elements[(library, 'Preset', preset_id)] = preset
        else:
            ET.SubElement(container, 'Type', Value=kind)
        elements[(library, 'ParamDef', ident)] = param
        ET.SubElement(definition, 'Parameter', Type='ParamDef', Library=library, Id=ident)
    document = SimpleNamespace(standard=library, elements=elements, path=Path('NativeLib.TriggerLib'), sha256='fixture-sha')
    return SimpleNamespace(documents=[document], resolve=lambda key, doc: (document, elements[key]))


@pytest.mark.parametrize('name,parameters,expected', [
    ('CutsceneShow', [('int',), ('bool',)], 'native void CutsceneShow(int p0, bool p1);'),
    ('CutsceneFade', [('bool',), 'fixed', 'color', 'fixed', 'playergroup', ('bool',)],
     'native void CutsceneFade(bool p0, fixed p1, color p2, fixed p3, playergroup p4, bool p5);'),
])
def test_cutscene_signatures_resolve_official_preset_base_types(name, parameters, expected):
    source, evidence = native_supplement(official_target(name, parameters), {})
    assert source.strip() == expected
    assert len(evidence) == 1
    assert evidence[0]['sha256'] == 'fixture-sha'
    assert evidence[0]['scope'] == 'GUI-derived static typing only; engine ABI unverified'


def test_existing_cutscene_declaration_is_not_redeclared():
    source, evidence = native_supplement(official_target('CutsceneShow', [('int',), ('bool',)]),
                                         {'natives.galaxy': 'native void CutsceneShow(int id, bool show);'})
    assert not source.strip() and evidence == []


def test_return_call_is_not_a_cutscene_declaration():
    source, evidence = native_supplement(official_target('CutsceneShow', [('int',), ('bool',)]),
                                         {'lib.galaxy': 'void F() {\nreturn CutsceneShow(2, true);\n}'})
    assert 'native void CutsceneShow(int p0, bool p1);' in source and len(evidence) == 1


def test_non_native_cutscene_definition_is_rejected():
    with pytest.raises(SC2Error, match='not native'):
        native_supplement(official_target('CutsceneShow', [('int',), ('bool',)], native=False), {})


@pytest.mark.parametrize('parameters', [[(None,)], ['unknown_type']])
def test_unknown_cutscene_type_is_not_guessed(parameters):
    with pytest.raises(SC2Error):
        native_supplement(official_target('CutsceneShow', parameters), {})


@pytest.mark.parametrize('name,library', [('InjectedNative', 'Ntve'), ('CutsceneShow', 'User')])
def test_cutscene_supplement_stays_whitelisted_and_official(name, library):
    source, evidence = native_supplement(official_target(name, [('int',)], library=library), {})
    assert not source.strip() and evidence == []
