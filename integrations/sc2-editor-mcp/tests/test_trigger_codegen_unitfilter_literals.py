import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator


class Bindings:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def bind(self, name, returns, types, values, statement, doc, key, definition):
        self.calls.append((name, returns, types, values, statement))
        if not self.available:
            raise SC2Error('native_binding_missing', 'no verified UnitFilterStr declaration')
        assert name == 'UnitFilterStr' and returns == 'unitfilter'
        assert types == ['string'] and not statement
        return 'UnitFilterStr(' + values[0] + ')'


def evaluate(value, bindings):
    p = E.Element('Element', Type='Param')
    E.SubElement(p, 'ValueType', Type='unitfilter')
    E.SubElement(p, 'Value').text = value
    return Generator(None, bindings=bindings).expr(SimpleNamespace(path=Path('Triggers')), ('A431EF10', 'Param', 'D9F2000E'), p)


@pytest.mark.parametrize('value', ['-;Missile,Dead', '-;Missile,UnderConstruction,Dead'])
def test_proven_filters_use_checked_native_binding(value):
    b = Bindings()
    assert evaluate(value, b) == 'UnitFilterStr("' + value + '")'
    assert len(b.calls) == 1


@pytest.mark.parametrize('value', ['', 'Missile', '-;Unknown,Dead', '-;Missile,Dead"; arbitrary();'])
def test_filter_strings_remain_data_for_native_converter(value):
    b = Bindings()
    assert evaluate(value, b) == 'UnitFilterStr(' + json.dumps(value) + ')'
    assert len(b.calls) == 1
    assert json.loads(b.calls[0][3][0]) == value


def test_missing_native_declaration_cannot_fall_back_to_unchecked_call():
    with pytest.raises(SC2Error, match='no verified'):
        evaluate('-;Missile,Dead', Bindings(available=False))
