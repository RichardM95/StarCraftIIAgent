import struct
from pathlib import Path

import numpy as np
import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.terrain import Terrain, plan_terrain, render_terrain


def make_terrain(root: Path, tiles=16):
    root.mkdir(parents=True, exist_ok=True)
    def grid(name, magic, version, header, w, h, payload, offset=8):
        raw=bytearray(header)
        raw[:4]=magic
        struct.pack_into('<I',raw,4,version)
        struct.pack_into('<II',raw,offset,w,h)
        raw[-4:]=b'KEEP'
        (root/name).write_bytes(raw+payload)
    (root/'t3Terrain.xml').write_text(
        f'<terrain version="115"><heightMap dim="{tiles+1} {tiles+1}" tileSet="Test">'
        '<vertData quantizeBias="16" quantizeScale="0.001"/>'
        '<textureList><texture i="0" name="A"/><texture i="1" name="B"/>'
        '<texture i="2" name="C"/></textureList></heightMap></terrain>',encoding='utf-8')
    vertices=np.zeros((tiles+1,tiles+1,3),dtype='<u2')
    vertices[:]=[20000,20000,1]
    sync=np.zeros_like(vertices[:,:,:2],dtype='<i2'); sync[:]=[2048,1]
    grid('t3HeightMap',b'HMAP',101,32,tiles+1,tiles+1,vertices.tobytes())
    grid('t3SyncHeightMap',b'SMAP',102,64,tiles+1,tiles+1,sync.tobytes())
    grid('t3SyncCliffLevel',b'CLIF',100,32,tiles,tiles,np.full((tiles,tiles),64,dtype='<u2').tobytes())
    grid('t3CellFlags',b'LFCT',102,32,tiles,tiles,np.full((tiles,tiles),2,dtype='u1').tobytes(),24)
    # Grid helper's unknown marker overlaps LFCT dimensions: restore only h.
    raw=bytearray((root/'t3CellFlags').read_bytes());struct.pack_into('<I',raw,28,tiles);(root/'t3CellFlags').write_bytes(raw)
    grid('t3TextureMasks',b'MASK',102,64,tiles*8,tiles*8,bytes([255])*(tiles*tiles*32)+bytes(tiles*tiles*32*7),12)
    (root/'t3SyncTextureInfo').write_bytes(struct.pack('<4s4I',b'RTXT',101,tiles,tiles,1)+b'A\0B\0C\0\0\0\0\0\0'+bytes(tiles*tiles*8))
    for name in ('CellAttribute_Pnp','CellAttribute_Pnb'):
        (root/name).write_bytes(struct.pack('<I',tiles*tiles*8)+bytes(tiles*tiles))
    return root


def test_noop_preserves_every_byte(tmp_path):
    root=make_terrain(tmp_path)
    assert plan_terrain(root,[{'op':'raise','rect':[2,2,4,4],'value':0}])=={}
    t=Terrain(root)
    assert t.encode_texture_weights(t.texture_weights())==(root/'t3TextureMasks').read_bytes()
    # Synchronized texture IDs may include editor-specific choice at a blend.
    # No-op painting must preserve these values instead of recomputing the grid.
    data=bytearray((root/'t3SyncTextureInfo').read_bytes())
    data[-8:]=struct.pack('<Q',2)
    (root/'t3SyncTextureInfo').write_bytes(data)
    assert plan_terrain(root,[{'op':'paint_texture','rect':[0,0,16,16],'texture':0,'strength':0}])=={}


def test_height_only_changes_selected_channel_and_synchronized_height(tmp_path):
    root=make_terrain(tmp_path)
    before=Terrain(root)
    changes=plan_terrain(root,[{'op':'raise','rect':[2,3,5,7],'value':.25}])
    after=Terrain(root,changes)
    assert set(changes)=={'t3HeightMap','t3SyncHeightMap'}
    changed=before.heights!=after.heights
    assert changed.sum()==20
    assert np.all(after.heights[3:8,2:6]==8.25)
    assert np.array_equal(before.vertices[:,:,1:],after.vertices[:,:,1:])
    assert np.array_equal(before.sync[:,:,1],after.sync[:,:,1])
    assert changes['t3HeightMap'][:32]==before.raw['t3HeightMap'][:32]
    assert (root/'t3HeightMap').read_bytes()==before.raw['t3HeightMap']


def test_texture_blocks_and_normalization(tmp_path):
    root=make_terrain(tmp_path)
    changes=plan_terrain(root,[{'op':'paint_texture','rect':[1,9,3,11],'texture':1,'strength':.35}])
    t=Terrain(root,changes)
    weights=t.texture_weights()
    assert np.all(weights.sum(axis=0)==15)
    assert np.all(weights[1,72:88,8:24]==5)
    assert np.count_nonzero(weights[1])==256
    # Distinct 64x64 blocks must not be interpreted as full-width scanlines.
    stored=(t.raw['t3TextureMasks'][64:])
    assert t.encode_texture_weights(weights)==b''.join([t.raw['t3TextureMasks'][:64],stored])


def test_multiple_operations_accumulate(tmp_path):
    root=make_terrain(tmp_path)
    operations=[{'op':'raise','rect':[2,2,4,4],'value':.25}]*2
    changes=plan_terrain(root,operations)
    assert Terrain(root,changes).heights[3,3]==8.5
    changes=plan_terrain(root,[{'op':'block_ground','rect':[2,2,4,4]}, {'op':'block_ground','rect':[5,5,6,6]}])
    assert np.count_nonzero(Terrain(root,changes).pathing_layer('CellAttribute_Pnp'))==5


@pytest.mark.parametrize('op',[
    {'op':'raise','rect':[0,0,1,1],'value':float('nan')},
    {'op':'raise','rect':[0,0,1,1],'value':1e100},
    {'op':'raise','rect':[0,0,1,1],'value':128},
    {'op':'set_cliff','rect':[0,0,1,1],'value':2},
    {'op':'raise','rect':[-1,0,1,1],'value':1},
])
def test_invalid_or_unknown_operations_are_rejected(tmp_path,op):
    with pytest.raises(SC2Error):
        plan_terrain(make_terrain(tmp_path),[op])


def test_previews_are_explicitly_offline(tmp_path):
    root=make_terrain(tmp_path/'map')
    result=render_terrain(root,tmp_path/'preview')
    assert len(result['files'])==4
    assert result['editor_render'] is False
    assert all(Path(p).is_file() for p in result['files'].values())


def test_missing_or_unsupported_preview_layers_are_reported(tmp_path):
    root=make_terrain(tmp_path/'map')
    (root/'t3TextureMasks').write_bytes(b'unknown format')
    (root/'CellAttribute_Pnp').unlink()
    result=render_terrain(root,tmp_path/'preview')
    assert result['complete'] is False
    assert set(result['files'])=={'height','geometry'}
    assert {item['preview']:item['code'] for item in result['unavailable']}=={
        'textures':'unsupported_terrain_format','pathing':'terrain_component_missing'}
