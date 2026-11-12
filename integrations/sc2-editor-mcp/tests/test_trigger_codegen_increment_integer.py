from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree
ID=('Ntve','FunctionDef','A0F31305')
class Mapping:
    def type(self,e,d,k,tag):
        t=e.find(tag+'/Type');return t.get('Value') if t is not None else None
    raw_type=type
class IncrTree(Tree):
    def __init__(self):
        super().__init__();self.generator.bindings=Mapping()
        for x in E.parse(Path(__file__).parent/'fixtures/increment.xml').getroot():self.nodes[('Ntve',x.get('Type'),x.get('Id'))]=deepcopy(x)
        self.var=self.put('Variable');E.SubElement(self.nodes[self.var],'Identifier').text='count';E.SubElement(E.SubElement(self.nodes[self.var],'VariableType'),'Type',Value='int')
    def call_increment(self,op='+',constant=False,literal_lhs=False):
        c=self.call(ID);p=self.put('Param');self.ref(self.nodes[p],'ParameterDef',('Ntve','ParamDef','7B3B0884'))
        if literal_lhs:E.SubElement(self.nodes[p],'ValueType',Type='int');E.SubElement(self.nodes[p],'Value').text='1'
        else:self.ref(self.nodes[p],'Variable',self.var)
        self.ref(self.nodes[c],'Parameter',p)
        if constant:E.SubElement(self.nodes[self.var].find('VariableType'),'Constant')
        o=self.put('Param');self.ref(self.nodes[o],'ParameterDef',('Ntve','ParamDef','5BFF7323'));pv=self.put('PresetValue','Ntve');E.SubElement(self.nodes[pv],'Value').text=op;self.ref(self.nodes[o],'Preset',pv);self.ref(self.nodes[c],'Parameter',o)
        v=self.put('Param');self.ref(self.nodes[v],'ParameterDef',('Ntve','ParamDef','6725C0EB'));E.SubElement(self.nodes[v],'ValueType',Type='int');E.SubElement(self.nodes[v],'Value').text='2';self.ref(self.nodes[c],'Parameter',v);return c

@pytest.mark.parametrize('op',['+','-','*','/','%'])
def test_exact_native_compound_assignment(op):
    t=IncrTree();code=t.body(t.call_increment(op));assert code.strip()=='gv_count '+op+'= 2;'

@pytest.mark.parametrize('op',['==','&&','|'])
def test_non_arithmetic_operator_rejected(op):
    t=IncrTree()
    with pytest.raises(SC2Error):t.body(t.call_increment(op))

@pytest.mark.parametrize('mutation',['constant','literal','fixed','template','expression','name','return'])
def test_unsupported_contract_rejected(mutation):
    t=IncrTree();c=t.call_increment(constant=mutation=='constant',literal_lhs=mutation=='literal')
    if mutation=='fixed':t.nodes[t.var].find('VariableType/Type').set('Value','fixed')
    elif mutation=='template':t.nodes[ID].find('ScriptCode').text='bad'
    elif mutation=='name':t.nodes[ID].find('Identifier').text='Other'
    elif mutation=='return':E.SubElement(E.SubElement(t.nodes[ID],'ReturnType'),'Type',Value='int')
    with pytest.raises(SC2Error):
        if mutation=='expression':t.generator.call(t.doc,c,t.nodes[c],False)
        else:t.body(c)

def test_indexed_integer_lvalue_is_not_expanded_twice():
    t=IncrTree();c=t.call_increment();E.SubElement(t.nodes[t.var].find('VariableType'),'ArraySize',Dim='0',Value='2');t.generator.global_variables[(str(t.doc.path),t.var)]={'array':2}
    pref=t.nodes[c].findall('Parameter')[0];pkey=(pref.get('Library'),pref.get('Type'),pref.get('Id'));p=t.nodes[pkey];idx=t.put('Param');E.SubElement(t.nodes[idx],'ValueType',Type='int');E.SubElement(t.nodes[idx],'Value').text='1';t.ref(p,'Array',idx)
    assert t.body(c).strip()=='gv_count[1] += 2;'

def test_argument_order_uses_binding_not_xml_position():
    t=IncrTree();c=t.call_increment();n=t.nodes[c];var=n.findall('Parameter')[0];n.remove(var);n.append(var);assert t.body(c).strip()=='gv_count += 2;'
