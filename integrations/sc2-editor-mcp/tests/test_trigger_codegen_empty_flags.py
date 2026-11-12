from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.storage import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def flags_case(tmp_path, *, as_bits=True, base='int', extra=False):
    root, mods = gui_target(tmp_path)
    native = mods / 'Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'
    tree = ET.parse(native)
    preset = ET.SubElement(tree.getroot(), 'Element', {'Type':'Preset','Id':'E85564CA'})
    ET.SubElement(preset, 'Identifier').text = 'Unit_Create_Style2'
    ET.SubElement(preset, 'BaseType', {'Value':base})
    if as_bits:
        ET.SubElement(preset, 'PresetAsBits')
    tree.write(native, encoding='utf-8')
    target = target_for(root, str(mods))
    doc = next(d for d in target.documents if not d.standard)
    # Exact empty creation-flags shape in NativeLib.TriggerLib, Param 02AE1E39.
    param = ET.fromstring('''<Element><ValueType Type="preset"/>
      <ValueElement Type="Preset" Library="Ntve" Id="E85564CA"/></Element>''')
    if extra:
        ET.SubElement(param, 'FutureSelectedFlags')
    return Generator(target), doc, ('','Param','CA180001'), param


def test_empty_bit_flags_generate_zero(tmp_path):
    gen, doc, key, param = flags_case(tmp_path)
    assert gen.expr(doc, key, param) == '0'


@pytest.mark.parametrize('kwargs', [
    {'as_bits':False}, {'base':'string'}, {'extra':True},
])
def test_empty_flags_do_not_coerce_other_presets_or_unknown_fields(tmp_path, kwargs):
    gen, doc, key, param = flags_case(tmp_path, **kwargs)
    with pytest.raises(SC2Error):
        gen.expr(doc, key, param)
