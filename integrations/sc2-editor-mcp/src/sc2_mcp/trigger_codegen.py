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
        self.foreach_scopes = []
        self.switch_scopes = []
        self.body_decl_lens = {}
        self.resource_inputs = {}
        # (path,key) of every Variable registered at Root/Category, plus the minimal
        # ['array'|'constant'] facts applied after the complete registration pass.
        self.global_variables = {}
        # (path,key) of registered global scalar int Constants -> literal int.
        self.global_constants = {}

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
        prefix='' if key[1]=='ParamDef' else ('lib'+key[0]+'_' if key[0] else '')
        return prefix+{'Variable':'gv_','ParamDef':'lp_','FunctionDef':'gf_','Trigger':'gt_'}.get(key[1],'v_')+name

    def typ(self,e,d,key,tag):
        container=e.find(tag)
        t=container.find('Type') if container is not None else None
        value=t.get('Value') if t is not None else 'void' if tag=='ReturnType' else None
        if not value or not re.fullmatch('[a-z]+',value):self.error('unsupported type',d,key)
        # Constant is accepted only for the exact VariableType of a global Constant registered by
        # constant_literal; every other use (local/ParamDef/ReturnType/unknown attribute/array) fails.
        constant=container is not None and container.find('Constant') is not None
        if constant:
            if tag!='VariableType' or 'constant' not in (self.global_variables.get((str(d.path),key)) or {}):self.error('unsupported array/reference type',d,key)
            if (any(c.tag not in {'Type','Constant'} for c in container) or len(container.findall('Type'))!=1 or len(container.findall('Constant'))!=1
                    or container.find('Constant').attrib or len(container.find('Constant'))):self.error('unsupported array/reference type',d,key)
        elif container is not None and any(c.tag not in {'Type','TypeElement','GameType','ArraySize'} for c in container):self.error('unsupported array/reference type',d,key)
        mapped=self.mapping().type(e,d,key,tag)
        if not mapped:self.error('type has no resolved Galaxy representation',d,key)
        arrays=container.findall('ArraySize') if container is not None else []
        if len(arrays)>1:self.error('duplicate ArraySize',d,key)
        if arrays:
            if constant:self.error('unsupported array/reference type',d,key)
            a=arrays[0]
            if tag!='VariableType':self.error('unsupported array type',d,key)
            if mapped=='string':
                # Existing local/declaration string arrays: Dim0 literal editor maximum only.
                if set(a.attrib)!={'Dim','Value'} or len(a) or a.get('Dim')!='0' or not re.fullmatch('[0-9]+',a.get('Value','')) or int(a.get('Value'))>8191:self.error('unsupported array type',d,key)
                return mapped+'['+str(int(a.get('Value'))+1)+']'
            if mapped=='int':
                # Only an int array already registered as a Root/Category global (arrays are
                # applied before functions/triggers are emitted); locals carry another identity.
                entry=self.global_variables.get((str(d.path),key))
                if entry is None or 'array' not in entry:self.error('unsupported array type',d,key)
                return mapped+'['+str(self.int_array_length(a,d,key)+1)+']'
            self.error('unsupported array type',d,key)
        return mapped

    def expr(self,d,key,e):
        variants=[c for c in e if c.tag in {'FunctionCall','Variable','Parameter','Preset','ValueElement','Value'}]
        if any(c.tag=='Array' for c in e) and not (len(variants)==1 and variants[0].tag=='Variable'):self.error('array index requires variable reference',d,key)
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
        if not variants and value_type is not None and value_type.get('Type') in {'string','gamelink'}:
            tag_counts={t:sum(1 for c in e if c.tag==t) for t in {'ParameterDef','ValueType','ValueGameType','Comment'}}
            allowed={'ParameterDef','ValueType','Comment'}
            if value_type.get('Type')=='gamelink':allowed.add('ValueGameType')
            if (tag_counts['ValueType']==1 and tag_counts['ParameterDef']<=1
                    and tag_counts['ValueGameType']<=(1 if value_type.get('Type')=='gamelink' else 0)
                    and all(c.tag in allowed for c in e)):
                return json.dumps('',ensure_ascii=True)
        if len(variants)!=1:self.error('ambiguous or unsupported parameter value',d,key)
        v=variants[0]
        if v.tag=='Value':
            t=e.find('ValueType'); t=t.get('Type') if t is not None else None; value=v.text or ''
            if t=='text':return 'StringExternal('+json.dumps(value)+')'
            if t in {'string','gamelink','anygamelink'}:return json.dumps(value,ensure_ascii=True)
            if t in {'userfield','userinstance','catalogfieldpath'} and self.mapping().aliases.get(t)=='string':
                vt=next((c for c in e if c.tag=='ValueType'),None); ctxs=e.findall('ValueContext')
                if (sum(1 for c in e if c.tag=='Value')==1 and sum(1 for c in e if c.tag=='ValueType')==1
                        and sum(1 for c in e if c.tag=='ParameterDef')<=1
                        and set(c.tag for c in e)<={'ParameterDef','Value','ValueType','ValueContext','Comment'}
                        and set(e.attrib)<={'Type','Id'} and e.get('Type') in {None,'Param'}
                        and vt is not None and set(vt.attrib)=={'Type'} and not len(vt) and not (vt.text or '').strip()
                        and not v.attrib and not len(v) and bool((v.text or '').strip())
                        and len(ctxs)==1 and set(ctxs[0].attrib)=={'Value'} and not len(ctxs[0])
                        and not (ctxs[0].text or '').strip() and bool(ctxs[0].get('Value','').strip())):
                    return json.dumps(value,ensure_ascii=True)
            if t=='bool' and value in {'true','false'}:return value
            if t=='unitfilter':
                quoted=json.dumps(value,ensure_ascii=True);return self.mapping().bind('UnitFilterStr','unitfilter',['string'],[quoted],False,d,key,key)
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
            if value is None:
                implicit=self.implicit_integer_preset(dd,k,el)
                if implicit is not None:return implicit
            if value is None or not re.fullmatch(r'-?\d+(?:\.\d+)?|[A-Za-z_]\w*|==|!=|<=|>=|<|>|\+|-|\*|/|%',value):self.error('unsupported preset',dd,k)
            return value
        if (v.tag=='ValueElement' and k[1]=='Preset' and value_type is not None and value_type.get('Type')=='preset'
                and el.find('PresetAsBits') is not None and el.find('BaseType') is not None and el.find('BaseType').get('Value')=='int'
                and not ({c.tag for c in e}-{'ParameterDef','ValueType','ValueElement','Comment'})):
            return '0'
        if v.tag=='ValueElement' and k[1]!='Trigger':self.error('unsupported element value',dd,k)
        arrays=el.findall('VariableType/ArraySize') if el is not None else []
        if len(arrays)>1 or (el is not None and any(c.tag=='ArraySize' for c in el)):self.error('duplicate ArraySize',dd,k)
        if not arrays:
            def has_array(node):
                return any(True for _ in node.iter('Array'))
            if k[1]=='Variable' and has_array(e):self.error('scalar variable cannot carry Array',d,key)
            if k[1]!='Variable' and (has_array(e) or has_array(el)):self.error('array is only supported for variable references',d,key)
            if k[1]=='Variable':self.variables[(str(dd.path),k)]=(dd,k,el)
            return self.symbol(dd,k)
        if k[1]!='Variable':self.error('array is only supported for variable references',d,key)
        if set(c.tag for c in e)-{'ParameterDef','Variable','Array','Comment'}:self.error('unsupported array reference',d,key)
        refs=e.findall('Array')
        if len(refs)!=1:self.error('array reference requires exactly one Array',d,key)
        ref=refs[0]
        if set(ref.attrib)-{'Type','Library','Id'}:self.error('unsupported array metadata',d,key)
        if ref.get('Type')!='Param' or len(ref) or not (ref.get('Id') or '').strip():self.error('unsupported array reference type',d,key)
        ad,ak,ae=self.resolve(ref,d,key)
        size=self.typ(el,dd,k,'VariableType')
        n=int(size[size.rfind('[')+1:-1])
        if ae is None or set(c.tag for c in ae)-{'ParameterDef','Variable','ValueType','Value','Comment'}:self.error('unsupported array index',d,key)
        values=ae.findall('Value')
        vrefs=ae.findall('Variable')
        if len(values)==1 and not vrefs:
            vtypes=ae.findall('ValueType')
            vtype=vtypes[0] if len(vtypes)==1 else None
            raw=values[0]
            if vtype is None or set(vtype.attrib)!={'Type'} or vtype.get('Type')!='int' or len(vtype) or raw.attrib or len(raw) or raw.text is None or not re.fullmatch('-?[0-9]+',raw.text):self.error('unsupported array index',d,key)
            idx=int(raw.text)
            if not 0<=idx<n:self.error('array index out of range',d,key)
            return self.symbol(dd,k)+'['+str(idx)+']'
        if len(vrefs)==1 and not values and not ae.findall('ValueType'):
            vref=vrefs[0]
            if set(vref.attrib)-{'Type','Library','Id'} or len(vref) or vref.get('Type')!='Variable' or not (vref.get('Id') or '').strip():self.error('unsupported array index',d,key)
            id,ik,ie=self.resolve(vref,ad,ak)
            ivts=ie.findall('VariableType') if ie is not None else []
            ivt=ivts[0] if len(ivts)==1 else None
            itypes=ivt.findall('Type') if ivt is not None else []
            itype=itypes[0] if len(itypes)==1 else None
            if ik[1]!='Variable' or ivt is None or ivt.attrib or set(c.tag for c in ivt)-{'Type'}:self.error('array index must be an int scalar',d,key)
            if itype is None or set(itype.attrib)!={'Value'} or itype.get('Value')!='int' or len(itype) or ie.find('VariableType/ArraySize') is not None:self.error('array index must be an int scalar',d,key)
            return self.symbol(dd,k)+'['+self.symbol(id,ik)+']'
        self.error('unsupported array index',d,key)

    def implicit_integer_preset(self,d,key,el):
        # Exact implicit PresetInteger group: a Value-less PresetValue whose single parent Preset in the
        # same document lists it by direct <Item Type='PresetValue' Library='...' Id='...'/> refs, the
        # group carrying exactly one empty PresetInteger and BaseType int, and every sibling item an
        # empty PresetValue. The zero-based Item position is the ordinal; any duplicate, foreign,
        # missing, explicit or unknown detail fails closed (None -> caller's unsupported preset).
        if key[1]!='PresetValue' or el is None or len(el.findall('DefinesDefault'))>1:return None
        if {c.tag for c in el}-{'DefinesDefault'} or any(len(c) or c.attrib for c in el):return None
        elements=dict(getattr(d,'elements',{}))
        allowed={'Identifier','Label','PresetInteger','BaseType','Item'}
        refs_ok=lambda r: set(r.attrib)=={'Type','Library','Id'} and r.get('Type')=='PresetValue' and r.get('Library')==key[0] and not len(r) and bool((r.get('Id') or '').strip())
        parents=[]
        for ek,ev in elements.items():
            if ek[1]!='Preset' or ek[0]!=key[0] or ev is None:continue
            refs=ev.findall('Item')
            keys=[(ek[0],'PresetValue',r.get('Id')) for r in refs if refs_ok(r)]
            if key in keys:parents.append((ev,refs,keys))
        if len(parents)!=1:return None
        parent,refs,keys=parents[0]
        if (set(c.tag for c in parent)-allowed or len(parent.findall('PresetInteger'))!=1
                or parent.find('PresetInteger').attrib or len(parent.find('PresetInteger'))):return None
        groups=parent.findall('BaseType')
        if (len(groups)!=1 or set(groups[0].attrib)!={'Value'} or len(groups[0]) or groups[0].get('Value')!='int'
                or len(refs)!=len(keys) or len(set(keys))!=len(keys) or keys.count(key)!=1):return None
        for ref in keys:
            node=elements.get(ref); flags=node.findall('DefinesDefault') if node is not None else []
            if (node is None or set(c.tag for c in node)-{'DefinesDefault'} or node.get('Value') is not None
                    or node.find('ScriptCode') is not None or len(flags)>1 or any(len(f) or f.attrib for f in flags)):return None
        return str(keys.index(key)) if sum(len(elements[ref].findall('DefinesDefault')) for ref in keys)<=1 else None

    def param(self,ref,d,key):
        dd,k,e=self.resolve(ref,d,key)
        return self.expr(dd,k,e)

    def foreach_temp(self,d,key):
        # One automatic int per ForEachInteger occurrence, declared at the top of the enclosing
        # function/trigger (hoisted by body) and only assigned after the trigger guard, before start.
        scopes=getattr(self,'foreach_scopes',[])
        if not scopes:self.error('ForEachInteger: dynamic bound requires an enclosing function/trigger scope',d,key)
        name='auto_foreach_ae_'+str(len(scopes[-1])+1); scopes[-1].append(name)
        return name

    def switch_temp(self,d,key):
        # One automatic string per Switch activation, declared with the enclosing function/trigger
        # locals (hoisted by body) and only assigned at the original action position, after the guard.
        scopes=getattr(self,'switch_scopes',None)
        if not scopes:self.error('Switch: string selector requires an enclosing function/trigger scope',d,key)
        name='auto_switch_str_'+str(len(scopes[-1])+1); scopes[-1].append(name)
        return name

    def switch_type(self,container,tag,d,key):
        # Expression-string type of a literal ValueType/ParameterType/VariableType/ReturnType: the exact
        # single <Type Value="..."/>, mapped through the existing GUI type/alias API; unknown -> None.
        return self.mapping().type(container,d,key,tag) if container is not None else None

    def switch_param(self,ref,d,key,expected):
        # A Switch/SwitchCase argument is a Param bound to exactly one Ntve parameter definition; its
        # expression children are the ParameterDef binding plus at most one value expression.
        pd,pk,pe=self.resolve(ref,d,key)
        pds=pe.findall('ParameterDef') if pe is not None else []
        if (pk[1]!='Param' or len(pds)!=1 or (pds[0].get('Library'),pds[0].get('Id'))!=expected
                or {c.tag for c in pe}-{'ParameterDef','ValueType','FunctionCall','Variable','Parameter','Value','Comment','Preset'}):
            self.error('Switch: argument is bound to a foreign or unsupported parameter',d,key)
        return pd,pk,pe

    def switch_expr_type(self,pd,pk,pe,d,key):
        # Proven string when the Param carries literal ValueType string (including empty value), a
        # string Parameter or Variable reference, or a FunctionCall whose definition ReturnType is string.
        vts=pe.findall('ValueType')
        if len(vts)>1:self.error('Switch: duplicate ValueType',d,key)
        if vts:
            t=vts[0]
            if (set(t.attrib)!={'Type'} or len(t) or t.get('Type')!='string'
                    or {c.tag for c in pe}-{'ParameterDef','ValueType','Value','Comment'} or len(pe.findall('Value'))>1):
                self.error('Switch: unsupported string value type',d,key)
            return 'string'
        variants=[c for c in pe if c.tag in {'FunctionCall','Variable','Parameter','Value'}]
        if len(variants)!=1:self.error('Switch: unsupported string expression',d,key)
        v=variants[0]
        if {c.tag for c in pe}-{'ParameterDef','Comment',v.tag}:self.error('Switch: unsupported string expression',d,key)
        dd,k,el=self.resolve(v,pd,pk)
        if v.tag=='Variable':          return self.switch_type(el,'VariableType',dd,k)
        if v.tag=='Parameter':         return self.switch_type(el,'ParameterType',dd,k)
        if v.tag=='FunctionCall':
            fd,fk,fe=self.resolve(el.find('FunctionDef'),dd,k)
            return self.switch_type(fe,'ReturnType',fd,fk)
        return None

    def _switch_signature(self,element,d,key,expected,fields,required):
        # Exact native definition shape: allowed child tags, required flags, and the whitespace-normalized
        # ScriptCode template must all match. SubFuncType elements carry only <Action/>.
        if {c.tag for c in element}-fields:self.error('Switch: unsupported template fields',d,key)
        if any(element.find(tag) is None for tag in required):self.error('Switch: template flag missing',d,key)
        if re.sub(r'\s+','',element.findtext('ScriptCode') or '')!=expected:self.error('Switch: mutated template',d,key)

    def native_switch(self,d,key,e,statement):
        # Only the exact native Ntve Switch 91C49196: selector Param (B4ACF12A, anycompare) of proven
        # string type, ordered children = Ntve SwitchCase (role AD43BC93) and/or default actions (role
        # 3E7C4C40). Emitted as one string cache plus a forward if/else-if chain; defaults are a plain
        # block after the cases. No loop is entered, so loop_depth and break/return stay unchanged.
        dd,k,f=self.resolve(e.find('FunctionDef'),d,key)
        if k!=('Ntve','FunctionDef','91C49196'):self.error('Switch: unexpected definition identity',d,key)
        self._switch_signature(f,d,key,'#INITAUTOVAR(val,value)#SUBFUNCS(cases)#IFHAVESUBFUNCS(cases,else){#SUBFUNCS(defaults)}',
                               {'Identifier','Label','FlagAction','FlagSubFunctions','Parameter','SubFunctionType','ScriptCode'},['FlagAction','FlagSubFunctions'])
        if f.findtext('Identifier')!='Switch' or f.find('Label') is None:self.error('Switch: unexpected definition identity',d,key)
        refs=f.findall('Parameter')
        pd,pk,pe=self.resolve(refs[0],dd,k) if len(refs)==1 else (None,None,None)
        pdt=pe.find('ParameterType/Type') if pe is not None else None
        if (pk!=('Ntve','ParamDef','B4ACF12A') or pe.findtext('Identifier')!='value' or pdt is None
                or set(pdt.attrib)!={'Value'} or len(pdt) or pdt.get('Value')!='anycompare'
                or {c.tag for c in pe}-{'Identifier','ParameterType'}):
            self.error('Switch: unexpected parameter signature',d,key)
        groups=f.findall('SubFunctionType')
        if len(groups)!=2 or {(r.get('Library'),r.get('Id')) for r in groups}!={('Ntve','AD43BC93'),('Ntve','3E7C4C40')}:
            self.error('Switch: unexpected subfunction signature',d,key)
        for ref in groups:
            sd,sk,se=self.resolve(ref,dd,k)
            tag=se.find('FunctionDef')
            if se.find('Action') is None:self.error('Switch: unexpected subfunction signature',d,key)
            if sk==('Ntve','SubFuncType','AD43BC93'):
                if (se.findtext('Identifier')!='cases' or tag is None
                        or (tag.get('Type'),tag.get('Library'),tag.get('Id'))!=('FunctionDef','Ntve','3A1227AB')):
                    self.error('Switch: unexpected case subfunction signature',d,key)
            elif sk==('Ntve','SubFuncType','3E7C4C40'):
                if (se.findtext('Identifier')!='defaults' or tag is not None
                        or se.find('FlagAction') is not None or se.find('FlagSubFunctions') is not None):
                    self.error('Switch: unexpected default subfunction signature',d,key)
            else:self.error('Switch: unexpected subfunction signature',d,key)
        parameter=e.findall('Parameter')
        if len(parameter)!=1 or parameter[0].get('Type')!='Param':self.error('Switch: exactly one selector argument required',d,key)
        spd,spk,spe=self.switch_param(parameter[0],d,key,('Ntve','B4ACF12A'))
        if self.switch_expr_type(spd,spk,spe,d,key)!='string':self.error('Switch: string selector required',d,key)
        if not statement:self.error('Switch: standalone Switch is not an expression',d,key)
        selector=self.expr(spd,spk,spe)
        chain=[]; defaults=[]
        for child in e.findall('FunctionCall'):
            cd,ck,ce=self.resolve(child,d,key)
            if ce.find('Disabled') is not None:
                # Disabled child skipped before its role is read; keep existing subtree resolution.
                for inner in ce.findall('FunctionCall'):
                    if inner.get('Library')==ce.get('Library'):self.resolve(inner,cd,ck)
                continue
            sub=ce.find('SubFunctionType')
            _,sk,_=self.resolve(sub,cd,ck) if sub is not None else (None,None,None)
            if sk==('Ntve','SubFuncType','AD43BC93'):
                # Roles are independent groups: the template emits #SUBFUNCS(cases) then
                # #SUBFUNCS(defaults), so physical interleaving order carries no meaning; only the
                # relative order within each role is preserved.
                result=self.native_switch_case(cd,ck,ce)
                if result is not None:chain.append(result)
            elif sk==('Ntve','SubFuncType','3E7C4C40'):
                # Defaults are ordered actions; multiple default children are all emitted in order.
                if {c.tag for c in ce}-{'FunctionDef','Parameter','FunctionCall','SubFunctionType','Disabled','ScriptCode','Comment'}:
                    self.error('Switch: foreign default role',d,key)
                code=self.call(cd,ck,ce,True)
                if code:defaults.append(code)
            else:self.error('Switch: foreign child role',d,key)
        temp=self.switch_temp(d,key)
        parts=[]
        for i,(value,actions) in enumerate(chain):
            parts.append(('if ' if i==0 else 'else if ')+'('+temp+' == '+value+') {\n'+'\n'.join(actions)+'\n}')
        if defaults:
            block='{\n'+'\n'.join(defaults)+'\n}'
            parts.append(('else ' if parts else '')+block)
        self.mapping().used.append({'definition':list(k),'name':'Switch','kind':'GUI native control flow',
                                    'path':str(dd.path),'sha256':dd.sha256,'call_site':list(key)})
        return temp+' = '+selector+';\n'+'\n'.join(parts)

    def native_switch_case(self,d,key,e):
        # A Switch child: resolve its FunctionDef so definition element (cf) and call metadata (e) stay
        # separate. Disabled cases never open an else branch; the caller already skips them and GUI
        # prevalidation resolves references.
        if e.find('Disabled') is not None:return None
        cd,ck,cf=self.resolve(e.find('FunctionDef'),d,key)
        if ck!=('Ntve','FunctionDef','3A1227AB'):self.error('Switch: foreign case definition',d,key)
        self._switch_signature(cf,d,key,'#IFSUBFUNC(notfirst,else)if(#AUTOVAR(val,parent)==#PARAM(value)){#SUBFUNCS(actions)}',
                               {'Identifier','Label','FlagAction','FlagSubFunctions','FlagHidden','Parameter','SubFunctionType','ScriptCode'},['FlagAction','FlagSubFunctions','FlagHidden'])
        if cf.findtext('Identifier')!='SwitchCase':self.error('Switch: foreign case definition',d,key)
        refs=cf.findall('Parameter')
        qpd,qpk,qpe=self.resolve(refs[0],cd,ck) if len(refs)==1 else (None,None,None)
        qdt=qpe.find('ParameterType/Type') if qpe is not None else None
        if (qpk!=('Ntve','ParamDef','9A8F1093') or qpe.findtext('Identifier')!='value' or qdt is None
                or set(qdt.attrib)!={'Value'} or len(qdt) or qdt.get('Value')!='sameasparent'
                or {c.tag for c in qpe}-{'Identifier','ParameterType'}):
            self.error('Switch case: unexpected parameter signature',d,key)
        refs=cf.findall('SubFunctionType')
        gpd,gpk,gpe=self.resolve(refs[0],cd,ck) if len(refs)==1 else (None,None,None)
        if (gpk!=('Ntve','SubFuncType','363CE97C') or gpe.findtext('Identifier')!='actions' or gpe.find('Action') is None
                or gpe.find('FunctionDef') is not None):
            self.error('Switch case: actions role required',d,key)
        params=e.findall('Parameter')
        if len(params)!=1 or params[0].get('Type')!='Param':self.error('Switch: case requires exactly one value',d,key)
        vpd,vpk,vpe=self.switch_param(params[0],d,key,('Ntve','9A8F1093'))
        if self.switch_expr_type(vpd,vpk,vpe,d,key)!='string':self.error('Switch case: unsupported case value type',d,key)
        # Proven string expression, evaluated only when its case is reached.
        code=self.expr(vpd,vpk,vpe)
        actions=[]
        for inner in e.findall('FunctionCall'):
            id_,ik,ie=self.resolve(inner,d,key)
            sub=ie.find('SubFunctionType')
            _,sk2,_=self.resolve(sub,id_,ik) if sub is not None else (None,None,None)
            if sk2!=('Ntve','SubFuncType','363CE97C'):self.error('Switch case: foreign action role',d,key)
            emitted=self.call(id_,ik,ie,True)
            if emitted:actions.append(emitted)
        return code,actions


    def call(self,d,key,e,statement=True,event_trigger=None):
        if key[1]=='Comment':
            if not statement:self.error('GUI comment used as expression',d,key)
            return ''
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
        if k==('Ntve','FunctionDef','91C49196'):
            # Exact native string Switch is resolved here, before the generic FlagSubFunctions walk.
            return self.native_switch(d,key,e,statement)
        if f.find('FlagSubFunctions') is not None:
            groups={}
            for ref in f.findall('SubFunctionType'):
                sd,sk,se=self.resolve(ref,dd,k); groups[sk]=[se.findtext('Identifier'),[]]
            for child in e.findall('FunctionCall'):
                cd,ck,ce=self.resolve(child,d,key)
                _,sk,_=self.resolve(ce.find('SubFunctionType'),cd,ck)
                if sk not in groups:self.error('foreign subfunction type',d,key)
                role=groups[sk][0]
                entering_loop=((role or '').lower()=='actions' and k[0]=='Ntve' and (name in {'RepeatForever','While'} or (k==('Ntve','FunctionDef','66474248') and name=='ForEachInteger')))
                previous_depth=getattr(self,'loop_depth',0)
                if entering_loop:self.loop_depth=previous_depth+1
                try:
                    code=self.call(cd,ck,ce,(role or '').lower() not in {'if','conditions','cond'})
                finally:
                    if entering_loop:self.loop_depth=previous_depth
                if code:groups[sk][1].append(code)
            byname={n:v for n,v in groups.values()}
            if k[0]=='Ntve' and name=='IfThenElse':
                cond=' && '.join(byname.get('if',[])) or 'true'
                return 'if ('+cond+') {\n'+'\n'.join(byname.get('then',[]))+'\n} else {\n'+'\n'.join(byname.get('else',[]))+'\n}'
            if k[0]=='Ntve' and name=='RepeatForever':return 'while (true) {\n'+'\n'.join(byname.get('actions',[]))+'\n}'
            if k[0]=='Ntve' and name=='While':return 'while ('+(' && '.join(byname.get('Conditions',[])) or 'true')+') {\n'+'\n'.join(byname.get('Actions',[]))+'\n}'
            if k==('Ntve','FunctionDef','66474248') and name=='ForEachInteger':
                if not (statement and len(values)==4 and [definitions[i][2].findtext('Identifier') for i in range(len(definitions))]==['var','s','e','increment'] and all(f.find(t) is not None for t in ('FlagAction','FlagSubFunctions','FlagAllowBreak')) and re.sub(r'\s+','',f.findtext('ScriptCode') or '')=='#INITAUTOVAR(ae,e)#INITAUTOVAR(ai,increment)#PARAM(var)=#PARAM(s);for(;((#AUTOVAR(ai)>=0&&#PARAM(var)<=#AUTOVAR(ae))||(#AUTOVAR(ai)<0&&#PARAM(var)>=#AUTOVAR(ae)));#PARAM(var)+=#AUTOVAR(ai)){#SUBFUNCS(actions)}'):
                    self.error('unsupported control-flow template',dd,k)
                var,start,end,step=values
                # var stays a simple identifier; step stays a non-zero decimal constant literal.
                # start/end are already compiled int expressions (constant, variable or function call).
                if (not re.match(r'^[A-Za-z_]\w*$',var) or not re.match(r'^-?[0-9]+$',step) or int(step)==0
                        or not start or start[0] in ';{}' or not end or end[0] in ';{}'):
                    self.error('ForEachInteger: unsupported dynamic/zero-step loop (int start/end expressions, non-zero decimal integer literal step and simple identifier var required)',dd,k)
                if re.match(r'^-?[0-9]+$',start) and re.match(r'^-?[0-9]+$',end):
                    op='<=' if int(step)>0 else '>='
                    return var+' = '+start+';\nwhile ('+var+' '+op+' '+end+') {\n'+'\n'.join(byname.get('actions',[]))+'\n'+var+' = '+var+' + ('+step+');\n}'
                # #INITAUTOVAR(ae,e)#INITAUTOVAR(ai,increment)#PARAM(var)=#PARAM(s): a non-literal compiled
                # end is cached once in this loop's own function-scope temp, before start is assigned, so
                # edits to the end variable inside the body cannot move this activation's inclusive bound.
                if not re.match(r'^-?[0-9]+$',end):
                    ae=self.foreach_temp(dd,k); end_bound=ae
                    head=ae+' = '+end+';\n'+var+' = '+start+';'
                else:
                    end_bound=end; head=var+' = '+start+';'
                ai='('+step+')'
                cond='(('+ai+' >= 0 && '+var+' <= '+end_bound+') || ('+ai+' < 0 && '+var+' >= '+end_bound+'))'
                return head+'\nwhile ('+cond+') {\n'+'\n'.join(byname.get('actions',[]))+'\n'+var+' = '+var+' + '+ai+';\n}'
            if k[0]=='Ntve' and name in {'And','Or'}:
                return '('+(' && ' if name=='And' else ' || ').join(byname.get('cond',[]))+')' if byname.get('cond') else ('true' if name=='And' else 'false')
            self.error('unsupported control-flow template',dd,k)
        if k[0]=='Ntve' and name=='SetVariable' and len(values)==2:return values[0]+' = '+values[1]+';'
        if k[0]=='Ntve' and name=='Return' and len(values)==1:return 'return '+values[0]+';'
        if (k==('Ntve','FunctionDef','7B4A4D9D') and name=='StopLooping' and statement and not values
                and getattr(self,'loop_depth',0)>0
                and (f.findtext('ScriptCode') or '').strip()=='#SMARTBREAK'
                and f.find('FlagAction') is not None and f.find('FlagOperator') is not None
                and f.find('ReturnType') is None):
            return 'break;'
        if (k==('Ntve','FunctionDef','00000139') and name=='SkipRemaining' and not values
                and statement and getattr(self,'void_action_scope',False)
                and (f.findtext('ScriptCode') or '').strip()=='return #DEFRETURN;'
                and f.find('FlagAction') is not None and f.find('FlagOperator') is not None
                and f.find('ReturnType') is None):
            return 'return;'
        if k[0]=='Ntve' and name in {'Comparison','ArithmeticInt','ArithmeticReal'} and len(values)==3:
            if values[1] not in {'==','!=','<','>','<=','>=','+','-','*','/','%'}:self.error('invalid operator',d,key)
            return '('+values[0]+' '+values[1]+' '+values[2]+')'
        if k[0]=='Ntve' and name=='CombineStrings' and len(values)==2 and not statement:
            if ((f.findtext('ScriptCode') or '').strip()!='(#PARAM(str1) + #PARAM(str2))'
                    or f.find('FlagOperator') is None
                    or self.mapping().raw_type(f,dd,k,'ReturnType')!='string'
                    or [pe.findtext('Identifier') for _,_,pe in definitions]!=['str1','str2']
                    or any(self.mapping().raw_type(pe,pd,pk,'ParameterType')!='string' for pd,pk,pe in definitions)):
                self.error('unsupported expression template',dd,k)
            return '('+values[0]+' + '+values[1]+')'
        if k==('Ntve','FunctionDef','A0F31305'):
            if (name!='IncrementInteger' or not statement or len(values)!=3
                    or re.sub(r'\s+','',f.findtext('ScriptCode') or '')!='#PARAM(var)#PARAM(operator)=#PARAM(val);'
                    or f.find('FlagAction') is None or f.find('FlagOperator') is None
                    or f.find('ReturnType') is not None
                    or [pk for pd,pk,pe in definitions]!=[('Ntve','ParamDef','7B3B0884'),('Ntve','ParamDef','5BFF7323'),('Ntve','ParamDef','6725C0EB')]
                    or values[1] not in {'+','-','*','/','%'}):
                self.error('unsupported native IncrementInteger template',dd,k)
            # values[0] must be a direct Variable reference bound to the var Parameter (7B3B0884).
            refs=[]
            for ref in e.findall('Parameter'):
                pd,pk,pe=self.resolve(ref,d,key)
                _,binding_key,_=self.resolve(pe.find('ParameterDef'),pd,pk)
                if binding_key==('Ntve','ParamDef','7B3B0884'):refs.append((pd,pk,pe))
            if len(refs)!=1:self.error('unsupported native IncrementInteger lvalue',d,key)
            pd,pk,pe=refs[0]
            targets=[c for c in pe if c.tag in {'Variable','FunctionCall','Value','Parameter','Preset'}]
            if len(targets)!=1 or targets[0].tag!='Variable':
                self.error('unsupported native IncrementInteger lvalue',d,key)
            vd,vk,ve=self.resolve(targets[0],pd,pk)
            if (vk[1]!='Variable' or self.mapping().type(ve,vd,vk,'VariableType')!='int'
                    or ve.find('VariableType/Constant') is not None):
                self.error('unsupported native IncrementInteger lvalue',d,key)
            return values[0]+' '+values[1]+'= '+values[2]+';'
        if k==('Ntve','FunctionDef','E4B86923'):
            # Exact Ntve StringToText2 E4B86923 is a GUI operator, not a callable native: no Galaxy
            # libNtve_gf_StringToText2 exists and the Editor save shows (UserDataGetUpgrade(...)) for
            # the compiled argument. Exact identity only; any signature/metadata drift fails closed.
            fields={'Identifier','Label','FlagCall','FlagOperator','ReturnType','Parameter'}
            ret=f.find('ReturnType'); label=f.find('Label'); plist=f.findall('Parameter')
            if not (not statement and name=='StringToText2' and len(values)==1
                    and {c.tag for c in f}==fields
                    and all(len(f.findall(t))==1 for t in fields)
                    and all(f.find(t).attrib=={} and len(f.find(t))==0 for t in ('FlagCall','FlagOperator'))
                    and label.attrib=={'Type':'Label','Library':'Ntve','Id':'00000014'}
                    and ret.attrib=={} and [c.tag for c in ret]==['Type']
                    and ret.find('Type').attrib=={'Value':'string'} and len(ret.find('Type'))==0
                    and self.mapping().raw_type(f,dd,k,'ReturnType')=='string'
                    and len(plist)==1
                    and plist[0].attrib=={'Type':'ParamDef','Library':'Ntve','Id':'711D5A26'} and len(plist[0])==0
                    and f.find('FlagNative') is None and f.find('ScriptCode') is None):
                self.error('unsupported native StringToText2 operator template',dd,k)
            pd,pk,pe=definitions[0]
            pkids=pe.findall('Identifier'); ptys=pe.findall('ParameterType')
            if not (pk==('Ntve','ParamDef','711D5A26') and len(pkids)==1 and pkids[0].text=='val'
                    and {c.tag for c in pe}=={'Identifier','ParameterType'}
                    and len(ptys)==1 and ptys[0].attrib=={} and len(ptys[0])==1
                    and [c.tag for c in ptys[0]]==['Type']
                    and ptys[0].find('Type').attrib=={'Value':'anygamelink'} and len(ptys[0].find('Type'))==0
                    and self.mapping().raw_type(pe,pd,pk,'ParameterType')=='anygamelink'
                    and self.mapping().type(pe,pd,pk,'ParameterType')=='string'
                    and self.mapping().aliases.get('anygamelink')=='string'):
                self.error('unsupported native StringToText2 parameter signature',dd,k)
            self.mapping().used.append({'definition':list(k),'name':'StringToText2','kind':'GUI operator',
                                        'path':str(dd.path),'sha256':dd.sha256,'call_site':list(key)})
            return '('+values[0]+')'
        if (k==('Ntve','FunctionDef','86E40471') and name=='CombineText' and not statement
                and len(values)==2
                and re.sub(r'\s+','',f.findtext('ScriptCode') or '')=='(#PARAM(text1)+#PARAM(text2))'
                and f.find('FlagCall') is not None and f.find('FlagOperator') is not None
                and f.find('FlagNative') is None
                and self.mapping().raw_type(f,dd,k,'ReturnType')=='text'
                and [pk for pd,pk,pe in definitions]==[('Ntve','ParamDef','174E8B8C'),('Ntve','ParamDef','BD48D330')]
                and [pe.findtext('Identifier') for _,_,pe in definitions]==['text1','text2']
                and all(self.mapping().raw_type(pe,pd,pk,'ParameterType')=='text' for pd,pk,pe in definitions)):
            # CombineText concatenates already-compiled text handles; no StringToText/TextToString or markup evaluation here.
            return '('+values[0]+' + '+values[1]+')'
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
        previous=getattr(self,'void_action_scope',False)
        previous_depth=getattr(self,'loop_depth',0)
        self.loop_depth=0
        self.void_action_scope=(key[1]=='FunctionDef' and (e.find('ReturnType') is None
                                or e.find('ReturnType/Type') is not None and e.find('ReturnType/Type').get('Value')=='void'))
        temps=[]
        self.foreach_scopes.append(temps)
        # Distinct list for native string Switch selector caches; appended/populated independently of
        # the ForEachInteger int temps above and popped separately in the same finally.
        switchtemps=[]
        self.switch_scopes.append(switchtemps)
        try:
            locals=[]; code=[]
            for ref in e.findall('Variable'):
                vd,vk,v=self.resolve(ref,d,key)
                locals.append(self.typ(v,vd,vk,'VariableType')+' '+self.symbol(vd,vk)+';')
                if v.find('Value') is not None:
                    if v.findall('VariableType/ArraySize'):
                        initial=self.param(v.find('Value'),vd,vk)
                        if initial not in {'""','null'}:self.error('unsupported array initializer',vd,vk)
                    else:code.append(self.symbol(vd,vk)+' = '+self.param(v.find('Value'),vd,vk)+';')
            for ref in list(e):
                if ref.tag in {'Action','FunctionCall'}:
                    cd,ck,c=self.resolve(ref,d,key); code.append(self.call(cd,ck,c))
            # ForEachInteger end caches: declared with the function/trigger locals; their assignments
            # stay in code, i.e. after the trigger guard. The declaration count is reported separately.
            locals.extend('int '+t+';' for t in temps)
            # String selector caches of each Switch in this scope are declared alongside the locals;
            # their assignments stay in code (after the trigger guard) at the original action position.
            locals.extend('string '+t+';' for t in switchtemps)
            self.body_decl_lens[(str(d.path),key)]=len(locals)
            return '\n'.join(locals+code)
        finally:
            self.switch_scopes.pop()
            self.foreach_scopes.pop()
            self.void_action_scope=previous
            self.loop_depth=previous_depth

    def generate(self,proof_token=None, sample_seconds=5, runtime_smoke=False):
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
                    elif k[1]=='Variable':
                        identity=(str(dd.path),k)
                        if identity in self.global_variables:self.error('duplicate global variable declaration',dd,k)
                        self.global_variables[identity]={}
                        globals.append((dd,k,e))
                    elif k[1]=='FunctionDef':self.functions[(str(dd.path),k)]=(dd,k,e)
                    elif k[1] not in {'Comment','Label','Preset'}:self.error('unsupported declaration',dd,k)
            root=d.root.find('Root')
            if root is not None:visit(root,(d.standard,'Root',''))
            for lib in d.root.findall('Library'):
                if lib.find('Root') is not None:visit(lib.find('Root'),(lib.get('Id'),'Root',''))
        # All identities registered first; constants then arrays; never by declaration order.
        self.apply_global_declarations(globals)
        schedule={}
        # Follow component/library load order. A dependency's trigger handles
        # must exist before a dependent map initializes references to them.
        for group in group_order:schedule[group]=[]
        for d,k,e in globals:
            entry=self.global_variables[(str(d.path),k)]
            # Only new support stays out of InitMap: int arrays are naturally zero and Constants
            # are compile-time. Every ordinary scalar keeps its original Param initializer.
            if 'array' in entry or 'constant' in entry:continue
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
            local_count=self.body_decl_lens.get((str(d.path),k),len(e.findall('Variable')))
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
        # Same single string for the emitted (blanked) global and the prelude entry, so a const
        # can never leave a second non-const declaration behind.
        for d,k,e in globals:
            self.emit(self.global_declaration(d,k,e),d,k)
        # Galaxy requires declarations before use: emit prototypes and globals first.
        # source mapping remains stable by adding a separate declarations prelude.
        prelude=[]
        for d,k,e in globals:prelude.append(self.global_declaration(d,k,e))
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
            from .offline_test import proof_lines
            bank_lines=proof_lines(proof_token, sample_seconds) if runtime_smoke else []
            proof=['bool gf_AgentOfflineProof(bool testConds, bool runActions) {', *bank_lines[:1],
                   'if (!runActions) { return true; }',
                   'UIDisplayMessage(PlayerGroupAll(), c_messageAreaChat, StringToText('+json.dumps('GUI_OFFLINE_EXEC_'+proof_token)+'));',
                   *bank_lines[1:], 'return true;','}']
            init.append('TriggerAddEventMapInit(TriggerCreate("gf_AgentOfflineProof"));')
        return {'source':'\n'.join(prelude+self.lines+proof+['void InitMap() {']+init+['}'])+'\n',
                'source_map':self.source_map,'validation':report,'complete':True,
                'used_mappings':self.mapping().used,'resource_inputs':self.resource_inputs}

    def int_array_length(self,array,d,key):
        # ArraySize editor maximum to use as-is (callers add 1), either decimal Value 0..8191 or the
        # reference form <ArraySize Dim="0" Type="Variable" Library=".." Id=".."/> with no children,
        # resolved and looked up by (path,key) in registered global int Constants.
        if set(array.attrib)=={'Dim','Value'} and len(array)==0:
            if array.get('Dim')!='0' or not re.fullmatch('[0-9]+',array.get('Value','')) or int(array.get('Value'))>8191:self.error('unsupported array type',d,key)
            return int(array.get('Value'))
        if set(array.attrib)=={'Dim','Type','Library','Id'} and len(array)==0 and array.get('Dim')=='0' and array.get('Type')=='Variable' and (array.get('Id') or '').strip()=='':
            self.error('unsupported array type',d,key)
        if set(array.attrib)!={'Dim','Type','Library','Id'} or len(array) or array.get('Dim')!='0' or array.get('Type')!='Variable':self.error('unsupported array type',d,key)
        dd,k,_=self.resolve(array,d,key)
        literal=self.global_constants.get((str(dd.path),k))
        if literal is None:self.error('array length must be a registered global constant int',d,key)
        return literal

    def int_zero_initializer(self,d,key,ref,what):
        # Only a Param holding exactly int Value 0 is a natural zero initializer; anything else
        # (FunctionCall/Preset/Variable, or an expression that merely evaluates to 0) fails.
        # Nothing is compiled or evaluated; the result is only a validation.
        if ref is None or set(ref.attrib)!={'Type','Library','Id'} or len(ref) or ref.get('Type')!='Param' or (ref.get('Id') or '').strip()=='':self.error('unsupported '+what,d,key)
        pd,pk,pe=self.resolve(ref,d,key)
        if pe is None or pk[1]!='Param' or set(c.tag for c in pe)-{'ParameterDef','Value','ValueType'}:self.error('unsupported '+what,d,key)
        values=pe.findall('Value'); types=pe.findall('ValueType')
        if len(values)!=1 or len(types)!=1:self.error('unsupported '+what,d,key)
        if values[0].attrib or len(values[0]) or (values[0].text or '')!='0':self.error('unsupported '+what,d,key)
        if set(types[0].attrib)!={'Type'} or types[0].get('Type')!='int' or len(types[0]) or (types[0].text or '').strip()!='':self.error('unsupported '+what,d,key)
        return 0

    def apply_global_declarations(self,globals):
        # Pass 1 validates and registers every Constant int (all identities already exist).
        for d,k,e in globals:
            vt=e.find('VariableType')
            if vt is not None and vt.find('Constant') is not None:self.constant_literal(d,k,e)
        # Pass 2 handles arrays: Constant-length references resolve into the pass-1 registry no
        # matter where the Constant is declared. String/gamelink/multi-dimensional/dynamic fail
        # with the original 'global arrays unsupported'.
        for d,k,e in globals:
            vt=e.find('VariableType')
            if vt is None or vt.find('Constant') is not None:continue
            arrays=vt.findall('ArraySize')
            if not arrays:continue
            if len(arrays)!=1:self.error('duplicate ArraySize',d,k)
            heads=vt.findall('Type')
            if (len(heads)!=1 or set(heads[0].attrib)!={'Value'} or len(heads[0]) or heads[0].get('Value')!='int'
                    or vt.find('TypeElement') is not None or vt.find('GameType') is not None
                    or not (arrays[0].get('Dim') or '').strip()):
                self.error('global arrays unsupported',d,k)
            bound=self.int_array_length(arrays[0],d,k)
            value=e.find('Value')
            if value is not None:self.int_zero_initializer(d,k,value,'global int array initializer')
            # Natural zero: recorded only, never scheduled as a whole-array assignment.
            self.global_variables[(str(d.path),k)]['array']=bound

    def constant_literal(self,d,key,e):
        # A Constant is accepted only as VariableType exactly <Type Value="int"|"fixed"/><Constant/>
        # whose Value is a Param with exactly one matching ValueType and one plain decimal literal.
        # int: signed 32-bit plain decimal (-2147483648..2147483647); only the array-eligible subset
        # 0..8191 is registered in global_constants for array dimensions, while every int literal is
        # registered as a `constant` declaration. fixed: any plain decimal spelling (optionally
        # signed), kept verbatim and registered only as a `constant` declaration; it never enters
        # global_constants, so it can never act as an array dimension.
        identity=(str(d.path),key)
        vt=e.find('VariableType')
        heads=vt.findall('Type') if vt is not None else []
        constants=vt.findall('Constant') if vt is not None else []
        if (len(heads)!=1 or set(heads[0].attrib)!={'Value'} or len(heads[0])
                or heads[0].get('Value') not in {'int','fixed'}
                or len(constants)!=1 or constants[0].attrib or len(constants[0])
                or {c.tag for c in vt}!={'Type','Constant'}):
            self.error('unsupported constant type',d,key)
        name=heads[0].get('Value')
        value=e.find('Value')
        if value is None or set(value.attrib)!={'Type','Library','Id'} or len(value) or value.get('Type')!='Param' or (value.get('Id') or '').strip()=='':self.error('unsupported constant value',d,key)
        pd,pk,pe=self.resolve(value,d,key)
        if pe is None or pk[1]!='Param' or set(c.tag for c in pe)-{'ParameterDef','Value','ValueType'}:self.error('unsupported constant value',d,key)
        literals=pe.findall('Value'); types=pe.findall('ValueType')
        if len(literals)!=1 or len(types)!=1:self.error('unsupported constant value',d,key)
        text=literals[0].text or ''
        if name=='int':
            # Plain optional-minus decimal only; no space, plus, exponent, decimals or expression.
            if literals[0].attrib or len(literals[0]) or not re.fullmatch('-?[0-9]+',text) or not -2147483648<=int(text)<=2147483647:self.error('unsupported constant value',d,key)
        elif literals[0].attrib or len(literals[0]) or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',text):
            # Plain decimal only: no exponent, sign duplication, nan/inf, trailing/leading dots or spacing.
            self.error('unsupported constant value',d,key)
        if set(types[0].attrib)!={'Type'} or types[0].get('Type')!=name or len(types[0]) or (types[0].text or '').strip()!='':self.error('unsupported constant value',d,key)
        if name=='int':
            literal=int(text)
            # Only the array-eligible 0..8191 subset is a candidate array dimension; every int
            # Constant (including signed/negative/oversize) is still a valid const declaration.
            if 0<=literal<=8191:self.global_constants[identity]=literal
            self.global_variables[identity]['constant']=literal
        else:
            self.global_variables[identity]['constant']=text

    def global_declaration(self,d,key,e):
        # Single declaration text for both the emitted global and the prelude; a registered int
        # Constant is declared once as `const int symbol = literal;` and never in InitMap.
        identity=(str(d.path),key)
        entry=self.global_variables.get(identity) or {}
        base=self.typ(e,d,key,'VariableType')+' '+self.symbol(d,key)
        if 'constant' in entry:return 'const '+base+' = '+str(entry['constant'])+';'
        return base+';'
