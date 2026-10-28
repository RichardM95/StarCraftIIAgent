import xml.etree.ElementTree as ET
import struct
import numpy as np
import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.spatial_batch import plan_place_objects, sample_height
from test_terrain import make_terrain


def test_grounded_batch_registers_native_component_without_mutating_source(tmp_path):
    root=make_terrain(tmp_path/'map')
    metadata=b'cdesipam'+struct.pack('<9I',2,97426,5,0,15,97426,1,1783594777,1)
    (root/'MapInfo.version').write_bytes(metadata)
    component=b'<?xml version="1.0"?><Components>\n    <DataComponent Type="terr">t3Terrain.xml</DataComponent>\n</Components>'
    (root/'ComponentList.SC2Components').write_bytes(component)
    changes=plan_place_objects(root,[{'kind':'doodad','attributes':{'Type':'Rock','Position':'2.5,3.2,-0.1'}},
                                    {'kind':'point','attributes':{'Type':'StartLoc','Position':'4,4,0'}}])
    objects=ET.fromstring(changes['Objects'])
    assert objects.get('Version')=='27'
    assert changes['Objects.version']==b'cdesbolp'+metadata[8:]
    assert not (root/'Objects.version').exists()
    assert objects[0].get('Position')=='2.500000,3.200000,7.900000'
    assert objects[0].find('Flag').attrib=={'Index':'HeightAbsolute','Value':'1'}
    assert objects[1].get('Position')=='4,4,0'
    assert objects[1].find('Flag') is None
    assert not (root/'Objects').exists()
    assert (root/'ComponentList.SC2Components').read_bytes()==component
    assert ET.fromstring(changes['ComponentList.SC2Components']).findall('DataComponent')[1].get('Type')=='plob'


def test_existing_objects_bytes_preserved_and_ids_do_not_collide(tmp_path):
    root=make_terrain(tmp_path/'map')
    old=b'<PlacedObjects Version="27"><!-- preserve --><ObjectPoint Id="44" Type="Normal" Position="1,1,0"/></PlacedObjects>'
    (root/'Objects').write_bytes(old)
    (root/'Objects.version').write_bytes(b'opaque-existing-sidecar')
    (root/'ComponentList.SC2Components').write_bytes(b'<Components><DataComponent Type="plob">Objects</DataComponent></Components>')
    result=plan_place_objects(root,[{'kind':'unit','attributes':{'UnitType':'Marine','Position':'2,2,0'}}])
    assert result['Objects'].startswith(old.split(b'</PlacedObjects>')[0])
    assert ET.fromstring(result['Objects'])[-1].get('Id')=='45'
    assert set(result)=={'Objects'}
    assert (root/'Objects.version').read_bytes()==b'opaque-existing-sidecar'
    with pytest.raises(SC2Error):
        plan_place_objects(root,[{'kind':'unit','attributes':{'Id':'44','UnitType':'Marine','Position':'2,2,0'}}])


def test_bilinear_height_and_outside_rejection():
    grid=np.array([[0,2],[4,6]],dtype=float)
    assert sample_height(grid,.5,.5)==3
    assert sample_height(grid,1,1)==6
    for x,y in [(-.1,0),(2,0),(float('nan'),0)]:
        with pytest.raises(SC2Error):sample_height(grid,x,y)


def test_new_objects_require_known_native_save_metadata(tmp_path):
    root=make_terrain(tmp_path/'map')
    (root/'ComponentList.SC2Components').write_bytes(b'<Components/>')
    for data in (None, b'unknown', b'cdesipam'+struct.pack('<9I',99,1,2,3,4,5,6,7,8)):
        if data is not None:
            (root/'MapInfo.version').write_bytes(data)
        with pytest.raises(SC2Error, match='MapInfo.version'):
            plan_place_objects(root,[{'kind':'point','attributes':{'Type':'Normal','Position':'4,4,0'}}])
        assert not (root/'Objects').exists()


def test_numeric_grid_not_silently_passable_and_huge_radius():
    from sc2_mcp.pathing_audit import audit_grid
    with pytest.raises(SC2Error):audit_grid(np.full((3,3),float('nan')),[[0,0],[1,1]])
    assert audit_grid(np.ones((3,3),bool),[[0,0],[1,1]],1e100)['connected'] is False
