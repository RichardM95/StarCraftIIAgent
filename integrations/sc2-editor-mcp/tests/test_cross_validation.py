from pathlib import Path

import pytest

from sc2_mcp.cross_validation import validate_references
from sc2_mcp.catalog import CatalogSession
from sc2_mcp.errors import SC2Error
from sc2_mcp.storage import snapshot


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "map.SC2Map"
    root.mkdir()
    put(root, "DocumentInfo", "<DocInfo><Dependencies/></DocInfo>")
    put(root, "Base.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="Marine"><WeaponArray index="0" Link="Gun"/></CUnit></Catalog>')
    put(root, "Base.SC2Data/GameData/WeaponData.xml", '<Catalog><CWeapon id="Gun"><Effect value="Damage"/></CWeapon></Catalog>')
    put(root, "Base.SC2Data/GameData/EffectData.xml", '<Catalog><CEffectDamage id="Damage"/></Catalog>')
    put(root, "Objects", '<PlacedObjects><ObjectPoint Id="7" Type="Normal" Position="1,2,0"/><ObjectUnit Id="8" UnitType="Marine" Position="3,2,0"/></PlacedObjects>')
    put(root, "Regions", '<Regions><region id="1"><name value="area"/></region></Regions>')
    put(root, "MapScript.galaxy", 'void f(){point p=PointFromId(7); UnitCreate(1, "Marine", 0, 1, null, 0.0);}')
    return root, tmp_path / "validation"


def check(project, changes, dependencies=None):
    root, workspace = project
    return validate_references(root, changes, dependencies or [], workspace)


def test_new_missing_weapon_is_rejected_without_source_writes(project):
    root, _ = project
    baseline = snapshot(root)
    value = (root / "Base.SC2Data/GameData/UnitData.xml").read_bytes().replace(b'Link="Gun"', b'Link="Missing"')
    with pytest.raises(SC2Error) as error:
        check(project, {"Base.SC2Data/GameData/UnitData.xml": value})
    assert error.value.code == "new_missing_references"
    edge = error.value.details["report"]["new_missing"][0]
    assert edge["to"] == {"catalog": "Weapon", "object_id": "Missing"}
    assert snapshot(root) == baseline
    assert not (root / ".sc2-mcp").exists()


def test_atomic_candidate_can_add_the_referenced_definition(project):
    root, _ = project
    unit = (root / "Base.SC2Data/GameData/UnitData.xml").read_bytes().replace(b'Link="Gun"', b'Link="NewGun"')
    weapon = (root / "Base.SC2Data/GameData/WeaponData.xml").read_bytes().replace(b"</Catalog>", b'<CWeapon id="NewGun"><Effect value="Damage"/></CWeapon></Catalog>')
    result = check(project, {"Base.SC2Data/GameData/UnitData.xml": unit, "Base.SC2Data/GameData/WeaponData.xml": weapon})
    assert result["static"] == "passed"


def test_existing_missing_is_tolerated_but_replacing_it_is_not(project):
    root, _ = project
    path = root / "Base.SC2Data/GameData/UnitData.xml"
    value = path.read_bytes().replace(b'Link="Gun"', b'Link="LegacyMissing"')
    path.write_bytes(value)
    result = check(project, {"Base.SC2Data/GameData/UnitData.xml": value.replace(b"</CUnit>", b'<LifeMax value="100"/></CUnit>')})
    assert result["existing_catalog_missing_count"] >= 1
    with pytest.raises(SC2Error):
        check(project, {"Base.SC2Data/GameData/UnitData.xml": value.replace(b"LegacyMissing", b"AnotherMissing")})


def test_renaming_referenced_id_breaks_incoming_edge(project):
    root, _ = project
    path = "Base.SC2Data/GameData/WeaponData.xml"
    with pytest.raises(SC2Error) as error:
        check(project, {path: (root / path).read_bytes().replace(b'id="Gun"', b'id="Renamed"')})
    assert any(edge.get("to", {}).get("object_id") == "Gun" for edge in error.value.details["report"]["new_missing"])


def test_new_parent_link_and_parent_cycles_are_rejected(project):
    root, _ = project
    path = "Base.SC2Data/GameData/UnitData.xml"
    with pytest.raises(SC2Error) as error:
        check(project, {path: (root / path).read_bytes().replace(b'id="Marine"', b'id="Marine" parent="MissingParent"')})
    assert any(edge.get("field") == "parent" for edge in error.value.details["report"]["new_missing"])
    with pytest.raises(SC2Error) as error:
        check(project, {path: b'<Catalog><CUnit id="Marine" parent="Other"/><CUnit id="Other" parent="Marine"/></Catalog>'})
    assert any(edge["kind"] == "catalog_parent_cycle" for edge in error.value.details["report"]["new_missing"])


def test_dependency_objects_resolve_and_removal_context_detects_break(project, tmp_path):
    root, _ = project
    dependency = tmp_path / "dep.SC2Mod"
    dependency.mkdir()
    put(dependency, "Base.SC2Data/GameData/WeaponData.xml", '<Catalog><CWeapon id="ExternalGun"/></Catalog>')
    path = "Base.SC2Data/GameData/UnitData.xml"
    value = (root / path).read_bytes().replace(b'Link="Gun"', b'Link="ExternalGun"')
    assert check(project, {path: value}, [dependency])["static"] == "passed"
    (root / path).write_bytes(value)
    with pytest.raises(SC2Error) as error:
        check(project, {"DocumentInfo": b"<DocInfo><Dependencies/></DocInfo>"}, {"before": [dependency], "after": []})
    assert error.value.code == "new_missing_references"


def test_dependency_declaration_change_requires_both_contexts(project):
    with pytest.raises(SC2Error) as error:
        check(project, {"DocumentInfo": b"<DocInfo><Dependencies><Value>file:New.SC2Mod</Value></Dependencies></DocInfo>"})
    assert error.value.code == "dependency_validation_context_required"


def test_unattached_xml_stays_unloaded_but_new_include_is_resolved(project):
    root, _ = project
    put(root, "Base.SC2Data/GameData/Unattached.xml", '<Catalog><CUnit id="Extra"><WeaponArray Link="Missing"/></CUnit></Catalog>')
    assert check(project, {"MapScript.galaxy": b"void f(){}"})["static"] == "passed"
    with pytest.raises(SC2Error):
        check(project, {"Base.SC2Data/GameData.xml": b'<Includes><Catalog path="GameData/Unattached.xml"/></Includes>'})


def test_missing_include_and_removed_definition_are_rejected(project):
    with pytest.raises(SC2Error) as error:
        check(project, {"Base.SC2Data/GameData.xml": b'<Includes><Catalog path="GameData/Absent.xml"/></Includes>'})
    assert error.value.code == "missing_catalog_include"
    with pytest.raises(SC2Error) as error:
        check(project, {"Base.SC2Data/GameData/EffectData.xml": None})
    assert error.value.code == "new_missing_references"


def test_spatial_unit_type_missing_is_rejected(project):
    root, _ = project
    value = (root / "Objects").read_bytes().replace(b'UnitType="Marine"', b'UnitType="MissingUnit"')
    with pytest.raises(SC2Error) as error:
        check(project, {"Objects": value})
    assert any(edge["kind"] == "placed_object_catalog_reference" for edge in error.value.details["report"]["new_missing"])


def test_point_removed_then_script_readded_is_caught_on_complete_candidate(project):
    root, _ = project
    objects = (root / "Objects").read_bytes().replace(b'<ObjectPoint Id="7" Type="Normal" Position="1,2,0"/>', b"")
    with pytest.raises(SC2Error) as error:
        check(project, {"Objects": objects, "MapScript.galaxy": b"void newFunction(){PointFromId(7);}"})
    assert any(edge["kind"] == "galaxy_spatial_reference" for edge in error.value.details["report"]["new_missing"])


def test_comments_and_literal_strings_are_not_spatial_calls(project):
    result = check(project, {"MapScript.galaxy": b'void f(){ /* PointFromId(999); */ string x="PointFromId(1000)";}'})
    assert result["static"] == "passed"


def test_unitcreate_removed_existing_unit_is_provable_but_new_missing_is_unknown(project):
    root, _ = project
    # Also remove preplaced reference so the native Galaxy literal is isolated.
    objects = (root / "Objects").read_bytes().replace(b'<ObjectUnit Id="8" UnitType="Marine" Position="3,2,0"/>', b"")
    with pytest.raises(SC2Error) as error:
        check(project, {"Base.SC2Data/GameData/UnitData.xml": b"<Catalog/>", "Objects": objects})
    assert any(edge["kind"] == "galaxy_unit_type" for edge in error.value.details["report"]["new_missing"])
    result = check(project, {"MapScript.galaxy": b'void f(){UnitCreate(1,"UnknownUnit",0,1,null,0.0);UnitCreate(1,type,0,1,null,0.0);}'})
    assert {item["kind"] for item in result["unresolved"]} >= {"galaxy_unit_type", "dynamic_unit_create"}


def test_doodad_type_is_only_proved_for_observed_doodad_actor(project):
    root, _ = project
    put(root, "Base.SC2Data/GameData/ActorData.xml", '<Catalog><CActorDoodad id="Rock"/></Catalog>')
    objects = (root / "Objects").read_bytes().replace(b"</PlacedObjects>", b'<ObjectDoodad Id="9" Type="Rock"/></PlacedObjects>')
    (root / "Objects").write_bytes(objects)
    with pytest.raises(SC2Error) as error:
        check(project, {"Base.SC2Data/GameData/ActorData.xml": b"<Catalog/>"})
    assert any(edge.get("to", {}).get("catalog") == "Actor" for edge in error.value.details["report"]["new_missing"])
    result = check(project, {"Objects": objects.replace(b'Type="Rock"', b'Type="UnknownDoodad"')})
    assert result["unresolved"][0]["kind"] == "doodad_catalog_type_unverified"


def test_group_reference_is_checked_after_other_file_edits(project):
    root, _ = project
    objects = (root / "Objects").read_bytes().replace(b"</PlacedObjects>", b'<Group Id="20" Type="ObjectPoint"><GroupObject Id="999"/></Group></PlacedObjects>')
    with pytest.raises(SC2Error) as error:
        check(project, {"Objects": objects})
    assert any(edge["kind"] == "group_member_reference" for edge in error.value.details["report"]["new_missing"])


def test_expression_reference_is_explicitly_unknown(project):
    root, _ = project
    path = "Base.SC2Data/GameData/WeaponData.xml"
    value = (root / path).read_bytes().replace(b'value="Damage"', b'value="##effect##"')
    result = check(project, {path: value})
    assert any(edge["kind"] == "nonliteral_catalog_reference" for edge in result["unresolved"])
    assert result["engine_parity"] is False


def test_workspace_cannot_write_into_source_or_dependencies(project, tmp_path):
    root, _ = project
    for workspace in (root, root / "subdir"):
        with pytest.raises(SC2Error) as error:
            validate_references(root, {"MapScript.galaxy": b"void f(){}"}, [], workspace)
        assert error.value.code == "unsafe_validation_workspace"
    dep = tmp_path / "dep.SC2Mod"
    dep.mkdir()
    with pytest.raises(SC2Error):
        validate_references(root, {"MapScript.galaxy": b"void f(){}"}, [dep], dep / "scratch")


def test_non_reference_change_does_not_create_workspace(project):
    root, workspace = project
    result = check(project, {"Assets/Textures/new.dds": b"fake asset bytes"})
    assert result["static"] == "not_applicable"
    assert not workspace.exists()


@pytest.mark.parametrize("attribute", ['value="file:New.SC2Mod"', 'file="New.SC2Mod"',
                                       'bnet="s2ma:123/1"', 'file="New.SC2Mod" bnet="s2ma:123/1"'])
def test_dependency_attribute_declaration_change_requires_both_contexts(project, attribute):
    with pytest.raises(SC2Error) as error:
        check(project, {"DocumentInfo": ('<DocInfo><Dependencies><Value ' + attribute + '/></Dependencies></DocInfo>').encode()})
    assert error.value.code == "dependency_validation_context_required"


def test_dependency_equivalent_text_and_attribute_do_not_need_new_context(project):
    root, _ = project
    put(root, "DocumentInfo", '<DocInfo><Dependencies><Value>file:Test.SC2Mod</Value></Dependencies></DocInfo>')
    assert check(project, {"DocumentInfo": b'<DocInfo><Dependencies><Value value="file:Test.SC2Mod"/></Dependencies></DocInfo>'})["static"] == "passed"


@pytest.mark.parametrize("identifier", ["New-Gun", "2ndGun", "Weapon.V2", "新武器"])
def test_unusual_literal_ids_do_not_hide_new_missing_references(project, identifier):
    root, _ = project
    path = "Base.SC2Data/GameData/UnitData.xml"
    value = (root / path).read_bytes().replace(b'Link="Gun"', ('Link="' + identifier + '"').encode())
    with pytest.raises(SC2Error) as error:
        check(project, {path: value})
    assert error.value.code == "new_missing_references"


def test_unit_group_literal_requires_unit_group_type(project):
    root, _ = project
    objects = (root / "Objects").read_bytes().replace(b"</PlacedObjects>", b'<Group Id="20" Type="ObjectDoodad"/></PlacedObjects>')
    with pytest.raises(SC2Error) as error:
        check(project, {"Objects": objects, "MapScript.galaxy": b'void f(){UnitGroupFromId(20);}'})
    assert error.value.code == "new_missing_references"


@pytest.mark.parametrize("change", ["content", "include", "new_catalog", "delete"])
def test_dependency_changes_during_validation_are_rejected(project, tmp_path, monkeypatch, change):
    from sc2_mcp import cross_validation

    root, _ = project
    dependency = tmp_path / "dep.SC2Mod"
    dependency.mkdir()
    data = put(dependency, "Base.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="External"/></Catalog>')
    manifest = put(dependency, "Base.SC2Data/GameData.xml", '<Includes/>')
    original = cross_validation._catalog_graph
    calls = 0

    def changing_graph(session):
        nonlocal calls
        result = original(session)
        calls += 1
        if calls == 2:
            if change == "content":
                data.write_bytes(b'<Catalog><CUnit id="Changed"/></Catalog>')
            elif change == "include":
                manifest.write_bytes(b'<Includes><!-- changed --></Includes>')
            elif change == "new_catalog":
                put(dependency, "Base.SC2Data/GameData/WeaponData.xml", '<Catalog><CWeapon id="Added"/></Catalog>')
            else:
                data.unlink()
        return result

    monkeypatch.setattr(cross_validation, "_catalog_graph", changing_graph)
    with pytest.raises(SC2Error) as error:
        check(project, {"MapScript.galaxy": b'void f(){}'}, [dependency])
    assert error.value.code == "reference_dependency_changed"


def test_catalog_session_fingerprints_are_loaded_bytes_including_empty_manifests(project):
    from sc2_mcp.storage import digest

    root, _ = project
    manifest = put(root, "Base.SC2Data/GameData.xml", '<Includes/>')
    session = CatalogSession([root])
    expected = session.file_fingerprints()
    assert expected[str(manifest.resolve())] == digest(b'<Includes/>')
    manifest.write_bytes(b'<Includes><!-- later edit --></Includes>')
    assert session.file_fingerprints() == expected
    expected.clear()
    assert session.file_fingerprints()
