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
        assert not any(name.startswith('sc2_keystone_') for name in dispatcher.operations)
        assert 'sc2_script_replace' not in dispatcher.operations
        with pytest.raises(SC2Error, match='not exposed'):
            dispatcher.call('sc2_script_replace', {})
    finally:
        dispatcher.close()
