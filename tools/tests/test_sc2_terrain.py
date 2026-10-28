"""Terrain file golden offsets, source protection, reference and history tests."""
import importlib.util
import json
import math
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sc2_terrain import CellAttribute, Grid, HardTiles, LightingMap, MapInfo, Masks, TerrainMap, Water, Foliage, SyncTextures, VertexColors, terrain_difference, object_contract
from sc2_terrain_ops import Edit, NeedsEvidence
from sc2_terrain_work import apply_plan, compare, fingerprint, history_move, make_plan
from sc2_terrain_preview import render


def fixture(root):
    root.mkdir()
    (root / 't3Terrain.xml').write_text('''<terrain version="115"><heightMap tileSet="Fixture" dim="9 9" offset="0 0 0" scale="1 1 1">
      <cliffSetList num="1"><cliffSet i="0" name="FixtureCliff"/></cliffSetList>
      <vertData quantizeScale="0.001" quantizeBias="8" standardHeight="8" name="t3HeightMap"/>
      <textureList num="8"><texture i="0" name="Dirt"/><texture i="1" name="Rock"/></textureList>
      <rampList num="0"/><blockTextureSetList num="1"><blockTextureSet i="0" tileSet="0"/></blockTextureSetList>
      </heightMap></terrain>''')
    (root / 't3HeightMap').write_bytes(struct.pack('<4sIII16s', b'HMAP', 101, 9, 9, b'preserve header!') + struct.pack('<HHH', 10000, 16000, 2) * 81)
    (root / 't3SyncHeightMap').write_bytes(struct.pack('<4sIII48s', b'SMAP', 102, 9, 9, b'') + struct.pack('<hH', 2560, 2) * 81)
    (root / 't3SyncCliffLevel').write_bytes(struct.pack('<4sIII16s', b'CLIF', 100, 8, 8, b'') + struct.pack('<H', 128) * 64)
    (root / 't3CellFlags').write_bytes(struct.pack('<4sI16sII', b'LFCT', 102, b'', 8, 8) + bytes([2]) * 64)
    (root / 't3TextureMasks').write_bytes(struct.pack('<4sIIII44s', b'MASK', 102, 0, 64, 64, b'') + bytes([255]) * 2048 + bytes(7 * 2048))
    names = b'Dirt\0Rock\0' + b'\0' * 6
    (root / 't3SyncTextureInfo').write_bytes(struct.pack('<4sIIII', b'RTXT', 101, 8, 8, 1) + names + struct.pack('<II', 0, 12345) * 64)
    (root / 't3Water').write_bytes(struct.pack('<4sIII16s', b'WATR', 110, 1, 0, b'') + b'Default'.ljust(40,b'\0') + struct.pack('<4f', 0, 0, 8, 8))
    (root / 't3FluffDoodad').write_bytes(struct.pack('<4sI16sI', b'DLFT', 103, b'', 1) + struct.pack('<ffB', 1, 1, 5))
    tile = struct.pack('<14fBB', 1, 2, 10, 0, 0, 1, 1, 0, 0, -1, 0, 0, 1, 1, 1, 0)
    (root / 't3HardTile').write_bytes(struct.pack('<4sI16sII', b'HRDT', 102, b'', 1, 1) + tile + b'\0\1\0RoadFixture\0' + struct.pack('<I', 123))
    prefix = struct.pack('<4sIQIII', b'IpaM', 31, 1000, 8, 8, 0) + struct.pack('<I', 1) + b'\0' + struct.pack('<II', 1, 0)
    (root / 'MapInfo').write_bytes(prefix + b'Black\0Fixture\0' + struct.pack('<4I', 1, 1, 7, 7) + b'unknown-player-variant-suffix')
    (root / 'Objects').write_text('''<PlacedObjects Version="27">
      <ObjectUnit Id="1" Position="1,1,0" UnitType="Marine" Player="1" Scale="1,1,1"><Flag Index="HeightOffset" Value="1"/></ObjectUnit>
      <ObjectUnit Id="2" Position="2,2,0" UnitType="Marauder" Player="1" Scale="1,1,1"/>
      <ObjectDoodad Id="3" Position="3,3,10" Type="Rock" Scale="1,1,1"/>
      <ObjectPoint Id="4" Position="4,4,0" Type="Normal" Name="Probe"/>
      <ObjectPoint Id="5" Position="5,5,0" Type="StartLoc" Name="Start"/>
      <ObjectCamera Id="6" Name="CameraProbe" Position="2,2,0" CameraTarget="3,2" Rotation="0"><CameraValue Index="Yaw" Value="0"/></ObjectCamera>
      <Group Id="1" Type="ObjectUnit" Name="Existing"><GroupObject Id="2"/></Group>
      <!-- preserve this comment --></PlacedObjects>''')
    (root / 'Regions').write_text('<Regions><region id="1"><name value="Area"/><shape type="rect"><quad value="1,1,2,2"/></shape></region></Regions>')
    (root / 'Triggers').write_text('<TriggerData><Element><ValueType Type="unit"/><ValueId Id="1"/></Element></TriggerData>')
    (root / 'MapScript.galaxy').write_bytes(b'// generated output is protected\nUnitFromId(1);\n')
    (root / 'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>')
    (root / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    (root / 'opaque.dat').write_bytes(bytes(range(256)))
    return root


class TerrainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.map = fixture(self.root / 'Source.SC2Map')

    def tearDown(self):
        self.temp.cleanup()

    def test_all_codecs_preserve_original_bytes(self):
        readers = {'t3HardTile':HardTiles,'t3FluffDoodad':Foliage,'t3Water':Water,'t3TextureMasks':Masks,'MapInfo':MapInfo,'t3SyncTextureInfo':SyncTextures}
        for name, cls in readers.items():
            data = (self.map/name).read_bytes()
            self.assertEqual(cls(data).encode(),data,name)
        self.assertEqual(TerrainMap(self.map).height_grid().get(0,0),(10000,16000,2))

    def test_height_changes_only_expected_channels_and_sync(self):
        before = fingerprint(self.map)
        edit = Edit(self.map)
        changes = edit.apply([{'op':'height','mode':'raise','rect':[1,1,2,2],'value':0.25}])
        self.assertEqual(set(changes),{'t3HeightMap','t3SyncHeightMap'})
        grid = Grid(changes['t3HeightMap'],b'HMAP',{101},32,'<HHH')
        self.assertEqual(grid.get(1,1),(10000,16250,2))
        self.assertEqual(grid.get(2,1),(10000,16000,2))
        sync = Grid(changes['t3SyncHeightMap'],b'SMAP',{102},64,'<hH')
        self.assertEqual(sync.get(1,1),(2624,2))
        self.assertEqual(changes['t3HeightMap'][:32],(self.map/'t3HeightMap').read_bytes()[:32])
        self.assertEqual(fingerprint(self.map),before)

    def test_mask_nibble_and_tile_offsets(self):
        masks = Masks((self.map/'t3TextureMasks').read_bytes())
        masks.set(0,0,[1,2,3,4,5,6,7,8]);masks.set(1,0,[8,7,6,5,4,3,2,1])
        self.assertEqual(masks.encode()[64],0x18)
        self.assertEqual(masks.encode()[64+2048],0x27)
        self.assertEqual(masks.get(0,0),[1,2,3,4,5,6,7,8])

    def test_diagnostic_height_channels_are_isolated(self):
        for channel,expected in [(0,(10250,16000,2)),(1,(10000,16250,2))]:
            changes=Edit(self.map).apply([{'op':'height','channel':channel,'rect':[1,1,2,2],'value':0.25}])
            self.assertEqual(Grid(changes['t3HeightMap'],b'HMAP',{101},32,'<HHH').get(1,1),expected)

    def test_opaque_vertex_color_and_cell_attribute_records(self):
        data=struct.pack('<4sII20s',b'VTCL',104,1,b'')+bytes(range(32))+struct.pack('<I',3)+b'\x07\x80\xff'
        self.assertEqual(VertexColors(data).encode(),data)
        bitset=struct.pack('<I',9)+b'\x80\x01'
        self.assertEqual(CellAttribute(bitset).encode(),bitset)
        self.assertEqual(list(CellAttribute(bitset).populated_bits()),[7,8])
        with self.assertRaises(ValueError):CellAttribute(bitset[:-1])

    def test_lighting_tga_retains_id_footer_and_normalizes_image_origin(self):
        header=bytearray(18);header[0]=3;header[2]=2
        struct.pack_into('<HH',header,12,2,2);header[16:18]=bytes([32,0x28])
        pixels=bytes(range(16));data=bytes(header)+b'ID!'+pixels+b'preserved-footer'
        raster=LightingMap(data)
        self.assertEqual(raster.get(0,0),(8,9,10,11))
        self.assertEqual(raster.get(1,1),(4,5,6,7))
        self.assertEqual(raster.encode(),data)
        header[17]=0x18
        self.assertEqual(LightingMap(bytes(header)+b'ID!'+pixels).get(0,0),(4,5,6,7))
        with self.assertRaises(ValueError):LightingMap(data[:23])
        with self.assertRaises(ValueError):raster.get(2,0)

    def test_new_optional_layer_undo_removes_file_and_redo_restores_exact_bytes(self):
        data=struct.pack('<I',512)+b'\xff'+bytes(63)
        before=fingerprint(self.map);output=self.root/'NewLayer.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):
            plan=make_plan(self.map,[{'op':'creep','mode':'paint','rect':[0,0,1,1]}])
            self.assertIsNone(plan['changed_components'][0]['before_sha256'])
            apply_plan(plan,output,True)
            self.assertEqual((output/'CellAttribute_Cpl').read_bytes(),data)
            history_move(output,apply=True)
            self.assertFalse((output/'CellAttribute_Cpl').exists())
            self.assertEqual(fingerprint(output),before)
            history_move(output,redo=True,apply=True)
            self.assertEqual((output/'CellAttribute_Cpl').read_bytes(),data)

    def test_creep_clear_preserves_outside_subcell_bytes_and_other_components(self):
        original=struct.pack('<I',512)+bytes(range(64))
        (self.map/'CellAttribute_Cpl').write_bytes(original)
        changes=Edit(self.map).apply([{'op':'creep','mode':'remove','rect':[1,1,2,2]}])
        self.assertEqual(set(changes),{'CellAttribute_Cpl'})
        expected=bytearray(original);expected[4+8+1]=0
        self.assertEqual(changes['CellAttribute_Cpl'],bytes(expected))
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{'op':'creep','mode':'paint','rect':[1.5,1,2,2]}])

    def test_visibility_paints_its_own_layer_and_refuses_silent_road_material_change(self):
        (self.map/'CellAttribute_Cpl').write_bytes(struct.pack('<I',512)+bytes(64))
        changes=Edit(self.map).apply([{'op':'visibility','mode':'paint','rect':[1,2,3,4]}])
        self.assertEqual(set(changes),{'CellAttribute_Vbl'})
        self.assertEqual([i for i,v in enumerate(changes['CellAttribute_Vbl'][4:]) if v],[17,18,25,26])
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{'op':'roads','mode':'move','group':0,'offset':[0,0,0],'type':'Unknown'}])

    def test_lighting_paints_region_two_and_clear_restores_exact_raster(self):
        header=bytearray(18);header[2]=2;struct.pack_into('<HH',header,12,32,32);header[16:18]=bytes([32,0x28])
        data=header+b'\x00\x00\xff\x00'*1024+b'original-footer'
        (self.map/'LightingMap.tga').write_bytes(data)
        op={'op':'lighting','mode':'add','region':2,'rect':[1,1,1.5,1.5],'strength':0.5}
        changes=Edit(self.map).apply([op]);raster=LightingMap(changes['LightingMap.tga'])
        self.assertEqual(raster.get(4,4),(0,128,127,0))
        self.assertEqual(raster.get(3,4),(0,0,255,0))
        self.assertEqual(changes['LightingMap.tga'][:18],bytes(header))
        self.assertTrue(changes['LightingMap.tga'].endswith(b'original-footer'))
        self.assertEqual(Edit(self.map).apply([op,{'op':'lighting','mode':'remove','rect':[1,1,1.5,1.5]}]),{})
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([dict(op,region=3)])

    def test_ground_pathing_preserves_unrelated_bits_and_optional_layer_history(self):
        output=self.root/'Pathing.SC2Map'
        op={'op':'pathing','mode':'paint','rect':[2,2,4,4]}
        original=fingerprint(self.map)
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(make_plan(self.map,[op]),output,True)
            data=(output/'CellAttribute_Pnp').read_bytes()
            self.assertEqual([i for i,v in enumerate(data[4:]) if v], [18,19,26,27])
            self.assertEqual(set(data[4:]),{0,255})
            history_move(output,apply=True);self.assertEqual(fingerprint(output),original)
            history_move(output,redo=True,apply=True);self.assertEqual((output/'CellAttribute_Pnp').read_bytes(),data)
        raw=bytearray(struct.pack('<I',512)+bytes(64));raw[4+1]=37;raw[4+18]=142
        (self.map/'CellAttribute_Pnp').write_bytes(raw)
        changed=Edit(self.map).apply([op])['CellAttribute_Pnp']
        self.assertEqual(changed[5],37);self.assertEqual(changed[22],255)
        cleared=Edit(self.map).apply([{'op':'pathing','mode':'remove','rect':[2,2,4,4]}])['CellAttribute_Pnp']
        self.assertEqual(cleared[5],37);self.assertEqual(cleared[22],0)
        (self.map/'PaintedPathingLayer').write_bytes(b'legacy')
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([op])

    def test_owned_blockers_follow_moves_deletions_overlap_and_history(self):
        raw=bytearray(struct.pack('<I',512)+bytes(64));raw[4+18]=37
        (self.map/'CellAttribute_Pnp').write_bytes(raw)
        profile={'Rock':{'mode':'static','rect':[-0.5,-0.5,0.5,0.5],'evidence':'test-only measured footprint'}}
        sync={'op':'doodad-blockers','selector':{'kind':'doodad'},'profiles':profile}
        working=self.root/'Owned.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(make_plan(self.map,[{'op':'objects','mode':'duplicate','selector':{'kind':'doodad','ids':[3]}},sync]),working,True)
            apply_plan(make_plan(working,[{'op':'objects','mode':'transform','selector':{'kind':'doodad','ids':[3]},'offset':[2,0,0]}]),working,True)
            data=(working/'CellAttribute_Pnp').read_bytes()
            self.assertEqual([i for i,v in enumerate(data[4:]) if v==255],[18,19,20,21,26,27,28,29])
            apply_plan(make_plan(working,[{'op':'objects','mode':'delete','selector':{'kind':'doodad','ids':[7]}}]),working,True)
            data=(working/'CellAttribute_Pnp').read_bytes()
            self.assertEqual(data[4+18],37)
            self.assertEqual([i for i,v in enumerate(data[4:]) if v==255],[20,21,28,29])
            history_move(working,apply=True)
            self.assertEqual((working/'CellAttribute_Pnp').read_bytes()[4+18],255)
            history_move(working,redo=True,apply=True)
            apply_plan(make_plan(working,[{'op':'objects','mode':'delete','selector':{'kind':'doodad','ids':[3]}}]),working,True)
            self.assertEqual((working/'CellAttribute_Pnp').read_bytes(),raw)
            self.assertEqual((working/'MapScript.galaxy').read_bytes(),(self.map/'MapScript.galaxy').read_bytes())

    def test_blocker_rect_rotation_scale_native_profiles_and_clearance_guards(self):
        op={'op':'doodad-blockers','selector':{'kind':'doodad'},'profiles':{'Rock':{'mode':'static','rect':[-1,-0.25,1,0.25],'evidence':'test-only local rectangle'}}}
        changed=Edit(self.map).apply([
            {'op':'objects','mode':'update','selector':{'ids':[3]},'attributes':{'Rotation':math.pi/2,'Scale':'2,1,1'}},op])
        self.assertEqual([i for i,v in enumerate(changed['CellAttribute_Pnp'][4:]) if v],[10,11,18,19,26,27,34,35])
        native={**op,'profiles':{'Rock':{'mode':'native','evidence':'test-only native collision'}}}
        self.assertEqual(Edit(self.map).apply([native]),{})
        with self.assertRaisesRegex(ValueError,'keep_clear'):
            Edit(self.map).apply([{**op,'keep_clear':[[2,2,4,4]]}])
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{**op,'profiles':{}}])
        edit=Edit(self.map);edit.apply([op])
        original=edit.changes['CellAttribute_Pnp']
        (self.map/'CellAttribute_Pnp').write_bytes(original)
        bad=bytearray(original);bad[4]^=1;(self.map/'CellAttribute_Pnp').write_bytes(bad)
        with self.assertRaisesRegex(ValueError,'does not match'):
            Edit(self.map,blockers=edit.blockers).apply([op])
        with self.assertRaisesRegex(ValueError,'owned doodad'):
            Edit(self.map,blockers=edit.blockers).apply([{'op':'pathing','mode':'paint','rect':[0,0,1,1]}])

    def test_blocker_ownership_survives_copy_then_undo_to_initial_state(self):
        sync={'op':'doodad-blockers','selector':{'kind':'doodad'},'profiles':{'Rock':{'mode':'static','rect':[-0.5,-0.5,0.5,0.5],'evidence':'test-only footprint'}}}
        first,second=self.root/'First.SC2Map',self.root/'Second.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(make_plan(self.map,[sync]),first,True)
            move={'op':'objects','mode':'transform','selector':{'ids':[3]},'offset':[2,0,0]}
            apply_plan(make_plan(first,[move]),second,True)
            history_move(second,apply=True)
            apply_plan(make_plan(second,[{'op':'objects','mode':'delete','selector':{'ids':[3]}}]),second,True)
            self.assertEqual(set((second/'CellAttribute_Pnp').read_bytes()[4:]),{0})

    def test_owned_blockers_automatically_follow_rotation_scale_and_reject_route_conflict(self):
        sync={'op':'doodad-blockers','selector':{'kind':'doodad','rect':[2,2,4,4]},'profiles':{'Rock':{'mode':'static','rect':[-1,-0.25,1,0.25],'evidence':'test-only footprint'}},'keep_clear':[[6,0,8,8]]}
        working=self.root/'Rotated.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(make_plan(self.map,[sync]),working,True)
            change={'op':'objects','mode':'update','selector':{'ids':[3]},'attributes':{'Rotation':math.pi/2,'Scale':'2,1,1'}}
            apply_plan(make_plan(working,[change]),working,True)
            self.assertEqual([i for i,v in enumerate((working/'CellAttribute_Pnp').read_bytes()[4:]) if v],[10,11,18,19,26,27,34,35])
            before=fingerprint(working)
            move={'op':'objects','mode':'transform','selector':{'ids':[3]},'offset':[1,0,0]}
            apply_plan(make_plan(working,[move]),working,True)
            self.assertEqual([i for i,v in enumerate((working/'CellAttribute_Pnp').read_bytes()[4:]) if v],[11,12,19,20,27,28,35,36])
            before=fingerprint(working)
            with self.assertRaisesRegex(ValueError,'keep_clear'):
                make_plan(working,[{'op':'objects','mode':'transform','selector':{'ids':[3]},'offset':[3,0,0]}])
            self.assertEqual(fingerprint(working),before)

    def test_straight_road_reuses_profile_and_places_grounded_endpoints(self):
        roads=HardTiles((self.map/'t3HardTile').read_bytes())
        records=[]
        for x,flags in [(1,(1,0)),(5,(0,1))]:
            records.append(struct.pack('<14fBB',x,2,10,0,0,1,-1,0,0,1,0,0,1,1,*flags))
        roads.groups[0]['tiles']=records;(self.map/'t3HardTile').write_bytes(roads.encode())
        changes=Edit(self.map).apply([{'op':'roads','mode':'add','group':0,'points':[[4,2],[4,6]]}])
        result=HardTiles(changes['t3HardTile']);self.assertEqual(len(result.groups),2)
        self.assertEqual(result.groups[0],roads.groups[0])
        first=struct.unpack('<14fBB',result.groups[1]['tiles'][0])
        self.assertEqual(first[:3],(4,2,10))
        self.assertEqual(first[6:12],(0,-1,0,0,1,0))
        self.assertEqual(result.groups[1]['model'],roads.groups[0]['model'])
        grid=TerrainMap(self.map).height_grid();grid.set(4,4,(10000,16000,3));(self.map/'t3HeightMap').write_bytes(grid.encode())
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{'op':'roads','mode':'add','group':0,'points':[[4,2],[4,6]]}])

    def test_foliage_priority_changes_order_without_changing_any_record(self):
        f=Foliage((self.map/'t3FluffDoodad').read_bytes())
        f.entries=[struct.pack('<ffB',x,1,k) for x,k in [(1,5),(4,6),(2,7),(5,1)]]
        (self.map/'t3FluffDoodad').write_bytes(f.encode())
        changes=Edit(self.map).apply([{'op':'foliage','mode':'prioritize','rect':[4,0,6,2]}])
        result=Foliage(changes['t3FluffDoodad'])
        self.assertEqual(result.entries,[f.entries[i] for i in [1,3,0,2]])
        self.assertEqual(sorted(result.entries),sorted(f.entries))

    def test_scattered_foliage_precedes_existing_records_for_visibility(self):
        original=Foliage((self.map/'t3FluffDoodad').read_bytes()).entries
        changes=Edit(self.map).apply([{'op':'foliage','mode':'scatter','rect':[2,2,3,3],'template_flag':5,'density':3,'seed':4}])
        result=Foliage(changes['t3FluffDoodad'])
        self.assertEqual(result.entries[3:],original)
        self.assertEqual(len(result.entries),4)
        self.assertTrue(all(2<=x<3 and 2<=y<3 and flag==5 for x,y,flag in result.positions()[:3]))

    def test_unchanged_object_properties_preserve_original_xml_bytes(self):
        path=self.map/'Objects';path.write_text(path.read_text().replace('Position="4,4,0"','Position="4.0000,4.0000,0.00"'))
        before=(self.map/'Objects').read_bytes()
        self.assertEqual(Edit(self.map).apply([{'op':'objects','mode':'update','selector':{'kind':'point','ids':[4]},'attributes':{'Name':'Probe'}}]),{})
        self.assertEqual((self.map/'Objects').read_bytes(),before)

    def test_new_camera_moves_target_with_absolute_placement(self):
        changes=Edit(self.map).apply([{'op':'objects','mode':'add','kind':'camera','template':{'kind':'camera','ids':[6]},'position':[4,4,0]}])
        e=ET.fromstring(changes['Objects']).find("ObjectCamera[@Id='7']")
        self.assertEqual(e.get('Position'),'4,4,0')
        self.assertEqual(e.get('CameraTarget'),'5,4')

    def test_semantic_diff_reports_bit_layer_creation_and_raw_lighting_pixels(self):
        after=self.root/'After.SC2Map';fixture(after)
        (after/'CellAttribute_Cpl').write_bytes(struct.pack('<I',8)+b'\x81')
        header=bytearray(18);header[2]=2;struct.pack_into('<HH',header,12,1,1);header[16:18]=bytes([32,8])
        (self.map/'LightingMap.tga').write_bytes(header+b'\x00\x00\xff\x00')
        (after/'LightingMap.tga').write_bytes(header+b'\x00\xff\x00\x00')
        result=terrain_difference(self.map,after)
        self.assertEqual(result['cell_attributes'][0]['presence'],[False,True])
        self.assertEqual(result['cell_attributes'][0]['added_storage_bit_examples'],[0,7])
        self.assertEqual(result['lighting_raster']['changed_pixels'],1)
        self.assertEqual(result['lighting_raster']['inclusive_image_bounds'],[0,0,0,0])

    def test_texture_updates_matching_sync_cell_preserving_unknown_channel(self):
        edit=Edit(self.map)
        data=edit.apply([{'op':'texture','mode':'set','slot':1,'rect':[1,1,2,2]}])
        masks=Masks(data['t3TextureMasks']);self.assertEqual(masks.get(8,8),[0,15,0,0,0,0,0,0])
        self.assertEqual(masks.get(7,8),[15,0,0,0,0,0,0,0])
        sync=SyncTextures(data['t3SyncTextureInfo'])
        self.assertEqual(struct.unpack_from('<II',sync.raw,sync.offset+9*8),(1,12345))

    def test_bad_input_and_unimplemented_semantics_do_not_modify_source(self):
        before=fingerprint(self.map)
        for op in [
            {'op':'height','rect':[-1,0,2,2]},
            {'op':'height','rect':[1,1,2,2],'value':float('nan')},
            {'op':'height','rect':[1,1,2,2],'value':99999},
            {'op':'height','rect':[1,1,2,2],'mode':'set','value':10},
            {'op':'cliff','rect':[1,1,2,2]},
            {'op':'water','type':'UnverifiedType','rect':[1,1,2,2]},
        ]:
            with self.subTest(op=op),self.assertRaises(ValueError):Edit(self.map).apply([op])
        self.assertEqual(fingerprint(self.map),before)

    def test_object_identity_references_and_new_ids(self):
        edit=Edit(self.map)
        with self.assertRaisesRegex(ValueError,'referenced'):
            edit.apply([{'op':'objects','mode':'delete','selector':{'kind':'unit','ids':[1]}}])
        changes=Edit(self.map).apply([{'op':'objects','mode':'duplicate','selector':{'kind':'unit','ids':[2]},'offset':[2,0,0]}])
        root=ET.fromstring(changes['Objects'])
        self.assertEqual(root.find("ObjectUnit[@Id='2']").get('Position'),'2,2,0')
        self.assertEqual(root.find("ObjectUnit[@Id='7']").get('Position'),'4,2,0')
        self.assertIn(b'preserve this comment',changes['Objects'])
        data=Edit(self.map).apply([{'op':'objects','mode':'delete','selector':{'kind':'unit','ids':[2]}}])
        self.assertEqual(len(ET.fromstring(data['Objects']).find('Group')),0)

    def test_generated_references_protect_objects_even_without_triggers(self):
        (self.map/'Triggers').unlink()
        with self.assertRaisesRegex(ValueError,'referenced'):
            Edit(self.map).apply([{'op':'objects','mode':'delete','selector':{'kind':'unit','ids':[1]}}])

    def test_face_target_uses_final_position_without_moving_existing_objects(self):
        changes=Edit(self.map).apply([
            {'op':'objects','mode':'update','selector':{'kind':'unit','ids':[1]},'face_towards':[1,4]},
            {'op':'objects','mode':'duplicate','selector':{'kind':'doodad','ids':[3]},'offset':[1,0,0],'face_towards':[1,3]},
            {'op':'objects','mode':'add','kind':'unit','template':{'ids':[2]},'position':[5,5,0],'face_towards':[5,2]},
        ])
        root=ET.fromstring(changes['Objects'])
        for identity,position,angle in [('1','1,1,0',math.pi/2),('7','4,3,10',math.pi),('8','5,5,0',-math.pi/2)]:
            obj=next(e for e in root if e.get('Id')==identity and e.tag!='Group')
            self.assertEqual(obj.get('Position'),position)
            self.assertAlmostEqual(float(obj.get('Rotation')),angle,places=5)
        for extra in ({'face_towards':[1,1]}, {'face_towards':[1,2],'attributes':{'Rotation':0}}):
            with self.assertRaises(ValueError):
                Edit(self.map).apply([{'op':'objects','mode':'update','selector':{'kind':'unit','ids':[1]},**extra}])

    def test_absolute_doodad_moves_and_duplicates_follow_terrain_height_delta(self):
        root=ET.fromstring((self.map/'Objects').read_bytes())
        ET.SubElement(root.find('ObjectDoodad'),'Flag',{'Index':'HeightAbsolute','Value':'1'})
        (self.map/'Objects').write_bytes(ET.tostring(root))
        grid=TerrainMap(self.map).height_grid();grid.set(5,3,(10000,18000,2));(self.map/'t3HeightMap').write_bytes(grid.encode())
        for mode in ('transform','duplicate'):
            with self.subTest(mode=mode):
                changes=Edit(self.map).apply([{'op':'objects','mode':mode,'selector':{'kind':'doodad','ids':[3]},'offset':[2,0,0]}])
                result=ET.fromstring(changes['Objects']);obj=result.findall('ObjectDoodad')[-1]
                self.assertEqual(obj.get('Position'),'5,3,12')

    def test_doodad_grounding_keeps_explicit_z_and_supports_snap_and_alignment(self):
        root=ET.fromstring((self.map/'Objects').read_bytes());stone=root.find('ObjectDoodad')
        ET.SubElement(stone,'Flag',{'Index':'HeightAbsolute','Value':'1'})
        ET.SubElement(root,'ObjectDoodad',{'Id':'7','Type':'Rock','Position':'1,3,10','Scale':'1,1,1'}).append(ET.Element('Flag',{'Index':'HeightAbsolute','Value':'1'}))
        (self.map/'Objects').write_bytes(ET.tostring(root))
        grid=TerrainMap(self.map).height_grid();grid.set(5,3,(10000,18000,2));(self.map/'t3HeightMap').write_bytes(grid.encode())
        base={'op':'objects','mode':'transform','selector':{'ids':[3]},'offset':[2,0,0]}
        for extra,expected in [({'grounding':'keep-z'},'5,3,10'),({'position':[5,3,7],'offset':[0,0,0]},'5,3,7'),({'position':[5,3,7],'offset':[0,0,0],'grounding':'snap'},'5,3,12'),({'offset':[2,0,0.5]},'5,3,12.5'),({'offset':[1.5,0,0]},'4.5,3,11')]:
            changed=Edit(self.map).apply([{**base,**extra}]);e=ET.fromstring(changed['Objects']).find("ObjectDoodad[@Id='3']")
            self.assertEqual(e.get('Position'),expected)
        changed=Edit(self.map).apply([{'op':'objects','mode':'distribute','selector':{'kind':'doodad'},'axis':'x','spacing':4}])
        self.assertEqual(ET.fromstring(changed['Objects']).find("ObjectDoodad[@Id='3']").get('Position'),'5,3,12')
        stone.set('Position','3,3,8');(self.map/'Objects').write_bytes(ET.tostring(root))
        changed=Edit(self.map).apply([{'op':'objects','mode':'update','selector':{'ids':[3]},'grounding':'snap'}])
        self.assertEqual(ET.fromstring(changed['Objects']).find("ObjectDoodad[@Id='3']").get('Position'),'3,3,10')
        with self.assertRaises(NeedsEvidence):
            Edit(self.map).apply([{'op':'objects','mode':'update','selector':{'kind':'unit','ids':[1]},'grounding':'snap'}])
        grid.set(5,3,(10000,18000,3));(self.map/'t3HeightMap').write_bytes(grid.encode())
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{**base,'offset':[1.5,0,0]}])

    def test_start_locations_are_not_silently_created(self):
        for mode in ('add','duplicate','delete'):
            op={'op':'objects','mode':mode,'selector':{'kind':'point','ids':[5]},'kind':'point','template':{'kind':'point','ids':[5]},'position':[3,3,0]}
            with self.subTest(mode=mode),self.assertRaises(NeedsEvidence):Edit(self.map).apply([op])

    def test_camera_position_target_yaw_move_together(self):
        changes=Edit(self.map).apply([{'op':'objects','mode':'transform','selector':{'kind':'camera','ids':[6]},'position':[4,4,0],'angle':math.pi/2,'pivot':[4,4,0]}])
        e=ET.fromstring(changes['Objects']).find('ObjectCamera')
        self.assertEqual(e.get('Position'),'4,4,0')
        target=[float(v) for v in e.get('CameraTarget').split(',')]
        self.assertAlmostEqual(target[0],4);self.assertAlmostEqual(target[1],5)
        self.assertEqual(e.find('CameraValue').get('Value'),'90')

    def test_water_roads_foliage_and_regions(self):
        changes=Edit(self.map).apply([
            {'op':'water','mode':'add','type':'Default','rect':[1,1,2,2]},
            {'op':'roads','mode':'duplicate','group':0,'offset':[1,2,0]},
            {'op':'foliage','mode':'scatter','rect':[2,2,4,4],'density':1,'template_flag':5,'seed':7},
            {'op':'regions','mode':'add','name':'目标','shapes':[{'type':'circle','center':[4,4],'radius':1}]},
        ])
        self.assertEqual(len(Water(changes['t3Water']).entries),2)
        roads=HardTiles(changes['t3HardTile']);self.assertEqual(struct.unpack_from('<3f',roads.groups[1]['tiles'][0]),(2,4,10))
        self.assertEqual(len(Foliage(changes['t3FluffDoodad']).entries),5)
        self.assertTrue(changes['Regions'].isascii())
        self.assertEqual(ET.fromstring(changes['Regions']).findall('region')[1].find('name').get('value'),'目标')

    def test_bounds_update_hash_delta_and_preserve_unknown_suffix(self):
        original=MapInfo((self.map/'MapInfo').read_bytes())
        changes=Edit(self.map).apply([{'op':'bounds','rect':[2,2,6,6]}])
        changed=MapInfo(changes['MapInfo'])
        self.assertEqual(changed.bounds,(2,2,6,6))
        self.assertEqual(struct.unpack_from('<Q',changed.raw,8)[0],1000+2*(32-72))
        self.assertEqual(changed.raw[changed.bounds_at+16:],original.raw[original.bounds_at+16:])

    def test_plan_preview_publication_undo_redo_and_stale_protection(self):
        output=self.root/'Working.SC2Map'
        plan=make_plan(self.map,[{'op':'height','rect':[1,1,2,2],'value':0.125}])
        original=fingerprint(self.map)
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(plan,output,False);self.assertFalse(output.exists())
            apply_plan(plan,output,True)
            edited=fingerprint(output);self.assertNotEqual(edited,original)
            self.assertEqual(fingerprint(self.map),original)
            self.assertEqual((output/'opaque.dat').read_bytes(),(self.map/'opaque.dat').read_bytes())
            self.assertEqual((output/'MapScript.galaxy').read_bytes(),(self.map/'MapScript.galaxy').read_bytes())
            history_move(output,apply=True);self.assertEqual(fingerprint(output),original)
            history_move(output,redo=True,apply=True);self.assertEqual(fingerprint(output),edited)
            (output/'opaque.dat').write_bytes(b'external edit')
            with self.assertRaisesRegex(ValueError,'outside terrain tools'):history_move(output,apply=True)
        (self.map/'opaque.dat').write_bytes(b'changed since plan')
        with patch('sc2_terrain_work.REPO',self.root),self.assertRaisesRegex(ValueError,'changed since'):
            apply_plan(plan,self.root/'Other.SC2Map',True)

    def test_failed_validation_never_publishes(self):
        output=self.root/'Working.SC2Map'
        plan=make_plan(self.map,[{'op':'height','rect':[1,1,2,2],'value':0.125}])
        before=fingerprint(self.map)
        with patch('sc2_terrain_work.REPO',self.root),patch('sc2_terrain_work.validate_changed',side_effect=ValueError('deliberate failed check')):
            with self.assertRaisesRegex(ValueError,'deliberate'):apply_plan(plan,output,True)
        self.assertFalse(output.exists());self.assertEqual(fingerprint(self.map),before)

    def test_outputs_cannot_overwrite_sources_or_escape_workspace(self):
        plan=make_plan(self.map,[{'op':'height','rect':[1,1,2,2],'value':0.125}])
        with patch('sc2_terrain_work.REPO',self.root):
            for output in (self.map,self.map/'Nested.SC2Map',self.root/'publish/Bad.SC2Map',self.root.parent/'Outside.SC2Map'):
                with self.subTest(output=output),self.assertRaises((ValueError,OSError)):apply_plan(plan,output,True)

    def test_malformed_payloads_are_rejected(self):
        for cls,name in [(Masks,'t3TextureMasks'),(Water,'t3Water'),(HardTiles,'t3HardTile'),(Foliage,'t3FluffDoodad'),(SyncTextures,'t3SyncTextureInfo')]:
            with self.subTest(name=name),self.assertRaises(ValueError):cls((self.map/name).read_bytes()[:-1])
        data=bytearray((self.map/'t3HeightMap').read_bytes());struct.pack_into('<I',data,4,999)
        with self.assertRaises(ValueError):Grid(data,b'HMAP',{101},32,'<HHH')

    def test_svg_is_valid_and_marks_diagnostic_scope(self):
        svg=render(self.map,['height','water','unit','point','camera','regions','grid','cliffs'],1)
        self.assertEqual(ET.fromstring(svg).tag,'{http://www.w3.org/2000/svg}svg')
        self.assertIn('runtime pathing unverified',svg)
        (self.map/'CellAttribute_Pnp').write_bytes(struct.pack('<I',512)+b'\x8e'+bytes(63))
        self.assertIn('Pnp no-ground-path paint byte 142',render(self.map,['pathing'],1))

    def test_semantic_difference_reports_coordinates_and_channels(self):
        import shutil
        other=self.root/'Other.SC2Map';shutil.copytree(self.map,other)
        edit=Edit(other);changes=edit.apply([{'op':'height','channel':0,'rect':[1,1,2,2],'value':0.25}])
        for name,data in changes.items():(other/name).write_bytes(data)
        result=terrain_difference(self.map,other)
        height=result['grids'][0]
        self.assertEqual(height['changed_cells'],1)
        self.assertEqual(height['inclusive_bounds'],[1,1,1,1])
        self.assertEqual(height['changed_channels'],{0:1})
        self.assertFalse(result['migration_confounded'])

    def test_cliff_stamp_transfers_coordinated_fields_and_refuses_nonflat_target(self):
        import shutil
        donor=self.root/'Donor.SC2Map';shutil.copytree(self.map,donor)
        for path in (self.map,donor):
            flags=Grid((path/'t3CellFlags').read_bytes(),b'LFCT',{102},32,'<B',24)
            for y in range(8):
                for x in range(8):flags.set(x,y,(0,))
            (path/'t3CellFlags').write_bytes(flags.encode())
            root=ET.parse(path/'t3Terrain.xml').getroot();ET.SubElement(root.find('heightMap'),'cliffCellList',{'num':'16','numOccupied':'0'})
            (path/'t3Terrain.xml').write_bytes(ET.tostring(root))
        h=TerrainMap(donor).height_grid();s=Grid((donor/'t3SyncHeightMap').read_bytes(),b'SMAP',{102},64,'<hH')
        for x,y in [(4,4),(3,4),(5,4),(4,3),(4,5)]:
            a,b,_=h.get(x,y);h.set(x,y,(a,b+2000,3));s.set(x,y,(3072,3))
        (donor/'t3HeightMap').write_bytes(h.encode());(donor/'t3SyncHeightMap').write_bytes(s.encode())
        c=Grid((donor/'t3SyncCliffLevel').read_bytes(),b'CLIF',{100},32,'<H')
        for x,y in [(3,3),(4,3),(3,4),(4,4)]:c.set(x,y,(192,))
        (donor/'t3SyncCliffLevel').write_bytes(c.encode())
        changes=Edit(self.map).apply([{'op':'cliff-stamp','template':str(donor),'source_center':[4,4],'center':[4,4],'radius':2}])
        self.assertEqual(Grid(changes['t3HeightMap'],b'HMAP',{101},32,'<HHH').get(4,4),(10000,18000,3))
        self.assertEqual(Grid(changes['t3SyncCliffLevel'],b'CLIF',{100},32,'<H').get(4,4),(192,))
        self.assertEqual(Grid(changes['t3SyncHeightMap'],b'SMAP',{102},64,'<hH').get(4,4),(3072,3))
        (self.map/'t3HeightMap').write_bytes(changes['t3HeightMap'])
        with self.assertRaisesRegex(NeedsEvidence,'flat destination'):
            Edit(self.map).apply([{'op':'cliff-stamp','template':str(donor),'source_center':[4,4],'center':[4,4],'radius':2}])

    def test_local_water_height_and_clone_keep_original_and_other_states(self):
        file=self.map/'Base.SC2Data/GameData/WaterData.xml';file.parent.mkdir(parents=True)
        file.write_text('<Catalog><CWater id="Default" parent="Agria"><State index="0"><Height value="2.2"/><Name value="Default"/><Color value="0.1,0.2,0.3,0.4"/></State><State index="1"><Height value="8"/></State></CWater></Catalog>')
        changes=Edit(self.map).apply([
            {'op':'water-config','mode':'clone','id':'ProbeWater','template':'Default','state':0,'values':{'Height':3.2}},
            {'op':'water','mode':'add','type':'ProbeWater','rect':[2,2,4,4]}])
        root=ET.fromstring(changes['Base.SC2Data/GameData/WaterData.xml'])
        self.assertEqual(root.find("CWater[@id='Default']/State/Height").get('value'),'2.2')
        self.assertEqual(root.find("CWater[@id='ProbeWater']/State/Height").get('value'),'3.2')
        self.assertEqual(root.find("CWater[@id='ProbeWater']/State[@index='1']/Height").get('value'),'8')
        self.assertEqual(Water(changes['t3Water']).describe()[-1]['type'],'ProbeWater')
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{'op':'water-config','id':'InheritedOnly','values':{'Height':4}}])

    def test_uniform_height_matches_sample_without_changing_cliff_mask(self):
        path=self.map/'t3HeightMap';grid=TerrainMap(self.map).height_grid()
        grid.set(1,1,(10000,17000,2));path.write_bytes(grid.encode())
        changes=Edit(self.map).apply([{'op':'height','mode':'uniform','sample':[1,1],'rect':[2,2,3,3]}])
        new=Grid(changes['t3HeightMap'],b'HMAP',{101},32,'<HHH')
        self.assertEqual(new.get(2,2),(10000,17000,2))
        self.assertEqual(new.get(3,3),(10000,16000,2))
        grid.set(2,2,(10000,16000,3));path.write_bytes(grid.encode())
        with self.assertRaises(NeedsEvidence):Edit(self.map).apply([{'op':'height','mode':'uniform','sample':[1,1],'rect':[2,2,3,3]}])

    def test_water_height_transaction_preserves_all_ground_components_and_undo(self):
        file=self.map/'Base.SC2Data/GameData/WaterData.xml';file.parent.mkdir(parents=True)
        file.write_text('<Catalog><CWater id="Default"><State index="0"><Height value="2.2"/></State></CWater></Catalog>')
        plan=make_plan(self.map,[{'op':'water-config','id':'Default','values':{'Height':4.2}}])
        output=self.root/'Water.SC2Map';before=fingerprint(self.map)
        with patch('sc2_terrain_work.REPO',self.root):
            apply_plan(plan,output,True)
            for name in ['t3HeightMap','t3SyncHeightMap','t3SyncCliffLevel','t3CellFlags','t3Terrain.xml']:
                self.assertEqual((self.map/name).read_bytes(),(output/name).read_bytes(),name)
            history_move(output,apply=True)
            self.assertEqual(fingerprint(output),before)

    def test_small_object_coordinates_pass_real_objects_schema(self):
        plan=make_plan(self.map,[{'op':'objects','mode':'update','selector':{'kind':'point','ids':[4]},'position':[0.00001,4,0]}])
        output=self.root/'Objects.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):apply_plan(plan,output,True)
        e=ET.parse(output/'Objects').getroot().find("ObjectPoint[@Id='4']")
        self.assertEqual(float(e.get('Position').split(',')[0]),0.00001)

    def test_scan_distinguishes_absent_terrain_from_damaged_terrain(self):
        spec=importlib.util.spec_from_file_location('terrain_cli_test',Path(__file__).resolve().parents[1]/'sc2-terrain.py')
        cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
        hub=self.root/'Hub.SC2Map';hub.mkdir()
        (self.map/'t3HeightMap').unlink()
        result=cli.scan(self.root)
        self.assertEqual(len(result['errors']),1)
        self.assertFalse(next(e for e in result['maps'] if e['relative_path']=='Hub.SC2Map')['has_terrain'])

    def test_schema_defined_children_can_be_added_and_removed_with_xsd_validation(self):
        operations=[
            {'op':'objects','mode':'update','selector':{'kind':'point','ids':[4]},'children':[{'tag':'Flag','index':'PointHidden','value':1}]},
            {'op':'objects','mode':'update','selector':{'kind':'unit','ids':[2]},'children':[{'tag':'AIActive','index':1,'value':0}]},
            {'op':'objects','mode':'update','selector':{'kind':'camera','ids':[6]},'children':[{'tag':'CameraValue','index':'Distance','value':0.00001}]},
        ]
        plan=make_plan(self.map,operations);output=self.root/'Properties.SC2Map'
        with patch('sc2_terrain_work.REPO',self.root):apply_plan(plan,output,True)
        root=ET.parse(output/'Objects').getroot()
        self.assertEqual(root.find("ObjectPoint[@Id='4']/Flag").get('Value'),'1')
        self.assertEqual(root.find("ObjectUnit[@Id='2']/AIActive").get('Index'),'1')
        self.assertEqual(root.find("ObjectCamera/CameraValue[@Index='Distance']").get('Value'),'0.00001')
        edit=Edit(output);changes=edit.apply([{'op':'objects','mode':'update','selector':{'kind':'point','ids':[4]},'children':[{'tag':'Flag','index':'PointHidden','remove':True}]}])
        self.assertIsNone(ET.fromstring(changes['Objects']).find("ObjectPoint[@Id='4']/Flag"))
        self.assertIn('HeightAbsolute',object_contract('point')['enums']['EObjectFlagType'])

    def test_new_and_duplicated_objects_apply_requested_child_overrides(self):
        changes=Edit(self.map).apply([
            {'op':'objects','mode':'add','kind':'point','template':{'kind':'point','ids':[4]},'position':[3,4,0],
             'children':[{'tag':'Flag','index':'PointHidden','value':1}]},
            {'op':'objects','mode':'duplicate','selector':{'kind':'unit','ids':[1]},'offset':[1,0,0],
             'attributes':{'Player':2},'children':[{'tag':'Flag','index':'HeightOffset','value':0}]},
        ])
        root=ET.fromstring(changes['Objects'])
        self.assertEqual(root.find("ObjectPoint[@Id='7']/Flag").get('Value'),'1')
        unit=root.find("ObjectUnit[@Id='8']")
        self.assertEqual(unit.get('Player'),'2')
        self.assertEqual(unit.find('Flag').get('Value'),'0')


if __name__=='__main__':
    unittest.main()
