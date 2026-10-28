from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness2_codex as transport
import harness2_sc2 as adapter


def plan_for(cases):
    return {'cases': [{'case': c['case'], 'surface': c['_surface'], 'target': c['target'],
        'locale': c['locale'], 'operation': 'inspect_editor' if c['case'] == 'editor' else 'audit_fill',
        'file': 'ObjectStrings.txt' if c['case'] == 'editor' else 'GameStrings.txt',
        'key': c['_key'], 'status': 'root cause confirmed'} for c in cases]}


class Harness2SC2Tests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Native Windows transport')
    def test_concurrent_identical_requests_wait_and_share_one_model_process(self):
        from concurrent.futures import ThreadPoolExecutor
        import time
        config = {'codex': 'fake-codex.exe', 'model': 'chosen-model', 'effort': 'low',
                  'auth_home': str(self.source), 'timeout_seconds': 2}
        started = []
        class FakeProcess:
            pid, returncode = 4242, 0
            def __init__(inner, command, **kwargs):
                started.append(command)
                inner.directory, inner.stdout = Path(kwargs['cwd']), kwargs['stdout']
            def communicate(inner, prompt, timeout):
                time.sleep(.15)
                transport.save(inner.directory / 'response.json', {'answer': 'same result', 'files': []})
                inner.stdout.write((json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100}}) + '\n').encode())
                inner.stdout.flush()
        with patch.object(transport, 'STATE', self.source / 'native'), \
             patch.object(transport, 'settings', side_effect=lambda: dict(config)), \
             patch.object(transport.subprocess, 'Popen', side_effect=FakeProcess):
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = [pool.submit(transport.invoke, 'identical source request', label='duplicate') for _ in range(2)]
                results = [job.result() for job in jobs]
        self.assertEqual(len(started), 1)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0]['answer'], 'same result')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        self.cases = adapter.make_cases(self.source)
        self.before = adapter.snapshot(self.source)

    def test_actual_tool_restores_both_runtime_anchors_and_preserves_other_files(self):
        result, obs = adapter.SC2Adapter.check_and_apply(json.dumps(plan_for(self.cases)), self.source, self.before, self.cases)
        self.assertTrue(all(item['passed'] for item in result), result)
        changed = obs[-1]['actual_changed_files']
        self.assertEqual(len(changed), 2)
        self.assertTrue(all(name.endswith('/GameStrings.txt') for name in changed))
        self.assertFalse(obs[-1]['generated_sources_changed'])

    def test_cross_target_and_false_editor_acceptance_do_not_write(self):
        plan = plan_for(self.cases)
        for row in plan['cases']:
            row['target'] = '../../LoyalWOL.SC2Mod'
            row['status'] = 'Editor accepted'
        result, _ = adapter.SC2Adapter.check_and_apply(json.dumps(plan), self.source, self.before, self.cases)
        self.assertFalse(any(item['passed'] for item in result))
        self.assertEqual(adapter.snapshot(self.source), self.before)

    def test_duplicate_case_rejects_whole_plan(self):
        plan = plan_for(self.cases)
        plan['cases'][1] = plan['cases'][0]
        result, _ = adapter.SC2Adapter.check_and_apply(json.dumps(plan), self.source, self.before, self.cases)
        self.assertFalse(result[0]['passed'])
        self.assertEqual(adapter.snapshot(self.source), self.before)

    def test_preexecution_status_and_postexecution_evidence_are_distinct(self):
        result, observations = adapter.SC2Adapter.check_and_apply(json.dumps(plan_for(self.cases)), self.source, self.before, self.cases)
        self.assertTrue(all(p['passed'] for p in result))
        self.assertTrue(all(p['post_execution_status'] == 'static validation passed' for p in observations[:-1]))

    def test_native_command_cannot_bypass_sandbox_or_hook_trust(self):
        command = transport.argv({'codex': 'codex.exe', 'model': 'chosen-model', 'effort': 'high'}, self.source)
        self.assertIn('read-only', command)
        self.assertIn('on-request', command)
        self.assertIn('--ignore-user-config', command)
        self.assertFalse(any('dangerously' in item for item in command))
        self.assertNotIn('--add-dir', command)
        self.assertIn('shell_tool', command)

    def test_all_codex_entrypoints_preserve_sandbox_and_approval(self):
        root = adapter.ROOT / 'integrations/harness2'
        for name in ('harness2/substrate/codex.py', 'third_party/jb_runner/run_benchmark_codex_cli_adapt.sh',
                     'third_party/wb_runner/agents/codex_agent.py', 'third_party/lab_runner/adapt_runs_cx/run_codex_lab.py'):
            source = (root / name).read_text(encoding='utf-8')
            self.assertNotIn('--dangerously-bypass-', source, name)
            self.assertIn('workspace-write', source, name)
            self.assertIn('on-request', source, name)

    def test_skill_cannot_change_frontmatter_or_drop_explicit_target(self):
        original = adapter.SOURCE.read_text(encoding='utf-8-sig')
        adapter.validate_skill(original, original)
        with self.assertRaises(ValueError):
            adapter.validate_skill(original.replace('--mod-dir', '--wrong-target'), original)
        with self.assertRaises(ValueError):
            adapter.validate_skill(original.replace('name: sc2-localization', 'name: other-skill'), original)

    def test_restore_preserves_original_bytes_and_refuses_later_user_changes(self):
        run = self.source / 'sc2-runs/restore-check'
        run.mkdir(parents=True)
        original, applied = b'original\r\nwith original line endings\r\n', b'applied candidate\n'
        (run / 'original-skill.md').write_bytes(original)
        transport.save(run / 'adoption.json', {'applied': True, 'original_sha256': adapter.digest(original),
                                              'applied_sha256': adapter.digest(applied)})
        live = self.source / 'LiveSkill.md'
        live.write_bytes(b'later user changes')
        with patch.object(adapter, 'SOURCE', live), patch.object(adapter, 'STATE', self.source):
            with self.assertRaises(ValueError):
                adapter.restore(run)
            self.assertEqual(live.read_bytes(), b'later user changes')
            live.write_bytes(applied)
            adapter.restore(run)
        self.assertEqual(live.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
