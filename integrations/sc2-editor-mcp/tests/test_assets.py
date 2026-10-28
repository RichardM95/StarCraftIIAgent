import os
from pathlib import Path

import pytest

from sc2_mcp.assets import inspect_assets, missing_asset_references, plan_asset_import
from sc2_mcp.errors import SC2Error


def put(root, relative, data=b"asset"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_inventory_query_virtual_path_and_backups(tmp_path):
    put(tmp_path, "Assets/Textures/One.dds")
    put(tmp_path, "Base.SC2Assets/Assets/Models/Marine.m3")
    put(tmp_path, "_codex_backups/Assets/Textures/old.dds")
    result = inspect_assets(tmp_path)
    assert result["count"] == 2
    assert inspect_assets(tmp_path, "MARINE")["assets"][0]["logical_path"] == "Assets/Models/Marine.m3"
    assert result["collisions"] == []


def test_reference_audit_resolves_dependencies_and_records_sources(tmp_path):
    dependency = tmp_path / "dep.SC2Mod"
    project = tmp_path / "map.SC2Map"
    dependency.mkdir()
    project.mkdir()
    put(dependency, "Base.SC2Assets/Assets/Textures/Test.dds", b"dep")
    put(project, "Base.SC2Data/GameData/ModelData.xml",
        b'<Catalog><CModel id="M"><Model value="Assets\\Models\\Missing.m3"/><Texture value="assets/Textures/test.DDS"/>'
        b'<Texture value="Assets/Textures/@race@.dds"/></CModel></Catalog>')
    result = missing_asset_references([dependency, project])
    assert len(result["resolved"]) == len(result["missing"]) == len(result["unresolved"]) == 1
    assert result["resolved"][0]["resolved"]["root"] == str(dependency.resolve())
    assert result["missing"][0]["attribute"] == "value"
    assert result["unresolved"][0]["reason"] == "engine_macro"
    assert not result["complete"]


def test_later_root_overrides_and_same_root_collision_remains_unknown(tmp_path):
    low, high = tmp_path / "low", tmp_path / "high"
    low.mkdir(); high.mkdir()
    put(low, "Assets/Textures/a.dds", b"low")
    put(high, "Assets/Textures/a.dds", b"high")
    put(high, "Preload.xml", b'<Preload><Texture path="Assets/Textures/a.dds"/></Preload>')
    result = missing_asset_references([low, high])
    assert result["resolved"][0]["resolved"]["root"] == str(high.resolve())
    assert len(result["resolved"][0]["shadowed"]) == 1
    put(high, "zhCN.SC2Assets/Assets/Textures/a.dds", b"locale")
    result = missing_asset_references([low, high])
    assert not result["resolved"]
    assert result["unresolved"][0]["reason"] == "ambiguous_virtual_path"


def test_galaxy_literals_ignore_comments_and_handle_backslashes(tmp_path):
    put(tmp_path, "Assets/Textures/a.dds")
    put(tmp_path, "MapScript.galaxy",
        b'// "Assets/Textures/missing.dds"\nstring x="Assets\\\\Textures\\\\a.dds";\n'
        b'/* "Assets/Textures/missing2.dds" */\nstring y="Assets/Textures/b.dds";')
    result = missing_asset_references([tmp_path])
    assert result["reference_count"] == 2
    assert result["missing"][0]["line"] == 4
    assert len(result["resolved"]) == 1


def test_import_returns_candidate_without_writing_source_or_target(tmp_path):
    project = tmp_path / "map"
    project.mkdir()
    source = put(tmp_path, "source.dds", b"different")
    result = plan_asset_import(project, source, "Assets\\Textures\\new.dds")
    assert result == {"Assets/Textures/new.dds": b"different"}
    assert not list(project.iterdir())
    assert source.read_bytes() == b"different"


@pytest.mark.parametrize("destination", ["../outside.dds", "Assets/../outside.dds", "C:/a.dds", "/a.dds", "C:a.dds",
                                         "Assets/CON.dds", "Assets/a.dds:stream", "Assets/a.dds.",
                                         "Assets//a.dds", "_codex_backups/a.dds", "MapScript.galaxy"])
def test_import_path_guards(tmp_path, destination):
    project = tmp_path / "map"
    project.mkdir()
    source = put(tmp_path, "source.dds")
    with pytest.raises(SC2Error):
        plan_asset_import(project, source, destination)


def test_overwrite_requires_exact_path_and_returns_noop_for_identical(tmp_path):
    project = tmp_path / "map"
    project.mkdir()
    source = put(tmp_path, "source.dds", b"new")
    target = put(project, "Assets/Textures/a.dds", b"old")
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "Assets/Textures/a.dds")
    assert error.value.code == "asset_exists"
    assert plan_asset_import(project, source, "Assets/Textures/a.dds", overwrite=True) == {"Assets/Textures/a.dds": b"new"}
    assert target.read_bytes() == b"old"
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "Assets/Textures/A.dds", overwrite=True)
    assert error.value.code == "asset_collision"
    source.write_bytes(b"old")
    assert plan_asset_import(project, source, "Assets/Textures/a.dds", overwrite=True) == {}


def test_import_rejects_virtual_collision_and_parent_file(tmp_path):
    project = tmp_path / "map"
    project.mkdir()
    source = put(tmp_path, "source.dds")
    put(project, "Base.SC2Assets/Assets/Textures/a.dds")
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "Assets/Textures/a.dds", overwrite=True)
    assert error.value.code == "asset_collision"
    put(project, "Assets/Blocked", b"file")
    with pytest.raises(SC2Error):
        plan_asset_import(project, source, "Assets/Blocked/a.dds")


def test_import_preserves_parent_directory_spelling(tmp_path):
    project = tmp_path / "map"
    (project / "Assets/Textures").mkdir(parents=True)
    source = put(tmp_path, "source.dds")
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "assets/Textures/a.dds")
    assert error.value.code == "asset_collision"


def test_missing_source_and_no_roots_are_structured_errors(tmp_path):
    with pytest.raises(SC2Error) as error:
        plan_asset_import(tmp_path, tmp_path / "absent.dds", "Assets/a.dds")
    assert error.value.code == "asset_source_missing"
    with pytest.raises(SC2Error):
        missing_asset_references([])


def test_malformed_xml_is_diagnostic_not_clean_report(tmp_path):
    put(tmp_path, "bad.xml", b"<Catalog>")
    report = missing_asset_references([tmp_path])
    assert report["diagnostics"][0]["code"] == "invalid_xml"
    assert not report["complete"]


def test_symlink_cannot_redirect_import(tmp_path):
    project = tmp_path / "map"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    source = put(tmp_path, "source.dds")
    try:
        (project / "Assets").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links")
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "Assets/a.dds")
    assert error.value.code == "linked_asset_path"
    assert not list(outside.iterdir())


def test_hardlinked_target_cannot_be_overwritten(tmp_path):
    source = put(tmp_path, "source.dds")
    outside = put(tmp_path, "outside.dds")
    project = tmp_path / "map"
    (project / "Assets").mkdir(parents=True)
    try:
        os.link(outside, project / "Assets/a.dds")
    except OSError:
        pytest.skip("Hard links unavailable")
    with pytest.raises(SC2Error) as error:
        plan_asset_import(project, source, "Assets/a.dds", overwrite=True)
    assert error.value.code == "hardlinked_asset"
