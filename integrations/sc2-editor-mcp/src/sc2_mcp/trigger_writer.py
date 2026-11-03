"""In-memory GUI edits. Only the transaction layer may commit these bytes."""
from __future__ import annotations
import re
from xml.etree import ElementTree as ET
from .errors import SC2Error
from .storage import digest, safe_path

TYPES = {'Category', 'Variable', 'FunctionDef', 'ParamDef', 'Trigger', 'FunctionCall', 'Param'}
ID = re.compile(r'[0-9A-Fa-f]{8}\Z')
TAG = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')


def _matches(pattern,text):
    # Comments/CDATA are opaque; local edits cannot enter nested libraries.
    opaque=[(m.start(),m.end()) for m in re.finditer(r'<!--.*?-->|<!\[CDATA\[.*?\]\]>',text,re.S)]
    nested=[] if text.lstrip().startswith('<Library') else [(m.start(),m.end()) for m in re.finditer(r'<Library\b[^>]*>.*?</Library>',text,re.S)]
    return [m for m in re.finditer(pattern,text,re.S) if not any(a<=m.start()<b for a,b in opaque+nested)]


def fail(message, **details):
    raise SC2Error('trigger_write_invalid', message, **details)


def validate_editor_library_layout(root):
    """Conservative supported shape from saved maps, not an engine-wide schema."""
    children=list(root)
    map_root=root.find('Root')
    for library in root.findall('Library'):
        if map_root is not None and children.index(library)>children.index(map_root):
            fail('unsupported Editor library layout: Library must precede map Root',library=library.get('Id'))
        for item in library.findall('Root/Item'):
            if not item.get('Library'):
                fail('unsupported Editor library registration: explicit Library required',library=library.get('Id'),id=item.get('Id'))


def node(data):
    if set(data) - {'tag', 'attributes', 'text', 'children'}:
        fail('unknown node fields')
    tag = data.get('tag', '')
    if not TAG.fullmatch(tag) or tag == 'Element':
        fail('invalid child tag')
    attrs = data.get('attributes', {})
    if any(not TAG.fullmatch(k) or not isinstance(v, str) for k,v in attrs.items()):
        fail('invalid child attributes')
    e = ET.Element(tag, attrs)
    e.text = data.get('text')
    for child in data.get('children', []):
        e.append(node(child))
    return e


def _replace_container(text, library, fn):
    pattern = r'<Library\b[^>]*\bId=[\"\']' + re.escape(library) + r'[\"\'][^>]*>.*?</Library>' if library else r'\A.*\Z'
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1:
        fail('missing or ambiguous library', library=library)
    m = matches[0]
    return text[:m.start()] + fn(m.group()) + text[m.end():]


def _upsert(text, typ, ident, xml, newline):
    matches=[]
    for m in _matches(r'<Element\b[^>]*?(?:/>|>.*?</Element>)', text):
        e=ET.fromstring(m.group())
        if (e.get('Type'),e.get('Id')) == (typ,ident): matches.append(m)
    if len(matches)>1: fail('duplicate source ID', id=ident)
    if matches:
        m=matches[0]; return text[:m.start()] + xml + text[m.end():]
    end=text.rfind('</Library>') if text.lstrip().startswith('<Library') else text.rfind('</TriggerData>')
    if end<0: fail('unsupported trigger container')
    return text[:end]+xml+newline+text[end:]


def plan_write(root, operations, expected_sha256=None, locale='zhCN'):
    path=safe_path(root,'Triggers'); raw=path.read_bytes()
    if expected_sha256 is not None and digest(raw)!=expected_sha256:
        fail('source fingerprint changed')
    if not re.fullmatch(r'[a-z]{2}[A-Z]{2}',locale): fail('invalid locale')
    bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text=raw.decode('utf-8-sig'); newline='\r\n' if '\r\n' in text else '\n'
    tree=ET.fromstring(text)
    if tree.tag!='TriggerData': fail('expected TriggerData')
    seen=set(); names={}; game_strings={}
    for op in operations:
        if set(op)-{'type','id','library','children','name','owner','index','strings'}: fail('unknown operation fields')
        for anchor,value in op.get('strings',{}).items():
            if not isinstance(anchor,str) or not anchor or any(c in anchor for c in '=\r\n\x00') or not isinstance(value,str) or any(c in value for c in '\r\n\x00'):
                fail('invalid GameStrings anchor/value')
            if anchor in game_strings and game_strings[anchor]!=value:fail('conflicting GameStrings values')
            game_strings[anchor]=value
        typ=op.get('type'); ident=op.get('id',''); lib=op.get('library','')
        if not isinstance(lib,str) or (lib and not re.fullmatch('[A-Za-z0-9_]+',lib)):fail('invalid library ID')
        if typ not in TYPES or not ID.fullmatch(ident): fail('unsupported type or invalid ID')
        key=(lib,typ,ident)
        if key in seen: fail('duplicate operation ID',id=ident)
        seen.add(key)
        element=ET.Element('Element',{'Type':typ,'Id':ident})
        for child in op.get('children',[]): element.append(node(child))
        xml=ET.tostring(element,encoding='unicode').replace('\n',newline)
        text=_replace_container(text,lib,lambda t:_upsert(t,typ,ident,xml,newline))
        if 'name' in op:
            name=op['name']
            if not isinstance(name,str) or any(c in name for c in '\r\n\x00'): fail('invalid name')
            names[f'{typ}/Name/'+(f'lib_{lib}_' if lib else '')+ident]=name
        # Declaration membership is explicit, except top-level GUI objects.
        owner=op.get('owner')
        if owner is None and typ in {'Category','Trigger','FunctionDef','Variable'}:
            owner={'type':'Root'}
        if owner:
            owner_type=owner.get('type'); owner_id=owner.get('id')
            if owner_type not in {'Root','Category','Trigger','FunctionDef'}: fail('invalid owner')
            def register(t):
                pattern=r'<Root\b[^>]*?(?:/>|>.*?</Root>)' if owner_type=='Root' else r'<Element\b[^>]*?(?:/>|>.*?</Element>)'
                found=[]
                for m in _matches(pattern,t):
                    e=ET.fromstring(m.group())
                    if owner_type=='Root' or (e.get('Type'),e.get('Id'))==(owner_type,owner_id):found.append((m,e))
                if len(found)!=1: fail('missing or ambiguous owner')
                m,e=found[0]
                tag='Item' if owner_type in {'Root','Category'} else ('Parameter' if typ=='ParamDef' else 'Variable')
                if tag=='Variable' and typ!='Variable': fail('invalid declaration membership')
                old=[c for c in e if c.tag==tag and c.get('Type')==typ and c.get('Id')==ident]
                if len(old)>1: fail('duplicate membership')
                if old and 'index' not in op and (not lib or old[0].get('Library')==lib): return t
                old_index=list(e).index(old[0]) if old else len(e)
                for c in old:e.remove(c)
                ref=ET.Element(tag,{'Type':typ,'Id':ident,**({'Library':lib} if lib else {})})
                index=op.get('index',old_index)
                if not isinstance(index,int) or not 0<=index<=len(e):fail('invalid insertion index')
                e.insert(index,ref)
                # Membership changes preserve all untouched owner bytes/comments.
                original=m.group()
                ref_xml=ET.tostring(ref,encoding='unicode')
                if 'index' not in op and not old:
                    if original.rstrip().endswith('/>'):
                        replacement=original.rstrip()[:-2]+'>'+ref_xml+'</'+('Root' if owner_type=='Root' else 'Element')+'>'
                    else:
                        end=original.rfind('</');replacement=original[:end]+ref_xml+original[end:]
                else:
                    replacement=ET.tostring(e,encoding='unicode')
                return t[:m.start()]+replacement+t[m.end():]
            text=_replace_container(text,lib,register)
    result={'Triggers':bom+text.encode('utf-8')}
    for filename,values in [('TriggerStrings.txt',names),('GameStrings.txt',game_strings)]:
        if not values:continue
        relative=f'{locale}.SC2Data/LocalizedData/{filename}'
        p=safe_path(root,relative); old=p.read_bytes() if p.exists() else b''
        sbom=b'\xef\xbb\xbf' if old.startswith(b'\xef\xbb\xbf') else b''
        st=old.decode('utf-8-sig'); snl='\r\n' if '\r\n' in st else newline
        for key,value in values.items():
            pattern=r'(?m)^'+re.escape(key)+r'=[^\r\n]*'
            if len(re.findall(pattern,st))>1:fail('duplicate string anchor',key=key)
            if re.search(pattern,st):st=re.sub(pattern,lambda _:key+'='+value,st)
            else:st+=('' if not st or st.endswith('\n') else snl)+key+'='+value+snl
        result[relative]=sbom+st.encode('utf-8')
    return {k:v for k,v in result.items() if not safe_path(root,k).exists() or safe_path(root,k).read_bytes()!=v}
