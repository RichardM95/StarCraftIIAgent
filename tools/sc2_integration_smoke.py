"""Real stdio and optional DeepSeek smoke test on a fresh disposable Components fixture."""
from __future__ import annotations
import argparse
import asyncio
from contextlib import AsyncExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from sc2_integration_runtime import WORKSPACE, runtime_command


def fingerprint(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


async def run(with_deepseek):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    base = WORKSPACE / 'temp/integration-smoke' / uuid.uuid4().hex
    source = base / 'fixture.SC2Map'
    data = source / 'Base.SC2Data/GameData'
    data.mkdir(parents=True)
    (source / 'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>', encoding='utf-8')
    (source / 'MapScript.galaxy').write_text('void InitMap() {}\n', encoding='utf-8')
    (data / 'UnitData.xml').write_text('<Catalog><CUnit id="IntegrationProbe"><LifeMax value="100"/></CUnit></Catalog>', encoding='utf-8')
    (source / 'notes.txt').write_text('pending\n', encoding='utf-8')
    (source / 'AGENTS.md').write_text('This is an isolated SC2 integration fixture. Inspect supplied components only. Generated Galaxy and original components are read-only. Only notes.txt and the SC2 bridge request may change.\n', encoding='utf-8')
    baseline = fingerprint(source)
    sc2_python = WORKSPACE / 'integrations/sc2-editor-mcp/.venv/Scripts/python.exe'
    ds_python = WORKSPACE / 'integrations/deepseek-supervisor/.venv/Scripts/python.exe'
    env = {**os.environ, 'SC2_AGENT_RUNTIME_ROOT': str(base / 'runtime'),
           'SC2_AGENT_WORKSPACE': str(WORKSPACE), 'SC2_EDITOR_MCP_PYTHON': str(sc2_python),
           'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    report = {'fixture': str(source), 'runtime': str(base / 'runtime'),
              'numpy': __import__('numpy').__version__, 'editor': 'not_run', 'packaged_runtime': 'not_run'}

    async def call(session, name, arguments):
        result = await session.call_tool(name, arguments)
        if result.isError:
            raise ValueError(name + ': ' + '\n'.join(c.text for c in result.content if hasattr(c, 'text')))
        structured = getattr(result, 'structuredContent', None)
        return structured if structured is not None else json.loads(next(c.text for c in result.content if hasattr(c, 'text')))

    def cli(command):
        result = subprocess.run(runtime_command('deepseek-supervisor', 'supervisor.cli',
                                 ['--ui-language', 'zh-CN', *command]), env=env, cwd=WORKSPACE,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode:
            raise ValueError('CLI ' + command[0] + ': ' + (result.stdout + result.stderr)[-2000:])
        return json.loads(result.stdout.strip().splitlines()[-1])['result']

    try:
        async with AsyncExitStack() as stack:
            launch = runtime_command('sc2-editor-mcp', 'sc2_mcp', ['--project-states'])
            streams = await stack.enter_async_context(stdio_client(StdioServerParameters(
                command=launch[0], args=launch[1:], env=env)))
            sc2 = await stack.enter_async_context(ClientSession(*streams))
            await sc2.initialize()
            tools = await sc2.list_tools()
            report['sc2_mcp_tools'] = len(tools.tools)
            opened = await call(sc2, 'sc2_project_open', {'path': str(source), 'writable': False})
            key = opened['result']['project_id']
            inspected = await call(sc2, 'sc2_catalog_inspect', {'project_id': key, 'catalog_type': 'Unit', 'object_id': 'IntegrationProbe'})
            report['catalog_inspect'] = inspected['ok']
            report['source_unchanged_after_sc2_reads'] = fingerprint(source) == baseline
            if not with_deepseek:
                return report
            launch = runtime_command('deepseek-supervisor', 'supervisor.cli', ['serve'])
            streams = await stack.enter_async_context(stdio_client(StdioServerParameters(
                command=launch[0], args=launch[1:], env=env)))
            ds = await stack.enter_async_context(ClientSession(*streams))
            await ds.initialize()
            report['deepseek_mcp_tools'] = len((await ds.list_tools()).tools)
            request = {'protocol': 'sc2-worker-bridge/1', 'id': 'probe-unit', 'operation': 'catalog_inspect',
                       'arguments': {'catalog': 'Unit', 'object_id': 'IntegrationProbe'}}
            packet = {'goal': 'Use the SC2 file bridge to inspect IntegrationProbe. First write .sc2-mcp/request.json with this exact JSON: '
                + json.dumps(request) + '. Read .sc2-mcp/response.json after the host responds. Once it reports the unit LifeMax value 100, replace notes.txt with exactly IntegrationProbe LifeMax=100 followed by one newline. Do not change the original component files. Finish with a short factual statement.',
                'request_id': 'integration-smoke-' + base.name, 'workspace': str(source),
                'input_files': ['DocumentInfo', 'Base.SC2Data/GameData/UnitData.xml', 'notes.txt', 'AGENTS.md'],
                'allowed_files': ['notes.txt', '.sc2-mcp/request.json'], 'profile': 'sc2',
                'constraints': ['No shell, no external files, no generated Galaxy edits. Only use the supplied fixture and bridge.'],
                'acceptance': 'Host independently checks bridge ok=true, exact notes.txt bytes, source component hashes and the real candidate diff.',
                'timeout_seconds': 180, 'max_tool_calls': 30}
            (base / 'task.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding='utf-8')
            record = await call(ds, 'submit_task', {'task': packet})
            task_id = record['task_id']
            report['task_id'] = task_id
            print(json.dumps({'stage': 'task_submitted', 'task_id': task_id}), flush=True)
            duplicate = await call(ds, 'submit_task', {'task': packet})
            report['same_request_same_task'] = duplicate['task_id'] == task_id
            report['cli_sees_mcp_task'] = (await asyncio.to_thread(cli, ['status', task_id]))['task_id'] == task_id
            deadline = time.monotonic() + 210
            while True:
                status = await call(ds, 'task_status', {'task_id': task_id})
                if status['state'] not in ('queued', 'running'):
                    break
                if time.monotonic() > deadline:
                    await call(ds, 'cancel_task', {'task_id': task_id})
                    raise ValueError('Smoke task exceeded its host deadline; cancellation requested')
                await asyncio.sleep(1)
            result = await call(ds, 'task_result', {'task_id': task_id})
            report['task_state'] = status['state']
            report['task_error'] = status.get('error')
            report['bridge_events'] = result.get('sc2_bridge', {}).get('events', [])
            report['changes'] = result['changes']
            report['source_unchanged_before_integration'] = fingerprint(source) == baseline
            (base / 'task-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            if status['state'] != 'worker_completed':
                raise ValueError('DeepSeek task did not complete: ' + json.dumps(status.get('error', status['state']), ensure_ascii=False))
            expected = b'IntegrationProbe LifeMax=100\n'
            candidate = Path(result['candidate_directory'])
            if (candidate / 'notes.txt').read_bytes() != expected:
                raise ValueError('Actual candidate notes differ from acceptance bytes')
            if [change['file'] for change in result['changes']] != ['notes.txt']:
                raise ValueError('Unexpected candidate changes')
            if not report['source_unchanged_before_integration'] or not all(c['allowed'] and c['source_unchanged'] for c in result['changes']):
                raise ValueError('Source or scope conflict')
            if not any(e.get('ok') for e in report['bridge_events']):
                raise ValueError('No successful host-side SC2 bridge event')
            integrated = await asyncio.to_thread(cli, ['integrate', task_id, '--review-note',
                'Independent host checked exact candidate bytes, sole allowed diff, unchanged source hashes and a successful SC2 bridge response.'])
            report['cli_integration_state'] = integrated['state']
            report['integrated_notes_match'] = (source / 'notes.txt').read_bytes() == expected
            after = fingerprint(source)
            report['game_components_unchanged'] = all(after[k] == v for k, v in baseline.items() if k != 'notes.txt')
            report['passed'] = all(report[k] for k in ('same_request_same_task', 'cli_sees_mcp_task',
                'integrated_notes_match', 'game_components_unchanged'))
            return report
    finally:
        (base / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'report': str(base / 'report.json'), 'passed': report.get('passed', False)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-deepseek', action='store_true')
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.with_deepseek))
        return 0 if report.get('passed', report.get('source_unchanged_after_sc2_reads')) else 1
    except Exception as exc:
        def leaves(error):
            if isinstance(error, BaseExceptionGroup):
                return [message for child in error.exceptions for message in leaves(child)]
            return [str(error)]
        print(json.dumps({'ok': False, 'error': {'code': 'smoke_failed',
            'messages': leaves(exc)}}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
