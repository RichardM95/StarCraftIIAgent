import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sc2_talent_export import Study, write_workbook
from sc2_triggers import Document
from sc2_migrate import ComponentLoader
from sc2_migrate_catalog import Catalog


class ExportTests(unittest.TestCase):
    def test_bom_equals_and_catalog_inheritance(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".runtime") as tmp:
            root = Path(tmp) / "Example.SC2Mod"
            data = root / "Base.SC2Data/GameData"
            data.mkdir(parents=True)
            (data / "UserData.xml").write_text(
                '<Catalog><CUser id="Base"><Fields Id="Max" Type="Int"/>'
                '<Instances Id="X"><Int Int="5"><Field Id="Max"/></Int></Instances></CUser>'
                '<CUser id="Child" parent="Base"><Instances Id="X"><String String="Hi">'
                '<Field Id="Name"/></String></Instances></CUser></Catalog>', encoding="utf-8")
            locale = root / "enUS.SC2Data/LocalizedData"
            locale.mkdir(parents=True)
            (locale / "GameStrings.txt").write_text("D=a=b<c/>\n", encoding="utf-8-sig")
            source, files, texts, inputs = ComponentLoader().read(root)
            self.assertEqual(texts[("enUS", "GameStrings.txt", "D")]["value"], "a=b<c/>")
            study = self.study("<TriggerData/>")
            study.catalog = Catalog([source], files)
            study.tables = {"Child": study.catalog.effective("User", "Child")}
            rows = study.user_rows({"tables": [{"id": "Child", "roles": {"name": "Name", "max": "Max"}}]})
            self.assertEqual(rows[0]["max"], "5")
            self.assertTrue(rows[0]["field_sources"])

    def test_invalid_rarity_and_missing_language_are_diagnostics(self):
        study = self.study("<TriggerData/>")
        study.user_rows = lambda mapping: [{"id": "a", "rarity": "bad", "name_key": "K"}]
        study.trigger_rows = lambda mapping: []
        study.tables = {}
        study.texts = {("enUS", "GameStrings.txt", "K"): {"value": "A"}}
        study.catalog = type("Catalog", (), {"objects": {}, "diagnostics": []})()
        rows = study.rows({})
        self.assertEqual(rows[0]["enUS_name"], "A")
        self.assertEqual(rows[0]["zhCN_name"], "")
        self.assertIn("invalid_rarity", {p["code"] for p in study.problems})

    def study(self, xml):
        study = Study.__new__(Study)
        study.problems = []
        study.documents = [Document(Path("Example.SC2Mod/Triggers"), xml.encode(), names={}, localized_names={})]
        return study

    def registration(self, value, ident="ROW", name="same", extra=""):
        return f"""<Element Type="FunctionCall" Id="{ident}">
        <FunctionDef Type="FunctionDef" Library="L" Id="REG"/>
        <Parameter Type="Param" Id="{ident}I"/><Parameter Type="Param" Id="{ident}N"/></Element>
        <Element Type="Param" Id="{ident}I"><ParameterDef Id="I"/><Value>{value}</Value></Element>
        <Element Type="Param" Id="{ident}N"><ParameterDef Id="N"/><Value>{name}</Value>{extra}</Element>"""

    def test_registrations_names_do_not_merge_and_dynamic_fields_reported(self):
        xml = '<TriggerData><Library Id="L">' + self.registration("a") + self.registration("b", "B") + self.registration(
            "c", "C", extra='<FunctionCall Type="FunctionCall" Id="DYNAMIC"/>') + '</Library></TriggerData>'
        study = self.study(xml)
        rows = study.trigger_rows({"triggers": [{"library": "L", "function": "REG", "roles": {"id": "I", "name": "N"}}]})
        self.assertEqual([r["id"] for r in rows], ["a", "b", "c"])
        self.assertEqual(rows[0]["name"], rows[1]["name"])
        self.assertEqual(rows[0]["locations"][0]["element"], "ROW")
        self.assertTrue(any(d["code"] == "dynamic_trigger_value" for d in study.problems))

    def test_gui_external_text_parameter(self):
        xml = '<TriggerData><Library Id="L">' + self.registration("a", name="") + '</Library></TriggerData>'
        xml = xml.replace('<Value></Value>', '<ValueType Type="text"/>')
        study = self.study(xml)
        rows = study.trigger_rows({"triggers": [{"library": "L", "function": "REG", "roles": {"id": "I", "name_key": "N"}}]})
        self.assertEqual(rows[0]["name_key"], "Param/Value/lib_L_ROWN")

    def test_array_index_and_variable_filter(self):
        xml = """<TriggerData><Library Id="L">
        <Element Type="FunctionCall" Id="C"><FunctionDef Type="FunctionDef" Library="Ntve" Id="SET"/>
        <Parameter Type="Param" Id="P"/><Parameter Type="Param" Id="V"/></Element>
        <Element Type="Param" Id="P"><ParameterDef Id="TARGET"/>
        <Variable Type="Variable" Id="ARRAY"/><Array Type="Param" Id="INDEX"/></Element>
        <Element Type="Param" Id="INDEX"><Value>3</Value></Element>
        <Element Type="Param" Id="V"><ParameterDef Id="VALUE"/><Value>Example</Value></Element>
        </Library></TriggerData>"""
        spec = {"library": "Ntve", "function": "SET", "array_id": "T", "variable": "ARRAY",
                "roles": {"array_index": {"parameter": "TARGET", "array_index": True}, "name": "VALUE"}}
        study = self.study(xml)
        self.assertEqual(study.trigger_rows({"triggers": [spec]})[0]["id"], "T[3]")
        spec["variable"] = "OTHER"
        self.assertEqual(study.trigger_rows({"triggers": [spec]}), [])
        spec["variable"] = "ARRAY"
        study = self.study(xml.replace("<Value>3</Value>", '<Variable Id="DYNAMIC"/>'))
        self.assertEqual(study.trigger_rows({"triggers": [spec]}), [])
        self.assertTrue(study.problems)

    def test_mixed_unique_upgrade_merges(self):
        study = self.study("<TriggerData/>")
        study.user_rows = lambda mapping: [{"id": "data", "upgrade": "U", "raw": {}, "locations": [], "status": "availability_unconfirmed"}]
        study.trigger_rows = lambda mapping: [{"id": "gui", "upgrade": "U", "locations": [{"element": "C"}]}]
        study.tables = {}
        study.texts = {}
        study.catalog = type("Catalog", (), {"objects": {("Upgrade", "U"): []}, "diagnostics": []})()
        rows = study.rows({"merge_on": "upgrade"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "data")
        self.assertEqual(rows[0]["locations"], [{"element": "C"}])

    def test_text_and_safe_workbook(self):
        from openpyxl import load_workbook
        study = self.study("<TriggerData/>")
        study.texts = {("enUS", "GameStrings.txt", "D"): {"value": "=a=b< c />"}}
        self.assertEqual(study.text("enUS", "D", "x"), "=a=b< c />")
        self.assertEqual(study.text("zhCN", "D", "x"), "")
        study.mod = Path("Example.SC2Mod")
        study.sources = []
        study.fingerprint = "test"
        rows = [{"id": "=1+1", "zhCN_name": "中文", "enUS_description": "=a=b< c />", "status": "availability_unconfirmed"}]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".runtime") as tmp:
            target = Path(tmp) / "out.xlsx"
            write_workbook(target, study, rows, {})
            book = load_workbook(target)
            self.assertEqual(book.sheetnames, ["天赋清单"])
            self.assertEqual(book.active["I2"].value, "=1+1")
            self.assertEqual(book.active["I2"].data_type, "s")
            book.close()
            before = target.read_bytes()
            with patch("openpyxl.workbook.workbook.Workbook.save", side_effect=OSError("failed")):
                with self.assertRaises(OSError):
                    write_workbook(target, study, rows, {})
            self.assertEqual(target.read_bytes(), before)

    def test_render_static_ref_and_preserve_adjacent_text_on_failure(self):
        from sc2_talent_text import render_description
        node = {"@tag": "DamageResponse", "attributes": {"ModifyFraction": "1.25"}}
        root = {"attributes": {}, "children": [node]}
        catalog = type("Catalog", (), {"effective": lambda self, family, ident: root})()
        counts = {"resolved": 0, "unresolved": 0}
        problems = []
        result = render_description(
            '<c val="abc"><d ref="(Behavior,Kit@Wraith,DamageResponse.ModifyFraction-1)*100" precision="2"/>%</c>'
            '<n/>A<d ref="1/0"/>B<d ref="Behavior,X,Missing"/>', catalog, "zhCN", "id", counts,
            lambda code, detail: problems.append(detail))
        self.assertEqual(result, "25.00%\nA数值待确认B数值待确认")
        self.assertEqual(counts, {"resolved": 1, "unresolved": 2})
        self.assertEqual(problems[1]["reference"], '<d ref="Behavior,X,Missing"/>')


if __name__ == "__main__":
    unittest.main()
