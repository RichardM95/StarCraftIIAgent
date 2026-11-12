from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_codegen import Generator


class Tree:
    def __init__(self):
        self.nodes = {}
        self.serial = 0
        self.doc = SimpleNamespace(path=Path('Triggers'), elements=self.nodes, standard=False)
        self.generator = Generator(self)
        self.stop = self.definition('StopLooping', ident='7B4A4D9D')
        E.SubElement(self.nodes[self.stop], 'FlagOperator')
        E.SubElement(self.nodes[self.stop], 'ScriptCode').text = '#SMARTBREAK'
        self.repeat = self.definition('RepeatForever', ['actions'])
        self.while_ = self.definition('While', ['Conditions', 'Actions'])
        self.if_ = self.definition('IfThenElse', ['if', 'then', 'else'])

    def put(self, kind, library='', ident=None):
        self.serial += 1
        key = (library, kind, ident or f'CA44{self.serial:04X}')
        self.nodes[key] = E.Element('Element', Type=kind, Id=key[2])
        return key

    def ref(self, parent, tag, key):
        return E.SubElement(parent, tag, Type=key[1], Library=key[0], Id=key[2])

    def definition(self, name, roles=(), ident=None, library='Ntve'):
        key = self.put('FunctionDef', library, ident)
        n = self.nodes[key]
        E.SubElement(n, 'Identifier').text = name
        E.SubElement(n, 'FlagAction')
        if roles:
            E.SubElement(n, 'FlagSubFunctions')
        for role in roles:
            sub = self.put('SubFuncType', library)
            E.SubElement(self.nodes[sub], 'Identifier').text = role
            self.ref(n, 'SubFunctionType', sub)
        return key

    def resolve(self, key, doc):
        return self.doc, self.nodes[key]

    def call(self, definition, groups=None):
        key = self.put('FunctionCall')
        n = self.nodes[key]
        self.ref(n, 'FunctionDef', definition)
        for ref in self.nodes[definition].findall('SubFunctionType'):
            sub = (ref.get('Library'), ref.get('Type'), ref.get('Id'))
            role = self.nodes[sub].findtext('Identifier')
            for child in (groups or {}).get(role, []):
                self.ref(self.nodes[child], 'SubFunctionType', sub)
                self.ref(n, 'FunctionCall', child)
        return key

    def body(self, call):
        key = self.put('FunctionDef')
        n = self.nodes[key]
        self.ref(n, 'FunctionCall', call)
        return self.generator.body(self.doc, key, n)


def test_break_inside_repeat_if_retains_correct_structure():
    t = Tree()
    stop = t.call(t.stop)
    branch = t.call(t.if_, {'then': [stop]})
    loop = t.call(t.repeat, {'actions': [branch]})
    assert t.body(loop) == 'while (true) {\nif (true) {\nbreak;\n} else {\n\n}\n}'
    assert getattr(t.generator, 'loop_depth', 0) == 0


def test_nested_while_repeat_breaks_only_inner_loop():
    t = Tree()
    inner = t.call(t.repeat, {'actions': [t.call(t.stop)]})
    outer = t.call(t.while_, {'Actions': [inner]})
    assert t.body(outer) == 'while (true) {\nwhile (true) {\nbreak;\n}\n}'


@pytest.mark.parametrize('statement', [False, True])
def test_unscoped_break_is_rejected(statement):
    t = Tree()
    key = t.call(t.stop)
    with pytest.raises(SC2Error):
        t.generator.call(t.doc, key, t.nodes[key], statement)


def test_break_in_while_condition_is_rejected_and_scope_recovers():
    t = Tree()
    loop = t.call(t.while_, {'Conditions': [t.call(t.stop)]})
    with pytest.raises(SC2Error):
        t.body(loop)
    assert getattr(t.generator, 'loop_depth', 0) == 0
    assert t.body(t.call(t.repeat, {'actions': [t.call(t.stop)]})) == 'while (true) {\nbreak;\n}'


@pytest.mark.parametrize('corruption', ['template', 'library', 'return'])
def test_break_rejects_unverified_definition(corruption):
    t = Tree()
    definition = t.stop
    if corruption == 'template':
        t.nodes[definition].find('ScriptCode').text = 'arbitrary;'
    elif corruption == 'library':
        definition = t.definition('StopLooping', library='Other', ident='7B4A4D9D')
        E.SubElement(t.nodes[definition], 'FlagOperator')
        E.SubElement(t.nodes[definition], 'ScriptCode').text = '#SMARTBREAK'
    else:
        E.SubElement(E.SubElement(t.nodes[definition], 'ReturnType'), 'Type', Value='int')
    loop = t.call(t.repeat, {'actions': [t.call(definition)]})
    with pytest.raises(SC2Error):
        t.body(loop)
    assert getattr(t.generator, 'loop_depth', 0) == 0


def test_exception_inside_action_cleans_depth_and_next_body_is_unscoped():
    t = Tree()
    t.nodes[t.stop].find('ScriptCode').text = 'wrong;'
    with pytest.raises(SC2Error):
        t.body(t.call(t.repeat, {'actions': [t.call(t.stop)]}))
    assert getattr(t.generator, 'loop_depth', 0) == 0
    t.nodes[t.stop].find('ScriptCode').text = '#SMARTBREAK'
    with pytest.raises(SC2Error):
        t.body(t.call(t.stop))


def test_new_function_body_does_not_inherit_surrounding_loop():
    t = Tree()
    t.generator.loop_depth = 1
    with pytest.raises(SC2Error):
        t.body(t.call(t.stop))
    assert t.generator.loop_depth == 1
