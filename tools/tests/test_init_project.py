from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location("init_project", TOOLS_DIR / "init-project.py")
assert SPEC is not None and SPEC.loader is not None
INIT_PROJECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INIT_PROJECT)


class ProjectLayoutTests(unittest.TestCase):
    def test_infers_standard_sc2_layout_from_primary_mod(self) -> None:
        primary = Path("E:/Games/StarCraft II/Mods/Campaign.SC2Mod")
        layout = INIT_PROJECT.infer_project_layout(primary)
        self.assertEqual(layout["mods_dir"], Path("E:/Games/StarCraft II/Mods"))
        self.assertEqual(layout["sc2_install_dir"], Path("E:/Games/StarCraft II"))
        self.assertEqual(
            layout["campaign_maps_dir"],
            Path("E:/Games/StarCraft II/Maps/Campaign"),
        )

    def test_requires_override_for_nonstandard_mods_parent(self) -> None:
        primary = Path("E:/Projects/Components/Campaign.SC2Mod")
        with self.assertRaises(ValueError):
            INIT_PROJECT.infer_project_layout(primary)

    def test_finds_mods_ancestor_for_nested_primary_mod(self) -> None:
        primary = Path("E:/Games/StarCraft II/Mods/Campaigns/Campaign.SC2Mod")
        layout = INIT_PROJECT.infer_project_layout(primary)
        self.assertEqual(layout["mods_dir"], Path("E:/Games/StarCraft II/Mods"))
        self.assertEqual(
            INIT_PROJECT.primary_mod_config_value(primary, layout["mods_dir"]),
            "Campaigns/Campaign.SC2Mod",
        )

    def test_rejects_primary_mod_outside_configured_mods_dir(self) -> None:
        with self.assertRaises(ValueError):
            INIT_PROJECT.primary_mod_config_value(
                Path("E:/Projects/Campaign.SC2Mod"),
                Path("E:/Games/StarCraft II/Mods"),
            )

    @patch.object(INIT_PROJECT.os.path, "relpath", side_effect=ValueError("different drive"))
    def test_cross_drive_path_falls_back_to_absolute(self, _relpath) -> None:
        value = INIT_PROJECT.config_path_value(Path("D:/Games/StarCraft II"))
        self.assertTrue(Path(value).is_absolute())

    @patch.object(INIT_PROJECT, "load_project_config", side_effect=ValueError("invalid JSON"))
    def test_invalid_existing_config_is_not_silently_replaced(self, _load) -> None:
        layout = {
            "workspace_dir": INIT_PROJECT.REPO_ROOT,
            "sc2_install_dir": Path("E:/Games/StarCraft II"),
            "mods_dir": Path("E:/Games/StarCraft II/Mods"),
            "campaign_maps_dir": Path("E:/Games/StarCraft II/Maps/Campaign"),
        }
        with self.assertRaises(ValueError):
            INIT_PROJECT.build_config(
                Path("E:/Games/StarCraft II/Mods/Campaign.SC2Mod"),
                layout,
            )

    @patch.object(
        INIT_PROJECT,
        "load_project_config",
        return_value={
            "validation": {
                "include_dependencies": True,
                "exclude_mods": ["Heros.SC2Mod"],
            }
        },
    )
    def test_preserves_validation_policy(self, _load) -> None:
        layout = {
            "workspace_dir": INIT_PROJECT.REPO_ROOT,
            "sc2_install_dir": Path("E:/Games/StarCraft II"),
            "mods_dir": Path("E:/Games/StarCraft II/Mods"),
            "campaign_maps_dir": Path("E:/Games/StarCraft II/Maps/Campaign"),
        }
        config = INIT_PROJECT.build_config(
            Path("E:/Games/StarCraft II/Mods/Campaign.SC2Mod"),
            layout,
        )
        self.assertEqual(
            config["validation"],
            {
                "include_dependencies": True,
                "exclude_mods": ["Heros.SC2Mod"],
            },
        )
        self.assertEqual(config["project"]["source_mode"], "in_place")


if __name__ == "__main__":
    unittest.main()
