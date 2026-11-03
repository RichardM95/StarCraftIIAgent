"""Conservative offline GUI compiler. Unknown executable forms are errors."""
from __future__ import annotations
import json
import re
from .errors import SC2Error


class Generator:
    def __init__(self, target, external_libraries=(), bindings=None):
        self.target=target; self.lines=[]; self.source_map=[]; self.stack=set(); self.functions={}; self.variables={}
        self.external_libraries={'Ntve',*external_libraries}
        self.bindings = bindings
        self.parameter_scopes = []
        self.call_sites = []
        self.resource_inputs = {}

    def mapping(self):
        if self.bindings is None:
            from .trigger_pipeline import controlled_files
            from .trigger_bindings import Bindings
            files, _ = controlled_files(self.target, skip_generated=True)
            roots = [p for p in ('triggerlibs/natives.galaxy', 'triggerlibs/nativelib.galaxy') if p in files]
            self.bindings = Bindings(self.target, files, roots)
        return self.bindings

    def error(self, message, d, key):
        raise SC2Error('trigger_generation_unsupported',message,path=str(d.path),node=list(key))

    def emit(self, text, d, key):
        start=len(self.lines)+1
        self.lines.extend(text.splitlines() or [''])
        self.source_map.append({'start':start,'end':len(self.lines),'path':str(d.path),'node':list(key)})

    def resolve(self, ref, d, key):
        from sc2_triggers import ref_key
        if ref is None:self.error('missing reference',d,key)
        k=ref_key(ref,key)
        dd,e=self.target.resolve(k,d)
        return dd,k,e

    def symbol(self,d,key):
        e=d.elements[key]
        name=e.findtext('Identifier') or d.name(key) or key[2]
        name=re.sub('[^A-Za-z0-9_]','',name)
        if not name or name[0].isdigit():name='N'+name
        return ('lib'+key[0]+'_' if key[0] else '')+{'Variable':'gv_','ParamDef':'lp_','FunctionDef':'gf_','Trigger':'gt_'}.get(key[1],'v_')+name

    def typ(self,e,d,key,tag):
        container=e.find(tag)
        t=container.find('Type') if container is not None else None
        value=t.get('Value') if t is not None else 'void' if tag=='ReturnType' else None
        if not value or not re.fullmatch('[a-z]+',value):self.error('unsupported type',d,key)
        if container is not None and any(c.tag not in {'Type','TypeElement','GameType'} for c in container):self.error('unsupported array/reference type',d,key)
        mapped=self.mapping().type(e,d,key,tag)
        if not mapped:self.error('type has no resolved Galaxy representation',d,key)
        return mapped

    def expr(self,d,key,e):
        variants=[c for c in e if c.tag in {'FunctionCall','Variable','Parameter','Preset','ValueElement','Value'}]
        value_type=e.find('ValueType')
        value_id=e.find('ValueId')
        if value_id is not None and value_type is not None and value_type.get('Type')=='region':
            from .storage import digest,safe_path
            from xml.etree import ElementTree as ET
            path=safe_path(d.component,'Regions');ident=value_id.get('Id','')
            if not ident.isdigit() or not path.is_file():self.error('named region resource missing',d,key)
            raw=path.read_bytes()
            matches=[r for r in ET.fromstring(raw).findall('region') if r.get('id')==ident]
            if len(matches)!=1:self.error('named region ID missing or ambiguous',d,key)
            self.resource_inputs[str(path)]={'sha256':digest(raw),'kind':'Regions'}
            return self.mapping().bind('RegionFromId','region',['int'],[str(int(ident))],False,d,key,key)
        if not variants and value_type is not None and value_type.get('Type')=='text':
            anchor='Param/Value/'+(f'lib_{key[0]}_' if key[0] else '')+key[2]
            return 'StringExternal('+json.dumps(anchor)+')'
        if len(variants)!=1:self.error('ambiguous or unsupported parameter value',d,key)
        v=variants[0]
        if v.tag=='Value':
            t=e.find('ValueType'); t=t.get('Type') if t is not None else None; value=v.text or ''
            if t=='text':return 'StringExternal('+json.dumps(value)+')'
            if t in {'string','gamelink','anygamelink'}:return json.dumps(value,ensure_ascii=True)
            if t=='bool' and value in {'true','false'}:return value
            if t in {'int','byte','fixed'} and re.fullmatch(r'-?\d+(?:\.\d+)?',value):return value
            self.error('unsupported literal',d,key)
        dd,k,el=self.resolve(v,d,key)
        if k[1] == 'ParamDef':
            for scope in reversed(self.parameter_scopes):
                if (str(dd.path), k) in scope:
                    return scope[(str(dd.path), k)]
        if v.tag=='FunctionCall':return self.call(dd,k,el,False)
        if v.tag=='Preset':
            value=el.findtext('Value')
            if value is not None and value.startswith('"'):
                try:
                    literal=json.loads(value)
                    if isinstance(literal,str):return json.dumps(literal,ensure_ascii=True)
                except ValueError:pass
            if value is None or not re.fullmatch(r'-?\d+(?:\.\d+)?|[A-Za-z_]\w*|==|!=|<=|>=|<|>|\+|-|\*|/|%',value):self.error('unsupported preset',dd,k)
            return value
        if v.tag=='ValueElement' and k[1]!='Trigger':self.error('unsupported element value',dd,k)
        if k[1]=='Variable':self.variables[(str(dd.path),k)]=(dd,k,el)
        return self.symbol(dd,k)

    def param(self,ref,d,key):
        dd,k,e=self.resolve(ref,d,key)
        return self.expr(dd,k,e)

    def call(self,d,key,e,statement=True,event_trigger=None):
        if e.find('Disabled') is not None:return ''
        identity=(str(d.path),key)
        if identity in self.stack:self.error('recursive expression/call instance',d,key)
        self.stack.add(identity)
        self.call_sites.append((d.standard, {'path':str(d.path),'node':list(key)}))
        try:return self._call(d,key,e,statement,event_trigger)
        except SC2Error as exc:
            sites=[site for standard,site in self.call_sites if not standard]
            exc.details.setdefault('call_site',sites[-1] if sites else self.call_sites[-1][1])
            raise
        finally:
            self.stack.remove(identity)
            self.call_sites.pop()

    def _call(self,d,key,e,statement,event_trigger=None):
        unknown={c.tag for c in e}-{'FunctionDef','Parameter','FunctionCall','SubFunctionType','Disabled','ScriptCode','Comment'}
        if unknown:self.error('unsupported call fields: '+','.join(sorted(unknown)),d,key)
        dd,k,f=self.resolve(e.find('FunctionDef'),d,key)
        name=f.findtext('Identifier')
        if f.find('FlagCustomScript') is not None:
            code=e.findtext('ScriptCode')
            if code is None:self.error('missing Custom Script',d,key)
            return code
        args={}
        for p in e.findall('Parameter'):
            pd,pk,pe=self.resolve(p,d,key)
            definition=pe.find('ParameterDef')
            fd,fk,fe=self.resolve(definition,pd,pk)
            if fk in args:self.error('duplicate argument',d,key)
            args[fk]=self.expr(pd,pk,pe)
        values=[]
        definitions=[]
        scope={}
        for p in f.findall('Parameter'):
            if p.get('Type')=='Comment':continue
            pd,pk,pe=self.resolve(p,dd,k)
            if pk not in args:
                raise SC2Error('trigger_argument_missing','missing explicit argument',path=str(d.path),node=list(key),
                               function=name,definition=list(k),expected_parameter=list(pk),actual_parameters=[list(a) for a in args])
            values.append(args.pop(pk))
            definitions.append((pd,pk,pe))
            scope[(str(pd.path),pk)] = values[-1]
        if args:
            raise SC2Error('trigger_argument_foreign','foreign argument',path=str(d.path),node=list(key),
                           function=name,definition=list(k),actual_parameters=[list(a) for a in args])
        if f.find('FlagNative') is not None and f.find('FunctionCall') is not None:
            allowed={'Identifier','Label','Deprecated','FlagNative','FlagAction','FlagCall','FlagCondition','FlagEvent','ReturnType','Parameter','FunctionCall','Internal','Comment'}
            if any(child.tag not in allowed for child in f):self.error('unsupported compatibility template fields',d,key)
            children=f.findall('FunctionCall')
            if not statement and len(children)!=1:self.error('compatibility expression requires exactly one call',d,key)
            self.parameter_scopes.append(scope)
            try:
                output=[]
                for ref in children:
                    cd,ck,ce=self.resolve(ref,dd,k)
                    output.append(self.call(cd,ck,ce,statement,event_trigger))
            finally:self.parameter_scopes.pop()
            self.mapping().used.append({'definition':list(k),'name':name,'kind':'GUI compatibility body',
                                        'path':str(dd.path),'sha256':dd.sha256,'call_site':list(key)})
            return '\n'.join(output)
        if f.find('FlagSubFunctions') is not None:
            groups={}
            for ref in f.findall('SubFunctionType'):
                sd,sk,se=self.resolve(ref,dd,k); groups[sk]=[se.findtext('Identifier'),[]]
            for child in e.findall('FunctionCall'):
                cd,ck,ce=self.resolve(child,d,key)
                _,sk,_=self.resolve(ce.find('SubFunctionType'),cd,ck)
                if sk not in groups:self.error('foreign subfunction type',d,key)
                role=groups[sk][0]
                code=self.call(cd,ck,ce,(role or '').lower() not in {'if','conditions','cond'})
                if code:groups[sk][1].append(code)
            byname={n:v for n,v in groups.values()}
            if k[0]=='Ntve' and name=='IfThenElse':
                cond=' && '.join(byname.get('if',[])) or 'true'
                return 'if ('+cond+') {\n'+'\n'.join(byname.get('then',[]))+'\n} else {\n'+'\n'.join(byname.get('else',[]))+'\n}'
            if k[0]=='Ntve' and name=='RepeatForever':return 'while (true) {\n'+'\n'.join(byname.get('actions',[]))+'\n}'
            if k[0]=='Ntve' and name=='While':return 'while ('+(' && '.join(byname.get('Conditions',[])) or 'true')+') {\n'+'\n'.join(byname.get('Actions',[]))+'\n}'
            if k[0]=='Ntve' and name in {'And','Or'}:
                return '('+(' && ' if name=='And' else ' || ').join(byname.get('cond',[]))+')' if byname.get('cond') else ('true' if name=='And' else 'false')
            self.error('unsupported control-flow template',dd,k)
        if k[0]=='Ntve' and name=='SetVariable' and len(values)==2:return values[0]+' = '+values[1]+';'
        if k[0]=='Ntve' and name=='Return' and len(values)==1:return 'return '+values[0]+';'
        if k[0]=='Ntve' and name in {'Comparison','ArithmeticInt','ArithmeticReal'} and len(values)==3:
            if values[1] not in {'==','!=','<','>','<=','>=','+','-','*','/','%'}:self.error('invalid operator',d,key)
            return '('+values[0]+' '+values[1]+' '+values[2]+')'
        if f.find('ScriptCode') is not None:self.error('unsupported expression template',dd,k)
        if f.find('FlagNative') is not None:
            if not name or not re.fullmatch(r'[A-Za-z_]\w*',name):self.error('invalid native binding',dd,k)
            types=[]
            for i,(pd,pk,pe) in enumerate(definitions):
                parameter_type=self.mapping().raw_type(pe,pd,pk,'ParameterType')
                if parameter_type=='unitref':
                    # B98370 AnyUnit uses the null unitref directly; only concrete unit expressions are converted.
                    if values[i]!='null':
                        conversion=self.mapping().candidates('UnitRefFromUnit')
                        if not any(r['return']=='unitref' and r['parameters']==['unit'] for r in conversion):
                            self.error('unit reference conversion declaration missing',d,key)
                        values[i]='UnitRefFromUnit('+values[i]+')'
                types.append(parameter_type)
            if f.find('FlagEvent') is not None:
                if event_trigger is None:self.error('event call requires explicit registration trigger',d,key)
                values.insert(0,event_trigger)
                types.insert(0,'trigger')
            value=self.mapping().bind(name,self.mapping().raw_type(f,dd,k,'ReturnType'),types,values,statement,d,key,k,dd)
            return value+';' if statement else value
        else:
            name=self.symbol(dd,k)
            # Core GUI helper bodies are provided by the registered official
            # NativeLib.galaxy include, not regenerated under duplicate names.
            if k[0] not in self.external_libraries:self.functions[(str(dd.path),k)]=(dd,k,f)
        value=name+'('+', '.join(values)+')'
        return value+';' if statement else value

    def body(self,d,key,e):
        allowed={'Identifier','Variable','Action','FunctionCall','Event','Condition','Disabled','FlagInitiallyOff','FlagRunOnMapInit','FlagAction','FlagCall','FlagCondition','FlagEvent','FlagInternal','FlagHidden','Parameter','ReturnType','Label','Comment'}
        unknown={c.tag for c in e}-allowed
        if unknown:self.error('unsupported executable fields: '+','.join(sorted(unknown)),d,key)
        locals=[]; code=[]
        for ref in e.findall('Variable'):
            vd,vk,v=self.resolve(ref,d,key)
            locals.append(self.typ(v,vd,vk,'VariableType')+' '+self.symbol(vd,vk)+';')
            if v.find('Value') is not None:code.append(self.symbol(vd,vk)+' = '+self.param(v.find('Value'),vd,vk)+';')
        for ref in list(e):
            if ref.tag in {'Action','FunctionCall'}:
                cd,ck,c=self.resolve(ref,d,key); code.append(self.call(cd,ck,c))
        return '\n'.join(locals+code)

    def generate(self,proof_token=None):
        if proof_token is not None and not re.fullmatch(r'[A-Za-z0-9_]{1,64}',proof_token):
            raise SC2Error('invalid_runtime_proof','invalid runtime proof token')
        from sc2_triggers import check
        from .trigger_writer import validate_editor_library_layout
        for document in self.target.documents:
            validate_editor_library_layout(document.root)
        report=check(self.target)
        if report['errors']:raise SC2Error('trigger_validation_failed','GUI dependency/structure validation failed',diagnostics=report['errors'])
        triggers=[]; globals=[]; group_order=[]
        loading=self.target.graph.get('loading_order',[])
        if isinstance(loading,dict):loading=loading.get('components',[])
        order={str(path).casefold():i for i,path in enumerate(loading)}
        for d in sorted(self.target.documents,key=lambda d:order.get(str(d.component).casefold(),0)):
            if d.standard in self.external_libraries:continue
            # Declaration order is Root/Category order, never XML Element order.
            def visit(container,key):
                for ref in container.findall('Item'):
                    dd,k,e=self.resolve(ref,d,key)
                    if e.find('Disabled') is not None:continue
                    group=(str(dd.path),k[0])
                    if group not in group_order:group_order.append(group)
                    if k[1]=='Category':visit(e,k)
                    elif k[1]=='Trigger':triggers.append((dd,k,e))
                    elif k[1]=='Variable':globals.append((dd,k,e))
                    elif k[1]=='FunctionDef':self.functions[(str(dd.path),k)]=(dd,k,e)
                    elif k[1] not in {'Comment','Label'}:self.error('unsupported declaration',dd,k)
            root=d.root.find('Root')
            if root is not None:visit(root,(d.standard,'Root',''))
            for lib in d.root.findall('Library'):
                if lib.find('Root') is not None:visit(lib.find('Root'),(lib.get('Id'),'Root',''))
        schedule={}
        # Follow component/library load order. A dependency's trigger handles
        # must exist before a dependent map initializes references to them.
        for group in group_order:schedule[group]=[]
        for d,k,e in globals:
            if e.find('Value') is not None:schedule[(str(d.path),k[0])].append(self.symbol(d,k)+' = '+self.param(e.find('Value'),d,k)+';')
        for d,k,e in triggers:
            init=schedule[(str(d.path),k[0])]
            name=self.symbol(d,k); callback=name+'_Func'
            self.emit('trigger '+name+';',d,k)
            body=self.body(d,k,e)
            conditions=[]
            for ref in e.findall('Condition'):
                cd,ck,c=self.resolve(ref,d,k); conditions.append(self.call(cd,ck,c,False))
            guard=' && '.join(x for x in conditions if x) or 'true'
            local_count=len(e.findall('Variable'))
            body_lines=body.splitlines()
            declarations='\n'.join(body_lines[:local_count])
            actions='\n'.join(body_lines[local_count:])
            self.emit('bool '+callback+'(bool testConds, bool runActions) {\n'+declarations+'\nif (testConds && !('+guard+')) { return false; }\nif (!runActions) { return true; }\n'+actions+'\nreturn true;\n}',d,k)
            init.append(name+' = TriggerCreate('+json.dumps(callback)+');')
            if e.find('FlagInitiallyOff') is not None:init.append('TriggerEnable('+name+', false);')
            for ref in e.findall('Event'):
                cd,ck,c=self.resolve(ref,d,k);init.append(self.call(cd,ck,c,event_trigger=name))
            if e.find('FlagRunOnMapInit') is not None:self.error('RunOnMapInit scheduling requires official evidence',d,k)
        done=set()
        while set(self.functions)-done:
            identity=next(x for x in self.functions if x not in done); done.add(identity)
            d,k,e=self.functions[identity]
            if e.find('Disabled') is not None:self.error('call to disabled definition',d,k)
            params=[]
            for ref in e.findall('Parameter'):
                if ref.get('Type')=='Comment':continue
                pd,pk,p=self.resolve(ref,d,k);params.append(self.typ(p,pd,pk,'ParameterType')+' '+self.symbol(pd,pk))
            self.emit(self.typ(e,d,k,'ReturnType')+' '+self.symbol(d,k)+'('+', '.join(params)+') {\n'+self.body(d,k,e)+'\n}',d,k)
        for d,k,e in globals:
            self.emit(self.typ(e,d,k,'VariableType')+' '+self.symbol(d,k)+';',d,k)
        # Galaxy requires declarations before use: emit prototypes and globals first.
        # source mapping remains stable by adding a separate declarations prelude.
        prelude=[]
        for d,k,e in globals:prelude.append(self.typ(e,d,k,'VariableType')+' '+self.symbol(d,k)+';')
        for d,k,e in triggers:prelude.append('trigger '+self.symbol(d,k)+';')
        for line in self.lines:
            if re.match(r'^\w+ \w+\([^;]*\) \{$',line):prelude.append(line[:-2]+';')
        # Remove the original standalone globals, retaining line count for the map.
        standalone=set(prelude)
        self.lines=['' if l in standalone else l for l in self.lines]
        shift=len(prelude)
        for m in self.source_map:m['start']+=shift;m['end']+=shift
        init=[line for group in schedule.values() for line in group]
        proof=[]
        if proof_token:
            proof=['bool gf_AgentOfflineProof(bool testConds, bool runActions) {',
                   'if (!runActions) { return true; }',
                   'UIDisplayMessage(PlayerGroupAll(), c_messageAreaChat, StringToText('+json.dumps('GUI_OFFLINE_EXEC_'+proof_token)+'));',
                   'return true;','}']
            init.append('TriggerAddEventMapInit(TriggerCreate("gf_AgentOfflineProof"));')
        return {'source':'\n'.join(prelude+self.lines+proof+['void InitMap() {']+init+['}'])+'\n',
                'source_map':self.source_map,'validation':report,'complete':True,
                'used_mappings':self.mapping().used,'resource_inputs':self.resource_inputs}
