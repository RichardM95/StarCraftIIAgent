"""Prepare a GUI-only, self-checking acceptance map in a NEW directory.

Run from the workspace with --source pointing at an Editor-saved Components
map shell and --destination pointing at a new independent .SC2Map directory.
No generated Galaxy is edited and no editor/game is launched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from xml.etree import ElementTree as ET

WORKSPACE=next(p for p in Path(__file__).resolve().parents if (p/'tools/sc2_triggers.py').is_file())
sys.path[:0]=[str(WORKSPACE/'tools'),str(WORKSPACE/'integrations/sc2-editor-mcp/src')]
from sc2_mcp.trigger_pipeline import target_for
from sc2_mcp.trigger_writer import plan_write
from sc2_triggers import ref_key

LIB='AC030001'


def node(tag,attributes=None,text=None,children=None):
    return {k:v for k,v in dict(tag=tag,attributes=attributes,text=text,children=children).items() if v is not None}


def ref(tag,typ,ident,library=None):
    return node(tag,dict(Type=typ,Id=ident,**({'Library':library} if library else {})))


class Matrix:
    def __init__(self,target):
        self.target=target;self.ops=[];self.counter=0;self.defs={};self.messages=[]
        d=next(d for d in target.documents if d.standard=='Ntve')
        self.native={e.findtext('Identifier'):key for key,e in d.elements.items() if key[1]=='FunctionDef'}
        self.defs={key:[ref_key(p,key) for p in e.findall('Parameter') if p.get('Type')!='Comment']
                   for key,e in d.elements.items() if key[1]=='FunctionDef'}

    def ident(self):
        self.counter+=1
        return f'AC02{self.counter:04X}'

    def add(self,typ,children,lib='',ident=None,**kw):
        ident=ident or self.ident()
        self.ops.append(dict(type=typ,id=ident,library=lib,children=children,**kw))
        return (lib,typ,ident)

    def reference(self,tag,key):
        return ref(tag,key[1],key[2],key[0])

    def value(self,value):
        typ='bool' if isinstance(value,bool) else 'int'
        return [node('Value',text=str(value).lower()),node('ValueType',{'Type':typ})]

    def read(self,key):
        return [self.reference('Parameter' if key[1]=='ParamDef' else 'Variable',key)]

    def literal_param(self,value,lib=''):
        return self.add('Param',self.value(value),lib)

    def variable(self,name,typ='int',lib='',owner=None,initial=None):
        children=[node('Identifier',text=name),node('VariableType',children=[node('Type',{'Value':typ})])]
        if initial is not None:children.append(self.reference('Value',self.literal_param(initial,lib)))
        kw={'name':name}
        if owner:kw['owner']={'type':owner[1],'id':owner[2]}
        return self.add('Variable',children,lib,**kw)

    def call(self,definition,args=(),lib='',groups=(),disabled=False):
        key=self.native[definition] if isinstance(definition,str) else definition
        children=[self.reference('FunctionDef',key)]
        parameters=self.defs[key]
        if len(parameters)!=len(args):raise ValueError(f'argument count: {key}')
        for pd,value in zip(parameters,args):
            param=self.add('Param',[self.reference('ParameterDef',pd)]+value,lib)
            children.append(self.reference('Parameter',param))
        for subtype,calls in groups:
            for c in calls:
                op=next(o for o in self.ops if (o['library'],o['type'],o['id'])==c)
                op['children'].append(ref('SubFunctionType','SubFuncType',subtype,'Ntve'))
                children.append(self.reference('FunctionCall',c))
        if disabled:children.append(node('Disabled'))
        return self.add('FunctionCall',children,lib)

    def expression(self,definition,args=(),lib=''):
        return [self.reference('FunctionCall',self.call(definition,args,lib))]

    def arithmetic(self,a,operator,b,lib=''):
        preset='00000085' if operator=='+' else '00000087'
        return self.expression('ArithmeticInt',[a,[ref('Preset','PresetValue',preset,'Ntve')],b],lib)

    def compare(self,a,operator,b,lib=''):
        return self.call('Comparison',[a,[ref('Preset','PresetValue','1E7A4625' if operator=='==' else '684CA9CE','Ntve')],b],lib)

    def assign(self,var,expression,lib='',disabled=False):
        return self.call('SetVariable',[self.read(var),expression],lib,disabled=disabled)

    def branch(self,condition,yes,no=(),lib=''):
        return self.call('IfThenElse',lib=lib,groups=[('00000003',[condition]),('00000004',yes),('00000005',no)])

    def message(self,text):
        ident=self.ident();anchor='Param/Value/'+ident
        param=self.add('Param',[ref('ParameterDef','ParamDef','78A54B52','Ntve'),node('Value',text=anchor),node('ValueType',{'Type':'text'})],ident=ident,strings={anchor:text})
        players=self.add('Param',[ref('ParameterDef','ParamDef','0D120C33','Ntve')]+self.expression('PlayerGroupAll'))
        area=self.add('Param',[ref('ParameterDef','ParamDef','A4C19F41','Ntve'),ref('Preset','PresetValue','89CC0A21','Ntve')])
        self.messages.append(text)
        return self.add('FunctionCall',[self.reference('FunctionDef',self.native['UIDisplayMessage'])]+[self.reference('Parameter',p) for p in [players,area,param]])

    def verify(self,condition,label,all_passed):
        return self.branch(condition,[self.message('GUI_MATRIX_'+label+'_PASS')],
                           [self.assign(all_passed,self.value(False)),self.message('GUI_MATRIX_'+label+'_FAIL')])

    def build(self):
        trigger=('', 'Trigger',self.ident());function=('', 'FunctionDef',self.ident());action=(LIB,'FunctionDef',self.ident())
        score=self.variable('MatrixScore');ok=self.variable('AllPassed','bool')
        index=self.variable('LoopIndex',owner=trigger,initial=0)
        cross=self.variable('CrossLibraryResult',lib=LIB)
        arg=self.add('ParamDef',[node('Identifier',text='Input'),node('ParameterType',children=[node('Type',{'Value':'int'})])],owner={'type':'FunctionDef','id':function[2]})
        local=self.variable('Doubled',owner=function)
        twice_body=[self.assign(local,self.arithmetic(self.read(arg),'*',self.value(2))),self.call('Return',[self.read(local)])]
        self.add('FunctionDef',[node('Identifier',text='DoubleInput'),node('FlagCall'),node('ReturnType',children=[node('Type',{'Value':'int'})]),self.reference('Parameter',arg),self.reference('Variable',local)]+[self.reference('FunctionCall',c) for c in twice_body],ident=function[2],name='Double Input')
        self.defs[function]=[arg]
        crossarg=self.add('ParamDef',[node('Identifier',text='Input'),node('ParameterType',children=[node('Type',{'Value':'int'})])],LIB,owner={'type':'FunctionDef','id':action[2]})
        set_cross=self.assign(cross,self.arithmetic(self.read(crossarg),'+',self.value(5),LIB),LIB)
        self.add('FunctionDef',[node('Identifier',text='AddFiveAndStore'),node('FlagAction'),self.reference('Parameter',crossarg),self.reference('FunctionCall',set_cross)],LIB,ident=action[2],name='Add Five And Store')
        self.defs[action]=[crossarg]
        loop=self.call('While',groups=[('20298AEC',[self.compare(self.read(index),'<',self.value(3))]),('A1B37466',[
            self.assign(score,self.arithmetic(self.read(score),'+',self.value(1))),
            self.assign(index,self.arithmetic(self.read(index),'+',self.value(1)))])])
        actions=[self.assign(ok,self.value(True)),self.assign(score,self.value(0)),loop,
                 self.verify(self.compare(self.read(index),'==',self.value(3)),'LOOP',ok),
                 self.assign(score,self.value(-999),disabled=True),
                 self.verify(self.compare(self.read(score),'==',self.value(3)),'DISABLED',ok),
                 self.branch(self.compare(self.read(score),'==',self.value(99)),[self.assign(score,self.value(-100))],[self.assign(score,self.value(10))]),
                 self.branch(self.compare(self.read(score),'==',self.value(10)),[self.assign(score,self.value(12))],[self.assign(score,self.value(-100))]),
                 self.verify(self.compare(self.read(score),'==',self.value(12)),'BRANCH',ok),
                 self.assign(score,self.expression(function,[self.read(score)])),
                 self.verify(self.compare(self.read(score),'==',self.value(24)),'FUNCTION',ok),
                 self.call(action,[self.read(score)]),
                 self.verify(self.compare(self.read(cross),'==',self.value(29)),'CROSSLIB',ok),
                 self.branch(self.compare(self.read(ok),'==',self.value(True)),[self.message('GUI_MATRIX_ALL_PASS')],[self.message('GUI_MATRIX_ALL_FAIL')])]
        event=self.call('TriggerAddEventMapInit')
        self.add('Trigger',[node('Identifier',text='MatrixInit'),self.reference('Variable',index),self.reference('Event',event)]+[self.reference('Action',c) for c in actions],ident=trigger[2],name='Matrix Initialization')
        # Owners must exist before declaration registration; graph references
        # themselves may refer forward until the final dependency check.
        return sorted(self.ops,key=lambda o:0 if o['type'] in {'Trigger','FunctionDef','Category'} else 1)


def prepare(source,destination):
    source=source.resolve();destination=destination.resolve()
    if destination.exists():raise ValueError('destination must be new')
    if destination.suffix.lower()!='.sc2map' or not destination.is_relative_to(WORKSPACE):raise ValueError('use a new workspace .SC2Map destination')
    target=target_for(source)
    if target.problems:raise ValueError(target.problems)
    matrix=Matrix(target);ops=matrix.build()
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('.sc2-mcp','_codex_backups'))
    # Match the Editor-saved layout: embedded Library blocks precede map Root.
    root=ET.Element('TriggerData');library=ET.SubElement(root,'Library',{'Id':LIB});ET.SubElement(library,'Root');ET.SubElement(root,'Root')
    # New candidate source only; copied MapScript is never edited.
    (destination/'Triggers').write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
    changes=plan_write(destination,ops,locale='enUS')
    for relative,raw in changes.items():
        p=destination/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    packet={'map':str(destination),'scope':'finite While, both branches, disabled action, custom return/local variable, same-map cross-library GUI action',
            'expected_messages':[s for s in matrix.messages if s.endswith('_PASS')],
            'Editor accepted':False,'packaged runtime passed':False,
            'triggers_sha256':hashlib.sha256((destination/'Triggers').read_bytes()).hexdigest()}
    (destination.parent/'matrix-handoff.json').write_text(json.dumps(packet,indent=2),encoding='utf-8')
    (destination.parent/'matrix-operations.json').write_text(json.dumps(ops,indent=2),encoding='utf-8')
    return packet


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.source,args.destination),indent=2))
