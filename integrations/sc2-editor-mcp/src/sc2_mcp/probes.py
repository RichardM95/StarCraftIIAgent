"""Controlled, restart-recoverable diagnostics on independent map copies.

The existing Jobs executes runs and Transactions applies the diagnostic setup.
There is no user-script injection or second background-task implementation.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path

import psutil

from . import archives, editor
from .errors import SC2Error
from .storage import atomic_write, digest, file_lock, guard_absolute_path, map_files, safe_path, snapshot, write_json
from .transactions import Transactions
from .validation import validate_changes, lexical_balance

TEMPLATE_VERSION = '20261016.3'
_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
_FIELD = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\[[A-Za-z0-9_]+\])?(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[A-Za-z0-9_]+\])?)*\Z')
_TEMPLATES = {'catalog_snapshot', 'unit_combat_behavior', 'variant_upgrade_parity', 'terrain_diagnostic'}


def _identifier(value, name):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise SC2Error('invalid_probe_parameter', '探针参数必须为明确的 Catalog ID', parameter=name)
    return value


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise SC2Error('invalid_probe_parameter', '探针数值超出范围', parameter=name)
    return float(value)


def render_template(template: str, parameters: dict, run_id: str) -> tuple[bytes, list[str]]:
    if template not in _TEMPLATES or not isinstance(parameters, dict):
        raise SC2Error('unsupported_probe_template', '仅支持固定诊断模板', supported=sorted(_TEMPLATES))
    if not isinstance(run_id, str) or not re.fullmatch('[a-f0-9]{32}', run_id):
        raise SC2Error('invalid_probe_id', '探针 ID 无效')
    bank = 'SC2MCPProbe_' + run_id
    if template == 'terrain_diagnostic':
        from .terrain_probe import render_terrain_probe
        return render_terrain_probe(parameters, run_id)
    if template == 'catalog_snapshot':
        if set(parameters) - {'catalog', 'object_id', 'fields', 'arrays'}:
            raise SC2Error('invalid_probe_parameter', 'Catalog 模板包含未知参数')
        kind = parameters.get('catalog', 'Unit')
        if kind not in {'Unit', 'Abil', 'Weapon', 'Effect', 'Behavior', 'Actor', 'Model', 'Upgrade'}:
            raise SC2Error('unsupported_probe_catalog', '此模板未支持指定 Catalog')
        identifier = _identifier(parameters.get('object_id'), 'object_id')
        fields, arrays = parameters.get('fields', []), parameters.get('arrays', [])
        if not isinstance(fields, list) or not isinstance(arrays, list) or not 1 <= len(fields) + len(arrays) <= 100:
            raise SC2Error('invalid_probe_parameter', '请指定 1 至 100 个字段或数组')
        if any(not isinstance(v, str) or not _FIELD.fullmatch(v) for v in fields + arrays):
            raise SC2Error('invalid_probe_parameter', '字段路径包含不支持的语法')
        lines = ['include "TriggerLibs/NativeLib"', '', 'bank probeBank;', 'trigger probeTrigger;', '',
            'bool ProbeRun (bool testConds, bool runActions) {', '    int i;', '    int count;', '    string field;',
            '    if (!runActions) {', '        return true;', '    }', '    Wait(1.0, c_timeGame);',
            f'    probeBank = BankLoad("{bank}", 1);', f'    BankValueSetFromString(probeBank, "Run", "RunId", "{run_id}");',
            '    BankValueSetFromString(probeBank, "Run", "Status", "STARTED");',
            '    BankValueSetFromFixed(probeBank, "Run", "StartedGameTime", GameGetMissionTime());',
            '    BankValueSetFromFixed(probeBank, "Catalog", "StartedGameTime", GameGetMissionTime());',
            '    BankValueSetFromString(probeBank, "Catalog", "StageStatus", "STARTED");', '    BankSave(probeBank);']
        constant = 'c_gameCatalog' + kind
        for field in fields:
            lines.append(f'    BankValueSetFromString(probeBank, "Catalog", "{field}", CatalogFieldValueGet({constant}, "{identifier}", "{field}", 1));')
        for field in arrays:
            lines.extend([f'    count = CatalogFieldValueCount({constant}, "{identifier}", "{field}", 1);',
                f'    BankValueSetFromInt(probeBank, "Catalog", "{field}.Count", count);', '    i = 0;',
                '    while (i < count) {', f'        field = "{field}[" + IntToString(i) + "]";',
                f'        BankValueSetFromString(probeBank, "Catalog", field, CatalogFieldValueGet({constant}, "{identifier}", field, 1));',
                f'        BankValueSetFromString(probeBank, "Catalog", field + ".Link", CatalogFieldValueGet({constant}, "{identifier}", field + ".Link", 1));',
                '        i += 1;', '    }'])
        lines.extend(['    BankValueSetFromFixed(probeBank, "Catalog", "FinishedGameTime", GameGetMissionTime());',
            '    BankValueSetFromString(probeBank, "Catalog", "StageStatus", "FINISHED");',
            '    BankValueSetFromFixed(probeBank, "Run", "FinishedGameTime", GameGetMissionTime());',
            '    BankValueSetFromString(probeBank, "Run", "Status", "FINISHED");', '    BankSave(probeBank);',
            '    return true;', '}', '', 'void InitMap () {', '    libNtve_InitLib();',
            '    probeTrigger = TriggerCreate("ProbeRun");', '    TriggerAddEventMapInit(probeTrigger);', '}', ''])
        raw = '\n'.join(lines).encode('utf-8')
        phases = ['Catalog']
    else:
        allowed = {'sample_seconds'} | ({'unit_id', 'waiting_behavior', 'caster_id'} if template == 'unit_combat_behavior' else {'base_unit', 'variant_unit', 'weapon_upgrade', 'armor_upgrade'})
        if set(parameters) - allowed:
            raise SC2Error('invalid_probe_parameter', '固定模板包含未知参数', unknown=sorted(set(parameters)-allowed))
        text = (Path(__file__).parent / 'templates' / (template + '.galaxy')).read_text('utf-8')
        text = text.replace('__BANK__', bank).replace('__RUN_ID__', run_id)
        replacements = ({'HighTemplar': parameters.get('unit_id', 'HighTemplar'),
            'CasterWaitingToMoveOut':parameters.get('waiting_behavior', 'CasterWaitingToMoveOut'),
            'KSCG2HighTemplarCardCaster':parameters.get('caster_id', 'KSCG2HighTemplarCardCaster')}
            if template == 'unit_combat_behavior' else {'Marauder':parameters.get('base_unit','Marauder'),
            'MarauderWarfield':parameters.get('variant_unit','MarauderWarfield'),
            'TerranInfantryWeaponsLevel1':parameters.get('weapon_upgrade','TerranInfantryWeaponsLevel1'),
            'TerranInfantryArmorsLevel1':parameters.get('armor_upgrade','TerranInfantryArmorsLevel1')})
        # Match quoted tokens in a single pass so swapping IDs cannot cascade.
        text = re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)"', lambda m: '"'+_identifier(replacements[m[1]],m[1])+'"' if m[1] in replacements else m[0], text)
        seconds = _number(parameters.get('sample_seconds', 5), 'sample_seconds', 0.25, 60)
        text = text.replace('Wait(5.0, c_timeGame);', f'Wait({seconds:.4f}, c_timeGame);')
        raw = text.encode('utf-8')
        phases = (['Born','Attack','AfterAttack','Waiting','Released','CardCaster'] if template == 'unit_combat_behavior'
            else ['BaseBorn','VariantBorn','BaseUpgrade','VariantUpgrade','BaseStim','VariantStim','BaseExtraUpgrade','VariantExtraUpgrade','VariantBornUpgraded','Death'])
    lexical_balance(raw)
    return raw, phases


class Probes:
    def __init__(self, state: Path):
        self.state = guard_absolute_path(Path(state)).resolve()

    def folder(self, probe_id):
        if not isinstance(probe_id,str) or not re.fullmatch('[a-f0-9]{32}',probe_id):
            raise SC2Error('invalid_probe_id','探针 ID 无效')
        return guard_absolute_path(self.state/'probes'/probe_id)

    def read(self, probe_id):
        path=self.folder(probe_id)/'manifest.json'
        if not path.is_file():raise SC2Error('probe_missing','探针不存在')
        return json.loads(path.read_text('utf-8'))

    @contextlib.contextmanager
    def _manifest_lock(self, area):
        deadline=time.monotonic()+5
        while True:
            lock=file_lock(area/'manifest.lock')
            try:
                lock.__enter__()
            except SC2Error as exc:
                if exc.code!='project_busy' or time.monotonic()>=deadline:raise
                time.sleep(.01)
            else:
                break
        try:
            yield
        finally:
            lock.__exit__(None,None,None)

    def save(self, manifest, result=None, bank_raw=None):
        area=self.folder(manifest['probe_id'])
        with self._manifest_lock(area):
            path=area/'manifest.json'
            current=json.loads(path.read_text('utf-8')) if path.is_file() else None
            terminal={'finished','recovered_finished','cancelled','timed_out','interrupted','failed','blocked'}
            if current and current['state'] in terminal:
                # A collector may have parsed the Bank while the worker was
                # cancelling. Preserve the latest terminal lifecycle atomically.
                for key in ('state','execution','verdict','finished_at','error','timeout_phase','stopped_owned_pids'):
                    if key in current:manifest[key]=current[key]
            if result is not None:
                previous_path=area/'result.json'
                previous=json.loads(previous_path.read_text('utf-8')) if previous_path.is_file() else None
                def quality(value):
                    execution=value.get('execution')
                    complete=isinstance(execution,dict) and execution.get('state')=='complete'
                    phases=value.get('phases',{}).get('observed',{})
                    return (complete,sum(bool(phase.get('finished')) for phase in phases.values()),len(value.get('sections',{})))
                preserve_failure=(previous and manifest['state'] in {'cancelled','timed_out','interrupted','failed'}
                    and previous.get('verdict')=='failed' and result.get('verdict')!='failed'
                    and quality(previous)>=quality(result))
                if previous and (quality(previous)>quality(result) or preserve_failure):
                    source_status={key:result[key] for key in ('source_stale','evidence_status','source_context_error') if key in result}
                    result.clear();result.update(previous)
                    for key in ('source_stale','evidence_status','source_context_error'):result.pop(key,None)
                    result.update(source_status)
                    bank_raw=None
                result['run_state']=manifest['state']
                if manifest['state'] in {'cancelled','timed_out','interrupted','failed'}:
                    if result.get('verdict')!='failed':result['verdict']='partial'
                    result['termination_reason']=manifest['state']
                manifest['verdict']=result['verdict']
                if bank_raw is not None:atomic_write(area/'result.SC2Bank',bank_raw)
                write_json(area/'result.json',result)
            write_json(path,manifest)
        return manifest

    def prepare(self, root, template, parameters, *, source_context=None, candidate=None, assertions=None):
        from .probe_bank import parse_probe_bank
        parse_probe_bank(b'<Bank/>',assertions=assertions)
        probe_id=uuid.uuid4().hex
        raw,phases=render_template(template,parameters,probe_id)
        root=guard_absolute_path(Path(root)).resolve()
        before=snapshot(root)
        area=self.folder(probe_id); area.mkdir(parents=True,exist_ok=False)
        target=area/'diagnostic.SC2Map'; target.mkdir()
        for rel,path in map_files(root):
            dest=safe_path(target,rel); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dest)
        if snapshot(root)!=before or snapshot(target)!=before:
            raise SC2Error('baseline_conflict','复制期间源地图发生变化，未启动')
        changes={}
        if candidate:
            if candidate['state']!='prepared' or Path(candidate['root']).resolve()!=root:
                raise SC2Error('invalid_candidate','探针候选不属于源地图或状态不正确')
            if candidate.get('baseline')!=before:raise SC2Error('baseline_conflict','探针候选已过期')
            for entry in candidate['entries']:
                data=safe_path(self.state/'changes'/candidate['id']/'candidate',entry['path']).read_bytes() if entry['after'] is not None else None
                if (digest(data) if data is not None else None)!=entry['after']:raise SC2Error('candidate_corrupt','探针候选被修改')
                changes[entry['path']]=data
        changes['MapScript.galaxy']=raw
        changes['BankList.xml']=(f'<?xml version="1.0" encoding="utf-8"?>\n<BankList>\n    <Bank Name="SC2MCPProbe_{probe_id}" Player="1"/>\n</BankList>\n').encode()
        tx=Transactions(self.state).run(target,lambda:changes,label='probe_setup',validator=lambda c:validate_changes(target,c))
        archive=area/'diagnostic.SC2Map.mpq'
        # The launch filename must remain an actual .SC2Map archive.
        archive=area/'run.SC2Map'
        export=archives.export_archive(target,archive)
        manifest={'probe_id':probe_id,'run_id':probe_id,'state':'prepared','template':template,'template_version':TEMPLATE_VERSION,
            'parameters':parameters,'expected_phases':phases,'assertions':assertions or [],'source':str(root),'source_snapshot':before,
            'source_context':source_context,'change_id':candidate['id'] if candidate else None,'component_copy':str(target),
            'copy_snapshot':snapshot(target),'script_sha256':digest(raw),'archive':str(archive),'archive_sha256':digest(archive.read_bytes()),
            'bank_name':'SC2MCPProbe_'+probe_id,'transaction':tx,'export':export,'created_at':time.time(),
            'execution':'not_started','verdict':'not_observed','editor':'not_run','visual':'not_reviewed','owned_processes':[]}
        self.save(manifest)
        return manifest

    @staticmethod
    def owned_process(item, manifest):
        try:
            process=psutil.Process(item['pid'])
            verified=(abs(process.create_time()-item['created'])<0.001 and
                str(Path(process.exe()).resolve()).casefold()==item['executable'].casefold() and
                str(Path(manifest['archive']).resolve()).casefold() in [str(Path(arg).resolve()).casefold() for arg in process.cmdline()[1:] if not arg.startswith('-')])
            return process if verified else None
        except (psutil.Error,OSError,KeyError,ValueError):return None

    @staticmethod
    def verified_process(item, manifest):
        return Probes.owned_process(item,manifest) is not None

    def discover_owned(self, manifest):
        expected=str(Path(manifest['launch']['selected_client']).resolve()).casefold()
        for process in editor.processes(Path(manifest['installation'])):
            if (process.get('executable') or '').casefold()!=expected or process['created']<manifest['launched_at']-1:
                continue
            item={'pid':process['pid'],'created':process['created'],'executable':process['executable']}
            if self.verified_process(item,manifest) and item not in manifest['owned_processes']:
                manifest['owned_processes'].append(item)
        self.save(manifest)

    def stop_owned(self, manifest):
        stopped=[]
        for item in manifest.get('owned_processes',[]):
            process=self.owned_process(item,manifest)
            if process is not None:
                try:process.terminate(); stopped.append(item['pid'])
                except psutil.Error:pass
        return stopped

    def collect(self, probe_id):
        from .probe_bank import parse_probe_bank
        manifest=self.read(probe_id)
        result={'probe_id':probe_id,'execution':manifest['execution'],'verdict':manifest['verdict'],
            'source_stale':snapshot(Path(manifest['source']))!=manifest['source_snapshot'],
            'archive':manifest['archive'],'archive_sha256':manifest['archive_sha256'],'visual':'not_reviewed'}
        result['run_state']=manifest['state']
        if manifest.get('source_context'):
            from .source_context import assert_source_context_current
            try:assert_source_context_current(manifest['source_context'])
            except SC2Error as exc:
                result['source_stale']=True
                result['source_context_error']=exc.as_dict()
        if digest(Path(manifest['archive']).read_bytes())!=manifest['archive_sha256']:
            raise SC2Error('probe_archive_changed','探针归档改变，拒收结果')
        if not manifest.get('launch') or manifest.get('launched_at') is None:
            result['evidence_status']='not_launched'
            return result
        owner=manifest.get('worker');owner_alive=None
        if owner:
            try:owner_alive=abs(psutil.Process(owner['pid']).create_time()-owner['created'])<.001
            except (psutil.Error,KeyError,TypeError,ValueError):owner_alive=False
        result['worker_status']='unknown' if owner_alive is None else 'running' if owner_alive else 'exited'
        bankdir=editor.documents_root()/'Banks'
        # 98370 sanitizes the underscore in BankLoad's logical name when
        # creating its physical filename. RunId remains mandatory in either
        # spelling, so this cannot admit an unrelated/old player bank.
        names={manifest['bank_name']+'.SC2Bank',manifest['bank_name'].replace('_','')+'.SC2Bank'}
        matches=[p for name in names for p in bankdir.rglob(name)] if bankdir.is_dir() else []
        if len(matches)>1:raise SC2Error('ambiguous_probe_bank','多个位置存在同名探针 Bank，拒绝自动选择')
        archived=self.folder(probe_id)/'result.SC2Bank'
        if not matches and archived.is_file():matches=[archived]
        if matches:
            bank=matches[0]
            if bank!=archived and bank.stat().st_mtime < manifest.get('launched_at',manifest['created_at'])-1:
                raise SC2Error('stale_probe_bank','探针 Bank 早于本次启动')
            raw=bank.read_bytes()
            if bank==archived:
                previous=self.folder(probe_id)/'result.json'
                if previous.is_file() and json.loads(previous.read_text('utf-8')).get('bank_sha256')!=digest(raw):
                    raise SC2Error('probe_bank_changed','已归档探针Bank指纹改变，拒绝复用')
            parsed=parse_probe_bank(raw,expected_run_id=probe_id,expected_phases=manifest['expected_phases'],assertions=manifest['assertions'])
            evidence=self.folder(probe_id)/'result.SC2Bank'
            result.update(parsed,bank=str(evidence),bank_sha256=digest(raw),physical_bank_name=bank.name)
            result['bank_verdict']=parsed['verdict']
            if manifest['state'] in {'cancelled','timed_out','interrupted','failed'} and parsed['verdict']!='failed':
                result['verdict']='partial'
                result['termination_reason']=manifest['state']
            manifest.update(execution=parsed['execution']['state'],verdict=parsed['verdict'])
            manifest['verdict']=result['verdict']
            if owner_alive is False and manifest['state']=='launching':
                recovered='recovered_finished' if parsed['execution']['state']=='complete' else 'interrupted'
                manifest['state']=recovered;result['run_state']=recovered
                result['recovery']='worker_exited_bank_recovered'
                if recovered=='interrupted' and result['verdict']!='failed':result['verdict']='partial'
            if result['source_stale']:result['evidence_status']='stale_source'
            elif owner_alive is None:result['evidence_status']='worker_identity_unknown'
            else:result['evidence_status']='bound_runtime'
            self.save(manifest,result,raw)
        elif owner_alive is False and manifest['state']=='launching':
            manifest.update(state='interrupted',execution='partial',verdict='partial')
            result.update(run_state='interrupted',execution='partial',verdict='partial',evidence_status='no_bank',recovery='worker_exited_without_bank')
            self.save(manifest,result)
        return result

    def run(self, probe_id, installation, product='s2_cn', startup_timeout=120, probe_timeout=120, cancel=None):
        startup_timeout=_number(startup_timeout,'startup_timeout',1,600)
        probe_timeout=_number(probe_timeout,'probe_timeout',1,600)
        manifest=self.read(probe_id)
        installation=guard_absolute_path(Path(installation)).resolve()
        lock=self.state/'probe-installation-locks'/(digest(str(installation).casefold().encode())+'.lock')
        with file_lock(lock):
            # Recheck the persisted state inside the installation lock.
            manifest=self.read(probe_id)
            if manifest['state']!='prepared':raise SC2Error('probe_already_started','探针只能启动一次；重启后使用 result 回收')
            if cancel and cancel.is_set():
                manifest.update(state='cancelled',execution='not_started',verdict='partial');self.save(manifest)
                return self.collect(probe_id)
            existing=editor.processes(installation)
            if existing:
                manifest.update(state='blocked',execution='not_started',verdict='not_observed',blocked={'code':'application_running','processes':existing})
                self.save(manifest);return manifest
            if snapshot(Path(manifest['source']))!=manifest['source_snapshot']:
                raise SC2Error('baseline_conflict','探针源快照变化，请重新准备')
            if snapshot(Path(manifest['component_copy']))!=manifest['copy_snapshot'] or digest(Path(manifest['archive']).read_bytes())!=manifest['archive_sha256']:
                raise SC2Error('probe_archive_changed','探针组件或归档变化')
            if manifest.get('source_context'):
                from .source_context import assert_source_context_current
                assert_source_context_current(manifest['source_context'])
            logs={item['path']:item['bytes'] for item in editor.log_files(100)}
            manifest.update(installation=str(installation),state='launching',launched_at=time.time(),log_baselines=logs,
                worker={'pid':os.getpid(),'created':psutil.Process().create_time()})
            self.save(manifest)
            started=None
            try:
                if cancel and cancel.is_set():
                    manifest.update(state='cancelled',execution='not_started',verdict='partial');self.save(manifest)
                    return self.collect(probe_id)
                manifest['launch']=editor.launch_test(Path(manifest['archive']),installation,product)
                self.save(manifest)
                while True:
                    self.discover_owned(manifest)
                    if cancel and cancel.is_set():
                        manifest.update(state='cancelled',execution='partial',verdict='partial');break
                    try:result=self.collect(probe_id)
                    except SC2Error as exc:
                        if exc.code in {'stale_probe_bank','probe_archive_changed','ambiguous_probe_bank'}:raise
                        result={'execution':'partial','verdict':'partial','read_error':exc.as_dict()}
                    manifest=self.read(probe_id)
                    if result.get('bank') and started is None:started=time.monotonic()
                    if isinstance(result.get('execution'),dict) and result['execution']['state']=='complete':
                        manifest.update(state='finished',execution='complete',verdict=result['verdict']);break
                    elapsed=time.time()-manifest['launched_at']
                    if (started is None and elapsed>=startup_timeout) or (started is not None and time.monotonic()-started>=probe_timeout):
                        manifest.update(state='timed_out',execution='partial' if started is not None else 'not_started',verdict='partial',timeout_phase='probe' if started is not None else 'startup');break
                    if manifest['owned_processes'] and not any(self.verified_process(p,manifest) for p in manifest['owned_processes']):
                        manifest.update(state='interrupted',execution='partial',verdict='partial');break
                    if cancel and hasattr(cancel,'report_progress'):cancel.report_progress(20 if started is None else 60,'等待探针启动' if started is None else '收集阶段观测')
                    time.sleep(.25)
            except BaseException as exc:
                manifest.update(state='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
                    execution='partial',verdict='partial',error=exc.as_dict() if isinstance(exc,SC2Error) else
                    {'code':type(exc).__name__,'message':str(exc)})
                raise
            finally:
                manifest['stopped_owned_pids']=self.stop_owned(manifest)
                manifest['finished_at']=time.time()
                self.save(manifest)
                deltas=[]
                for item in editor.log_files(100):
                    path=Path(item['path']); offset=logs.get(item['path'],0)
                    # Only read log increments; never replace the user's logs.
                    with path.open('rb') as stream:
                        stream.seek(offset if item['bytes']>=offset else 0);raw=stream.read(4*1024*1024)
                    if raw:
                        target=self.folder(probe_id)/'logs'/(digest(str(path).encode())[:12]+'_'+path.name)
                        target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
                        deltas.append({'source':str(path),'offset':offset,'file':str(target),'sha256':digest(raw)})
                manifest['log_deltas']=deltas;self.save(manifest)
            result=self.collect(probe_id)
            result['run_state']=manifest['state'];result['manifest']=str(self.folder(probe_id)/'manifest.json')
            return result
