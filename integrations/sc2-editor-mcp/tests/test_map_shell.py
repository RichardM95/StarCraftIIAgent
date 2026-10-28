import struct
import xml.etree.ElementTree as ET

from sc2_mcp.map_shell import inspect_map_shell


def _version(fourcc=b"cdesipam"):
    return fourcc + struct.pack("<9I", 2, 97426, 5, 0, 15, 97426, 1, 1783594777, 1)


def _map(root, *, objects=True, regions=True, mapinfo=True, mapinfo_version=True):
    root.mkdir()
    (root / "DocumentInfo").write_bytes(b"doc")
    (root / "DocumentHeader").write_bytes(b"header")
    entries = [
        '<DataComponent Type="info">DocumentInfo</DataComponent>',
        '<DataComponent Type="mapi">MapInfo</DataComponent>',
        '<DataComponent Type="terr">t3Terrain.xml</DataComponent>',
    ]
    (root / "t3Terrain.xml").write_bytes(b"<Terrain/>")
    if mapinfo:
        data = bytearray(24)
        data[:4] = b"IpaM"
        struct.pack_into("<I", data, 4, 39)
        struct.pack_into("<I", data, 16, 128)
        struct.pack_into("<I", data, 20, 128)
        (root / "MapInfo").write_bytes(data)
    if mapinfo_version:
        (root / "MapInfo.version").write_bytes(_version())
    if objects:
        entries.append('<DataComponent Type="plob">Objects</DataComponent>')
        (root / "Objects").write_bytes(b"<PlacedObjects/>")
        (root / "Objects.version").write_bytes(_version(b"cdesbolp"))
    if regions:
        entries.append('<DataComponent Type="regi">Regions</DataComponent>')
        (root / "Regions").write_bytes(b"<Regions/>")
        (root / "Regions.version").write_bytes(_version(b"cdesiger"))
    xml = "<?xml version=\"1.0\"?><Components>" + "".join(entries) + "</Components>"
    (root / "ComponentList.SC2Components").write_text(xml, encoding="utf-8")


def test_valid_complete_shell_is_passed(tmp_path):
    root = tmp_path / "map"
    _map(root)
    result = inspect_map_shell(root)
    assert result["verdict"] == "passed"
    assert result["errors"] == []
    assert all(item["format"] == "sc2_component_version_v2" for item in result["version_sidecars"] if item["present"])


def test_declared_objects_without_sidecar_is_blocked_and_repairable(tmp_path):
    root = tmp_path / "map"
    _map(root)
    (root / "Objects.version").unlink()
    result = inspect_map_shell(root)
    assert result["verdict"] == "blocked"
    assert any(item["code"] == "missing_component_version" for item in result["errors"])
    repair = result["repairability"]["safe_static_repair"]
    assert repair == []
    assert any(item["path"] == "Objects.version" for item in result["repairability"]["requires_native_source"])


def test_missing_mapinfo_is_blocked_without_guessing(tmp_path):
    root = tmp_path / "map"
    _map(root, mapinfo=False, mapinfo_version=False)
    result = inspect_map_shell(root)
    assert result["verdict"] == "blocked"
    assert any(item["code"] == "missing_mapinfo" for item in result["errors"])
    assert result["repairability"]["safe_static_repair"] == []
    assert any(item["path"] == "MapInfo" for item in result["repairability"]["requires_native_source"])


def test_unknown_sidecar_is_reported_as_native_editor_boundary(tmp_path):
    root = tmp_path / "map"
    _map(root)
    (root / "Regions.version").write_bytes(b"unknown")
    result = inspect_map_shell(root)
    assert result["verdict"] == "needs_native_editor"
    assert any(item["path"] == "Regions.version" for item in result["repairability"]["unsupported"])


def test_approved_native_mapinfo_without_mapinfo_version_is_allowed(tmp_path):
    root = tmp_path / "map"
    _map(root, mapinfo_version=False, objects=False, regions=False)
    result = inspect_map_shell(root)
    assert result["verdict"] == "passed"
    assert result["mapinfo"]["format"] == "native_mapinfo_binary"
    assert result["mapinfo"]["payload_version"] == 39
    assert result["mapinfo"]["dimensions"] == [128, 128]


def test_declared_component_missing_and_component_list_xml_error(tmp_path):
    root = tmp_path / "map"
    _map(root)
    (root / "Objects").unlink()
    (root / "Objects.version").unlink()
    result = inspect_map_shell(root)
    assert any(item["code"] == "declared_component_missing" for item in result["errors"])
    (root / "ComponentList.SC2Components").write_bytes(b"<broken")
    result = inspect_map_shell(root)
    assert result["verdict"] == "blocked"
    assert any(item["code"] == "invalid_component_list" for item in result["errors"])
