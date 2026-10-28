from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.catalog import inspect_catalog
from sc2_mcp.catalog_patch import plan_catalog_patch
from sc2_mcp.errors import SC2Error


def put(root, content, kind="Unit", filename=None):
    path = root / (filename or f"Base.SC2Data/GameData/{kind}Data.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = content.encode() if isinstance(content, str) else content
    path.write_bytes(raw)
    return path


def ops(action, **kwargs):
    return {"operation": action, "catalog": "Unit", "object_id": "A", **kwargs}


def apply(root, changes):
    for relative, raw in changes.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def test_dependency_scalar_builds_minimal_local_override_without_source_write(tmp_path):
    dep, root = tmp_path / "dep", tmp_path / "map"
    before = b'<Catalog><!--dependency--><CUnit id="A"><LifeMax value="45"/><Speed value="3"/></CUnit></Catalog>'
    path = put(dep, before)
    root.mkdir()
    result = plan_catalog_patch(root, [dep, root], [ops("set", field_path="LifeMax", value="50", expected="45")])
    assert not (root / "Base.SC2Data").exists()
    assert path.read_bytes() == before
    candidate = ET.fromstring(result["Base.SC2Data/GameData/UnitData.xml"])
    node = candidate.find("CUnit")
    assert node.attrib == {"id": "A"}
    assert [child.tag for child in node] == ["LifeMax"]
    apply(root, result)
    assert inspect_catalog([dep, root], "Unit", "A")["fields"]["Speed"]["value"] == "3"


def test_multiple_edits_preserve_comments_unknown_attributes_and_crlf(tmp_path):
    raw = b'<?xml version="1.0" encoding="utf-8"?>\r\n<Catalog>\r\n  <!-- keep -->\r\n  <CUnit custom="stable" id="A"><LifeMax value = \'45\'/><Unknown value="untouched"/></CUnit>\r\n  <CUnit id="Other"/>\r\n</Catalog>\r\n'
    path = put(tmp_path, raw)
    result = plan_catalog_patch(tmp_path, [tmp_path], [ops("set", field_path="LifeMax", value="50"), ops("set", field_path="LifeMax", value="60", expected="50")])
    assert result == {"Base.SC2Data/GameData/UnitData.xml": raw.replace(b"value = '45'", b"value = '60'")}
    assert path.read_bytes() == raw


def test_append_remove_restore_keep_exact_slots_and_payload(tmp_path):
    dep, root = tmp_path / "dep", tmp_path / "map"
    put(dep, '<Catalog><CUnit id="A"><WeaponArray index="0" Link="W0"/><WeaponArray index="1" Link="W1"/></CUnit></Catalog>')
    root.mkdir()
    result = plan_catalog_patch(root, [dep, root], [ops("remove", field_path="WeaponArray[0]"), ops("append", field_path="WeaponArray[2]", attributes={"Link": "W2"}), ops("restore", field_path="WeaponArray[0]", attributes={"Link": "W0-restored"})])
    assert not (root / "Base.SC2Data").exists()
    apply(root, result)
    item = inspect_catalog([dep, root], "Unit", "A")
    assert {field: record["value"] for field, record in item["fields"].items()} == {"WeaponArray[0].Link": "W0-restored", "WeaponArray[1].Link": "W1", "WeaponArray[2].Link": "W2"}
    assert not item["removed"]


@pytest.mark.parametrize("payload,code", [
    (ops("append", field_path="WeaponArray[1]", attributes={"Link": "W"}), "catalog_append_index_mismatch"),
    (ops("append", field_path="WeaponArray[2]", attributes={}), "catalog_array_payload_required"),
    (ops("append", field_path="WeaponArray[2]", attributes={"Link": "##macro##"}), "catalog_macro_unsupported"),
    (ops("append", field_path="UnknownArray[0]", attributes={"value": "X"}), "unknown_catalog_array_rule"),
    (ops("remove", field_path="WeaponArray[8]"), "catalog_array_slot_missing"),
    (ops("restore", field_path="WeaponArray[1]", attributes={"Link": "W"}), "catalog_array_slot_not_removed"),
])
def test_invalid_structure_rejects_without_writes(tmp_path, payload, code):
    raw = b'<Catalog><CUnit id="A"><WeaponArray index="0" Link="W0"/><WeaponArray index="1" Link="W1"/></CUnit></Catalog>'
    path = put(tmp_path, raw)
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path], [ops("set", field_path="LifeMax", value="100"), payload])
    assert error.value.code == code
    assert path.read_bytes() == raw


@pytest.mark.parametrize("entries", ['<WeaponArray Link="W0"/>', '<WeaponArray index="0" Link="W0"/><WeaponArray index="0" Link="W1"/>'])
def test_unindexed_or_duplicate_slots_reject_all_guessing(tmp_path, entries):
    put(tmp_path, '<Catalog><CUnit id="A">' + entries + '</CUnit></Catalog>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path], [ops("remove", field_path="WeaponArray[0]")])
    assert error.value.code in {"ambiguous_unindexed_array", "ambiguous_catalog_field"}


def test_create_and_selected_clone_preserve_old_objects(tmp_path):
    raw = b'<Catalog><!--keep--><CUnit id="A"><LifeMax value="45"/><Speed value="3"/><WeaponArray index="0" Link="W"/></CUnit></Catalog>'
    path = put(tmp_path, raw)
    result = plan_catalog_patch(tmp_path, [tmp_path], [
        {"operation": "clone", "catalog": "Unit", "object_id": "New", "source_id": "A", "fields": ["LifeMax", "WeaponArray[0].Link"]},
        {"operation": "create", "catalog": "Unit", "object_id": "Other", "class": "CUnit", "fields": {"LifeMax": "80"}},
    ])
    candidate = next(iter(result.values()))
    assert raw[:-10] in candidate
    assert path.read_bytes() == raw
    parsed = ET.fromstring(candidate)
    assert parsed.find("CUnit[@id='New']/Speed") is None
    assert parsed.find("CUnit[@id='New']/WeaponArray").get("Link") == "W"
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path], [{"operation": "create", "catalog": "Unit", "object_id": "A", "class": "CUnit"}])
    assert error.value.code == "catalog_id_exists"


def test_ambiguous_duplicate_objects_and_locale_shadow_rejected(tmp_path):
    put(tmp_path, '<Catalog><CUnit id="A"/><CUnit id="A"/></Catalog>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path], [ops("set", field_path="LifeMax", value="60")])
    assert error.value.code == "ambiguous_catalog_object"
    put(tmp_path, '<Catalog><CUnit id="A"><LifeMax value="45"/></CUnit></Catalog>')
    put(tmp_path, '<Catalog><CUnit id="A"><LifeMax value="70"/></CUnit></Catalog>', filename="zhCN.SC2Data/GameData/UnitData.xml")
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path, tmp_path / "zhCN.SC2Data"], [ops("set", field_path="LifeMax", value="60")])
    assert error.value.code == "catalog_patch_shadowed"


def test_inline_include_order_is_not_regrouped_by_file(tmp_path):
    dep, root = tmp_path / "dep", tmp_path / "map"
    put(dep, '<Catalog><CUnit id="A"><LifeMax value="40"/></CUnit><Include path="extra.xml"/><CUnit id="A"><LifeMax value="60"/></CUnit></Catalog>')
    put(dep, '<Catalog><CUnit id="A"><LifeMax value="50"/></CUnit></Catalog>', filename="Base.SC2Data/GameData/extra.xml")
    root.mkdir()
    result = plan_catalog_patch(root, [dep, root], [ops("set", field_path="Speed", value="4"), ops("set", field_path="LifeMax", value="70", expected="60")])
    apply(root, result)
    assert inspect_catalog([dep, root], "Unit", "A")["fields"]["LifeMax"]["value"] == "70"


def test_selected_clone_preserves_unlisted_attribute_names(tmp_path):
    put(tmp_path, '<Catalog><CUpgrade id="U"><EffectArray index="0" Reference="Unit,A,LifeMax" Operation="Add" Value="10"/></CUpgrade></Catalog>', kind="Upgrade")
    result = plan_catalog_patch(tmp_path, [tmp_path], [{"operation": "clone", "catalog": "Upgrade", "object_id": "New", "source_id": "U", "fields": ["EffectArray[0].Reference", "EffectArray[0].Operation", "EffectArray[0].Value"]}])
    cloned = ET.fromstring(next(iter(result.values()))).find("CUpgrade[@id='New']/EffectArray")
    assert cloned.attrib == {"index": "0", "Reference": "Unit,A,LifeMax", "Operation": "Add", "Value": "10"}
    assert not list(cloned)


def test_empty_slots_are_preserved_in_append_and_remove(tmp_path):
    put(tmp_path, '<Catalog><CUnit id="A"><WeaponArray index="0" Link="W"/><WeaponArray index="1"/></CUnit></Catalog>')
    result = plan_catalog_patch(tmp_path, [tmp_path], [ops("remove", field_path="WeaponArray[1]"), ops("append", field_path="WeaponArray[2]", attributes={"Link": "W2"})])
    node = ET.fromstring(next(iter(result.values()))).find("CUnit")
    assert [(child.get("index"), child.get("removed")) for child in node] == [("0", None), ("1", "1"), ("2", None)]


def test_explicit_attribute_path_and_observed_subclass_guards(tmp_path):
    put(tmp_path, '<Catalog><CUnit id="A"><WeaponArray index="0" Link="W"/></CUnit></Catalog>')
    result = plan_catalog_patch(tmp_path, [tmp_path], [ops("set", field_path="WeaponArray[0].@Link", value="New")])
    assert ET.fromstring(next(iter(result.values()))).find("CUnit/WeaponArray").get("Link") == "New"
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(tmp_path, [tmp_path], [{"operation": "create", "catalog": "Unit", "object_id": "New", "class": "CUnitMadeUp"}])
    assert error.value.code == "unknown_catalog_class"
