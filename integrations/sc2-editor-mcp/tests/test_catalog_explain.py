import json
from pathlib import Path

import pytest

from sc2_mcp.catalog_explain import catalog_explain
from sc2_mcp.errors import SC2Error
from sc2_mcp.source_context import prepare_source_context


def put(root, relative, raw):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw.encode() if isinstance(raw, str) else raw)
    return path


def cat(root, content):
    put(root, "DocumentInfo", "<DocInfo/>")
    put(root, "Base.SC2Data/GameData/UnitData.xml", "<Catalog>" + content + "</Catalog>")
    return root


def test_per_field_provenance_native_default_macro_and_array_limits(tmp_path):
    base = cat(tmp_path / "base", '<CUnit id="A"><LifeMax value="45"/><WeaponArray Link="Rifle"/><Name value="Unit/Name/##id##"/><Uncovered value="X"/></CUnit>')
    local = cat(tmp_path / "map", '<CUnit id="A"><LifeMax value="50"/><WeaponArray index="0" Turret="T"/></CUnit>')
    result = catalog_explain([base, local], "Unit", "A", ["LifeMax", "EnergyMax", "Name", "WeaponArray[0].Link", "WeaponArray[0].Turret", "Uncovered"])
    fields = result["fields"]
    assert fields["LifeMax"]["status"] == "known_static"
    assert [item["value"] for item in fields["LifeMax"]["provenance"]] == ["45", "50"]
    assert fields["EnergyMax"]["status"] == "unknown"
    assert fields["Name"]["status"] == "unknown"
    assert fields["Uncovered"]["status"] == "partial"
    assert fields["WeaponArray[0].Link"]["status"] == "partial"
    assert fields["WeaponArray[0].Turret"]["status"] == "partial"
    assert fields["LifeMax"]["comparison"] == "not_observed"
    assert not result["engine_parity"]
    json.dumps(result)


def test_runtime_comparison_is_bound_and_never_replaces_static(tmp_path):
    root = cat(tmp_path / "map", '<CUnit id="A"><LifeMax value="45"/><Speed value="3"/></CUnit>')
    context = prepare_source_context(root, [], tmp_path / "cache")
    observations = {"source_context_id": context["source_context_id"], "observations": [
        {"field": "LifeMax", "value": "45.000", "evidence_id": "runtime-bank-sha256"},
        {"field": "Speed", "value": "4", "evidence": {"bank_sha256": "b" * 64}},
        {"field": "EnergyMax", "status": "missing", "evidence_id": "runtime-bank-sha256"},
    ]}
    result = catalog_explain([root], "Unit", "A", ["LifeMax", "Speed", "EnergyMax"], context, observations)
    assert result["fields"]["LifeMax"]["comparison"] == "matched"
    assert result["fields"]["Speed"]["comparison"] == "mismatched"
    assert result["fields"]["Speed"]["static"]["value"] == "3"
    assert result["fields"]["EnergyMax"]["comparison"] == "unknown"
    observations["source_context_id"] = "stale"
    assert catalog_explain([root], "Unit", "A", ["LifeMax"], context, observations)["fields"]["LifeMax"]["comparison"] == "unknown"


def test_runtime_missing_evidence_or_context_cannot_match(tmp_path):
    root = cat(tmp_path / "map", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    context = prepare_source_context(root, [], tmp_path / "cache")
    obs = {"source_context_id": context["source_context_id"], "fields": {"LifeMax": {"value": "45"}}}
    assert catalog_explain([root], "Unit", "A", None, context, obs)["fields"]["LifeMax"]["comparison"] == "unknown"
    obs["fields"]["LifeMax"]["evidence_id"] = "bank"
    assert catalog_explain([root], "Unit", "A", None, None, obs)["fields"]["LifeMax"]["comparison"] == "unknown"


def test_missing_includes_are_unknown_without_a_fake_candidate(tmp_path):
    root = cat(tmp_path / "map", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    put(root, "Base.SC2Data/GameData.xml", '<Includes><Catalog path="GameData/Missing.xml"/></Includes>')
    context = prepare_source_context(root, [], tmp_path / "cache")
    result = catalog_explain([root], "Unit", "A", ["LifeMax"], context)
    assert result["fields"]["LifeMax"]["status"] == "unknown"
    assert result["fields"]["LifeMax"]["static"]["value"] is None
    assert result["error"]["code"] == "missing_catalog_include"


def test_source_changes_make_old_observation_unknown(tmp_path):
    root = cat(tmp_path / "map", '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    context = prepare_source_context(root, [], tmp_path / "cache")
    obs = {"source_context_id": context["source_context_id"], "fields": {"LifeMax": {"value": "50", "evidence_id": "old-bank"}}}
    cat(root, '<CUnit id="A"><LifeMax value="50"/></CUnit>')
    result = catalog_explain([root], "Unit", "A", ["LifeMax"], context, obs)
    assert result["source_context_current"] is False
    assert result["fields"]["LifeMax"]["comparison"] == "unknown"


def test_duplicate_stage_observations_rejected(tmp_path):
    root = cat(tmp_path / "map", '<CUnit id="A"/>')
    with pytest.raises(SC2Error) as error:
        catalog_explain([root], "Unit", "A", ["LifeMax"], observations={"observations": [{"field": "LifeMax", "value": "45"}, {"field": "LifeMax", "value": "55"}]})
    assert error.value.code == "ambiguous_catalog_observation"
