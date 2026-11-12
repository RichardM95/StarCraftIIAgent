"""Non-executable GUI comments stay in Triggers and produce no call text."""
from xml.etree import ElementTree as E
import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree

def comment(t):
    key=t.put('Comment')
    E.SubElement(t.nodes[key],'Comment').text='空天赋/无效天赋校验'
    return key

def test_statement_comment_is_not_a_missing_function():
    t=Tree();key=comment(t)
    assert t.generator.call(t.doc,key,t.nodes[key])==''

def test_comment_does_not_drop_next_real_action():
    t=Tree();note=comment(t)
    definition=t.definition('TestCustom')
    E.SubElement(t.nodes[definition],'FlagCustomScript')
    action=t.call(definition)
    E.SubElement(t.nodes[action],'ScriptCode').text='Marker();'
    fn=t.put('FunctionDef')
    t.ref(t.nodes[fn],'FunctionCall',note)
    t.ref(t.nodes[fn],'FunctionCall',action)
    assert t.generator.body(t.doc,fn,t.nodes[fn]).strip()=='Marker();'

def test_nested_comment_keeps_loop_and_other_body_actions():
    t=Tree();note=comment(t)
    loop=t.call(t.repeat,{'actions':[note,t.call(t.stop)]})
    assert 'break;' in t.body(loop)

def test_comment_is_not_an_expression_value():
    t=Tree();key=comment(t)
    with pytest.raises(SC2Error):t.generator.call(t.doc,key,t.nodes[key],False)

def test_disabled_comment_is_still_not_an_expression_value():
    t=Tree();key=comment(t)
    E.SubElement(t.nodes[key],'Disabled')
    with pytest.raises(SC2Error):t.generator.call(t.doc,key,t.nodes[key],False)

@pytest.mark.parametrize('kind',['FunctionCall','Param','Label'])
def test_other_missing_function_nodes_are_not_ignored(kind):
    t=Tree();key=t.put(kind)
    with pytest.raises(SC2Error):t.generator.call(t.doc,key,t.nodes[key])
