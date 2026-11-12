"""Catalog indices preserve Editor expression order and reject incomplete references."""
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
from sc2_mcp.trigger_codegen import Generator
from sc2_mcp.errors import SC2Error


def generator():
    document=SimpleNamespace(path='map/Triggers')
    elements={
        ('', 'Param', 'A'):ET.fromstring('<Element><Value>0</Value><ValueType Type="int"/></Element>'),
        ('', 'Param', 'B'):ET.fromstring('<Element><Value>1</Value><ValueType Type="int"/></Element>'),
    }
    def resolve(key, doc):
        if key not in elements:
            raise SC2Error('trigger_reference_missing','missing reference',node=list(key))
        return document,elements[key]
    bindings=SimpleNamespace(aliases={'catalogentry':'string','catalogfieldpath':'string'})
    return Generator(SimpleNamespace(resolve=resolve),bindings=bindings),document


def field(refs):
    return ET.fromstring('<Element Type="Param" Id="P"><Value>Cost[0].Vital[1]</Value>'
        '<ValueType Type="catalogfieldpath"/><ValueContext Value="CAbilEffectTarget"/>'
        + ''.join('<ValueParam Type="Param" Id="'+r+'"/>' for r in refs)+'</Element>')


def test_catalog_entry_uses_proven_string_alias():
    gen,doc=generator()
    node=ET.fromstring('<Element><Value>ExampleAbility</Value><ValueType Type="catalogentry"/></Element>')
    assert gen.expr(doc,('', 'Param','P'),node)=='"ExampleAbility"'
    gen.bindings.aliases['catalogentry']='int'
    with pytest.raises(SC2Error):gen.expr(doc,('', 'Param','P'),node)


def test_two_indices_match_native_string_construction():
    gen,doc=generator()
    assert gen.expr(doc,('', 'Param','P'),field(['A','B']))=='"Cost[" + IntToString(0) + "].Vital[" + IntToString(1) + "]"'


@pytest.mark.parametrize('refs',[['A'],['A','B','A'],['A','missing']])
def test_incomplete_indices_fail(refs):
    gen,doc=generator()
    with pytest.raises(SC2Error):gen.expr(doc,('', 'Param','P'),field(refs))
