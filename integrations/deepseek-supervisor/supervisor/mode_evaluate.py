"""Compare installed Agent presets with their own native tool presentation."""
import argparse
import asyncio
import hashlib
import json
import random
import time
from pathlib import Path
from .runtime import ROOT, Harness
from .evaluate import fixture, evaluate_output, snapshot
from .heldout import fixture as heldout_fixture, oracle as heldout_oracle

MODES = ('standard', 'minimal', 'ptc', 'cordis')
CATEGORIES = ('code', 'structured', 'retrieval', 'diagnosis', 'memory', 'scope')
SHIPPED = 'D:/deepseek/resources/app.asar/dsh/node_modules/@deepseek-ai/dsh-web-app/presets'


def mode_patches(directory, workspace, mode):
    inspection = ROOT / 'state/mode-inspection'
    web = (inspection / 'dsh-web-app__cordis.patch.yml').read_text(encoding='utf-8')
    boundary = web[web.index('- id: tool-plugin-manager\n', web.index('# ──')):]
    # This is the host-to-preset move block at the end, not Web UI/HTTP startup.
    boundary = boundary.replace('default: standard', f'default: {mode}')
    boundary += '\n- id: workspace-dependencies\n  disabled: true\n- id: skill-office\n  disabled: true\n'
    boundary += "\n- insert:\n    - id: subagent-model-selection-settings\n      name: '@deepseek-ai/dsh-tool-subagent/model-selection-settings'\n"
    boundary += "\n- insert:\n    - id: cordis-inspect-providers\n      name: '@deepseek-ai/dsh-tool-cordis/host'\n"
    boundary += "\n- insert:\n    - id: cordis-host-runner\n      name: '@deepseek-ai/dsh-cordis-host-runner'\n"
    # The installed Windows ACL backend fails before executing tools on this
    # machine. Apply the same explicit test-only policy to every preset.
    boundary += '\n- id: sandbox-policy\n  config:\n    mode: danger-full-access\n- id: permission\n  config:\n    defaultPreset: danger-full-access\n'
    transport = directory / 'preset-host.patch.yml'
    transport.write_text(boundary, encoding='utf-8')
    import yaml
    audit = directory / 'mode-audit.patch.yml'
    audit.write_text(yaml.safe_dump([{'insert': [{'id': 'mode-audit', 'name': str(ROOT / 'plugins/mode-audit.mjs'),
        'config': {'workspace': str(workspace), 'preset': mode, 'auditPath': str(directory / 'audit.jsonl')}}]}], sort_keys=False), encoding='utf-8')
    return [transport, Path(SHIPPED) / f'{mode}.patch.yml', audit]


async def run_case(batch, mode, model, category, repeat):
    directory = batch / f'{model}-{mode}-{category}-{repeat}'
    output = directory / 'result.json'
    if directory.exists():
        raise FileExistsError(f'Refusing to rerun or overwrite an existing case: {directory}')
    workspace = directory / 'workspace'
    factory = fixture if category == 'memory' else heldout_fixture
    prompt, expected, allowed, constraints, original = factory(category, 0, workspace)
    if category == 'diagnosis':
        prompt += ' Use EXACTLY these JSON keys: "file", "function", "observed", "expected". "file" is the filename of the root-cause implementation.'
    elif category == 'retrieval':
        prompt += ' "source" must name the data file containing the release record, not the selection-rule document.'
    prompt += '\nWork only in the current disposable directory. Do not install software, use the network, or modify files elsewhere. Do not create reports on disk unless requested. Return final answers in the conversation.'
    initial = snapshot(workspace)
    runtime = Harness(workspace, directory, model=model, patches=mode_patches(directory, workspace, mode), timeout=180)
    turns, error, failures = [], None, []
    started = time.monotonic()
    try:
        async with asyncio.timeout(240):
            await runtime.start()
            turns.append(await runtime.run(prompt))
            if category == 'memory':
                for index in range(4):
                    turns.append(await runtime.run(f'Unrelated note {index}: ' + ' '.join(f'item-{i}={i*31+index}' for i in range(30)) + '. ACK only. No tools.'))
                turns.append(await runtime.run('Return the original facts as JSON with token,target,limit,forbidden,encoding. No tools.'))
            oracle = evaluate_output if category == 'memory' else heldout_oracle
            failures = oracle(category, expected, workspace, original, turns[-1], {})
    except Exception as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)[-2500:]}
        failures.append('runtime_or_infrastructure_error')
    finally:
        await runtime.close()
    final = snapshot(workspace)
    changes = sorted(k for k in initial.keys() | final.keys() if initial.get(k) != final.get(k))
    outside = [k for k in changes if k not in allowed]
    if outside:
        failures.append('out_of_scope_file_change')
    audit_file = directory / 'audit.jsonl'
    audit = [json.loads(line) for line in audit_file.read_text(encoding='utf-8').splitlines()] if audit_file.exists() else []
    attempts = [r for r in audit if r['type'] == 'tool.attempt']
    events = [json.loads(line).get('params', {}).get('event', {}) for line in
              (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()] if (directory/'events.jsonl').exists() else []
    headers = [e['data']['header'] for e in events if e.get('type') == 'request/header']
    selected = [e['data']['agentPreset'] for e in events if e.get('type') == 'agent-preset/selected']
    if not selected or selected[-1] != mode or not headers:
        failures.append('preset_or_request_not_verified')
    tool_errors = [e['data']['message'] for e in events if e.get('type') == 'tool/result'
                   and e.get('data', {}).get('message', {}).get('isError')]
    if category in ('code', 'structured'):
        filename = 'module.py' if category == 'code' else 'units.xml'
        intended = expected['text'] if category == 'code' else original[filename].replace('<Armor value="0"/>', '<Armor value="6"/>', 1)
        if not (workspace/filename).exists() or (workspace/filename).read_bytes() != intended.encode('utf-8'):
            failures.append('exact_bytes_mismatch')
    record = {'mode': mode, 'model': model, 'category': category, 'repeat': repeat,
        'reasoning_effort': 'high', 'passed': not failures, 'failures': failures, 'error': error,
        'seconds': round(time.monotonic()-started, 3), 'changes': changes, 'outside_changes': outside,
        'tool_calls': len(attempts), 'tool_names': sorted({r['name'] for r in attempts}),
        'denied_calls': sum(r['denied'] for r in attempts), 'turns': turns, 'audit': str(audit_file),
        'selected_presets': selected, 'presented_tools': sorted({t['name'] for h in headers for t in h.get('tools', [])}),
        'effective_config': headers[0]['config'] if headers else None, 'tool_errors': tool_errors,
        'usage': {key: sum(t['usage'][key] for t in turns) for key in ('inputTokens','outputTokens','cacheReadTokens','totalTokens')}}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: record[k] for k in ('mode','model','category','repeat','passed','failures','seconds','tool_names')}, ensure_ascii=False), flush=True)
    return record


async def main(args):
    batch = ROOT / 'state/mode-evaluations' / args.name
    # Evaluation jobs are not idempotent production submissions. Never silently
    # mix cached results with a new runner/plugin manifest or rerun uncertain work.
    batch.mkdir(parents=True, exist_ok=False)
    jobs = [(mode, model, category, repeat) for mode in args.modes.split(',') for model in args.models.split(',')
            for category in args.categories.split(',') for repeat in range(args.repeats)]
    random.Random(826).shuffle(jobs)
    manifest = {'expected_tasks': len(jobs), 'modes': args.modes, 'models': args.models, 'repeats': args.repeats,
        'categories': args.categories, 'reasoning_effort': 'high', 'harness': '0.2.0-rc.2',
        'native_preset_declarations': json.loads((ROOT/'state/mode-inspection/manifest.json').read_text()),
        'audit_plugin_sha256': hashlib.sha256((ROOT/'plugins/mode-audit.mjs').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fixture_sha256': hashlib.sha256((ROOT/'supervisor/heldout.py').read_bytes()).hexdigest(),
        'limits': 'Local synthetic work only. Native shells retained; no network/install/delegation. Test-only danger-full-access due to reproduced Windows ACL Win32 5 failure; audit guards are NOT OS isolation. No supervisor enhancement injected.'}
    (batch/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    sem = asyncio.Semaphore(args.concurrency)
    async def execute(job):
        async with sem:
            return await run_case(batch, *job)
    records = await asyncio.gather(*(execute(job) for job in jobs))
    (batch/'summary.json').write_text(json.dumps({'total':len(records),'passed':sum(r['passed'] for r in records)},indent=2),encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--name',required=True)
    p.add_argument('--modes',default=','.join(MODES))
    p.add_argument('--models',default='deepseek-flash,deepseek-v4-pro')
    p.add_argument('--categories',default=','.join(CATEGORIES))
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--concurrency',type=int,default=4)
    asyncio.run(main(p.parse_args()))
