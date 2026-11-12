"""Offline production-map smoke tests using the existing probe lifecycle."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from .errors import SC2Error
from .storage import digest, snapshot


def probe_identity(token):
    return digest(token.encode())[:32]


def validate_options(sample_seconds, startup_timeout, probe_timeout):
    from .probes import _number
    _number(sample_seconds, 'sample_seconds', .25, 600)
    _number(startup_timeout, 'startup_timeout', 1, 600)
    _number(probe_timeout, 'probe_timeout', 1, 600)


def proof_lines(token, sample_seconds=5):
    validate_options(sample_seconds, 120, 120)
    run_id = probe_identity(token)
    return [
        'bank offlineBank;',
        f'offlineBank = BankLoad("SC2MCPProbe_{run_id}", 1);',
        f'BankValueSetFromString(offlineBank, "Run", "RunId", "{run_id}");',
        f'BankValueSetFromString(offlineBank, "Run", "RuntimeMarker", "GUI_OFFLINE_EXEC_{token}");',
        'BankValueSetFromString(offlineBank, "Run", "Status", "STARTED");',
        'BankValueSetFromString(offlineBank, "MapInit", "StageStatus", "FINISHED");',
        'BankSave(offlineBank);',
        f'Wait({sample_seconds:.4f}, c_timeGame);',
        'BankValueSetFromFixed(offlineBank, "Heartbeat", "GameTime", GameGetMissionTime());',
        'BankValueSetFromString(offlineBank, "Heartbeat", "StageStatus", "FINISHED");',
        'BankValueSetFromString(offlineBank, "Run", "Status", "FINISHED");',
        'BankSave(offlineBank);',
    ]


def evaluate_logs(deltas):
    result = {'errors': [], 'warnings': []}
    for item in deltas:
        if item.get('sha256') and digest(Path(item['file']).read_bytes()) != item['sha256']:
            raise SC2Error('offline_log_changed', 'Archived runtime log changed.')
        for line in Path(item['file']).read_text('utf-8-sig', errors='replace').splitlines():
            if re.search(r'(?i)((?:script|trigger).*(?:error|failed|exception)|(?:error|failed).*(?:script|trigger)|syntax error|native.*prototype.*mismatch|undeclared (?:identifier|variable)|divis?ion by zero|divide by zero)', line):
                result['errors'].append({'file': item['file'], 'text': line})
            elif re.search(r'(?i)\bwarning\b', line):
                result['warnings'].append({'file': item['file'], 'text': line})
    return result


def context_covers_build(build, context):
    """Reuse only a freshly verified, complete inventory of every script root."""
    norm=lambda p: os.path.normcase(os.path.normpath(p))
    inventories={norm(p):files for p,files in context.get('inventories',{}).items()}
    if not build.get('root') or norm(build['root']) not in inventories:
        return False
    fingerprints={norm(p):sha for p,sha in context.get('fingerprints',{}).items()}
    client=context.get('build')
    if client:
        fingerprints[norm(str(Path(client['installation'])/'.build.info'))]=client['build_info_sha256']
    records={**build.get('inputs',{}), **build.get('resources',{})}
    for record in build.get('scripts',{}).values():
        path=norm(record['path'])
        if not any(path.startswith(root+os.sep) for root in inventories):
            return False
        records[record['path']]=record
    return all(fingerprints.get(norm(path))==record['sha256'] for path,record in records.items())


def enrich_result(manifest, result, *, context_verified=False):
    """Re-evaluate immutable evidence on every collection, including recovery."""
    if manifest.get('template') != 'offline_map_smoke':
        return result
    result.update(build_id=manifest['build_id'], scope='map_smoke', editor='not_run',
                  runtime_marker=manifest['runtime_marker'], log_deltas=manifest.get('log_deltas', []))
    try:
        result['logs'] = evaluate_logs(result['log_deltas'])
    except (SC2Error, OSError) as exc:
        result['logs'] = {'errors': [], 'warnings': [], 'error': str(exc)}
        result.update(source_stale=True, evidence_status='changed_logs')
    try:
        from .trigger_pipeline import target_for, controlled_files
        build_path=Path(manifest['build_manifest'])
        if digest(build_path.read_bytes()) != manifest['build_manifest_sha256']:
            raise SC2Error('galaxy_build_stale', 'Build manifest changed')
        build=json.loads(build_path.read_text('utf-8'))
        if context_verified and context_covers_build(build,manifest['source_context']):
            result['freshness_validation']='verified_source_context'
        else:
            result['freshness_validation']='reparsed_trigger_graph'
            target=target_for(Path(manifest['source']), build['mods_dir'])
            _,scripts=controlled_files(target, skip_generated=True)
            if target.problems or target.inputs != build['inputs'] or scripts != build['scripts']:
                raise SC2Error('galaxy_build_stale', 'Build inputs changed')
            for path, record in build.get('resources', {}).items():
                if digest(Path(path).read_bytes()) != record['sha256']:
                    raise SC2Error('galaxy_build_stale', 'Resource input changed')
    except (SC2Error, OSError) as exc:
        result.update(source_stale=True, evidence_status='stale_source', build_error=str(exc))
    if result['logs']['errors']:
        result['verdict'] = 'failed'
    elif result.get('source_stale') or manifest['state'] not in {'finished', 'recovered_finished'}:
        if result.get('verdict') != 'failed':
            result['verdict'] = 'partial'
    result['packaged_runtime_passed'] = (result.get('verdict') == 'complete'
        and result.get('evidence_status') == 'bound_runtime' and bool(result.get('bank'))
        and manifest.get('logs_collected', False))
    return result


def run_test(service, project_id, installation, product, sample_seconds, startup_timeout, probe_timeout, cancel):
    from . import trigger_pipeline, trigger_package
    validate_options(sample_seconds, startup_timeout, probe_timeout)
    timings={}
    def step(phase, fn):
        started=time.perf_counter()
        try:
            return fn()
        except SC2Error as exc:
            error=exc.as_dict()
            raise SC2Error(error['code'],error['message'],**{
                **error.get('details',{}),'phase':phase,
                'editor_required':False,
                'next_action':'diagnose_offline_generation' if error['code']=='trigger_generation_unsupported' else 'diagnose_failure',
                'stage_seconds':{**timings,phase:round(time.perf_counter()-started,3)}}) from exc
        finally:
            timings[phase]=round(time.perf_counter()-started,3)
    _, root = service.record(project_id)
    if root.suffix.lower() != '.sc2map':
        raise SC2Error('offline_map_required', 'Runtime tests require an explicit map, not a Mod.')
    before = step('snapshot',lambda:snapshot(root))
    context = step('dependencies',lambda:service.prepare_dependencies(project_id, installation=installation, product=product))
    validation = step('static',lambda:service.validate(project_id))
    if validation['static'] != 'passed':
        raise SC2Error('offline_static_failed', 'Map static validation failed.', report=validation)
    if cancel and cancel.is_set():
        return {'verdict': 'partial', 'execution': 'not_started'}
    build = step('generate',lambda:trigger_pipeline.generate(service, project_id, runtime_probe=True, sample_seconds=sample_seconds, runtime_smoke=True))
    package = step('package',lambda:trigger_package.package_build(service, project_id, build['build_id']))
    area = Path(package['archive']).parent
    probe_id = probe_identity(package['runtime_marker'].removeprefix('GUI_OFFLINE_EXEC_'))
    manifest = dict(probe_id=probe_id, run_id=probe_id, state='prepared', template='offline_map_smoke',
        template_version='1', project_id=project_id, build_id=build['build_id'],
        build_manifest=build['manifest'], build_manifest_sha256=digest(Path(build['manifest']).read_bytes()),
        runtime_marker=package['runtime_marker'], expected_phases=['MapInit', 'Heartbeat'],
        assertions=[dict(id='offline_execution', section='Run', key='RuntimeMarker', operator='eq', expected=package['runtime_marker'])],
        source=str(root), source_snapshot=before, source_context=context,
        component_copy=str(area/'assembly'), copy_snapshot=snapshot(area/'assembly'),
        archive=package['archive'], archive_sha256=package['archive_sha256'],
        bank_name='SC2MCPProbe_'+probe_id, created_at=time.time(), execution='not_started',
        verdict='not_observed', editor='not_run', visual='not_reviewed', owned_processes=[])
    service.probes.save(manifest)
    result = step('runtime',lambda:service.probes.run(probe_id, installation, product, startup_timeout, probe_timeout, cancel))
    result['stage_seconds']=timings
    result.setdefault('packaged_runtime_passed', False)
    result.setdefault('scope', 'map_smoke')
    result.setdefault('build_id', build['build_id'])
    return result
