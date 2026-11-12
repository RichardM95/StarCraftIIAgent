"""Literal emission and rejection only; these do not assert gameplay values."""
import json
from types import SimpleNamespace
from xml.etree import ElementTree as E
import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree

def setup(kind='userfield',value='Taken',alias='string'):
    t=Tree()
    t.generator.bindings=SimpleNamespace(aliases={} if alias is None else {kind:alias})
    key=t.put('Param')
    n=t.nodes[key]
    E.SubElement(n,'ParameterDef',Type='ParamDef',Library='Ntve',Id='344B79F1')
    E.SubElement(n,'ValueType',Type=kind)
    E.SubElement(n,'Value').text=value
    E.SubElement(n,'ValueContext',Value='RogueTalents')
    return t,key,n

def emit(t,key,n):return t.generator.expr(t.doc,key,n)

@pytest.mark.parametrize('kind,value',[('userfield','Taken'),('userinstance','Secret Password'),('userfield','中文 "quoted" \\ = 1'),('userinstance','@my-instance'),('userinstance','null')])
def test_source_bound_alias_emits_exact_quoted_string(kind,value):
    t,key,n=setup(kind,value)
    assert emit(t,key,n)==json.dumps(value,ensure_ascii=True)

@pytest.mark.parametrize('alias',[None,'int','text','userfield'])
def test_alias_must_actually_be_string(alias):
    t,key,n=setup(alias=alias)
    with pytest.raises(SC2Error):emit(t,key,n)

@pytest.mark.parametrize('corrupt',['no-context','duplicate-context','context-attribute','context-child','context-text','empty-context','duplicate-type','type-attribute','type-text','duplicate-value','value-attribute','value-child','unknown-child','element-attribute','second-parameter','mixed-value'])
def test_uncovered_metadata_is_not_silently_dropped(corrupt):
    t,key,n=setup()
    if corrupt=='no-context':n.remove(n.find('ValueContext'))
    elif corrupt=='duplicate-context':n.append(E.fromstring('<ValueContext Value="Other"/>'))
    elif corrupt=='context-attribute':n.find('ValueContext').set('Id','surprise')
    elif corrupt=='context-child':E.SubElement(n.find('ValueContext'),'Other')
    elif corrupt=='context-text':n.find('ValueContext').text='UnknownMetadata'
    elif corrupt=='empty-context':n.find('ValueContext').set('Value','')
    elif corrupt=='duplicate-type':E.SubElement(n,'ValueType',Type='userfield')
    elif corrupt=='type-attribute':n.find('ValueType').set('GameType','surprise')
    elif corrupt=='type-text':n.find('ValueType').text='UnknownMetadata'
    elif corrupt=='duplicate-value':E.SubElement(n,'Value').text='Different'
    elif corrupt=='value-attribute':n.find('Value').set('Id','surprise')
    elif corrupt=='value-child':E.SubElement(n.find('Value'),'Other')
    elif corrupt=='unknown-child':E.SubElement(n,'Other')
    elif corrupt=='element-attribute':n.set('Unexpected','true')
    elif corrupt=='second-parameter':E.SubElement(n,'ParameterDef',Type='ParamDef',Library='Ntve',Id='619F5CB9')
    elif corrupt=='mixed-value':E.SubElement(n,'Variable',Type='Variable',Id='BAD00001')
    with pytest.raises(SC2Error):emit(t,key,n)

def test_unrelated_gui_type_remains_rejected_even_with_string_alias():
    t,key,n=setup(kind='unknownvalue')
    with pytest.raises(SC2Error):emit(t,key,n)
