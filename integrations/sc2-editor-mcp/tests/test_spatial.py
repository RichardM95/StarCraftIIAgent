from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.spatial import (inspect_spatial, plan_object_add, plan_object_edit,
                             plan_object_remove, plan_region_edit)


OBJECTS = (b'<?xml version="1.0" encoding="utf-8"?>\r\n'
           b'<PlacedObjects Version="27">\r\n'
           b'    <!-- keep <ObjectPoint Id="7"/> and bytes -->\r\n'
           b'    <ObjectPoint Id="7" Position="1,2,0" Type="Normal" Name="East &amp; West"/>\r\n'
           b'    <ObjectDoodad Id=\'8\' Position="4,5,0" Scale="1,1,1" Type="Rock">\r\n'
           b'        <Flag Index="HeightAbsolute" Value="1"/>\r\n'
           b'    </ObjectDoodad>\r\n'
           b'    <ObjectUnit Id="9" Position="3,2,0" UnitType="Marine"/>\r\n'
           b'</PlacedObjects>\r\n')
REGIONS = (b'<?xml version="1.0" encoding="utf-8"?>\r\n<Regions>\r\n'
           b'    <region id="1"><name value="Start"/><shape type="rect"><quad value="1,2,3,4"/></shape></region>\r\n'
           b'    <region id="2"><name value="Circle"/><shape type="circle"><radius value="4"/></shape></region>\r\n'
           b'</Regions>\r\n')


@pytest.fixture
def project(tmp_path):
    (tmp_path / "Objects").write_bytes(OBJECTS)
    (tmp_path / "Regions").write_bytes(REGIONS)
    return tmp_path


def test_inspection_uses_xml_not_comment_matches(project):
    result = inspect_spatial(project)
    assert result["counts"] == {"ObjectPoint": 1, "ObjectDoodad": 1, "ObjectUnit": 1, "region": 2}
    assert result["objects"][0]["attributes"]["Name"] == "East & West"
    assert inspect_spatial(project, "point")["counts"] == {"ObjectPoint": 1}


def test_edit_preserves_exact_unrelated_bytes_and_quote_style(project):
    changes = plan_object_edit(project, "8", {"Position": "5,6,0", "Name": 'A"B<C&D'})
    expected = OBJECTS.replace(b'Id=\'8\' Position="4,5,0"', b'Id=\'8\' Position="5,6,0"')
    expected = expected.replace(b'Type="Rock">', b'Type="Rock" Name="A&quot;B&lt;C&amp;D">')
    assert changes == {"Objects": expected}
    assert (project / "Objects").read_bytes() == OBJECTS
    assert ET.fromstring(changes["Objects"])[1].attrib["Name"] == 'A"B<C&D'
    assert plan_object_edit(project, "7", {"Position": "1,2,0"}) == {}


@pytest.mark.parametrize("attrs", [{"Id": "10"}, {"Position": "NaN,2,3"}, {"Position": "1,2"},
                                    {"Scale": "1,0,1"}, {"Rotation": "inf"}, {"Name": "a\nb"},
                                    {"UnknownInjectedField": "true"}])
def test_reject_bad_attributes_and_id_changes(project, attrs):
    with pytest.raises(SC2Error):
        plan_object_edit(project, "8", attrs)


def test_add_and_remove_leave_source_unchanged(project):
    changes = plan_object_add(project, "unit", {"Position": "4,5,0", "UnitType": "Marine"})
    parsed = ET.fromstring(changes["Objects"])
    assert parsed[-1].attrib == {"Id": "1", "Position": "4,5,0", "UnitType": "Marine"}
    assert changes["Objects"].replace(b'    <ObjectUnit Id="1" Position="4,5,0" UnitType="Marine"/>\r\n', b"") == OBJECTS
    deleted = plan_object_remove(project, "8")["Objects"]
    assert b"HeightAbsolute" not in deleted
    assert deleted == OBJECTS.replace(OBJECTS[OBJECTS.index(b"<ObjectDoodad"):OBJECTS.index(b"</ObjectDoodad>") + len(b"</ObjectDoodad>")], b"")
    assert (project / "Objects").read_bytes() == OBJECTS


def test_add_empty_document_and_duplicate_id_guard(project):
    (project / "Objects").write_bytes(b'<PlacedObjects Version="27"/>')
    value = plan_object_add(project, "ObjectPoint", {"Id": "23", "Position": "1,2,0", "Type": "Normal"})
    assert ET.fromstring(value["Objects"])[0].attrib["Id"] == "23"
    (project / "Objects").write_bytes(OBJECTS)
    with pytest.raises(SC2Error, match="ID 已存在"):
        plan_object_add(project, "point", {"Id": "7", "Position": "1,2,0", "Type": "Normal"})


@pytest.mark.parametrize("script", [b'void f(){ point p = PointFromId(7); }',
                                    b'void f(){ point p = PointFromId(0x7); }',
                                    b'void f(){ string p = "East & West"; }'])
def test_remove_rejects_literal_galaxy_refs(project, script):
    (project / "MapScript.galaxy").write_bytes(script)
    with pytest.raises(SC2Error) as error:
        plan_object_remove(project, "7")
    assert error.value.code == "spatial_reference"
    assert error.value.details["references"][0]["source"] == "MapScript.galaxy"


def test_ignore_commented_and_quoted_calls_but_scan_includes(project):
    (project / "MapScript.galaxy").write_text('// PointFromId(7);\nstring s="PointFromId(7)"; /* PointFromId(7) */', encoding="utf-8")
    assert plan_object_remove(project, "7")
    (project / "extra.galaxy").write_text("point f(){return PointFromId(7);}", encoding="utf-8")
    with pytest.raises(SC2Error):
        plan_object_remove(project, "7")


def test_same_id_in_different_spatial_namespace_is_not_a_reference(project):
    (project / "MapScript.galaxy").write_text("region r=RegionFromId(7); unit u=UnitFromId(7);", encoding="utf-8")
    assert plan_object_remove(project, "7")


@pytest.mark.parametrize("trigger", [b'<TriggerData><Value Type="point">7</Value></TriggerData>',
                                     b'<TriggerData><Value Type="point" Id="7"/></TriggerData>',
                                     b'<TriggerData><Value>East &amp; West</Value></TriggerData>'])
def test_trigger_literal_refs_block_removal(project, trigger):
    (project / "Triggers").write_bytes(trigger)
    with pytest.raises(SC2Error) as error:
        plan_object_remove(project, "7")
    assert error.value.code == "spatial_reference"


def test_group_membership_blocks_removal(project):
    value = OBJECTS.replace(b"</PlacedObjects>", b'<Group Id="20" Type="ObjectDoodad" Name="g"><GroupObject Id="8"/></Group></PlacedObjects>')
    (project / "Objects").write_bytes(value)
    with pytest.raises(SC2Error) as error:
        plan_object_remove(project, "8")
    assert error.value.details["references"][-1]["kind"] == "group_membership"
    assert plan_object_remove(project, "20")


def test_name_refs_prevent_rename_but_not_move(project):
    (project / "MapScript.galaxy").write_text('string s = "East & West";', encoding="utf-8")
    with pytest.raises(SC2Error):
        plan_object_edit(project, "7", {"Name": "new"})
    assert plan_object_edit(project, "7", {"Position": "1,4,0"})


def test_region_edit_preserves_other_geometry_and_escapes_name(project):
    result = plan_region_edit(project, 1, name='A&B"', rect=[-1, -2, 4, 5])
    expected = REGIONS.replace(b'value="Start"', b'value="A&amp;B&quot;"').replace(b'value="1,2,3,4"', b'value="-1,-2,4,5"')
    assert result == {"Regions": expected}
    assert (project / "Regions").read_bytes() == REGIONS
    with pytest.raises(SC2Error) as error:
        plan_region_edit(project, 2, rect=[1, 2, 3, 4])
    assert error.value.code == "unsupported_region_schema"


@pytest.mark.parametrize("rect", [[0, 0, 0, 2], [2, 0, 1, 2], [0, 0, 1, float("nan")], [False, 0, 1, 2], [1, 2, 3]])
def test_bad_region_rects(project, rect):
    with pytest.raises(SC2Error):
        plan_region_edit(project, 1, rect=rect)


def test_region_name_reference_guard_preserves_stable_id(project):
    (project / "MapScript.galaxy").write_text('region r=RegionFromId(1); string n="Start";', encoding="utf-8")
    with pytest.raises(SC2Error):
        plan_region_edit(project, 1, name="New")
    candidate = plan_region_edit(project, 1, rect=[0, 0, 10, 10])["Regions"]
    assert b'id="1"' in candidate


def test_duplicate_ids_fail_writes_and_inspection_explains(project):
    (project / "Objects").write_bytes(OBJECTS.replace(b'Id="9"', b'Id="7"'))
    assert inspect_spatial(project)["diagnostics"][0]["code"] == "duplicate_spatial_id"
    with pytest.raises(SC2Error):
        plan_object_edit(project, "8", {"Position": "0,0,0"})


def test_forbid_dtd_and_unsupported_camera_creation(project):
    with pytest.raises(SC2Error) as error:
        plan_object_add(project, "Camera", {"Name": "C"})
    assert error.value.code == "unsupported_spatial_schema"
    (project / "Objects").write_bytes(b'<!DOCTYPE PlacedObjects [<!ENTITY a "hello">]><PlacedObjects/>')
    with pytest.raises(SC2Error) as error:
        inspect_spatial(project)
    assert error.value.code == "unsupported_xml"


def test_observed_camera_attributes_can_be_edited(project):
    camera = b'<Camera Id="10" Name="Shot" Distance="12" Position="1,2,3"/>'
    (project / "Objects").write_bytes(OBJECTS.replace(b"</PlacedObjects>", camera + b"</PlacedObjects>"))
    value = plan_object_edit(project, "10", {"Distance": "14"})["Objects"]
    assert camera.replace(b'12"', b'14"') in value
    assert plan_object_add(project, "Camera", {"Name": "Shot 2", "Distance": "12", "Position": "0,0,0"})


def test_backup_references_are_excluded(project):
    backups = project / "_codex_backups"
    backups.mkdir()
    (backups / "MapScript.galaxy").write_text("PointFromId(7)", encoding="utf-8")
    assert plan_object_remove(project, "7")
