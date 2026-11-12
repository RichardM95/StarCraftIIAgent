from types import SimpleNamespace
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree


def setup_array(*, maximum='10', dimension='0', kind='gamelink', default=None):
    t = Tree()
    t.generator.bindings = SimpleNamespace(type=lambda n, d, k, tag: {'gamelink': 'string'}.get(n.find(tag + '/Type').get('Value'), n.find(tag + '/Type').get('Value')))
    key = t.put('Variable')
    n = t.nodes[key]
    E.SubElement(n, 'Identifier').text = 'Items'
    ty = E.SubElement(n, 'VariableType')
    E.SubElement(ty, 'Type', Value=kind)
    if kind == 'gamelink':
        E.SubElement(ty, 'GameType', Value='Unit')
    E.SubElement(ty, 'ArraySize', Dim=dimension, Value=maximum)
    if default is not None:
        preset = t.put('PresetValue', 'Ntve')
        E.SubElement(t.nodes[preset], 'Value').text = '"' + default + '"'
        param = t.put('Param')
        t.ref(t.nodes[param], 'Preset', preset)
        t.ref(n, 'Value', param)
    return t, key, n


def index_expression(t, variable, value=None, dynamic=None):
    index = t.put('Param')
    if dynamic is None:
        E.SubElement(t.nodes[index], 'ValueType', Type='int')
        E.SubElement(t.nodes[index], 'Value').text = value
    else:
        t.ref(t.nodes[index], 'Variable', dynamic)
    key = t.put('Param')
    t.ref(t.nodes[key], 'Variable', variable)
    t.ref(t.nodes[key], 'Array', index)
    return key


def evaluate(t, key):
    return t.generator.expr(t.doc, key, t.nodes[key])


@pytest.mark.parametrize('maximum,length', [('0', 1), ('10', 11)])
def test_editor_maximum_index_declares_maximum_plus_one_slots(maximum, length):
    t, key, n = setup_array(maximum=maximum)
    assert t.generator.typ(n, t.doc, key, 'VariableType') == f'string[{length}]'


def test_empty_default_is_not_an_illegal_whole_array_assignment():
    t, key, _ = setup_array(default='')
    fn = t.put('FunctionDef')
    t.ref(t.nodes[fn], 'Variable', key)
    assert t.generator.body(t.doc, fn, t.nodes[fn]) == 'string[11] gv_Items;'


def test_nonempty_default_is_rejected_without_silently_discarding_it():
    t, key, _ = setup_array(default='Hive')
    fn = t.put('FunctionDef')
    t.ref(t.nodes[fn], 'Variable', key)
    with pytest.raises(SC2Error):
        t.generator.body(t.doc, fn, t.nodes[fn])


def test_actual_official_none_preset_is_natural_array_default():
    t, key, _ = setup_array(default='')
    preset = next(n for k, n in t.nodes.items() if k[1] == 'PresetValue')
    preset.find('Value').text = 'null'
    fn = t.put('FunctionDef')
    t.ref(t.nodes[fn], 'Variable', key)
    assert t.generator.body(t.doc, fn, t.nodes[fn]) == 'string[11] gv_Items;'


def test_nonvariable_literal_cannot_silently_drop_array_metadata():
    t, key, _ = setup_array()
    p = index_expression(t, key, '0')
    t.nodes[p].remove(t.nodes[p].find('Variable'))
    E.SubElement(t.nodes[p], 'ValueType', Type='int')
    E.SubElement(t.nodes[p], 'Value').text = '0'
    with pytest.raises(SC2Error):
        evaluate(t, p)


def test_global_arrays_remain_explicitly_unsupported(tmp_path):
    from sc2_mcp.trigger_codegen import Generator
    from sc2_mcp.trigger_pipeline import target_for
    from test_trigger_pipeline import gui_target

    root, mods = gui_target(tmp_path)
    p = root / 'Triggers'
    tree = E.parse(p)
    E.SubElement(tree.getroot().find('Root'), 'Item', Type='Variable', Id='CA45A001')
    node = E.SubElement(tree.getroot(), 'Element', Type='Variable', Id='CA45A001')
    E.SubElement(node, 'Identifier').text = 'UnsupportedGlobalArray'
    ty = E.SubElement(node, 'VariableType')
    E.SubElement(ty, 'Type', Value='gamelink')
    E.SubElement(ty, 'GameType', Value='Unit')
    E.SubElement(ty, 'ArraySize', Dim='0', Value='10')
    tree.write(p, encoding='utf-8')
    with pytest.raises(SC2Error, match='global arrays unsupported'):
        Generator(target_for(root, str(mods))).generate()


@pytest.mark.parametrize('value', ['0', '4', '10'])
def test_literal_index_preserves_zero_based_read_and_write_expression(value):
    t, key, _ = setup_array()
    assert evaluate(t, index_expression(t, key, value)) == f'gv_Items[{value}]'


def test_int_variable_can_index_array_without_clamping_or_offset():
    t, key, _ = setup_array()
    i = t.put('Variable')
    E.SubElement(t.nodes[i], 'Identifier').text = 'Index'
    E.SubElement(E.SubElement(t.nodes[i], 'VariableType'), 'Type', Value='int')
    assert evaluate(t, index_expression(t, key, dynamic=i)) == 'gv_Items[gv_Index]'


@pytest.mark.parametrize('value', ['-1', '11', '1.5', 'wrong'])
def test_invalid_or_out_of_range_constant_index_is_rejected(value):
    t, key, _ = setup_array()
    with pytest.raises(SC2Error):
        evaluate(t, index_expression(t, key, value))


@pytest.mark.parametrize('kwargs', [{'maximum': '-1'}, {'maximum': '8192'}, {'maximum': '1.5'}, {'dimension': '1'}, {'kind': 'int'}])
def test_unverified_array_declarations_still_fail(kwargs):
    t, key, n = setup_array(**kwargs)
    with pytest.raises(SC2Error):
        t.generator.typ(n, t.doc, key, 'VariableType')


@pytest.mark.parametrize('corruption', ['duplicate', 'unknown', 'scalar', 'bare-array', 'bad-index-type'])
def test_array_metadata_cannot_be_silently_dropped(corruption):
    t, key, n = setup_array()
    p = index_expression(t, key, '0')
    if corruption == 'duplicate':
        t.nodes[p].append(E.fromstring(E.tostring(t.nodes[p].find('Array'))))
    elif corruption == 'unknown':
        E.SubElement(t.nodes[p], 'Unknown')
    elif corruption == 'scalar':
        n.find('VariableType').remove(n.find('VariableType/ArraySize'))
    elif corruption == 'bare-array':
        t.nodes[p].remove(t.nodes[p].find('Array'))
    else:
        index_ref = t.nodes[p].find('Array')
        index = t.nodes[(index_ref.get('Library'), 'Param', index_ref.get('Id'))]
        index.find('ValueType').set('Type', 'fixed')
    with pytest.raises(SC2Error):
        evaluate(t, p)
