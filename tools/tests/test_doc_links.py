
import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('doc_links', Path(__file__).resolve().parents[1] / 'check-doc-links.py')
DOCS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DOCS)


class DocLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def test_unicode_duplicate_setext_and_html_anchors(self):
        self.write('target.md', '# 中文标题\n# 中文标题\n## 💬 对话\n<a id="custom"></a>\n<a name="legacy"></a>\nSetext\n---\n')
        self.write('README.md', '\n'.join(f'[link](target.md#{a})' for a in ('中文标题', '中文标题-1', '-对话', 'custom', 'legacy', 'setext')))
        self.assertEqual(DOCS.check(self.root), [])
        self.write('README.md', '[bad](target.md#missing)')
        self.assertIn('missing anchor', DOCS.check(self.root)[0])

    def test_complex_and_encoded_paths_and_titles(self):
        p = self.write('目录 (x86)/a(b).md', '# 目标\n')
        self.write('README.md', f'[one]( <目录 (x86)/a(b).md#目标> )\n[two](目录%20(x86)/a(b).md#%E7%9B%AE%E6%A0%87 "title")\n[abs](<{p}#目标>)')
        self.assertEqual(DOCS.check(self.root), [])

    def test_fences_mask_links_and_headings_but_not_tool_commands(self):
        self.write('README.md', '# Real\n```md\n[fake](missing.md)\n# Fake\n~~~\n```\n[real](#real)\n~~~md\n[fake](absent.md)\n~~~\n')
        self.assertEqual(DOCS.check(self.root), [])
        self.write('README.md', '```md\n# Fake\n```\n[bad](#fake)\n```text\npython tools/absent.py\n```')
        errors = DOCS.check(self.root)
        self.assertTrue(any('missing anchor' in e for e in errors))
        self.assertTrue(any('missing tool' in e for e in errors))

    def test_ignored_directories_and_external_schemes(self):
        for name in ('backup', '_backups', 'tmp-123', 'reports', '.git', '.workspace-recovery', 'publish', '__pycache__', 'node_modules'):
            self.write(f'{name}/bad.md', '[bad](missing.md)\npython tools/missing.py')
        self.write('README.md', '[web](https://example.invalid/a#b)\n[app](codex://review)\n[mail](mailto:a@b)\n[cdn](//example.invalid/a)')
        self.assertEqual(DOCS.check(self.root), [])

    def test_missing_file_and_tools_in_yaml(self):
        self.write('README.md', '[bad](absent.md)')
        self.write('agents/a.yaml', 'command: python tools/absent.py')
        self.assertEqual(len(DOCS.check(self.root)), 2)

    def test_horizontal_rule_does_not_duplicate_atx_heading(self):
        self.write('README.md', '# Real\n---\n[bad](#real-1)')
        self.assertIn('missing anchor', DOCS.check(self.root)[0])
