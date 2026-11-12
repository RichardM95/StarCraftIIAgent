"""Global fixed constants retain exact literals without becoming array bounds."""
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def fixed_target(tmp_path, literal='400.0', mutate=None):
    root, mods = gui_target(tmp_path)
    tree = E.parse(root/'Triggers')
    lib = E.Element('Library', Id='A431EF10')
    tree.getroot().insert(0, lib)
    registry = E.SubElement(lib, 'Root')
    node = E.SubElement(lib, 'Element', Type='Variable', Id='908C0343')
    E.SubElement(node, 'Identifier').text = 'TalentButtonDistance'
    vt = E.SubElement(node, 'VariableType')
    E.SubElement(vt, 'Type', Value='fixed')
    E.SubElement(vt, 'Constant')
    E.SubElement(node, 'Value', Type='Param', Library='A431EF10', Id='957F9A23')
    value = E.SubElement(lib, 'Element', Type='Param', Id='957F9A23')
    E.SubElement(value, 'Value').text = literal
    E.SubElement(value, 'ValueType', Type='fixed')
    E.SubElement(registry, 'Item', Type='Variable', Library='A431EF10', Id='908C0343')
    if mutate:
        mutate(lib, node, value)
    tree.write(root/'Triggers', encoding='utf-8')
    return target_for(root, str(mods))


@pytest.mark.parametrize('literal', ['400.0', '-12.5', '0.0', '0', '17', '-0.0625'])
def test_fixed_constant_is_declared_once_and_not_runtime_initialized(tmp_path, literal):
    gen = Generator(fixed_target(tmp_path, literal))
    result = gen.generate()
    source = result['source']
    declaration = f'const fixed libA431EF10_gv_TalentButtonDistance = {literal};'
    assert source.count(declaration) == 1
    assert 'gv_TalentButtonDistance =' not in source.replace(declaration, '')
    assert source.index(declaration) < source.index('void InitMap()')
    assert gen.global_constants == {}
    assert all(1 <= row['start'] <= row['end'] <= len(source.splitlines()) for row in result['source_map'])


@pytest.mark.parametrize('literal', ['4e2', 'NaN', 'inf', 'Infinity', '.5', '5.', '+5', ' 400.0', '400.0 ', '1/2'])
def test_non_decimal_fixed_constant_is_rejected(tmp_path, literal):
    with pytest.raises(SC2Error):
        Generator(fixed_target(tmp_path, literal)).generate()


@pytest.mark.parametrize('case', ['type-mismatch', 'duplicate-literal', 'duplicate-type', 'constant-attribute', 'array', 'dynamic'])
def test_unsupported_constant_shapes_stay_rejected(tmp_path, case):
    def mutate(lib, node, value):
        if case == 'type-mismatch':
            value.find('ValueType').set('Type', 'int')
        elif case == 'duplicate-literal':
            E.SubElement(value, 'Value').text = '1.0'
        elif case == 'duplicate-type':
            E.SubElement(value, 'ValueType', Type='fixed')
        elif case == 'constant-attribute':
            node.find('VariableType/Constant').set('Id', 'bad')
        elif case == 'array':
            E.SubElement(node.find('VariableType'), 'ArraySize', Dim='0', Value='5')
        elif case == 'dynamic':
            value.remove(value.find('Value'))
            E.SubElement(value, 'Variable', Type='Variable', Library='A431EF10', Id='908C0343')
    with pytest.raises(SC2Error):
        Generator(fixed_target(tmp_path, mutate=mutate)).generate()


def test_fixed_constant_cannot_supply_integer_array_dimension(tmp_path):
    def mutate(lib, node, value):
        array = E.SubElement(lib, 'Element', Type='Variable', Id='E1360001')
        E.SubElement(array, 'Identifier').text = 'Boundary'
        vt = E.SubElement(array, 'VariableType')
        E.SubElement(vt, 'Type', Value='int')
        E.SubElement(vt, 'ArraySize', Dim='0', Type='Variable', Library='A431EF10', Id='908C0343')
        E.SubElement(lib.find('Root'), 'Item', Type='Variable', Library='A431EF10', Id='E1360001')
    with pytest.raises(SC2Error, match='registered global constant int'):
        Generator(fixed_target(tmp_path, mutate=mutate)).generate()
