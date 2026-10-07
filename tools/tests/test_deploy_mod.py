from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location("deploy_mod_tool", TOOLS_DIR / "deploy-mod.py")
assert SPEC is not None and SPEC.loader is not None
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class DeploymentSafetyTests(unittest.TestCase):
    @patch.object(DEPLOY, "find_project_mods")
    def test_default_source_uses_shared_project_discovery(self, find_project_mods) -> None:
        expected = [Path("E:/Games/StarCraft II/Mods/Campaign.SC2Mod")]
        find_project_mods.return_value = expected

        self.assertEqual(DEPLOY.find_local_mods(), expected)
        find_project_mods.assert_called_once_with(DEPLOY.REPO_ROOT, None)

    @patch.object(Path, "is_dir", autospec=True, return_value=True)
    @patch.object(DEPLOY.shutil, "copytree")
    def test_same_source_and_target_is_a_noop(self, copytree, _is_dir) -> None:
        source = Path("E:/Games/StarCraft II/Mods/Campaign.SC2Mod")
        with redirect_stdout(io.StringIO()):
            result = DEPLOY.deploy_mod(source, source.parent)
        self.assertEqual(result, source)
        copytree.assert_not_called()

    @patch.object(Path, "is_dir", autospec=True, return_value=True)
    @patch.object(DEPLOY.shutil, "copytree")
    def test_dry_run_does_not_copy(self, copytree, _is_dir) -> None:
        source = Path("E:/Workspace/Campaign.SC2Mod")
        target = Path("E:/Games/StarCraft II/Mods")
        with redirect_stdout(io.StringIO()):
            result = DEPLOY.deploy_mod(source, target, clean=True, dry_run=True)
        self.assertEqual(result, target / source.name)
        copytree.assert_not_called()

    def test_copy_preserves_generated_library_in_source_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "workspace" / "Campaign.SC2Mod"
            base_data = source / "Base.SC2Data"
            base_data.mkdir(parents=True)
            generated = base_data / "Lib12345678.galaxy"
            original = (
                "// Custom Script: ScriptBlock\n"
                "//--------------------------------------------------------------------------------------------------\n"
                "editor generated body\nvoid lib12345678_Init() {}\n"
            )
            generated.write_text(original, encoding="utf-8")
            generated_before = generated.read_bytes()
            (root / "workspace" / "Campaign_ScriptBlock.galaxy").write_text(
                "replacement that must not be injected", encoding="utf-8"
            )
            target = root / "mods"
            target.mkdir()
            with patch.object(DEPLOY, "REPO_ROOT", root / "workspace"):
                with redirect_stdout(io.StringIO()):
                    destination = DEPLOY.deploy_mod(source, target)
            self.assertEqual(generated.read_bytes(), generated_before)
            self.assertEqual(
                (destination / "Base.SC2Data" / generated.name).read_bytes(),
                generated_before,
            )


if __name__ == "__main__":
    unittest.main()
