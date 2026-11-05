import asyncio
import json
from pathlib import Path
import threading

import pytest

from sc2_mcp import reference_receipts as receipts
from sc2_mcp.jobs import Jobs
from sc2_mcp.errors import SC2Error


def test_receipt_reuses_only_identical_inputs_and_checks_integrity(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts, 'implementation', lambda: 'v1')
    calls = []
    def compute():
        calls.append(1)
        return dict(static='passed', new_missing=[], unresolved=[{'code':'kept'}])
    args = (tmp_path, dict(root='project', profile='general'), {'a.xml':b'one'},
            {'source_context_id':'before'}, {'source_context_id':'after'}, compute)
    first = receipts.reference_validation(*args)
    second = receipts.reference_validation(*args)
    assert not first['reuse']['hit'] and second['reuse']['hit'] and len(calls)==1
    assert second['unresolved']==first['unresolved']
    path=Path(first['reuse']['receipt'])
    data=json.loads(path.read_text('utf-8'));data['report']['unresolved']=[]
    path.write_text(json.dumps(data),encoding='utf-8')
    assert not receipts.reference_validation(*args)['reuse']['hit']
    monkeypatch.setattr(receipts, 'implementation', lambda: 'v2')
    assert not receipts.reference_validation(*args)['reuse']['hit']
    assert len(calls)==3


def test_job_request_deduplicates_across_managers(tmp_path):
    a,b=Jobs(tmp_path),Jobs(tmp_path)
    gate=threading.Event()
    try:
        first=a.submit_once('prepare','request',{'a':1},lambda token:gate.wait(2))
        second=b.submit_once('prepare','request',{'a':1},lambda token:pytest.fail('duplicate'))
        assert first['job_id']==second['job_id']
        with pytest.raises(SC2Error,match='request_id'):
            b.submit_once('prepare','request',{'a':2},lambda token:None)
    finally:
        gate.set();a.shutdown();b.shutdown()


def test_reference_only_inspection_keeps_warning_dicts_isolated(tmp_path):
    from sc2_mcp.catalog import _Library
    folder=tmp_path/'Base.SC2Data/GameData';folder.mkdir(parents=True)
    (folder/'UnitData.xml').write_text('<Catalog><CUnit id="A"/></Catalog>')
    library=_Library([tmp_path]);library.warnings.append({'code':'original'})
    view=library.inspect('Unit','A',reference_only=True)
    view['warnings'][0]['code']='changed'
    assert library.warnings[-1]['code']=='original'


def test_native_backend_failure_is_explicit_without_legacy_fallback(monkeypatch):
    from sc2_mcp import archives, storm_adapter
    monkeypatch.setattr(archives,'_native_enabled',lambda:True)
    def broken(): raise ValueError('DLL fingerprint mismatch')
    monkeypatch.setattr(storm_adapter,'capabilities',broken)
    caps=archives.backend_capabilities()
    assert not caps['can_export'] and 'fingerprint' in caps['reason']


def test_receipt_changed_candidate_and_source_cannot_hit(tmp_path,monkeypatch):
    monkeypatch.setattr(receipts,'implementation',lambda:'v1')
    calls=[]
    def compute(): calls.append(1);return {'static':'passed','new_missing':[]}
    for content,context in [(b'one','a'),(b'two','a'),(b'two','b')]:
        result=receipts.reference_validation(tmp_path,{'root':'r','profile':'g'},
            {'a.xml':content},{'source_context_id':context},{'source_context_id':context},compute)
        assert not result['reuse']['hit']
    assert len(calls)==3


def test_public_background_prepare_apply_reuses_references(tmp_path,monkeypatch):
    import time
    from sc2_mcp.dispatch import Dispatcher
    from sc2_mcp import catalog
    from sc2_mcp.storage import digest
    root=tmp_path/'mod.SC2Mod';root.mkdir()
    (root/'DocumentInfo').write_text('<DocInfo/>')
    folder=root/'Base.SC2Data/GameData';folder.mkdir(parents=True)
    path=folder/'UnitData.xml';path.write_bytes(b'<Catalog><CUnit id="A"><LifeMax value="1"/></CUnit></Catalog>')
    candidate=tmp_path/'candidate.xml';candidate.write_bytes(path.read_bytes().replace(b'value="1"',b'value="2"'))
    dispatcher=Dispatcher(tmp_path/'state')
    monkeypatch.setattr(dispatcher.service,'editor_conflict',lambda:None)
    monkeypatch.setattr(dispatcher.service,'_source_cache',lambda record:tmp_path/'cache')
    calls=[];original=catalog.reference_graph
    def counted(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(catalog,'reference_graph',counted)
    key=dispatcher.call('sc2_project_open',{'path':str(root),'writable':True})['result']['project_id']
    arguments={'project_id':key,'patches':[{'path':'Base.SC2Data/GameData/UnitData.xml',
        'baseline_sha256':digest(path.read_bytes()),'candidate_sha256':digest(candidate.read_bytes()),
        'candidate_file':str(candidate)}],'background':True,'request_id':'test-request'}
    def finish(job):
        deadline=time.monotonic()+20
        while job['state'] in {'queued','running','cancelling'}:
            assert time.monotonic()<deadline
            time.sleep(.02);job=dispatcher.service.jobs.status(job['job_id'])
        assert job['state']=='completed',job
        return job['result']
    try:
        job=dispatcher.call('sc2_changes_prepare',arguments)['result']
        assert dispatcher.call('sc2_changes_prepare',arguments)['result']['job_id']==job['job_id']
        prepared=finish(job);count=len(calls)
        assert count>0
        applied=finish(dispatcher.call('sc2_changes_apply',{'project_id':key,
            'change_id':prepared['change_id'],'background':True})['result'])
        assert applied['state']=='committed' and len(calls)==count
        assert applied['validation']['references']['reuse']['hit']
        assert path.read_bytes()==candidate.read_bytes()
    finally:dispatcher.close()
