import json
import tempfile
import unittest
from pathlib import Path

from supervisor.manager import TaskSpec
from supervisor.policy import make_policy


class Sc2BridgeContract(unittest.TestCase):
    def test_sc2_profile_adds_request_file_and_keeps_folder_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = TaskSpec(goal="inspect SC2", workspace=temp, acceptance="report", profile="sc2")
            self.assertIn(".sc2-mcp/request.json", spec.allowed_files)

    def test_policy_patch_contains_sc2_plugin_and_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            run = Path(temp) / "run"
            patch = make_policy(run, root, goal="inspect", allowed_files=[".sc2-mcp/request.json"],
                                acceptance="response", profile="sc2",
                                plugin=Path(__file__).resolve().parents[1] / 'plugins/sc2-worker-policy.mjs')
            contract = json.loads((run / "contract.json").read_text(encoding="utf-8"))
            self.assertEqual(contract["profile"], "sc2")
            self.assertTrue((run / "sc2-worker-policy.mjs").is_file())
            self.assertTrue((run / "task-policy.mjs").is_file())
            self.assertIn("sc2-worker-policy.mjs", patch.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
