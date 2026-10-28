import json
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from supervisor.mode_report import load_case
from supervisor.mode_evaluate import main as evaluate_main


class ModeEvidenceTests(unittest.TestCase):
    def test_existing_batch_is_rejected_before_model_calls(self):
        with tempfile.TemporaryDirectory() as root:
            batch = Path(root)/'state/mode-evaluations/existing'
            batch.mkdir(parents=True)
            with patch('supervisor.mode_evaluate.ROOT', Path(root)):
                with self.assertRaises(FileExistsError):
                    asyncio.run(evaluate_main(SimpleNamespace(name='existing')))

    def make_case(self, root, failures, outside):
        case = Path(root)/'case'
        case.mkdir()
        record = {'passed': not failures, 'failures': failures, 'outside_changes': outside}
        (case/'result.json').write_text(json.dumps(record), encoding='utf-8')
        events = [
            {'params': {'event': {'type': 'assistant/message', 'data': {'message': {
                'content': [{'type': 'tool-call', 'name': 'run_code'}, {'type': 'text', 'text': 'done'}]}}}}},
            {'params': {'event': {'type': 'tool/result', 'data': {'message': {'content': []}}}}},
        ]
        (case/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events), encoding='utf-8')
        return case/'result.json'

    def test_scope_is_not_waived_by_answer_review(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.make_case(root, ['wrong_fact:items', 'out_of_scope_file_change'], ['__pycache__/app.pyc'])
            result = load_case(path, {'accepted_rubric_failures': ['wrong_fact:items']})
            self.assertFalse(result['passed'])
            self.assertFalse(result['reviewed_passed'])
            self.assertTrue(result['answer_or_target_passed'])
            self.assertTrue(result['cache_only_extra_changes'])

    def test_model_call_count_excludes_tool_result_events(self):
        with tempfile.TemporaryDirectory() as root:
            result = load_case(self.make_case(root, [], []))
            self.assertEqual(result['model_tool_calls'], 1)
            self.assertEqual(result['model_tool_names'], {'run_code': 1})

    def test_review_cannot_override_scope_or_runtime_errors(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.make_case(root, ['out_of_scope_file_change'], ['KEEP.txt'])
            with self.assertRaises(ValueError):
                load_case(path, {'accepted_rubric_failures': ['out_of_scope_file_change']})


if __name__ == '__main__':
    unittest.main()
