from __future__ import annotations

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"

import importlib.util
import sys
import unittest
import tempfile
from unittest.mock import patch
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
    def test_expands_defaults_and_parent_templates_for_each_object(self):
        text = '''<Catalog>
          <CArmyCategory default="1"><Description value="Button/Tooltip/##id##"/></CArmyCategory>
          <CArmyCategory id="Marine"/>
          <CArmyCategory id="Parent"><Description value="Unit/Tooltip/##id##"/></CArmyCategory>
          <CArmyCategory id="Child" parent="Parent"/>
          <CArmyCategory id="Override"><Description value="Button/Tooltip/Specific"/></CArmyCategory>
        </Catalog>'''
        self.assertEqual(AUDIT.extract_string_references(text), {
            'Button/Tooltip/Marine', 'Unit/Tooltip/Parent',
            'Unit/Tooltip/Child', 'Button/Tooltip/Specific'})
        self.assertEqual(AUDIT.extract_string_references('<Catalog><CButton default="1"><Tooltip value="Button/Tooltip/##id##"/></CButton></Catalog>'), set())

    def test_dependency_strings_and_cross_file_inheritance_do_not_need_fill(self):
        with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as folder:
            mods = Path(folder) / 'Mods'
            dep, target = mods / 'Dep.SC2Mod', mods / 'Main.SC2Mod'
            for mod in (dep, target):
                (mod / 'Base.SC2Data/GameData').mkdir(parents=True)
                (mod / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
                (mod / 'DocumentInfo').write_text('<DocInfo/>')
                for locale in ('enUS', 'zhCN'):
                    strings = mod / f'{locale}.SC2Data/LocalizedData/GameStrings.txt'
                    strings.parent.mkdir(parents=True)
                    strings.write_text('')
            (target / 'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Dep.SC2Mod</Value></Dependencies></DocInfo>')
            (dep / 'Base.SC2Data/GameData/ArmyCategoryData.xml').write_text('<Catalog><CArmyCategory id="Parent"><Description value="Button/Tooltip/##id##"/></CArmyCategory></Catalog>')
            (dep / 'Base.SC2Data/GameData/BehaviorData.xml').write_text('<Catalog><CBehaviorBuff default="1"><Name value="Behavior/Name/##id##"/></CBehaviorBuff><CBehaviorBuff id="Existing"><Name value="Behavior/Name/Existing"/></CBehaviorBuff></Catalog>')
            (target / 'Base.SC2Data/GameData/BehaviorData.xml').write_text('<Catalog><CBehaviorBuff id="Existing"/><CBehaviorBuff id="Internal"/></Catalog>')
            (target / 'Base.SC2Data/GameData/ArmyCategoryData.xml').write_text('<Catalog><CArmyCategory id="Marine" parent="Parent"/></Catalog>')
            (dep / 'zhCN.SC2Data/LocalizedData/GameStrings.txt').write_text('Button/Tooltip/Marine=Marine\n')
            self.assertEqual(AUDIT.audit_mod_localization(target, locale='zhCN'), [])
            self.assertEqual(AUDIT.audit_mod_localization(target, fill=True, locale='zhCN'), [])
            self.assertEqual((target / 'zhCN.SC2Data/LocalizedData/GameStrings.txt').read_bytes(), b'')
            self.assertIn('Button/Tooltip/Marine', str(AUDIT.audit_mod_localization(target, locale='enUS')))
            (target / 'Base.SC2Data/GameData/DefaultData.xml').write_text('<Catalog><CArmyCategory default="1"><Description value="Unit/Tooltip/##id##"/></CArmyCategory><CArmyCategory id="Missing"/></Catalog>')
            self.assertIn('Unit/Tooltip/Missing', str(AUDIT.audit_mod_localization(target, locale='zhCN')))

    def test_incomplete_dependency_evidence_is_not_ignored(self):
        with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as folder:
            mod = Path(folder) / 'Mods/Main.SC2Mod'
            (mod / 'Base.SC2Data/GameData').mkdir(parents=True)
            (mod / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
            (mod / 'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Missing.SC2Mod</Value></Dependencies></DocInfo>')
            strings = mod / 'zhCN.SC2Data/LocalizedData/GameStrings.txt'
            strings.parent.mkdir(parents=True)
            strings.write_text('')
            self.assertIn('missing dependency', str(AUDIT.audit_mod_localization(mod, locale='zhCN')))

    def test_unavailable_locale_evidence_blocks_fill_instead_of_claiming_missing(self):
        with tempfile.TemporaryDirectory(dir=TOOLS_DIR) as folder:
            mod = Path(folder)
            data = mod / 'Base.SC2Data/GameData'
            data.mkdir(parents=True)
            (data / 'ButtonData.xml').write_text('<Catalog><CButton id="Marine"><Tooltip value="Button/Tooltip/##id##"/></CButton></Catalog>')
            strings = mod / 'enUS.SC2Data/LocalizedData/GameStrings.txt'
            strings.parent.mkdir(parents=True)
            strings.write_text('')
            (strings.parent / 'ObjectStrings.txt').write_text('Button/Tooltip/Marine=Text\n')
            metadata = (mod, {'enus.sc2data/localizeddata/gamestrings.txt'}, {'enUS': False})
            with patch.object(AUDIT, 'localization_sources', return_value=[(mod, metadata)]):
                issues = AUDIT.audit_mod_localization(mod, fill=True)
            self.assertIn('Localization audit unconfirmed: enUS', str(issues))
            self.assertNotIn('Missing GameStrings', str(issues))
            self.assertEqual(strings.read_bytes(), b'')

    def test_inheritance_cycle_is_an_error_not_a_clean_audit(self):
        text = '<Catalog><CUnit id="A" parent="B"/><CUnit id="B" parent="A"/></Catalog>'
        with self.assertRaisesRegex(ValueError, 'inheritance cycle'):
            AUDIT.extract_string_references(text)

    def test_later_scalar_override_does_not_require_obsolete_anchor(self):
        text = '<Catalog><CButton id="A"><Tooltip value="Button/Tooltip/Old"/></CButton><CButton id="A"><Tooltip value="Button/Tooltip/Current"/></CButton></Catalog>'
        self.assertEqual(AUDIT.extract_string_references(text), {'Button/Tooltip/Current'})

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
