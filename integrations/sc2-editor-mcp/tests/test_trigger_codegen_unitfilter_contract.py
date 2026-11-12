import json
from xml.etree import ElementTree as E

import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree


class Mapping:
    def __init__(self, reject=False):
        self.calls = []
        self.reject = reject

    def bind(self, name, result, types, values, statement, doc, key, binding):
        self.calls.append((name, result, types, values, statement, key, binding))
        if self.reject:
            raise SC2Error('test_binding_rejected', 'native ABI not verified')
        assert (name, result, types, statement) == ('UnitFilterStr', 'unitfilter', ['string'], False)
        return name + '(' + values[0] + ')'


def expression(value, kind='unitfilter', reject=False, ambiguous=False):
    tree = Tree()
    tree.generator.bindings = mapping = Mapping(reject)
    key = tree.put('Param')
    param = tree.nodes[key]
    E.SubElement(param, 'ValueType', Type=kind)
    E.SubElement(param, 'Value').text = value
    if ambiguous:
        E.SubElement(param, 'Value').text = 'second'
    return tree, mapping, key, param


@pytest.mark.parametrize('value', [
    '-;Missile,Dead', '-;Missile,UnderConstruction,Dead',
    '-;Missile,Dead,Hidden,Summoned', '',
    'Enemy;Air,Ground', 'unrecognized_runtime_token',
    '\"); UnitKill(1); //', 'line\nwith\tcontrol\\characters', '敌方',
])
def test_literal_uses_native_string_converter_and_escapes_data(value):
    tree, mapping, key, param = expression(value)
    code = tree.generator.expr(tree.doc, key, param)
    assert code == 'UnitFilterStr(' + json.dumps(value, ensure_ascii=True) + ')'
    assert len(mapping.calls) == 1
    assert json.loads(mapping.calls[0][3][0]) == value
    assert mapping.calls[0][-2:] == (key, key)


@pytest.mark.parametrize('kind', ['int', 'bool', 'fixed', 'unregistered'])
def test_other_typed_literals_do_not_become_filters(kind):
    tree, mapping, key, param = expression('-;Missile,Dead,Hidden,Summoned', kind)
    with pytest.raises(SC2Error):
        tree.generator.expr(tree.doc, key, param)
    assert not mapping.calls


def test_ambiguous_literal_is_rejected_before_binding():
    tree, mapping, key, param = expression('-;Missile,Dead', ambiguous=True)
    with pytest.raises(SC2Error):
        tree.generator.expr(tree.doc, key, param)
    assert not mapping.calls


def test_unverified_native_mapping_still_fails():
    tree, mapping, key, param = expression('-;Missile,Dead,Hidden,Summoned', reject=True)
    with pytest.raises(SC2Error) as caught:
        tree.generator.expr(tree.doc, key, param)
    assert caught.value.code == 'test_binding_rejected'
