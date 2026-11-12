"""Global int Constants accept plain signed 32-bit literals; only 0..8191 supply array bounds.

Variable A431EF10/1C71FE0D with Param A431EF10/889554C7 is the plain int -1 Constant that the full
Kerrigan Main could not generate. A valid constant declaration and the bounded array registry are
different facts: every int Constant becomes `const int ... = literal;`, but only the 0..8191 subset
is a candidate array dimension. Static generator checks only, not Editor/game acceptance.
"""
import xml.etree.ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.trigger_pipeline import target_for
from test_trigger_pipeline import gui_target


def int_target(tmp_path, literal='-1', mutate=None):
    """Minimal GUI target with one global int Constant plus one literals scalar reference."""
    root, mods = gui_target(tmp_path)
    tree = E.parse(root/'Triggers')
    lib = E.Element('Library', Id='A431EF10')
    tree.getroot().insert(0, lib)
    registry = E.SubElement(lib, 'Root')
    node = E.SubElement(lib, 'Element', Type='Variable', Id='1C71FE0D')
    E.SubElement(node, 'Identifier').text = 'NegativeOffset'
    vt = E.SubElement(node, 'VariableType')
    E.SubElement(vt, 'Type', Value='int')
    E.SubElement(vt, 'Constant')
    E.SubElement(node, 'Value', Type='Param', Library='A431EF10', Id='889554C7')
    value = E.SubElement(lib, 'Element', Type='Param', Id='889554C7')
    E.SubElement(value, 'Value').text = literal
    E.SubElement(value, 'ValueType', Type='int')
    E.SubElement(registry, 'Item', Type='Variable', Library='A431EF10', Id='1C71FE0D')
    if mutate:
        mutate(lib, node, value)
    tree.write(root/'Triggers', encoding='utf-8')
    return target_for(root, str(mods))


def add_array(lib, bound_id):
    """Declare an int array whose bound references the int Constant bound_id."""
    array = E.SubElement(lib, 'Element', Type='Variable', Id='E1360001')
    E.SubElement(array, 'Identifier').text = 'Boundaries'
    vt = E.SubElement(array, 'VariableType')
    E.SubElement(vt, 'Type', Value='int')
    E.SubElement(vt, 'ArraySize', Dim='0', Type='Variable', Library='A431EF10', Id=bound_id)
    E.SubElement(lib.find('Root'), 'Item', Type='Variable', Library='A431EF10', Id='E1360001')


def test_actual_kerrigan_minus_one_constant_declares_once_and_never_initializes(tmp_path):
    gen = Generator(int_target(tmp_path))
    result = gen.generate()
    source = result['source']
    declaration = 'const int libA431EF10_gv_NegativeOffset = -1;'
    assert source.count(declaration) == 1
    assert 'libA431EF10_gv_NegativeOffset =' not in source.replace(declaration, '')
    assert source.index(declaration) < source.index('void InitMap()')
    assert 'libA431EF10_gv_NegativeOffset' not in source[source.index('void InitMap()'):]
    # Declaration is valid, but a negative literal is not array-eligible.
    assert gen.global_constants == {}
    assert all(1 <= row['start'] <= row['end'] <= len(source.splitlines()) for row in result['source_map'])


@pytest.mark.parametrize('literal', ['-2147483648', '-1', '0', '8191', '8192', '2147483647'])
def test_signed_int_constant_boundaries_declare_and_register_eligibility(tmp_path, literal):
    gen = Generator(int_target(tmp_path, literal))
    source = gen.generate()['source']
    declaration = f'const int libA431EF10_gv_NegativeOffset = {literal};'
    assert source.count(declaration) == 1
    assert source.index(declaration) < source.index('void InitMap()')
    assert 'libA431EF10_gv_NegativeOffset =' not in source.replace(declaration, '')
    number = int(literal)
    registered = [value for value in gen.global_constants.values()]
    assert registered == ([number] if 0 <= number <= 8191 else [])


@pytest.mark.parametrize('literal', ['-2147483649', '2147483648', '99999999999', '--1', '+-1', '- 1',
                                     ' 1', '1 ', '1\n', '+1', '-1.0', '1.5', '1e3', '-1e3',
                                     '-0x10', '1+2', '-1+2', '', '-', 'abc'])
def test_signed_int_constant_invalid_spelling_or_range_is_rejected(tmp_path, literal):
    with pytest.raises(SC2Error):
        Generator(int_target(tmp_path, literal)).generate()


@pytest.mark.parametrize('bound_id,literal', [('1C71FE0D', '-1'), ('1C71FE0D', '8192')])
def test_referenced_int_constant_outside_array_bounds_stays_rejected(tmp_path, bound_id, literal):
    def mutate(lib, node, value):
        add_array(lib, bound_id)
    with pytest.raises(SC2Error, match='registered global constant int'):
        Generator(int_target(tmp_path, literal, mutate=mutate)).generate()


@pytest.mark.parametrize('literal,expected', [('0', 'int[1] libA431EF10_gv_Boundaries;'),
                                              ('8191', 'int[8192] libA431EF10_gv_Boundaries;')])
def test_referenced_array_eligible_int_constant_still_supplies_dimension(tmp_path, literal, expected):
    def mutate(lib, node, value):
        add_array(lib, '1C71FE0D')
    source = Generator(int_target(tmp_path, literal, mutate=mutate)).generate()['source']
    assert source.count(expected) == 1
    assert source.count(f'const int libA431EF10_gv_NegativeOffset = {literal};') == 1
    assert 'libA431EF10_gv_Boundaries = ' not in source


@pytest.mark.parametrize('case', ['type-mismatch', 'constant-attribute', 'array', 'dynamic'])
def test_signed_int_constant_keeps_existing_shape_validation(tmp_path, case):
    def mutate(lib, node, value):
        if case == 'type-mismatch':
            value.find('ValueType').set('Type', 'fixed')
        elif case == 'constant-attribute':
            node.find('VariableType/Constant').set('Id', 'bad')
        elif case == 'array':
            E.SubElement(node.find('VariableType'), 'ArraySize', Dim='0', Value='5')
        elif case == 'dynamic':
            value.remove(value.find('Value'))
            E.SubElement(value, 'Variable', Type='Variable', Library='A431EF10', Id='1C71FE0D')
    with pytest.raises(SC2Error):
        Generator(int_target(tmp_path, mutate=mutate)).generate()
