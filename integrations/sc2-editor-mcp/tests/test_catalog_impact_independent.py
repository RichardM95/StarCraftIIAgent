"""Independent report review with synthetic maps; no engine or formal map access."""
import hashlib
import json
from pathlib import Path

import pytest

from sc2_mcp import catalog_impact
from sc2_mcp.catalog_patch import plan_catalog_patch, plan_catalog_patch_report
from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.source_context import prepare_source_context
from sc2_mcp.storage import snapshot


def put(root, kind, content):
    path = root / "Base.SC2Data/GameData" / (kind + "Data.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<Catalog>" + content + "</Catalog>", encoding="utf-8")
    return path


def operation(kind="Unit", ident="A", action="set", **kwargs):
    return {"operation": action, "catalog": kind, "object_id": ident, **kwargs}


def context(root, cache):
    (root / "DocumentInfo").write_bytes(b"<DocInfo/>")
    return prepare_source_context(root, [], cache)


def test_deep_inheritance_and_transitive_references_distinguish_actual_and_potential(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit><CUnit id="Child" parent="A"/><CUnit id="Grand" parent="Child"/><CUnit id="Override" parent="A"><LifeMax value="99"/></CUnit>')
    put(root, "Effect", '<CEffectCreateUnit id="Spawn"><SpawnUnit value="Grand"/></CEffectCreateUnit><CEffectSet id="Indirect"><EffectArray index="0" value="Spawn"/></CEffectSet>')
    before = snapshot(root)
    report = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="60")])["report"]
    assert {row["object_id"] for row in report["numeric_changes"]} == {"A", "Child", "Grand"}
    objects = {row["object_id"]: row for row in report["objects"]}
    assert objects["Override"]["status"] == "unchanged_static"
    affected = {row["object_id"]: row for row in report["potentially_impacted_objects"]}
    assert {"Spawn", "Indirect", "Override"} <= set(affected)
    assert affected["Override"]["changed_effective_fields"] is False
    assert snapshot(root) == before


def test_equal_reference_local_override_is_source_only_for_fields_and_edges(tmp_path):
    dep, root = tmp_path / "dep", tmp_path / "map"
    put(dep, "Unit", '<CUnit id="A"><WeaponArray index="0" Link="W"/></CUnit>')
    put(dep, "Weapon", '<CWeapon id="W"/>')
    root.mkdir()
    report = plan_catalog_patch_report(root, [dep, root], [operation(field_path="WeaponArray[0].Link", value="W")])["report"]
    assert report["value_changes"] == report["structural_changes"] == []
    assert len(report["source_only_changes"]) == 1
    refs = report["reference_changes"]
    assert refs["added"] == refs["removed"] == []
    assert len(refs["source_only"]) == 1
    assert Path(refs["source_only"][0]["after"]["source"]["root"]) == root


def test_same_file_hash_change_does_not_relabel_untouched_reference_edges(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/><WeaponArray index="0" Link="W"/></CUnit><CUnit id="Other"><WeaponArray index="0" Link="W"/></CUnit>')
    put(root, "Weapon", '<CWeapon id="W"/>')
    report = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="50")])["report"]
    assert report["reference_changes"] == {"added": [], "removed": [], "source_only": []}
    assert report["source_only_changes"] == []


def test_empty_slot_tombstone_is_structural_even_without_flattened_value_change(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><WeaponArray index="0"/></CUnit>')
    operations = [operation(action="remove", field_path="WeaponArray[0]")]
    result = plan_catalog_patch_report(root, [root], operations)
    assert result["changes"] == plan_catalog_patch(root, [root], operations)
    report = result["report"]
    assert report["value_changes"] == report["source_only_changes"] == []
    shapes = [row for row in report["structural_changes"] if row["kind"] == "node_shape"]
    assert shapes[0]["before"] == [{"path": "WeaponArray[0]", "removed": False}]
    assert shapes[0]["after"] == [{"path": "WeaponArray[0]", "removed": True}]


def test_new_missing_parent_resolution_reaches_existing_descendants(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="Child" parent="NewParent"/><CUnit id="Grand" parent="Child"/>')
    report = plan_catalog_patch_report(root, [root], [operation(ident="NewParent", action="create", **{"class": "CUnit", "fields": {"LifeMax": "45"}})])["report"]
    assert {row["object_id"] for row in report["structural_changes"] if row["kind"] == "field_added"} == {"NewParent", "Child", "Grand"}
    assert any(row["side"] == "before" and row.get("warning", {}).get("code") == "missing_catalog_parent" for row in report["unknown"])
    assert {row["to"]["object_id"] for row in report["unresolved_references"]["before"]} == {"NewParent"}
    assert report["unresolved_references"]["after"] == []


def test_first_object_cycle_and_stable_missing_reference_remain_explicit(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="Cycle1" parent="Cycle2"/><CUnit id="Cycle2" parent="Cycle1"/><CUnit id="A"><LifeMax value="45"/></CUnit><CUnit id="MissingConsumer"><WeaponArray index="0" Link="AbsentWeapon"/></CUnit>')
    report = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="50")])["report"]
    assert any(row.get("scope") == "reference_graph" and row["detail"].get("code") == "catalog_parent_cycle" for row in report["unknown"])
    for side in ["before", "after"]:
        assert [row["to"]["object_id"] for row in report["unresolved_references"][side]] == ["AbsentWeapon"]
    assert report["reference_changes"] == {"added": [], "removed": [], "source_only": []}
    assert report["engine_parity"] is False


def test_untouched_dynamic_field_remains_unknown_and_never_becomes_numeric_fact(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/><Speed value="$DynamicSpeed$"/></CUnit>')
    report = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="50")])["report"]
    assert any(row.get("warning", {}).get("code") == "unevaluated_catalog_expression" for row in report["unknown"])
    assert [row["field"] for row in report["numeric_changes"]] == ["LifeMax"]
    assert any("动态" in text for text in report["limitations"])


def test_same_numeric_value_spelling_is_explicitly_equal_and_not_source_only(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    report = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="45.000")])["report"]
    assert report["numeric_changes"][0]["numeric_equal"] is True
    assert report["source_only_changes"] == []


def test_selected_context_and_candidate_source_digest_bind_same_bytes(tmp_path):
    root = tmp_path / "map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    selected = context(root, tmp_path / "cache")
    before = snapshot(root)
    result = plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="50")], source_context=selected)
    report = result["report"]
    assert report["source_context_id"] == selected["source_context_id"]
    assert report["source_complete"] == selected["complete"]
    path, raw = next(iter(result["changes"].items()))
    expected = hashlib.sha256(raw).hexdigest()
    assert report["candidate_files"][path] == {"sha256": expected, "bytes": len(raw)}
    assert report["numeric_changes"][0]["after"]["source"]["sha256"] == expected
    assert snapshot(root) == before
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("failure", ["roots", "stale"])
def test_wrong_or_stale_context_refuses_report_without_candidate_writes(tmp_path, failure):
    root = tmp_path / "map"
    source = put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    selected = context(root, tmp_path / "cache")
    roots = [root]
    if failure == "roots":
        extra = tmp_path / "extra"
        extra.mkdir()
        roots = [extra, root]
    else:
        source.write_bytes(source.read_bytes().replace(b'45', b'46'))
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        plan_catalog_patch_report(root, roots, [operation(field_path="LifeMax", value="50")], source_context=selected)
    assert caught.value.code == ("source_context_roots_mismatch" if failure == "roots" else "source_context_stale")
    assert snapshot(root) == before


def test_source_change_during_impact_generation_cannot_return_bound_report(tmp_path, monkeypatch):
    root = tmp_path / "map"
    source = put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    original = catalog_impact.inspect_patch_impact
    def racing(*args, **kwargs):
        report = original(*args, **kwargs)
        source.write_bytes(source.read_bytes().replace(b'45', b'46'))
        return report
    monkeypatch.setattr(catalog_impact, "inspect_patch_impact", racing)
    with pytest.raises(SC2Error) as caught:
        plan_catalog_patch_report(root, [root], [operation(field_path="LifeMax", value="50")])
    assert caught.value.code == "catalog_source_changed"
    assert b'46' in source.read_bytes() and b'50' not in source.read_bytes()


def test_noop_service_returns_empty_report_without_inventing_transaction(tmp_path, monkeypatch):
    root = tmp_path / "map.SC2Map"
    put(root, "Unit", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    (root / "DocumentInfo").write_bytes(b"<DocInfo/>")
    (root / "MapScript.galaxy").write_bytes(b"void InitMap () {}\n")
    service = Service(tmp_path / "state")
    monkeypatch.setattr(service, "editor_conflict", lambda: None)
    try:
        project = service.projects.open(str(root), True)
        before = snapshot(root)
        result = service.prepare_catalog_patch(project["project_id"], [operation(field_path="LifeMax", value="45")])
        assert result["state"] == "unchanged" and "change_id" not in result
        assert result["impact_report"]["candidate_files"] == {}
        assert result["impact_report"]["potentially_impacted_objects"] == []
        assert snapshot(root) == before
    finally:
        service.jobs.shutdown()
