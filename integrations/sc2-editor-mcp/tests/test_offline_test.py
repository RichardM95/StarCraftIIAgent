import pytest
from types import SimpleNamespace
from sc2_mcp.offline_test import proof_lines, evaluate_logs, validate_options
from sc2_mcp.errors import SC2Error


def test_verified_context_covers_build_without_reparsing(tmp_path, monkeypatch):
    import json
    from sc2_mcp.offline_test import enrich_result
    from sc2_mcp.storage import digest
    from sc2_mcp import trigger_pipeline
    source=tmp_path/'Map.SC2Map';source.mkdir()
    script=source/'extra.galaxy'
    build={'root':str(source),'mods_dir':str(tmp_path),'inputs':{},
           'scripts':{'extra.galaxy':{'path':str(script),'sha256':'bytes'}}}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(build))
    context={'root':str(source),'fingerprints':{str(script):'bytes'},
             'inventories':{str(source):{'extra.galaxy':'bytes'}}}
    manifest={'template':'offline_map_smoke','build_id':'build','runtime_marker':'proof',
        'source':str(source),'source_context':context,'build_manifest':str(path),
        'build_manifest_sha256':digest(path.read_bytes()),'state':'finished','logs_collected':True}
    monkeypatch.setattr(trigger_pipeline,'target_for',lambda *a:pytest.fail('already verified full source inventories'))
    result=enrich_result(manifest,{'verdict':'complete','evidence_status':'bound_runtime','bank':'bank'},context_verified=True)
    assert result['packaged_runtime_passed'] is True
    assert result['freshness_validation']=='verified_source_context'


def test_long_real_project_sample_and_incomplete_coverage():
    from sc2_mcp.offline_test import context_covers_build
    assert 'Wait(90.0000, c_timeGame);' in proof_lines('abcdef123456',90)
    assert not context_covers_build({'root':'map','inputs':{'new':{'sha256':'x'}}},
                                  {'inventories':{'map':{}},'fingerprints':{}})


def test_proof_records_unique_run_and_game_heartbeat():
    code = '\n'.join(proof_lines('abcdef123456', 5))
    assert 'bank offlineBank;' in code
    assert 'SC2MCPProbe_' in code
    assert '"MapInit", "StageStatus", "FINISHED"' in code
    assert 'Wait(5.0000, c_timeGame)' in code
    assert code.index('"STARTED"') < code.index('Wait(') < code.index('"Heartbeat"')


def test_log_errors_fail_but_warnings_are_separate(tmp_path):
    log = tmp_path/'script.log'
    log.write_text('Warning: missing texture\nScript runtime error: division by zero\n')
    result = evaluate_logs([{'file': str(log)}])
    assert len(result['errors']) == 1
    assert len(result['warnings']) == 1


def test_observed_native_division_error_is_rejected(tmp_path):
    import json
    from pathlib import Path
    proof=json.loads((Path(__file__).parent/'fixtures/trigger-pipeline/offline-smoke-98370.json').read_text('utf-8'))
    log=tmp_path/'ScriptError.txt'
    log.write_text('\n'.join(proof['intentional_runtime_failure']['error_lines']),encoding='utf-8')
    assert evaluate_logs([{'file':str(log)}])['errors']


@pytest.mark.parametrize('value', [True, 0, -1, float('nan'), 601])
def test_invalid_timeouts_do_not_launch(value):
    with pytest.raises(SC2Error):
        validate_options(5, value, 120)


def test_changed_log_evidence_is_rejected(tmp_path):
    log=tmp_path/'runtime.log'
    log.write_text('clean')
    with pytest.raises(SC2Error):
        evaluate_logs([{'file':str(log),'sha256':'changed'}])


def test_cancelled_save_clears_previous_runtime_success(tmp_path):
    from sc2_mcp.probes import Probes
    probes=Probes(tmp_path)
    manifest={'probe_id':'a'*32,'state':'cancelled','template':'offline_map_smoke','logs_collected':True}
    probes.folder(manifest['probe_id']).mkdir(parents=True)
    result={'verdict':'complete','packaged_runtime_passed':True,'evidence_status':'bound_runtime'}
    probes.save(manifest,result)
    assert result['verdict']=='partial'
    assert result['packaged_runtime_passed'] is False


def test_client_discovery_normalizes_equivalent_executable_paths(tmp_path, monkeypatch):
    from sc2_mcp.probes import Probes
    from sc2_mcp import editor
    exe=str((tmp_path/'SC2_x64.exe').resolve())
    # Process APIs can report duplicate Windows separators.
    reported=exe.replace('\\', '\\\\')
    manifest={'launch':{'selected_client':exe},'installation':str(tmp_path),
              'launched_at':1,'owned_processes':[]}
    monkeypatch.setattr(editor,'processes',lambda *_:[{'pid':42,'created':2,'executable':reported}])
    monkeypatch.setattr(Probes,'verified_process',staticmethod(lambda item,_:item['executable']==exe))
    monkeypatch.setattr(Probes,'save',lambda *args:None)
    Probes(tmp_path).discover_owned(manifest)
    assert manifest['owned_processes']==[{'pid':42,'created':2,'executable':exe}]


@pytest.mark.parametrize('failure', ['static', 'generator', 'unsupported', 'mod', 'cancel'])
def test_failure_paths_never_launch_editor_or_game(tmp_path, monkeypatch, failure):
    from sc2_mcp import trigger_pipeline, editor
    from sc2_mcp.offline_test import run_test
    root=tmp_path/('Test.SC2Mod' if failure=='mod' else 'Test.SC2Map')
    root.mkdir()
    def no_launch(*args, **kwargs):
        pytest.fail('failure must not launch an application')
    monkeypatch.setattr(editor,'launch_test',no_launch)
    monkeypatch.setattr(editor,'open_editor',no_launch)
    calls=[]
    def generate(*args, **kwargs):
        calls.append('generate')
        raise SC2Error('trigger_generation_unsupported' if failure=='unsupported' else 'unsupported_node','unsupported GUI node')
    monkeypatch.setattr(trigger_pipeline,'generate',generate)
    service=SimpleNamespace(record=lambda _:({},root),
        prepare_dependencies=lambda *a,**k:{},
        validate=lambda _:{'static':'failed' if failure=='static' else 'passed'})
    cancel=SimpleNamespace(is_set=lambda:True) if failure=='cancel' else None
    if failure=='cancel':
        assert run_test(service,'test','install','s2',5,120,120,cancel)['verdict']=='partial'
    else:
        with pytest.raises(SC2Error) as captured:
            run_test(service,'test','install','s2',5,120,120,cancel)
        if failure in {'generator','unsupported'}:
            detail=captured.value.as_dict()['details']
            assert detail['phase']=='generate'
            assert detail['editor_required'] is (failure=='unsupported')
    assert calls == (['generate'] if failure in {'generator','unsupported'} else [])


def test_background_entry_preserves_legacy_interface(tmp_path, monkeypatch):
    from sc2_mcp.operations import create_operations
    from sc2_mcp.service import Service
    service=Service(tmp_path/'state')
    monkeypatch.setattr(service.jobs,'submit',lambda name,fn:{'job_id':'test-job','kind':name})
    operations=create_operations(service)
    assert 'sc2_validate_launch_test' in operations
    result=operations['sc2_validate_run_test'][0]('map','install',product='s2')
    assert result=={'job_id':'test-job','kind':'offline_map_smoke'}


def test_orchestration_builds_fresh_code_and_preserves_product(tmp_path, monkeypatch):
    from sc2_mcp import trigger_pipeline, trigger_package, editor
    from sc2_mcp.offline_test import run_test
    root=tmp_path/'Map.SC2Map';root.mkdir()
    (root/'Triggers').write_text('new GUI')
    build=tmp_path/'build.json';build.write_text('{}')
    assembly=tmp_path/'assembly';assembly.mkdir()
    events=[];saved=[]
    def generate(*args, **kwargs):
        assert kwargs=={'runtime_probe':True,'sample_seconds':2,'runtime_smoke':True}
        assert (root/'Triggers').read_text()=='new GUI'
        events.append('generate')
        return {'build_id':'fresh','manifest':str(build)}
    def package(*args):
        assert args[-1]=='fresh';events.append('package')
        return {'archive':str(tmp_path/'map.SC2Map'),'archive_sha256':'hash','runtime_marker':'GUI_OFFLINE_EXEC_abcdef123456'}
    def run(probe_id,installation,product,*args):
        assert saved[0]['build_id']=='fresh'
        assert product=='s2'
        events.append('run');return {'probe_id':probe_id}
    monkeypatch.setattr(trigger_pipeline,'generate',generate)
    monkeypatch.setattr(trigger_package,'package_build',package)
    monkeypatch.setattr(editor,'open_editor',lambda *a:pytest.fail('Editor must not launch'))
    service=SimpleNamespace(record=lambda _:({},root),prepare_dependencies=lambda *a,**k:{},
        validate=lambda _:{'static':'passed'},probes=SimpleNamespace(save=saved.append,run=run))
    result=run_test(service,'map','install','s2',2,120,120,None)
    assert events==['generate','package','run']
    assert result['packaged_runtime_passed'] is False
    assert (root/'Triggers').read_text()=='new GUI'


@pytest.mark.parametrize('condition, passed', [('valid',True),('log_error',False),('stale',False),('timeout',False),('no_logs',False)])
def test_scoped_success_requires_current_bound_evidence(tmp_path, monkeypatch, condition, passed):
    import json
    from sc2_mcp import trigger_pipeline
    from sc2_mcp.offline_test import enrich_result
    from sc2_mcp.storage import digest
    build=tmp_path/'manifest.json'
    build.write_text(json.dumps({'mods_dir':str(tmp_path),'inputs':{},'scripts':{}}))
    target=SimpleNamespace(problems=[],inputs={})
    monkeypatch.setattr(trigger_pipeline,'target_for',lambda *a:target)
    monkeypatch.setattr(trigger_pipeline,'controlled_files',lambda *a,**k:({},{}))
    manifest={'template':'offline_map_smoke','build_id':'build','runtime_marker':'proof',
        'build_manifest':str(build),'build_manifest_sha256':digest(build.read_bytes()),
        'source':str(tmp_path),'state':'timed_out' if condition=='timeout' else 'finished',
        'logs_collected':condition!='no_logs'}
    if condition=='stale':build.write_text('{}')
    if condition=='log_error':
        log=tmp_path/'script.log';log.write_text('Script runtime error: failure')
        manifest['log_deltas']=[{'file':str(log)}]
    result=enrich_result(manifest,{'verdict':'complete','evidence_status':'bound_runtime','bank':'bank'})
    assert result['packaged_runtime_passed'] is passed
    assert result['editor']=='not_run'
    assert result['scope']=='map_smoke'
