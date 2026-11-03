"""Stage an independent Mod-link acceptance pair from an Editor-saved matrix.

Creates new workspace candidates only. Deploy the staged Mod using the normal
deploy-mod.py tool, then save that deployed Mod in the Editor before its map.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET

WORKSPACE=next(p for p in Path(__file__).resolve().parents if (p/'tools/sc2_triggers.py').is_file())
MOD_NAME='CodexGuiLinkAcceptance.SC2Mod'
LIB='AC040001'


def write_xml(path,root):
    ET.indent(root)
    path.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))


def validate_mod_template(template):
    """Require a provided Editor-saved shell; never synthesize opaque metadata."""
    if template.suffix.lower()!='.sc2mod' or not template.is_dir():
        raise ValueError('an Editor-saved Components .SC2Mod template is required')
    required=['DocumentHeader','ComponentList.SC2Components','DocumentInfo','DocumentInfo.version','Triggers','Triggers.version','GameText.version']
    missing=[name for name in required if not (template/name).is_file()]
    if missing:raise ValueError('native Mod shell incomplete: '+', '.join(missing))
    components=ET.parse(template/'ComponentList.SC2Components').getroot()
    if not components.findall("DataComponent[@Type='trig']") or not components.findall("DataComponent[@Type='info']"):
        raise ValueError('native shell must register info and trig components; save a ShellMarker GUI action first')
    for component in components.findall("DataComponent[@Type='text']"):
        locale=component.get('Locale','')
        if locale not in {'enUS','zhCN'}:raise ValueError('acceptance shell requires enUS/zhCN locales')
        if not (template/(locale+'.SC2Data')/'LocalizedData').is_dir():raise ValueError('registered text component missing: '+locale)
    if any((template/name).stat().st_size==0 for name in required):raise ValueError('native shell metadata cannot be empty')


def prepare(source,destination,mod_template,mod_name=MOD_NAME):
    source=source.resolve();destination=destination.resolve()
    if destination.exists() or not destination.is_relative_to(WORKSPACE):
        raise ValueError('destination must be a NEW workspace directory')
    if Path(mod_name).name!=mod_name or not mod_name.endswith('.SC2Mod') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.' for c in mod_name):
        raise ValueError('invalid test Mod filename')
    mod_template=mod_template.resolve();validate_mod_template(mod_template)
    raw=(source/'Triggers').read_bytes();tree=ET.fromstring(raw)
    libraries=tree.findall('Library')
    if len(libraries)!=1:raise ValueError('source must be the accepted single-library matrix')
    library=libraries[0];old=library.get('Id')
    if tree.find("Element[@Type='Trigger']/Identifier").text!='MatrixInit':
        raise ValueError('source is not the matrix acceptance map')
    for element in tree.iter():
        if element.get('Library')==old:element.set('Library',LIB)
    library.set('Id',LIB)
    tree.remove(library)
    mod_tree=ET.Element('TriggerData');mod_tree.append(library)
    mod=destination/'Mods'/mod_name;mod.parent.mkdir(parents=True)
    shutil.copytree(mod_template,mod,ignore=shutil.ignore_patterns('.sc2-mcp','_codex_backups'))
    map_root=destination/'GuiModLink.SC2Map'
    shutil.copytree(source,map_root,ignore=shutil.ignore_patterns('.sc2-mcp','_codex_backups'))
    write_xml(mod/'Triggers',mod_tree);write_xml(map_root/'Triggers',tree)
    # Keep the native template's dependency identity and component ordering.
    # The shell must use the intended Liberty baseline before staging.
    map_info=ET.Element('DocInfo');deps=ET.SubElement(map_info,'Dependencies')
    ET.SubElement(deps,'Value').text='file:Mods/'+mod_name
    write_xml(map_root/'DocumentInfo',map_info)
    components=ET.parse(mod/'ComponentList.SC2Components').getroot()
    locales=[e.get('Locale') for e in components.findall("DataComponent[@Type='text']")]
    if not locales:raise ValueError('native Mod shell must include a saved text component')
    for locale in locales:
        folder=mod/(locale+'.SC2Data')/'LocalizedData';folder.mkdir(parents=True,exist_ok=True)
        names=source/(locale+'.SC2Data')/'LocalizedData/TriggerStrings.txt'
        values=names.read_text(encoding='utf-8-sig').splitlines() if names.is_file() else []
        selected=[line.replace('lib_'+old+'_','lib_'+LIB+'_') for line in values if 'lib_'+old+'_' in line]
        selected.insert(0,'Library/Name/'+LIB+'=Mod Link Helpers')
        (folder/'TriggerStrings.txt').write_text('\n'.join(selected)+'\n',encoding='utf-8')
        strings=folder/'GameStrings.txt'
        text=strings.read_text(encoding='utf-8-sig') if strings.is_file() else ''
        if 'DocInfo/Name=' not in text:text+='\nDocInfo/Name=Codex GUI Link Acceptance\n'
        strings.write_text(text,encoding='utf-8')
    for locale in ('enUS','zhCN'):
        map_text=map_root/(locale+'.SC2Data')/'LocalizedData/GameStrings.txt'
        if map_text.is_file():
            text=map_text.read_text(encoding='utf-8-sig').replace('GUI_MATRIX_ALL_PASS','GUI_MODLINK_ALL_PASS').replace('GUI_MATRIX_ALL_FAIL','GUI_MODLINK_ALL_FAIL').replace('GUI_MATRIX_CROSSLIB_PASS','GUI_MODLINK_CALL_PASS')
            map_text.write_text(text,encoding='utf-8')
    # Header, version sidecars, component list and dependency info stay byte-exact.
    result={'source_matrix_sha256':hashlib.sha256(raw).hexdigest(),'staged_mod':str(mod),
            'map':str(map_root),'mod_name':mod_name,'library_id':LIB,
            'expected':'GUI_MODLINK_ALL_PASS','scope':'map-to-independent-Mod GUI action and shared variable',
            'native_mod_template':str(mod_template),
            'native_shell_hashes':{name:hashlib.sha256((mod/name).read_bytes()).hexdigest() for name in ['DocumentHeader','ComponentList.SC2Components','DocumentInfo','DocumentInfo.version','Triggers.version','GameText.version']},
            'Editor accepted':False,'packaged runtime passed':False,
            'editor_steps':['Save deployed test Mod as Components','Close Mod','Open and save GuiModLink.SC2Map','Ctrl+F9 and observe GUI_MODLINK_ALL_PASS']}
    (destination/'modlink-handoff.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--mod-template',type=Path,required=True)
    p.add_argument('--mod-name',default=MOD_NAME)
    args=p.parse_args();print(json.dumps(prepare(args.source,args.destination,args.mod_template,args.mod_name),indent=2))
