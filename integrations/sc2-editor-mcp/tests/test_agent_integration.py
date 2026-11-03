"""Integration-specific invariants, independent of upstream project assumptions."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import pytest

from sc2_mcp.dispatch import Dispatcher
from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.storage import digest, snapshot
from sc2_mcp.transactions import Transactions


def component(tmp_path):
    root = tmp_path / 'test.SC2Map'
    root.mkdir()
    (root / 'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>')
    (root / 'MapScript.galaxy').write_text('void InitMap() {}\n')
    path = root / 'Base.SC2Data/GameData/UnitData.xml'
    path.parent.mkdir(parents=True)
    path.write_text('<Catalog><CUnit id="TestUnit"><LifeMax value="100"/></CUnit></Catalog>')
    return root


def test_cli_imports_without_mcp_sdk(tmp_path):
    code = '''import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'mcp' or name.startswith('mcp.'):
        raise AssertionError('CLI tried to load the MCP SDK')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from sc2_mcp.local_cli import main
raise SystemExit(main(['--state', STATE, 'capabilities']))
'''.replace('STATE', repr(str(tmp_path / 'state')))
    proc = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], capture_output=True, text=True, encoding='utf-8')
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)['ok'] is True


def test_cli_mcp_same_results_and_invalid_request(tmp_path):
    from sc2_mcp.server import create_server
    state = tmp_path / 'state'
    server = create_server(state)
    async def check():
        result = await server.call_tool('sc2_capabilities', {})
        # FastMCP returns content blocks and structured content for dict results.
        blocks = result[0] if isinstance(result, tuple) else result
        mcp_result = json.loads(next(block.text for block in blocks if hasattr(block, 'text')))
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'sc2_mcp.local_cli',
            '--state', str(state), 'capabilities'], capture_output=True, text=True, encoding='utf-8')
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == mcp_result
        with pytest.raises(Exception, match='project_missing'):
            await server.call_tool('sc2_project_open', {'path': 'x', 'writable': 'false'})
    try:
        asyncio.run(check())
    finally:
        server.sc2_dispatcher.close()


@pytest.mark.parametrize('name', ['MapScript.galaxy', 'Lib1234.galaxy', 'TriggerLibs/Lib1234_h.galaxy', 'publish/a.xml'])
def test_transaction_rejects_generated_and_publish_even_candidates(tmp_path, name):
    root = component(tmp_path)
    before = snapshot(root)
    transactions = Transactions(tmp_path / 'state')
    with pytest.raises(SC2Error) as caught:
        transactions.run(root, lambda: {name: b'changed'}, preview_only=True)
    assert caught.value.code == 'source_boundary'
    assert snapshot(root) == before


def test_batch_cannot_bypass_generated_source_boundary(tmp_path, monkeypatch):
    root = component(tmp_path)
    service = Service(tmp_path / 'state')
    monkeypatch.setattr(service, 'editor_conflict', lambda: None)
    key = service.projects.open(str(root), True)['project_id']
    before = snapshot(root)
    try:
        with pytest.raises(SC2Error, match='Generated Galaxy'):
            service.edit(key, 'batch', {'edits': [{'operation': 'script_replace', 'parameters': {
                'old': 'void InitMap() {}', 'new': 'void InitMap() { int a; }',
                'expected_sha256': digest((root / 'MapScript.galaxy').read_bytes())}}]})
        assert snapshot(root) == before
    finally:
        service.jobs.shutdown()


def test_preexisting_generated_candidate_cannot_apply(tmp_path, monkeypatch):
    root = component(tmp_path)
    service = Service(tmp_path / 'state')
    monkeypatch.setattr(service, 'editor_conflict', lambda: None)
    key = service.projects.open(str(root), True)['project_id']
    import sc2_mcp.transactions as module
    with monkeypatch.context() as context:
        context.setattr(module, 'guard_source_changes', lambda *args: None)
        prepared = service.transactions.run(root, lambda: {'MapScript.galaxy': b'void InitMap() { int a; }\n'}, preview_only=True)
    before = snapshot(root)
    try:
        with pytest.raises(SC2Error, match='Generated Galaxy'):
            service.apply_candidate(key, prepared['change_id'])
        assert snapshot(root) == before
    finally:
        service.jobs.shutdown()


def test_project_runtime_routes_across_clients_and_refuses_stale_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv('SC2_AGENT_RUNTIME_ROOT', str(tmp_path / 'runtime'))
    root = component(tmp_path)
    first = Dispatcher(tmp_path / 'index', project_states=True)
    second = Dispatcher(tmp_path / 'index', project_states=True)
    monkeypatch.setattr(Service, 'editor_conflict', lambda self: None)
    try:
        key = first.call('sc2_project_open', {'path': str(root), 'writable': True})['result']['project_id']
        result = first.call('sc2_catalog_set', {'project_id': key, 'catalog_type': 'Unit',
            'object_id': 'TestUnit', 'field_path': 'LifeMax', 'value': '120', 'expected': '100', 'preview_only': True})
        change_id = result['result']['change_id']
        assert second.call('sc2_project_list')['result']['projects'][0]['project_id'] == key
        inspected = second.call('sc2_changes_inspect', {'project_id': key, 'change_id': change_id})
        assert inspected['result']['state'] == 'prepared'
        assert Path(inspected['result']['candidate']).is_relative_to(tmp_path / 'runtime/projects')
        (root / 'manual.txt').write_text('new user change')
        with pytest.raises(SC2Error, match='候选生成后'):
            second.call('sc2_changes_apply', {'project_id': key, 'change_id': change_id})
        assert (root / 'manual.txt').read_text() == 'new user change'
    finally:
        first.close()
        second.close()


def test_project_specific_and_generated_edit_operations_not_exposed(tmp_path):
    dispatcher = Dispatcher(tmp_path / 'state')
    try:
        assert 'sc2_script_replace' not in dispatcher.operations
        with pytest.raises(SC2Error, match='not exposed'):
            dispatcher.call('sc2_script_replace', {})
    finally:
        dispatcher.close()

def test_routing_inventory_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_AGENT_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = Dispatcher(tmp_path / "index", project_states=True)
    try:
        manifest = Path(__file__).resolve().parents[2] / "CAPABILITIES.json"
        rows = json.loads(manifest.read_text("utf-8"))["operations"]
        assert set(client.operations) == {r["operation"] for r in rows if r["ownership"] != "excluded_project_or_generated_source"}
        ids = []
        for name in ("A", "B"):
            parent = tmp_path / name
            parent.mkdir()
            ids.append(client.call("sc2_project_open", {"path": str(component(parent))})["result"]["project_id"])
        for _ in range(2):
            assert {p["project_id"] for p in client.call("sc2_project_list")["result"]["projects"]} == set(ids)
        client.close()
        client = Dispatcher(tmp_path / "index", project_states=True)
        for key in ids:
            assert client.call("sc2_project_read_text", {"project_id":key, "path":"DocumentInfo"})["ok"]
    finally:
        client.close()


def test_report_pages_reconstruct_original(tmp_path):
    client = Dispatcher(tmp_path / "state")
    try:
        root = component(tmp_path)
        (root / "large.txt").write_text(('abcd中文"\\' * 15000), encoding="utf-8")
        key = client.call("sc2_project_open", {"path":str(root)})["result"]["project_id"]
        report = client.call("sc2_project_read_text", {"project_id":key,"path":"large.txt","limit":100000})["result"]
        offset, parts = 0, []
        while offset is not None:
            page = client.call("sc2_report_read", {"name":report["report_name"], "offset":offset,"limit":100000})["result"]
            assert len(json.dumps(page, ensure_ascii=False)) <= 48000
            parts.append(page["text"])
            offset = page["next_offset"]
        assert "".join(parts) == Path(report["report_file"]).read_text("utf-8")
    finally:
        client.close()


def test_effect_candidate_with_missing_then_restored_dependency(tmp_path, monkeypatch):
    root = component(tmp_path)
    (root / "DocumentInfo").write_text("<DocInfo><Dependencies><Value>file:Mods/External.SC2Mod</Value></Dependencies></DocInfo>")
    mods = tmp_path / "Mods"
    mods.mkdir()
    data = root / "Base.SC2Data/GameData"
    (data / "EffectData.xml").write_text('<Catalog><CEffectApplyBehavior id="Buff"><Behavior value="Old"/></CEffectApplyBehavior></Catalog>')
    (data / "BehaviorData.xml").write_text('<Catalog><CBehaviorBuff id="Old"/></Catalog>')
    service = Service(tmp_path / "state")
    monkeypatch.setattr(service, "editor_conflict", lambda: None)
    try:
        key = service.projects.open(str(root), True, search_roots=[mods])["project_id"]
        def preview():
            return service.edit(key, "catalog_set", {"catalog":"Effect","object_id":"Buff","field_path":"Behavior","expected":"Old","value":"ExternalBuff"}, preview_only=True)
        with pytest.raises(SC2Error) as partial:
            preview()
        assert partial.value.code == "reference_dependencies_incomplete"
        report = partial.value.details["report"]
        assert report["source_coverage"]["after"]["missing"] and report["static"] == "partial"
        assert any(row.get("field") == "Behavior" and row["reference"]["raw_value"] == "ExternalBuff" for row in report["unresolved"])
        dep = mods / "External.SC2Mod"
        folder = dep / "Base.SC2Data/GameData"
        folder.mkdir(parents=True)
        (dep / "DocumentInfo").write_text("<DocInfo/>")
        target = folder / "BehaviorData.xml"
        target.write_text('<Catalog><CBehaviorBuff id="ExternalBuff"/></Catalog>')
        assert preview()["state"] == "prepared"
        target.write_text('<Catalog/>')
        with pytest.raises(SC2Error) as broken:
            preview()
        assert broken.value.code == "new_missing_references"
    finally:
        service.jobs.shutdown()

def test_template_routes_and_evidence_across_restarts(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_AGENT_RUNTIME_ROOT", str(tmp_path / "runtime"))
    client = Dispatcher(tmp_path / "index", project_states=True)
    try:
        def call(op, **args):
            return client.call(op, args)["result"]
        def register(name):
            root = tmp_path / (name + ".SC2Mod")
            root.mkdir()
            for path, raw in [("DocumentInfo","<DocInfo/>"),("ComponentList.SC2Components","<Components/>"),("DocumentHeader",name)]:
                (root / path).write_text(raw)
            key = call("sc2_project_open", path=str(root))["project_id"]
            proof = tmp_path / (name + ".txt")
            proof.write_text("Synthetic routing fixture")
            eid = call("sc2_validate_record",project_id=key,level="editor",status="passed",evidence_path=str(proof),notes="fixture")["id"]
            call("sc2_project_register_template",project_id=key,name="Sample",evidence_id=eid)
            return key, root, proof
        key, root, proof = register("First")
        client.close()
        client = Dispatcher(tmp_path / "index", project_states=True)
        target = tmp_path / "Copy.SC2Mod"
        created = call("sc2_project_create",template="Sample",destination=str(target))
        assert call("sc2_project_open",path=str(target))["project_id"] == created["project_id"]
        with pytest.raises(SC2Error,match="副本"):
            call("sc2_project_create",template="Sample",destination=str(target))
        register("Second")
        fresh = tmp_path / "Another.SC2Mod"
        args = dict(template="Sample",destination=str(fresh))
        with pytest.raises(SC2Error) as ambiguous:
            call("sc2_project_create",**args)
        assert len(ambiguous.value.details["candidates"]) == 2 and not fresh.exists()
        args["template_project_id"] = key
        call("sc2_project_create",**args)
        args["destination"] = str(tmp_path / "Unused.SC2Mod")
        proof.write_text("changed")
        with pytest.raises(SC2Error) as stale:
            call("sc2_project_create",**args)
        assert stale.value.code == "evidence_changed"
        (root / "DocumentHeader").write_text("updated")
        with pytest.raises(SC2Error) as stale:
            call("sc2_project_create",**args)
        assert stale.value.code == "template_changed"
        assert not Path(args["destination"]).exists()
    finally:
        client.close()
