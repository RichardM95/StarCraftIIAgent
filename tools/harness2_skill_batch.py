"""Frozen, progressively disclosed SC2 Skill experiments on the existing Harness2 adapter."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from harness2_codex import ROOT, STATE, invoke, save, settings
from harness2_sc2 import SC2Adapter, digest, proposer, snapshot
from sc2_integration_runtime import process_lock

# The legacy module may already be cached when a test runner prepends tools/.
sys.path.insert(0, str(ROOT / 'integrations/harness2'))

MANIFEST = ROOT / 'tools/harness2-skills.json'


def registry():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def matches(actual, expected):
    """Grade domain meaning; harmless explanatory metadata is not a routing failure."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            current = actual.get(key)
            if key in ('query_tool', 'library_discovery') and isinstance(current, str):
                current = re.sub(r'^(?:python3?|py)(?:\.exe)?\s+', '', current.strip('` '))
                if isinstance(value, str) and current.split()[:len(value.split())] == value.split():
                    continue
            if key not in actual or not matches(current, value):
                return False
        return True
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(x in actual for x in expected)
    return type(actual) is type(expected) and actual == expected


def headings(text):
    """Headings outside fenced code, including examples containing Markdown headings."""
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark[0]
            elif mark[0] == fence:
                fence = None
        elif fence is None:
            match = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line.rstrip())
            if match:
                yield offset, len(match[1]), match[2]
        offset += len(line)


def slug(text):
    return re.sub(r'[^\w\- ]', '', re.sub(r'[`*_]', '', text)).lower().replace(' ', '-')


def split_source(text):
    if not text.startswith('---\n'):
        raise ValueError('Expected Skill frontmatter.')
    end = text.index('\n---', 4) + 4
    front, body = text[:end] + '\n', text[end:].lstrip('\n')
    cuts = [(pos, title) for pos, level, title in headings(body) if level == 2]
    if not cuts or cuts[0][0]:
        cuts.insert(0, (0, 'Overview'))
    parts = []
    for i, (pos, title) in enumerate(cuts):
        finish = cuts[i + 1][0] if i + 1 < len(cuts) else len(body)
        filename = f'{i + 1:02d}-' + (re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:55] or 'reference') + '.md'
        parts.append({'title': title, 'file': 'references/' + filename, 'content': body[pos:finish]})
    if ''.join(p['content'] for p in parts) != body:
        raise ValueError('Lossless section split failed.')
    return front, body, parts


def rebase(content, anchors):
    """Only Markdown link destinations move; APIs, code fences and prose remain verbatim."""
    def link(m):
        target = m[2]
        if target.startswith('#'):
            target = anchors.get(target[1:], '../SKILL.md') + target
        elif not re.match(r'^[a-zA-Z][\w+.-]*:|^/', target):
            target = '../' + target
        return m[1] + target + m[3]
    result, block = [], []
    fence = None
    for line in content.splitlines(keepends=True):
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            fence = None if fence == match[1][0] else match[1][0]
            result.append(line)
        else:
            result.append(line if fence else re.sub(r'(\]\()([^\s)]+)(\))', link, line))
    return ''.join(result)


def prepare_skill(skill_id, source):
    front, body, parts = split_source(source)
    anchors = {}
    counts = {}
    for part in parts:
        for _, _, title in headings(part['content']):
            base = slug(title)
            n = counts.get(base, 0)
            counts[base] = n + 1
            anchors[base + (f'-{n}' if n else '')] = Path(part['file']).name
    refs = {p['file']: rebase(p['content'], anchors) for p in parts}
    index = '\n'.join(f"| {p['title']} | [{p['file']}]({p['file']}) |" for p in parts)
    aliases = '\n'.join(f'<a id="{a}"></a>' for a in anchors)
    seed = front + f'''\n# {skill_id}\n
Use this Skill only within its existing description and parent routing boundary. Read the relevant section below before using an API, XML field, example, or command; the section includes its caveats. Read additional linked sections when the task crosses subsystems.

Follow workspace AGENTS.md and the configured project. GUI triggers come first; edit only verified hand-authored Galaxy. Generated MapScript.galaxy, Lib*.galaxy and publish/ remain protected. Catalog changes require the active dependency chain, inherited effective value, exact field/index and explicit source target. Reference examples alone do not establish availability. Use explicit --ui-language independently of SC2 --locale.

Use existing local tools and their --help; choose checks for the changed scope and actual target. Static evidence supports at most `static validation passed`; Editor and packaged runtime require their own observations. Parent skills own the implementation workflow; this entry selects technical references.

## Read by task\n
| Task topic | Load when needed |\n|---|---|\n{index}\n
{aliases}\n'''
    return {'id': skill_id, 'front': front, 'body_sha256': digest(body.encode()),
            'parts': [{k: v for k, v in p.items() if k != 'content'} for p in parts],
            'references': refs, 'seed': seed}


def technical_symbol(content):
    """Take API names from code, never prose such as 'helpers (NativeLib)'."""
    fenced = False
    fence = None
    for line in content.splitlines():
        mark = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if mark:
            fence = None if fence == mark[1][0] else mark[1][0]
            fenced = fence is not None
            continue
        stripped = line.strip()
        if len(stripped) < 25 or stripped.startswith(('//', '#', '/*', '*', '<!--')):
            continue
        declaration = re.match(r'^\s*(?:native\s+)?(?:void|int|fixed|bool|string|text|unit|point)\s+([A-Za-z_]\w{3,})\s*\(', line)
        if declaration:
            return declaration[1]
        if not fenced:
            continue
        code = line.split('//', 1)[0]
        match = re.search(r'\b([A-Za-z_]\w{3,})\s*\(|<([A-Za-z_]\w{3,})\b', code)
        if match and (match[1] or match[2]) not in ('while', 'switch', 'return', 'foreach'):
            return match[1] or match[2]
    return None


def make_cases(item):
    """Six disjoint reference questions plus family-specific operational branches."""
    parts = item['parts']
    technical = [p for p in parts if len(item['references'][p['file']]) > 300 and p['title'].lower() not in
                 ('overview', 'loading boundary', 'prerequisite', 'key references', 'references', 'related skills')]
    pool = technical if len(technical) >= 6 else parts
    if len(pool) < 6:
        # Separate questions may share a reference, but never the same source line.
        pool = (pool * 6)[:6]
    chosen = [pool[(i * len(pool)) // 6] for i in range(6)]
    result = []
    for i, part in enumerate(chosen):
        content = item['references'][part['file']]
        lines = [x.strip() for x in content.splitlines() if len(x.strip()) >= 35 and not x.startswith(('#', '```', '~~~', '---'))]
        line = lines[(i // max(1, len(parts))) % len(lines)] if lines else content.strip()
        symbol = technical_symbol(content)
        result.append({'id': f"{item['id']}:{i + 1}", 'skill': item['id'], 'topic': part['title'],
                       'symbol': symbol,
                       'request': 'Find the technical guidance for this topic and symbol when supplied. Quote one complete operative source line containing that symbol and explain its application. Identify any evidence boundary.',
                       '_source': part['file'], '_line': line})
    return result


POLICIES = {
    'reference': 'Read the referenced API or XML section before naming signatures/fields. New triggers use GUI first; generated Galaxy is protected.',
    'catalog': 'A local Unit omits LifeMax; active parent provides 45, an inactive sibling provides 999. User requests 60 in an explicit isolated Components copy. Explain investigation before modification.',
    'actor': 'A child actor inherits a creation event and references a model asset in active dependencies. Static XML checks pass. Identify what to inspect and the supported acceptance stage.',
    'triggers': 'Create a map trigger calling a mod action. An official example library is absent from the target active libraries. Choose the representation and discovery steps; generated Galaxy is read-only.',
    'entry': 'Route new GUI triggers, existing Galaxy, catalog fields, actors, string anchors, terrain, bank, unit migration, shared tools and Editor handoff. A separate request changes only documentation. User selects Chinese UI but enUS game strings. Explain project binding and routing.',
    'tools': 'Choose checks for documentation-only, shared-tool and mod changes; a workspace_copy project is missing source_mod. Static checks pass without Editor or runtime evidence. Explain deployment and evidence boundaries.'}


def scenario(profile, heldout=False):
    parent, override = (72, 90) if heldout else (45, 60)
    fields = {
        'reference': {'api_evidence': 'read_target_reference', 'example_scope': 'reference_only'},
        'catalog': {'effective_value': parent, 'requested_override': override, 'inactive_sibling_authoritative': False,
                    'query_tool': 'tools/sc2-catalog-query.py'},
        'actor': {'inspect': ['parent', 'creation_events', 'model', 'asset_chain'], 'visual_acceptance': False},
        'triggers': {'representation': 'gui', 'library_discovery': 'tools/sc2-trigger-query.py libraries',
                     'official_example_proves_availability': False},
        'entry': {'routes': {'new_trigger': 'sc2-map-triggers', 'existing_galaxy': 'sc2-galaxy-scripting',
             'catalog': 'sc2-catalog-xml', 'actor': 'sc2-actor-system', 'string_anchor': 'sc2-localization',
             'terrain': 'sc2-terrain-editing', 'bank': 'sc2-bank-system', 'unit_migration': 'sc2-unit-migration',
             'shared_tools': 'sc2-shared-tools', 'handoff': 'sc2-editor-handoff',
             'validation': 'sc2-tools-validation', 'attack_wave': 'sc2-attack-wave-scaling',
             'initialize_project': 'sc2-project-entry', 'docs_only': 'direct'}},
        'tools': {'scopes': {'docs_only': ['docs'], 'shared_tools': ['tools', 'docs'], 'mod_only': ['mod']},
                  'missing_workspace_source': 'stop', 'publish_writable': False}}
    question = POLICIES[profile].replace('45', str(parent)).replace('60', str(override))
    if profile == 'actor':
        question += ' Return inspect categories as parent, creation_events, model, asset_chain in that order.'
    if profile == 'reference':
        question += ' Encode API evidence as read_target_reference or memory; encode example scope as reference_only or active_dependency.'
    if profile == 'entry':
        question += ' Also route validation/deployment, attack-wave scaling and project initialization.'
    question += ' Return assessment with these field names and shapes: ' + json.dumps(
        {k: {n: 'your answer' for n in v} if isinstance(v, dict) else ['your categories'] if isinstance(v, list) else 'your answer'
         for k, v in fields[profile].items()})
    return question, fields[profile]


class SkillAdapter(SC2Adapter):
    def __init__(self, root):
        from harness2.core import tree
        from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
        from harness2.substrate.codex import CodexSubstrate, CODEX_SURFACE
        self.root = root
        self.manifest = load_json(root / 'batch.json')
        self.items = self.manifest['skills']
        self.rules = (root / 'original-agents.md').read_text(encoding='utf-8-sig')
        self.rules += '\n\nIsolated reference experiments: ' + ', '.join(x['id'] for x in self.items) + '. No source edits or external tools.\n'
        self.substrate = CodexSubstrate()
        self.surface_spec = replace(CODEX_SURFACE, always_on_max=len(self.rules) + 1000)
        self.substrate.surface = lambda: self.surface_spec
        channel = ChannelSpec('codex_cli', settings()['model'], effort='medium', timeout=600)
        self.spec = BenchSpec('sc2-skills', root / 'runs', 'codex_root', BenchPrompts(
            work='SC2 reference selection, source-grounded technical guidance and safe task routing',
            inv_levers='Improve task-triggered reference selection and retain operational boundaries.',
            dom_levers='Use the supplied lossless reference sections; preserve all technical content and case independence.',
            yardstick='Accurate source-grounded answers, bounded evidence and measured total input tokens including reference selection.'),
            {'proposer': channel, 'selector': channel})
        self.editable_paths = tuple(f".agents/skills/{x['id']}/SKILL.md" for x in self.items)
        self.edit_effort = 'medium'
        self.proposer_context_limit = 4_000_000
        self.edit_contract = ('Tools are disabled. Return notes/choice/experience using the mission format. For edits return complete Skill entries only in files. '
            'Use the candidate seeds and immutable references from sources/candidate-seeds.json. Preserve frontmatter exactly and every reference link. '
            'Replace the long inline manual with a concise task router: keep parent prerequisites, workflow, safety and evidence boundaries immediately visible. Preserve every anchor alias from the seed. '
            'Reference Markdown is an exact host-controlled migration; do not rewrite it. AGENTS, scripts, hooks, configuration and examples are immutable. '
            'No test identities or case-specific rules. Every moved section must remain reachable. Keep workflow prose within 250 words per entry, excluding metadata, reference index and anchor aliases. Make one direct, bounded improvement to the seed; no technical research or rewriting is required. Optimize actual task context including reference reads. '
            'For selection or reflection files must be empty.')
        self.base = {'AGENTS.md': self.rules}
        self.reference_tree = {}
        for item in self.items:
            prefix = f".agents/skills/{item['id']}/"
            self.base[prefix + 'SKILL.md'] = (root / 'originals' / item['path']).read_text(encoding='utf-8-sig')
            self.reference_tree.update({prefix + p: c for p, c in item['references'].items()})
        # Immutable references live once in the frozen manifest. Only accepted groups
        # materialise them; Harness2 copies the small editable entry surface.
        tree.write_tree(self.surface_spec, self.base, self.base_harness(), stubs=False)
        source = self.task_files('group')
        source.mkdir(parents=True, exist_ok=True)
        save(source / 'candidate-seeds.json', {x['id']: x['seed'] for x in self.items})
        self.cases = [c for x in self.items for c in make_cases(x)[:3]]
        self.heldout = [c for x in self.items for c in make_cases(x)[3:]]
        save(source / 'training.json', [{k: v for k, v in c.items() if not k.startswith('_')} for c in self.cases])

    def proposer_context(self, context):
        """Only routers are editable; duplicated immutable manuals do not aid that edit."""
        result, inventory = {}, {}
        for path, content in context.items():
            if '/references/' in path:
                key = path[path.rfind('/skills/') + 1:]
                inventory[key] = {'sha256': digest(content.encode()), 'characters': len(content)}
                continue
            item = next((x for x in self.items if path.endswith('/' + x['id'] + '/SKILL.md')), None)
            if item:
                original_parts = split_source(self.base[f".agents/skills/{item['id']}/SKILL.md"])[2]
                relevant = [part['content'] for part in original_parts if any(term in part['file'] for term in
                    ('loading-boundary', 'prerequisite', 'user-language', 'when-to-use', 'project-rules', 'task-routing', 'workflow'))]
                result[path] = item['front'] + '\n<!-- Optimizer view: immutable technical body is preserved by the host. Canonical destination: ' + item['path'] + '. Returned entry links must use this canonical directory, not the flattened temporary .agents path or the references subdirectory. Contract sections below retain ORIGINAL entry-relative links. See candidate-seeds.json for the complete router and every reference/anchor. -->\n' + '\n'.join(relevant)
            else:
                result[path] = content
        result['context/immutable-reference-inventory.json'] = json.dumps(inventory, ensure_ascii=False)
        if sum(len(v) for v in result.values()) > 250_000:
            raise ValueError('Router evidence exceeds the bounded optimizer context; no evidence was truncated.')
        return result

    def tasks(self, split='all'):
        return ['group']

    def task_prompt(self, task_id):
        return 'Resolve each training case using its Skill and only the references selected through the host. Explain the supplied operational scenarios. No mutations.'

    def validate_tree(self, proposed):
        if set(proposed) != set(self.base) or proposed['AGENTS.md'] != self.rules:
            raise ValueError('Candidate escaped the declared Markdown surface.')
        for item in self.items:
            path = f".agents/skills/{item['id']}/SKILL.md"
            value = proposed[path]
            if not value.startswith(item['front']) or len(value) > len(self.base[path]) * 1.15:
                raise ValueError('Candidate changed identity or expanded without a bound.')
            if value != self.base[path]:
                for part in item['parts']:
                    if '](' + part['file'] + ')' not in value:
                        raise ValueError('Candidate dropped a source section: ' + part['file'])
                for alias in re.findall(r'<a id="([^"]+)"', item['seed']):
                    if f'<a id="{alias}"></a>' not in value:
                        raise ValueError('Candidate dropped an existing section anchor: ' + alias)
        validate_links(self.markdown_files(proposed))

    def markdown_files(self, proposed, selected=None):
        files = {}
        for item in self.items:
            if selected is not None and item['id'] not in selected:
                continue
            parent = Path(item['path']).parent
            files[item['path']] = proposed[f".agents/skills/{item['id']}/SKILL.md"]
            files.update({(parent / path).as_posix(): content for path, content in item['references'].items()})
        return files

    def execute(self, task_id, harness_dir, run_id, *, timeout=None, heldout=False):
        try:
            return self._execute(task_id, harness_dir, run_id, timeout=timeout, heldout=heldout)
        except Exception as error:
            save(self.root / 'errors' / (digest(run_id.encode())[:24] + '.json'),
                 {'run_id': run_id, 'error': type(error).__name__ + ': ' + str(error)})
            raise

    def _execute(self, task_id, harness_dir, run_id, *, timeout=None, heldout=False):
        from harness2.core import tree
        selected = tree.read_tree(self.surface_spec, harness_dir or self.base_harness())
        self.validate_tree(selected)
        cases = self.heldout if heldout else self.cases
        work = self.root / 'executions' / digest(run_id.encode())[:24]
        work.mkdir(parents=True, exist_ok=True)
        identity = digest(json.dumps([selected, cases, self.manifest['identity']], sort_keys=True).encode())
        if (work / 'input.json').exists() and load_json(work / 'input.json')['sha256'] != identity:
            raise ValueError('Changed execution inputs require a fresh experiment.')
        save(work / 'input.json', {'sha256': identity})
        if (work / 'verification.json').exists():
            return work
        records, calls, answers, observations, ranges = [], [], [], [], {}
        # Sequential skills, at most two independent model calls in the Harness2 phase.
        for item in self.items:
            first_call = len(calls)
            prefix = f".agents/skills/{item['id']}/"
            entry = selected[prefix + 'SKILL.md']
            original_sections = {part['file']: part['content'] for part in split_source(self.base[prefix + 'SKILL.md'])[2]}
            own = [c for c in cases if c['skill'] == item['id']]
            public = [{k: v for k, v in c.items() if not k.startswith('_')} for c in own]
            available = {} if entry == self.base[prefix + 'SKILL.md'] else item['references']
            question, expected_assessment = scenario(item['profile'], heldout)
            common = {'rules': self.rules, 'skill': entry, 'cases': public,
                      'already_loaded_parent_context': self.manifest['parent_context'],
                      'scenario': question + ' The explicitly targeted fixture passed static validation; no Editor or game evidence exists. No formal project is writable. User requests Chinese UI and enUS game strings; workspace_copy source_mod is missing.'}
            reads = {'read': []}
            if available:
                value, call = invoke(json.dumps({**common, 'available_references': list(available),
                    'instruction': 'Return answer as JSON {"read":[relative reference paths]}. Only exact strings in available_references may be selected. The current Skill and parent prerequisites are already loaded; never select them or any path merely mentioned in their text. Select the sections necessary to answer these cases and the scenario. No file edits.'}, ensure_ascii=False), label='read-select:' + run_id + ':' + item['id'], effort='low')
                calls.append(str(call))
                reads = json.loads(value['answer'])
                if value['files'] or set(reads) != {'read'} or not isinstance(reads['read'], list) or len(set(reads['read'])) != len(reads['read']) or any(p not in available for p in reads['read']):
                    raise ValueError('Reference selection escaped the host whitelist.')
            supplied = {p: available[p] for p in reads['read']}
            value, call = invoke(json.dumps({**common, 'references': supplied, 'instruction':
                'Return answer as JSON {"cases":[{"id":"...","quote":"one complete operative source line copied exactly","explanation":"apply the guidance and its caveats"}],'
                '"policy":{"generated_sources":"read_only OR editable","new_triggers":"gui_first OR standalone_galaxy","effective_values":"active_dependencies_and_parent OR sibling_folder",'
                '"target":"explicit_configured_source OR publish","status":"highest justified final acceptance stage","deployment":"stop_if_source_missing OR guess_source",'
                '"ui_language":"chosen user interface language code","locale":"requested game string locale"},'
                '"assessment":{}, "scenario_answer":"specific workflow, tools, routing and limitations"}. Complete assessment using the scenario field names; use JSON numbers and booleans, canonical paths and exact Skill IDs, scope arrays, and direct for maintenance without a Skill. Answer every case exactly once. Do not claim execution or use tools; files must be empty.'}, ensure_ascii=False), label='solve:' + run_id + ':' + item['id'], effort='low')
            calls.append(str(call))
            ranges[item['id']] = (first_call, len(calls))
            answer = json.loads(value['answer'])
            answers.append({'skill': item['id'], 'answer': answer, 'reads': reads['read']})
            if value['files']:
                raise ValueError('Solver attempted a mutation.')
            entries = answer.get('cases', [])
            if len(entries) != len(own) or {a.get('id') for a in entries} != {c['id'] for c in own}:
                records.append({'skill': item['id'], 'passed': False, 'error': 'Missing or duplicate case.'})
            visible = entry + '\n' + '\n'.join(supplied.values()) + '\n' + '\n'.join(self.manifest['parent_context'].values())
            for case in own:
                row = next((a for a in entries if a.get('id') == case['id']), {})
                quote = row.get('quote', '')
                source = original_sections[case['_source']] if entry == self.base[prefix + 'SKILL.md'] else item['references'][case['_source']]
                grounded = isinstance(quote, str) and len(quote) >= 25 and quote in source and quote in visible and (not case['symbol'] or case['symbol'] in quote)
                records.append({'case': case['id'], 'passed': grounded and bool(row.get('explanation')),
                                'source': case['_source'], 'reference_read': case['_source'] in supplied})
            policy = answer.get('policy', {})
            expected = {'generated_sources': 'read_only', 'new_triggers': 'gui_first',
                        'effective_values': 'active_dependencies_and_parent', 'target': 'explicit_configured_source',
                        'status': 'static validation passed', 'deployment': 'stop_if_source_missing', 'ui_language': 'zh-CN', 'locale': 'enUS'}
            records.append({'skill': item['id'], 'branch': 'source_and_evidence_boundaries',
                            'passed': matches(policy, expected) and len(answer.get('scenario_answer', '')) >= 100})
            records.append({'skill': item['id'], 'branch': item['profile'],
                            'passed': matches(answer.get('assessment'), expected_assessment),
                            'assessment': answer.get('assessment')})
            observations.append({'skill': item['id'], 'references_read': reads['read'], 'answer': answer})
        usage = [load_json(Path(p) / 'state.json').get('usage') for p in calls]
        if any(not u or not isinstance(u.get('input_tokens'), int) for u in usage):
            raise ValueError('Real input token usage is required; no character proxy.')
        save(work / 'answer.json', answers)
        save(work / 'verification.json', {'cases': records, 'calls': calls,
             'input_tokens': sum(u['input_tokens'] for u in usage), 'model_calls': len(calls),
             'includes_reference_selection': True, 'observations': observations,
             'by_skill': {name: sum(u['input_tokens'] for u in usage[start:finish])
                          for name, (start, finish) in ranges.items()},
             'call_counts_by_skill': {name: finish - start for name, (start, finish) in ranges.items()}})
        (work / 'trajectory.md').write_text('[ACTION] Select references, then answer source-grounded SC2 questions\n[OBSERVATION]\n' + json.dumps(observations, ensure_ascii=False), encoding='utf-8')
        return work


def code_identity():
    paths = ['tools/harness2.py', 'tools/harness2_skill_batch.py', 'tools/harness2_sc2.py', 'tools/harness2_codex.py',
             'tools/sc2_integration_runtime.py', 'tools/harness2-skills.json', 'tools/check-doc-links.py']
    paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'integrations/harness2/harness2/core').glob('*.py'))]
    return {p: digest((ROOT / p).read_bytes()) for p in paths}


def start(ids, root=None):
    specs = {x['id']: x for g in registry()['groups'] for x in g['skills']}
    if not ids or len(set(ids)) != len(ids) or any(i not in specs for i in ids):
        raise ValueError('Select unique registered Skill IDs.')
    root = Path(root).resolve() if root else STATE / 'skill-batches' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    check_root(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'batch.json').exists():
        check_identity(root)
    else:
        items = []
        for skill_id in ids:
            spec = specs[skill_id]
            source = ROOT / spec['path']
            raw = source.read_bytes()
            dest = root / 'originals' / spec['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            item = {**spec, **prepare_skill(skill_id, raw.decode('utf-8-sig').replace('\r\n', '\n')), 'original_sha256': digest(raw)}
            items.append(item)
        (root / 'original-agents.md').write_bytes((ROOT / 'AGENTS.md').read_bytes())
        parents = set()
        if any(i.startswith('galaxy-') for i in ids):
            parents.add('skills/sc2-galaxy-scripting/SKILL.md')
        if any(i.startswith('sc2data-') for i in ids):
            parents.add('skills/sc2-catalog-xml/SKILL.md')
        context = {p: (ROOT / p).read_text(encoding='utf-8-sig') for p in sorted(parents)}
        save(root / 'batch.json', {'version': 1, 'skills': items, 'parent_context': context,
            'reasoning_effort': {'optimizer': 'medium', 'solver': 'low'}, 'identity': {'code': code_identity(),
            'settings': settings(), 'agents': digest((ROOT / 'AGENTS.md').read_bytes())}})
    return root


def check_root(root):
    if not root.resolve().is_relative_to((STATE / 'skill-batches').resolve()) or root.is_symlink():
        raise ValueError('Batch must remain in its dedicated runtime.')


def check_identity(root):
    check_root(root)
    manifest = load_json(root / 'batch.json')
    if manifest.get('reasoning_effort') != {'optimizer': 'medium', 'solver': 'low'}:
        raise ValueError('Experiment reasoning configuration changed.')
    if manifest['identity'] != {'code': code_identity(), 'settings': settings(), 'agents': digest((ROOT / 'AGENTS.md').read_bytes())}:
        raise ValueError('Code, model or rules changed; create a new experiment.')
    if any((ROOT / p).read_text(encoding='utf-8-sig') != c for p, c in manifest['parent_context'].items()):
        raise ValueError('Parent Skill changed; create a new experiment.')
    for item in manifest['skills']:
        raw = (root / 'originals' / item['path']).read_bytes()
        if digest(raw) != item['original_sha256']:
            raise ValueError('Original backup fingerprint changed.')
        prepared = prepare_skill(item['id'], raw.decode('utf-8-sig').replace('\r\n', '\n'))
        if any(item[key] != value for key, value in prepared.items()):
            raise ValueError('Frozen source migration changed.')
    return manifest


def optimize(ids, root=None):
    from harness2.core.schedule import run_domain
    root = start(ids, root)
    with process_lock(STATE / 'skill-batches.lock', timeout=2):
        adapter = SkillAdapter(root)
        result = run_domain('sc2', adapter.tasks(), 1, adapter=adapter, prop=proposer(adapter),
                            runs_root=root / 'runs', library_root=root / 'library', modes=('agg',))
        save(root / 'experiment.json', result)
    print(json.dumps({'run': str(root), 'done': result['done'], 'failed': result['failed']}), flush=True)
    return root


def finalize(root):
    root = Path(root).resolve()
    check_identity(root)
    adapter = SkillAdapter(root)
    work = root / 'runs/sc2-skills-cx-agg1/group'
    summary = load_json(work / 'summary.json')
    if summary['status'] not in ('ok', 'skipped'):
        raise ValueError('Inspect the failed Harness2 round before proceeding.')
    selection = summary['selections']['agg']
    candidate = work / 'harnesses' / selection['chosen_label']
    from harness2.core import tree
    proposed = tree.read_tree(adapter.surface_spec, candidate)
    adapter.validate_tree(proposed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        baseline = pool.submit(adapter.execute, 'group', adapter.base_harness(), 'independent/base', heldout=True)
        changed = pool.submit(adapter.execute, 'group', candidate, 'independent/candidate', heldout=True)
        independent = [load_json(p.result() / 'verification.json') for p in (baseline, changed)]
    training = [load_json(Path(summary['base'][0]['run_dir']) / 'verification.json'),
                load_json(Path(selection['chosen_run_dir']) / 'verification.json')]
    all_pass = all(c['passed'] for v in (training[1], independent[1]) for c in v['cases'])
    base_tokens = sum(v['input_tokens'] for v in (training[0], independent[0]))
    candidate_tokens = sum(v['input_tokens'] for v in (training[1], independent[1]))
    reduction = 1 - candidate_tokens / base_tokens
    per_skill = []
    for item in adapter.items:
        name = item['id']
        b = sum(v['by_skill'][name] for v in (training[0], independent[0]))
        c = sum(v['by_skill'][name] for v in (training[1], independent[1]))
        passed = all(row['passed'] for v in (training[1], independent[1]) for row in v['cases']
                     if row.get('skill') == name or row.get('case', '').startswith(name + ':'))
        corrections = []
        for before, after in (training, independent):
            for old in before['cases']:
                if old.get('skill') == name and old.get('branch') and not old['passed']:
                    if any(new.get('skill') == name and new.get('branch') == old['branch'] and new['passed'] for new in after['cases']):
                        corrections.append(old['branch'])
        per_skill.append({'id': name, 'baseline_input_tokens': b, 'candidate_input_tokens': c,
                          'baseline_mean_input_per_bundle': b / 2, 'candidate_mean_input_per_bundle': c / 2,
                          'baseline_model_calls': sum(v['call_counts_by_skill'][name] for v in (training[0], independent[0])),
                          'candidate_model_calls': sum(v['call_counts_by_skill'][name] for v in (training[1], independent[1])),
                          'input_token_reduction': 1 - c / b, 'cases_passed': passed,
                          'observed_route_corrections': sorted(set(corrections)),
                          'eligible': passed and (1 - c / b >= .1 or bool(corrections)),
                          'reason': 'Candidate checks failed' if not passed else 'Observed route correction' if corrections else
                                    'Measured input reduction >= 10%' if 1 - c / b >= .1 else 'Measured input reduction below 10%; retain original'})
    report = {'version': 1, 'run': str(root), 'candidate': str(candidate), 'all_cases_passed': all_pass,
              'model': adapter.manifest['identity']['settings']['model'],
              'authentication': adapter.manifest['identity']['settings']['authentication'],
              'reasoning_effort': adapter.manifest['reasoning_effort'], 'billing_cost_usd': None,
              'input_token_reduction': reduction, 'baseline_input_tokens': base_tokens,
              'candidate_input_tokens': candidate_tokens, 'includes_reference_selection': True,
              'eligible': any(s['eligible'] for s in per_skill), 'skills': per_skill, 'applied': False,
              'reason': 'Measured input reduction and all checks passed' if all_pass and reduction >= .1 else 'Case failure or total input reduction below 10%',
              'status': 'static validation passed' if all_pass else 'reported',
              'training': training, 'independent': independent,
              'candidate_fingerprints': {p: digest(c.encode()) for p, c in proposed.items()}}
    previous = root / 'adoption.json'
    if previous.exists() and load_json(previous).get('applied'):
        raise ValueError('Already applied; do not overwrite its restoration record.')
    save(previous, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('training', 'independent', 'candidate_fingerprints')}), flush=True)
    return report


def candidate_files(root, report, *, eligible_only=False):
    adapter = SkillAdapter(root)
    from harness2.core import tree
    proposed = tree.read_tree(adapter.surface_spec, Path(report['candidate']))
    adapter.validate_tree(proposed)
    if {p: digest(c.encode()) for p, c in proposed.items()} != report['candidate_fingerprints']:
        raise ValueError('Candidate changed after acceptance.')
    selected = {s['id'] for s in report['skills'] if s['eligible']} if eligible_only else None
    return adapter.markdown_files(proposed, selected)


def validate_links(files):
    spec = importlib.util.spec_from_file_location('batch_doc_links', ROOT / 'tools/check-doc-links.py')
    docs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(docs)
    for path, content in files.items():
        for _, line in docs.visible_lines(content):
            for destination in docs.link_destinations(line):
                target = docs.local_target(destination)
                if target is None:
                    continue
                name, anchor = target
                resolved = (ROOT / path).parent.joinpath(name).resolve() if name else (ROOT / path).resolve()
                try:
                    rel = resolved.relative_to(ROOT).as_posix()
                except ValueError:
                    raise ValueError('Link escaped workspace: ' + destination) from None
                text = files.get(rel)
                if text is None:
                    if not resolved.exists():
                        raise ValueError(path + ': broken link ' + destination)
                    if resolved.suffix == '.md':
                        text = resolved.read_text(encoding='utf-8-sig')
                if anchor and text is not None and anchor not in docs.anchors(list(docs.visible_lines(text))):
                    raise ValueError(path + ': missing anchor ' + destination)
        for tool in docs.TOOL_REF_RE.findall(content):
            if not (ROOT / tool).is_file():
                raise ValueError(path + ': missing tool ' + tool)


def apply(root):
    root = Path(root).resolve()
    manifest = check_identity(root)
    report = load_json(root / 'adoption.json')
    if not report['eligible'] or report.get('applied'):
        raise ValueError('Only a verified, unapplied candidate can be installed.')
    files = candidate_files(root, report, eligible_only=True)
    validate_links(files)
    review = load_json(root / 'review.json')
    if review.get('candidate_fingerprints') != report['candidate_fingerprints'] or review.get('reviewer') != 'primary-agent':
        raise ValueError('Primary agent must review the complete frozen diff before applying.')
    with process_lock(STATE / 'sc2-skill-apply.lock', timeout=2):
        expected = {x['path']: x['original_sha256'] for x in manifest['skills'] if x['path'] in files}
        for path in files:
            target = ROOT / path
            if target.is_symlink() or not target.resolve().is_relative_to((ROOT / 'skills').resolve()):
                raise ValueError('Target escaped canonical Skills.')
            if path in expected:
                if digest(target.read_bytes()) != expected[path]:
                    raise ValueError('Live source changed: ' + path)
            elif target.exists():
                raise ValueError('Reference already exists: ' + path)
        installed = {}
        for path, content in files.items():
            target = ROOT / path
            raw = (root / 'originals' / path).read_bytes() if path in expected else b''
            data = content.replace('\n', '\r\n').encode('utf-8') if b'\r\n' in raw else content.encode('utf-8')
            if raw.startswith(b'\xef\xbb\xbf'):
                data = b'\xef\xbb\xbf' + data
            installed[path] = digest(data)
            staged = root / 'staged' / path
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
        report.update(applied=False, applying=True, installed=installed, original_files=expected)
        save(root / 'adoption.json', report)
        for path in files:
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(root / 'staged' / path, target)
        report.update(applied=True, applying=False)
        save(root / 'adoption.json', report)


def restore(root):
    root = Path(root).resolve()
    check_root(root)
    report = load_json(root / 'adoption.json')
    if not (report.get('applied') or report.get('applying')):
        raise ValueError('Batch was not applied.')
    with process_lock(STATE / 'sc2-skill-apply.lock', timeout=2):
        for path, installed in report['installed'].items():
            target = ROOT / path
            if not target.resolve().is_relative_to((ROOT / 'skills').resolve()):
                raise ValueError('Restoration target escaped canonical Skills.')
            expected = report['original_files'].get(path)
            current = digest(target.read_bytes()) if target.is_file() else None
            if current not in {installed, expected} or target.is_symlink():
                raise ValueError('Later modification prevents group restoration: ' + path)
            if expected and digest((root / 'originals' / path).read_bytes()) != expected:
                raise ValueError('Backup changed: ' + path)
        for path in report['original_files']:
            staged = root / 'restore-staged' / path
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes((root / 'originals' / path).read_bytes())
        for path in report['installed']:
            target = ROOT / path
            if path in report['original_files']:
                os.replace(root / 'restore-staged' / path, target)
            elif target.exists():
                target.unlink()
        report.update(applied=False, applying=False, restored=True)
        save(root / 'adoption.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('optimize', 'finalize', 'apply', 'restore'))
    parser.add_argument('run', nargs='?', type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--skill')
    selection.add_argument('--batch', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'optimize':
        ids = [args.skill] if args.skill else load_json(args.batch)['skills'] if args.batch else []
        optimize(ids, args.run)
    elif args.run is None:
        parser.error('An experiment directory is required.')
    elif args.action == 'finalize':
        finalize(args.run)
    elif args.action == 'apply':
        apply(args.run)
    else:
        restore(args.run)
    return 0
