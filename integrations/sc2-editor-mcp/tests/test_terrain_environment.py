import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.terrain_environment import plan_environment


NAME = "Base.SC2Data/GameData/TerrainData.xml"


def fixture(root, content=None, terrain_id="Char2"):
    (root / "t3Terrain.xml").write_text(f'<terrain version="115"><heightMap tileSet="{terrain_id}"/></terrain>', encoding="utf-8")
    if content is not None:
        p = root / NAME
        p.parent.mkdir(parents=True)
        p.write_bytes(content)
    return root


def test_exact_replacement_preserves_other_bytes_and_maps(tmp_path):
    raw = (b"\xef\xbb\xbf<?xml version='1.0' encoding='utf-8'?>\r\n<Catalog>\r\n"
           b"<!-- <CTerrain id='Char2'><Lighting value='decoy'/></CTerrain> -->\r\n"
           b"  <CTerrain id='Other'><Lighting value='IceWorld'/></CTerrain>\r\n"
           b"  <CTerrain id='Char2' parent='Parent'>\r\n"
           b"    <Lighting note=' value=\"decoy\" >' value='IceWorld'/>\r\n"
           b"    <Camera value='Dflt'/><Gravity value='-9.8'/><CreepSettingsArray index='High' value='keep'/>\r\n"
           b"  </CTerrain>\r\n</Catalog>\r\n")
    root = fixture(tmp_path, raw)
    changed = plan_environment(root, {"Lighting": 'Sky&"Light'})
    assert set(changed) == {NAME}
    assert changed[NAME] == raw.replace(b"value='IceWorld'/>\r\n", b"value='Sky&amp;&quot;Light'/>\r\n")
    assert (root / NAME).read_bytes() == raw
    assert ET.fromstring(changed[NAME]).find("CTerrain[@id='Char2']/Lighting").get("value") == 'Sky&"Light'


def test_noop_keeps_entity_spelling(tmp_path):
    root = fixture(tmp_path, b'<Catalog><CTerrain id="Char2"><Lighting value="&#65;"/></CTerrain></Catalog>')
    assert plan_environment(root, {"Lighting": "A"}) == {}
    assert plan_environment(root, {}) == {}


def test_new_fields_preserve_creep_camera_and_unknown_content(tmp_path):
    raw = b'<Catalog>\n  <CTerrain id="Char2">\n    <Camera value="Dflt"/>\n    <!-- keep -->\n    <CreepSettingsArray index="High" value="1"/>\n  </CTerrain>\n</Catalog>'
    changed = plan_environment(fixture(tmp_path, raw), {"FixedSkyboxModel": "", "FogColor": "255,56,90,118", "FogStartingHeight": "-13", "FogEnabled": "1"})[NAME]
    assert raw.split(b"  </CTerrain>")[0] in changed
    node = ET.fromstring(changed).find("CTerrain")
    assert node.find("FixedSkyboxModel").get("value") == ""
    assert node.find("Camera").get("value") == "Dflt"
    assert node.find("FogStartingHeight").get("value") == "-13"


def test_create_missing_file_without_writing(tmp_path):
    root = fixture(tmp_path)
    changed = plan_environment(root, {"FixedSkyboxActor": "KorhalFallingSkybox"})
    assert not (root / NAME).exists()
    node = ET.fromstring(changed[NAME]).find("CTerrain")
    assert node.get("id") == "Char2"
    assert node.find("FixedSkyboxActor").get("value") == "KorhalFallingSkybox"


@pytest.mark.parametrize("raw", [b'<Catalog/>', b'<Catalog><CTerrain id="Other"/></Catalog>'])
def test_append_missing_terrain_object(tmp_path, raw):
    changed = plan_environment(fixture(tmp_path, raw), {"Lighting": "Sky"})[NAME]
    doc = ET.fromstring(changed)
    assert doc.find("CTerrain[@id='Char2']/Lighting").get("value") == "Sky"
    if b'Other' in raw:
        assert b'<CTerrain id="Other"/>' in changed


@pytest.mark.parametrize("raw", [
    b'<Catalog><CTerrain id="Char2"/><CTerrain id="Char2"/></Catalog>',
    b'<Catalog><CTerrain id="Char2"><Lighting value="A"/><Lighting value="B"/></CTerrain></Catalog>',
    b'<Catalog><CTerrain id="Char2"><Lighting index="0" value="A"/></CTerrain></Catalog>',
    b'<Catalog><CTerrain id="Char2"><Lighting removed="1"/></CTerrain></Catalog>',
    b'<Catalog><CTerrain id="Char2"><Lighting><Child/></Lighting></CTerrain></Catalog>',
    b'<Catalog><CTerrain id="Char2" removed="1"/></Catalog>',
    b'<Other/>', b'<!DOCTYPE Catalog><Catalog/>',
])
def test_ambiguous_or_unsupported_xml_rejected(tmp_path, raw):
    root = fixture(tmp_path, raw)
    with pytest.raises(SC2Error):
        plan_environment(root, {"Lighting": "Sky"})
    assert (root / NAME).read_bytes() == raw


@pytest.mark.parametrize("settings", [
    {"Gravity": "-9.8"}, {"Camera": "SpacePlatform"}, {"BlendTextures": "x"},
    {"FogEnabled": "true"}, {"HideLowestLevel": "2"}, {"FogDensity": "NaN"},
    {"FogFalloff": "Infinity"}, {"FogStartingHeight": ""}, {"FogDensity": "xyz"},
    {"FogDensity": "1_0"},
    {"FogColor": "256,0,0,0"}, {"FogColor": "1,2,3"}, {"FogColor": "1,2,3,4.0"},
    {"FogColor": "1,2,3,-4"}, {"Lighting": "a\0b"}, {"Lighting": "bad\ud800"},
    {"Lighting": "bad\ufffe"}, {"Lighting": 5}, [],
])
def test_invalid_values_and_gameplay_fields_rejected(tmp_path, settings):
    root = fixture(tmp_path)
    with pytest.raises(SC2Error):
        plan_environment(root, settings)
    assert not (root / NAME).exists()


@pytest.mark.parametrize("xml", [b'<terrain/>', b'<terrain><heightMap/></terrain>', b'<terrain><heightMap tileSet="A"/><heightMap tileSet="B"/></terrain>'])
def test_missing_or_ambiguous_tileset_rejected(tmp_path, xml):
    (tmp_path / "t3Terrain.xml").write_bytes(xml)
    with pytest.raises(SC2Error):
        plan_environment(tmp_path, {"Lighting": "Sky"})


def test_case_preserved_output_path(tmp_path):
    fixture(tmp_path)
    file = tmp_path / "base.sc2data/gamedata/terraindata.XML"
    file.parent.mkdir(parents=True)
    file.write_bytes(b'<Catalog><CTerrain id="Char2"/></Catalog>')
    assert set(plan_environment(tmp_path, {"Lighting": "Sky"})) == {"base.sc2data/gamedata/terraindata.XML"}


def test_all_supported_fields_and_explicit_inherited_link_clear(tmp_path):
    root = fixture(tmp_path, b'<Catalog><CTerrain id="Char2"><FixedSkyboxActor value="Old"/></CTerrain></Catalog>')
    values = {"Lighting": "KorhalPlatformEx2", "Ambience": "Ambience_Space", "FixedSkyboxActor": "",
              "FixedSkyboxModel": "", "NonFixedSkyboxModel": "", "FogEnabled": "1",
              "FogColor": "255,56,90,118", "FogDensity": "5e-2", "FogFalloff": ".18",
              "FogStartingHeight": "-13", "HideLowestLevel": "1"}
    changed = plan_environment(root, values)[NAME]
    assert {node.tag:node.get("value") for node in ET.fromstring(changed).find("CTerrain")} == values


def test_new_field_keeps_crlf_without_rewriting_existing_nodes(tmp_path):
    raw = b'<Catalog>\r\n\t<CTerrain id="Char2">\r\n\t\t<Lighting value="Old"/>\r\n\t</CTerrain>\r\n</Catalog>\r\n'
    changed = plan_environment(fixture(tmp_path, raw), {"FogEnabled": "1"})[NAME]
    insertion = b'\t\t<FogEnabled value="1"/>\r\n'
    assert changed.count(insertion) == 1
    assert changed.replace(insertion, b"") == raw


def test_empty_settings_does_not_propose_new_file(tmp_path):
    assert plan_environment(fixture(tmp_path), {}) == {}
