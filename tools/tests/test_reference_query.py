from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "sc2-reference-query.py"


class ReferenceQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        package = self.root / "mods" / "Example.SC2Mod"
        game_data = package / "Base.SC2Data" / "GameData"
        game_data.mkdir(parents=True)
        (game_data / "UnitData.xml").write_text('<Catalog><CUnit id="Marine"/></Catalog>\n', encoding="utf-8")
        (game_data / "ActorData.xml").write_text('<Catalog><CActorUnit id="Marine"/></Catalog>\n', encoding="utf-8")
        strings = package / "zhCN.SC2Data" / "LocalizedData"
        strings.mkdir(parents=True)
        (strings / "GameStrings.txt").write_text("Unit/Name/Marine=陆战队员\n", encoding="utf-8")
        (strings / "LegacyStrings.txt").write_bytes("Unit/Name/Medic=医疗兵\n".encode("cp936"))

    def tearDown(self):
        self.temp.cleanup()

    def run_query(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            check=False,
        )

    def test_find_filters_catalog_family(self):
        result = self.run_query("find", "Marine", "--family", "Unit")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("UnitData.xml", result.stdout)
        self.assertNotIn("ActorData.xml", result.stdout)

    def test_object_returns_exact_family_and_id(self):
        result = self.run_query("object", "Unit:Marine", "--component", "Example")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("UnitData.xml", result.stdout)
        self.assertIn('<CUnit id="Marine"', result.stdout)
        self.assertNotIn("ActorData.xml", result.stdout)

    def test_find_filters_localization_area(self):
        result = self.run_query("find", "陆战队员", "--area", "zhcn")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("GameStrings.txt", result.stdout)
        self.assertNotIn("UnitData.xml", result.stdout)

    def test_find_legacy_chinese_encoding(self):
        result = self.run_query("find", "医疗兵", "--area", "zhcn")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("LegacyStrings.txt", result.stdout)

    def test_components_lists_package_and_areas(self):
        result = self.run_query("components")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("mods/Example.SC2Mod", result.stdout)
        self.assertIn("gamedata,zhcn", result.stdout)
        self.assertIn("components: 1", result.stdout)

    def test_no_match_has_distinct_exit_code(self):
        result = self.run_query("find", "DoesNotExist")
        self.assertEqual(1, result.returncode)
        self.assertIn("matches: 0", result.stdout)

    def test_long_line_keeps_match_and_bounds_output(self):
        path = self.root / "mods" / "Example.SC2Mod" / "Base.SC2Data" / "GameData" / "EffectData.xml"
        path.write_text("x" * 1000 + "Needle" + "y" * 1000 + "\n", encoding="utf-8")
        result = self.run_query("find", "Needle", "--family", "Effect")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Needle", result.stdout)
        self.assertLess(len(result.stdout), 600)


if __name__ == "__main__":
    unittest.main()
