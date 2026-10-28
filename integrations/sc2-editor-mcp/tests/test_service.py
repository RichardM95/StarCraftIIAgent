import asyncio
import json
from pathlib import Path

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot
from sc2_mcp.validation import lexical_balance, validate_changes
from sc2_mcp.localization import inspect_localization, plan_localization_set


@pytest.fixture
def opened(tmp_path,monkeypatch):
    root=tmp_path/'test.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo><Dependencies/></DocInfo>')
    (root/'MapScript.galaxy').write_bytes(b'void Init () {\r\n    int a = 1;\r\n}\r\n')
    text=root/'zhCN.SC2Data/LocalizedData/GameStrings.txt';text.parent.mkdir(parents=True)
    text.write_bytes(b'A=1\r\n')
    service=Service(tmp_path/'state')
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    project=service.projects.open(str(root),True)
    yield service,project['project_id'],root
    service.jobs.shutdown()


def test_edit_backups_and_rollback(opened):
    service,key,root=opened
    before=snapshot(root)
    result=service.edit(key,'localization_set',{'updates':{'A':'2'}})
    assert result['state']=='committed'
    assert (Path(result['backup'])/'zhCN.SC2Data/LocalizedData/GameStrings.txt').read_bytes()==b'A=1\r\n'
    service.transactions.rollback(result['change_id'],root)
    assert snapshot(root)==before


def test_live_editor_defers_and_candidate_detects_unrelated_changes(opened,monkeypatch):
    service,key,root=opened
    monkeypatch.setattr(service,'editor_conflict',lambda:{'code':'editor_unsaved_state_unknown'})
    result=service.edit(key,'localization_set',{'updates':{'A':'2'}})
    assert result['state']=='prepared'
    assert (root/'zhCN.SC2Data/LocalizedData/GameStrings.txt').read_bytes()==b'A=1\r\n'
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    (root/'manual.txt').write_bytes(b'edited after the candidate')
    with pytest.raises(SC2Error,match='候选生成后'):
        service.apply_candidate(key,result['change_id'])


def test_candidate_commits_when_baseline_unchanged(opened):
    service,key,root=opened
    result=service.edit(key,'localization_set',{'updates':{'A':'2'}},True)
    applied=service.apply_candidate(key,result['change_id'])
    assert applied['state']=='committed'


def test_batch_failure_is_atomic(opened):
    service,key,root=opened
    before=snapshot(root)
    with pytest.raises(SC2Error):
        service.edit(key,'batch',{'edits':[
            {'operation':'localization_set','parameters':{'updates':{'A':'2'}}},
            {'operation':'object_remove','parameters':{'object_id':'123'}},
        ]})
    assert snapshot(root)==before


def test_mixed_batch_and_source_immutability(opened):
    service,key,root=opened
    from sc2_mcp.storage import digest
    baseline=(root/'MapScript.galaxy').read_bytes()
    before=snapshot(root)
    with pytest.raises(SC2Error,match='Generated Galaxy'):
        service.edit(key,'batch',{'edits':[
            {'operation':'localization_set','parameters':{'updates':{'A':'2'}}},
            {'operation':'script_replace','parameters':{'old':'int a = 1;','new':'int a = 2;','expected_sha256':digest(baseline)}},
        ]})
    assert snapshot(root)==before


@pytest.mark.parametrize('data',[b'void f() { /* broken',b'void f() { string a="broken; }',b'void f() { int a[)]; }'])
def test_lexical_structure_rejects_malformed(data):
    with pytest.raises(SC2Error): lexical_balance(data)


def test_localization_never_edits_other_locale(opened):
    _,_,root=opened
    with pytest.raises(SC2Error): plan_localization_set(root,{'A':'other'},'enUS')
    assert inspect_localization(root)['card_pairs']=={'paired':[],'missing':[]}


def test_keystone_stable_identity_and_new_card_limit(tmp_path):
    script=(
        'const int lib1_gv_mAX_CARD_ID = 1;\n'
        'void lib1_Cards () {\n int lv_id;\n lv_id = 1;\n'
        ' lib1_gf_DefineCard(lv_id, SET, RACE, "Marine Squad", Name);\n}\n')
    (tmp_path/'MapScript.galaxy').write_bytes(script.encode('utf-8'))
    with pytest.raises(SC2Error) as error:
        validate_changes(tmp_path,{'MapScript.galaxy':script.replace('Marine Squad','Renamed').encode()},'keystone')
    assert error.value.code=='keystone_card_identity'
    with pytest.raises(SC2Error) as error:
        validate_changes(tmp_path,{'MapScript.galaxy':script.replace('= 1;','= 0;',1).encode()},'keystone')
    assert error.value.code=='keystone_card_limit'


def test_mcp_schemas_and_structured_results(tmp_path):
    from sc2_mcp.server import create_server
    server=create_server(tmp_path/'server-state')
    async def check():
        tools=await server.list_tools()
        index={t.name:t for t in tools}
        assert {'sc2_terrain_edit','sc2_changes_rollback','sc2_dependencies_set','sc2_job_cancel'}<=index.keys()
        assert 'sc2_validate_region_diagnose' in index
        assert index['sc2_validate_region_diagnose'].annotations.readOnlyHint is True
        assert all(name.startswith('sc2_') for name in index)
        assert index['sc2_terrain_edit'].inputSchema['properties']['operations']['type']=='array'
        result=await server.call_tool('sc2_capabilities',{})
        assert 'experimental' in str(result)
    try: asyncio.run(check())
    finally: server.sc2_service.jobs.shutdown()


@pytest.mark.asyncio
async def test_real_stdio_handshake(tmp_path):
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=sys.executable,args=['-m','sc2_mcp','--state',str(tmp_path/'stdio')])
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            initialized=await session.initialize()
            assert initialized.serverInfo.name=='sc2-editor'
            from sc2_mcp import __version__
            assert initialized.serverInfo.version==__version__
            listed=await session.list_tools()
            assert any(t.name=='sc2_capabilities' for t in listed.tools)
            result=await session.call_tool('sc2_capabilities',{})
            assert not result.isError
            assert 'candidate_only' in str(result)
            bad=await session.call_tool('sc2_project_inspect',{'project_id':'not-open'})
            assert bad.isError


def test_catalog_dangling_reference_rejected_before_commit(opened):
    service,key,root=opened
    data=root/'Base.SC2Data/GameData'
    data.mkdir(parents=True)
    unit=data/'UnitData.xml'
    unit.write_bytes(b'<Catalog><CUnit id="Marine"><WeaponArray index="0" Link="Gun"/></CUnit></Catalog>')
    (data/'WeaponData.xml').write_bytes(b'<Catalog><CWeapon id="Gun"/></Catalog>')
    baseline=snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.edit(key,'catalog_set',{'catalog':'Unit','object_id':'Marine',
                     'field_path':'WeaponArray[0].Link','value':'MissingGun','expected':'Gun'})
    assert error.value.code=='new_missing_references'
    assert snapshot(root)==baseline
