from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "refresh-sc2-reference.py"


class RefreshReferenceTests(unittest.TestCase):
    def test_check_apply_and_recheck(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {name: root / name for name in ("mods", "campaigns", "CM")}
            for directory in sources.values():
                directory.mkdir()
            source_file = sources["mods"] / "Example.SC2Mod" / "Base.SC2Data" / "GameData" / "UnitData.xml"
            source_file.parent.mkdir(parents=True)
            source_file.write_text('<Catalog><CUnit id="Marine"/></Catalog>', encoding="utf-8")
            target = root / "snapshot"
            target.mkdir()
            (target / "README.md").write_text(
                "本次提取覆盖 0 个组件包、0 个源文件，共 0 字节。\n", encoding="utf-8"
            )
            (target / "obsolete.txt").write_text("old", encoding="utf-8")
            command = [
                sys.executable, str(SCRIPT),
                "--mods", str(sources["mods"]),
                "--campaigns", str(sources["campaigns"]),
                "--cm", str(sources["CM"]),
                "--target", str(target),
            ]
            self.assertEqual(1, subprocess.run(command, capture_output=True).returncode)
            self.assertEqual(0, subprocess.run([*command, "--apply"], capture_output=True).returncode)
            self.assertEqual(source_file.read_bytes(), (target / "mods" / "Example.SC2Mod" / "Base.SC2Data" / "GameData" / "UnitData.xml").read_bytes())
            self.assertFalse((target / "obsolete.txt").exists())
            self.assertEqual(0, subprocess.run(command, capture_output=True).returncode)
            self.assertEqual(1, len(list(root.glob(".sc2-reference-backup-*"))))


if __name__ == "__main__":
    unittest.main()
