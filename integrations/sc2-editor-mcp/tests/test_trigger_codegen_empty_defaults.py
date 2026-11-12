from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator

PARAM_KEY = ('A431EF10', 'Param', 'DA1A000D')


def _expr(xml):
    gen = Generator(None)
    doc = SimpleNamespace(path=Path('Triggers'))
    return gen.expr(doc, PARAM_KEY, ET.fromstring(xml))


@pytest.mark.parametrize(
    'xml',
    [
        '<Parameter><ParameterDef Id="DA1A000D"/><ValueType Type="string"/></Parameter>',
        '<Parameter><ValueType Type="string"/></Parameter>',
        '<Parameter><ParameterDef Id="DA1A000D"/><ValueType Type="string"/><Comment>editor empty</Comment></Parameter>',
        '<Parameter><ParameterDef Id="DA1A000D"/><ValueType Type="gamelink"/><ValueGameType Type="Unit"/></Parameter>',
        '<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/></Parameter>',
        '<Parameter><ParameterDef Id="DA1A000D"/><ValueType Type="gamelink"/></Parameter>',
        '<Parameter><ValueType Type="gamelink"/></Parameter>',
        '<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/><Comment>empty unit link</Comment></Parameter>',
    ],
)
def test_editor_empty_literals(xml):
    assert _expr(xml) == '""'


def test_explicit_empty_value_matches_editor_metadata_only_shape():
    assert _expr('<Parameter><ValueType Type="string"/><Value/></Parameter>') == _expr(
        '<Parameter><ValueType Type="string"/></Parameter>'
    )
    assert _expr('<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/><Value/></Parameter>') == _expr(
        '<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/></Parameter>'
    )


@pytest.mark.parametrize(
    'xml',
    [
        '<Parameter><ParameterDef Id="DA1A000D"/><ValueGameType Type="Unit"/></Parameter>',
        '<Parameter><ParameterDef Id="DA1A000D"/></Parameter>',
        '<Parameter><ValueType Type="int"/></Parameter>',
        '<Parameter><ValueType Type="fixed"/></Parameter>',
        '<Parameter><ValueType Type="bool"/></Parameter>',
        '<Parameter><ValueType Type="unitfilter"/></Parameter>',
        '<Parameter><ValueType Type="anygamelink"/></Parameter>',
        '<Parameter><ValueType Type="string"/><Unknown/></Parameter>',
        '<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/><Unknown/></Parameter>',
        '<Parameter><ValueType Type="string"/><ValueType Type="string"/></Parameter>',
        '<Parameter><ValueType Type="string"/><ValueGameType Type="Unit"/></Parameter>',
        '<Parameter><ParameterDef Id="DA1A000D"/><ParameterDef Id="DA1A000D"/><ValueType Type="string"/></Parameter>',
        '<Parameter><ValueType Type="gamelink"/><ValueGameType Type="Unit"/><ValueGameType Type="Unit"/></Parameter>',
        '<Parameter><ValueType Type="string"/><Value/><Value/></Parameter>',
    ],
)
def test_unsupported_empty_literals_still_fail(xml):
    with pytest.raises(SC2Error):
        _expr(xml)


def test_text_without_value_keeps_string_external_anchor():
    assert _expr('<Parameter><ValueType Type="text"/></Parameter>') == (
        'StringExternal("Param/Value/lib_A431EF10_DA1A000D")'
    )
