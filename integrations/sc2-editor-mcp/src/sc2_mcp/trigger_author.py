"""Versioned behavior requests, lowered to the existing GUI writer and transaction."""
import copy
import difflib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from .errors import SC2Error
from .storage import digest, safe_path, write_json
from .trigger_context import definition, fingerprint, inputs, local_document
from .trigger_pipeline import target_for
from .trigger_writer import plan_write, _matches, _replace_container


def fail(path, message, **details):
    raise SC2Error('trigger_author_invalid', message, spec_path=path, **details)


def fields(value, allowed, path):
    if not isinstance(value,dict):fail(path,'expected an object')
    unknown=set(value)-set(allowed.split())
    if unknown:fail(path,'unknown request fields',fields=sorted(unknown))


def reference(tag, key):
    return ET.Element(tag,{'Type':key[1],'Id':key[2],**({'Library':key[0]} if key[0] else {})})


def child_data(e):
    return {'tag':e.tag,'attributes':dict(e.attrib),'text':e.text,
            'children':[child_data(c) for c in e]}


def rewrite_children(original,element):
    """Keep original spans for unmodified children, including unknown XML and comments."""
    from .spatial import _parse
    raw=original.encode('utf-8');span=_parse(raw,'Triggers');old=ET.fromstring(raw)
    def signature(e):
        e=copy.deepcopy(e);e.tail=None
        return ET.tostring(e)
    if len(span.children)!=len(old):fail('edits','cannot align XML child spans')
    available={};gaps={}
    for i,(node,e) in enumerate(zip(span.children,old)):
        end=span.children[i+1].start if i+1<len(span.children) else span.close_start
        available.setdefault(signature(e),[]).append((i,raw[node.start:node.end]))
        gaps[i]=raw[node.end:end]
    opening=raw[:span.open_end]
    if opening.rstrip().endswith(b'/>'):
        return (opening.rstrip()[:-2]+b'>'+b''.join(signature(c) for c in element)+b'</'+element.tag.encode()+b'>').decode('utf-8')
    prefix=raw[span.open_end:span.children[0].start] if span.children else raw[span.open_end:span.close_start]
    pieces=[opening,prefix];used=set()
    for c in element:
        matches=available.get(signature(c),[])
        if matches:
            i,data=matches.pop(0);used.add(i);pieces.extend([data,gaps[i]])
        else:pieces.append(signature(c))
    pieces.extend(gap for i,gap in gaps.items() if i not in used)
    pieces.append(raw[span.close_start:])
    return b''.join(pieces).decode('utf-8')


def _selected_elements(text,key):
    # Same directed (Type,Id) lookahead as writer.register: any attribute order and either quote style.
    pattern=(r'<Element\b(?=[^>]*?\bType\s*=\s*[\"\']'+re.escape(key[1])+r'[\"\'])(?=[^>]*?\bId\s*=\s*[\"\']'+re.escape(key[2])+r'[\"\'])[^>]*?(?:/>|>.*?</Element>)')
    return _matches(pattern,text)


class Author:
    def __init__(self, root, target, spec):
        self.root=root;self.target=target;self.doc=local_document(target);self.spec=spec
        self.library=spec.get('library','');self.elements=copy.deepcopy(self.doc.elements)
        self.original=copy.deepcopy(self.elements);self.names={};self.scopes={};self._scope_lookup_cache={};self.node_map={}
        self.instances={};self.path_aliases={};self.recheck_parameters={}
        self.roots={(self.doc.standard,'Root',''):copy.deepcopy(self.doc.root.find('Root'))}
        self.roots.update({(lib.get('Id'),'Root',''):copy.deepcopy(lib.find('Root')) for lib in self.doc.root.findall('Library')})
        self.old_roots=copy.deepcopy(self.roots)
        self.strings={};self.display_names={};self.deleted=set();self.impacts=[]
        self.used={k[2] for d in target.documents for k in d.elements}
        self.current_scope=None;self.return_type=None
        from .trigger_bindings import Bindings
        from .trigger_pipeline import controlled_files
        files,_=controlled_files(target,skip_generated=True)
        self.mapping=Bindings(target,files,[p for p in ('triggerlibs/natives.galaxy','triggerlibs/nativelib.galaxy') if p in files])
        if self.library and self.doc.root.find("Library[@Id='"+self.library+"']") is None:
            fail('library','target library must already exist in this document')

    def alloc(self, typ, path):
        salt=0
        while True:
            ident=digest((self.spec['request_id']+'\0'+path+'\0'+str(salt)).encode())[:8].upper()
            if ident not in self.used:break
            salt+=1
        self.used.add(ident);key=(self.library,typ,ident);self.node_map.setdefault(path,list(key))
        self.instances.setdefault(path,[]).append(list(key))
        self.elements[key]=ET.Element('Element',{'Type':typ,'Id':ident})
        return key

    def public_path(self,path):
        for _ in range(len(self.path_aliases)+1):
            source=next((path[:i] for i in range(len(path),-1,-1) if (i==len(path) or path[i] in '.[') and path[:i] in self.path_aliases),None)
            if source is None:break
            path=self.path_aliases[source]+path[len(source):]
        return path

    def resolve(self, ref, kind, path):
        if isinstance(ref,str) and ref in self.names:
            key=self.names[ref]
            if key in self.deleted:fail(path,'request reference was deleted by an earlier edit',reference=list(key))
            if key[1]!=kind:fail(path,'wrong symbolic reference kind',expected=kind,actual=list(key))
            return self.doc,key,self.elements[key]
        if isinstance(ref,list) and len(ref)==3 and tuple(ref) in self.deleted:
            fail(path,'request reference was deleted by an earlier edit',reference=ref)
        if isinstance(ref,list) and len(ref)==3 and tuple(ref) in self.elements:
            key=tuple(ref)
            if key[1]!=kind:fail(path,'wrong reference kind',expected=kind,actual=ref)
            return self.doc,key,self.elements[key]
        try:return definition(self.target,self.doc,ref,kind)
        except (SC2Error,ValueError) as exc:
            fail(path,str(exc),**(exc.details if isinstance(exc,SC2Error) else {}))

    def type_node(self, value, tag, path):
        e=ET.Element(tag)
        if isinstance(value,str) and re.fullmatch('[a-z]+',value):ET.SubElement(e,'Type',Value=value)
        elif isinstance(value,dict) and set(value)=={'preset'}:
            _,key,_=self.resolve(value['preset'],'Preset',path)
            ET.SubElement(e,'Type',Value='preset');e.append(reference('TypeElement',key))
        else:fail(path,'type must be a GUI type or an exact preset reference')
        return e

    def typ(self,d,key,e,tag):
        value=self.mapping.raw_type(e,d,key,tag)
        return 'unit' if value=='unitref' else value

    def expression_type(self,value,path):
        if isinstance(value,bool):return 'bool'
        if isinstance(value,int):return 'int'
        if isinstance(value,float):return 'fixed'
        if isinstance(value,str):return 'string'
        if not isinstance(value,dict):fail(path,'unsupported expression')
        if 'compare' in value:return 'bool'
        if 'arithmetic' in value:return self.expression_type(value['left'],path+'.left')
        if 'literal' in value:return value.get('type','string')
        if 'region' in value:return 'region'
        if 'var' in value or 'parameter' in value:
            kind='Variable' if 'var' in value else 'ParamDef';field='var' if kind=='Variable' else 'parameter'
            d,k,e=self.resolve(value[field],kind,path)
            return self.typ(d,k,e,'VariableType' if kind=='Variable' else 'ParameterType')
        if 'call' in value:
            d,k,e=self.resolve(value['call'],'FunctionDef',path+'.call')
            return self.typ(d,k,e,'ReturnType')
        if 'preset' in value:
            d,k,e=self.resolve(value['preset'],'PresetValue',path)
            return self.preset_type(k,path)
        fail(path,'cannot infer expression type')

    def preset_type(self,key,path):
        parents=[e for d in self.target.documents for k,e in d.elements.items() if k[1]=='Preset'
                 and any(self.ref_key(c,k)==key for c in e.findall('Item'))]
        if len(parents)!=1 or parents[0].find('BaseType') is None:fail(path,'preset value has no unique owning preset',reference=list(key))
        return parents[0].find('BaseType').get('Value')

    def expect(self, actual, expected, path):
        if expected in {None,'anycompare','anyvariable','any','return'}:return
        if actual==expected or (expected=='fixed' and actual=='int'):return
        fail(path,'argument type mismatch',expected=expected,actual=actual)

    def check_scope(self,key,path):
        # self.scopes holds only declared locals (build relies on 'key in self.scopes'); global lookups cache separately.
        cache=self._scope_lookup_cache
        if key in self.scopes:owner=self.scopes[key]
        elif key in cache:owner=cache[key]
        else:
            owner=None
            for parent,e in self.elements.items():
                if parent[1] in {'FunctionDef','Trigger'} and any(self.ref_key(c,parent)==key for c in e if c.tag in {'Variable','Parameter'}):
                    owner=parent;break
            cache[key]=owner
        if owner and owner!=self.current_scope:fail(path,'local reference crosses function scope',reference=list(key),owner=list(owner))

    def expression(self,value,path,expected=None):
        if isinstance(value,(bool,int,float,str)):
            typ='bool' if isinstance(value,bool) else 'int' if isinstance(value,int) else 'fixed' if isinstance(value,float) else 'string'
            result=[ET.Element('Value'),ET.Element('ValueType',Type=typ)]
            result[0].text=str(value).lower() if typ=='bool' else str(value)
        else:
            fields(value,'var parameter preset call arguments compare left right arithmetic literal type game_type region data_context',path)
            forms=set(value)&{'var','parameter','preset','call','compare','arithmetic','literal','region'}
            if len(forms)!=1:fail(path,'expression needs exactly one value form')
            user='literal' in value and isinstance(value['literal'],str)
            if 'data_context' in value and not (user and value.get('type') in {'userfield','userinstance'}):
                fail(path+'.data_context','data_context is only valid with a userfield or userinstance string literal')
            if 'var' in value or 'parameter' in value:
                kind='Variable' if 'var' in value else 'ParamDef';field='var' if 'var' in value else 'parameter'
                d,k,e=self.resolve(value[field],kind,path);self.check_scope(k,path)
                typ=self.typ(d,k,e,'VariableType' if kind=='Variable' else 'ParameterType')
                result=[reference('Variable' if kind=='Variable' else 'Parameter',k)]
            elif 'preset' in value:
                d,k,e=self.resolve(value['preset'],'PresetValue',path)
                typ=self.preset_type(k,path);result=[reference('Preset',k)]
            elif 'call' in value or 'compare' in value or 'arithmetic' in value:
                if 'compare' in value or 'arithmetic' in value:
                    op=value.get('compare',value.get('arithmetic'))
                    if op not in {'==','!=','<','>','<=','>=','+','-','*','/','%'}:fail(path,'unsupported operator')
                    left_type=self.expression_type(value['left'],path+'.left')
                    self.expect(self.expression_type(value['right'],path+'.right'),left_type,path+'.right')
                    name='Comparison' if 'compare' in value else 'ArithmeticInt' if left_type=='int' else 'ArithmeticReal'
                    d,k,f=self.resolve(name,'FunctionDef',path)
                    slots=[self.ref_key(c,k) for c in f.findall('Parameter') if c.get('Type')=='ParamDef']
                    pd,pe=self.target.resolve(slots[1],d)
                    preset_ref=pe.find('ParameterType/TypeElement')
                    preset_key=self.ref_key(preset_ref,slots[1]);sd,se=self.target.resolve(preset_key,pd)
                    choices=[]
                    for c in se.findall('Item'):
                        ck=self.ref_key(c,preset_key);_,ce=self.target.resolve(ck,sd)
                        if ce.findtext('Value')==op:choices.append(list(ck))
                    if len(choices)!=1:fail(path,'operator preset missing or ambiguous',operator=op)
                    self.path_aliases.update({path+'.arguments[0].value':path+'.left',path+'.arguments[1].value':path+('.compare' if 'compare' in value else '.arithmetic'),path+'.arguments[2].value':path+'.right'})
                    value={'call':list(k),'arguments':[
                        {'slot':list(slots[0]),'value':value['left']},
                        {'slot':list(slots[1]),'value':{'preset':choices[0]}},
                        {'slot':list(slots[2]),'value':value['right']} ]}
                key,typ=self.call(value,path,expression=True);result=[reference('FunctionCall',key)]
            elif 'literal' in value:
                typ=value.get('type','string');literal=value['literal']
                if typ=='text':
                    # Anchor is bound to the containing Param, assigned in param().
                    result=[ET.Element('Value'),ET.Element('ValueType',Type='text')];result[0].text=str(literal)
                elif typ in {'userfield','userinstance'}:
                    context=value.get('data_context')
                    if not isinstance(literal,str) or not literal:fail(path,'user literal needs a nonempty string value')
                    if not isinstance(context,str) or not context.strip() or not re.fullmatch(r'[ \x21-\x7e]+',context):fail(path+'.data_context','user literal needs a nonempty printable ASCII data_context')
                    result=[ET.Element('Value'),ET.Element('ValueType',Type=typ),ET.Element('ValueContext',Value=context)];result[0].text=literal
                elif typ in {'gamelink','anygamelink'}:
                    if not isinstance(literal,str):fail(path,'game link must be a string')
                    result=[ET.Element('Value'),ET.Element('ValueType',Type=typ)];result[0].text=literal
                    if typ=='gamelink':
                        if not re.fullmatch('[A-Za-z]+',value.get('game_type','')):fail(path+'.game_type','game link needs an explicit catalog type')
                        result.append(ET.Element('ValueGameType',Type=value['game_type']))
                else:
                    result,actual=self.expression(literal,path+'.literal');self.expect(actual,typ,path)
            elif 'region' in value:
                from .spatial import inspect_spatial
                regions=inspect_spatial(self.root,'regions')['regions']
                matches=[r for r in regions if str(value['region'])==r['id'] or any(c['kind']=='name' and c['attributes'].get('value')==value['region'] for c in r['children'])]
                if len(matches)!=1:fail(path,'named region missing or ambiguous',candidates=regions)
                typ='region';result=[ET.Element('ValueType',Type='region'),ET.Element('ValueId',Id=matches[0]['id'])]
            else:fail(path,'unsupported expression')
        self.expect(typ,expected,path)
        return result,typ

    @staticmethod
    def ref_key(ref,owner):
        from sc2_triggers import ref_key
        return ref_key(ref,owner)

    def param(self,value,path,slot=None,expected=None):
        key=self.alloc('Param',path)
        children,typ=self.expression(value,path,expected)
        if any(c.tag=='ValueType' and c.get('Type')=='text' for c in children):
            anchor='Param/Value/'+(f'lib_{key[0]}_' if key[0] else '')+key[2]
            self.strings[anchor]=children[0].text;children[0].text=anchor
        if slot:self.elements[key].append(reference('ParameterDef',slot))
        self.elements[key].extend(children)
        return key,typ

    def reuse_instance(self,replacement,key):
        node=self.elements.pop(replacement);node.set('Id',key[2]);self.elements[key]=node
        if key[1]=='Param' and node.find("ValueType[@Type='text']") is not None:
            value=node.find('Value');old=value.text
            value.text='Param/Value/'+(f'lib_{key[0]}_' if key[0] else '')+key[2]
            self.strings[value.text]=self.strings.pop(old)
        for path,ref in self.node_map.items():
            if tuple(ref)==replacement:self.node_map[path]=list(key)
        for path,refs in self.instances.items():
            self.instances[path]=[list(key) if tuple(ref)==replacement else ref for ref in refs]
        return node

    def existing_type(self,key,path,seen=None):
        seen=seen or set()
        if key in seen:fail(path,'cyclic expression type',reference=list(key))
        d,key,e=self.resolve(list(key),key[1],path)
        if key[1] in {'Variable','ParamDef'}:return self.typ(d,key,e,'VariableType' if key[1]=='Variable' else 'ParameterType')
        if key[1]=='FunctionCall':
            d,fk,f=self.resolve(list(self.ref_key(e.find('FunctionDef'),key)),'FunctionDef',path)
            return self.typ(d,fk,f,'ReturnType') if f.find('ReturnType') is not None else 'void'
        if key[1]=='PresetValue':return self.preset_type(key,path)
        if key[1]=='Param' and (e.find('CustomType') is not None or e.find('ScriptCode') is not None):
            self.known_instance(key,path);return 'filepath'
        value_type=e.find('ValueType')
        if value_type is not None:return value_type.get('Type')
        for c in e:
            if c.tag in {'Variable','Parameter','Preset','FunctionCall'}:
                return self.existing_type(self.ref_key(c,key),path,seen|{key})
        fail(path,'cannot determine existing expression type',reference=list(key))

    def parameter_expected(self,key,path):
        e=self.elements[key];pd=e.find('ParameterDef')
        if pd is not None:
            d,pk,pe=self.resolve(list(self.ref_key(pd,key)),'ParamDef',path)
            raw=pe.find('ParameterType/Type');kind=raw.get('Value') if raw is not None else None
            if kind=='return':return self.return_type
            if kind!='sameas':return self.typ(d,pk,pe,'ParameterType')
            other=pe.find('ParameterType/TypeElement')
            if other is None:fail(path,'sameas parameter has no source slot',parameter=list(pk))
            slot=self.ref_key(other,pk);matches=[]
            for parent,ce in self.elements.items():
                if not any(c.tag=='Parameter' and self.ref_key(c,parent)==key for c in ce):continue
                for c in ce.findall('Parameter'):
                    ck=self.ref_key(c,parent);param=self.elements[ck];pref=param.find('ParameterDef')
                    if pref is not None and self.ref_key(pref,ck)==slot:matches.append(ck)
            if len(matches)!=1:fail(path,'sameas source argument missing or ambiguous',parameter=list(pk))
            return self.existing_type(matches[0],path)
        owners=[(pk,pe) for pk,pe in self.elements.items() if pk[1]=='Variable'
                and any(self.ref_key(c,pk)==key for c in pe.findall('Value'))]
        if len(owners)==1:return self.typ(self.doc,owners[0][0],owners[0][1],'VariableType')
        return None

    def owner_scope(self,key,seen=None):
        seen=seen or set()
        if key in seen:return None
        if key[1] in {'Trigger','FunctionDef'}:return key
        for pk,pe in self.elements.items():
            if any(self.ref_key(c,pk)==key and c.tag in {'FunctionCall','Action','Condition','Event','Parameter','Variable','Value','Array'} for c in pe):
                scope=self.owner_scope(pk,seen|{key})
                if scope:return scope
        return None

    def queue_parameter_check(self,key,path):
        self.recheck_parameters[key]=path
        for parent,call in self.elements.items():
            if parent[1]=='FunctionCall' and any(self.ref_key(c,parent)==key for c in call.findall('Parameter')):
                for c in call.findall('Parameter'):self.recheck_parameters.setdefault(self.ref_key(c,parent),path)

    def check_parameter_edits(self):
        # sameas constraints are checked against the final atomic batch, not an intermediate edit.
        for key,path in self.recheck_parameters.items():
            if key not in self.elements:continue
            self.current_scope=self.owner_scope(key)
            scope=self.elements.get(self.current_scope)
            self.return_type=self.typ(self.doc,self.current_scope,scope,'ReturnType') if scope is not None else None
            e=self.elements[key];actual=self.existing_type(key,path);expected=self.parameter_expected(key,path)
            if actual=='void':fail(path,'void action cannot be used as expression')
            if expected=='anyvariable' and e.find('Variable') is None:fail(path,'assignment target must be a variable')
            self.expect(actual,expected,path)
            for c in e:
                if c.tag in {'Variable','Parameter'}:self.check_scope(self.ref_key(c,key),path)
            pd=e.find('ParameterDef');game=e.find('ValueGameType')
            if pd is not None and game is not None:
                _,_,pe=self.resolve(list(self.ref_key(pd,key)),'ParamDef',path)
                required=pe.find('ParameterType/GameType')
                if required is not None and game.get('Type')!=required.get('Value'):
                    fail(path+'.game_type','game link catalog mismatch',expected=required.get('Value'),actual=game.get('Type'))
        self.current_scope=None;self.return_type=None

    def review_node(self,key,depth=3,seen=None):
        """Bounded source-derived labels for review; never interpret unknown executable XML."""
        key=tuple(key);seen=seen or set()
        if key in seen:return {'reference':list(key),'summary':'cyclic '+key[1]+' '+key[2],'summary_truncated':True}
        seen=seen|{key};d=self.doc;e=self.elements.get(key,self.roots.get(key))
        if e is None:
            try:d,e=self.target.resolve(key,self.doc)
            except ValueError:return {'reference':list(key),'summary':key[1]+' '+key[2],'summary_truncated':True}
        name=self.display_names.get(key) or e.findtext('Identifier')
        if not name:name=d.name(key) if key in d.elements else key[1]
        truncated=False;data={'reference':list(key)}
        if key[1]=='FunctionCall' and e.find('FunctionDef') is not None:
            definition=self.ref_key(e.find('FunctionDef'),key)
            name=self.review_node(definition,0,seen)['summary'];data['definition']=list(definition)
            args=[];params=e.findall('Parameter')
            if depth:
                for c in params[:6]:
                    pk=self.ref_key(c,key);param=self.elements.get(pk)
                    slot=param.find('ParameterDef') if param is not None else None
                    label=self.review_node(self.ref_key(slot,pk),0,seen)['summary']+'=' if slot is not None else ''
                    value=self.review_node(pk,depth-1,seen);args.append(label+value['summary']);truncated|=value.get('summary_truncated',False)
            truncated|=len(params)>6 or bool(params and not depth)
            name+='('+', '.join(args)+(', ...' if len(params)>6 else '...' if params and not depth else '')+')'
        elif key[1]=='Param':
            refs=[c for c in e if c.tag in {'Variable','Parameter','Preset','FunctionCall'}]
            if refs:
                child=self.review_node(self.ref_key(refs[0],key),depth,seen)
                name=child['summary'];truncated=child.get('summary_truncated',False)
            else:
                value=e.findtext('Value');region=e.find('ValueId')
                name='region '+region.get('Id','') if region is not None else self.strings.get(value,value) if value is not None else name
        elif key[1]=='PresetValue':name=e.findtext('Identifier') or d.name(key) or e.findtext('Value') or name
        data.update(summary=str(name)[:240],summary_truncated=truncated or len(str(name))>240)
        if e.find('Disabled') is not None:data['disabled']=True
        return data

    def creation_reviews(self):
        result=[]
        for field in ('declarations','triggers'):
            for i,item in enumerate(self.spec.get(field,[])):
                key=self.names[item['key']]
                if key not in self.elements:continue
                e=self.elements[key]
                impact={'spec_path':f'{field}[{i}]','operation':'create','id_policy':'allocated',
                        'before':[],'after':[self.review_node(key)],'roles':{},'preserves_unselected_nodes':True}
                parents=[pk for pk,pe in {**self.elements,**self.roots}.items() if pe is not None
                         and any(self.ref_key(c,pk)==key for c in pe.findall('Item'))]
                if len(parents)==1:impact['parent']=self.review_node(parents[0])
                if key[1]=='Variable':
                    impact['type']=self.typ(self.doc,key,e,'VariableType')
                    if e.find('Value') is not None:impact['initial']=self.review_node(self.ref_key(e.find('Value'),key))
                if key[1] in {'Trigger','FunctionDef'}:
                    for role,tag in [('events','Event'),('conditions','Condition'),('actions','Action' if key[1]=='Trigger' else 'FunctionCall'),('locals','Variable'),('parameters','Parameter')]:
                        children=[self.ref_key(c,key) for c in e.findall(tag)]
                        nodes=[self.review_node(k) for k in children[:40]]
                        impact['roles'][role]={'nodes':nodes,'count':len(children),
                            'truncated':len(children)>40 or any(n.get('summary_truncated') for n in nodes)}
                result.append(impact)
        return result

    def clone_default(self,d,key,path):
        # Clone mutable instances; reusable definitions and declarations keep exact references.
        new=self.alloc(key[1],path);e=copy.deepcopy(d.elements[key]);e.set('Id',new[2])
        for i,c in enumerate(list(e)):
            if c.get('Type') in {'Param','FunctionCall'}:
                ck=self.ref_key(c,key);cd,_=self.target.resolve(ck,d)
                c.attrib=reference(c.tag,self.clone_default(cd,ck,path+'.default['+str(i)+']')).attrib
        vt=e.find('ValueType')
        if key[1]=='Param' and vt is not None and vt.get('Type')=='text' and e.find('Value') is None:
            old_anchor='Param/Value/'+(f'lib_{key[0]}_' if key[0] else '')+key[2]
            strings=d.component/(self.spec.get('locale','zhCN')+'.SC2Data/LocalizedData/GameStrings.txt')
            value=''
            if strings.is_file():
                for line in strings.read_text('utf-8-sig').splitlines():
                    if line.startswith(old_anchor+'='):value=line.split('=',1)[1];break
            anchor='Param/Value/'+(f'lib_{new[0]}_' if new[0] else '')+new[2]
            self.strings[anchor]=value;ET.SubElement(e,'Value').text=anchor
        self.elements[new]=e
        return new

    def call(self,value,path,expression=False,event=False):
        fields(value,'call arguments branches disabled',path)
        d,k,f=self.resolve(value.get('call'),'FunctionDef',path+'.call')
        if event and f.find('FlagEvent') is None:fail(path,'definition is not an event',definition=list(k))
        if not event and f.find('FlagEvent') is not None:fail(path,'event only allowed in events list')
        typ=self.typ(d,k,f,'ReturnType') if f.find('ReturnType') is not None else 'void'
        if expression and typ=='void':fail(path,'void action cannot be used as expression')
        slots=[]
        for c in f.findall('Parameter'):
            if c.get('Type')!='ParamDef':continue
            pk=self.ref_key(c,k)
            if pk in self.elements:pd,pe=self.doc,self.elements[pk]
            else:pd,pe=self.target.resolve(pk,d)
            slots.append((pd,pk,pe))
        args=value.get('arguments',{});bound={}
        if isinstance(args,list):
            for i,a in enumerate(args):
                fields(a,'slot value',path+'.arguments['+str(i)+']')
                pk=tuple(a['slot'])
                if pk in bound:fail(path+'.arguments','duplicate argument',slot=list(pk))
                bound[pk]=(a['value'],path+'.arguments['+str(i)+'].value')
        elif isinstance(args,dict):
            for name,v in args.items():
                matches=[pk for pd,pk,pe in slots if name in {pe.findtext('Identifier'),pd.name(pk) if pk in pd.elements else None}]
                if len(matches)!=1:fail(path+'.arguments.'+name,'parameter slot missing or ambiguous',candidates=[list(pk) for _,pk,_ in slots])
                bound[matches[0]]=(v,path+'.arguments.'+name)
        else:fail(path+'.arguments','arguments must be a slot/value list or unique parameter names')
        if set(bound)-{pk for _,pk,_ in slots}:fail(path+'.arguments','foreign parameter slot')
        key=self.alloc('FunctionCall',path);e=self.elements[key];e.append(reference('FunctionDef',k));types={}
        for pd,pk,pe in slots:
            raw=pe.find('ParameterType/Type');expected=raw.get('Value') if raw is not None else None
            if expected=='sameas':expected=types.get(self.ref_key(pe.find('ParameterType/TypeElement'),pk))
            elif expected=='return':expected=self.return_type
            elif expected not in {'anyvariable','anycompare','any'}:expected=self.typ(pd,pk,pe,'ParameterType')
            if pk in bound:
                v,vpath=bound[pk]
                if raw is not None and raw.get('Value')=='anyvariable' and not (isinstance(v,dict) and 'var' in v):fail(vpath,'assignment target must be a variable')
                param,actual=self.param(v,vpath,pk,expected)
                game_type=pe.find('ParameterType/GameType')
                if game_type is not None and isinstance(v,dict) and v.get('type')=='gamelink' and v.get('game_type')!=game_type.get('Value'):
                    fail(vpath+'.game_type','game link catalog mismatch',expected=game_type.get('Value'),actual=v.get('game_type'))
            else:
                default=pe.find('Default')
                if default is None:fail(path+'.arguments','missing required parameter',expected_parameter=list(pk),function=list(k))
                dk=self.ref_key(default,pk);dd,_=self.target.resolve(dk,pd)
                param=self.clone_default(dd,dk,path+'.defaults.'+pk[2]);actual=expected
                existing=self.elements[param].find('ParameterDef')
                if existing is not None:self.elements[param].remove(existing)
                self.elements[param].insert(0,reference('ParameterDef',pk))
            types[pk]=actual;e.append(reference('Parameter',param))
        roles={}
        for c in f.findall('SubFunctionType'):
            sk=self.ref_key(c,k);_,se=self.target.resolve(sk,d);roles[se.findtext('Identifier')]=(sk,se.find('Condition') is not None)
        for role,actions in value.get('branches',{}).items():
            if role not in roles:fail(path+'.branches.'+role,'unsupported branch role',candidates=list(roles))
            sk,condition=roles[role]
            for i,action in enumerate(actions):
                child=self.behavior(action,path+'.branches.'+role+'['+str(i)+']',condition=condition)
                self.elements[child].append(reference('SubFunctionType',sk));e.append(reference('FunctionCall',child))
        if value.get('disabled'):ET.SubElement(e,'Disabled')
        return key,typ

    def behavior(self,value,path,condition=False,event=False):
        if not isinstance(value,dict):fail(path,'behavior must be an object')
        if 'set' in value:
            fields(value,'set value',path)
            _,key,ve=self.resolve(value['set'],'Variable',path+'.set');self.check_scope(key,path)
            _,fkey,f=self.resolve('SetVariable','FunctionDef',path)
            slots=[self.ref_key(c,fkey) for c in f.findall('Parameter') if c.get('Type')=='ParamDef']
            value={'call':list(fkey),'arguments':[{'slot':list(slots[0]),'value':{'var':list(key)}},{'slot':list(slots[1]),'value':value['value']}]}
            self.path_aliases.update({path+'.arguments[0].value':path+'.set',path+'.arguments[1].value':path+'.value'})
            # Preserve the public request path for assignment value diagnostics.
            self.expect(self.expression_type(value['arguments'][1]['value'],path+'.value'),self.typ(self.doc,key,ve,'VariableType'),path+'.value')
        elif 'if' in value:
            fields(value,'if then else',path)
            single=not isinstance(value['if'],list)
            value={'call':'IfThenElse','branches':{'if':value['if'] if isinstance(value['if'],list) else [value['if']], 'then':value.get('then',[]),'else':value.get('else',[])}}
            self.path_aliases.update({path+'.branches.'+role:path+'.'+role for role in ['if','then','else']})
            if single:self.path_aliases[path+'.branches.if[0]']=path+'.if'
        elif 'while' in value:
            fields(value,'while actions',path)
            single=not isinstance(value['while'],list)
            value={'call':'While','branches':{'Conditions':value['while'] if isinstance(value['while'],list) else [value['while']], 'Actions':value.get('actions',[])}}
            self.path_aliases.update({path+'.branches.Conditions':path+'.while',path+'.branches.Actions':path+'.actions'})
            if single:self.path_aliases[path+'.branches.Conditions[0]']=path+'.while'
        elif 'return' in value:
            fields(value,'return',path)
            if self.return_type in {None,'void'}:fail(path,'value return requires a value-returning function')
            value={'call':'Return','arguments':{'val':value['return']}}
            self.path_aliases[path+'.arguments.val']=path+'.return'
        if 'compare' in value or 'arithmetic' in value:
            result,typ=self.expression(value,path,'bool' if condition else None)
            return tuple([result[0].get('Library',''),result[0].get('Type'),result[0].get('Id')])
        key,typ=self.call(value,path,expression=condition,event=event)
        if condition:self.expect(typ,'bool',path)
        return key

    def declare(self,item,path,owner=None):
        fields(item,'kind key name type initial category parameters locals actions returns',path)
        kind={'category':'Category','variable':'Variable','action':'FunctionDef','function':'FunctionDef','parameter':'ParamDef'}.get(item.get('kind'))
        if not kind or not isinstance(item.get('key'),str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',item['key']):fail(path,'declaration needs a supported kind and an ASCII identifier key')
        name=item['key']
        if name in self.names:fail(path+'.key','duplicate request local name')
        key=self.alloc(kind,path);self.names[name]=key;self.display_names[key]=item.get('name',name)
        if owner:self.scopes[key]=owner
        if kind!='Category':ET.SubElement(self.elements[key],'Identifier').text=name
        if kind in {'Variable','ParamDef'}:
            self.elements[key].append(self.type_node(item['type'],'VariableType' if kind=='Variable' else 'ParameterType',path+'.type'))
        return key

    def build(self):
        declarations=self.spec.get('declarations',[]);triggers=self.spec.get('triggers',[])
        for i,item in enumerate(declarations):self.declare(item,'declarations['+str(i)+']')
        for i,item in enumerate(triggers):
            fields(item,'key name category events conditions actions locals disabled',f'triggers[{i}]')
            self.declare({'kind':'action','key':item['key'],'name':item.get('name',item['key'])},f'triggers[{i}]')
            old=self.names[item['key']];new=(old[0],'Trigger',old[2]);self.elements[new]=self.elements.pop(old);self.elements[new].set('Type','Trigger');self.names[item['key']]=new;self.display_names[new]=self.display_names.pop(old);self.node_map[f'triggers[{i}]']=list(new)
            self.instances[f'triggers[{i}]']=[list(new)]
        for i,item in enumerate(declarations):
            path=f'declarations[{i}]';key=self.names[item['key']];e=self.elements[key]
            if key[1]=='FunctionDef':
                ET.SubElement(e,'FlagCall' if item['kind']=='function' else 'FlagAction')
                if item['kind']=='function':e.append(self.type_node(item['returns'],'ReturnType',path+'.returns'))
                self.prepare_body(item,path,key)
        for i,item in enumerate(triggers):self.prepare_body(item,f'triggers[{i}]',self.names[item['key']])
        for i,item in enumerate(declarations):
            path=f'declarations[{i}]';key=self.names[item['key']];e=self.elements[key]
            if key[1]=='Variable' and 'initial' in item:
                p,_=self.param(item['initial'],path+'.initial',expected=self.typ(self.doc,key,e,'VariableType'));e.append(reference('Value',p))
            if key[1]=='FunctionDef':self.function_body(item,path,key)
        for i,item in enumerate(triggers):
            path=f'triggers[{i}]';key=self.names[item['key']];e=self.elements[key]
            self.function_body(item,path,key)
            if item.get('disabled'):ET.SubElement(e,'Disabled')
        for key in list(self.display_names):
            if key in self.scopes:continue
            item=next((v for v in declarations+triggers if self.names[v['key']]==key),None)
            if item and item.get('category'):
                _,parent,_=self.resolve(item['category'],'Category','category');self.elements[parent].append(reference('Item',key))
            else:
                rkey=(self.library,'Root','')
                if self.roots.get(rkey) is None:self.roots[rkey]=ET.Element('Root')
                self.roots[rkey].append(reference('Item',key))
        for i,edit in enumerate(self.spec.get('edits',[])):self.edit(edit,f'edits[{i}]')
        self.check_parameter_edits()
        return self.finish()

    def prepare_body(self,item,path,key):
        e=self.elements[key];self.current_scope=key
        for field,tag in [('parameters','Parameter'),('locals','Variable')]:
            for i,declaration in enumerate(item.get(field,[])):
                dp=path+f'.{field}[{i}]';declaration={**declaration,'kind':'parameter' if field=='parameters' else 'variable'}
                child=self.declare(declaration,dp,key);e.append(reference(tag,child))
        self.current_scope=None

    def function_body(self,item,path,key):
        e=self.elements[key];self.current_scope=key
        self.return_type=self.typ(self.doc,key,e,'ReturnType') if e.find('ReturnType') is not None else 'void'
        for i,declaration in enumerate(item.get('locals',[])):
            if 'initial' in declaration:
                child=self.names[declaration['key']];ce=self.elements[child]
                p,_=self.param(declaration['initial'],path+f'.locals[{i}].initial',expected=self.typ(self.doc,child,ce,'VariableType'));ce.append(reference('Value',p))
        for field,tag in [('events','Event'),('conditions','Condition'),('actions','Action' if key[1]=='Trigger' else 'FunctionCall')]:
            for i,value in enumerate(item.get(field,[])):
                child=self.behavior(value,path+f'.{field}[{i}]',condition=field=='conditions',event=field=='events');e.append(reference(tag,child))
        self.current_scope=None;self.return_type=None

    def edit(self,edit,path):
        fields(edit,'op target parent role index behaviors behavior expression order',path)
        op=edit.get('op')
        contracts={'insert':('parent role behaviors','index'),'replace_branch':('parent role behaviors',''),
                   'reorder':('parent role order',''),'replace':('target','behavior expression'),
                   'move':('target parent role','index'),'delete':('target','')}
        if op not in contracts:fail(path+'.op','unsupported edit operation',candidates=list(contracts))
        required,optional=contracts[op]
        for field in required.split():
            if field not in edit:fail(path+'.'+field,'missing required edit field')
        for field in edit:
            if field not in ('op '+required+' '+optional).split():fail(path+'.'+field,'field is not used by this edit operation')
        for field in ('behaviors','order'):
            if field in edit and not isinstance(edit[field],list):fail(path+'.'+field,'expected an ordered list')
        if 'index' in edit and type(edit['index']) is not int:fail(path+'.index','index must be an integer')
        impact={'spec_path':path,'operation':op,'preserves_unselected_nodes':True,
                'id_policy':'preserved' if op in {'replace','reorder','move'} else 'deleted' if op=='delete' else 'allocated'}
        def review(stage,keys):
            keys=list(keys);impact[stage]=[self.review_node(k) for k in keys[:40]]
            impact[stage+'_count']=len(keys)
            impact[stage+'_truncated']=len(keys)>40 or any(n.get('summary_truncated') for n in impact[stage])
        def local(ref):
            key=tuple(ref) if isinstance(ref,list) and len(ref)==3 else self.names.get(ref) if isinstance(ref,str) else None
            if key not in self.elements and key not in self.roots:fail(path,'edit target must be an exact local reference',reference=ref)
            if key[0]!=self.library:fail(path,'cross-library migration is unsupported')
            return key
        def element(key):return self.roots[key] if key[1]=='Root' else self.elements[key]
        def group(parent,role):
            e=element(parent)
            tags={'actions':'Action' if parent[1]=='Trigger' else 'FunctionCall','conditions':'Condition','events':'Event','items':'Item'}
            if parent[1]=='FunctionCall':
                fref=e.find('FunctionDef');d,k,f=self.resolve(list(self.ref_key(fref,parent)),'FunctionDef',path)
                roles={}
                for c in f.findall('SubFunctionType'):
                    sk=self.ref_key(c,k);_,se=self.target.resolve(sk,d);roles[se.findtext('Identifier')]=(sk,se.find('Condition') is not None)
                if role not in roles:fail(path+'.role','unsupported branch role',candidates=list(roles))
                sk,condition=roles[role]
                selected=[c for c in e.findall('FunctionCall') if self.ref_key(self.elements[self.ref_key(c,parent)].find('SubFunctionType'),self.ref_key(c,parent))==sk]
                return selected,'FunctionCall',sk,condition
            allowed={'Root':{'items'},'Category':{'items'},'Trigger':{'events','conditions','actions'},'FunctionDef':{'actions'}}
            if role not in allowed.get(parent[1],set()):fail(path+'.role','invalid parent/role',candidates=sorted(allowed.get(parent[1],set())))
            return e.findall(tags[role]),tags[role],None,role=='conditions'
        owner_scope=self.owner_scope
        if op in {'insert','replace_branch','reorder'}:
            parent=local(edit.get('parent'));e=element(parent);selected,tag,subtype,condition=group(parent,edit.get('role'))
            impact.update(parent=self.review_node(parent),role=edit['role'])
            review('before',[self.ref_key(c,parent) for c in selected])
            self.current_scope=owner_scope(parent)
            self.return_type=self.typ(self.doc,self.current_scope,element(self.current_scope),'ReturnType') if self.current_scope else None
            if op=='reorder':
                order=[local(r) for r in edit.get('order',[])]
                old=[self.ref_key(c,parent) for c in selected]
                if len(order)!=len(old) or set(order)!=set(old):fail(path+'.order','order must contain each selected child exactly once')
                positions=[list(e).index(c) for c in selected]
                for c in selected:e.remove(c)
                for i,k in zip(positions,order):e.insert(i,reference(tag,k))
            else:
                index=edit.get('index',len(selected))
                if not isinstance(index,int) or not 0<=index<=len(selected):fail(path+'.index','invalid role-relative insertion index')
                offset=list(e).index(selected[index]) if index<len(selected) else list(e).index(selected[-1])+1 if selected else len(e)
                old=[self.ref_key(c,parent) for c in selected] if op=='replace_branch' else []
                if op=='replace_branch':
                    offset=list(e).index(selected[0]) if selected else len(e)
                    for c in selected:e.remove(c)
                for i,b in enumerate(edit.get('behaviors',[])):
                    child=self.behavior(b,path+f'.behaviors[{i}]',condition,edit.get('role')=='events')
                    if subtype:self.elements[child].append(reference('SubFunctionType',subtype))
                    e.insert(offset+i,reference(tag,child))
                self.prune(old,path)
            review('after',[self.ref_key(c,parent) for c in group(parent,edit['role'])[0]])
            self.current_scope=None
        elif op=='replace':
            key=local(edit.get('target'));e=element(key);self.current_scope=owner_scope(key)
            impact.update(target=list(key),role='expression' if key[1]=='Param' else 'call');review('before',[key])
            self.return_type=self.typ(self.doc,self.current_scope,element(self.current_scope),'ReturnType') if self.current_scope else None
            if key[1]=='FunctionCall':
                if 'behavior' not in edit:fail(path+'.behavior','call replacement requires behavior')
                if 'expression' in edit:fail(path+'.expression','call replacement uses behavior')
                self.known_instance(key,path)
                old=[self.ref_key(c,key) for c in e if c.get('Type') in {'Param','FunctionCall'}]
                links=[c for pk,pe in self.elements.items() for c in pe if self.ref_key(c,pk)==key]
                condition=any(c.tag=='Condition' for c in links)
                subtype=e.find('SubFunctionType')
                if subtype is not None:
                    _,se=self.target.resolve(self.ref_key(subtype,key),self.doc)
                    condition=condition or se.find('Condition') is not None
                replacement=self.behavior(edit['behavior'],path+'.behavior',condition=condition,event=any(c.tag=='Event' for c in links))
                new=self.reuse_instance(replacement,key)
                for pk,pe in self.elements.items():
                    if pk[1]=='Param' and any(c.tag=='FunctionCall' and self.ref_key(c,pk)==key for c in pe):self.queue_parameter_check(pk,path+'.behavior')
                if e.find('SubFunctionType') is not None:new.append(copy.deepcopy(e.find('SubFunctionType')))
                if e.find('Disabled') is not None and not ('disabled' in edit['behavior']) and new.find('Disabled') is None:ET.SubElement(new,'Disabled')
                self.node_map[path+'.behavior']=list(key);self.prune(old,path)
            elif key[1]=='Param':
                if 'expression' not in edit:fail(path+'.expression','parameter replacement requires expression')
                if 'behavior' in edit:fail(path+'.behavior','parameter replacement uses expression')
                self.known_instance(key,path)
                old=[self.ref_key(c,key) for c in e if c.get('Type') in {'Param','FunctionCall'}]
                pd=e.find('ParameterDef');expected=None
                if pd is not None:
                    d,pk,pe=self.resolve(list(self.ref_key(pd,key)),'ParamDef',path)
                    raw=pe.find('ParameterType/Type')
                    if raw is None or raw.get('Value')!='sameas':expected=self.parameter_expected(key,path+'.expression')
                    if expected=='anyvariable' and not (isinstance(edit['expression'],dict) and 'var' in edit['expression']):fail(path+'.expression','assignment target must be a variable')
                else:expected=self.parameter_expected(key,path+'.expression')
                replacement,_=self.param(edit['expression'],path+'.expression',self.ref_key(pd,key) if pd is not None else None,expected)
                self.reuse_instance(replacement,key);self.node_map[path+'.expression']=list(key);self.prune(old,path)
                self.queue_parameter_check(key,path+'.expression')
            else:fail(path,'replace supports a call or parameter expression')
            review('after',[key])
            self.current_scope=None
        elif op=='move':
            key=local(edit.get('target'));parent=local(edit.get('parent'));e=element(parent)
            selected,tag,subtype,condition=group(parent,edit.get('role'))
            if key==parent:fail(path,'cannot move a node into itself')
            if parent in self.closure([key]):fail(path,'cannot move a call into its own subtree')
            if tag=='Item' and key[1]!='Trigger':fail(path,'category moves support triggers only')
            if tag!='Item' and key[1]!='FunctionCall':fail(path,'body moves support call instances only')
            owners=[(pk,pe,c) for pk,pe in {**self.elements,**self.roots}.items() if pe is not None for c in pe if c.tag in {'Item','Action','Condition','Event','FunctionCall'} and self.ref_key(c,pk)==key]
            if len(owners)!=1:fail(path,'moving requires exactly one owning reference',references=[list(pk) for pk,_,_ in owners])
            impact.update(target=list(key),role=edit['role'],from_parent=self.review_node(owners[0][0]),to_parent=self.review_node(parent))
            review('before',[key])
            if tag!='Item':
                cd,ck,ce=self.resolve(list(self.ref_key(self.elements[key].find('FunctionDef'),key)),'FunctionDef',path)
                if condition:self.expect(self.typ(cd,ck,ce,'ReturnType'),'bool',path)
                if (ce.find('FlagEvent') is not None)!=(edit.get('role')=='events'):fail(path,'event/body move role mismatch')
                for ck in self.closure([key]):
                    if ck[1]=='Param':self.queue_parameter_check(ck,path)
                self.known_instance(key,path)
                child=self.elements[key];oldsub=child.find('SubFunctionType')
                if oldsub is not None:child.remove(oldsub)
                if subtype:child.append(reference('SubFunctionType',subtype))
            owners[0][1].remove(owners[0][2]);selected=[c for c in selected if c in list(e)]
            index=edit.get('index',len(selected))
            if not isinstance(index,int) or not 0<=index<=len(selected):fail(path+'.index','invalid role-relative index')
            offset=list(e).index(selected[index]) if index<len(selected) else list(e).index(selected[-1])+1 if selected else len(e)
            e.insert(offset,reference(tag,key))
            review('after',[key])
        elif op=='delete':
            key=local(edit.get('target'))
            impact['target']=list(key);review('before',[key])
            if key[1] not in {'FunctionCall','Param','Variable','FunctionDef','Trigger','Category'}:fail(path,'unsupported delete kind')
            if key[1]=='Category' and element(key).find('Item') is not None:fail(path,'cannot delete a non-empty category')
            # Detach only the unique owning declaration/body link. Value/call references remain blockers.
            tags={'Item','Action','Condition','Event','FunctionCall'} if key[1]!='Param' else set()
            for pk,pe in {**self.elements,**self.roots}.items():
                if pe is None:continue
                for c in list(pe):
                    declaration=key[1]=='Variable' and pk[1] in {'Trigger','FunctionDef'} and c.tag=='Variable'
                    if (c.tag in tags or declaration) and self.ref_key(c,pk)==key:pe.remove(c)
            self.prune([key],path)
            review('after',[])
        else:fail(path+'.op','unsupported edit operation')
        self.impacts.append(impact)

    def known_instance(self,key,path):
        allowed={'FunctionCall':{'FunctionDef','Parameter','FunctionCall','SubFunctionType','Disabled','Comment'},
                 'Param':{'ParameterDef','Value','ValueType','ValueId','Variable','Parameter','Preset','FunctionCall','ValueElement','ValueGameType','ValueContext','Array','CustomType','ScriptCode','ValueTypeInfo'}}
        e=self.elements[key];unknown={c.tag for c in e}-allowed.get(key[1],set())
        if unknown:fail(path,'selected instance contains unknown XML; cannot rewrite',reference=list(key),fields=sorted(unknown))
        if key[1]!='Param':return
        for c in e.findall('Array'):
            if set(c.attrib)not in ({'Type','Id'},{'Type','Id','Library'}) or c.get('Type')!='Param' or not re.fullmatch(r'[0-9A-Fa-f]{8}',c.get('Id','')) or ('Library' in c.attrib and not re.fullmatch(r'[A-Za-z0-9_]+',c.get('Library',''))) or len(c) or (c.text and c.text.strip()):
                fail(path,'unsupported legacy array; cannot rewrite',reference=list(key),fields=['Array'])
        if e.find('CustomType') is not None or e.find('ScriptCode') is not None:
            types=e.findall('CustomType');scripts=e.findall('ScriptCode')
            if len(types)!=1 or len(scripts)!=1 or dict(types[0].attrib)!={'Type':'filepath'} or len(types[0]) or (types[0].text and types[0].text.strip()) or \
               scripts[0].attrib or len(scripts[0]) or (scripts[0].text or '').strip()!='""' or {c.tag for c in e}-{'ParameterDef','CustomType','ScriptCode'}:
                fail(path,'unsupported legacy custom type; cannot rewrite',reference=list(key),fields=['CustomType'])
        if e.find('ValueTypeInfo') is not None:
            infos=e.findall('ValueTypeInfo');types=e.findall('ValueType')
            if len(infos)!=1 or dict(infos[0].attrib)!={'Value':'5'} or len(infos[0]) or (infos[0].text and infos[0].text.strip()) or \
               len(types)!=1 or dict(types[0].attrib)!={'Type':'filepath'} or len(types[0]) or (types[0].text and types[0].text.strip()):
                fail(path,'unsupported legacy value type info; cannot rewrite',reference=list(key),fields=['ValueTypeInfo'])
        self.known_context(key,path)

    def known_context(self,key,path):
        # CatalogFieldValueGet keeps exactly '<ValueContext Value="CAbilTrain"/>' beside a catalogfieldpath value type.
        # Legacy user literals keep one printable-ASCII '<ValueContext Value="..."/>' beside a userfield/userinstance value type.
        e=self.elements[key];nodes=[c for c in e if c.tag=='ValueContext']
        if len(nodes)>1:fail(path,'parameter has repeated value contexts; cannot rewrite',reference=list(key),fields=['ValueContext'])
        if not nodes:return
        ctx=nodes[0];types=[c for c in e if c.tag=='ValueType']
        if list(ctx) or (ctx.text and ctx.text.strip()) or set(ctx.attrib)!={'Value'}:
            fail(path,'unsupported value context; cannot rewrite',reference=list(key),fields=['ValueContext'])
        if ctx.get('Value')=='CAbilTrain' and len(types)==1 and dict(types[0].attrib)=={'Type':'catalogfieldpath'} and not len(types[0]) and not (types[0].text and types[0].text.strip()):return
        if not ctx.get('Value','').strip() or not re.fullmatch(r'[ \x21-\x7e]+',ctx.get('Value','')) or len(types)!=1 or dict(types[0].attrib)not in ({'Type':'userfield'},{'Type':'userinstance'}) or len(types[0]) or (types[0].text and types[0].text.strip()):
            fail(path,'value context is not a supported legacy user literal or catalog field path',reference=list(key),fields=['ValueContext'])

    def closure(self,keys):
        pending=list(keys);found=set()
        from sc2_triggers import references
        while pending:
            key=pending.pop()
            if key in found or key not in self.elements:continue
            found.add(key)
            pending.extend(r for r in references(self.elements[key],key) if r[1] in {'FunctionCall','Param'} or
                           (key[1] in {'FunctionDef','Trigger'} and r[1] in {'Variable','ParamDef'}))
        return found

    def prune(self,keys,path):
        from sc2_triggers import references
        removing=self.closure(keys);incoming=[]
        containers=[(self.doc,k,e) for k,e in {**self.elements,**self.roots}.items()]
        containers.extend((d,k,e) for d in self.target.documents if d is not self.doc for k,e in d.elements.items())
        for d,key,e in containers:
            if e is None:continue
            if d is self.doc and key in removing:continue
            for r in references(e,key):
                if r in removing and (r[0] or d is self.doc):incoming.append({'source':str(d.path),'reference':list(key),'target':list(r)})
        if incoming:fail(path,'selected nodes are still referenced',references=incoming)
        for key in removing:
            if key[1] in {'FunctionCall','Param'}:self.known_instance(key,path)
            self.elements.pop(key);self.deleted.add(key)

    def finish(self):
        ops=[]
        live_anchors={e.findtext('Value') for k,e in self.elements.items() if k[1]=='Param'}
        self.strings={anchor:value for anchor,value in self.strings.items() if anchor in live_anchors}
        registered={self.ref_key(c,k) for k,e in self.roots.items() if e is not None for c in e.findall('Item')}
        for key,e in self.elements.items():
            if key in self.original:continue
            op={'library':key[0],'type':key[1],'id':key[2],'children':[child_data(c) for c in e], 'owner':False}
            if key in registered:op['owner']={'type':'Root'}
            if key in self.display_names:op['name']=self.display_names[key]
            ops.append(op)
        allocated=len(ops)
        if self.strings:
            if not ops:
                key=next(k for k,e in self.elements.items() if k[1]=='Param' and e.findtext('Value') in self.strings)
                ops.append({'library':key[0],'type':key[1],'id':key[2],'children':[child_data(c) for c in self.elements[key]],'owner':False})
            ops[0]['strings']=self.strings
        changes=plan_write(self.root,ops,locale=self.spec.get('locale','zhCN'))
        raw=changes.get('Triggers',(self.root/'Triggers').read_bytes());text=raw.decode('utf-8-sig');nl='\r\n' if '\r\n' in text else '\n'
        for key,e in self.elements.items():
            if key in self.original and ET.tostring(e)!=ET.tostring(self.original[key]):
                def replace(t):
                    found=_selected_elements(t,key)
                    if len(found)!=1:fail('edits','missing or ambiguous selected element',reference=list(key))
                    m=found[0]
                    return t[:m.start()]+rewrite_children(m.group(),e)+t[m.end():]
                text=_replace_container(text,key[0],replace)
        for key in self.deleted:
            def remove(t):
                for m in _selected_elements(t,key):
                    return t[:m.start()]+t[m.end():]
                return t
            text=_replace_container(text,key[0],remove)
        for key,e in self.roots.items():
            if e is None or (self.old_roots.get(key) is not None and ET.tostring(e)==ET.tostring(self.old_roots[key])):continue
            def replace_root(t):
                matches=_matches(r'<Root\b[^>]*?(?:/>|>.*?</Root>)',t)
                if len(matches)!=1:fail('edits','missing or ambiguous library root')
                m=matches[0]
                return t[:m.start()]+rewrite_children(m.group(),e)+t[m.end():]
            text=_replace_container(text,key[0],replace_root)
        result=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+text.encode()
        if result!=(self.root/'Triggers').read_bytes():changes['Triggers']=result
        node_map={self.public_path(p):key for p,key in self.node_map.items() if tuple(key) in self.elements}
        instances={}
        for p,refs in self.instances.items():
            live=[r for r in refs if tuple(r) in self.elements]
            if live:instances.setdefault(self.public_path(p),[]).extend(live)
        return {'changes':changes,'node_map':node_map,'instances':instances,'allocated_internal_ids':allocated,
                'impacts':self.creation_reviews()+self.impacts,'operations':ops}


def plan_author(root,spec,mods_dir=None):
    fields(spec,'version request_id expected_fingerprint library locale declarations triggers edits acceptance', 'spec')
    if spec.get('version')!=1 or not isinstance(spec.get('request_id'),str) or not 1<=len(spec['request_id'])<=128:
        fail('spec','version=1 and a stable request_id are required')
    target=target_for(root,mods_dir)
    if target.problems:fail('spec','dependency context incomplete',diagnostics=target.problems)
    before=fingerprint(target)
    if spec.get('expected_fingerprint')!=before:fail('expected_fingerprint','输入已变化，请重新读取目标节点',actual=before)
    builder=Author(root,target,spec)
    try:result=builder.build()
    except SC2Error as exc:
        if 'spec_path' in exc.details:exc.details['spec_path']=builder.public_path(exc.details['spec_path'])
        raise
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        fail('spec','invalid or unsupported request shape',reason=str(exc))
    target.refresh()
    if target.problems or fingerprint(target)!=before:fail('expected_fingerprint','规划期间输入变化，请重新读取目标节点')
    result.update(inputs=inputs(target),fingerprint=before)
    return result


def candidate_fingerprint(changes):
    return digest(json.dumps({k:digest(v) for k,v in changes.items()},sort_keys=True).encode())


def validate_candidate(service,project_id,root,planned,mods_dir):
    from .archives import _collect_export_members
    from .trigger_pipeline import generate,check_build
    from .storage import guard_absolute_path
    import shutil
    import uuid
    folder=guard_absolute_path(service.state/'trigger-author'/uuid.uuid4().hex/'Candidate.SC2Map')
    folder.mkdir(parents=True)
    members,_=_collect_export_members(root)
    for relative,source in members:
        # Generated scripts are never input to GUI regeneration and may be locked by Editor.
        if source.name.casefold()=='mapscript.galaxy' or re.fullmatch(r'Lib[0-9A-Fa-f]{8}(?:_h)?\.galaxy',source.name,re.I):continue
        target=safe_path(folder,relative);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for relative,raw in planned['changes'].items():
        p=safe_path(folder,relative);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    if any(safe_path(folder,k).read_bytes()!=v for k,v in planned['changes'].items()):fail('spec','candidate copy bytes differ')
    class CopyService:
        runtime_root=folder.parent/'runtime'
        def record(self,pid):return {},folder
    try:
        build=generate(CopyService(),project_id,mods_dir)
        checked=check_build(CopyService(),project_id,build['build_id'])
        if checked['status']!='static validation passed':
            raise SC2Error('trigger_author_validation','candidate Galaxy static check failed',diagnostics=checked)
    except SC2Error as exc:
        reverse={tuple(k):path for path,k in planned['node_map'].items()}
        reverse.update({tuple(k):path for path,keys in planned.get('instances',{}).items() for k in keys})
        diagnostics=exc.details.get('diagnostics',{})
        if isinstance(diagnostics,dict):
            for diagnostic in diagnostics.get('diagnostics',[]):
                node=tuple(diagnostic.get('gui',{}).get('node',[]))
                diagnostic['spec_path']=reverse.get(node,'spec')
        node=exc.details.get('call_site',{}).get('node',exc.details.get('node',[]))
        exc.details.setdefault('spec_path',reverse.get(tuple(node),'spec'))
        exc.details['request_nodes']=planned['node_map'];exc.details['copy']=str(folder)
        write_json(folder.parent/'failure.json',exc.as_dict())
        raise
    return {**checked,'copy':str(folder),'build':build,'candidate_fingerprint':candidate_fingerprint(planned['changes'])}


def author(service,project_id,spec,mode='preview',mods_dir=None,include_diff=False):
    from .storage import file_lock
    if mode not in {'preview','candidate'}:fail('mode','mode must be preview or candidate')
    _,root=service.record(project_id,write=mode=='candidate')
    request_hash=digest(json.dumps(spec,sort_keys=True,allow_nan=False).encode())
    receipt=service.state/'trigger-author-requests'/digest((project_id+'\0'+str(spec.get('request_id'))).encode())
    with file_lock(receipt.with_suffix('.lock')):
        if mode=='candidate' and receipt.with_suffix('.json').is_file():
            previous=json.loads(receipt.with_suffix('.json').read_text('utf-8'))
            if previous['request_hash']!=request_hash:fail('request_id','request_id already used with different content; choose a new request_id')
            manifest=service.transactions.read(previous['result']['change_id'])
            application=service.transactions.completed_application(manifest)
            if application:
                return {**previous['result'],'application':application,'reused':True}
            if fingerprint(target_for(root,mods_dir))!=spec.get('expected_fingerprint'):fail('expected_fingerprint','输入已变化，请重新读取目标节点')
            result={**previous['result'],'reused':True}
            if include_diff and result.get('diff_file'):result['diff_text']=Path(result['diff_file']).read_text('utf-8')
            return result
        planned=plan_author(root,spec,mods_dir)
        validation=validate_candidate(service,project_id,root,planned,mods_dir)
        if fingerprint(target_for(root,mods_dir))!=planned['fingerprint']:fail('expected_fingerprint','验证期间输入变化，请重新读取目标节点')
        diff=''.join(line for k,raw in planned['changes'].items() for line in difflib.unified_diff(
            (safe_path(root,k).read_text('utf-8-sig') if safe_path(root,k).is_file() else '').splitlines(True),
            raw.decode('utf-8-sig').splitlines(True),fromfile='before/'+k,tofile='after/'+k))
        diff_path=service.state/'trigger-author-diffs'/(request_hash+'.diff')
        from .storage import atomic_write
        atomic_write(diff_path,diff.encode('utf-8'))
        result={'project_id':project_id,'mode':mode,'node_map':planned['node_map'],'instances':planned['instances'],'impacts':planned['impacts'],
                'acceptance':spec.get('acceptance',[]),'candidate_fingerprint':validation['candidate_fingerprint'],
                'validation':validation,'diff_file':str(diff_path),'input_fingerprint':planned['fingerprint'],
                'behavior_summary':{'triggers':spec.get('triggers',[]),'declarations':spec.get('declarations',[]),'edits':spec.get('edits',[])},
                'efficiency':{'request_bytes':len(json.dumps(spec,ensure_ascii=False).encode()),
                              'low_level_bytes':len(json.dumps(planned['operations'],ensure_ascii=False).encode()),
                              'allocated_internal_ids':planned['allocated_internal_ids']}}
        if include_diff:result['diff_text']=diff
        if mode=='candidate':
            def planner(root,roots,context):
                if fingerprint(target_for(root,mods_dir))!=planned['fingerprint']:fail('expected_fingerprint','提交候选期间输入变化，请重新读取目标节点')
                return planned['changes']
            transaction=service.prepare_domain(project_id,'trigger_author',planner)
            result.update(transaction)
            result['validation']=validation
            if transaction.get('change_id'):
                manifest=service.transactions.read(transaction['change_id'])
                manifest['trigger_author']={'mods_dir':mods_dir,'input_fingerprint':planned['fingerprint'],
                                           'candidate_fingerprint':result['candidate_fingerprint'],'validation':validation}
                service.transactions._save(manifest)
                write_json(receipt.with_suffix('.json'),{'request_hash':request_hash,'result':result})
        return result


def guard_candidate(root,manifest,changes=None):
    evidence=manifest.get('trigger_author')
    if not evidence:return
    if fingerprint(target_for(root,evidence['mods_dir']))!=evidence['input_fingerprint']:
        fail('expected_fingerprint','已验证候选的输入发生变化，请重新读取目标节点')
    if changes is not None and candidate_fingerprint(changes)!=evidence['candidate_fingerprint']:
        fail('spec','candidate differs from the exact bytes that passed static validation')
