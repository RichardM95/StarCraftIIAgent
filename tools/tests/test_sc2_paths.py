from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sc2_paths
from sc2_paths import find_project_mods


class ProjectModDiscoveryTests(unittest.TestCase):
    @patch.object(Path, "is_dir", autospec=True)
    def test_explicit_relative_path_is_resolved_from_repo_root(self, is_dir) -> None:
        repo = Path("C:/workspace/agent")
        mod = repo / "mods" / "Example.SC2Mod"
        is_dir.side_effect = lambda path: path.resolve(strict=False) == mod.resolve(strict=False)

        self.assertEqual(
            find_project_mods(repo, "mods/Example.SC2Mod"),
            [mod.resolve()],
        )

    @patch.object(Path, "is_dir", autospec=True, return_value=True)
    @patch.object(sc2_paths, "load_project_config", side_effect=ValueError("invalid config"))
    def test_explicit_path_does_not_require_valid_config(self, _load, _is_dir) -> None:
        repo = Path("C:/workspace/agent")
        explicit = Path("D:/Mods/Example.SC2Mod")
        self.assertEqual(find_project_mods(repo, str(explicit)), [explicit.resolve()])
        _load.assert_not_called()

    @patch.object(Path, "is_dir", autospec=True)
    def test_discovers_sibling_starcraft_install_layout(self, is_dir) -> None:
        parent = Path("C:/Program Files (x86)")
        repo = parent / "StarCraftIIAgent"
        mod = parent / "StarCraft II" / "Mods" / "Campaign.SC2Mod"
        is_dir.side_effect = lambda path: path.resolve(strict=False) == mod.resolve(strict=False)

        self.assertEqual(
            find_project_mods(
                repo,
                primary_name="Campaign.SC2Mod",
                env={},
            ),
            [mod.resolve()],
        )

    @patch.object(Path, "is_dir", autospec=True)
    def test_environment_path_takes_part_in_discovery(self, is_dir) -> None:
        repo = Path("C:/workspace/agent")
        mods_root = Path("D:/custom-mods")
        mod = mods_root / "Campaign.SC2Mod"
        is_dir.side_effect = lambda path: path.resolve(strict=False) == mod.resolve(strict=False)

        self.assertEqual(
            find_project_mods(
                repo,
                primary_name="Campaign.SC2Mod",
                env={"SC2_MODS_PATH": str(mods_root)},
                config={},
            ),
            [mod.resolve()],
        )

    @patch.object(Path, "is_dir", autospec=True)
    def test_configuration_supplies_relative_mods_path_and_primary_mod(self, is_dir) -> None:
        repo = Path("C:/workspace/StarCraftIIAgent")
        mod = Path("C:/workspace/StarCraft II/Mods/Campaign.SC2Mod")
        is_dir.side_effect = lambda path: path.resolve(strict=False) == mod.resolve(strict=False)

        self.assertEqual(
            find_project_mods(
                repo,
                env={},
                config={
                    "paths": {"mods_dir": "../StarCraft II/Mods"},
                    "project": {"primary_mod": "Campaign.SC2Mod"},
                },
            ),
            [mod.resolve()],
        )

    @patch.object(Path, "is_dir", autospec=True, return_value=False)
    def test_missing_explicit_path_does_not_fall_back(self, _is_dir) -> None:
        repo = Path("C:/workspace/agent")
        self.assertEqual(
            find_project_mods(repo, "missing.SC2Mod", env={}),
            [],
        )

    def test_no_config_does_not_guess_a_project(self) -> None:
        self.assertEqual(
            find_project_mods(Path("C:/workspace/agent"), env={}, config={}),
            [],
        )

    @patch.object(Path, "is_dir", autospec=True, return_value=True)
    def test_configured_primary_cannot_escape_mods_root(self, _is_dir) -> None:
        repo = Path("C:/workspace/agent")
        self.assertEqual(
            find_project_mods(
                repo,
                env={},
                config={
                    "paths": {"mods_dir": "mods"},
                    "project": {"primary_mod": "../Outside.SC2Mod"},
                },
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
