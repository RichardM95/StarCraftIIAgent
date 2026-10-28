"""SC2 localization Skill experiments using Harness2 and restricted real Codex calls."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import time

from harness2_codex import ROOT, STATE, invoke, save, settings

# The public tools/harness2.py launcher must not shadow the upstream package.
sys.path.insert(0, str(ROOT / 'integrations/harness2'))

SKILL = 'sc2-localization'
REL = f'.agents/skills/{SKILL}/SKILL.md'
SOURCE = ROOT / f'skills/{SKILL}/SKILL.md'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): digest(p.read_bytes())
            for p in directory.rglob('*') if p.is_file()}


def text_files(directory, *, max_chars=600_000):
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Evidence contains a symlink.')
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = path.read_text(encoding='utf-8-sig')
    if sum(len(v) for v in result.values()) > max_chars:
        raise ValueError('Evidence exceeds the pilot limit; no evidence was truncated.')
    return result


def validate_skill(content, original):
    prefix = original.split('---', 2)[:2]
    if not content.startswith('---') or content.split('---', 2)[:2] != prefix:
        raise ValueError('Preserve the original Skill name and description exactly.')
    for term in ('GameStrings.txt', 'ObjectStrings.txt', 'TriggerStrings.txt', 'GameHotkeys.txt',
                 '--mod-dir', '--locale', '--fill', 'EditorPrefix', 'EditorDescription'):
        if term not in content:
            raise ValueError('Required localization contract missing: ' + term)
    if re.search(r'(?i)(LoyalWOL|HarnessProbe|Hover\.SC2Mod|Editor\.SC2Mod|Button\.SC2Mod)', content):
        raise ValueError('Do not embed test cases or current-project identities in a reusable Skill.')
    if len(content) > len(original) * 1.1:
        raise ValueError('This pilot must improve clarity without expanding the Skill.')


def validate_links(content):
    spec = importlib.util.spec_from_file_location('harness2_doc_links', ROOT / 'tools/check-doc-links.py')
    docs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(docs)
    for _, line in docs.visible_lines(content):
        for destination in docs.link_destinations(line):
            target = docs.local_target(destination)
            if target is None:
                continue
            path, fragment = target
            resolved = (SOURCE.parent / path).resolve() if path else SOURCE
            if not resolved.exists():
                raise ValueError('Candidate Skill link is missing: ' + destination)
            if fragment and resolved.suffix == '.md' and fragment not in docs.anchors(list(docs.visible_lines(resolved.read_text(encoding='utf-8-sig')))):
                raise ValueError('Candidate Skill anchor is missing: ' + destination)
    for tool in docs.TOOL_REF_RE.findall(content):
        if not (ROOT / tool).is_file():
            raise ValueError('Candidate references a missing tool: ' + tool)


def make_cases(directory: Path, heldout=False):
    cases = []
    for number, (label, surface, field) in enumerate((('hover', 'world_hover', 'Description'),
                                                    ('button', 'command_card_tooltip', 'Tooltip'),
                                                    ('editor', 'editor_text', 'Name'))):
        locale = ('frFR', 'zhTW', 'enUS')[number] if heldout else ('zhCN', 'deDE', 'zhCN')[number]
        identity = ('Verification' if heldout else 'HarnessProbe') + str(number)
        mod = Path('components') / (label.title() + '.SC2Mod')
        target = directory / mod
        data = target / 'Base.SC2Data/GameData'
        data.mkdir(parents=True, exist_ok=True)
        (target / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>', encoding='utf-8')
        (target / 'DocumentInfo').write_text('<DocInfo/>', encoding='utf-8')
        kind = 'Button' if label == 'button' else 'Unit'
        key = f'{kind}/{"Name" if label == "editor" else "Tooltip"}/{identity}'
        (data / f'{kind}Data.xml').write_text(f'<Catalog><C{kind} id="{identity}"><{field} value="{key}"/></C{kind}></Catalog>', encoding='utf-8')
        expected = f'Text {number} <c val="FFFF00">%value%</c>=preserved'
        for current in (locale, 'koKR'):
            strings = target / f'{current}.SC2Data/LocalizedData'
            strings.mkdir(parents=True, exist_ok=True)
            (strings / 'GameStrings.txt').write_text('Sentinel/Preserve=unchanged\n' + (f'{key}=Runtime name\n' if label == 'editor' else ''), encoding='utf-8-sig')
            (strings / 'ObjectStrings.txt').write_text(f'{key}={expected}\n{kind}/EditorPrefix/{identity}=Test\n{kind}/EditorDescription/{identity}=Editor-only evidence\n', encoding='utf-8-sig')
        (target / 'MapScript.galaxy').write_bytes(b'// generated evidence: never edit\r\n')
        request = ('只定位该对象在数据编辑器中显示名称的文件和精确键，不修改名称或运行时文字。'
                   if label == 'editor' else
                   ('恢复该单位在游戏世界悬停时缺失的说明。' if label == 'hover' else '恢复命令卡按钮缺失的提示文字。')
                   + ' XML 已有显式锚点，文本在同语言 ObjectStrings 中；逐字保留标记和占位符，不创造新文案。')
        cases.append({'case': label, 'target': mod.as_posix(), 'locale': locale, 'request': request,
                      '_surface': surface, '_key': key, '_value': expected})
    public = [{k: v for k, v in c.items() if not k.startswith('_')} for c in cases]
    save(directory / 'cases.json', public)
    return cases


TASK = '''处理 cases.json 中的三个独立 SC2 Components 子任务。仅使用各 case 明确指定的 target 和 locale。
本次没有编辑器或游戏运行证据。返回的 answer 必须是无 Markdown 围栏的 JSON：
{"cases":[{"case":"case 标识","surface":"world_hover 或 command_card_tooltip 或 editor_text",
"target":"原 target","locale":"原 locale","operation":"audit_fill 或 inspect_editor",
"file":"GameStrings.txt 或 ObjectStrings.txt","key":"从 XML 和文本确认的精确键",
"status":"有证据支持的精确验收状态"}]}。
audit_fill 由宿主调用现有 audit-gamestrings-anchors.py 的业务实现，绑定 --mod-dir target --locale locale --fill；
inspect_editor 只读取 ObjectStrings，不执行写入。files 必须为空数组。不要自行调用工具。
这是工具执行前的操作提案；根据已给出的 XML 和文本定位证据，提案 status 应为 root cause confirmed。
宿主实际执行工具并复核差异后，另行记录 static validation passed；不要在提案中提前声称工具已执行。
'''


class SC2Adapter:
    def __init__(self, root):
        from harness2.core import tree
        from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
        from harness2.substrate.codex import CodexSubstrate, CODEX_SURFACE
        self.root = root
        self.original = (root / 'original-skill.md').read_text(encoding='utf-8-sig')
        self.rules = (root / 'original-agents.md').read_text(encoding='utf-8-sig') + '\n\nThis isolated experiment binds every operation to cases.json. Only the localization Skill is editable; AGENTS, scripts, hooks, project configuration and generated Galaxy are immutable.\n'
        self.substrate = CodexSubstrate()
        self.surface_spec = replace(CODEX_SURFACE, always_on_max=max(8000, len(self.rules) + 100))
        self.substrate.surface = lambda: self.surface_spec
        channel = ChannelSpec('codex_cli', settings()['model'], effort=settings()['effort'], timeout=settings()['timeout_seconds'])
        self.spec = BenchSpec('sc2-localization', root / 'runs', 'codex_root',
            BenchPrompts(work='SC2 player-text restoration and editor-name diagnosis',
                         inv_levers='Clarify and compress the existing localization Skill while retaining its operational constraints.',
                         dom_levers='Use explicit Components targets, locale folders and actual XML string anchors.',
                         yardstick='Preserve markup, generated sources and the distinction between static, Editor and runtime evidence.'),
            {'proposer': channel, 'selector': channel})
        tree.write_tree(self.surface_spec, {'AGENTS.md': self.rules, REL: self.original}, self.base_harness(), stubs=False)
        self.cases = make_cases(self.task_files('localization'))

    def tasks(self, split='all'):
        return ['localization']

    def domain_of(self, task_id):
        return 'sc2'

    def task_prompt(self, task_id):
        return TASK

    def task_files(self, task_id):
        return self.root / 'sources' / task_id

    def base_harness(self):
        return self.root / 'base'

    def validate_tree(self, proposed):
        if set(proposed) != {'AGENTS.md', REL} or proposed['AGENTS.md'] != self.rules:
            raise ValueError('Only the existing localization Skill body may change.')
        validate_skill(proposed[REL], self.original)

    def execute(self, task_id, harness_dir, run_id, *, timeout=None):
        from harness2.core import tree
        selected = tree.read_tree(self.surface_spec, harness_dir or self.base_harness())
        self.validate_tree(selected)
        work = self.root / 'executions' / digest(run_id.encode())[:24]
        work.mkdir(parents=True, exist_ok=True)
        identity = digest(json.dumps([selected, snapshot(self.task_files(task_id)), settings()], sort_keys=True).encode())
        identity_file = work / 'input.json'
        if identity_file.exists():
            if json.loads(identity_file.read_text())['sha256'] != identity:
                raise ValueError('Execution inputs changed; do not reuse this run ID.')
            if (work / 'verification.json').exists() and (work / 'answer.json').exists():
                return work
        else:
            save(identity_file, {'sha256': identity})
        copied = work / 'source'
        if not copied.exists():
            shutil.copytree(self.task_files(task_id), copied)
        before = snapshot(copied)
        prompt = json.dumps({'instructions': TASK, 'harness': selected, 'source_files': text_files(copied)}, ensure_ascii=False)
        response, call = invoke(prompt, label='solver:' + run_id)
        if response['files']:
            raise ValueError('A solver may return a plan, not file edits.')
        (work / 'answer.json').write_text(response['answer'], encoding='utf-8')
        results, observations = self.check_and_apply(response['answer'], copied, before, self.cases)
        save(work / 'verification.json', {'cases': results, 'call': str(call)})
        (work / 'trajectory.md').write_text('[ACTION] Submit structured SC2 localization operations\n[OBSERVATION]\n' + json.dumps(observations, ensure_ascii=False), encoding='utf-8')
        return work

    @staticmethod
    def check_and_apply(answer, copied, before, cases):
        spec = importlib.util.spec_from_file_location('harness2_sc2_anchor_audit', ROOT / 'tools/audit-gamestrings-anchors.py')
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        try:
            plan = json.loads(answer)
            if not isinstance(plan, dict) or set(plan) != {'cases'}:
                raise ValueError('Unexpected top-level operation fields.')
            entries = plan['cases']
            if not isinstance(entries, list) or len(entries) != len(cases):
                raise ValueError('Expected one operation for each case.')
            ids = [p['case'] for p in entries]
            if len(set(ids)) != len(cases) or set(ids) != {c['case'] for c in cases}:
                raise ValueError('Duplicate or unknown cases.')
        except (ValueError, KeyError, TypeError) as error:
            return [{'passed': False, 'error': str(error)}], [{'error': 'Malformed structured operation.'}]
        results, observations, allowed = [], [], set()
        for case in cases:
            p = next(p for p in entries if p['case'] == case['case'])
            errors = []
            target = copied / case['target']
            editor = case['case'] == 'editor'
            expected = {'surface': case['_surface'], 'target': case['target'], 'locale': case['locale'],
                        'operation': 'inspect_editor' if editor else 'audit_fill',
                        'file': 'ObjectStrings.txt' if editor else 'GameStrings.txt',
                        'key': case['_key'], 'status': 'root cause confirmed'}
            if set(p) != set(expected) | {'case'} or any(p.get(k) != v for k, v in expected.items()):
                errors.append('Returned operation does not match the supplied UI surface, target, locale, anchor or evidence.')
            if not errors and not editor:
                issues = audit.audit_mod_localization(target, fill=True, locale=case['locale'],
                                                      mods_dir=copied / 'components', campaigns_dir=copied / 'components')
                errors.extend(issues)
                relative = case['target'] + '/' + case['locale'] + '.SC2Data/LocalizedData/GameStrings.txt'
                allowed.add(relative)
                actual = audit.parse_string_map(copied / relative)
                if actual.get(case['_key']) != case['_value']:
                    errors.append('Actual restored bytes do not preserve the source text.')
            results.append({'case': case['case'], 'passed': not errors, 'errors': errors})
            observations.append({'case': case['case'], 'operation': p.get('operation'), 'issues': errors,
                                 'post_execution_status': 'static validation passed' if not errors else 'reported'})
        after = snapshot(copied)
        changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
        if not changed <= allowed:
            results.append({'passed': False, 'error': 'Changes escaped the allowed localization files.'})
        observations.append({'actual_changed_files': sorted(changed), 'generated_sources_changed': any(p.endswith('.galaxy') for p in changed)})
        return results, observations

    def delivered(self, run_dir):
        return (run_dir / 'answer.json').is_file()

    def trajectory(self, run_dir, *, obs_trunc):
        return (run_dir / 'trajectory.md').read_text(encoding='utf-8')

    def deliverable_text(self, run_dir):
        return (run_dir / 'answer.json').read_text(encoding='utf-8')

    def deliverable_files(self, run_dir):
        return {'answer.json': self.deliverable_text(run_dir)}


def proposer(adapter):
    from harness2.core.proposer import Proposer, ProposerError, Reply, _call_fingerprint

    class CodexProposer(Proposer):
        def call(self, mission, context_dir, label, *, system='', timeout=None, max_attempts=None, harvest=None):
            key = _call_fingerprint(label, mission, system, context_dir)
            cached = self._cached(label, key, require_workspace=bool(harvest))
            if cached is not None:
                self._calls.append(cached)
                return cached
            if getattr(adapter, 'transport_failure', None):
                raise ProposerError('Inspect the prior transport failure before any further model submission: ' + adapter.transport_failure, attempts=0)
            started = time.monotonic()
            context = {'context/' + k: v for k, v in text_files(Path(context_dir), max_chars=getattr(adapter, 'proposer_context_limit', 600_000)).items()}
            if hasattr(adapter, 'proposer_context'):
                context = adapter.proposer_context(context)
            prompt = json.dumps({'system': system,
                'transport': getattr(adapter, 'edit_contract', 'All context files are included below. Tools are disabled. Return answer text using the requested notes/choice/experience format. For an edit, return the full changed Skill in files; only its body is editable. Keep frontmatter, protected AGENTS and all non-obvious localization rules. Aim to reduce the Skill by at least 10%; link to existing authoritative references instead of repeating manuals. Do not add test identities or case-specific rules. For selection or reflection return an empty files array.'),
                'mission': mission, 'context_files': context}, ensure_ascii=False)
            try:
                value, call = invoke(prompt, getattr(adapter, 'editable_paths', (REL,)) if harvest else (), label=label,
                                     effort=getattr(adapter, 'edit_effort', None))
                workspace = None
                if harvest:
                    workspace = self._paths(label, key)['workspace']
                    if workspace.exists():
                        raise ValueError('Existing candidate workspace requires inspection.')
                    shutil.copytree(Path(context_dir) / 'harness', workspace)
                    for item in value['files']:
                        (workspace / item['path']).write_text(item['content'], encoding='utf-8')
                reply = Reply(label, value['answer'], True, attempts=1, channel='codex_cli',
                              workspace=workspace, wall_s=round(time.monotonic() - started, 2))
                self._write_audit(reply, mission, system, key)
                self._calls.append(reply)
                return reply
            except Exception as error:
                adapter.transport_failure = str(error)
                raise ProposerError(f'{label}: {error}', attempts=1) from error

    return CodexProposer(adapter.spec.channels['proposer'], audit_dir=adapter.root / 'audit', attempts=1)


def optimize(run=None):
    from harness2.core.schedule import run_domain
    from sc2_integration_runtime import process_lock
    root = Path(run).resolve() if run else STATE / 'sc2-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if not root.is_relative_to((STATE / 'sc2-runs').resolve()):
        raise ValueError('SC2 experiment must be inside its dedicated runtime.')
    root.mkdir(parents=True, exist_ok=True)
    with process_lock(STATE / 'sc2-optimize.lock', timeout=2):
        if not (root / 'original-skill.md').exists():
            (root / 'original-skill.md').write_bytes(SOURCE.read_bytes())
            (root / 'original-agents.md').write_bytes((ROOT / 'AGENTS.md').read_bytes())
            save(root / 'identity.json', {'settings': settings(), 'source_sha256': digest(SOURCE.read_bytes()),
                                       'agents_sha256': digest((ROOT / 'AGENTS.md').read_bytes())})
        identity = json.loads((root / 'identity.json').read_text())
        if identity['settings'] != settings() or identity['source_sha256'] != digest(SOURCE.read_bytes()) or identity['agents_sha256'] != digest((ROOT / 'AGENTS.md').read_bytes()):
            raise ValueError('Configuration or Skill changed; start a new experiment.')
        adapter = SC2Adapter(root)
        result = run_domain('sc2', adapter.tasks(), 1, adapter=adapter, prop=proposer(adapter),
                            runs_root=root / 'runs', library_root=root / 'library', modes=('agg',))
        save(root / 'experiment.json', result)
        print(json.dumps({'run': str(root), 'done': result['done'], 'failed': result['failed']}, ensure_ascii=False), flush=True)
        return root


def finalize(run, apply=False):
    from harness2.core import tree
    from sc2_integration_runtime import process_lock
    root = Path(run).resolve()
    if not root.is_relative_to((STATE / 'sc2-runs').resolve()):
        raise ValueError('Experiment path is outside the dedicated runtime.')
    work = root / 'runs/sc2-localization-cx-agg1/localization'
    summary = json.loads((work / 'summary.json').read_text())
    if summary['status'] not in ('ok', 'skipped'):
        raise ValueError('The Harness2 experiment did not complete successfully.')
    selection = summary['selections']['agg']
    candidate = work / 'harnesses' / selection['chosen_label']
    adapter = SC2Adapter(root)
    reviewed = root / 'review.json'
    if reviewed.is_file():
        review = json.loads(reviewed.read_text())
        if digest((candidate / REL).read_bytes()) != review['composed_skill_sha256']:
            raise ValueError('The upstream composed Skill changed after review.')
        candidate = root / 'reviewed-harness'
        if digest((candidate / REL).read_bytes()) != review['reviewed_skill_sha256']:
            raise ValueError('The reviewed Skill changed; review it again before validation.')
    proposed = tree.read_tree(adapter.surface_spec, candidate)
    adapter.validate_tree(proposed)
    validate_links(proposed[REL])
    baseline_run = Path(summary['base'][0]['run_dir'])
    candidate_run = Path(selection['chosen_run_dir'])
    if reviewed.is_file():
        candidate_run = adapter.execute('localization', candidate, 'reviewed/training')
    def outcome(directory):
        # Recheck raw model artifacts under the current acceptance implementation.
        # Internal pilot verdicts never substitute for the final acceptance run.
        import tempfile
        checks = root / 'acceptance'
        checks.mkdir(exist_ok=True)
        task = 'holdout' if directory in (root / 'executions' / digest(b'heldout/baseline')[:24],
                                         root / 'executions' / digest(b'heldout/candidate')[:24]) else 'localization'
        with tempfile.TemporaryDirectory(dir=checks) as temporary:
            copied = Path(temporary) / 'source'
            shutil.copytree(adapter.task_files(task), copied)
            items, observations = adapter.check_and_apply((directory / 'answer.json').read_text(), copied,
                                                          snapshot(copied), adapter.cases)
            save(directory / 'acceptance-current.json', {'cases': items, 'observations': observations,
                                                        'acceptance_source_sha256': digest(Path(__file__).read_bytes())})
        return {'passed': sum(bool(p['passed']) for p in items), 'total': len(items)}
    train = {'baseline': outcome(baseline_run), 'candidate': outcome(candidate_run)}
    # Held-out materials are first created after upstream composition and selection.
    adapter.cases = make_cases(adapter.task_files('holdout'), heldout=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        base_future = pool.submit(adapter.execute, 'holdout', None, 'heldout/baseline')
        candidate_future = pool.submit(adapter.execute, 'holdout', candidate, 'heldout/candidate')
        holdout_base, holdout_candidate = base_future.result(), candidate_future.result()
    holdout = {'baseline': outcome(holdout_base), 'candidate': outcome(holdout_candidate)}
    reduction = 1 - len(proposed[REL]) / len(adapter.original)
    eligible = (train['candidate']['passed'] == train['candidate']['total'] == 3
                and holdout['candidate']['passed'] == holdout['candidate']['total'] == 3
                and train['candidate']['passed'] >= train['baseline']['passed']
                and holdout['candidate']['passed'] >= holdout['baseline']['passed']
                and reduction >= .10)
    report_file = root / 'adoption.json'
    previous = json.loads(report_file.read_text()) if report_file.exists() else {}
    report = {'skill': SKILL, 'run': str(root), 'model': settings()['model'],
              'endpoint': settings()['endpoint'], 'authentication': settings()['authentication'],
              'sandbox': 'read-only', 'agent_tool_execution_enabled': False,
              'training': train, 'heldout': holdout,
              'original_characters': len(adapter.original), 'candidate_characters': len(proposed[REL]),
              'character_reduction': round(reduction, 4),
              'eligible': eligible, 'applied': previous.get('applied', False),
              'original_sha256': digest((root / 'original-skill.md').read_bytes()),
              'candidate': str(candidate / REL), 'status': 'static validation passed',
              'primary_agent_review': reviewed.is_file(),
              'scope': 'Three training and three held-out localization cases; no Editor or game evidence.',
              'cost_usd': None}
    if report['applied']:
        report['applied_sha256'] = previous['applied_sha256']
    if apply and eligible and not report['applied']:
        with process_lock(STATE / 'sc2-skill-apply.lock', timeout=2):
            before = SOURCE.read_bytes()
            if digest(before) != report['original_sha256']:
                raise ValueError('The live Skill changed since the experiment; no merge was applied.')
            content = proposed[REL].replace('\r\n', '\n')
            if b'\r\n' in before:
                content = content.replace('\n', '\r\n')
            encoded = (b'\xef\xbb\xbf' if before.startswith(b'\xef\xbb\xbf') else b'') + content.encode('utf-8')
            temporary = SOURCE.with_name('SKILL.md.harness2.tmp')
            temporary.write_bytes(encoded)
            import os
            os.replace(temporary, SOURCE)
            report.update(applied=True, applied_sha256=digest(encoded))
    save(report_file, report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def restore(run):
    from sc2_integration_runtime import process_lock
    root = Path(run).resolve()
    if not root.is_relative_to((STATE / 'sc2-runs').resolve()):
        raise ValueError('Experiment path is outside the dedicated runtime.')
    report = json.loads((root / 'adoption.json').read_text())
    with process_lock(STATE / 'sc2-skill-apply.lock', timeout=2):
        if not report.get('applied') or digest(SOURCE.read_bytes()) != report['applied_sha256']:
            raise ValueError('The installed Skill changed or this experiment was not applied; inspect before restoring.')
        original = (root / 'original-skill.md').read_bytes()
        if digest(original) != report['original_sha256']:
            raise ValueError('The original Skill backup changed; restore stopped.')
        SOURCE.write_bytes(original)
        report.update(applied=False, restored=True)
        save(root / 'adoption.json', report)


if __name__ == '__main__':
    if '--help' in sys.argv or any(arg in ('--skill', '--batch') or arg.startswith(('--skill=', '--batch=')) for arg in sys.argv) or (len(sys.argv) > 2 and (Path(sys.argv[2]) / 'batch.json').is_file()):
        from harness2_skill_batch import main
        raise SystemExit(main(sys.argv[1:]))
    command = sys.argv[1] if len(sys.argv) > 1 else 'optimize'
    if command == 'optimize':
        optimize(sys.argv[2] if len(sys.argv) > 2 else None)
    elif command in ('finalize', 'apply'):
        finalize(sys.argv[2], apply=command == 'apply')
    elif command == 'restore':
        restore(sys.argv[2])
    else:
        raise SystemExit('Use optimize, finalize, apply or restore with an experiment directory.')
