import re
from xml.etree import ElementTree as E

import pytest

from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree


TEMPLATE = '#INITAUTOVAR(ae,e)#INITAUTOVAR(ai,increment)#PARAM(var)=#PARAM(s);for(;((#AUTOVAR(ai)>=0&&#PARAM(var)<=#AUTOVAR(ae))||(#AUTOVAR(ai)<0&&#PARAM(var)>=#AUTOVAR(ae)));#PARAM(var)+=#AUTOVAR(ai)){#SUBFUNCS(actions)}'


def loop_tree(start='0', end='4', step='1', *, breaking=False, library='Ntve'):
    t = Tree()
    definition = t.definition('ForEachInteger', ['actions'], ident='66474248', library=library)
    f = t.nodes[definition]
    E.SubElement(f, 'FlagAllowBreak')
    E.SubElement(f, 'ScriptCode').text = TEMPLATE
    slots = []
    for ident, name in [('8CB41668', 'var'), ('F13E2CDE', 's'), ('C25E6187', 'e'), ('F3144A4A', 'increment')]:
        slot = t.put('ParamDef', library, ident)
        E.SubElement(t.nodes[slot], 'Identifier').text = name
        E.SubElement(E.SubElement(t.nodes[slot], 'ParameterType'), 'Type', Value='int' if name != 'var' else 'anyvariable')
        t.ref(f, 'Parameter', slot)
        slots.append(slot)
    index = t.put('Variable')
    E.SubElement(t.nodes[index], 'Identifier').text = 'Index'
    E.SubElement(E.SubElement(t.nodes[index], 'VariableType'), 'Type', Value='int')
    body = [t.call(t.stop)] if breaking else []
    key = t.call(definition, {'actions': body})
    for slot, value in zip(slots, [None, start, end, step]):
        param = t.put('Param')
        n = t.nodes[param]
        t.ref(n, 'ParameterDef', slot)
        if value is None:
            t.ref(n, 'Variable', index)
        else:
            E.SubElement(n, 'ValueType', Type='int')
            E.SubElement(n, 'Value').text = value
        t.ref(t.nodes[key], 'Parameter', param)
    return t, key, f


@pytest.mark.parametrize('start,end,step,expected', [('0','4','1',[0,1,2,3,4]), ('4','0','-1',[4,3,2,1,0]), ('4','0','1',[]), ('0','4','-1',[])])
def test_inclusive_constant_loop_semantics(start, end, step, expected):
    t, key, _ = loop_tree(start, end, step)
    generated = t.body(key)
    assert re.search(r'gv_Index\s*=\s*' + re.escape(start) + r';', generated)
    op = '<=' if int(step) > 0 else '>='
    assert re.search(r'while\s*\(gv_Index\s*' + op + r'\s*' + re.escape(end) + r'\)', generated)
    assert re.search(r'gv_Index\s*=\s*gv_Index\s*\+\s*\(' + re.escape(step) + r'\);', generated)
    trace = []
    value = int(start)
    while (value <= int(end) if op == '<=' else value >= int(end)):
        trace.append(value)
        value += int(step)
        assert len(trace) < 100
    assert trace == expected


def test_break_is_inside_loop_before_increment_and_scope_does_not_leak():
    t, key, _ = loop_tree(breaking=True)
    generated = t.body(key)
    assert generated.index('while') < generated.index('break;') < generated.rindex('gv_Index =')
    assert getattr(t.generator, 'loop_depth', 0) == 0
    with pytest.raises(SC2Error):
        t.body(t.call(t.stop))


@pytest.mark.parametrize('corruption', ['template', 'zero-step', 'shadow', 'not-lvalue', 'missing-allow-break'])
def test_unverified_counting_loop_is_rejected(corruption):
    t, key, f = loop_tree(step='0' if corruption == 'zero-step' else '1', library='Other' if corruption == 'shadow' else 'Ntve')
    if corruption == 'template':
        f.find('ScriptCode').text = 'arbitrary template'
    elif corruption == 'missing-allow-break':
        f.remove(f.find('FlagAllowBreak'))
    elif corruption == 'not-lvalue':
        ref = t.nodes[key].find('Parameter')
        p = t.nodes[(ref.get('Library'), 'Param', ref.get('Id'))]
        p.remove(p.find('Variable'))
        E.SubElement(p, 'ValueType', Type='int')
        E.SubElement(p, 'Value').text = '0'
    with pytest.raises(SC2Error):
        t.body(key)
    assert getattr(t.generator, 'loop_depth', 0) == 0
