import json
from pathlib import Path

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.projects import Projects
from sc2_mcp.storage import snapshot


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "map.SC2Map"
    root.mkdir()
    (root / "DocumentInfo").write_bytes(b"<DocInfo/>")
    (root / "ComponentList.SC2Components").write_bytes(b"<Components/>")
    (root / "MapScript.galaxy").write_bytes(b"void f(){}")
    return root, Projects(tmp_path / "state")


def test_readonly_registration_persists_across_instances(setup):
    root, registry = setup
    record = registry.open(str(root), writable=False)
    other = Projects(registry.state)
    assert other.get(record["project_id"])["writable"] is False
    with pytest.raises(SC2Error) as error:
        other.get(record["project_id"], write=True)
    assert error.value.code == "readonly_project"
    writable = registry.open(str(root), writable=True)
    assert other.get(record["project_id"], write=True)["writable"] is True
    assert writable["project_id"] == record["project_id"]
    assert len(other.list()) == 1
    registry.open(str(root), writable=False)
    with pytest.raises(SC2Error):
        other.get(record["project_id"], write=True)


def test_missing_shell_metadata_is_reported_without_invention(setup):
    root, registry = setup
    result = registry.open(str(root))
    assert result["metadata"]["missing"] == ["DocumentHeader", "MapInfo"]
    assert result["warnings"][0]["code"] == "missing_shell_metadata"
    assert not (root / "DocumentHeader").exists()


@pytest.mark.parametrize("kwargs", [{"writable": "false"}, {"search_roots": "somewhere"}, {"profile": "other"}, {"search_roots": [None]}])
def test_invalid_registration_parameters(setup, kwargs):
    root, registry = setup
    with pytest.raises(SC2Error):
        registry.open(str(root), **kwargs)
    assert registry.list() == []


def test_clone_independent_hash_parity_without_service_metadata(setup, tmp_path):
    root, registry = setup
    (root / ".sc2-mcp").mkdir()
    (root / ".sc2-mcp/transaction.lock").write_bytes(b"internal")
    (root / "_codex_backups").mkdir()
    (root / "_codex_backups/old").write_bytes(b"old")
    record = registry.open(str(root))
    result = registry.clone(record["project_id"], str(tmp_path / "copy.SC2Map"))
    target = Path(result["root"])
    assert snapshot(root) == snapshot(target)
    assert not (target / ".sc2-mcp").exists()
    assert not (target / "_codex_backups").exists()
    assert result["writable"] is True
    (target / "MapScript.galaxy").write_bytes(b"changed")
    assert (root / "MapScript.galaxy").read_bytes() == b"void f(){}"


def test_clone_rejects_nested_or_existing_destination(setup, tmp_path):
    root, registry = setup
    record = registry.open(str(root))
    for destination in (root, root / "nested.SC2Map", tmp_path):
        with pytest.raises(SC2Error) as error:
            registry.clone(record["project_id"], str(destination))
        assert error.value.code == "invalid_destination"


def test_keystone_detection_cannot_be_disabled_by_generic_profile(setup):
    root, registry = setup
    (root / "MapScript.galaxy").write_bytes(b"int lib1_gv_mAX_CARD_ID = 123;")
    assert registry.open(str(root), profile="generic")["profile"] == "keystone"


def test_invalid_xml_and_wrong_root_are_not_component_maps(setup):
    root, registry = setup
    for value in (b"<bad>", b"<Other/>", b'<!DOCTYPE DocInfo [<!ENTITY x "1">]><DocInfo/>'):
        (root / "DocumentInfo").write_bytes(value)
        with pytest.raises(SC2Error):
            registry.open(str(root))
    assert registry.list() == []


def test_corrupt_registry_does_not_get_overwritten(setup):
    root, registry = setup
    registry.state.mkdir()
    registry.registry.write_text("[]", encoding="utf-8")
    with pytest.raises(SC2Error) as error:
        registry.open(str(root), writable=True)
    assert error.value.code == "invalid_registry"
    assert registry.registry.read_text("utf-8") == "[]"


def test_mod_shell_does_not_require_mapinfo(setup, tmp_path):
    _, registry = setup
    root = tmp_path / "test.SC2Mod"
    root.mkdir()
    (root / "DocumentInfo").write_bytes(b"<DocInfo/>")
    result = registry.open(str(root))
    assert result["kind"] == "mod"
    assert "MapInfo" not in result["metadata"]["missing"]


def test_archive_working_copy_is_content_addressed_and_preserves_mod_kind(setup, tmp_path, monkeypatch):
    _, registry = setup
    archive = tmp_path / "source.SC2Mod"
    archive.write_bytes(b"archive version 1")
    def extraction(source, destination):
        destination.mkdir(parents=True)
        (destination / "DocumentInfo").write_bytes(b"<DocInfo/>")
    monkeypatch.setattr("sc2_mcp.archives.extract_archive", extraction)
    first = registry.open(str(archive), writable=True)
    assert Path(first["root"]).suffix == ".SC2Mod"
    assert first["archive_source"] is True
    assert archive.read_bytes() == b"archive version 1"
    (Path(first["root"]) / "local-edit").write_bytes(b"saved")
    assert registry.open(str(archive))["root"] == first["root"]
    archive.write_bytes(b"archive version 2")
    second = registry.open(str(archive))
    assert first["project_id"] == second["project_id"]
    assert first["root"] != second["root"]
    assert (Path(first["root"]) / "local-edit").read_bytes() == b"saved"


def test_clone_detects_source_change_and_preserves_failed_candidate(setup, tmp_path, monkeypatch):
    root, registry = setup
    record = registry.open(str(root))
    import sc2_mcp.projects as module
    original = module.shutil.copy2
    changed = False
    def copy_and_mutate(source, target):
        nonlocal changed
        result = original(source, target)
        if not changed:
            changed = True
            (root / "MapScript.galaxy").write_bytes(b"external edit")
        return result
    monkeypatch.setattr(module.shutil, "copy2", copy_and_mutate)
    target = tmp_path / "failed-copy.SC2Map"
    with pytest.raises(SC2Error) as error:
        registry.clone(record["project_id"], str(target))
    assert error.value.code == "copy_verification_failed"
    assert target.is_dir()
    assert (root / "MapScript.galaxy").read_bytes() == b"external edit"
