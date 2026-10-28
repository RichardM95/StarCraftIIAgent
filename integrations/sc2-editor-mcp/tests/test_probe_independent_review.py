"""Read-only reproductions of issues in the reviewed main-source snapshot.

Some tests demonstrate remaining defects; the others verify reviewed fixes.
No real SC2 process is launched or terminated.
"""
from pathlib import Path
import threading
import os

import pytest

from sc2_mcp import editor, probes
from sc2_mcp.errors import SC2Error


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / 'source.SC2Map'
    root.mkdir()
    (root / 'DocumentInfo').write_bytes(b'<DocInfo><Dependencies/></DocInfo>')
    (root / 'MapScript.galaxy').write_bytes(b'void InitMap () {}\n')
    (root / 'BankList.xml').write_bytes(b'<BankList/>')
    def export(source, destination):
        destination.write_bytes(b'MPQ-fixture')
        return {'test_backend': True}
    monkeypatch.setattr(probes.archives, 'export_archive', export)
    docs = tmp_path / 'Documents'
    (docs / 'Banks').mkdir(parents=True)
    monkeypatch.setattr(editor, 'documents_root', lambda: docs)
    monkeypatch.setattr(editor, 'processes', lambda *args: [])
    monkeypatch.setattr(editor, 'log_files', lambda *args: [])
    manager = probes.Probes(tmp_path / 'state')
    manifest = manager.prepare(root, 'catalog_snapshot', {'object_id': 'HighTemplar', 'fields': ['LifeMax']})
    return manager, manifest, docs


def launch_record(manifest):
    return {'selected_client': str(Path(manifest['archive']).parent / 'SC2_x64.exe'), 'build': {'version': '98370'}}


def bank(manifest, docs, run_id=None):
    raw = (f'<Bank><Section name="Run"><Key name="RunId"><Value string="{run_id or manifest["run_id"]}"/></Key>'
           '<Key name="Status"><Value string="FINISHED"/></Key></Section><Section name="Catalog">'
           '<Key name="StageStatus"><Value string="FINISHED"/></Key><Key name="LifeMax"><Value string="150"/></Key>'
           '</Section></Bank>').encode()
    (docs / 'Banks' / (manifest['bank_name'] + '.SC2Bank')).write_bytes(raw)


def test_launch_error_is_persisted_as_failed(prepared, monkeypatch):
    manager, manifest, _ = prepared
    def fail(*args):
        raise SC2Error('LAUNCH_FAILED', 'fixture failure')
    monkeypatch.setattr(editor, 'launch_test', fail)
    with pytest.raises(SC2Error):
        manager.run(manifest['probe_id'], manager.state / 'install')
    stored = manager.read(manifest['probe_id'])
    assert stored['state'] == 'failed'
    assert stored['execution'] == 'partial' and stored['verdict'] == 'partial'
    assert stored['error']['code'] == 'LAUNCH_FAILED'


@pytest.mark.parametrize('failure', ['exception', 'interrupt'])
def test_loop_abnormal_exit_is_persisted_as_failed_or_interrupted(prepared, monkeypatch, failure):
    manager, manifest, _ = prepared
    monkeypatch.setattr(editor, 'launch_test', lambda *args: launch_record(manifest))
    error = RuntimeError('fixture error') if failure == 'exception' else KeyboardInterrupt()
    def fail(*args):
        raise error
    monkeypatch.setattr(manager, 'discover_owned', fail)
    with pytest.raises(type(error)):
        manager.run(manifest['probe_id'], manager.state / 'install')
    stored = manager.read(manifest['probe_id'])
    assert stored['state'] == ('failed' if failure == 'exception' else 'interrupted')
    assert stored['execution'] == 'partial' and stored['verdict'] == 'partial'
    assert 'finished_at' in stored


def test_already_cancelled_token_never_launches(prepared, monkeypatch):
    manager, manifest, _ = prepared
    calls = []
    def launch(*args):
        calls.append(args)
        return launch_record(manifest)
    monkeypatch.setattr(editor, 'launch_test', launch)
    token = threading.Event()
    token.set()
    result = manager.run(manifest['probe_id'], manager.state / 'install', cancel=token)
    assert calls == []
    assert result['run_state'] == 'cancelled'


def test_stop_owned_terminates_the_same_verified_process_object(prepared, monkeypatch):
    manager, manifest, _ = prepared
    item = {'pid': 123456789, 'created': 100., 'executable': str(manager.state / 'SC2_x64.exe')}
    manifest['owned_processes'] = [item]
    terminated = []
    class Original:
        def create_time(self): return item['created']
        def exe(self): return item['executable']
        def cmdline(self): return [item['executable'], '-run', manifest['archive']]
        def terminate(self): terminated.append('verified original process')
    class Reused:
        def create_time(self): return 200.
        def exe(self): return str(manager.state / 'unrelated.exe')
        def cmdline(self): return ['unrelated.exe']
        def terminate(self): terminated.append('unrelated process')
    sequence = iter([Original(), Reused()])
    monkeypatch.setattr(probes.psutil, 'Process', lambda pid: next(sequence))
    stopped = manager.stop_owned(manifest)
    assert stopped == [item['pid']] and terminated == ['verified original process']
    assert isinstance(next(sequence), Reused)


@pytest.mark.parametrize('mismatch', ['pid_missing', 'created', 'exe', 'archive'])
def test_stop_owned_refuses_identity_or_archive_mismatch(prepared, monkeypatch, mismatch):
    manager, manifest, _ = prepared
    item = {'pid': 123456789, 'created': 100., 'executable': str(manager.state / 'SC2_x64.exe')}
    manifest['owned_processes'] = [item]
    class Process:
        def create_time(self): return 200. if mismatch == 'created' else item['created']
        def exe(self): return str(manager.state / 'other.exe') if mismatch == 'exe' else item['executable']
        def cmdline(self): return [item['executable'], '-run', 'other.SC2Map' if mismatch == 'archive' else manifest['archive']]
        def terminate(self): pytest.fail('must not terminate an unmatched process')
    def process(pid):
        if mismatch == 'pid_missing': raise probes.psutil.NoSuchProcess(pid)
        return Process()
    monkeypatch.setattr(probes.psutil, 'Process', process)
    assert manager.stop_owned(manifest) == []


def test_unlaunched_records_refuse_complete_bank(prepared):
    manager, manifest, docs = prepared
    bank(manifest, docs)
    prepared_result = manager.collect(manifest['probe_id'])
    assert prepared_result['run_state'] == 'prepared' and prepared_result['verdict'] == 'not_observed'
    assert prepared_result['evidence_status'] == 'not_launched' and 'binding' not in prepared_result
    manifest = manager.read(manifest['probe_id'])
    manifest['state'] = 'launching'
    manager.save(manifest)
    result = manager.collect(manifest['probe_id'])
    assert result['evidence_status'] == 'not_launched' and 'sections' not in result


def test_complete_archived_bank_can_be_recovered_after_external_cleanup(prepared):
    manager, manifest, docs = prepared
    manifest.update(state='finished', launch=launch_record(manifest), launched_at=manifest['created_at'],
                    worker={'pid': os.getpid(), 'created': probes.psutil.Process().create_time()})
    manager.save(manifest)
    bank(manifest, docs)
    manager.collect(manifest['probe_id'])
    for path in (docs / 'Banks').glob('*.SC2Bank'):
        path.unlink()
    recovered = probes.Probes(manager.state).collect(manifest['probe_id'])
    assert recovered['run_state'] == 'finished' and recovered['verdict'] == 'complete'
    assert recovered['evidence_status'] == 'bound_runtime'


@pytest.mark.parametrize('phase', ['complete', 'partial', 'missing'])
def test_orphan_worker_recovery_classifies_finished_partial_and_missing_bank(prepared, monkeypatch, phase):
    manager, manifest, docs = prepared
    manifest.update(state='launching', launch=launch_record(manifest), launched_at=manifest['created_at'],
                    worker={'pid': 123456789, 'created': 100.})
    manager.save(manifest)
    if phase != 'missing':
        bank(manifest, docs)
        if phase == 'partial':
            path = docs / 'Banks' / (manifest['bank_name'] + '.SC2Bank')
            path.write_bytes(path.read_bytes().replace(b'string="FINISHED"', b'string="STARTED"'))
    def process(pid): raise probes.psutil.NoSuchProcess(pid)
    monkeypatch.setattr(probes.psutil, 'Process', process)
    result = probes.Probes(manager.state).collect(manifest['probe_id'])
    assert result['run_state'] == ('recovered_finished' if phase == 'complete' else 'interrupted')
    assert result['verdict'] == ('complete' if phase == 'complete' else 'partial')
    assert result['worker_status'] == 'exited'


def test_legacy_worker_identity_is_explicitly_unknown(prepared):
    manager, manifest, docs = prepared
    manifest.update(state='finished', launch=launch_record(manifest), launched_at=manifest['created_at'])
    manager.save(manifest)
    bank(manifest, docs)
    result = manager.collect(manifest['probe_id'])
    assert result['worker_status'] == 'unknown' and result['evidence_status'] == 'worker_identity_unknown'


@pytest.mark.parametrize('failure', ['run_id', 'timestamp', 'ambiguous', 'archive'])
def test_collector_rejects_old_or_ambiguous_bank_and_changed_archive(prepared, failure):
    manager, manifest, docs = prepared
    manifest.update(state='finished', launch=launch_record(manifest), launched_at=manifest['created_at'])
    manager.save(manifest)
    bank(manifest, docs, run_id='old-run-id' if failure == 'run_id' else None)
    path = docs / 'Banks' / (manifest['bank_name'] + '.SC2Bank')
    if failure == 'timestamp':
        os.utime(path, (manifest['created_at'] - 10, manifest['created_at'] - 10))
    elif failure == 'ambiguous':
        other = path.parent / 'other-profile' / path.name
        other.parent.mkdir()
        other.write_bytes(path.read_bytes())
    elif failure == 'archive':
        Path(manifest['archive']).write_bytes(b'changed archive')
    expected = {'run_id': 'stale_probe_bank', 'timestamp': 'stale_probe_bank',
                'ambiguous': 'ambiguous_probe_bank', 'archive': 'probe_archive_changed'}
    with pytest.raises(SC2Error) as exc:
        manager.collect(manifest['probe_id'])
    assert exc.value.code == expected[failure]


def test_explain_catalog_refuses_partial_termination(prepared, monkeypatch):
    from sc2_mcp.service import Service
    from sc2_mcp import source_context, catalog_explain
    manager, manifest, docs = prepared
    context = {'source_context_id': 'a' * 64, 'roots': [manifest['source']], 'build': {'version': '98370'}}
    manifest.update(project_id='project', source_context=context, state='cancelled', launch=launch_record(manifest), launched_at=manifest['created_at'])
    manager.save(manifest)
    monkeypatch.setattr(source_context, 'assert_source_context_current', lambda value: None)
    bank(manifest, docs)
    service = Service.__new__(Service)
    service.probes = manager
    service.source_context = lambda *args: context
    monkeypatch.setattr(catalog_explain, 'catalog_explain', lambda *args: args[-1])
    with pytest.raises(SC2Error) as exc:
        service.explain_catalog('project', 'Unit', 'HighTemplar', ['LifeMax'], context['source_context_id'], {'probe_id': manifest['probe_id']})
    assert exc.value.code == 'runtime_evidence_mismatch'
    assert manager.collect(manifest['probe_id'])['verdict'] == 'partial'


def test_invalid_assertions_are_rejected_before_export(prepared, monkeypatch):
    manager, manifest, _ = prepared
    monkeypatch.setattr(probes.archives, 'export_archive', lambda *args: pytest.fail('invalid assertions must fail before export'))
    with pytest.raises(SC2Error) as exc:
        manager.prepare(Path(manifest['source']), 'catalog_snapshot',
            {'object_id': 'HighTemplar', 'fields': ['LifeMax']}, assertions=[{'operator': 'typo'}])
    assert exc.value.code == 'invalid_assertion'


def test_candidate_context_mismatch_is_rejected(prepared):
    from sc2_mcp.service import Service
    from sc2_mcp.storage import snapshot
    manager, manifest, _ = prepared
    service = Service.__new__(Service)
    service.probes = manager
    root = Path(manifest['source'])
    service.record = lambda *args: ({}, root)
    context = {'source_context_id': 'b' * 64}
    service.source_context = lambda *args: context
    candidate = {'id': 'c' * 32, 'state': 'prepared', 'root': str(root), 'baseline': snapshot(root),
                 'entries': [], 'source_context_id': 'a' * 64}
    class Transactions:
        def read(self, key): return candidate
    service.transactions = Transactions()
    with pytest.raises(SC2Error) as exc:
        service.prepare_probe('project', 'catalog_snapshot', {'object_id': 'HighTemplar', 'fields': ['LifeMax']},
                              source_context_id=context['source_context_id'], change_id=candidate['id'])
    assert exc.value.code == 'source_context_mismatch'


def test_concurrent_collection_preserves_sticky_cancelled_state(prepared, monkeypatch):
    from sc2_mcp import probe_bank
    manager, manifest, docs = prepared
    manifest.update(state='launching', launch=launch_record(manifest), launched_at=manifest['created_at'],
                    worker={'pid': os.getpid(), 'created': probes.psutil.Process().create_time()})
    manager.save(manifest)
    bank(manifest, docs)
    parse = probe_bank.parse_probe_bank
    def cancellation_during_bank_parse(*args, **kwargs):
        current = manager.read(manifest['probe_id'])
        current.update(state='cancelled', execution='partial', verdict='partial')
        manager.save(current)
        return parse(*args, **kwargs)
    monkeypatch.setattr(probe_bank, 'parse_probe_bank', cancellation_during_bank_parse)
    result = manager.collect(manifest['probe_id'])
    stored = manager.read(manifest['probe_id'])
    assert stored['state'] == 'cancelled' and stored['verdict'] == 'partial'
    assert result['verdict'] == 'partial' and result['run_state'] == 'cancelled'


def test_late_partial_collection_preserves_complete_archived_bank(prepared, monkeypatch):
    from sc2_mcp import probe_bank
    manager, manifest, docs = prepared
    manifest.update(state='launching', launch=launch_record(manifest), launched_at=manifest['created_at'],
                    worker={'pid': os.getpid(), 'created': probes.psutil.Process().create_time()})
    manager.save(manifest)
    bank(manifest, docs)
    path = docs / 'Banks' / (manifest['bank_name'] + '.SC2Bank')
    complete = path.read_bytes()
    partial = complete.replace(b'string="FINISHED"', b'string="STARTED"')
    path.write_bytes(partial)
    parse = probe_bank.parse_probe_bank
    nested = False
    def completion_during_older_parse(*args, **kwargs):
        nonlocal nested
        parsed = parse(*args, **kwargs)
        if not nested:
            nested = True
            path.write_bytes(complete)
            assert manager.collect(manifest['probe_id'])['verdict'] == 'complete'
            current = manager.read(manifest['probe_id'])
            current.update(state='finished', execution='complete', verdict='complete')
            manager.save(current)
        return parsed
    monkeypatch.setattr(probe_bank, 'parse_probe_bank', completion_during_older_parse)
    result = manager.collect(manifest['probe_id'])
    stored = manager.read(manifest['probe_id'])
    assert stored['state'] == 'finished' and stored['verdict'] == 'complete'
    assert result['run_state'] == 'finished' and result['verdict'] == 'complete'
    assert (manager.folder(manifest['probe_id']) / 'result.SC2Bank').read_bytes() == complete


def test_preserved_complete_result_keeps_current_source_staleness(prepared):
    manager, manifest, docs = prepared
    manifest.update(state='finished', launch=launch_record(manifest), launched_at=manifest['created_at'],
                    worker={'pid': os.getpid(), 'created': probes.psutil.Process().create_time()})
    manager.save(manifest)
    bank(manifest, docs)
    assert manager.collect(manifest['probe_id'])['verdict'] == 'complete'
    (Path(manifest['source']) / 'external-change.txt').write_bytes(b'changed source')
    path = docs / 'Banks' / (manifest['bank_name'] + '.SC2Bank')
    path.write_bytes(path.read_bytes().replace(b'string="FINISHED"', b'string="STARTED"'))
    result = manager.collect(manifest['probe_id'])
    assert result['source_stale'] is True and result['evidence_status'] == 'stale_source'
    assert result['execution']['state'] == 'complete'


def test_short_manifest_lock_contention_is_retried_without_failing_probe(prepared):
    from sc2_mcp.storage import file_lock
    manager, manifest, _ = prepared
    acquired, release = threading.Event(), threading.Event()
    def competing_writer():
        with file_lock(manager.folder(manifest['probe_id']) / 'manifest.lock'):
            acquired.set()
            release.wait(5)
    thread = threading.Thread(target=competing_writer)
    thread.start()
    assert acquired.wait(5)
    timer = threading.Timer(.05, release.set)
    timer.start()
    try:
        manifest['test_contention'] = 'saved'
        manager.save(manifest)
    finally:
        release.set()
        thread.join(5)
        timer.join(5)
    assert manager.read(manifest['probe_id'])['test_contention'] == 'saved'


def test_cancelled_manifest_retains_observed_assertion_failure(prepared):
    manager, manifest, _ = prepared
    manifest.update(state='cancelled',execution='partial',verdict='partial')
    manager.save(manifest)
    result={'execution':{'state':'partial'},'verdict':'failed','sections':{},'phases':{}}
    manager.save(dict(manifest),result)
    assert manager.read(manifest['probe_id'])['state']=='cancelled'
    assert manager.read(manifest['probe_id'])['verdict']=='failed'
    assert result['verdict']=='failed' and result['termination_reason']=='cancelled'
