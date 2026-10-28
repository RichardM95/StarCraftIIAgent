"""Exercise actual service/transaction gates using synthetic temporary maps only."""
from pathlib import Path

import pytest

import sc2_mcp.service as service_module
from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot
from test_terrain import make_terrain


TERRAIN_DATA = "Base.SC2Data/GameData/TerrainData.xml"
TEXT = "zhCN.SC2Data/LocalizedData/GameStrings.txt"


@pytest.fixture
def environment_project(tmp_path, monkeypatch):
    root = make_terrain(tmp_path / "independent.SC2Map")
    (root / "DocumentInfo").write_bytes(b"<DocInfo><Dependencies/></DocInfo>")
    (root / "MapScript.galaxy").write_bytes(b"void Init () {}\n")
    data = root / TERRAIN_DATA
    data.parent.mkdir(parents=True)
    data.write_bytes(b'<Catalog><CTerrain id="Test"><FogDensity value="0.01"/><Camera value="Dflt"/></CTerrain></Catalog>')
    (data.parent / "CameraData.xml").write_bytes(b'<Catalog><CCamera id="Dflt"/></Catalog>')
    text = root / TEXT
    text.parent.mkdir(parents=True)
    text.write_bytes(b"Title=Original\n")
    service = Service(tmp_path / "state")
    monkeypatch.setattr(service, "editor_conflict", lambda: None)
    key = service.projects.open(str(root), writable=True)["project_id"]
    yield service, key, root
    service.jobs.shutdown()


def operation(batch):
    edit = {"operation": "terrain_environment", "parameters": {"settings": {"FogDensity": "0.05"}}}
    if not batch:
        return edit["operation"], edit["parameters"]
    return "batch", {"edits": [
        {"operation": "localization_set", "parameters": {"updates": {"Title": "Candidate"}}}, edit,
    ]}


@pytest.mark.parametrize("batch", [False, True])
def test_default_is_candidate_only_even_when_preview_false(environment_project, batch):
    service, key, root = environment_project
    before = snapshot(root)
    name, parameters = operation(batch)
    result = service.edit(key, name, parameters, preview_only=False)
    assert result["state"] == "prepared"
    assert result["write_deferred"]["code"] == "terrain_not_accepted"
    assert snapshot(root) == before
    candidate = Path(result["candidate"]) / TERRAIN_DATA
    assert b'value="0.05"' in candidate.read_bytes()
    assert result["previews"]["after"]["editor_render"] is False


@pytest.mark.parametrize("batch", [False, True])
def test_explicit_preview_still_wins_over_experimental_opt_in(environment_project, batch):
    service, key, root = environment_project
    before = snapshot(root)
    result = service.edit(key, *operation(batch), preview_only=True, experimental_write=True)
    assert result["state"] == "prepared"
    assert snapshot(root) == before


@pytest.mark.parametrize("batch", [False, True])
def test_independent_experimental_commit_is_backed_up_and_rollback_restores(environment_project, batch):
    service, key, root = environment_project
    before = snapshot(root)
    old = (root / TERRAIN_DATA).read_bytes()
    result = service.edit(key, *operation(batch), preview_only=False, experimental_write=True)
    assert result["state"] == "committed"
    assert (Path(result["backup"]) / TERRAIN_DATA).read_bytes() == old
    assert (root / TERRAIN_DATA).read_bytes() == old.replace(b'value="0.01"', b'value="0.05"')
    changed_paths = {k for k, v in snapshot(root).items() if before.get(k) != v}
    assert changed_paths == ({TERRAIN_DATA, TEXT} if batch else {TERRAIN_DATA})
    service.transactions.rollback(result["change_id"], root)
    assert snapshot(root) == before


@pytest.mark.parametrize("batch", [False, True])
def test_formal_path_is_rejected_before_planning_or_preview(environment_project, monkeypatch, batch):
    service, key, root = environment_project
    # Redirect the formal-path sentinel to this synthetic temp fixture. The
    # real formal Keystone directory is never read, registered or touched.
    monkeypatch.setattr(service_module, "KEYSTONE", root)
    before = snapshot(root)
    def forbidden(*args, **kwargs):
        pytest.fail("Formal-map gate must reject before any planning or rendering")
    monkeypatch.setattr(service, "_plan_one", forbidden)
    monkeypatch.setattr(service_module, "render_terrain", forbidden)
    with pytest.raises(SC2Error) as error:
        service.edit(key, *operation(batch), experimental_write=True)
    assert error.value.code == "experimental_formal_map"
    assert snapshot(root) == before
    assert not (service.state / "changes").exists()


@pytest.mark.parametrize("batch", [False, True])
def test_environment_candidate_cannot_be_promoted(environment_project, batch):
    service, key, root = environment_project
    before = snapshot(root)
    result = service.edit(key, *operation(batch), preview_only=True)
    with pytest.raises(SC2Error) as error:
        service.apply_candidate(key, result["change_id"])
    assert error.value.code == "terrain_not_accepted"
    assert snapshot(root) == before
    assert service.transactions.read(result["change_id"])["state"] == "prepared"


def test_batch_file_guard_is_case_insensitive(environment_project):
    service, key, root = environment_project
    lower = root / "Base.SC2Data/GameData/terraindata.xml"
    original = root / TERRAIN_DATA
    # Two-step rename handles case-only renames on Windows and Linux.
    temporary = original.with_name("rename-intermediate.xml")
    original.rename(temporary)
    temporary.rename(lower)
    before = snapshot(root)
    result = service.edit(key, *operation(True), preview_only=True)
    assert any(entry["path"].endswith("/terraindata.xml") for entry in result["files"])
    with pytest.raises(SC2Error) as error:
        service.apply_candidate(key, result["change_id"])
    assert error.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


@pytest.mark.parametrize("batch", [False, True])
def test_running_editor_keeps_experimental_edits_as_candidates(environment_project, monkeypatch, batch):
    service, key, root = environment_project
    before = snapshot(root)
    monkeypatch.setattr(service, "editor_conflict", lambda: {"code": "editor_unsaved_state_unknown"})
    result = service.edit(key, *operation(batch), experimental_write=True)
    assert result["state"] == "prepared"
    assert result["write_deferred"]["code"] == "editor_unsaved_state_unknown"
    assert snapshot(root) == before


def test_nested_batch_is_rejected_and_cannot_hide_environment_operation(environment_project):
    service, key, root = environment_project
    before = snapshot(root)
    nested_name, nested_parameters = operation(True)
    with pytest.raises(SC2Error) as error:
        service.edit(key, "batch", {"edits": [{"operation": nested_name, "parameters": nested_parameters}]})
    assert error.value.code == "unsupported_operation"
    assert snapshot(root) == before


def test_readonly_registration_blocks_even_preview(environment_project):
    service, key, root = environment_project
    service.projects.open(str(root), writable=False)
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.edit(key, *operation(False), preview_only=True)
    assert error.value.code == "readonly_project"
    assert snapshot(root) == before


def catalog_operation(catalog, batch=False):
    parameters = {"catalog": catalog, "object_id": "Test", "field_path": "FogDensity" if catalog.casefold() == "terrain" else "EditorCategories", "value": "0.05" if catalog.casefold() == "terrain" else "NewCategory"}
    if batch:
        return "batch", {"edits": [{"operation": "catalog_set", "parameters": parameters}]}
    return "catalog_set", parameters


@pytest.mark.parametrize("catalog", ["Terrain", "terrain", "TerrainTex"])
@pytest.mark.parametrize("batch", [False, True])
def test_catalog_terrain_routes_require_experimental_opt_in(environment_project, catalog, batch):
    service, key, root = environment_project
    if catalog == "TerrainTex":
        (root / "Base.SC2Data/GameData/TerrainTexData.xml").write_bytes(b'<Catalog><CTerrainTex id="Test"><EditorCategories value="OldCategory"/></CTerrainTex></Catalog>')
    before = snapshot(root)
    result = service.edit(key, *catalog_operation(catalog, batch))
    assert result["state"] == "prepared"
    assert result["write_deferred"]["code"] == "terrain_not_accepted"
    assert snapshot(root) == before
    with pytest.raises(SC2Error) as error:
        service.apply_candidate(key, result["change_id"])
    assert error.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


@pytest.mark.parametrize("catalog", ["Terrain", "TerrainTex"])
@pytest.mark.parametrize("batch", [False, True])
def test_formal_catalog_terrain_routes_cannot_commit(environment_project, monkeypatch, catalog, batch):
    service, key, root = environment_project
    monkeypatch.setattr(service_module, "KEYSTONE", root)
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.edit(key, *catalog_operation(catalog, batch), experimental_write=True)
    assert error.value.code == "experimental_formal_map"
    assert snapshot(root) == before


@pytest.mark.parametrize("kind", ["CTerrain", "CTerrainTex"])
@pytest.mark.parametrize("batch", [False, True])
def test_arbitrary_xml_import_cannot_commit_or_promote_terrain_definitions(environment_project, tmp_path, kind, batch):
    service, key, root = environment_project
    source = tmp_path / "environment-fragment.xml"
    source.write_bytes(f'<Catalog><{kind} id="Imported"/></Catalog>'.encode())
    parameters = {"source": str(source), "destination": "Assets/ArbitraryVisualDefinitions.xml"}
    request = ("batch", {"edits": [{"operation": "asset_import", "parameters": parameters}]}) if batch else ("asset_import", parameters)
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.edit(key, *request, experimental_write=True)
    assert error.value.code == "terrain_operation_required"
    assert snapshot(root) == before
    result = service.edit(key, *request, preview_only=True)
    assert result["state"] == "prepared"
    with pytest.raises(SC2Error) as error:
        service.apply_candidate(key, result["change_id"])
    assert error.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


def test_replacing_terrain_definition_with_other_xml_still_requires_gate(environment_project, tmp_path):
    service, key, root = environment_project
    target = root / "Assets/ArbitraryVisualDefinitions.xml"
    target.parent.mkdir(parents=True)
    target.write_bytes(b'<Catalog><CTerrain id="HiddenInInclude"/></Catalog>')
    source = tmp_path / "empty.xml"
    source.write_bytes(b'<Catalog/>')
    parameters = {"source": str(source), "destination": target.relative_to(root).as_posix(), "overwrite": True}
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.edit(key, "asset_import", parameters)
    assert error.value.code == "terrain_operation_required"
    assert snapshot(root) == before
    result = service.edit(key, "asset_import", parameters, preview_only=True)
    with pytest.raises(SC2Error) as error:
        service.apply_candidate(key, result["change_id"])
    assert error.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


def test_nonterrain_xml_import_remains_available(environment_project, tmp_path):
    service, key, root = environment_project
    source = tmp_path / "model.xml"
    source.write_bytes(b'<Catalog><!-- CTerrain is mentioned but not defined --><CModel id="Decoration"/></Catalog>')
    result = service.edit(key, "asset_import", {"source": str(source), "destination": "Assets/Reference.xml"})
    assert result["state"] == "committed"
    assert (root / "Assets/Reference.xml").read_bytes() == source.read_bytes()


def test_catalog_terrain_mod_without_map_components_needs_no_preview_renderer(environment_project, monkeypatch):
    service, key, root = environment_project
    for path in list(root.iterdir()):
        if path.name.startswith(("t3", "CellAttribute_")):
            path.unlink()
    monkeypatch.setattr(service_module, "render_terrain", lambda *a, **k: pytest.fail("A component mod has no terrain grid to render"))
    before = snapshot(root)
    candidate = service.edit(key, *catalog_operation("Terrain"))
    assert candidate["state"] == "prepared"
    assert "previews" not in candidate
    assert snapshot(root) == before
    result = service.edit(key, *catalog_operation("Terrain"), experimental_write=True)
    assert result["state"] == "committed"
    assert "previews" not in result
