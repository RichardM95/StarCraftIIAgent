from __future__ import annotations

import importlib.util
import sys
import unittest
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location(
    "gamestrings_audit_tool",
    TOOLS_DIR / "audit-gamestrings-anchors.py",
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class StringReferenceTests(unittest.TestCase):
    def test_chinese_locale_and_english_default_are_independent(self) -> None:
        with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as folder:
            mod = Path(folder)
            data = mod / "Base.SC2Data" / "GameData"
            data.mkdir(parents=True)
            (data / "UnitData.xml").write_text('<Catalog><CUnit id="Example"><Name value="Unit/Name/Example"/></CUnit></Catalog>', encoding="utf-8")
            for locale in ("enUS", "zhCN"):
                target = mod / f"{locale}.SC2Data" / "LocalizedData"
                target.mkdir(parents=True)
                (target / "GameStrings.txt").write_text("", encoding="utf-8")
                (target / "ObjectStrings.txt").write_text("Unit/Name/Example=示例\n", encoding="utf-8")
            self.assertEqual(len(AUDIT.audit_mod_localization(mod)), 1)
            self.assertEqual(AUDIT.audit_mod_localization(mod, fill=True, locale="zhCN"), [])
            self.assertEqual(len(AUDIT.audit_mod_localization(mod)), 1)
            self.assertEqual((mod / "enUS.SC2Data/LocalizedData/GameStrings.txt").read_text(), "")
    def test_extracts_description_keys(self) -> None:
        text = (
            '<Catalog><CButton id="Example">'
            '<Description value="Button/Description/Example"/>'
            "</CButton></Catalog>"
        )
        self.assertIn(
            "Button/Description/Example",
            AUDIT.extract_string_references(text),
        )

    def test_ignores_literal_description_text(self) -> None:
        text = (
            '<Catalog><CButton id="Example">'
            '<Description value="Literal text"/>'
            "</CButton></Catalog>"
        )
        self.assertEqual(AUDIT.extract_string_references(text), set())


if __name__ == "__main__":
    unittest.main()
