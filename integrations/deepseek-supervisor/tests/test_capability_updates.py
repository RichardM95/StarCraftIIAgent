import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor import report


class CapabilityUpdates(unittest.TestCase):
    def update(self):
        return {
            "schema_version": 1,
            "registered_at": "2026-10-17T17:16:59+08:00",
            "evaluation": {"id": "flash-1017", "report_date": "2026-10-17",
                           "model_snapshot": "DeepSeek-V4.1-Flash-1017",
                           "report_path": "reports/1017.md"},
            "effective_routing": {"deepseek-flash": {
                "algorithms": {"label": "算法", "routing": "auto_delegate_with_review"},
                "compaction": {"label": "压缩", "routing": "provisional_only",
                               "tested_on_snapshot": False}}},
            "model_profiles": {"deepseek-flash": {"report_date": "2026-10-17"}},
            "limitations": ["1017 compaction not tested"],
        }

    def test_missing_updates_preserve_existing_profile(self):
        profile = {"effective_routing": {"legacy": {}}, "limitations": ["old"]}
        before = copy.deepcopy(profile)
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(report.apply_capability_updates(profile, Path(temp)), before)

    def test_new_snapshot_does_not_inherit_old_compaction_and_preserves_pro(self):
        pro = {"code": {"routing": "auto_delegate_with_review"}}
        profile = {"effective_routing": {
            "deepseek-flash": {"compaction": {"routing": "auto_delegate_with_review"},
                               "obsolete_category": {"routing": "auto_delegate_with_review"}},
            "deepseek-v4-pro": copy.deepcopy(pro)},
            "batches": [{"id": "historical-score", "passed": 66}], "limitations": ["legacy"]}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "2026-10-17.json").write_text(json.dumps(self.update()), encoding="utf-8")
            result = report.apply_capability_updates(profile, directory)
            self.assertEqual(result["effective_routing"]["deepseek-v4-pro"], pro)
            self.assertEqual(result["batches"], [{"id": "historical-score", "passed": 66}])
            flash = result["effective_routing"]["deepseek-flash"]
            self.assertNotIn("obsolete_category", flash)
            self.assertEqual(flash["compaction"]["routing"], "provisional_only")
            self.assertEqual(result["legacy_evaluation_limitations"], ["legacy"])
            first = copy.deepcopy(result)
            self.assertEqual(report.apply_capability_updates(result, directory), first)

    def test_report_regeneration_keeps_dated_update_and_new_category_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "state/evaluations").mkdir(parents=True)
            (root / "plugins").mkdir()
            (root / "plugins/task-policy.mjs").write_text("// fixture", encoding="utf-8")
            directory = root / "reports/capability_updates"
            directory.mkdir(parents=True)
            (directory / "2026-10-17.json").write_text(json.dumps(self.update()), encoding="utf-8")
            with patch.object(report, "ROOT", root), patch("builtins.print"):
                report.main()
            generated = json.loads((root / "reports/capabilities.json").read_text(encoding="utf-8"))
            self.assertEqual(generated["latest_evaluation_id"], "flash-1017")
            self.assertEqual(generated["recorded_date"], "2026-10-17")
            self.assertFalse(generated["effective_routing"]["deepseek-flash"]["compaction"]["tested_on_snapshot"])
            self.assertIn("2026-10-17", (root / "reports/evaluation.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
