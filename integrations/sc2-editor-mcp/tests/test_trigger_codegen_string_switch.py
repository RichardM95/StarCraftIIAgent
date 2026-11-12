"""Independent real-template emission checks; native execution is a separate gate."""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from xml.etree import ElementTree as E
import re
import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree

SW=('Ntve','FunctionDef','91C49196'); CASE=('Ntve','FunctionDef','3A1227AB')
CASES=('Ntve','SubFuncType','AD43BC93'); DEFAULTS=('Ntve','SubFuncType','3E7C4C40'); ACTIONS=('Ntve','SubFuncType','363CE97C')
class Mapping:
    aliases={'gamelink':'string'}
    def __init__(self):self.used=[]
    def raw_type(self,e,d,k,tag):
        t=e.find(tag+'/Type');return t.get('Value') if t is not None else ('void' if tag=='ReturnType' else None)
    def type(self,e,d,k,tag):
        v=self.raw_type(e,d,k,tag);return self.aliases.get(v,v)
class SwitchTree(Tree):
    def __init__(self):
        super().__init__();self.doc.sha256='unit-fixture';self.generator.bindings=Mapping()
        for x in E.parse(Path(__file__).parent/'fixtures/string_switch_native.xml').getroot():self.nodes[('Ntve',x.get('Type'),x.get('Id'))]=deepcopy(x)
    def literal(self,definition,value,typ='string'):
        k=self.put('Param');e=self.nodes[k];self.ref(e,'ParameterDef',definition);E.SubElement(e,'ValueType',Type=typ)
        if value is not None:E.SubElement(e,'Value').text=value
        return k
    def marker(self,name):
        d=self.definition('TestCustom',library='');E.SubElement(self.nodes[d],'FlagCustomScript');c=self.call(d);E.SubElement(self.nodes[c],'ScriptCode').text=name+'();';return c
    def case(self,value,actions,disabled=False):
        c=self.call(CASE,{'actions':actions});self.ref(self.nodes[c],'Parameter',self.literal(('Ntve','ParamDef','9A8F1093'),value))
        if disabled:E.SubElement(self.nodes[c],'Disabled')
        return c
    def switch(self,value='A',cases=(),defaults=(),selector=None):
        c=self.call(SW,{'cases':list(cases),'defaults':list(defaults)});self.ref(self.nodes[c],'Parameter',selector or self.literal(('Ntve','ParamDef','B4ACF12A'),value));return c
    def selector(self,kind,typ='string'):
        p=self.put('Param');self.ref(self.nodes[p],'ParameterDef',('Ntve','ParamDef','B4ACF12A'))
        if kind in ['Variable','Parameter']:
            k=self.put('Variable' if kind=='Variable' else 'ParamDef');e=self.nodes[k];E.SubElement(e,'Identifier').text='selectorValue';E.SubElement(E.SubElement(e,'VariableType' if kind=='Variable' else 'ParameterType'),'Type',Value=typ);self.ref(self.nodes[p],kind,k)
        else:
            d=self.definition('TestSelector',library='');E.SubElement(self.nodes[d],'FlagCustomScript');E.SubElement(E.SubElement(self.nodes[d],'ReturnType'),'Type',Value=typ);c=self.call(d);E.SubElement(self.nodes[c],'ScriptCode').text='Selector()';self.ref(self.nodes[p],'FunctionCall',c)
        return p

def decls(code):return re.findall(r'^string (\w+);$',code,re.M)
def test_first_match_chain_preserves_order_and_no_fallthrough():
    t=SwitchTree();s=t.switch(cases=[t.case('A',[t.marker('First')]),t.case('A',[t.marker('Second')])],defaults=[t.marker('Fallback')]);code=t.body(s)
    assert len(decls(code))==1 and code.index('First();')<code.index('Second();')<code.index('Fallback();')
    assert re.search(r'}\s*else if\s*\(',code) and re.search(r'}\s*else\s*{',code)
    assert 'switch (' not in code

def test_empty_literal_case_is_retained():
    t=SwitchTree();code=t.body(t.switch(value=None,cases=[t.case(None,[t.marker('Empty')])]))
    assert '== ""' in code and 'Empty();' in code

def test_default_only_executes_after_selector():
    t=SwitchTree();code=t.body(t.switch(defaults=[t.marker('One'),t.marker('Two')],selector=t.selector('FunctionCall')))
    assert code.count('Selector()')==1 and code.index('Selector()')<code.index('One();')<code.index('Two();')
    assert 'else' not in code

@pytest.mark.parametrize('kind',['Variable','Parameter','FunctionCall'])
def test_supported_string_selector(kind):
    t=SwitchTree();code=t.body(t.switch(selector=t.selector(kind),cases=[t.case('A',[t.marker('Hit')])]))
    assert len(decls(code))==1 and 'Hit();' in code
    if kind=='FunctionCall':assert code.count('Selector()')==1

def test_adjacent_and_nested_switches_have_distinct_hoisted_temps():
    t=SwitchTree();inner=t.switch(cases=[t.case('B',[t.marker('Inner')])]);outer=t.switch(cases=[t.case('A',[inner])]);other=t.switch(cases=[t.case('C',[t.marker('Other')])]);f=t.put('FunctionDef');t.ref(t.nodes[f],'FunctionCall',outer);t.ref(t.nodes[f],'FunctionCall',other);code=t.generator.body(t.doc,f,t.nodes[f]);names=decls(code)
    assert len(names)==3 and len(set(names))==3
    assert all(code.index('string '+n+';')<code.index(' = ') for n in names)

@pytest.mark.parametrize('disabled_index',[0,1])
def test_disabled_case_does_not_break_chain(disabled_index):
    t=SwitchTree();cases=[t.case('A',[t.marker('Drop' if i==disabled_index else 'Keep')],disabled=i==disabled_index) for i in range(2)];code=t.body(t.switch(cases=cases));assert 'Drop();' not in code and 'Keep();' in code;assert not re.search(r'^else if',code,re.M)

def test_default_actions_preserve_order_after_cases():
    t=SwitchTree();code=t.body(t.switch(cases=[t.case('A',[t.marker('Hit')])],defaults=[t.marker('D1'),t.marker('D2')]));assert code.index('Hit();')<code.index('D1();')<code.index('D2();')

def test_selector_assignment_follows_prior_action():
    t=SwitchTree();s=t.switch(selector=t.selector('FunctionCall'));f=t.put('FunctionDef');t.ref(t.nodes[f],'FunctionCall',t.marker('Before'));t.ref(t.nodes[f],'FunctionCall',s);code=t.generator.body(t.doc,f,t.nodes[f]);assert code.count('Selector()')==1 and code.index('Before();')<code.index('Selector()')

@pytest.mark.parametrize('target',[SW,CASE])
def test_control_flow_not_expression(target):
    t=SwitchTree();c=t.switch() if target==SW else t.case('A',[])
    with pytest.raises(SC2Error):t.generator.call(t.doc,c,t.nodes[c],False)

def test_case_without_parent_rejected():
    t=SwitchTree();c=t.case('A',[])
    with pytest.raises(SC2Error):t.body(c)

@pytest.mark.parametrize('mutation',['template','case_template','role','case_definition'])
def test_mutated_or_foreign_native_shapes_rejected(mutation):
    t=SwitchTree();c=t.case('A',[]);s=t.switch(cases=[c])
    if mutation=='template':t.nodes[SW].find('ScriptCode').text='not native template'
    elif mutation=='case_template':t.nodes[CASE].find('ScriptCode').text='not native template'
    elif mutation=='role':t.nodes[c].find('SubFunctionType').set('Library','Other')
    else:t.nodes[c].find('FunctionDef').set('Library','Other')
    with pytest.raises((SC2Error,KeyError)):t.body(s)
    assert t.generator.foreach_scopes==[] and getattr(t.generator,'switch_scopes',[])==[]

def test_integer_selector_is_not_guessed_as_string():
    t=SwitchTree();s=t.switch(selector=t.selector('Variable','int'))
    with pytest.raises(SC2Error):t.body(s)

def test_switch_does_not_create_break_scope():
    t=SwitchTree();s=t.switch(cases=[t.case('A',[t.call(t.stop)])])
    with pytest.raises(SC2Error):t.body(s)
    assert t.generator.loop_depth==0 and getattr(t.generator,'switch_scopes',[])==[]

def test_switch_inside_loop_retains_enclosing_break():
    t=SwitchTree();s=t.switch(cases=[t.case('A',[t.call(t.stop)])]);code=t.body(t.call(t.repeat,{'actions':[s]}));assert code.count('while (true)')==1 and code.count('break;')==1 and t.generator.loop_depth==0

@pytest.mark.parametrize('default_position',[0,1])
def test_subfunction_roles_not_xml_interleaving_control_default(default_position):
    t=SwitchTree();s=t.switch(cases=[t.case('A',[t.marker('Hit1')]),t.case('B',[t.marker('Hit2')])],defaults=[t.marker('Fallback')]);parent=t.nodes[s];refs=parent.findall('FunctionCall');default=refs[-1];parent.remove(default)
    # XML position is deliberately interleaved: native template groups cases first.
    at=list(parent).index(refs[default_position]);parent.insert(at,default);code=t.body(s)
    assert code.index('Hit1();')<code.index('Hit2();')<code.index('Fallback();')
    assert re.search(r'}\s*else\s*{',code)
