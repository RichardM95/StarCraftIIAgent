import unittest
from pathlib import Path
from supervisor.evaluate import parse_json, scope_attempt


class Evidence(unittest.TestCase):
    def test_first_requested_json_is_not_merged_with_later_object(self):
        self.assertEqual(parse_json('```json\n{"tests_run": false}\n```\nAdditional {"note": 1}'), {"tests_run": False})

    def test_rejected_escape_counts_without_resolved_path(self):
        self.assertTrue(scope_attempt({"name": "read", "denied": True, "reason": "Path is outside the task workspace"}, Path.cwd(), []))

    def test_progress_stop_is_not_misclassified_as_scope_escape(self):
        self.assertFalse(scope_attempt({"name": "read", "denied": True,
            "reason": "Repeated identical operations; returning control to supervisor"}, Path.cwd(), []))


if __name__ == "__main__":
    unittest.main()
