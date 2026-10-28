import asyncio
import hashlib
import json

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.server import create_server
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot


def test_war3_source_tools_are_project_scoped_and_readonly(tmp_path):
    root=tmp_path/'map.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo/>')
    source=tmp_path/'source';source.mkdir()
    data=b'function main takes nothing returns nothing\nendfunction\n'
    (source/'war3map.j').write_bytes(data)
    service=Service(tmp_path/'state')
    try:
        key=service.projects.open(str(root),False)['project_id']
        before=snapshot(root)
        assert service.war3_inspect(key,str(source))['source']['sha256']==hashlib.sha256(data).hexdigest()
        assert service.war3_plan(key,str(source))['complete'] is False
        assert service.war3_coverage(key,str(source))['bound_count']==0
        assert snapshot(root)==before
        assert (source/'war3map.j').read_bytes()==data
        with pytest.raises(SC2Error):service.war3_inspect('missing-project',str(source))
    finally:service.jobs.shutdown()


def test_guarded_edit_uses_normal_transaction_backup_and_rollback(tmp_path,monkeypatch):
    root=tmp_path/'map.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo/>')
    source=b'void InitMap() { int counter = 0; if (counter < 4) { Counter(counter); } }\n'
    (root/'MapScript.galaxy').write_bytes(source)
    service=Service(tmp_path/'state')
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    try:
        key=service.projects.open(str(root),True)['project_id']
        before=snapshot(root)
        with pytest.raises(SC2Error):
            service.edit(key,'script_guarded_replace',{'old':'Counter(counter);','new':'','expected_sha256':hashlib.sha256(source).hexdigest()})
        assert snapshot(root)==before
        changed=service.edit(key,'script_guarded_replace',{'old':'counter < 4','new':'counter < 5','expected_sha256':hashlib.sha256(source).hexdigest(),
                              'review':{'author':'a','reviewer':'b','evidence':'independent-leaf-review'}})
        assert changed['state']=='committed'
        assert (root/'MapScript.galaxy').read_bytes()==source.replace(b'< 4',b'< 5')
        assert (tmp_path/'state').is_dir()
        service.transactions.rollback(changed['change_id'],root)
        assert snapshot(root)==before
    finally:service.jobs.shutdown()


def test_new_tools_are_discoverable_with_explicit_limits(tmp_path):
    server=create_server(tmp_path/'state')
    try:
        tools=asyncio.run(server.list_tools())
        by_name={tool.name:tool for tool in tools}
        assert {'sc2_war3_inspect','sc2_war3_plan','sc2_war3_coverage','sc2_script_guard','sc2_script_guarded_replace','sc2_script_build','sc2_script_build_inspect'}<=by_name.keys()
        assert by_name['sc2_war3_inspect'].annotations.readOnlyHint
        assert not by_name['sc2_script_guarded_replace'].annotations.readOnlyHint
    finally:server.sc2_service.jobs.shutdown()


def test_script_build_commits_both_components_and_rolls_back(tmp_path,monkeypatch):
    root=tmp_path/'map.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo/>')
    folder=root/'source';folder.mkdir()
    data=b'void Port_Init () { }\n'
    (folder/'all.galaxy').write_bytes(data)
    manifest={'schema':'sc2-script-build/1','files':[{'path':'source/all.galaxy','sha256':hashlib.sha256(data).hexdigest()}],
              'init_functions':['Port_Init']}
    raw=json.dumps(manifest).encode('utf8')
    (folder/'manifest.json').write_bytes(raw)
    service=Service(tmp_path/'state')
    monkeypatch.setattr(service,'editor_conflict',lambda:None)
    try:
        key=service.projects.open(str(root),True)['project_id']
        before=snapshot(root)
        parameters={'manifest_path':'source/manifest.json','expected_manifest_sha256':hashlib.sha256(raw).hexdigest()}
        preview=service.edit(key,'script_build',parameters,True)
        assert preview['state']=='prepared'
        assert snapshot(root)==before
        result=service.edit(key,'script_build',parameters)
        assert result['state']=='committed'
        assert {item['path'] for item in result['files']}=={'MapScript.galaxy','Triggers'}
        assert data in (root/'MapScript.galaxy').read_bytes()
        service.transactions.rollback(result['change_id'],root)
        assert snapshot(root)==before
        (folder/'all.galaxy').write_bytes(data+b'// later change\n')
        with pytest.raises(SC2Error) as error:
            service.edit(key,'script_build',parameters)
        assert error.value.code=='SCRIPT_BUILD_SOURCE_STALE'
        assert not (root/'MapScript.galaxy').exists()
    finally:service.jobs.shutdown()
