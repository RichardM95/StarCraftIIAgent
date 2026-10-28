"""Merge only authored component layers; never copy dependency definitions."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from sc2_archive import scan, allowed_target, no_links
from sc2_components import require_editable
from sc2_migrate import decode, safe_relative
from sc2_migrate_catalog import digest, family
from sc2_publication import staged_directory, publish_component

VERSION=1
EXCLUDED_SUFFIXES={'.galaxy','.sc2layout','.sc2style','.sc2lib','.triggerlib'}


def xml_root(path):
    parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,insert_pis=True))
    return ET.fromstring(Path(path).read_bytes(),parser=parser)


def canonical(node):
    if not isinstance(node.tag,str):
        return None
    return (node.tag,tuple(sorted(node.attrib.items())),(node.text or '').strip(),
            tuple(canonical(c) for c in node if isinstance(c.tag,str)))


def catalog_rows(root):
    rows={};empty=[]
    directory=root/'Base.SC2Data/GameData'
    for path in sorted(directory.rglob('*.xml')) if directory.is_dir() else []:
        document=xml_root(path)
        if document.tag!='Catalog' or document.attrib:
            raise ValueError('Only plain local Catalog files are supported: '+str(path))
        count=0
        for node in document:
            if not isinstance(node.tag,str):
                continue
            if node.tag.startswith('C') and (node.get('id') is not None or node.get('default')=='1'):
                fam=family(node.tag)
                identifier=node.get('id', '@default:'+node.tag)
            elif node.tag=='const' and node.get('id'):
                fam='Game';identifier='@const:'+node.get('id')
            else:
                raise ValueError('Unsupported catalog operation: '+str(path)+': '+node.tag)
            key=(fam,identifier)
            if key in rows:
                raise ValueError('Ambiguous duplicate within one source: '+str(root)+': '+str(key))
            rows[key]={'node':copy.deepcopy(node),'file':path.relative_to(root).as_posix(),
                       'source':str(root),'tag':node.tag}
            count+=1
        if not count:
            empty.append(path.relative_to(root).as_posix())
    return rows,empty


def payload_kind(relative):
    path=Path(relative);parts=path.parts
    lower=relative.replace('\\','/').lower()
    if (path.suffix.lower() in EXCLUDED_SUFFIXES or path.name in {'Triggers','LibraryList.xml'}
            or lower.startswith(('base.sc2data/scripts/','base.sc2data/triggerlibs/','base.sc2data/ui/','ui/'))):
        return 'wiring'
    if lower.startswith('base.sc2data/gamedata/') and path.suffix.lower()=='.xml':
        return 'catalog'
    if re.fullmatch(r'[a-z]{4}\.sc2data/localizeddata/[^/]+\.txt',lower):
        return 'text'
    if lower.startswith(('assets/','base.sc2assets/')) or re.match(r'[a-z]{4}\.sc2assets/',lower):
        return 'asset'
    return 'metadata'


def text_entries(path):
    text,encoding,bom=decode(path.read_bytes())
    entries={}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(('//','#')):
            continue
        if '=' not in line:
            raise ValueError('Non-entry line in localization file: '+str(path)+': '+line[:80])
        key,value=line.split('=',1)
        entries[key]=value
    return entries,encoding,bom,'\r\n' if '\r\n' in text else '\n'


def component_validation(path):
    source=Path(__file__).with_name('validate-mod.py')
    spec=importlib.util.spec_from_file_location('mod_layer_validator',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    issues,status=module.validate_xml_catalogs(path)
    return {'issues':issues,'xsd':status,'passed':not issues}


def build_plan(sources,target,work_dir):
    """Later sources win complete rows, resource files and text key values."""
    sources=[Path(p).resolve() for p in sources];target=Path(target).resolve();work_dir=Path(work_dir).resolve()
    if not sources or len(set(sources))!=len(sources):
        raise ValueError('Pass distinct sources in low-to-high priority order')
    for root in [*sources,target]:
        require_editable(root);no_links(root)
        if not root.is_dir() or root.suffix.lower()!='.sc2mod':
            raise ValueError('A Components SC2Mod directory is required: '+str(root))
        if work_dir==root or work_dir.is_relative_to(root) or root.is_relative_to(work_dir):
            raise ValueError('Work directory must be disjoint from all components')
    if any(target==p or target.is_relative_to(p) or p.is_relative_to(target) for p in sources):
        raise ValueError('Sources and target must be disjoint')
    if work_dir.exists():
        raise FileExistsError('Work directory must be new: '+str(work_dir))
    snapshots={str(p):scan(p) for p in [*sources,target]}
    records={};assets={};texts={};conflicts=[];wiring=[];empty=[];counts=[]
    for priority,root in enumerate([target,*sources]):
        rows,empty_files=catalog_rows(root)
        empty.extend({'source':str(root),'file':f} for f in empty_files)
        for key,row in rows.items():
            old=records.get(key)
            if old and canonical(old['node'])!=canonical(row['node']):
                conflicts.append({'kind':'catalog','family':key[0],'id':key[1],
                                  'overridden_source':old['source'],'winner':str(root)})
            records[key]=row
        entry=snapshots[str(root)]['entries']
        local_counts=Counter()
        for relative,metadata in entry.items():
            if metadata['kind']!='file':
                continue
            kind=payload_kind(relative);path=root/relative;local_counts[kind]+=1
            if kind=='asset':
                identity=relative.casefold()
                old=assets.get(identity)
                if old and old['sha256']!=metadata['sha256']:
                    conflicts.append({'kind':'asset','path':relative,'overridden_source':old['source'],'winner':str(root)})
                assets[identity]={'path':relative,'source':str(root),'sha256':metadata['sha256']}
            elif kind=='text':
                identity=relative.casefold()
                values,encoding,bom,newline=text_entries(path)
                merged=texts.setdefault(identity,{'path':relative,'entries':{},'owners':{}})
                for key,value in values.items():
                    old=merged['entries'].get(key)
                    if key in merged['entries'] and old!=value:
                        conflicts.append({'kind':'text','file':relative,'key':key,
                                          'overridden_source':merged['owners'][key],'winner':str(root)})
                    merged['entries'][key]=value;merged['owners'][key]=str(root)
                merged.update(encoding=encoding,bom=bom,newline=newline)
            elif kind=='wiring' and priority:
                wiring.append({'source':str(root),'path':relative,'sha256':metadata['sha256']})
        if priority:
            declarations=xml_root(root/'DocumentInfo').find('Dependencies')
            counts.append({'source':str(root),'catalog_entries':len(rows), 'files':dict(local_counts),
                           'declared_dependencies':[] if declarations is None else [n.text for n in declarations]})
    work_dir.mkdir(parents=True)
    stage=work_dir/'component.SC2Mod'
    shutil.copytree(target,stage)
    # Remove only catalog files in the private copy. A single typed row is emitted
    # for each selected object, so no file-order inference or patch flattening occurs.
    for path in (stage/'Base.SC2Data/GameData').rglob('*.xml') if (stage/'Base.SC2Data/GameData').is_dir() else []:
        path.unlink()
    groups=defaultdict(list)
    for (fam,identifier),record in sorted(records.items()):
        groups[fam].append(record['node'])
    data=stage/'Base.SC2Data/GameData';data.mkdir(parents=True,exist_ok=True)
    for fam,nodes in groups.items():
        document=ET.Element('Catalog')
        document.extend(copy.deepcopy(nodes))
        ET.indent(document,space='    ')
        (data/(fam+'Data.xml')).write_bytes(ET.tostring(document,encoding='utf-8',xml_declaration=True)+b'\n')
    # Any custom old include registry refers to replaced files. Current layer mode
    # only accepts the conventional typed catalog directory, not custom data spaces.
    if (stage/'Base.SC2Data/GameData.xml').exists():
        raise ValueError('Custom GameData include registry requires explicit migration')
    for row in assets.values():
        destination=stage/str(safe_relative(row['path']));destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(row['source'])/row['path'],destination)
        if digest(destination.read_bytes())!=row['sha256']:
            raise ValueError('Asset copy verification failed: '+row['path'])
    locales=set()
    for row in texts.values():
        path=stage/str(safe_relative(row['path']));path.parent.mkdir(parents=True,exist_ok=True)
        text=''.join(key+'='+value+row['newline'] for key,value in sorted(row['entries'].items()))
        path.write_bytes(bytes.fromhex(row['bom'])+text.encode(row['encoding']))
        locales.add(Path(row['path']).parts[0].split('.')[0])
    registration=stage/'ComponentList.SC2Components'
    doc=xml_root(registration)
    existing={n.get('Locale','').casefold() for n in doc if n.get('Type')=='text'}
    for locale in sorted(locales):
        if locale.casefold() not in existing:
            ET.SubElement(doc,'DataComponent',{'Type':'text','Locale':locale}).text='GameText'
    registration.write_bytes(ET.tostring(doc,encoding='utf-8',xml_declaration=True)+b'\n')
    if (stage/'DocumentInfo').read_bytes()!=(target/'DocumentInfo').read_bytes():
        raise ValueError('Target dependency declaration was changed')
    validation=component_validation(stage)
    plan={'schema_version':VERSION,'kind':'sc2_mod_layer_merge','sources':list(map(str,sources)),
          'target':str(target),'stage':str(stage),'priority':'later_source_wins_complete_definition',
          'snapshots':snapshots,'source_summary':counts,'conflicts':conflicts,'excluded_wiring':wiring,
          'empty_catalogs_skipped':empty,'validation':validation,
          'catalog_providers':{fam+':'+oid:{k:v for k,v in row.items() if k!='node'} for (fam,oid),row in records.items()},
          'summary':{'catalog_entries':len(records),'catalog_files':len(groups),'assets':len(assets),
                     'localized_files':len(texts),'localized_entries':sum(len(v['entries']) for v in texts.values()),
                     'catalog_conflicts':sum(c['kind']=='catalog' for c in conflicts),
                     'asset_conflicts':sum(c['kind']=='asset' for c in conflicts),
                     'text_conflicts':sum(c['kind']=='text' for c in conflicts),'excluded_wiring':len(wiring)},
          'dependency_policy':'unchanged; missing official references are retained',
          'official_dependency_payload_copied':False}
    plan['stage_snapshot']=scan(stage)
    for root,expected in snapshots.items():
        if scan(Path(root))!=expected:
            raise ValueError('Input changed while preparing merge: '+root)
    plan['plan_id']=digest(plan)
    (work_dir/'layer-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(plan,work_dir/'report.md')
    return plan


def write_report(plan,path):
    lines=['# 模组本地数据层迁移','', '目标：'+plan['target'],'',
           '优先级（低到高）：'+' → '.join(Path(p).stem for p in plan['sources']),
           '同名对象采用最高优先级来源的完整本地条目。保留原 ID、parent、令牌、数组操作及官方引用，不展开继承值。',
           '仅迁移来源目录中的 Catalog、素材和本地化；未复制官方依赖内容。目标 DocumentInfo 保持原字节。','',
           '## 数量','']+['- '+key+': '+str(value) for key,value in plan['summary'].items()]
    lines+=['','## 官方依赖差异','']
    for source in plan['source_summary']:
        lines.append('- '+Path(source['source']).stem+': '+'; '.join(source['declared_dependencies']))
    lines+=['','来源使用的战役依赖未加入目标。缺失的官方对象、字符串、模型和声音引用仍保留；可被目标已有依赖满足的内容不会复制。',
            '完整未满足引用清单在本目录的依赖审计 JSON 中。','','## 未接入内容','']
    lines+=['- '+Path(row['source']).stem+'/'+row['path'] for row in plan['excluded_wiring']]
    lines+=['','以上触发器、Galaxy、UI 与库登记未复制。相关 Catalog/文本引用原样保留，运行机制需要另行接线。','',
            '## 验证','', 'Catalog XML: '+('static validation passed' if plan['validation']['passed'] else 'failed'),
            '未取得 Editor accepted 或 packaged runtime passed。回滚使用实际应用结果中记录的完整备份。','']
    Path(path).write_text('\n'.join(lines),encoding='utf-8')


def apply_plan(path,*,apply=False,before_publish=None):
    path=Path(path).resolve();plan=json.loads(path.read_text(encoding='utf-8'))
    if plan.get('schema_version')!=VERSION or plan.get('kind')!='sc2_mod_layer_merge':
        raise ValueError('Unsupported local-layer merge plan')
    if digest({k:v for k,v in plan.items() if k!='plan_id'})!=plan.get('plan_id'):
        raise ValueError('Layer plan integrity mismatch')
    target=Path(plan['target']);stage=Path(plan['stage'])
    allowed_target(target);no_links(stage)
    if stage!=path.parent/'component.SC2Mod' or not stage.is_dir():
        raise ValueError('Unowned staging path')
    for root,expected in plan['snapshots'].items():
        if scan(Path(root))!=expected:
            raise ValueError('Input changed before apply: '+root)
    if scan(stage)!=plan['stage_snapshot']:
        raise ValueError('Staged component changed since plan')
    current=component_validation(stage)
    if not current['passed']:
        raise ValueError('Staged Catalog validation failed: '+str(current['issues'][:8]))
    if not apply:
        return {'applied':False,'summary':plan['summary'],'stage':str(stage),'validation':current}
    from sc2_paths import load_project_config,project_identity_path,find_project_mods
    workspace=Path(__file__).resolve().parents[1];config=load_project_config(workspace)
    if config.get('project',{}).get('source_mode')=='workspace_copy' and project_identity_path(workspace,config)==target:
        actual=find_project_mods(workspace,config=config)
        if not actual or actual[0].resolve()!=target.resolve():
            raise ValueError('Target is a deployed copy; merge into the configured editing source')
    with staged_directory(target) as temporary:
        publish=temporary/target.name
        shutil.copytree(stage,publish)
        if scan(publish)!=plan['stage_snapshot']:
            raise ValueError('Publication copy verification failed')
        if before_publish:
            before_publish(publish)
        for root,expected in plan['snapshots'].items():
            if scan(Path(root))!=expected:
                raise ValueError('Input changed during publication: '+root)
        backup=publish_component(publish,target,expected=plan['snapshots'][str(target)],fingerprint=scan)
    result={'applied':True,'target':str(target),'backup':str(backup),'plan_id':plan['plan_id'],
            'summary':plan['summary'],'status':'source fixed',
            'catalog_xml_status':'static validation passed',
            'official_dependency_payload_copied':False,'editor_accepted':False,'packaged_runtime_passed':False}
    (path.parent/'applied.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
