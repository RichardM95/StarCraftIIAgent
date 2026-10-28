"""Application layer: project-scoped tools, transaction routing and evidence."""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, archives, assets, catalog, data_warnings, dependencies, editor, localization, map_shell, script, spatial, terrain_capability
from .errors import SC2Error
from .jobs import Jobs
from .projects import Projects, KEYSTONE
from .storage import atomic_write, digest, file_lock, map_files, safe_path, snapshot, write_json
from .terrain import Terrain, plan_terrain, render_terrain
from .transactions import Transactions
from .validation import inspect_project, validate_changes


class Service:
    def __init__(self, state: Path):
        self.state=Path(state).resolve()
        self.state.mkdir(parents=True,exist_ok=True)
        self.projects=Projects(self.state)
        self.transactions=Transactions(self.state)
        self.jobs=Jobs(self.state)
        from .probes import Probes
        self.probes=Probes(self.state)

    def capabilities(self):
        return {
            'name':'sc2-editor','version':__version__,'transport':'stdio','model_required':False,
            'state':str(self.state),'mouse_keyboard_control':False,
            'modules':{
                'projects':{'status':'implemented','features':['component maps/mods','MPQ work copies','hash-bound templates','independent export']},
                'terrain':{'status':'experimental','write_default':'candidate_only',
                    'formats':['XML115','HMAP101','SMAP102','CLIF100','LFCT102','MASK102 tiled64','RTXT101'],
                    'operations':['raise','set_height','smooth','paint_texture','block_ground','block_building','clear_ground_paint','clear_building_paint','terrain_fields','terrain_environment','terrain_flatten_protected','ground_offsets','paired_native_sync'],
                    'unimplemented':['cliff topology generation','native ramp generation','cliff editor/runtime acceptance','water editing','roads','native procedural foliage','64x64 battlefield acceptance'],
                    'engine_acceptance':'incomplete',
                    'cliff_status':'no_successful_native_topology_delivery_recorded',
                    'cliff_boundary':'existing-cliff preservation, visual surface work and Galaxy pathing layers do not count as native cliff topology success'},
                'terrain_capability_status':{'status':'blocked','tools':['sc2_cliff_capability_status'],
                    'native_cliff_topology_generation':'blocked','native_ramp_generation':'blocked',
                    'cliff_editor_acceptance':'blocked'},
                'dependencies':{'status':'implemented_static','features':['recursive file/bnet references','order','missing/cycles','lossless H2CS8 edits','impact report'],
                    'limitations':['Battle.net-only dependencies require locally available files','engine merge parity unverified']},
                'catalog':{'status':'implemented_static','features':['include/default/parent','field provenance','indexed/append/remove arrays','exact field edits','reference graph'],
                    'limitations':['native class defaults and dynamic expressions unknown','actor events not fully interpreted']},
                'spatial':{'status':'implemented_static','features':['unit/doodad/point/group edits','region rectangles','literal reference guards','batch placement','bilinear terrain grounding','native Objects version sidecar'],
                    'limitations':['camera creation requires observed simple schema','grounded doodads use bilinear terrain sampling; engine appearance unverified']},
                'script_text':{'status':'implemented_static','features':['Galaxy inspection/exact patches','Triggers read','locale edits','layout exact patches','fixed-build native evidence gate'],
                    'limitations':['no Galaxy compiler','no graphical Trigger writer']},
                'assets':{'status':'implemented_static','features':['local/dependency lookup','missing literal refs','import','local CASC extraction','module migration planning'],
                    'limitations':['unknown M3 structures and missing official parent metadata remain explicit unknown']},
                'validation':{'status':'implemented','features':['file structure','profile guards','transaction recovery','conflict-aware rollback','editor/test launch','evidence records'],
                    'levels':['static','editor','runtime','visual']},
                'editor_region_diagnostics':{'status':'implemented_static','features':['CN/international product and branch consistency','active build and build UID checks','editor executable path','Windows map-open registry inspection','map locale component check','recent editor log evidence'],
                    'limitations':['read-only; no registry edits or process launch','does not prove editor readiness or map load']},
                'map_shell':{'status':'implemented_static','features':['ComponentList registration and local component presence','MapInfo magic/payload version/dimensions/SHA-256','44-byte version sidecar FourCC/build fields','Objects and Regions missing-sidecar detection','DocumentInfo metadata root check','optional region/build environment cross-check','native-source repair boundary'],
                    'limitations':['does not prove native editor load','does not reconstruct opaque MapInfo or sidecars']},
                'data_warnings':{'status':'implemented_static_candidate_repairs','features':['XML warning log parsing','local/dependency source classification','entry/scope/field binding','array-index and invalid-field evidence','duplicate ID inventory','empty Actor event and Doodad runtime triage','byte-preserving hash-bound repair candidates','safe candidate vs dependency/reference/runtime disposition'],
                    'tools':['sc2_validate_data_warnings','sc2_plan_data_warning_repairs','sc2_changes_inspect','sc2_changes_apply','sc2_changes_rollback'],
                    'limitations':['does not evaluate final Catalog merge semantics','candidate generation does not prove editor/runtime acceptance','dependency, duplicate-ID, empty-event and Doodad warnings remain gated for manual/reference/runtime evidence']},
            },
            'enhancements':{
                'official_assets':{'status':'bundled_static_knowledge','schema':'official-assets-1',
                    'features':['Chinese name and ID search','Skin template parameter observations','ReplacementArray and EffectArray provenance','Abil/Behavior/Effect/Weapon/Validator/Upgrade/Requirement/Terrain metadata','current map dependency and asset readability audit'],
                    'tools':['sc2_official_assets_search','sc2_official_assets_explain','sc2_official_assets_audit'],
                    'limitations':['snapshot is not current map dependency closure','complex arrays and Actor macros not engine evaluated','no editor/runtime/visual acceptance']},
                'source_context':{'status':'implemented','parser':'source-context-2','features':['component/MPQ/CASC shared materialization','content/build/rule fingerprints','saved region/locale selection','precommit stale checks'],
                    'limitations':['official recursive metadata may be unavailable; actual cn98370 context incomplete']},
                'catalog_explain':{'status':'implemented_static_with_bound_observations','features':['per-field trust and history','indexed structural patch candidates','bound value/structure/source-only and reference impact reports','run-bound snapshot comparison'],
                    'limitations':['unknown macro/default/parent semantics do not become known from one runtime match']},
                'probes':{'status':'implemented','templates':['catalog_snapshot','unit_combat_behavior','variant_upgrade_parity','terrain_diagnostic'],
                    'features':['unique independent Bank','phase timestamps','assertions separate from lifecycle','shared installation lock','verified process identity','restart recovery','partial and terminal consistency'],
                    'evidence':['HT before failed/after passed','Warfield level1 and custom level12 complete','actual timeout partial']},
                'models':{'status':'implemented_readonly','features':['MD34 model metadata','animations/attachments/textures','sparse verified CASC asset cache','explicit extra source order'],
                    'limitations':['unsupported structures rejected or unknown','portrait external animation closure may be partial']},
                'unit_variant':{'status':'restricted_candidate_generator','template':'Marauder/Warfield','features':['unit actor model entry audit','exact upgrade references','shared damage protection','named secret_hangar production/addon/discard impact audit'],
                    'named_workflows':['secret_hangar'],
                    'limitations':['real new-ID generation blocked when parent weapon source incomplete','complex Skin/Actor macros unknown']},
                'keystone':{'status':'implemented_static_candidate_workflows','features':['card ID/cost/effect query','cost and hover preview synchronization','description composition audit','category/date news','152px DXT5 portrait append'],
                    'limitations':['recognized Galaxy fingerprints only','UI/player unlock behavior and visual acceptance not automated']},
                'terrain_control':{'status':'experimental','features':['protected HMAP brush candidate','explicit model origin offset grounding','paired native resave and final-target semantic gate'],
                    'support':'cn98370 exact editor SHA256, XML115/HMAP101/SMAP102 only',
                    'limitations':['original stale sync input rejected for shared native drift','normalized-baseline acceptance recorded separately','runtime and visual evidence require their own results']},
            },
            'limitations':['Process launch is not editor load or runtime acceptance.','Offline previews are diagnostic images.'],
        }

    def record(self,project_id,write=False):
        record=self.projects.get(project_id,write=write)
        return record,Path(record['root'])

    def war3_inspect(self,project_id,source_directory):
        from .storage import guard_absolute_path
        from .war3 import inspect_war3
        self.record(project_id)
        return inspect_war3(guard_absolute_path(Path(source_directory)))

    def war3_plan(self,project_id,source_directory):
        from .war3 import plan
        return plan(self.war3_inspect(project_id,source_directory))

    def war3_coverage(self,project_id,source_directory,implementations=None):
        from .war3 import coverage
        return coverage(self.war3_inspect(project_id,source_directory),implementations)

    def info(self,project_id):
        record,root=self.record(project_id)
        files=snapshot(root)
        result={**record,'file_count':len(files),'fingerprint':digest(json.dumps(files,sort_keys=True).encode()),
                'components':[name for name in ('DocumentInfo','DocumentHeader','MapInfo','ComponentList.SC2Components','Objects','Regions','Triggers','t3Terrain.xml','MapScript.galaxy','BankList.xml') if (root/name).exists()],
                'locales':[p.name for p in root.glob('*.SC2Data') if p.name!='Base.SC2Data']}
        if (root/'t3Terrain.xml').exists():
            try: result['terrain']=Terrain(root).summary()
            except SC2Error as exc: result['terrain_error']=exc.as_dict()
        return result

    def read_text(self,project_id,relative,offset=0,limit=16000):
        _,root=self.record(project_id)
        if not 0<=offset or not 1<=limit<=100000:
            raise SC2Error('invalid_range','读取范围无效')
        path=safe_path(root,relative)
        data=path.read_bytes()
        try: text=data.decode('utf-8-sig')
        except UnicodeError as exc: raise SC2Error('binary_file','该组件不是 UTF-8 文本') from exc
        if '\0' in text: raise SC2Error('binary_file','该组件为二进制数据')
        return {'path':relative,'sha256':digest(data),'bom':data.startswith(b'\xef\xbb\xbf'),
                'text':text[offset:offset+limit],'characters':len(text),'next_offset':offset+limit if offset+limit<len(text) else None}

    def roots(self,project_id):
        context=self.prepare_dependencies(project_id)
        report=dict(context['dependency_report'])
        report['complete']=context['complete']
        report['source_context_id']=context['source_context_id']
        return [Path(p) for p in context['roots']],report

    def _prepare_context(self,record,dependency_values=None,options=None):
        from .source_context import prepare_source_context
        path=self.state/'source-selections'/(record['project_id']+'.json')
        selected=json.loads(path.read_text('utf-8')) if path.is_file() else {}
        if options is not None:selected=options
        return prepare_source_context(Path(record['root']),[Path(p) for p in record['search_roots']],
            self.state/'source-cache',Path(selected['installation']) if selected.get('installation') else None,
            selected.get('locale','zhCN'),selected.get('product'),selected.get('branch'),dependency_values=dependency_values)

    def prepare_dependencies(self,project_id,installation=None,locale=None,product=None,branch=None):
        record,root=self.record(project_id)
        options=None
        overrides={key:value for key,value in {'installation':installation,'locale':locale,'product':product,'branch':branch}.items() if value is not None}
        if overrides:
            selected=self.state/'source-selections'/(project_id+'.json')
            options=json.loads(selected.read_text('utf-8')) if selected.is_file() else {}
            options.update(overrides)
        context=self._prepare_context(record,options=options)
        write_json(self.state/'source-contexts'/(context['source_context_id']+'.json'),{'project_id':project_id,'context':context})
        if options is not None:write_json(self.state/'source-selections'/(project_id+'.json'),options)
        return context

    def dependency_impact(self,project_id,values,catalogs=None,limit=10000):
        record,root=self.record(project_id)
        before=self._prepare_context(record)
        after=self._prepare_context(record,values)
        return dependencies.analyze_dependency_impact(root,values,[Path(p) for p in record['search_roots']],catalogs,limit,
            before_context=before,after_context=after)

    def source_context(self,project_id,source_context_id):
        from .source_context import assert_source_context_current
        if not isinstance(source_context_id,str) or not source_context_id or any(c not in 'abcdef0123456789' for c in source_context_id):
            raise SC2Error('invalid_source_context','来源上下文 ID 无效')
        self.record(project_id)
        path=self.state/'source-contexts'/(source_context_id+'.json')
        if not path.is_file():raise SC2Error('source_context_missing','来源上下文不存在，请先准备来源')
        envelope=json.loads(path.read_text('utf-8'))
        context=envelope['context']
        if envelope.get('project_id')!=project_id or context.get('source_context_id')!=source_context_id:
            raise SC2Error('source_context_mismatch','来源上下文不属于此项目')
        assert_source_context_current(context)
        return context

    def prepare_probe(self,project_id,template,parameters,source_context_id=None,change_id=None,assertions=None):
        _,root=self.record(project_id)
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        candidate=self.transactions.read(change_id) if change_id else None
        if candidate and candidate.get('source_context_id') and candidate['source_context_id']!=context['source_context_id']:
            raise SC2Error('source_context_mismatch','探针候选与选定来源上下文不一致，请按原来源复核或重新生成候选')
        result=self.probes.prepare(root,template,parameters,source_context=context,candidate=candidate,assertions=assertions)
        result['project_id']=project_id
        self.probes.save(result)
        return result

    def probe_result(self,probe_id=None,historical_bank_path=None,assertions=None):
        if historical_bank_path is not None:
            from .probe_bank import parse_probe_bank
            from .storage import guard_absolute_path
            path=guard_absolute_path(Path(historical_bank_path)).resolve()
            workspace=Path(__file__).resolve().parents[2]/'workspace'
            if not path.is_relative_to(workspace) or path.suffix.casefold()!='.sc2bank' or not path.is_file():
                raise SC2Error('invalid_probe_bank','历史探针只能读取本工程 workspace 内归档 Bank，不能读取玩家银行')
            data=path.read_bytes()
            return {**parse_probe_bank(data,assertions=assertions),'evidence_sha256':digest(data),
                'evidence':str(path),'runtime_binding':'historical_unbound','visual':'not_reviewed'}
        return self.probes.collect(probe_id)

    def prepare_changes(self,project_id,patches,source_context_id=None):
        from .change_import import plan_import
        record,root=self.record(project_id,True)
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        def plan():
            self.source_context(project_id,context['source_context_id'])
            return plan_import(root,patches)
        def validate(changes):
            if self._terrain_changes(root,changes):
                raise SC2Error('terrain_operation_required','候选导入不能绕过受控地形流程')
            # Generic map imports also protect identity and player banks. Data
            # shell edits have a separate, purpose-specific dependency API.
            protected={'documentinfo','documentheader','mapinfo','banklist.xml'}
            if any(rel.casefold() in protected or rel.casefold().endswith('.sc2bank') for rel in changes):
                raise SC2Error('protected_patch','候选导入不能修改地图身份、依赖外壳或银行')
            result=self._validate_candidate(record,root,changes,'candidate_import')
            self.source_context(project_id,context['source_context_id'])
            return result
        result=self.transactions.run(root,plan,label='candidate_import',validator=validate,preview_only=True,
            backup_root=root.parent/'_codex_backups' if record['profile']=='keystone' else None)
        if result.get('change_id'):
            manifest=self.transactions.read(result['change_id'])
            manifest['source_context_id']=context['source_context_id']
            self.transactions._save(manifest)
        result['source_context_id']=context['source_context_id']
        result['project_id']=project_id
        conflict=self.editor_conflict()
        if conflict:result['write_deferred']=conflict
        return result

    def prepare_domain(self,project_id,label,planner,source_context_id=None):
        """Route typed domain planners through the existing candidate transaction."""
        record,root=self.record(project_id,True)
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        roots=[Path(p) for p in context['roots']]
        def plan():
            self.source_context(project_id,context['source_context_id'])
            return planner(root,roots,context)
        def validate(changes):
            if self._terrain_changes(root,changes):raise SC2Error('terrain_operation_required','此领域入口不能绕过地形流程')
            result=self._validate_candidate(record,root,changes,label)
            self.source_context(project_id,context['source_context_id'])
            return result
        result=self.transactions.run(root,plan,label=label,validator=validate,preview_only=True,
            backup_root=root.parent/'_codex_backups' if record['profile']=='keystone' else None)
        if result.get('change_id'):
            manifest=self.transactions.read(result['change_id'])
            manifest['source_context_id']=context['source_context_id'];self.transactions._save(manifest)
        result.update(project_id=project_id,source_context_id=context['source_context_id'])
        conflict=self.editor_conflict()
        if conflict:result['write_deferred']=conflict
        return result

    def audit_named_unit_workflow(self,project_id,workflow,source_context_id=None):
        if workflow!='secret_hangar':
            raise SC2Error('unsupported_named_workflow','仅支持已固化的秘密机库命名审计',workflow=workflow)
        from .secret_hangar_audit import audit_secret_hangar
        _,root=self.record(project_id)
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        result=audit_secret_hangar(root,source_context=context)
        result.update(project_id=project_id,source_context_id=context['source_context_id'])
        return result

    def prepare_catalog_patch(self,project_id,operations,source_context_id=None):
        from .catalog_patch import plan_catalog_patch_report
        reports=[]
        def plan(root,roots,context):
            planned=plan_catalog_patch_report(root,roots,operations,source_context=context)
            reports.append(planned['report'])
            return planned['changes']
        result=self.prepare_domain(project_id,'catalog_patch',plan,source_context_id)
        result['impact_report']=reports[0]
        if result.get('change_id'):
            manifest=self.transactions.read(result['change_id'])
            manifest['impact_report']=reports[0]
            self.transactions._save(manifest)
        return result

    def keystone_inspect(self,project_id,workflow,parameters=None,source_context_id=None):
        from . import keystone
        _,root=self.record(project_id)
        parameters=parameters or {}
        if workflow=='card':return keystone.inspect_keystone_card(root,**parameters)
        if workflow=='news':return keystone.inspect_keystone_news(root,**parameters)
        if workflow=='portraits':return keystone.inspect_keystone_portraits(root)
        if workflow=='descriptions':
            context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
            return keystone.audit_keystone_descriptions(root,source_context=context,**parameters)
        raise SC2Error('invalid_keystone_workflow','未知钥石查询流程',workflow=workflow)

    def prepare_keystone(self,project_id,workflow,parameters,source_context_id=None):
        from . import keystone
        planners={'card_cost':keystone.plan_keystone_card_cost,'news':keystone.plan_keystone_news,'portrait':keystone.plan_keystone_portrait}
        if workflow not in planners:raise SC2Error('invalid_keystone_workflow','未知钥石候选流程',workflow=workflow)
        return self.prepare_domain(project_id,'keystone_'+workflow,lambda root,roots,context:planners[workflow](root,**parameters),source_context_id)

    def resolve_model_assets(self,project_id,reference=None,model_id=None,source_context_id=None,sources=None,cancel=None,references=None):
        from .asset_cache import materialize_assets
        from .assets_model import inspect_model_catalog
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        roots=[Path(p) for p in context['roots']]
        catalog_report=inspect_model_catalog(roots,model_id,source_context=context) if model_id else None
        if catalog_report:
            references=[edge['to'] for edge in catalog_report['edges'] if edge['from'] is None]
        elif references is None:references=[reference]
        if not references:
            return catalog_report or {'nodes':[],'complete':False,'unknown':[{'reason':'no_asset_references'}]}
        result=materialize_assets(context,references,sources=sources,cancel=cancel)
        if catalog_report:
            result['catalog']=catalog_report['catalog'];result['catalog_unknown']=catalog_report['catalog_unknown']
            result['complete']=result['complete'] and not result['catalog_unknown']
        return result

    def explain_catalog(self,project_id,kind,object_id,fields=None,source_context_id=None,observations=None):
        from .catalog_explain import catalog_explain
        context=self.source_context(project_id,source_context_id) if source_context_id else self.prepare_dependencies(project_id)
        bound=None
        if observations is not None:
            if not isinstance(observations,dict) or set(observations)!={'probe_id'}:
                raise SC2Error('runtime_evidence_required','运行时比较只接受本服务生成的Catalog探针ID：observations={probe_id:...}')
            manifest=self.probes.read(observations['probe_id'])
            result=self.probes.collect(observations['probe_id'])
            parameters=manifest['parameters']
            if (manifest.get('project_id')!=project_id or manifest['template']!='catalog_snapshot' or manifest.get('change_id') or
                manifest.get('source_context',{}).get('source_context_id')!=context['source_context_id'] or
                result.get('source_stale') or result.get('binding')!='run_bound' or
                result.get('execution',{}).get('state')!='complete' or result.get('run_state') not in {'finished','recovered_finished'} or
                result.get('evidence_status')!='bound_runtime' or
                parameters.get('catalog','Unit')!=kind or parameters.get('object_id')!=object_id):
                raise SC2Error('runtime_evidence_mismatch','探针不是当前对象、来源或未修改基准的观测')
            evidence={'probe_id':manifest['probe_id'],'bank':result['bank'],'bank_sha256':result['bank_sha256'],
                'archive_sha256':manifest['archive_sha256'],'player':1,'phase':'Catalog'}
            bound={'source_context_id':context['source_context_id'],'build':manifest['launch']['build'],
                'observations':[{'catalog':kind,'object_id':object_id,'field':field,'value':value,'status':'observed','evidence':evidence}
                    for field,value in result['sections'].get('Catalog',{}).items() if field not in {'StageStatus','StartedGameTime','FinishedGameTime'}]}
        return catalog_explain([Path(p) for p in context['roots']],kind,object_id,fields,context,bound)

    def _materialize_roots(self,report,root):
        roots=[]
        for value in report['load_order']:
            path=Path(value)
            if path.is_dir(): roots.append(path)
            elif path.is_file():
                # Reuse Projects' content-addressed archive extraction, preserving
                # source immutability and keeping it outside the component map.
                archive=self.projects.open(str(path),writable=False)
                roots.append(Path(archive['root']))
        if root not in roots: roots.append(root)
        return roots

    def _validate_candidate(self,record,root,changes,domain):
        validation=validate_changes(root,changes,record['profile'],domain)
        if not any(rel in ('Objects','Regions','DocumentInfo') or rel.endswith('.galaxy') or
                   (rel.endswith('.xml') and '.sc2data/' in rel.casefold()) for rel in changes):
            return validation
        from .cross_validation import validate_references
        before_context=self._prepare_context(record)
        before=before_context['dependency_report']
        after=before
        after_context=before_context
        if 'DocumentInfo' in changes:
            values=dependencies.decode_declarations(changes['DocumentInfo'])
            after_context=self._prepare_context(record,values)
            after=after_context['dependency_report']
        context={'before':[Path(p) for p in before_context['roots']],'after':[Path(p) for p in after_context['roots']]}
        report=validate_references(root,changes,context,self.state/'reference-checks')
        report['dependencies_complete']={'before':before_context['complete'],'after':after_context['complete']}
        report['source_context_id']={'before':before_context['source_context_id'],'after':after_context['source_context_id']}
        report['missing_dependencies']={'before':before['missing'],'after':after['missing']}
        validation['references']=report
        return validation

    def editor_conflict(self):
        running=[p for p in editor.processes() if 'editor' in p['name'].lower()]
        return {'code':'editor_unsaved_state_unknown','message':'编辑器仍在运行，无法确认未保存文档；结果保留为候选。',
                'processes':running} if running else None

    @staticmethod
    def _terrain_operation(operation, parameters):
        if operation in ('terrain', 'terrain_fields', 'terrain_environment','terrain_flatten_protected','ground_offsets'):
            return True
        if operation == 'catalog_set':
            return str(parameters.get('catalog', '')).casefold() in {'terrain', 'terraintex'}
        if operation == 'batch':
            return any(Service._terrain_operation(edit.get('operation'), edit.get('parameters', {}))
                       for edit in parameters.get('edits', []) if isinstance(edit, dict))
        return False

    @staticmethod
    def _terrain_changes(root, changes):
        """Classify actual candidate bytes, including deleted/replaced definitions.

        Includes may place CTerrain declarations in arbitrary XML files, so a
        filename-only check is insufficient. Invalid XML is left to validation.
        """
        for relative, content in changes.items():
            name = relative.replace('\\', '/').casefold()
            if name.startswith(('t3', 'cellattribute_')) or name.rsplit('/', 1)[-1] in {'terraindata.xml', 'terraintexdata.xml'}:
                return True
            if not name.endswith('.xml'):
                continue
            path = safe_path(root, relative)
            for raw in (content, path.read_bytes() if path.is_file() else None):
                if raw is None:
                    continue
                # DTD/entity declarations cannot become valid candidates. Avoid
                # evaluating any declarations merely to classify their content.
                if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                    raise SC2Error('unsupported_xml', '候选 XML 不接受 DTD 或实体声明', path=relative)
                try:
                    tree = ET.fromstring(raw)
                except ET.ParseError:
                    continue
                if any(node.tag in {'CTerrain', 'CTerrainTex'} for node in tree.iter()):
                    return True
        return False

    def _plan_one(self,root,operation,p):
        if operation=='terrain_flatten_protected':
            from .terrain_control import plan_flatten_protected
            return plan_flatten_protected(root,**p)
        if operation=='ground_offsets':
            from .terrain_control import plan_ground_offsets
            return plan_ground_offsets(root,**p)
        if operation=='terrain': return plan_terrain(root,p['operations'])
        if operation=='terrain_environment':
            from .terrain_environment import plan_environment
            return plan_environment(root,p['settings'])
        if operation=='terrain_fields':
            import numpy as np
            import zipfile
            from .terrain_fields import plan_terrain_fields
            source=Path(p['source']).resolve()
            if source.suffix.lower()!='.npz' or source.stat().st_size>256*1024*1024:
                raise SC2Error('invalid_terrain_field_file','需提供不超过256MiB的NPZ地形字段文件')
            with zipfile.ZipFile(source) as zipped:
                if sum(entry.file_size for entry in zipped.infolist())>256*1024*1024:
                    raise SC2Error('invalid_terrain_field_file','字段展开尺寸超过256MiB')
            fingerprint=digest(source.read_bytes())
            with np.load(source,allow_pickle=False) as loaded:
                allowed={'heights','texture_weights','ground_mask','building_mask'}
                if not set(loaded.files)<=allowed or not loaded.files:
                    raise SC2Error('invalid_terrain_field_file','NPZ字段为空或含未知数组')
                fields={name:loaded[name] for name in loaded.files}
            if digest(source.read_bytes())!=fingerprint:
                raise SC2Error('baseline_conflict','读取期间地形字段文件改变')
            palette=p.get('texture_palette')
            if palette is not None:palette={int(k):v for k,v in palette.items()}
            return plan_terrain_fields(root,texture_palette=palette,**fields)
        if operation=='object_batch':
            from .spatial_batch import plan_place_objects
            return plan_place_objects(root,p['objects'],p.get('ground_doodads',True))
        if operation=='catalog_set':
            if p['field_path'].lstrip('@').casefold()=='id':
                raise SC2Error('identity_not_scalar','对象重命名需要完整引用迁移，不能通过字段工具改 ID')
            return catalog.plan_catalog_set(root,p['catalog'],p['object_id'],p['field_path'],p['value'],p.get('expected'))
        if operation=='dependencies_set': return dependencies.plan_dependencies(root,p['values'])
        if operation=='object_edit': return spatial.plan_object_edit(root,p['object_id'],p['attributes'])
        if operation=='object_add': return spatial.plan_object_add(root,p['kind'],p['attributes'])
        if operation=='object_remove': return spatial.plan_object_remove(root,p['object_id'])
        if operation=='region_edit': return spatial.plan_region_edit(root,p['region_id'],p.get('name'),p.get('rect'))
        if operation=='script_replace': return script.plan_script_replace(root,p['old'],p['new'],p['expected_sha256'])
        if operation=='script_build':
            from .script_build import plan_script_build
            return plan_script_build(root,p['manifest_path'],p.get('expected_manifest_sha256'))
        if operation=='script_guarded_replace':
            from .script_guard import plan_guarded_replace
            return plan_guarded_replace(root,p['old'],p['new'],p['expected_sha256'],p.get('review'))
        if operation=='localization_set': return localization.plan_localization_set(root,p['updates'],p.get('locale','zhCN'))
        if operation=='asset_import': return assets.plan_asset_import(root,Path(p['source']),p['destination'],p.get('overwrite',False))
        if operation=='layout_replace':
            rel=p['path'];path=safe_path(root,rel)
            if path.suffix.casefold()!='.sc2layout': raise SC2Error('layout_required','此工具仅修改 SC2Layout')
            data=path.read_bytes()
            if digest(data)!=p['expected_sha256']: raise SC2Error('baseline_conflict','布局文件指纹已变化')
            old=p['old'].encode('utf-8');new=p['new'].encode('utf-8')
            if not old or data.count(old)!=1: raise SC2Error('ambiguous_context','布局上下文必须恰好匹配一次')
            return {rel:data.replace(old,new,1)}
        raise SC2Error('unsupported_operation','操作未实现',operation=operation)

    def edit(self,project_id,operation,parameters,preview_only=False,experimental_write=False,cancel=None):
        if cancel and hasattr(cancel,'report_progress'):cancel.report_progress(5,'读取项目与基准')
        record,root=self.record(project_id,True)
        conflict=self.editor_conflict()
        terrain=self._terrain_operation(operation,parameters)
        if conflict: preview_only=True
        if terrain and not experimental_write:
            preview_only=True
            conflict=conflict or {'code':'terrain_not_accepted','message':'地形写回尚未完成引擎验收，默认仅生成候选；独立测试图可显式 experimental_write=true。'}
        if terrain and experimental_write and root.resolve()==KEYSTONE.resolve():
            raise SC2Error('experimental_formal_map','未验收地形不能写正式钥石地图，请先克隆独立测试图')
        domain='dependencies' if operation=='dependencies_set' or (operation=='batch' and any(x.get('operation')=='dependencies_set' for x in parameters.get('edits',[]))) else operation
        impact={}
        def plan():
            if cancel and hasattr(cancel,'report_progress'):cancel.report_progress(15,'生成候选修改')
            if operation=='dependencies_set':
                impact.update(self.dependency_impact(project_id,parameters['values'],limit=10000))
            if operation!='batch': return self._plan_one(root,operation,parameters)
            edits=parameters.get('edits')
            if not isinstance(edits,list) or not 1<=len(edits)<=100:
                raise SC2Error('invalid_batch','批量修改需要 1 至 100 项操作')
            stage=self.state/'planning'/uuid.uuid4().hex/'map.SC2Map'
            stage.mkdir(parents=True)
            original=snapshot(root)
            for rel,path in map_files(root):
                target=safe_path(stage,rel);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
            for edit in edits:
                self.transactions.check_cancel(cancel)
                for rel,data in self._plan_one(stage,edit['operation'],edit['parameters']).items():
                    path=safe_path(stage,rel)
                    if data is None: path.unlink()
                    else: atomic_write(path,data)
            result=snapshot(stage)
            return {rel:(stage/rel).read_bytes() if rel in result else None for rel in original.keys()|result.keys() if original.get(rel)!=result.get(rel)}
        def validate(changes):
            if cancel and hasattr(cancel,'report_progress'):cancel.report_progress(60,'校验结构与跨文件引用')
            if not preview_only and not terrain and self._terrain_changes(root,changes):
                raise SC2Error('terrain_operation_required','候选包含地形定义，需通过显式地形实验流程；当前操作只能预览')
            if not preview_only and self.editor_conflict():
                raise SC2Error('editor_started_during_plan','规划时启动了编辑器，请重新调用以生成候选')
            result=self._validate_candidate(record,root,changes,domain)
            if not preview_only and self.editor_conflict():
                raise SC2Error('editor_started_during_plan','验证时启动了编辑器，未提交')
            return result
        backup=root.parent/'_codex_backups' if record['profile']=='keystone' else None
        before_preview=None
        if terrain and (root/'t3Terrain.xml').is_file():
            before_preview=render_terrain(root,self.state/'previews'/uuid.uuid4().hex/'before')
        result=self.transactions.run(root,plan,label=operation,validator=validate,cancel=cancel,
                                     preview_only=preview_only,backup_root=backup)
        result['project_id']=project_id
        result['operation']=operation
        if impact: result['impact']=impact
        if conflict: result['write_deferred']=conflict
        if terrain and before_preview is not None and result.get('change_id'):
            folder=Path(result['candidate'])
            overrides={e['path']:(folder/e['path']).read_bytes() if e['after'] is not None else None for e in result['files']}
            result['previews']={'before':before_preview,'after':render_terrain(root,self.state/'previews'/result['change_id']/'after',overrides)}
        return result

    def apply_candidate(self,project_id,change_id,experimental_write=False):
        record,root=self.record(project_id,True)
        if self.editor_conflict(): raise SC2Error('editor_unsaved_state_unknown','编辑器仍运行，候选保持未提交')
        manifest=self.transactions.read(change_id)
        if manifest['state']!='prepared' or Path(manifest['root']).resolve()!=root.resolve():
            raise SC2Error('invalid_candidate','候选状态或项目不匹配')
        terrain_candidate=manifest['label'] in {'terrain','terrain_fields','terrain_environment','terrain_flatten_protected','terrain_native_sync','ground_offsets'}
        if terrain_candidate and (not experimental_write or root.resolve()==KEYSTONE.resolve()):
            raise SC2Error('terrain_not_accepted','地形候选需通过独立图实验流程，不能直接向正式图提升')
        if manifest.get('source_context_id'):
            self.source_context(project_id,manifest['source_context_id'])
        def plan():
            baseline=manifest.get('baseline')
            if baseline is None or snapshot(root)!=baseline:
                raise SC2Error('baseline_conflict','候选生成后地图发生变化')
            result={}
            for entry in manifest['entries']:
                path=safe_path(root,entry['path'])
                if (digest(path.read_bytes()) if path.exists() else None)!=entry['before']:
                    raise SC2Error('baseline_conflict','候选生成后文件发生变化',path=entry['path'])
                data=safe_path(self.state/'changes'/change_id/'candidate',entry['path']).read_bytes() if entry['after'] else None
                if (digest(data) if data is not None else None)!=entry['after']:
                    raise SC2Error('candidate_corrupt','候选内容指纹不符')
                result[entry['path']]=data
            if self._terrain_changes(root,result) and (not experimental_write or root.resolve()==KEYSTONE.resolve()):
                raise SC2Error('terrain_not_accepted','地形候选尚不能向正式图提升')
            return result
        def validate(changes):
            if self.editor_conflict():raise SC2Error('editor_started_during_plan','检查期间启动了编辑器，候选保持未提交')
            if manifest.get('source_context_id'):self.source_context(project_id,manifest['source_context_id'])
            result=self._validate_candidate(record,root,changes,'dependencies' if 'DocumentInfo' in changes else 'general')
            if manifest.get('source_context_id'):self.source_context(project_id,manifest['source_context_id'])
            if self.editor_conflict():raise SC2Error('editor_started_during_plan','检查期间启动了编辑器，候选保持未提交')
            return result
        return self.transactions.run(root,plan,label='apply_'+manifest['label'],validator=validate,
            backup_root=root.parent/'_codex_backups' if record['profile']=='keystone' else None)

    def validate(self,project_id,cancel=None):
        record,root=self.record(project_id)
        self.transactions.check_cancel(cancel)
        result=inspect_project(root,record['profile'],cancel)
        shell=map_shell.inspect_map_shell(root)
        result['map_shell']=shell
        if shell['verdict']=='blocked':
            result['static']='failed'
            result['errors']=result.get('errors',[])+[
                {'file':'map-shell','code':item['code'],'message':item['message'],'details':item}
                for item in shell['errors']
            ]
        self.transactions.check_cancel(cancel)
        result['dependencies']=dependencies.resolve_dependencies(root,[Path(p) for p in record['search_roots']])
        result['static_scope']='syntax/component structure; dependency completeness reported separately'
        result['sha256_snapshot']=snapshot(root)
        output=self.state/'reports'/(uuid.uuid4().hex+'.json')
        write_json(output,result)
        return {**{k:v for k,v in result.items() if k!='sha256_snapshot'},'report':str(output)}

    def map_shell_audit(self,project_id,installation=None,product=None,branch=None,locale='zhCN'):
        _,root=self.record(project_id)
        result=map_shell.inspect_map_shell(root)
        if installation:
            result['environment']=editor.diagnose_editor_region(Path(installation),product,branch,locale,root)
            result['environment_verdict']=result['environment'].get('verdict','unknown')
        else:
            result['environment']={'provided':False,'verdict':'not_checked',
                                   'limitations':['未提供安装目录，未执行地区、构建和编辑器环境核对。']}
            result['environment_verdict']='not_checked'
        return result

    def cliff_capability_status(self):
        return terrain_capability.capability_status()

    def native_script_gate(self,project_id,manifest_path,native_root,installation,
                           expected_editor_sha256,evidence_path=None):
        _,root=self.record(project_id)
        from .script_native_validation import inspect_native_gate
        return inspect_native_gate(root,manifest_path,Path(native_root),Path(installation),
                                  expected_editor_sha256,Path(evidence_path) if evidence_path else None)

    def official_asset_audit(self,project_id,catalog_name,object_id,component=None,
                             installation=None,locale=None,product=None,branch=None,
                             source_context_id=None):
        """Audit bundled official knowledge against this map's real closure."""
        from . import official_assets
        self.record(project_id)
        context = None
        if source_context_id:
            context = self.source_context(project_id, source_context_id)
        else:
            # Dependency parsing is safe and useful without an installation;
            # CASC materialization remains explicitly unavailable in that case.
            context = self.prepare_dependencies(project_id, installation, locale, product, branch)
        explanation = official_assets.explain(catalog_name, object_id, component)
        asset_readability = None
        references = []
        for model in explanation.get('target_models', []):
            references.extend(model.get('model_path_candidates', []))
        if references and context.get('build'):
            from .asset_cache import materialize_assets
            try:
                closure = materialize_assets(context, list(dict.fromkeys(references)))
                asset_readability = {
                    'status': 'passed' if closure.get('complete') else ('missing' if closure.get('missing') else 'partial'),
                    'reference_count': len(set(references)),
                    'resolved_count': len(closure.get('nodes', [])),
                    'missing_count': len(closure.get('missing', [])),
                    'unknown_count': len(closure.get('unknown', [])),
                    'reason': closure.get('scope'),
                }
            except SC2Error as exc:
                asset_readability = {'status': 'unknown', 'reference_count': len(set(references)),
                                     'reason': exc.code, 'message': str(exc)}
        elif references:
            asset_readability = {'status': 'not_checked', 'reference_count': len(set(references)),
                                 'reason': 'installation_build_not_bound'}
        result = official_assets.audit(catalog_name, object_id, component, context, asset_readability)
        result['project_id'] = project_id
        result['source_context_id'] = context.get('source_context_id')
        return result

    def data_warnings_audit(self,project_id,log_path=None,log_text=None):
        _,root=self.record(project_id)
        return data_warnings.inspect_data_warnings(root,log_text=log_text,log_path=Path(log_path) if log_path else None)

    def prepare_data_warning_repairs(self,project_id,log_path=None,log_text=None,
                                     repair_ids=None,include_inferred=False):
        """Generate hash-bound Catalog warning repair candidates without applying them."""
        record,root=self.record(project_id,True)
        planned={}
        def plan():
            result=data_warnings.plan_warning_repairs(
                root,
                log_text=log_text,
                log_path=Path(log_path) if log_path else None,
                repair_ids=repair_ids,
                include_inferred=include_inferred,
            )
            planned.update(result)
            return result['changes']
        def validate(changes):
            if self._terrain_changes(root,changes):
                raise SC2Error('terrain_operation_required','数据警告修复不能绕过受控地形流程')
            return self._validate_candidate(record,root,changes,'data_warning_repairs')
        result=self.transactions.run(
            root,
            plan,
            label='data_warning_repairs',
            validator=validate,
            preview_only=True,
            backup_root=root.parent/'_codex_backups' if record['profile']=='keystone' else None,
        )
        result['warning_repair_report']=planned.get('report',{})
        result['blocked']=planned.get('blocked',[])
        result['project_id']=project_id
        if result.get('change_id'):
            manifest=self.transactions.read(result['change_id'])
            manifest['warning_repair_report']=planned.get('report',{})
            manifest['blocked']=planned.get('blocked',[])
            self.transactions._save(manifest)
        return result

    def record_evidence(self,project_id,level,status,evidence_path,notes):
        if level not in ('editor','runtime','visual') or status not in ('passed','failed','blocked','partial'):
            raise SC2Error('invalid_evidence','证据层级或状态无效')
        _,root=self.record(project_id)
        evidence=Path(evidence_path).resolve()
        if not evidence.is_file(): raise SC2Error('evidence_missing','证据文件不存在')
        result={'id':uuid.uuid4().hex,'project_id':project_id,'level':level,'status':status,
                'notes':notes,'source':'caller_attested','evidence':str(evidence),'evidence_sha256':digest(evidence.read_bytes()),
                'snapshot':snapshot(root),'created_at':datetime.now(timezone.utc).isoformat()}
        output=self.state/'evidence'/(result['id']+'.json');write_json(output,result)
        return {k:v for k,v in result.items() if k!='snapshot'}

    def register_template(self,project_id,name,evidence_id):
        if not name or len(name)>80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            raise SC2Error('invalid_template_name','模板名称仅允许 ASCII 字母、数字、横线和下划线')
        record,root=self.record(project_id)
        evidence=safe_path(self.state/'evidence',evidence_id+'.json')
        data=json.loads(evidence.read_text('utf-8'))
        if data['project_id']!=project_id or data['level']!='editor' or data['status']!='passed' or data['snapshot']!=snapshot(root):
            raise SC2Error('template_unverified','模板须有匹配当前文件指纹的编辑器载入通过证据')
        proof=Path(data['evidence'])
        if not proof.is_file() or digest(proof.read_bytes())!=data['evidence_sha256']:
            raise SC2Error('evidence_changed','编辑器验收证据文件丢失或已改变')
        required=['DocumentInfo','DocumentHeader','ComponentList.SC2Components']
        if record['kind']=='map': required.extend(['MapInfo','t3Terrain.xml'])
        missing=[name for name in required if not (root/name).is_file()]
        if missing:raise SC2Error('template_shell_missing','模板缺少必要组件',missing=missing)
        checks=inspect_project(root,record['profile'])
        if checks['static']!='passed': raise SC2Error('template_invalid','模板静态检查未通过',report=checks)
        result={'name':name,'project_id':project_id,'snapshot':data['snapshot'],'evidence_id':evidence_id,'evidence_source':data['source']}
        write_json(self.state/'templates'/(name+'.json'),result)
        return {'name':name,'registered':True,'evidence_source':data['source']}

    def create_from_template(self,name,destination):
        data=json.loads(safe_path(self.state/'templates',name+'.json').read_text('utf-8'))
        _,root=self.record(data['project_id'])
        if snapshot(root)!=data['snapshot']: raise SC2Error('template_changed','模板自验收后已改变，需重新验证')
        return self.projects.clone(data['project_id'],destination)

    def export(self,project_id,destination,cancel=None):
        _,root=self.record(project_id)
        # Exports read source files. Do not create map-local transaction metadata
        # in a project that was opened readonly.
        with file_lock(self.state/'export-locks'/(digest(str(root).casefold().encode())+'.lock')):
            self.transactions.check_cancel(cancel)
            result=archives.export_archive(root,Path(destination),cancel=cancel)
        result['editor']='not_run';result['runtime']='not_run'
        return result

    def migrate(self,project_id,selections,template_project_id,destination=None,preview_only=True):
        from .migration import inspect_migration,plan_migration
        record,root=self.record(project_id)
        _,template=self.record(template_project_id)
        search=[Path(p) for p in record['search_roots']]
        context=self._prepare_context(record)
        report=inspect_migration(root,selections,template,search,source_context=context)
        if preview_only or destination is None: return report
        target=Path(destination).resolve()
        if target.exists() or target.suffix.casefold()!='.sc2mod' or target.is_relative_to(root) or target.is_relative_to(template):
            raise SC2Error('invalid_destination','目标需为独立全新 .SC2Mod 目录')
        changes=plan_migration(root,selections,template,search,source_context=context)
        verified=False
        for path in (self.state/'templates').glob('*.json'):
            item=json.loads(path.read_text('utf-8'))
            if item.get('project_id')==template_project_id and item.get('snapshot')==snapshot(template):
                verified=True;break
        if not verified:
            raise SC2Error('template_unverified','迁移写入需要已注册且有匹配编辑器证据的模组模板；分析报告仍可生成')
        target.mkdir(parents=True,exist_ok=False)
        result=self.transactions.run(target,lambda:changes,label='module_migration',
            validator=lambda c:validate_changes(target,c))
        return {'migration':report,'change':result,'project':self.projects.open(str(target),True)}

    def native_sync(self,project_id,control_archive,candidate_archive,destination,installation,expected_editor_sha256,timeout=120,cancel=None):
        from .terrain_control import run_native_sync
        self.record(project_id)
        return run_native_sync(Path(control_archive),Path(candidate_archive),Path(destination),Path(installation),
            state_root=self.state,expected_editor_sha256=expected_editor_sha256,protected_roots=[KEYSTONE.parent],timeout=timeout,cancel=cancel)

    def prepare_native_result(self,project_id,control_before,control_after,candidate_before,candidate_after,protected_mask=None,support_radius=3):
        from .terrain_control import plan_native_sync_result_report
        record,root=self.record(project_id,True)
        if root.resolve()==KEYSTONE.resolve():raise SC2Error('experimental_formal_map','原生地形只允许独立测试地图')
        report={}
        def plan():
            value=plan_native_sync_result_report(root,Path(control_before),Path(control_after),Path(candidate_before),Path(candidate_after),
                protected_mask=protected_mask,support_radius=support_radius)
            report.update({key:value for key,value in value.items() if key!='changes'})
            return value['changes']
        result=self.transactions.run(root,plan,label='terrain_native_sync',preview_only=True,
            validator=lambda changes:validate_changes(root,changes,record['profile'],'terrain'))
        return {'change':result,'gate':report,'runtime':'not_observed','visual':'not_observed'}
