"""A Preset registered in Root or a Category is non-executable declaration data.

Regression for the line-688 traversal: Preset must be allowed like Comment/Label so the
declaration is skipped. Proof that its value is still produced when referenced comes from
the existing integer-preset helper (PresetTree.value); an unsupported sibling shape must
still be rejected by that same strict rule.
"""
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from test_trigger_codegen_integer_presets import PresetTree

PRESET = ('SwaC', 'Preset', '15CE809C')
CATEGORY_ID = 'C26EC66D'


def _register(t, place):
    """Give the fake document a real Root and register PRESET in Root or a Category."""
    t.doc.standard = False            # not in {'Ntve'}, so generate() traverses it
    t.doc.root = E.Element('TriggerData')
    t.doc.component = Path('.')
    t.documents = [t.doc]
    t.graph = {'loading_order': []}
    root = E.SubElement(t.doc.root, 'Root')
    if place == 'category':
        ck = t.put('Category', ident=CATEGORY_ID)
        t.ref(root, 'Category', ck)
        t.ref(t.nodes[ck], 'Item', PRESET)
    else:
        t.ref(root, 'Preset', PRESET)


def _generate(t):
    # mapping() caches in self.bindings (there is no _mapping attribute) and only .used is
    # read at the final return; the fake target has no on-disk files, so seed that cache.
    t.generator.bindings = SimpleNamespace(used=[])
    result = t.generator.generate()   # unpatched: this is the traversal under test
    assert result['complete'] is True
    return t.generator


@pytest.mark.parametrize('place', ['root', 'category'])
def test_registered_preset_declaration_is_not_executable(place, monkeypatch):
    import sc2_triggers
    from sc2_mcp import trigger_writer
    monkeypatch.setattr(sc2_triggers, 'check', lambda target: {'errors': []})
    monkeypatch.setattr(trigger_writer, 'validate_editor_library_layout', lambda root: None)
    t = PresetTree()
    _register(t, place)
    before = list(t.generator.lines)
    gen = _generate(t)
    # Before the fix: SC2Error('unsupported declaration') here. After: skipped like Comment/Label.
    assert gen.lines == before


@pytest.mark.parametrize('i', [0, 1, 2])
def test_registered_preset_value_still_inlined(i):
    t = PresetTree()
    _register(t, 'root')
    assert t.value(i) == str(i)


def test_registered_preset_unsupported_value_still_rejected():
    t = PresetTree()
    _register(t, 'root')
    E.SubElement(t.nodes[('SwaC', 'PresetValue', t.group.findall('Item')[0].get('Id'))], 'ScriptCode').text = 'bad();'
    with pytest.raises((SC2Error, KeyError)):
        t.value(0)
