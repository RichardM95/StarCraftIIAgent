import struct

import numpy as np
import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.terrain import Terrain
from sc2_mcp.terrain_fields import plan_terrain_fields
from test_terrain import make_terrain


def snapshot(root):
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def test_noop_preserves_unknown_texture_choice_and_entire_source(tmp_path):
    root = make_terrain(tmp_path)
    raw = bytearray((root / "t3SyncTextureInfo").read_bytes())
    raw[-8:] = struct.pack("<Q", 0xAABBCCDDEEFF0011)
    (root / "t3SyncTextureInfo").write_bytes(raw)
    before = snapshot(root)
    t = Terrain(root)
    assert plan_terrain_fields(root) == {}
    assert plan_terrain_fields(root, heights=t.heights, texture_weights=t.texture_weights(),
                               texture_palette={0: "A"}, ground_mask=t.pathing_layer("CellAttribute_Pnp"),
                               building_mask=t.pathing_layer("CellAttribute_Pnb")) == {}
    assert snapshot(root) == before


def test_local_height_preserves_residual_channels_headers_and_other_vertices(tmp_path):
    root = make_terrain(tmp_path)
    before = snapshot(root)
    t = Terrain(root)
    field = t.heights.copy()
    field[3:5, 8:11] += .25
    changes = plan_terrain_fields(root, heights=field)
    after = Terrain(root, changes)
    assert set(changes) == {"t3HeightMap", "t3SyncHeightMap"}
    assert np.count_nonzero(t.heights != after.heights) == 6
    assert np.all(after.heights[3:5, 8:11] == 8.25)
    assert np.array_equal(t.vertices[:, :, 1:], after.vertices[:, :, 1:])
    assert np.array_equal(t.sync[:, :, 1], after.sync[:, :, 1])
    unchanged = field == t.heights
    assert np.array_equal(t.vertices[unchanged], after.vertices[unchanged])
    assert changes["t3HeightMap"][:32] == before["t3HeightMap"][:32]
    assert changes["t3SyncHeightMap"][:64] == before["t3SyncHeightMap"][:64]
    assert snapshot(root) == before


def test_local_texture_update_across_blocks_preserves_other_sync_tiles(tmp_path):
    root = make_terrain(tmp_path)
    raw = bytearray((root / "t3SyncTextureInfo").read_bytes())
    raw[-8:] = struct.pack("<Q", 0xFFEEDDCCBBAA)
    (root / "t3SyncTextureInfo").write_bytes(raw)
    t = Terrain(root)
    weights = t.texture_weights()
    weights[0, 56:72, 56:72] = 3
    weights[1, 56:72, 56:72] = 12
    changes = plan_terrain_fields(root, texture_weights=weights)
    after = Terrain(root, changes)
    assert np.array_equal(after.texture_weights(), weights)
    old_sync, new_sync = t.sync_textures()[2], after.sync_textures()[2]
    changed_tiles = np.zeros((16, 16), dtype=bool)
    changed_tiles[7:9, 7:9] = True
    assert np.all(new_sync[changed_tiles] == 1)
    assert np.array_equal(new_sync[~changed_tiles], old_sync[~changed_tiles])
    assert changes["t3TextureMasks"][:64] == t.raw["t3TextureMasks"][:64]


def test_palette_growth_relocates_payload_without_changing_it(tmp_path):
    root = make_terrain(tmp_path)
    xml = (root / "t3Terrain.xml").read_bytes().replace(
        b'<texture i="1" name="B"/>', b"<!-- <texture i='1' name='decoy'/> -->\r\n<texture note=' name=\"DECOY\" >' i='1' name='B' extra='KEEP'/>")
    (root / "t3Terrain.xml").write_bytes(xml)
    before = Terrain(root)
    names, old_offset, old_sync = before.sync_textures()
    changes = plan_terrain_fields(root, texture_palette={1: "Long&New'Texture"})
    after = Terrain(root, changes)
    actual_names, new_offset, actual_sync = after.sync_textures()
    assert actual_names[1] == "Long&New'Texture"
    assert new_offset > old_offset
    assert np.array_equal(actual_sync, old_sync)
    assert changes["t3SyncTextureInfo"][new_offset:] == before.raw["t3SyncTextureInfo"][old_offset:]
    assert changes["t3Terrain.xml"] == xml.replace(b"name='B'", b"name='Long&amp;New&apos;Texture'")
    assert set(changes) == {"t3Terrain.xml", "t3SyncTextureInfo"}


def test_palette_and_weight_change_share_new_slot(tmp_path):
    root = make_terrain(tmp_path)
    xml = (root / "t3Terrain.xml").read_bytes().replace(b'name="B"', b'name=""')
    (root / "t3Terrain.xml").write_bytes(xml)
    raw = (root / "t3SyncTextureInfo").read_bytes().replace(b"A\0B\0C\0", b"A\0\0C\0", 1)
    (root / "t3SyncTextureInfo").write_bytes(raw)
    weights = Terrain(root).texture_weights()
    weights[0, :8, :8], weights[1, :8, :8] = 0, 15
    changes = plan_terrain_fields(root, texture_palette={1: "BelShirGrass"}, texture_weights=weights)
    after = Terrain(root, changes)
    assert after.sync_textures()[0][1] == "BelShirGrass"
    assert after.sync_textures()[2][0, 0] == 1
    assert np.array_equal(after.texture_weights(), weights)


def test_masks_only_change_requested_cells_and_preserve_header(tmp_path):
    root = make_terrain(tmp_path)
    t = Terrain(root)
    ground, building = t.pathing_layer("CellAttribute_Pnp"), t.pathing_layer("CellAttribute_Pnb")
    ground[5:7, 3:8] = 255
    building[10, 11] = 255
    changes = plan_terrain_fields(root, ground_mask=ground, building_mask=building)
    after = Terrain(root, changes)
    assert set(changes) == {"CellAttribute_Pnp", "CellAttribute_Pnb"}
    assert np.count_nonzero(after.pathing_layer("CellAttribute_Pnp")) == 10
    assert after.pathing_layer("CellAttribute_Pnb")[10, 11] == 255
    for name in changes:
        assert changes[name][:4] == t.raw[name][:4]


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, 1e300, -1e300, 1000, -1000])
def test_invalid_heights_rejected_without_writes(tmp_path, bad):
    root = make_terrain(tmp_path)
    before = snapshot(root)
    field = Terrain(root).heights.copy()
    field[2, 3] = bad
    with pytest.raises(SC2Error):
        plan_terrain_fields(root, heights=field)
    assert snapshot(root) == before


@pytest.mark.parametrize("kwargs", [
    {"heights": [[1, 2], [3]]}, {"heights": np.zeros((17, 17), dtype=bool)},
    {"texture_palette": {8: "A"}}, {"texture_palette": {3: "A"}},
    {"texture_palette": {True: "A"}}, {"texture_palette": {0: ""}},
    {"texture_palette": {0: "A\0B"}}, {"texture_palette": {0: "A\nB"}},
    {"texture_palette": {0: "\ud800"}}, {"texture_palette": []},
    {"texture_palette": {0: "Bad\ufffe"}},
    {"ground_mask": np.full((16, 16), 1, dtype=np.uint8)},
    {"building_mask": np.zeros((16, 16), dtype=float)},
])
def test_invalid_field_and_palette_inputs_rejected(tmp_path, kwargs):
    root = make_terrain(tmp_path)
    with pytest.raises(SC2Error):
        plan_terrain_fields(root, **kwargs)


@pytest.mark.parametrize("kind", ["float", "negative", "overflow", "sum", "empty_slot"])
def test_invalid_weights(tmp_path, kind):
    root = make_terrain(tmp_path)
    weights = Terrain(root).texture_weights().astype(np.int32)
    if kind == "float":
        weights = weights.astype(float)
    elif kind == "negative":
        weights[0, 0, 0], weights[1, 0, 0] = -1, 16
    elif kind == "overflow":
        weights[0, 0, 0] = 256
    elif kind == "sum":
        weights[0, 0, 0] = 14
    else:
        weights[0, 0, 0], weights[7, 0, 0] = 0, 15
    with pytest.raises(SC2Error):
        plan_terrain_fields(root, texture_weights=weights)


@pytest.mark.parametrize("name", ["CellAttribute_Pnp", "CellAttribute_Pnb"])
def test_missing_pathing_component_is_not_created(tmp_path, name):
    root = make_terrain(tmp_path)
    (root / name).unlink()
    kwargs = {"ground_mask" if name.endswith("Pnp") else "building_mask": np.zeros((16, 16), dtype=np.uint8)}
    with pytest.raises(SC2Error, match="缺少地形组件"):
        plan_terrain_fields(root, **kwargs)
    assert not (root / name).exists()


@pytest.mark.parametrize("mutation", ["duplicate", "multiple_sets", "mismatch", "version", "encoding"])
def test_unverified_or_inconsistent_xml_rejected(tmp_path, mutation):
    root = make_terrain(tmp_path)
    xml = (root / "t3Terrain.xml").read_bytes()
    if mutation == "duplicate":
        xml = xml.replace(b"</textureList>", b'<texture i="1" name="B"/></textureList>')
    elif mutation == "multiple_sets":
        xml = xml.replace(b"</textureList>", b'<texture i="8" name="D"/></textureList>')
    elif mutation == "mismatch":
        xml = xml.replace(b'name="B"', b'name="Other"')
    elif mutation == "version":
        xml = xml.replace(b'version="115"', b'version="113"')
    else:
        xml = b'<?xml version="1.0" encoding="iso-8859-1"?>' + xml
    (root / "t3Terrain.xml").write_bytes(xml)
    with pytest.raises(SC2Error):
        plan_terrain_fields(root, texture_palette={0: "NewA"})


@pytest.mark.parametrize("extra", [
    b'<textureSetList><textureSet i="0" name="Test"/><textureSet i="1" name="Other"/></textureSetList>',
    b'<blockTextureSetList><blockTextureSet i="0" tileSet="1"/></blockTextureSetList>',
    b'<textureList><texture i="4" name="D"/></textureList>',
])
def test_xml_other_texture_sets_and_duplicate_tables_rejected(tmp_path, extra):
    root = make_terrain(tmp_path)
    xml = (root / "t3Terrain.xml").read_bytes().replace(b"</heightMap>", extra + b"</heightMap>")
    (root / "t3Terrain.xml").write_bytes(xml)
    with pytest.raises(SC2Error):
        plan_terrain_fields(root, texture_palette={0: "NewA"})


def test_subquantum_height_change_is_exact_noop(tmp_path):
    root = make_terrain(tmp_path)
    t = Terrain(root)
    heights = t.heights.copy()
    heights[2, 3] += t.scale * .1
    assert plan_terrain_fields(root, heights=heights) == {}


def test_unchanged_xml_entity_spelling_is_preserved(tmp_path):
    root = make_terrain(tmp_path)
    xml = (root / "t3Terrain.xml").read_bytes().replace(b'name="A"', b'name="&#65;"')
    (root / "t3Terrain.xml").write_bytes(xml)
    assert plan_terrain_fields(root, texture_palette={0: "A"}) == {}
