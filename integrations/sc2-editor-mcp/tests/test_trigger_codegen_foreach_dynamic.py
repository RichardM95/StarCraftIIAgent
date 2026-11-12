"""Emitter-only checks. GUI validator is stubbed only in callback-layout test."""
import re
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as E
import pytest
from test_trigger_codegen_foreach_constant import loop_tree
from sc2_mcp.errors import SC2Error


def generator(t):
    t.doc.name=lambda k:k[2]
    return t.generator


def variable(t,name):
    k=t.put('Variable');n=t.nodes[k];E.SubElement(n,'Identifier').text=name;E.SubElement(E.SubElement(n,'VariableType'),'Type',Value='int');return k


def replace_arg(t,key,slot,ref):
    r=t.nodes[key].findall('Parameter')[slot];p=t.nodes[(r.get('Library'),r.get('Type'),r.get('Id'))]
    for n in list(p):
        if n.tag!='ParameterDef':p.remove(n)
    t.ref(p,ref[1],ref)


def script(t,code):
    f=t.definition('TestCustom');E.SubElement(t.nodes[f],'FlagCustomScript');k=t.call(f);E.SubElement(t.nodes[k],'ScriptCode').text=code;return k


def test_bound_is_cached_once_before_start_and_body_mutation():
    t,key,f=loop_tree();generator(t);end=variable(t,'Bound');start=variable(t,'Start');replace_arg(t,key,1,start);replace_arg(t,key,2,end)
    sub=f.find('SubFunctionType');body=script(t,'gv_Bound = 0;');t.ref(t.nodes[body],'SubFunctionType',(sub.get('Library'),sub.get('Type'),sub.get('Id')));t.ref(t.nodes[key],'FunctionCall',body)
    out=t.body(key);pairs=re.findall(r'(\w+) = gv_Bound;',out);assert len(pairs)==1;cache=pairs[0]
    assert out.index(cache+' = gv_Bound;')<out.index('gv_Index = gv_Start;')<out.index('while')<out.index('gv_Bound = 0;')
    condition=out[out.index('while'):out.index('{',out.index('while'))];assert cache in condition and 'gv_Bound' not in condition
    assert out.index('int '+cache+';')<out.index(cache+' = gv_Bound;')


def test_native_bound_expression_is_evaluated_once():
    t,key,_=loop_tree();generator(t);call=script(t,'ProbeEnd()');replace_arg(t,key,2,call);out=t.body(key)
    assert out.count('ProbeEnd()')==1 and out.index('ProbeEnd()')<out.index('gv_Index = 0;')


def test_nested_identical_expression_uses_distinct_cache():
    t,key,f=loop_tree();generator(t);end=variable(t,'Bound');replace_arg(t,key,2,end)
    # Independent inner call with the same bound expression.
    inner=t.call(('Ntve','FunctionDef','66474248'));iv=variable(t,'Inner')
    for i,slot in enumerate(f.findall('Parameter')):
        p=t.put('Param');n=t.nodes[p];t.ref(n,'ParameterDef',(slot.get('Library'),slot.get('Type'),slot.get('Id')))
        if i in [0,2]:t.ref(n,'Variable',iv if i==0 else end)
        else:E.SubElement(n,'ValueType',Type='int');E.SubElement(n,'Value').text='0' if i==1 else '1'
        t.ref(t.nodes[inner],'Parameter',p)
    sub=f.find('SubFunctionType');t.ref(t.nodes[inner],'SubFunctionType',(sub.get('Library'),sub.get('Type'),sub.get('Id')));t.ref(t.nodes[key],'FunctionCall',inner)
    out=t.body(key);names=re.findall(r'(\w+) = gv_Bound;',out);assert len(names)==2 and len(set(names))==2
    assert all(('int '+n+';') in out for n in names)


def test_same_bound_in_next_function_gets_declaration_again():
    t,key,_=loop_tree();generator(t);end=variable(t,'Bound');replace_arg(t,key,2,end)
    for _ in range(2):
        out=t.body(key);names=re.findall(r'(\w+) = gv_Bound;',out);assert len(names)==1 and ('int '+names[0]+';') in out


def test_dynamic_step_still_rejected_and_scope_recovers():
    t,key,_=loop_tree();generator(t);replace_arg(t,key,3,variable(t,'Step'))
    with pytest.raises(SC2Error):t.body(key)
    assert getattr(t.generator,'loop_depth',0)==0


def test_callback_auto_declarations_precede_guard_but_evaluation_follows(monkeypatch):
    t,key,_=loop_tree();g=generator(t);end=variable(t,'Bound');replace_arg(t,key,2,end)
    tr=t.put('Trigger');E.SubElement(t.nodes[tr],'Identifier').text='Probe';t.ref(t.nodes[tr],'Action',key)
    root=E.Element('TriggerData');r=E.SubElement(root,'Root');t.ref(r,'Item',tr);t.ref(r,'Item',end)
    t.doc.root=root;t.doc.component=Path('.');t.doc.standard='';t.documents=[t.doc];t.graph={}
    g.bindings=SimpleNamespace(used=[],type=lambda e,d,k,tag:e.find(tag+'/Type').get('Value'))
    import sc2_triggers,sc2_mcp.trigger_writer
    monkeypatch.setattr(sc2_triggers,'check',lambda target:{'errors':[]})
    monkeypatch.setattr(sc2_mcp.trigger_writer,'validate_editor_library_layout',lambda root:None)
    source=g.generate()['source'];body=source[source.index('bool gt_Probe_Func'):];name=re.search(r'(\w+) = gv_Bound;',body).group(1)
    assert body.index('int '+name+';')<body.index('if (testConds')<body.index('if (!runActions)')<body.index(name+' = gv_Bound;')
