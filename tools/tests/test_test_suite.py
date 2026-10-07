from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location("test_suite_tool", TOOLS_DIR / "test-suite.py")
assert SPEC is not None and SPEC.loader is not None
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)


class DependencyValidationTests(unittest.TestCase):
    def test_reads_dependency_defaults_and_exclusions(self) -> None:
        include, exclusions = SUITE.validation_settings(
            {
                "validation": {
                    "include_dependencies": True,
                    "exclude_mods": ["Heros.SC2Mod"],
                }
            }
        )
        self.assertTrue(include)
        self.assertEqual(exclusions, {"heros.sc2mod"})

    def test_invalid_exclusion_type_does_not_crash_preflight(self) -> None:
        include, exclusions = SUITE.validation_settings(
            {
                "validation": {
                    "include_dependencies": True,
                    "exclude_mods": 42,
                }
            }
        )
        self.assertTrue(include)
        self.assertEqual(exclusions, set())

    @patch.object(SUITE, "build_dependency_graph")
    @patch.object(SUITE, "find_project_mods")
    def test_workspace_copy_keeps_installed_dependencies(self, find_mods, graph):
        source = Path("C:/workspace/source/Main.SC2Mod").resolve()
        installed = Path("D:/StarCraft II/Mods").resolve()
        find_mods.return_value = [source]
        graph.return_value = {"nodes": {}, "missing": [], "errors": []}
        SUITE.dependency_validation_targets(source, {
            "paths": {"mods_dir": str(installed)},
            "project": {"source_mode": "workspace_copy", "source_mod": str(source)}}, set())
        graph.assert_called_once_with(source, installed)
        graph.reset_mock()
        other = Path("E:/OtherMods/Other.SC2Mod").resolve()
        targets, problems = SUITE.dependency_validation_targets(other, {
            "paths": {"mods_dir": str(installed)}}, set())
        self.assertEqual(targets, [])
        self.assertIn("--mods-dir", problems[0])
        graph.assert_not_called()
        with patch.object(Path, "is_dir", return_value=True):
            SUITE.dependency_validation_targets(other, {}, set(), str(other.parent))
        graph.assert_called_once_with(other, other.parent.resolve())

    @patch.object(SUITE, "build_dependency_graph")
    @patch.object(SUITE, "resolve_configured_path")
    def test_excludes_named_dependency(self, resolve_path, build_graph) -> None:
        primary = Path("E:/Games/StarCraft II/Mods/Main.SC2Mod")
        keep = Path("E:/Games/StarCraft II/Mods/Keep.SC2Mod")
        skip = Path("E:/Games/StarCraft II/Mods/Heros.SC2Mod")
        resolve_path.return_value = primary.parent
        build_graph.return_value = {
            "nodes": {
                str(primary.resolve(strict=False)).casefold(): {"path": str(primary)},
                str(keep.resolve(strict=False)).casefold(): {"path": str(keep)},
                str(skip.resolve(strict=False)).casefold(): {"path": str(skip)},
            },
            "missing": [],
            "errors": [],
        }

        targets, problems = SUITE.dependency_validation_targets(
            primary,
            {"paths": {"mods_dir": str(primary.parent)}},
            {"heros.sc2mod"},
        )

        self.assertEqual(targets, [keep])
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
