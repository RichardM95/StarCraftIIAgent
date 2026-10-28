from pathlib import Path

import pytest

from sc2_mcp import fixtures
from sc2_mcp.errors import SC2Error


def test_fixture_preserves_template_and_original_with_transaction(tmp_path, monkeypatch):
    source = tmp_path / "source.SC2Map"
    source.mkdir()
    (source / "DocumentInfo").write_bytes(b"<DocInfo/>\r\n")
    (source / "t3HeightMap").write_bytes(b"original")
    (source / "unknown.bin").write_bytes(b"\x00unknown\xff")
    monkeypatch.setattr(fixtures, "plan_terrain", lambda root, ops: {"t3HeightMap": b"changed"})
    class MockTerrain:
        def __init__(self, *args): pass
        def summary(self): return {"parsed": True}
    monkeypatch.setattr(fixtures, "Terrain", MockTerrain)
    monkeypatch.setattr(fixtures, "render_terrain", lambda *a: {"files": {}, "editor_render": False})
    result = fixtures.create_editor_validation_fixture(source, tmp_path / "validation")
    assert result["source_unchanged"]
    assert result["changed_files"] == ["t3HeightMap"]
    assert (source / "t3HeightMap").read_bytes() == b"original"
    assert (Path(result["original"]) / "t3HeightMap").read_bytes() == b"original"
    assert (Path(result["candidate"]) / "t3HeightMap").read_bytes() == b"changed"
    assert (Path(result["candidate"]) / "unknown.bin").read_bytes() == b"\x00unknown\xff"
    assert result["evidence"]["editor"] == "not_run"
    assert (Path(result["directory"]) / "fixture.json").is_file()


def test_fixture_rejects_output_within_source(tmp_path):
    source = tmp_path / "source.SC2Map"
    source.mkdir()
    (source / "DocumentInfo").write_text("<DocInfo/>")
    with pytest.raises(SC2Error) as exc:
        fixtures.create_editor_validation_fixture(source, source / "output")
    assert exc.value.code == "INVALID_FIXTURE_DESTINATION"
    assert not (source / "output").exists()
