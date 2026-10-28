from pathlib import Path
import pytest
from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.storage import digest,snapshot


@pytest.fixture
def environment(tmp_path,monkeypatch):
    source=tmp_path/'sources';source.mkdir()
    root=source/'map.SC2Map';root.mkdir()
    dep=source/'Mods/A.SC2Mod';dep.mkdir(parents=True)
    (root/'DocumentInfo').write_bytes(b'<DocInfo><Dependencies><Value>file:Mods/A.SC2Mod</Value></Dependencies></DocInfo>')
    (dep/'DocumentInfo').write_bytes(b'<DocInfo/>')
    folder=dep/'Base.SC2Data/GameData';folder.mkdir(parents=True)
    (folder/'UnitData.xml').write_bytes(b'<Catalog><CUnit id="A"><LifeMax value="45"/></CUnit></Catalog>')
    (root/'MapScript.galaxy').write_bytes(b'void InitMap () {}\n')
    service=Service(tmp_path/'state');monkeypatch.setattr(service,'editor_conflict',lambda:None)
    project=service.projects.open(str(root),True,search_roots=[str(source)])
    yield service,project['project_id'],root,dep
    service.jobs.shutdown()


def test_domain_candidate_revalidates_dependency_before_commit(environment):
    service,key,root,dep=environment
    from sc2_mcp.catalog_patch import plan_catalog_patch
    original=snapshot(root)
    prepared=service.prepare_domain(key,'catalog_patch',lambda r,roots,context:plan_catalog_patch(r,roots,[
        {'operation':'set','catalog':'Unit','object_id':'A','field_path':'LifeMax','value':'60','expected':'45'}]))
    assert snapshot(root)==original
    path=dep/'Base.SC2Data/GameData/UnitData.xml'
    path.write_bytes(path.read_bytes().replace(b'45',b'46'))
    with pytest.raises(SC2Error) as exc:service.apply_candidate(key,prepared['change_id'])
    assert exc.value.code=='source_context_stale'
    assert snapshot(root)==original


def test_import_candidate_commits_and_uses_original_transaction(environment,tmp_path):
    service,key,root,_=environment
    candidate=tmp_path/'candidate.galaxy';candidate.write_bytes(b'void InitMap () { int value = 1; }\n')
    before=(root/'MapScript.galaxy').read_bytes()
    result=service.prepare_changes(key,[{'path':'MapScript.galaxy','baseline_sha256':digest(before),
        'candidate_file':str(candidate),'candidate_sha256':digest(candidate.read_bytes())}])
    assert result['state']=='prepared' and (root/'MapScript.galaxy').read_bytes()==before
    commit=service.apply_candidate(key,result['change_id'])
    assert commit['state']=='committed'
    service.transactions.rollback(commit['change_id'],root)
    assert (root/'MapScript.galaxy').read_bytes()==before


@pytest.mark.parametrize('relative',['DocumentInfo','BankList.xml','t3HeightMap'])
def test_import_protected_domains_cannot_bypass(environment,tmp_path,relative):
    service,key,root,_=environment
    candidate=tmp_path/'candidate';candidate.write_bytes(b'<DocInfo/>')
    before=snapshot(root)
    with pytest.raises(SC2Error) as exc:
        service.prepare_changes(key,[{'path':relative,'baseline_sha256':digest((root/relative).read_bytes()) if (root/relative).exists() else None,
            'candidate_file':str(candidate),'candidate_sha256':digest(candidate.read_bytes())}])
    assert exc.value.code in {'protected_patch','terrain_operation_required'}
    assert snapshot(root)==before


def test_public_explanation_rejects_fabricated_runtime_evidence(environment):
    service,key,_,_=environment
    with pytest.raises(SC2Error) as exc:
        service.explain_catalog(key,'Unit','A',['LifeMax'],observations={'fields':{'LifeMax':{'value':'45','evidence_id':'pretend'}}})
    assert exc.value.code=='runtime_evidence_required'

def test_source_selection_updates_locale_without_forgetting_installation(environment,monkeypatch):
    service,key,_,_=environment
    calls=[]
    def prepare(record,dependency_values=None,options=None):
        calls.append(options)
        return {'source_context_id':'a'*64,'complete':False}
    monkeypatch.setattr(service,'_prepare_context',prepare)
    service.prepare_dependencies(key,'D:/StarCraft II','zhCN','s2_cn','cn')
    service.prepare_dependencies(key,locale='enUS')
    assert calls[-1]=={'installation':'D:/StarCraft II','locale':'enUS','product':'s2_cn','branch':'cn'}
    service.prepare_dependencies(key,product='s2',branch='kr')
    assert calls[-1]=={'installation':'D:/StarCraft II','locale':'enUS','product':'s2','branch':'kr'}
    service.prepare_dependencies(key)
    assert calls[-1] is None


def test_experimental_terrain_commit_requires_flag_and_independent_target(environment,monkeypatch):
    import sc2_mcp.service as module
    service,key,root,_=environment
    prepared=service.transactions.run(root,lambda:{'MapScript.galaxy':b'void InitMap () { int x = 1; }\n'},label='terrain_flatten_protected',preview_only=True)
    before=snapshot(root)
    with pytest.raises(SC2Error) as error:service.apply_candidate(key,prepared['change_id'])
    assert error.value.code=='terrain_not_accepted'
    monkeypatch.setattr(module,'KEYSTONE',root)
    with pytest.raises(SC2Error) as error:service.apply_candidate(key,prepared['change_id'],True)
    assert error.value.code=='terrain_not_accepted'
    assert snapshot(root)==before


def test_keystone_planner_routes_through_bound_candidate_and_rollback(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('keystone_service_fixture',Path(__file__).with_name('test_keystone.py'))
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    root=fixture.fixture(tmp_path/'map.SC2Map')
    (root/'DocumentInfo').write_bytes(b'<DocInfo/>')
    service=Service(tmp_path/'state');monkeypatch.setattr(service,'editor_conflict',lambda:None)
    try:
        project=service.projects.open(str(root),True)
        before=snapshot(root)
        card=service.keystone_inspect(project['project_id'],'card',{'card_id':1})
        prepared=service.prepare_keystone(project['project_id'],'card_cost',{'card_id':1,'mineral':6,'gas':3})
        assert prepared['state']=='prepared' and snapshot(root)==before
        assert service.transactions.read(prepared['change_id'])['source_context_id']==prepared['source_context_id']
        applied=service.apply_candidate(project['project_id'],prepared['change_id'])
        assert service.keystone_inspect(project['project_id'],'card',{'card_id':1})['mineral']==6
        service.transactions.rollback(applied['change_id'],root)
        assert snapshot(root)==before
    finally:service.jobs.shutdown()
