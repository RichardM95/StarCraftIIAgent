"""Translation freshness and coverage fail independently of semantic review."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ['SC2AGENT_UI_LANGUAGE'] = 'en'
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('doc_translations', TOOLS/'audit-doc-translations.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class TranslationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'tools').mkdir()
        self.source = self.root/'guide.md'
        self.english = self.root/'guide.en.md'
        self.source.write_text('# 中文\n\n[English](guide.en.md)\n', encoding='utf-8')
        self.item = {'source': 'guide.md', 'english': 'guide.en.md'}
        self.messages = self.root/'tools/sc2_ui_messages.json'
        self.messages.write_text('{"Hello {name}":"你好 {name}"}', encoding='utf-8')
        self.save_inventory()
        self.save_translation()

    def save_inventory(self):
        (self.root/'tools/sc2_doc_translations.json').write_text(json.dumps({'pages':[self.item]}))

    def save_translation(self, body=''):
        self.english.write_text('# English\n\n[中文](guide.md)\n'
            '<!-- translation-source: guide.md; sha256: '+audit.source_digest(self.source)+' -->\n'+body,
            encoding='utf-8')

    def test_missing_and_outdated_pair(self):
        self.assertEqual(audit.check(self.root), [])
        self.source.write_text(self.source.read_text(encoding='utf-8')+'changed\n', encoding='utf-8')
        self.assertTrue(any('Outdated' in x for x in audit.check(self.root)))
        self.save_translation()
        self.english.unlink()
        self.assertTrue(any('Missing translation pair' in x for x in audit.check(self.root)))

    def test_fingerprint_normalizes_checkout_line_endings(self):
        before = audit.source_digest(self.source)
        raw = self.source.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        self.source.write_bytes(b'\xef\xbb\xbf'+raw)
        self.assertEqual(audit.source_digest(self.source), before)

    def test_missing_switch_and_placeholder_mismatch(self):
        self.english.write_text(self.english.read_text(encoding='utf-8').replace('[中文](guide.md)', ''), encoding='utf-8')
        self.assertTrue(any('Missing language switch' in x for x in audit.check(self.root)))
        self.messages.write_text('{"Hello {name}":"你好 {id}"}', encoding='utf-8')
        self.assertTrue(any('placeholders' in x for x in audit.check(self.root)))

    def test_scenario_and_complete_dialogue_counts(self):
        rows=''.join(f'| {n:02} example | request | action |\n' for n in range(1,45))
        self.source.write_text(self.source.read_text(encoding='utf-8')+rows, encoding='utf-8')
        self.item.update(scenarios=44, dialogues=2)
        self.save_inventory()
        self.save_translation(rows+'\n### First\n\n### Second\n')
        self.assertEqual(audit.check(self.root), [])
        self.english.write_text(self.english.read_text(encoding='utf-8').replace('| 12 example', '| 11 example'), encoding='utf-8')
        self.assertTrue(any('numbering' in x for x in audit.check(self.root)))
        self.save_translation(rows+'\n### First\n')
        self.assertTrue(any('dialogue count' in x for x in audit.check(self.root)))

    def test_new_owned_help_requires_a_message(self):
        (self.root/'tools/new.py').write_text('p = UIArgumentParser(description="New owned help")\n')
        self.assertTrue(any('Missing UI message' in x for x in audit.check(self.root)))

    def test_rejects_chinese_example_placeholders_in_english_pages(self):
        for body in ('Unit:<单位ID>', '`<目录>`',
                     '```powershell\npython tools/init-project.py "<路径>"\n```',
                     '&lt;单位ID&gt;'):
            with self.subTest(body=body):
                self.save_translation(body)
                errors = audit.check(self.root)
                self.assertTrue(any('Untranslated English example placeholder: guide.en.md:' in x for x in errors), errors)

    def test_allows_translated_placeholders_and_original_source_data(self):
        self.save_translation('Author: 扯蛋虾米. Original title: 伊罕利英雄设计与调整.\n'
                              '`Unit:<unit-id>` in `<map.SC2Map>`.\n'
                              '<details><summary>Examples</summary>\n'
                              '```xml\n<CUnit id="原始对象ID" />\n```\n</details>')
        self.assertEqual(audit.check(self.root), [])


if __name__ == '__main__':
    unittest.main()
