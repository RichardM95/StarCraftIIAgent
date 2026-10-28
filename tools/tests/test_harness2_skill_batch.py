from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness2_skill_batch as batch


class SkillBatchTests(unittest.TestCase):
    def test_api_cases_do_not_turn_prose_or_comments_into_symbols(self):
        text = 'Use helpers (NativeLib).\n```galaxy\n// helpers (not an API declaration)\nfixed value = RealClamp(0.1, 0.0, 1.0);\n```\n'
        self.assertEqual(batch.technical_symbol(text), 'RealClamp')
        self.assertIsNone(batch.technical_symbol('Use helpers (NativeLib), consulting relevant references.'))

    def test_assessment_ignores_explanation_but_never_changes_domain_values(self):
        expected = {'effective_value': 45, 'inactive_sibling_authoritative': False,
                    'scopes': ['tools', 'docs']}
        self.assertTrue(batch.matches({**expected, 'explanation': 'No tools were executed.'}, expected))
        self.assertFalse(batch.matches({**expected, 'effective_value': 999}, expected))
        self.assertFalse(batch.matches({**expected, 'inactive_sibling_authoritative': 0}, expected))
        self.assertTrue(batch.matches({**expected, 'scopes': ['docs', 'tools']}, expected))

    def test_lossless_split_keeps_fenced_headings_and_examples(self):
        original = '---\nname: demo\ndescription: A test\n---\n\n# Title\n\n## API\n```markdown\n## example\n```\n\n## Caveat\nKeep this rule.\n'
        front, body, parts = batch.split_source(original)
        self.assertEqual(''.join(p['content'] for p in parts), body)
        self.assertEqual(len(parts), 3)
        self.assertIn('## example', parts[1]['content'])
        self.assertTrue(front.endswith('---\n'))

    def test_reference_rebasing_preserves_code_and_targets(self):
        source = '[Parent](../../parent.md)\n[Next](#next)\n```text\n[example](same.md)\n```\n'
        actual = batch.rebase(source, {'next': '02-next.md'})
        self.assertIn('(../../../parent.md)', actual)
        self.assertIn('(02-next.md#next)', actual)
        self.assertIn('[example](same.md)', actual)

    def test_optimizer_contract_retains_entry_coordinates_not_reference_coordinates(self):
        sid = 'galaxy-actor-and-visuals'
        path = f'skills/galaxy/{sid}/SKILL.md'
        source = (batch.ROOT / path).read_text(encoding='utf-8-sig')
        item = {**batch.prepare_skill(sid, source), 'path': path}
        agent = object.__new__(batch.SkillAdapter)
        agent.items = [item]
        key = f'.agents/skills/{sid}/SKILL.md'
        agent.base = {key: source}
        value = agent.proposer_context({'context/harness/' + key: source})['context/harness/' + key]
        self.assertIn('Canonical destination: ' + path, value)
        self.assertIn('](../../sc2-galaxy-scripting/SKILL.md)', value)
        self.assertNotIn('](../../../sc2-galaxy-scripting/SKILL.md)', value)

    def test_bad_parent_links_are_rejected_before_model_execution(self):
        sid = 'galaxy-actor-and-visuals'
        path = f'skills/galaxy/{sid}/SKILL.md'
        source = (batch.ROOT / path).read_text(encoding='utf-8-sig')
        item = {**batch.prepare_skill(sid, source), 'path': path}
        agent = object.__new__(batch.SkillAdapter)
        agent.items, agent.rules = [item], 'Rules'
        key = f'.agents/skills/{sid}/SKILL.md'
        agent.base = {'AGENTS.md': agent.rules, key: source}
        proposed = {**agent.base, key: item['seed'] + '\n[Parent](../../../sc2-galaxy-scripting/SKILL.md)\n'}
        with self.assertRaisesRegex(ValueError, 'broken link'):
            agent.validate_tree(proposed)

    def test_immutable_references_do_not_expand_upstream_editable_surface(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('batch_tree_test', batch.ROOT / 'integrations/harness2/harness2/core/tree.py')
        tree = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = tree
        spec.loader.exec_module(tree)
        is_allowed = tree.is_allowed
        CODEX_SURFACE = tree.SurfaceSpec(name='codex', always_on=('AGENTS.md',), always_on_max=8000,
            always_on_cap_reason='test', skill_dir='.agents/skills', skill_name_rule='must_match',
            trigger_hint='', autotrigger_file='AGENTS.md', trigger_line='', subagent_requires_mode=False,
            plugin_dir=None, hooks_file=None)
        path = '.agents/skills/demo/references/api.md'
        self.assertFalse(is_allowed(CODEX_SURFACE, path))
        for bad in ('.agents/skills/demo/references/../../AGENTS.md',
                    '.agents/skills/demo/references/hook.py', 'C:/outside.md'):
            self.assertFalse(is_allowed(CODEX_SURFACE, bad))

    def test_registry_has_exact_requested_order_and_coverage(self):
        groups = batch.registry()['groups']
        self.assertEqual([s['id'] for s in groups[0]['skills']],
            ['galaxy-language-fundamentals', 'galaxy-code-organization', 'galaxy-math-strings-conversion'])
        skills = [s['id'] for g in groups for s in g['skills']]
        self.assertEqual(len(skills), 24)
        self.assertEqual(len(set(skills)), 24)
        self.assertEqual([s['id'] for s in groups[-1]['skills']], ['sc2-project-entry', 'sc2-tools-validation'])
        self.assertNotIn('sc2-localization', skills)

    def test_every_source_is_losslessly_migrated_and_six_cases_are_disjoint(self):
        for group in batch.registry()['groups']:
            for spec in group['skills']:
                text = (batch.ROOT / spec['path']).read_text(encoding='utf-8-sig')
                item = batch.prepare_skill(spec['id'], text)
                cases = batch.make_cases(item)
                self.assertEqual(len(cases), 6, spec['id'])
                self.assertEqual(len({c['id'] for c in cases}), 6)
                self.assertTrue(all(c['_line'] in item['references'][c['_source']] for c in cases))

    def test_independent_catalog_case_changes_values(self):
        _, train = batch.scenario('catalog')
        _, independent = batch.scenario('catalog', True)
        self.assertEqual(train['effective_value'], 45)
        self.assertEqual(independent['effective_value'], 72)
        self.assertNotEqual(train, independent)

    def exercise_reader(self, root, *, candidate=False, escape=False):
        import types
        text = '---\nname: demo\ndescription: Reference test\n---\n\n' + ''.join(
            f'## API {i}\nFollow [index](../../wiki/index.md) before using this API.\n' + (f'int Native{i}(int count) {{ return count; }} // authoritative API example\n' * 8)
            for i in range(1, 7))
        item = {**batch.prepare_skill('demo', text), 'profile': 'reference', 'path': 'skills/demo/SKILL.md'}
        agent = object.__new__(batch.SkillAdapter)
        agent.root, agent.items, agent.rules = root, [item], 'Immutable rules'
        agent.surface_spec = None
        agent.manifest = {'parent_context': {}, 'identity': {}}
        entry = '.agents/skills/demo/SKILL.md'
        agent.base = {'AGENTS.md': agent.rules, entry: text}
        agent.reference_tree = {'.agents/skills/demo/' + p: c for p, c in item['references'].items()}
        agent.cases = batch.make_cases(item)[:3]
        agent.cases[0]['symbol'] = None
        agent.heldout = batch.make_cases(item)[3:]
        tree = dict(agent.base)
        if candidate:
            tree[entry] = item['seed']
        calls = []
        def invoke(prompt, *args, **kwargs):
            request = json.loads(prompt)
            calls.append(request)
            directory = root / 'calls' / str(len(calls))
            batch.save(directory / 'state.json', {'usage': {'input_tokens': 100}})
            if 'available_references' in request:
                self.assertNotIn('authoritative API example', prompt)
                return {'files': [], 'answer': json.dumps({'read': ['../../config'] if escape else
                    [c['_source'] for c in agent.cases]})}, directory
            raw_parts = {p['file']: p['content'] for p in batch.split_source(text)[2]}
            answer = {'cases': [{'id': c['id'], 'quote': next(line for line in (item['references'] if candidate else raw_parts)[c['_source']].splitlines()
                      if c['symbol'] in line) if c['symbol'] else next(line for line in (item['references'] if candidate else raw_parts)[c['_source']].splitlines() if line.startswith('Follow ')),
                      'explanation': 'Use the supplied exact API example.'} for c in agent.cases],
                      'assessment': batch.scenario('reference')[1],
                      'policy': {'generated_sources': 'read_only', 'new_triggers': 'gui_first',
                          'effective_values': 'active_dependencies_and_parent', 'target': 'explicit_configured_source',
                          'status': 'static validation passed', 'deployment': 'stop_if_source_missing',
                          'ui_language': 'zh-CN', 'locale': 'enUS'}, 'scenario_answer': 'Source-grounded bounded workflow. ' * 5}
            return {'files': [], 'answer': json.dumps(answer)}, directory
        fake_core = types.ModuleType('harness2.core')
        fake_core.tree = types.SimpleNamespace(read_tree=lambda *a, **k: tree)
        with patch.dict(sys.modules, {'harness2.core': fake_core}), patch.object(batch, 'invoke', side_effect=invoke):
            if escape:
                with self.assertRaisesRegex(ValueError, 'whitelist'):
                    agent.execute('group', root, 'test')
                self.assertEqual(len(calls), 1)
                return
            result = batch.load_json(agent.execute('group', root, 'test') / 'verification.json')
        self.assertTrue(all(c['passed'] for c in result['cases']))
        self.assertEqual(result['input_tokens'], 200 if candidate else 100)
        self.assertEqual(result['by_skill']['demo'], result['input_tokens'])
        self.assertEqual(len(calls), 2 if candidate else 1)

    def test_baseline_has_no_artificial_read_call_and_candidate_counts_both_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.exercise_reader(root / 'base')
            self.exercise_reader(root / 'candidate', candidate=True)

    def test_read_escape_is_rejected_before_solver_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.exercise_reader(Path(tmp), candidate=True, escape=True)

    def test_group_restore_checks_all_files_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'skills/demo').mkdir(parents=True)
            (root / '.runtime/harness2/skill-batches/run/originals/skills/demo').mkdir(parents=True)
            run = root / '.runtime/harness2/skill-batches/run'
            original = b'original\r\n'
            live = root / 'skills/demo/SKILL.md'
            live.write_bytes(b'installed')
            ref = root / 'skills/demo/ref.md'
            ref.write_bytes(b'user change')
            (run / 'originals/skills/demo/SKILL.md').write_bytes(original)
            report = {'applied': True, 'installed': {'skills/demo/SKILL.md': batch.digest(b'installed'),
                       'skills/demo/ref.md': batch.digest(b'reference')},
                      'original_files': {'skills/demo/SKILL.md': batch.digest(original)}}
            batch.save(run / 'adoption.json', report)
            with patch.object(batch, 'ROOT', root), patch.object(batch, 'STATE', root / '.runtime/harness2'):
                with self.assertRaisesRegex(ValueError, 'Later modification'):
                    batch.restore(run)
                self.assertEqual(live.read_bytes(), b'installed')
                ref.write_bytes(b'reference')
                batch.restore(run)
                self.assertEqual(live.read_bytes(), original)
                self.assertFalse(ref.exists())

    def test_interrupted_atomic_group_apply_can_restore_without_partial_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / '.runtime/harness2/skill-batches/run'
            original = b'original\r\n'
            path = 'skills/demo/SKILL.md'
            ref = 'skills/demo/references/api.md'
            live = root / path
            live.parent.mkdir(parents=True)
            live.write_bytes(original)
            backup = run / 'originals' / path
            backup.parent.mkdir(parents=True)
            backup.write_bytes(original)
            manifest = {'skills': [{'path': path, 'original_sha256': batch.digest(original)}]}
            report = {'eligible': True, 'applied': False, 'candidate_fingerprints': {'entry': 'reviewed'}}
            batch.save(run / 'adoption.json', report)
            batch.save(run / 'review.json', {'reviewer': 'primary-agent', 'candidate_fingerprints': report['candidate_fingerprints']})
            actual_replace = batch.os.replace
            def replace(source, target):
                if Path(target) == root / ref:
                    raise OSError('Simulated second-file interruption')
                return actual_replace(source, target)
            with patch.object(batch, 'ROOT', root), patch.object(batch, 'STATE', root / '.runtime/harness2'), \
                 patch.object(batch, 'check_identity', return_value=manifest), \
                 patch.object(batch, 'candidate_files', return_value={path: 'new\n', ref: 'API\n'}), \
                 patch.object(batch, 'validate_links'), patch.object(batch.os, 'replace', side_effect=replace):
                with self.assertRaisesRegex(OSError, 'second-file'):
                    batch.apply(run)
                self.assertEqual(live.read_bytes(), b'new\r\n')
                self.assertFalse((root / ref).exists())
                batch.restore(run)
                self.assertEqual(live.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
