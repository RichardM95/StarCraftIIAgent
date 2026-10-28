"""合成临时目录测试：scripts/validate_skyshield_copy.py 的保护边界。

不访问正式钥石地图；所有 fixture 在 tempfile.TemporaryDirectory 中生成。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from sc2_mcp.storage import snapshot  # noqa: E402

import validate_skyshield_copy as vsc  # noqa: E402

OBJECTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Objects>
  <ObjectUnit Id="Marine">
    <Field Name="LifeMax" Value="100"/>
  </ObjectUnit>
  <ObjectUnit Id="Zergling">
    <Field Name="LifeMax" Value="35"/>
  </ObjectUnit>
  <ObjectDoodad Id="DoodadA">
    <Field Name="Rotation" Value="0"/>
  </ObjectDoodad>
</Objects>
"""


def write(root: Path, relative: str, data) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    target.write_bytes(data)


def codes(result: dict) -> set[str]:
    return {violation["code"] for violation in result["violations"]}


class ValidateCopyTests(unittest.TestCase):
    def build(self) -> tuple[tempfile.TemporaryDirectory, Path, Path, dict[str, str]]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        source = Path(tmp.name) / "source"
        candidate = Path(tmp.name) / "candidate"
        write(source, "DocumentInfo", "<DocumentInfo/>")
        write(source, "DocumentHeader", "<DocumentHeader/>")
        write(source, "MapInfo", "<MapInfo/>")
        write(source, "MapScript.galaxy", "void main(){}\n")
        write(source, "t3HeightMap", b"\x00\x01\x02\x03")
        write(source, "t3SyncHeightMap", b"\x04\x05")
        write(source, "t3SyncCliffLevel", b"\x06")
        write(source, "t3CellFlags", b"\x07")
        write(source, "CellAttribute_0", b"\x10\x20")
        write(source, "Regions", b"\x00\x00")
        write(source, "CameraData", b"\x00\x01")
        write(source, "BankList", "<BankList/>")
        write(source, "UnitData", b"\xaa\xbb")
        write(source, "EffectData", b"\xaa\xbc")
        write(source, "WeaponData", b"\xaa\xbd")
        write(source, "BehaviorData", b"\xaa\xbe")
        write(source, "AbilData", b"\xaa\xbf")
        write(source, "Objects", OBJECTS_XML)
        write(source, "Localization.txt", "KEY=value\n")
        baseline = snapshot(source)
        shutil.copytree(source, candidate)
        return tmp, source, candidate, baseline

    # -- 合法场景 ---------------------------------------------------------
    def test_clean_copy_passes(self):
        _tmp, source, candidate, baseline = self.build()
        result = vsc.validate_copy(source, candidate, baseline, set())
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["violations"], [])

    def test_allowed_scene_change_passes(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Localization.txt", "KEY=changed\n")
        result = vsc.validate_copy(source, candidate, baseline, {"Localization.txt"})
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["changed_files"]), 1)
        change = result["changed_files"][0]
        self.assertEqual(change["path"], "Localization.txt")
        self.assertEqual(change["kind"], "modified")
        self.assertTrue(change["allowed"])
        self.assertFalse(change["protected"])

    def test_allowed_doodad_change_passes(self):
        _tmp, source, candidate, baseline = self.build()
        doodad_changed = OBJECTS_XML.replace('Value="0"', 'Value="90"')
        write(candidate, "Objects", doodad_changed)
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["objects"]["non_doodad_changed"])
        self.assertEqual(result["objects"]["duplicate_ids"], [])

    def test_objects_formatting_and_attr_order_is_normalised(self):
        _tmp, source, candidate, baseline = self.build()
        reordered = """<?xml version="1.0" encoding="UTF-8"?>
<Objects>
    <ObjectUnit Id="Marine">
        <Field Value="100" Name="LifeMax"></Field>
    </ObjectUnit>
    <ObjectUnit Id="Zergling">
        <Field Name="LifeMax" Value="35"/>
    </ObjectUnit>
    <ObjectDoodad Id="DoodadA"><Field Name="Rotation" Value="0"/></ObjectDoodad>
</Objects>
"""
        write(candidate, "Objects", reordered)
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["objects"]["non_doodad_changed"])

    def test_allowed_added_and_deleted_files_pass(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Extra.txt", "new\n")
        (candidate / "Localization.txt").unlink()
        result = vsc.validate_copy(
            source, candidate, baseline, {"Extra.txt", "Localization.txt"}
        )
        self.assertTrue(result["passed"], result)
        kinds = {change["path"]: change["kind"] for change in result["changed_files"]}
        self.assertEqual(kinds["Extra.txt"], "added")
        self.assertEqual(kinds["Localization.txt"], "deleted")

    # -- 源图变化 ---------------------------------------------------------
    def test_source_changed_fails(self):
        _tmp, source, candidate, baseline = self.build()
        write(source, "MapInfo", "<MapInfo>changed</MapInfo>")
        result = vsc.validate_copy(source, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertFalse(result["source_unchanged"])
        self.assertIn("source_changed", codes(result))

    def test_source_missing_fails(self):
        tmp, _source, candidate, baseline = self.build()
        missing = Path(tmp.name) / "does-not-exist"
        result = vsc.validate_copy(missing, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertFalse(result["source_unchanged"])
        self.assertIn("source_missing", codes(result))

    def test_source_empty_fails(self):
        tmp, _source, candidate, baseline = self.build()
        empty = Path(tmp.name) / "empty-source"
        empty.mkdir()
        result = vsc.validate_copy(empty, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertFalse(result["source_unchanged"])
        self.assertIn("source_empty", codes(result))

    # -- 未授权 / 受保护 --------------------------------------------------
    def test_unauthorized_change_fails(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Localization.txt", "KEY=tampered\n")
        result = vsc.validate_copy(source, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertIn("unauthorized_change", codes(result))

    def test_unauthorized_added_file_fails(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Extra.txt", "new\n")
        result = vsc.validate_copy(source, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertIn("unauthorized_change", codes(result))

    def test_protected_change_rejected_even_if_allowed(self):
        protected = [
            "t3HeightMap",
            "t3SyncHeightMap",
            "t3SyncCliffLevel",
            "t3CellFlags",
            "CellAttribute_0",
            "Regions",
            "CameraData",
            "BankList",
            "DocumentInfo",
            "DocumentHeader",
            "MapInfo",
            "MapScript.galaxy",
            "UnitData",
            "EffectData",
            "WeaponData",
            "BehaviorData",
            "AbilData",
        ]
        for rel in protected:
            with self.subTest(path=rel):
                _tmp, source, candidate, baseline = self.build()
                write(candidate, rel, b"\xff\xff\xff")
                result = vsc.validate_copy(source, candidate, baseline, {rel})
                self.assertFalse(result["passed"], rel)
                self.assertIn("protected_change", codes(result), rel)

    def test_protected_deletion_rejected_even_if_allowed(self):
        _tmp, source, candidate, baseline = self.build()
        (candidate / "Regions").unlink()
        result = vsc.validate_copy(source, candidate, baseline, {"Regions"})
        self.assertFalse(result["passed"])
        self.assertIn("protected_change", codes(result))

    # -- Objects ----------------------------------------------------------
    def test_non_doodad_changed_rejected_even_if_allowed(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Objects", OBJECTS_XML.replace('Value="100"', 'Value="120"'))
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertFalse(result["passed"])
        self.assertTrue(result["objects"]["non_doodad_changed"])
        self.assertIn("non_doodad_changed", codes(result))

    def test_non_doodad_reordered_rejected(self):
        _tmp, source, candidate, baseline = self.build()
        reordered = """<?xml version="1.0" encoding="UTF-8"?>
<Objects>
  <ObjectUnit Id="Zergling">
    <Field Name="LifeMax" Value="35"/>
  </ObjectUnit>
  <ObjectDoodad Id="DoodadA">
    <Field Name="Rotation" Value="0"/>
  </ObjectDoodad>
  <ObjectUnit Id="Marine">
    <Field Name="LifeMax" Value="100"/>
  </ObjectUnit>
</Objects>
"""
        write(candidate, "Objects", reordered)
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertFalse(result["passed"])
        self.assertIn("non_doodad_changed", codes(result))

    def test_duplicate_object_id_rejected(self):
        _tmp, source, candidate, baseline = self.build()
        duplicated = OBJECTS_XML.replace(
            "</Objects>",
            '  <ObjectDoodad Id="DoodadA">\n    <Field Name="Rotation" Value="45"/>\n  </ObjectDoodad>\n</Objects>',
        )
        write(candidate, "Objects", duplicated)
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertFalse(result["passed"])
        self.assertIn("duplicate_object_id", codes(result))
        self.assertEqual(result["objects"]["duplicate_ids"][0]["id"], "DoodadA")

    def test_objects_deleted_rejected_even_if_allowed(self):
        _tmp, source, candidate, baseline = self.build()
        (candidate / "Objects").unlink()
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertFalse(result["passed"])
        self.assertIn("objects_structure_change", codes(result))

    def test_unparsable_objects_fails_closed(self):
        _tmp, source, candidate, baseline = self.build()
        write(candidate, "Objects", b"\x00\x01\x02not-xml")
        result = vsc.validate_copy(source, candidate, baseline, {"Objects"})
        self.assertFalse(result["passed"])
        self.assertIn("objects_parse_error", codes(result))

    # -- 缺失文件不是内部错误 ---------------------------------------------
    def test_missing_candidate_file_recorded_not_raised(self):
        _tmp, source, candidate, baseline = self.build()
        (candidate / "Localization.txt").unlink()
        result = vsc.validate_copy(source, candidate, baseline, set())
        self.assertFalse(result["passed"])
        self.assertIn("unauthorized_change", codes(result))
        paths = [change["path"] for change in result["changed_files"]]
        self.assertIn("Localization.txt", paths)

    # -- CLI --------------------------------------------------------------
    def test_cli_json_and_exit_codes(self):
        tmp, source, candidate, baseline = self.build()
        baseline_path = Path(tmp.name) / "baseline.json"
        baseline_path.write_text(
            json.dumps({"snapshot": baseline}, ensure_ascii=False), encoding="utf-8"
        )
        write(candidate, "Localization.txt", "KEY=changed\n")

        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        script = str(REPO_ROOT / "scripts" / "validate_skyshield_copy.py")

        ok = subprocess.run(
            [
                sys.executable,
                "-B", "-X", "utf8",
                script,
                "--source",
                str(source),
                "--candidate",
                str(candidate),
                "--baseline",
                str(baseline_path),
                "--allowed",
                "Localization.txt",
            ],
            capture_output=True,
            text=True, encoding="utf-8",
            env=env,
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        ok_payload = json.loads(ok.stdout)
        self.assertTrue(ok_payload["passed"])

        bad = subprocess.run(
            [
                sys.executable,
                "-B", "-X", "utf8",
                script,
                "--source",
                str(source),
                "--candidate",
                str(candidate),
                "--baseline",
                str(baseline_path),
            ],
            capture_output=True,
            text=True, encoding="utf-8",
            env=env,
        )
        self.assertEqual(bad.returncode, 1, bad.stderr)
        bad_payload = json.loads(bad.stdout)
        self.assertFalse(bad_payload["passed"])
        self.assertIn("unauthorized_change", codes(bad_payload))


class ExplicitCatalogAppendTests(unittest.TestCase):
    REL = "Base.SC2Data/GameData/ValidatorData.xml"
    ORIGINAL = (b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\r\n'
                b'<Catalog>\r\n<!-- original comment -->\r\n'
                b'  <CValidatorUnitFilters id="Old"><Filters value="Dead;-"/></CValidatorUnitFilters>\r\n'
                b'  <CValidatorCombine id="Other"><Type value="And"/></CValidatorCombine>\r\n'
                b'</Catalog>\r\n')
    ENTRY = (b'<CValidatorCombine id="New">\r\n'
             b'    <Type value="And"/>\r\n'
             b'    <CombineArray index="0" value="IsDead"/>\r\n'
             b'    <CombineArray index="1" value="IsNotHallucination"/>\r\n'
             b'</CValidatorCombine>')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.source = Path(tmp.name) / "source"
        self.candidate = Path(tmp.name) / "candidate"
        write(self.source, self.REL, self.ORIGINAL)
        write(self.candidate, self.REL, self.appended())
        self.baseline = snapshot(self.source)

    def appended(self, entry=None):
        return self.ORIGINAL.replace(b'</Catalog>', b'\t' + (entry or self.ENTRY) + b'\r\n</Catalog>')

    def check(self, entries=None, allowed=None):
        return vsc.validate_copy(self.source, self.candidate, self.baseline,
                                 {self.REL} if allowed is None else allowed,
                                 explicit_catalog_appends={self.REL: entries if entries is not None else {"New": self.ENTRY}})

    def test_exact_append_preserves_bom_crlf_and_old_comments(self):
        result = self.check()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["explicit_catalog_appends"], {self.REL: ["New"]})
        self.assertTrue(result["changed_files"][0]["protected"])
        self.assertEqual((self.source / self.REL).read_bytes(), self.ORIGINAL)

    def test_json_utf8_text_payload_passes(self):
        entries = json.loads(json.dumps({"New": self.ENTRY.decode("utf-8")}))
        self.assertTrue(self.check(entries)["passed"])

    def test_default_protection_is_unchanged(self):
        result = vsc.validate_copy(self.source, self.candidate, self.baseline, {self.REL})
        self.assertIn("protected_change", codes(result))

    def test_allowed_path_still_required(self):
        self.assertFalse(self.check(allowed=set())["passed"])

    def test_mutated_original_and_extra_content_are_rejected(self):
        valid = self.appended()
        variants = {
            "old value": valid.replace(b'Dead;-', b'-;Dead'),
            "old deletion": valid.replace(b'  <CValidatorCombine id="Other"><Type value="And"/></CValidatorCombine>\r\n', b''),
            "old comment": valid.replace(b'original comment', b'new comment'),
            "root attribute": valid.replace(b'<Catalog>', b'<Catalog version="2">'),
            "root whitespace": valid.replace(b'<Catalog>', b'<Catalog >'),
            "newline conversion": valid.replace(b'\r\n', b'\n'),
            "bom deletion": valid[3:],
            "closing spelling": valid.replace(b'</Catalog>', b'</Catalog >'),
            "extra entry": valid.replace(b'</Catalog>', b'<CValidatorCombine id="Extra"/></Catalog>'),
            "extra comment": valid.replace(b'</Catalog>', b'<!--added--></Catalog>'),
            "extra instruction": valid.replace(b'</Catalog>', b'<?inserted x?></Catalog>'),
            "duplicate new id": valid.replace(b'</Catalog>', self.ENTRY + b'</Catalog>'),
            "extra text": valid.replace(b'</Catalog>', b'text</Catalog>'),
            "payload mutation": valid.replace(b'value="IsDead"', b'value="NotDead"'),
            "not appended": valid.replace(b'\t' + self.ENTRY + b'\r\n', b'').replace(b'<!-- original', self.ENTRY + b'<!-- original'),
        }
        old_a = b'  <CValidatorUnitFilters id="Old"><Filters value="Dead;-"/></CValidatorUnitFilters>\r\n'
        old_b = b'  <CValidatorCombine id="Other"><Type value="And"/></CValidatorCombine>\r\n'
        variants["old order"] = valid.replace(old_a + old_b, old_b + old_a)
        for label, data in variants.items():
            with self.subTest(label=label):
                write(self.candidate, self.REL, data)
                result = self.check()
                self.assertFalse(result["passed"], label)
                self.assertIn("invalid_catalog_append", codes(result))

    def test_missing_or_added_whole_file_rejected(self):
        (self.candidate / self.REL).unlink()
        self.assertFalse(self.check()["passed"])
        write(self.candidate, self.REL, self.appended())
        (self.source / self.REL).unlink()
        write(self.source, "DocumentInfo", "<DocInfo/>")
        self.baseline = snapshot(self.source)
        self.assertFalse(self.check()["passed"])

    def test_unchanged_file_does_not_silently_satisfy_append(self):
        write(self.candidate, self.REL, self.ORIGINAL)
        self.assertFalse(self.check()["passed"])

    def test_reused_id_and_invalid_payloads_rejected(self):
        cases = [
            {"Old": self.ENTRY.replace(b'id="New"', b'id="Old"')},
            {"Wrong": self.ENTRY}, {}, {"New": None}, {"New": 123},
            {"New": b'<!--extra-->' + self.ENTRY},
            {"New": self.ENTRY + b'<CValidatorCombine id="Extra"/>'},
            {"New": b'<Catalog id="New"/>'},
            {"New": b'<!DOCTYPE C [<!ENTITY x "x">]><C id="New"/>'},
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                self.assertFalse(self.check(entries)["passed"])

    def test_original_duplicate_ids_rejected_even_when_preserved(self):
        self.ORIGINAL = self.ORIGINAL.replace(b'id="Other"', b'id="Old"')
        write(self.source, self.REL, self.ORIGINAL)
        write(self.candidate, self.REL, self.appended())
        self.baseline = snapshot(self.source)
        self.assertFalse(self.check()["passed"])

    def test_multiple_entries_require_declared_order(self):
        second = b'<CValidatorCombine id="Next"/>'
        write(self.candidate, self.REL, self.appended(self.ENTRY + b'\n' + second))
        self.assertTrue(self.check({"New": self.ENTRY, "Next": second})["passed"])
        self.assertFalse(self.check({"Next": second, "New": self.ENTRY})["passed"])

    def test_invalid_path_or_declaration_shape_rejected(self):
        for declaration in [[], {"../ValidatorData.xml": {"New": self.ENTRY}},
                            {"DocumentInfo": {"New": self.ENTRY}}, {self.REL: []},
                            {self.REL: {"New": self.ENTRY}, self.REL.lower(): {"New": self.ENTRY}}]:
            with self.subTest(declaration=declaration):
                result = vsc.validate_copy(self.source, self.candidate, self.baseline, {self.REL}, declaration)
                self.assertFalse(result["passed"])

    def test_source_drift_is_not_excused_by_append(self):
        write(self.source, self.REL, self.ORIGINAL.replace(b'original comment', b'changed comment'))
        result = self.check()
        self.assertIn("source_changed", codes(result))
        self.assertFalse(result["passed"])

    def test_cli_accepts_explicit_json_append_contract(self):
        baseline_file = self.source.parent / "baseline.json"
        appends_file = self.source.parent / "appends.json"
        baseline_file.write_text(json.dumps(self.baseline), encoding="utf-8")
        appends_file.write_text(json.dumps({self.REL: {"New": self.ENTRY.decode("utf-8")}}), encoding="utf-8")
        process = subprocess.run([
            sys.executable, "-B", "-X", "utf8", str(REPO_ROOT / "scripts/validate_skyshield_copy.py"),
            "--source", str(self.source), "--candidate", str(self.candidate),
            "--baseline", str(baseline_file), "--allowed", self.REL,
            "--catalog-appends", str(appends_file),
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
