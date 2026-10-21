import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('lifecycle_audit', TOOLS / 'audit-issue-lifecycle.py')
AUDIT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUDIT)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'Suite'
        self.root.mkdir()
        self.ledger = self.base / 'issues.md'

    def tearDown(self):
        self.temp.cleanup()

    def run_audit(self, *args):
        with patch.object(AUDIT, 'REPO_ROOT', self.root), patch.object(sys, 'argv', ['audit', *map(str, args)]), redirect_stdout(io.StringIO()) as output:
            result = AUDIT.main()
        return result, output.getvalue()

    def issue(self, stage, **overrides):
        fields = {k: 'evidence' for k in AUDIT.BASE_FIELDS}
        fields.update(Status=stage)
        for gate, field in [('root cause confirmed', 'Root Cause'), ('source fixed', 'Fix'),
                            ('static validation passed', 'Validation'), ('Editor accepted', 'Editor Validation'),
                            ('packaged runtime passed', 'Runtime Validation')]:
            if AUDIT.STAGES.index(stage) >= AUDIT.STAGES.index(gate):
                fields[field] = 'target, operation and observed result'
        fields.update(overrides)
        self.ledger.write_text('### ISSUE-001: Probe\n' + ''.join(f'- **{k}:** {v}\n' for k, v in fields.items()), encoding='utf-8')

    def test_six_gates_and_each_required_evidence_field(self):
        for stage in AUDIT.STAGES:
            with self.subTest(stage=stage):
                self.issue(stage)
                self.assertEqual(self.run_audit('--ledger', self.ledger)[0], 0)
        for field in ('Root Cause', 'Fix', 'Validation', 'Editor Validation', 'Runtime Validation'):
            with self.subTest(field=field):
                self.issue('packaged runtime passed', **{field: ''})
                result, output = self.run_audit('--ledger', self.ledger)
                self.assertEqual(result, 1)
                self.assertIn(field, output)

    def test_xml_only_cannot_certify_runtime_and_ledger_is_unchanged(self):
        self.issue('packaged runtime passed', **{'Validation': 'XML only', 'Editor Validation': '', 'Runtime Validation': ''})
        before = self.ledger.read_bytes()
        self.assertEqual(self.run_audit('--ledger', self.ledger)[0], 1)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_target_isolation_reselection_and_workspace_copy(self):
        mods = self.base / 'Mods'
        main, other = mods / 'Main.SC2Mod', mods / 'Other.SC2Mod'
        source = self.base / 'Source/Main.SC2Mod'
        for p in (main, other, source):
            p.mkdir(parents=True)
        data = self.base / 'Records'
        (data / 'docs').mkdir(parents=True)
        (data / 'docs/issues.md').write_text('invalid ledger', encoding='utf-8')
        cfg = {'paths': {'mods_dir': str(mods)}, 'project': {'primary_mod': main.name, 'data_dir': str(data),
               'source_mode': 'workspace_copy', 'source_mod': str(source)}}
        config = self.root / 'agent-config.json'
        config.write_text(json.dumps(cfg), encoding='utf-8')
        for target in (main, source):
            self.assertEqual(self.run_audit('--target', target)[0], 1)
        self.assertEqual(self.run_audit('--target', other)[0], 0)
        self.assertFalse((mods / 'Other.agent').exists())
        cfg['project'] = {'primary_mod': other.name}
        config.write_text(json.dumps(cfg), encoding='utf-8')
        self.assertIn('SKIP', self.run_audit()[1])
        other_docs = mods / 'Other.agent/docs'
        other_docs.mkdir(parents=True)
        (other_docs / 'issues.md').write_text('当前无活动问题。', encoding='utf-8')
        self.assertEqual(self.run_audit('--target', other)[0], 0)
        (other_docs / 'issues.md').write_text('invalid target ledger', encoding='utf-8')
        self.assertEqual(self.run_audit('--target', other)[0], 1)
        self.assertEqual(self.run_audit()[0], 1)

    def test_selection_and_missing_files(self):
        self.assertIn('SKIP', self.run_audit()[1])
        self.assertEqual(self.run_audit('--ledger', self.ledger)[0], 1)
        self.assertEqual(self.run_audit('--target', self.base / 'Missing.SC2Mod')[0], 1)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_audit('--target', self.base, '--ledger', self.ledger)
