"""Explicit terrain operations on an in-memory component overlay."""
from __future__ import annotations

import copy
import math
import random
import re
import struct
import xml.etree.ElementTree as ET

from sc2_terrain import (CellAttribute, Foliage, Grid, HardTiles, LightingMap, MapInfo, Masks, SyncTextures,
                         TerrainMap, Water, csv, fmt, number, vector, xml_bytes, object_contract, sha)

TAGS = {'unit': 'ObjectUnit', 'doodad': 'ObjectDoodad', 'point': 'ObjectPoint', 'camera': 'ObjectCamera', 'group': 'Group'}


class NeedsEvidence(ValueError):
    pass


def require_keys(op, allowed):
    extra = set(op) - set(allowed.split()) - {'op'}
    if extra:
        raise ValueError('Unknown operation parameters: ' + ', '.join(sorted(extra)))


def region_box(op, terrain):
    bounds = op.get('rect')
    if bounds is None or len(bounds) != 4:
        raise ValueError('rect [left,bottom,right,top] is required')
    box = [number(v) for v in bounds]
    ox, oy = terrain.offset[:2]
    sx, sy = terrain.scale[:2]
    if sx <= 0 or sy <= 0:
        raise ValueError('Negative XY terrain scale needs Editor evidence')
    if not (ox <= box[0] < box[2] <= ox + (terrain.dim[0] - 1) * sx
            and oy <= box[1] < box[3] <= oy + (terrain.dim[1] - 1) * sy):
        raise ValueError('rect is outside the terrain extent or empty')
    return box


def in_box(x, y, box):
    return box[0] <= x < box[2] and box[1] <= y < box[3]


def weight(x, y, box, op):
    shape = op.get('shape', 'rect')
    if shape == 'rect':
        return 1.0 if in_box(x, y, box) else 0.0
    if shape not in ('circle', 'diamond'):
        raise ValueError('shape must be rect, circle or diamond')
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    dx, dy = abs((x - cx) / ((box[2] - box[0]) / 2)), abs((y - cy) / ((box[3] - box[1]) / 2))
    distance = math.hypot(dx, dy) if shape == 'circle' else dx + dy
    if distance >= 1:
        return 0.0
    falloff = number(op.get('falloff', 0))
    if not 0 <= falloff <= 1:
        raise ValueError('falloff must be within 0..1')
    return min(1.0, (1 - distance) / falloff) if falloff else 1.0


def coordinates(grid, terrain, op, factor=1):
    box = region_box(op, terrain)
    ox, oy = terrain.offset[:2]
    sx, sy = terrain.scale[0] / factor, terrain.scale[1] / factor
    for y in range(max(0, math.floor((box[1] - oy) / sy)), min(grid.height, math.ceil((box[3] - oy) / sy))):
        for x in range(max(0, math.floor((box[0] - ox) / sx)), min(grid.width, math.ceil((box[2] - ox) / sx))):
            w = weight(ox + x * sx, oy + y * sy, box, op)
            if w:
                yield x, y, w


def selected(root, selector):
    if not isinstance(selector, dict) or not selector:
        raise ValueError('A nonempty selector is required; use {"all":true} explicitly')
    if set(selector) - {'all', 'kind', 'ids', 'name', 'type', 'rect', 'player'}:
        raise ValueError('Unknown selector property')
    kind = selector.get('kind')
    tag = TAGS.get(kind, kind)
    ids = {str(v) for v in selector.get('ids', [])}
    result = []
    for e in root:
        if not isinstance(e.tag,str):
            continue
        if root.tag=='PlacedObjects' and e.tag not in TAGS.values():
            continue
        if root.tag=='Regions' and e.tag!='region':
            continue
        if tag and e.tag != tag:
            continue
        if ids and e.get('Id', e.get('id')) not in ids:
            continue
        if 'name' in selector and e.get('Name', e.find('name').get('value') if e.find('name') is not None else None) != selector['name']:
            continue
        if 'type' in selector and e.get('UnitType', e.get('Type')) != selector['type']:
            continue
        if 'player' in selector and e.get('Player') != str(selector['player']):
            continue
        if 'rect' in selector:
            if not e.get('Position') or not in_box(*vector(e.get('Position'), 3)[:2], selector['rect']):
                continue
        result.append(e)
    if not result:
        raise ValueError('Selector matched no objects')
    return result


class Edit:
    def __init__(self, path, blockers=None):
        self.terrain = TerrainMap(path)
        self.changes = {}
        self.notes = []
        self.blockers = copy.deepcopy(blockers)
        self.initial_blockers = copy.deepcopy(blockers)

    def read(self, name):
        return self.changes[name] if name in self.changes else self.terrain.read(name)

    def original(self, name):
        try:
            return self.terrain.read(name)
        except FileNotFoundError:
            return None

    def xml(self, name):
        return ET.fromstring(self.read(name), parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))

    def put(self, name, data):
        self.changes[name] = data

    def put_xml(self, name, root):
        original = self.original(name)
        if original is not None:
            old = ET.fromstring(original, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
            if ET.tostring(old) == ET.tostring(root):
                self.changes.pop(name, None)
                return
        self.put(name, xml_bytes(root))

    def referenced(self, kind, identity):
        path = self.terrain.path / 'Triggers'
        if path.exists():
            for node in ET.fromstring(path.read_bytes()).iter():
                vtype, vid = node.find('ValueType'), node.find('ValueId')
                if vtype is not None and vid is not None and vtype.get('Type') == kind and vid.get('Id') == str(identity):
                    return True
        calls = {'unit': 'Unit', 'point': 'Point', 'region': 'Region', 'camera': 'CameraInfo', 'doodad': 'Doodad'}
        if kind in calls:
            for script in self.terrain.path.rglob('*.galaxy'):
                if re.search(r'\b' + calls[kind] + r'FromId\(\s*' + re.escape(str(identity)) + r'\s*\)', script.read_text(encoding='utf-8-sig')):
                    return True
        if kind != 'region':
            for e in self.xml('Objects'):
                if e.get('ObjectId') == str(identity):
                    return True
        return False

    def height(self, op):
        require_keys(op, 'rect shape falloff mode value strength seed iterations channel sample')
        terrain = self.terrain
        grid = Grid(self.read('t3HeightMap'), b'HMAP', {101}, 32, '<HHH')
        sync = Grid(self.read('t3SyncHeightMap'), b'SMAP', {102}, 64, '<hH')
        if (grid.width, grid.height) != (sync.width, sync.height) or terrain.scale != [1, 1, 1]:
            raise NeedsEvidence('Height editing requires matching v102 sync grid and unit terrain scale')
        points = list(coordinates(grid, terrain, op))
        if not points:
            raise ValueError('Brush covers no vertices')
        mode = op.get('mode', 'raise')
        if mode not in ('raise', 'lower', 'set', 'smooth', 'noise', 'uniform'):
            raise ValueError('Unknown height brush mode')
        strength = number(op.get('strength', 1))
        if not 0 <= strength <= 1:
            raise ValueError('strength must be within 0..1')
        rng = random.Random(int(op.get('seed', 0)))
        channel = int(op.get('channel', 1))
        if channel not in (0, 1):
            raise ValueError('Height channel must be 0 or 1; channel selection is experimental')
        iterations = int(op.get('iterations', 1))
        if not 1 <= iterations <= 100:
            raise ValueError('iterations must be within 1..100')
        if mode == 'set':
            raise NeedsEvidence('Absolute render/simulation height conversion needs a controlled Editor height sample; use relative brushes or uniform with a sampled point')
        sample_total = sample_mask = None
        if mode == 'uniform':
            sample = op.get('sample')
            if not isinstance(sample,list) or len(sample)!=2:
                raise ValueError('uniform needs sample [world_x,world_y]')
            sample_x,sample_y = [number(v) for v in sample]
            ix = (sample_x-terrain.offset[0])/terrain.scale[0]
            iy = (sample_y-terrain.offset[1])/terrain.scale[1]
            if not ix.is_integer() or not iy.is_integer():
                raise ValueError('Uniform sample must be exactly on a height vertex')
            sa,sb,sample_mask = grid.get(int(ix),int(iy))
            sample_total = sa+sb
            if any(grid.get(x,y)[2]!=sample_mask for x,y,_ in points):
                raise NeedsEvidence('Uniform sampling currently requires one matching cliff level')
        for _ in range(iterations):
            original = Grid(grid.encode(), b'HMAP', {101}, 32, '<HHH')
            for x, y, w in points:
                a, b, mask = original.get(x, y)
                current = a + b
                if mode == 'uniform':
                    delta_raw = round((sample_total-current)*w*strength)
                elif mode == 'smooth':
                    neighbor = [sum(original.get(xx, yy)[:2])
                                for yy in range(max(0, y - 1), min(grid.height, y + 2))
                                for xx in range(max(0, x - 1), min(grid.width, x + 2))
                                if original.get(xx, yy)[2] == mask]
                    delta_raw = round((sum(neighbor) / len(neighbor) - current) * w * strength)
                else:
                    delta = number(op.get('value', 0.25))
                    if mode == 'lower':
                        delta = -delta
                    if mode == 'noise':
                        delta = rng.uniform(-abs(delta), abs(delta))
                    delta_raw = round(delta * w * strength / terrain.quantize)
                fine = (a if channel == 0 else b) + delta_raw
                if not 0 <= fine <= 65535:
                    raise ValueError('Height adjustment exceeds retained quantization range')
                old_sync, level = sync.get(x, y)
                new_sync = old_sync + round(delta_raw * terrain.quantize * 256)
                if not -32768 <= new_sync <= 32767:
                    raise ValueError('Sync height exceeds signed Q8 range')
                grid.set(x, y, (fine, b, mask) if channel == 0 else (a, fine, mask))
                sync.set(x, y, (new_sync, level))
        self.put('t3HeightMap', grid.encode())
        self.put('t3SyncHeightMap', sync.encode())
        self.notes.append('Relative height writes preserve existing render/sync offsets; Editor and runtime validation required')

    def texture(self, op):
        require_keys(op, 'rect shape falloff mode slot strength weights')
        terrain = self.terrain
        masks = Masks(self.read('t3TextureMasks'))
        sync = SyncTextures(self.read('t3SyncTextureInfo'))
        # Every observed corpus map uses 8 mask samples per terrain cell.
        if (masks.width, masks.height) != ((terrain.dim[0] - 1) * 8, (terrain.dim[1] - 1) * 8):
            raise NeedsEvidence('Texture mask/world sampling ratio not recognized')
        slot = int(op.get('slot', 0))
        if not 0 <= slot < len(sync.names):
            raise ValueError('Texture slot out of bounds')
        if not sync.names[slot]:
            raise ValueError('Texture slot is empty')
        # A mask channel means a local slot within a texture-set, not a global ID.
        set_id, layer = divmod(slot, 8)
        block_sets = {int(e.get('i')): int(e.get('tileSet')) for e in terrain.height.findall('blockTextureSetList/blockTextureSet')}
        mode = op.get('mode', 'add')
        if mode not in ('add', 'remove', 'set', 'blur', 'uniform'):
            raise ValueError('Unknown texture mode')
        strength = number(op.get('strength', 1))
        if not 0 <= strength <= 1:
            raise ValueError('strength must be within 0..1')
        snapshot = Masks(masks.encode()) if mode == 'blur' else masks
        touched = set()
        for x, y, w in coordinates(masks, terrain, op, 8):
            bx, by = x // 64, y // 64
            current_set = block_sets.get(by * ((terrain.dim[0] - 1) // 8) + bx, 0)
            if set_id != current_set:
                raise NeedsEvidence('Cross-set painting requires texture-set allocation evidence; choose a slot in the existing block set')
            values = snapshot.get(x, y)
            alpha = strength * w
            if mode == 'blur':
                neighbors = [snapshot.get(xx, yy) for yy in range(max(0, y - 1), min(masks.height, y + 2))
                             for xx in range(max(0, x - 1), min(masks.width, x + 2))]
                target = [sum(v[i] for v in neighbors) / len(neighbors) for i in range(8)]
            elif mode == 'uniform':
                target = [number(v) for v in op['weights']]
                if len(target) != 8 or any(not 0 <= v <= 15 for v in target):
                    raise ValueError('uniform requires 8 weights within 0..15')
            elif mode == 'remove':
                target = values[:]
                target[layer] = 0
            else:
                target = [0] * 8 if mode == 'set' else values[:]
                target[layer] = 15
            masks.set(x, y, [max(0, min(15, round(v * (1 - alpha) + t * alpha))) for v, t in zip(values, target)])
            touched.add((x // 8, y // 8))
        if not touched:
            raise ValueError('Brush covers no mask samples')
        for x, y in touched:
            totals = [0] * 8
            for yy in range(y * 8, y * 8 + 8):
                for xx in range(x * 8, x * 8 + 8):
                    totals = [a + b for a, b in zip(totals, masks.get(xx, yy))]
            sync.set(x, y, set_id * 8 + max(range(8), key=lambda i: totals[i]))
        self.put('t3TextureMasks', masks.encode())
        self.put('t3SyncTextureInfo', sync.encode())
        self.notes.append('Sync texture uses dominant painted weight; verify surface gameplay properties after Editor save')

    def water(self, op):
        require_keys(op, 'mode rect type index')
        water = Water(self.read('t3Water'))
        mode = op.get('mode', 'add')
        if mode == 'remove':
            index = int(op['index'])
            if not 0 <= index < len(water.entries):
                raise ValueError('Water entry index out of bounds')
            del water.entries[index]
        elif mode in ('add', 'update'):
            box = region_box(op, self.terrain)
            name = str(op['type']).encode('ascii')
            if not name or len(name) > 39 or b'\0' in name:
                raise ValueError('Water type must be 1..39 ASCII bytes')
            # A type is a water configuration ID; its height/state is not in this rectangle.
            known = {e['type'] for e in water.describe()}
            config_file = 'Base.SC2Data/GameData/WaterData.xml'
            if (self.terrain.path/config_file).exists():
                known.update(e.get('id') for e in self.xml(config_file).findall('CWater'))
            if name.decode() not in known:
                raise NeedsEvidence('Water type must exist in this map; adding another type requires catalog/Editor configuration evidence')
            entry = (name.ljust(40, b'\0'), tuple(box))
            if mode == 'add':
                water.entries.append(entry)
            else:
                index = int(op['index'])
                if not 0 <= index < len(water.entries):
                    raise ValueError('Water entry index out of bounds')
                water.entries[index] = entry
        else:
            raise ValueError('Unknown water mode')
        self.put('t3Water', water.encode())

    def water_config(self, op):
        """Only explicit map-local water states; never guess inherited values."""
        require_keys(op, 'mode id template state new_state values')
        name = 'Base.SC2Data/GameData/WaterData.xml'
        if not (self.terrain.path/name).exists():
            raise NeedsEvidence('Water configuration editing requires an existing map-local WaterData.xml')
        root = self.xml(name)
        if root.tag!='Catalog':
            raise ValueError('Invalid local water catalog')
        mode = op.get('mode','update')
        identity = str(op['id'])
        matches = [e for e in root.findall('CWater') if e.get('id')==identity]
        if mode=='clone':
            if matches or not identity or len(identity.encode('ascii'))>39 or '\0' in identity:
                raise ValueError('New water ID must be unique and 1..39 ASCII bytes')
            templates = [e for e in root.findall('CWater') if e.get('id')==str(op['template'])]
            if len(templates)!=1:
                raise NeedsEvidence('Water clone needs one explicit local template')
            node=copy.deepcopy(templates[0])
            node.set('id',identity)
            root.append(node)
        else:
            if len(matches)!=1:
                raise NeedsEvidence('Water ID must have exactly one explicit local definition')
            node=matches[0]
        state = str(int(op.get('state',0)))
        states = [e for e in node.findall('State') if e.get('index')==state]
        if len(states)!=1:
            raise NeedsEvidence('Water state must already be explicitly defined locally')
        target=states[0]
        if mode=='clone-state':
            index=int(op['new_state'])
            if not 0<=index<2**32 or any(e.get('index')==str(index) for e in node.findall('State')):
                raise ValueError('New water state index must be unique and uint32')
            target=copy.deepcopy(target)
            target.set('index',str(index))
            node.append(target)
        elif mode not in ('update','clone'):
            raise ValueError('Unknown water configuration mode')
        scalar_fields=set('Height ColorFallOff CausticsFallOff Specularity SpecularScaler UvRotate MeshRoughness TextureRoughness ReflectionDistortion RefractionDistortion ShadowDistortion MinReflection ReflectivityPower'.split())
        for field,value in op.get('values',{}).items():
            elements=target.findall(field)
            if len(elements)!=1 or (field not in scalar_fields and field not in ('Name','Color','UvRate')):
                raise NeedsEvidence('Water property must be an explicit supported local field: '+field)
            if field in scalar_fields:
                value=fmt(value)
            elif field in ('Color','UvRate'):
                values=vector(str(value),4) if isinstance(value,str) else [number(v) for v in value]
                if len(values)!=4 or (field=='Color' and any(not 0<=v<=1 for v in values)):
                    raise ValueError('Invalid water vector/color')
                value=csv(values)
            elements[0].set('value',str(value))
        self.put_xml(name,root)
        self.notes.append('Water configuration edits affect every rectangle using ID '+identity+'; only explicit local state fields were used')

    def objects(self, op):
        require_keys(op, 'mode selector kind template position attributes children offset pivot angle scale mirror axis spacing name face_towards grounding')
        if 'grounding' in op and (op['grounding'] not in ('preserve-offset', 'snap', 'keep-z')
                                  or op.get('mode') not in ('add', 'duplicate', 'update', 'transform', 'align', 'distribute')):
            raise ValueError('grounding requires a spatial object operation and preserve-offset/snap/keep-z')
        if 'face_towards' in op:
            if op.get('mode') not in ('add', 'duplicate', 'update', 'transform'):
                raise ValueError('face_towards requires add/duplicate/update/transform')
            if 'Rotation' in op.get('attributes', {}):
                raise ValueError('Choose face_towards or explicit Rotation')
        root = self.xml('Objects')
        ground_sources = {e.get('Id'): (vector(e.get('Position'), 3), self.absolute_doodad(e))
                          for e in root.findall('ObjectDoodad')}
        ground_targets = []
        mode = op['mode']
        if mode == 'add':
            kind = op['kind']
            if kind not in TAGS or kind == 'group':
                raise ValueError('Unsupported placed object kind')
            if 'template' not in op:
                raise ValueError('add requires a selector for an existing, validated template')
            template = selected(root, op['template'])
            if len(template) != 1 or template[0].tag != TAGS[kind]:
                raise ValueError('Expected one same-kind template')
            if kind == 'point' and template[0].get('Type') == 'StartLoc':
                raise NeedsEvidence('Start-location creation requires MapInfo linkage evidence; choose a normal point')
            e = copy.deepcopy(template[0])
            e.set('Id', str(max(int(n.get('Id', 0)) for n in root if n.tag != 'Group') + 1))
            if op.get('position') is None:
                raise ValueError('add requires position')
            self.transform(e, op)
            self.set_attributes(e, op.get('attributes', {}))
            self.set_children(e, op.get('children', []))
            self.face_towards(e, op)
            root.append(e)
            ground_targets.append(e)
            self.notes.append('Added object Id=' + e.get('Id'))
        else:
            targets = selected(root, op['selector'])
            if mode == 'group':
                kinds = {e.tag for e in targets}
                if len(kinds) != 1 or 'Group' in kinds:
                    raise ValueError('Group members must have one placed object kind')
                e = ET.SubElement(root, 'Group', {'Id': str(max((int(n.get('Id', 0)) for n in root if n.tag == 'Group'), default=0) + 1),
                                                 'Type': targets[0].tag, 'Name': op.get('name', 'Terrain tools group')})
                for target in targets:
                    ET.SubElement(e, 'GroupObject', {'Id': target.get('Id')})
            elif mode == 'ungroup':
                if any(e.tag != 'Group' for e in targets):
                    raise ValueError('ungroup selects Group nodes')
                for e in targets:
                    root.remove(e)
            elif mode == 'delete':
                for e in targets:
                    kind = next((k for k, v in TAGS.items() if v == e.tag), None)
                    if kind == 'group' or (kind == 'point' and e.get('Type') == 'StartLoc'):
                        raise NeedsEvidence('Start locations/group removal require dedicated linkage handling')
                    if self.referenced(kind, e.get('Id')):
                        raise ValueError('Object is referenced by triggers/generated script: ' + e.get('Id'))
                    for group in root.findall('Group'):
                        if group.get('Type') == e.tag:
                            for member in list(group.findall('GroupObject')):
                                if member.get('Id') == e.get('Id'):
                                    group.remove(member)
                    root.remove(e)
            elif mode == 'duplicate':
                next_id = max(int(n.get('Id', 0)) for n in root if n.tag != 'Group') + 1
                for e in targets:
                    if e.tag == 'Group' or (e.tag == 'ObjectPoint' and e.get('Type') == 'StartLoc'):
                        raise NeedsEvidence('Group/start-location duplication requires linkage evidence')
                    new = copy.deepcopy(e)
                    new.set('Id', str(next_id))
                    next_id += 1
                    if e.tag == 'ObjectDoodad':
                        ground_sources[new.get('Id')] = (vector(e.get('Position'), 3), self.absolute_doodad(e))
                    self.transform(new, op)
                    self.set_attributes(new, op.get('attributes', {}))
                    self.set_children(new, op.get('children', []))
                    self.face_towards(new, op)
                    root.append(new)
                    ground_targets.append(new)
            elif mode in ('update', 'transform', 'align', 'distribute'):
                ground_targets = targets
                if any(e.tag == 'Group' for e in targets):
                    raise ValueError('Select group members for spatial transforms')
                if mode in ('align', 'distribute'):
                    axis = {'x': 0, 'y': 1, 'z': 2}.get(op.get('axis', 'x'))
                    if axis is None:
                        raise ValueError('axis must be x, y or z')
                    targets.sort(key=lambda e: vector(e.get('Position'), 3)[axis])
                    first = vector(targets[0].get('Position'), 3)[axis]
                    step = number(op.get('spacing', 1))
                    for i, e in enumerate(targets):
                        pos = vector(e.get('Position'), 3)
                        pos[axis] = first if mode == 'align' else first + i * step
                        e.set('Position', csv(pos))
                for e in targets:
                    self.set_attributes(e, op.get('attributes', {}))
                    if mode in ('update', 'transform') and any(k in op for k in ('position', 'offset', 'pivot', 'angle', 'scale', 'mirror')):
                        self.transform(e, op)
                    self.set_children(e, op.get('children', []))
                    self.face_towards(e, op)
            else:
                raise ValueError('Unknown object operation mode')
        self.ground_doodads(ground_targets, op, ground_sources)
        self.validate_positions(root)
        self.put_xml('Objects', root)

    @staticmethod
    def absolute_doodad(e):
        return e.tag == 'ObjectDoodad' and any(c.get('Index') == 'HeightAbsolute' and c.get('Value') == '1' for c in e.findall('Flag'))

    def ground_doodads(self, targets, op, sources):
        grid = None
        def ground(x, y):
            nonlocal grid
            terrain = self.terrain
            if terrain.scale != [1, 1, 1] or terrain.offset != [0, 0, 0]:
                raise NeedsEvidence('Doodad grounding requires unit terrain scale and zero offset')
            if grid is None:
                grid = Grid(self.read('t3HeightMap'), b'HMAP', {101}, 32, '<HHH')
            if not (0 <= x <= grid.width - 1 and 0 <= y <= grid.height - 1):
                raise ValueError('Grounded doodad is outside terrain')
            ix, iy = min(math.floor(x), grid.width - 2), min(math.floor(y), grid.height - 2)
            fx, fy = x - ix, y - iy
            samples = [(grid.get(xx, yy), w) for xx, yy, w in
                       [(ix, iy, (1-fx)*(1-fy)), (ix+1, iy, fx*(1-fy)),
                        (ix, iy+1, (1-fx)*fy), (ix+1, iy+1, fx*fy)] if w > 0]
            if len({sample[2] for sample, _ in samples}) > 1:
                raise NeedsEvidence('Ground sampling across a cliff edge requires native geometry evidence; choose keep-z or a clear location')
            return sum(terrain.local_height(*sample[:2]) * w for sample, w in samples)
        for e in targets:
            explicit = op.get('grounding')
            if explicit == 'keep-z':
                continue
            if not self.absolute_doodad(e):
                if explicit:
                    raise NeedsEvidence('Grounding currently supports HeightAbsolute=1 doodads only')
                continue
            mode = explicit or ('keep-z' if 'position' in op or (op['mode'] in ('align', 'distribute') and op.get('axis', 'x') == 'z') else 'preserve-offset')
            if mode == 'keep-z':
                continue
            pos = vector(e.get('Position'), 3)
            if mode == 'snap':
                z = ground(*pos[:2])
            else:
                before = sources.get(e.get('Id'))
                if before is None or not before[1]:
                    if explicit:
                        raise NeedsEvidence('Preserving ground offset requires an existing absolute-height source')
                    continue
                if pos[:2] == before[0][:2]:
                    continue
                z = pos[2] + ground(*pos[:2]) - ground(*before[0][:2])
            if abs(z - pos[2]) > 1e-8:
                self.notes.append('Grounded doodad Id=' + e.get('Id') + ' using ' + mode + ': Z ' + fmt(pos[2]) + ' to ' + fmt(z))
                e.set('Position', csv([pos[0], pos[1], z]))

    def face_towards(self, e, op):
        if 'face_towards' not in op:
            return
        if e.tag not in ('ObjectUnit', 'ObjectDoodad'):
            raise ValueError('face_towards supports units and doodads only')
        target = [number(v) for v in op['face_towards']]
        if len(target) != 2:
            raise ValueError('face_towards requires target XY')
        x, y = vector(e.get('Position'), 3)[:2]
        if target == [x, y]:
            raise ValueError('Facing target must differ from object position')
        e.set('Rotation', fmt(math.atan2(target[1] - y, target[0] - x)))

    def set_children(self, e, children):
        for child in children:
            tag=child.get('tag')
            contract=object_contract(e.tag)
            if tag not in contract['children'] or tag in ('Texture','GroupObject','PatrolPoint'):
                raise ValueError('Unsupported indexed child for '+e.tag)
            fields=contract['children'][tag]
            key='Index' if 'Index' in fields else 'Type'
            input_key=key.lower()
            if set(child)-{'tag',input_key,'value','remove'} or input_key not in child:
                raise ValueError('Indexed child requires '+input_key+' and value, or remove=true')
            identity=str(child[input_key])
            enum=contract['enums'].get(fields[key]['type'])
            if enum and identity not in enum:
                raise ValueError('Unsupported child index/type: '+identity)
            match = next((n for n in e.findall(tag) if n.get(key) == identity), None)
            if child.get('remove'):
                if match is not None:e.remove(match)
                continue
            if match is None:
                match=ET.SubElement(e,tag,{key:identity})
            number(child['value'])
            value=fmt(child['value']) if fields['Value']['type']=='FixedValue' else str(child['value'])
            match.set('Value', value)

    def set_attributes(self, e, attributes):
        allowed = set(object_contract(e.tag)['attributes'])-{'Id','Position','ObjectId','ObjectType'}
        if set(attributes) - allowed:
            raise ValueError('Unsupported attribute for ' + e.tag + ': ' + str(set(attributes) - allowed))
        if e.tag == 'ObjectPoint' and e.get('Type') == 'StartLoc' and 'Type' in attributes:
            raise NeedsEvidence('Changing a start-location type requires MapInfo linkage evidence')
        if 'Type' in attributes and attributes['Type'] == 'StartLoc' and e.get('Type') != 'StartLoc':
            raise NeedsEvidence('Creating a start location requires MapInfo linkage evidence')
        for key, value in attributes.items():
            if key in ('Rotation', 'Pitch', 'Roll', 'Resources', 'BoostexCliffLevel', 'PathingRadiusHard', 'PathingRadiusSoft'):
                number(value)
            if key in ('Scale',):
                if any(v <= 0 for v in vector(str(value), 3)):
                    raise ValueError('Scale components must be positive')
            if key == 'CameraTarget':
                vector(str(value), 2)
            if key == 'Player' and not 0 <= int(value) <= 15:
                raise ValueError('Player must be 0..15')
            if key == 'Variation' and int(value) < 0:
                raise ValueError('Variation must be nonnegative')
            if key in ('UnitType', 'Type') and value != e.get(key):
                # Asset availability is proved by an existing same-kind placed instance.
                objects = self.xml('Objects')
                if not any(n.tag == e.tag and n.get(key) == str(value) for n in objects):
                    raise NeedsEvidence('Replacement type needs an existing same-kind instance or catalog validation')
            e.set(key, str(value))

    def transform(self, e, op):
        pos = vector(e.get('Position'), 3)
        old_position = pos[:]
        if 'position' in op:
            pos = [number(v) for v in op['position']]
            if len(pos) != 3:
                raise ValueError('position requires xyz')
        pivot = [number(v) for v in op.get('pivot', [0, 0, 0])]
        offset = [number(v) for v in op.get('offset', [0, 0, 0])]
        if len(pivot) != 3 or len(offset) != 3:
            raise ValueError('pivot/offset require xyz')
        angle = number(op.get('angle', 0))  # radians, same as placed Rotation
        mirror = op.get('mirror')
        if mirror not in (None, 'x', 'y'):
            raise ValueError('mirror must be x or y')
        dx, dy = pos[0] - pivot[0], pos[1] - pivot[1]
        old_rot = number(e.get('Rotation', 0))
        if mirror == 'x':
            dx, old_rot = -dx, math.pi - old_rot
        if mirror == 'y':
            dy, old_rot = -dy, -old_rot
        factor = number(op.get('scale', 1))
        if factor <= 0:
            raise ValueError('scale must be positive')
        nx = (dx * math.cos(angle) - dy * math.sin(angle)) * factor + pivot[0] + offset[0]
        ny = (dx * math.sin(angle) + dy * math.cos(angle)) * factor + pivot[1] + offset[1]
        nz = (pos[2] - pivot[2]) * factor + pivot[2] + offset[2]
        e.set('Position', csv([nx, ny, nz]))
        if angle or mirror:
            e.set('Rotation', fmt(old_rot + angle))
        if factor != 1:
            e.set('Scale', csv(v * factor for v in vector(e.get('Scale', '1,1,1'), 3)))
        if e.tag == 'ObjectCamera':
            target = vector(e.get('CameraTarget', csv(pos[:2])), 2)
            tx, ty = target[0] - old_position[0], target[1] - old_position[1]
            if mirror == 'x': tx = -tx
            if mirror == 'y': ty = -ty
            e.set('CameraTarget', csv([nx + (tx * math.cos(angle) - ty * math.sin(angle)) * factor,
                                      ny + (tx * math.sin(angle) + ty * math.cos(angle)) * factor]))
            yaw = next((c for c in e.findall('CameraValue') if c.get('Index') == 'Yaw'), None)
            if yaw is not None and (angle or mirror):
                degrees = number(yaw.get('Value'))
                if mirror == 'x': degrees = 180 - degrees
                if mirror == 'y': degrees = -degrees
                yaw.set('Value', fmt(degrees + math.degrees(angle)))

    def validate_positions(self, root):
        # Validate modified/new nodes via caller comparison; campaign cameras can
        # legitimately sit outside the playable map, so do not reject old nodes.
        for e in root:
            if e.get('Position'):
                vector(e.get('Position'), 3)

    def regions(self, op):
        require_keys(op, 'mode selector name shapes offset')
        root = self.xml('Regions')
        mode = op['mode']
        if mode == 'add':
            identity = max((int(e.get('id', 0)) for e in root), default=0) + 1
            e = ET.SubElement(root, 'region', {'id': str(identity)})
            ET.SubElement(e, 'name', {'value': str(op.get('name', 'Terrain tools region'))})
            ET.SubElement(e, 'color', {'value': '255,0,128,0'})
            self.add_shapes(e, op['shapes'])
            self.notes.append('Added region id=' + str(identity))
        else:
            targets = selected(root, op['selector'])
            if mode == 'merge':
                for e in targets[1:]:
                    # Keep source region identities/references. Merge copies shapes
                    # into the destination, rather than deleting referenced regions.
                    for shape in e.findall('shape'):
                        targets[0].append(copy.deepcopy(shape))
            elif mode == 'delete':
                for e in targets:
                    if self.referenced('region', e.get('id')):
                        raise ValueError('Region is referenced by triggers: ' + e.get('id'))
                    root.remove(e)
            elif mode in ('update', 'move'):
                for e in targets:
                    if 'name' in op:
                        e.find('name').set('value', str(op['name']))
                    if 'shapes' in op:
                        for shape in list(e.findall('shape')):
                            e.remove(shape)
                        self.add_shapes(e, op['shapes'])
                    dx, dy = [number(v) for v in op.get('offset', [0, 0])]
                    for shape in e.findall('shape'):
                        center = shape.find('center')
                        if center is not None:
                            x, y = vector(center.get('value'), 2)
                            center.set('value', csv([x + dx, y + dy]))
                        quad = shape.find('quad')
                        if quad is not None:
                            a, b, c, d = vector(quad.get('value'), 4)
                            quad.set('value', csv([a + dx, b + dy, c + dx, d + dy]))
            else:
                raise ValueError('Unknown region mode')
        self.put_xml('Regions', root)

    def add_shapes(self, node, shapes):
        if not isinstance(shapes, list) or not shapes:
            raise ValueError('At least one region shape is required')
        for shape in shapes:
            kind = shape['type']
            child = ET.SubElement(node, 'shape', {'type': kind})
            if kind == 'rect':
                quad = shape['rect']
                if len(quad) != 4 or not number(quad[0]) < number(quad[2]) or not number(quad[1]) < number(quad[3]):
                    raise ValueError('Invalid rectangle region')
                ET.SubElement(child, 'quad', {'value': csv(quad)})
            elif kind in ('circle', 'diamond'):
                center = shape['center']
                if len(center) != 2:
                    raise ValueError('Region center needs xy')
                ET.SubElement(child, 'center', {'value': csv(center)})
                for prop in ('radius',) if kind == 'circle' else ('width', 'height'):
                    value = number(shape[prop])
                    if value <= 0:
                        raise ValueError('Region size must be positive')
                    ET.SubElement(child, prop, {'value': fmt(value)})
            else:
                raise NeedsEvidence('Unsupported region shape: ' + kind)

    def foliage(self, op):
        require_keys(op, 'mode rect offset seed density template_flag')
        foliage = Foliage(self.read('t3FluffDoodad'))
        box = region_box(op, self.terrain)
        mode = op['mode']
        if mode == 'remove':
            foliage.entries = [e for e in foliage.entries if not in_box(*struct.unpack('<ffB', e)[:2], box)]
        elif mode == 'prioritize':
            # Controlled ordering probe: preserve every record and relative order
            # within each partition, changing only the selected prefix.
            inside, outside = [], []
            for entry in foliage.entries:
                (inside if in_box(*struct.unpack('<ffB', entry)[:2], box) else outside).append(entry)
            foliage.entries = inside + outside
        elif mode == 'scatter':
            self.notes.append('New foliage instances are prioritized before existing records; visible models still depend on the native flag/texture profile')
            known = {f for _, _, f in foliage.positions()}
            flag = int(op['template_flag'])
            if flag not in known:
                raise NeedsEvidence('Foliage flag must be observed in this map; it is not a catalog ID')
            density = number(op.get('density', 0.1))
            if density < 0:
                raise ValueError('Foliage density must be nonnegative')
            count = round((box[2] - box[0]) * (box[3] - box[1]) * density)
            if not 0 <= count <= 100000:
                raise ValueError('Invalid/oversized foliage density')
            rng = random.Random(int(op.get('seed', 0)))
            new_entries = [struct.pack('<ffB', rng.uniform(box[0], box[2]), rng.uniform(box[1], box[3]), flag)
                           for _ in range(count)]
            foliage.entries = new_entries + foliage.entries
        else:
            raise NeedsEvidence('Foliage allow/disallow paint semantics require an Editor pair')
        self.put('t3FluffDoodad', foliage.encode())

    def creep(self, op):
        """Whole-world-cell prepainted creep; preserve finer samples outside it."""
        if (self.terrain.path / 'PaintedCreepLayer').exists():
            raise NeedsEvidence('Legacy PaintedCreepLayer migration requires an Editor baseline before CellAttribute_Cpl editing')
        self.cell_attribute_brush(op, 'CellAttribute_Cpl')

    def visibility(self, op):
        """Paint/remove the observed vision-blocker layer, not global fog settings."""
        self.cell_attribute_brush(op, 'CellAttribute_Vbl')

    def pathing(self, op):
        """Supplemental no-ground-path paint; does not override native obstacles."""
        if self.blockers and self.blockers.get('base_cells'):
            raise ValueError('Sync/remove owned doodad blockers before manual pathing paint; preserve their baseline')
        if (self.terrain.path / 'PaintedPathingLayer').exists():
            raise NeedsEvidence('Legacy PaintedPathingLayer migration requires a native baseline')
        self.cell_attribute_brush(op, 'CellAttribute_Pnp')
        self.blockers = None

    def doodad_blockers(self, op):
        require_keys(op, 'selector profiles keep_clear allow_empty')
        if (self.terrain.path / 'PaintedPathingLayer').exists():
            raise NeedsEvidence('Legacy pathing must be migrated before supplementing blockers')
        terrain = self.terrain
        if terrain.scale[:2] != [1, 1] or terrain.offset[:2] != [0, 0]:
            raise NeedsEvidence('Blocker raster requires unit XY scale and zero XY offset')
        width, height = terrain.dim[0] - 1, terrain.dim[1] - 1
        data = self.original('CellAttribute_Pnp')
        original_present = data is not None
        data = self.read('CellAttribute_Pnp') if 'CellAttribute_Pnp' in self.changes or original_present else struct.pack('<I', width * height * 8) + bytes(width * height)
        if CellAttribute(data).bits != width * height * 8:
            raise NeedsEvidence('Pnp dimensions do not match terrain')
        raw = bytearray(data)
        if self.blockers is not None:
            state = self.blockers
            if (state.get('schema_version') != 1 or state.get('dimensions') != [width, height]
                    or state.get('pnp_sha256') != sha(data)):
                raise ValueError('Owned blocker state does not match Pnp; preserve external edits and reconcile before sync')
            seen = set()
            for index, before in state['base_cells']:
                if (not isinstance(index, int) or not 0 <= index < width * height or index in seen
                        or not isinstance(before, int) or not 0 <= before <= 255 or raw[4 + index] != 255):
                    raise ValueError('Invalid owned blocker cell')
                seen.add(index)
                raw[4 + index] = before
        selector = dict(op['selector'])
        if selector.get('kind', 'doodad') != 'doodad':
            raise ValueError('Supplemental blockers select doodads only; units retain native dynamic blocking')
        selector['kind'] = 'doodad'
        try:
            targets = selected(self.xml('Objects'), selector)
        except ValueError as exc:
            if str(exc) != 'Selector matched no objects' or op.get('allow_empty') is not True:
                raise
            targets = []
        profiles = op['profiles']
        if not isinstance(profiles, dict):
            raise ValueError('profiles must map existing doodad Type to a verified occupancy profile')
        clear = [region_box({'rect': box}, terrain) for box in op.get('keep_clear', [])]
        cells, skipped = set(), 0
        for e in targets:
            profile = profiles.get(e.get('Type'))
            if not isinstance(profile, dict) or not isinstance(profile.get('evidence'), str) or not profile['evidence'].strip():
                raise NeedsEvidence('Missing verified footprint profile for ' + str(e.get('Type')))
            if set(profile) - {'mode', 'rect', 'evidence'}:
                raise ValueError('Unknown footprint profile property')
            if profile.get('mode') == 'native':
                if 'rect' in profile:
                    raise ValueError('Native blocking profile must not add permanent paint')
                skipped += 1
                continue
            if profile.get('mode') != 'static':
                raise ValueError('Profile mode must explicitly be static supplemental scenery or native')
            box = [number(v) for v in profile['rect']]
            if len(box) != 4 or not (box[0] < box[2] and box[1] < box[3]):
                raise ValueError('Profile rect must be a nonempty local XY rectangle')
            x, y = vector(e.get('Position'), 3)[:2]
            sx, sy, _ = vector(e.get('Scale', '1,1,1'), 3)
            if sx <= 0 or sy <= 0:
                raise ValueError('Footprint scale must be positive')
            angle = number(e.get('Rotation', 0)); c, s = math.cos(angle), math.sin(angle)
            polygon = [(x + u * sx * c - v * sy * s, y + u * sx * s + v * sy * c)
                       for u, v in [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]]
            if any(not (0 <= px <= width and 0 <= py <= height) for px, py in polygon):
                raise ValueError('Transformed footprint extends beyond terrain')
            # A whole-cell conservative raster. SAT rejects touching edges only;
            # native finer sample layout remains unmeasured.
            axes = [(1, 0), (0, 1), (c, s), (-s, c)]
            projections = [(ax, ay, min(px * ax + py * ay for px, py in polygon),
                            max(px * ax + py * ay for px, py in polygon)) for ax, ay in axes]
            for cy in range(math.floor(min(p[1] for p in polygon)), math.ceil(max(p[1] for p in polygon))):
                for cx in range(math.floor(min(p[0] for p in polygon)), math.ceil(max(p[0] for p in polygon))):
                    if any(min(cx * ax, (cx + 1) * ax) + min(cy * ay, (cy + 1) * ay) >= high - 1e-9
                           or max(cx * ax, (cx + 1) * ax) + max(cy * ay, (cy + 1) * ay) <= low + 1e-9
                           for ax, ay, low, high in projections):
                        continue
                    if any(cx < b[2] and cx + 1 > b[0] and cy < b[3] and cy + 1 > b[1] for b in clear):
                        raise ValueError('Supplemental footprint conflicts with a keep_clear route')
                    cells.add(cy * width + cx)
        base_cells = [[index, raw[4 + index]] for index in sorted(cells)]
        for index in cells:
            raw[4 + index] = 255
        result = bytes(raw)
        if original_present or cells or 'CellAttribute_Pnp' in self.changes:
            self.put('CellAttribute_Pnp', result)
        recipe = {**copy.deepcopy(op), 'allow_empty': True,
                  'selector': {'kind': 'doodad', 'ids': [e.get('Id') for e in targets]}}
        self.blockers = ({'schema_version': 1, 'dimensions': [width, height],
                          'pnp_sha256': sha(result), 'base_cells': base_cells, 'recipe': recipe}
                         if cells else None)
        self.notes.append(f'Supplemental static doodad blockers: {len(cells)} whole cells; {skipped} native profiles unchanged. Occupancy is explicit evidence, not inferred model bounds')

    def lighting(self, op):
        require_keys(op, 'mode rect shape falloff strength region')
        terrain = self.terrain
        if terrain.scale[:2] != [1, 1] or terrain.offset[:2] != [0, 0]:
            raise NeedsEvidence('Lighting painting requires unit XY scale and zero XY offset')
        try:
            raster = LightingMap(self.read('LightingMap.tga'))
        except FileNotFoundError as exc:
            raise NeedsEvidence('Lighting painting currently requires an existing Editor-authored LightingMap.tga') from exc
        if (raster.width, raster.height) != ((terrain.dim[0] - 1) * 4, (terrain.dim[1] - 1) * 4):
            raise NeedsEvidence('Lighting raster/world sampling ratio not recognized')
        mode, region = op.get('mode'), op.get('region', 2)
        if mode not in ('add', 'remove') or region not in (1, 2):
            raise NeedsEvidence('Only add of Editor light regions 1/2 and remove of region 2 have encoding evidence')
        if mode == 'remove' and region != 2:
            raise ValueError('Removing lighting restores region 2 weights to default region 1')
        strength = number(op.get('strength', 1))
        if not 0 <= strength <= 1:
            raise ValueError('strength must be within 0..1')
        touched = False
        for x, y, w in coordinates(raster, terrain, op, 4):
            old = raster.get(x, y)
            if old[0] or old[3]:
                raise NeedsEvidence('The selected patch contains unverified light-region channels')
            target = [0, 0, 255, 0] if mode == 'remove' or region == 1 else [0, 255, 0, 0]
            alpha = strength * w
            if alpha == 0:
                touched = True
                continue
            green = max(0, min(255, round(old[1] * (1 - alpha) + target[1] * alpha)))
            raster.set(x, y, [0, green, 255 - green, 0])
            touched = True
        if not touched:
            raise ValueError('Brush covers no lighting pixels')
        self.put('LightingMap.tga', raster.encode())
        self.notes.append('Paints existing light-region 1/2 weights; light definitions, other regions and global lighting are unchanged')

    def cell_attribute_brush(self, op, name):
        require_keys(op, 'mode rect shape')
        if op.get('mode') not in ('paint', 'remove'):
            raise ValueError('Cell brush mode must be paint or remove')
        terrain = self.terrain
        if terrain.scale[:2] != [1, 1] or terrain.offset[:2] != [0, 0]:
            raise NeedsEvidence('Cell painting requires unit XY scale and zero XY offset')
        box = region_box(op, terrain)
        if any(v != int(v) for v in box):
            raise NeedsEvidence('Cell brush bounds must align to whole world cells')
        if op.get('shape', 'rect') not in ('rect', 'circle', 'diamond'):
            raise ValueError('shape must be rect, circle or diamond')
        width, height = terrain.dim[0] - 1, terrain.dim[1] - 1
        try:
            data = self.read(name)
        except FileNotFoundError:
            if op['mode'] == 'remove':
                return
            data = struct.pack('<I', width * height * 8) + bytes(width * height)
        if CellAttribute(data).bits != width * height * 8:
            raise NeedsEvidence('Cell raster dimensions do not match terrain')
        raw = bytearray(data)
        for y in range(int(box[1]), int(box[3])):
            for x in range(int(box[0]), int(box[2])):
                if weight(x + 0.5, y + 0.5, box, op):
                    raw[4 + y * width + x] = 255 if op['mode'] == 'paint' else 0
        self.put(name, bytes(raw))
        self.notes.append('Whole-cell '+name+' painting only; finer native samples and gameplay behavior require separate validation')

    def roads(self, op):
        require_keys(op, 'mode group offset type points')
        roads = HardTiles(self.read('t3HardTile'))
        index = int(op['group'])
        if not 0 <= index < len(roads.groups):
            raise ValueError('Road group index out of bounds')
        group = roads.groups[index]
        if 'type' in op and str(op['type']) != group['name']:
            raise NeedsEvidence('Road material replacement requires catalog and Editor evidence')
        if op['mode'] == 'add':
            roads.groups.append(self.straight_road(group, op['points']))
        elif op['mode'] == 'remove':
            del roads.groups[index]
        elif op['mode'] in ('duplicate', 'move'):
            if op['mode'] == 'duplicate':
                group = copy.deepcopy(group)
                roads.groups.append(group)
            offset = [number(v) for v in op['offset']]
            if len(offset) != 3:
                raise ValueError('Road offset requires xyz')
            for i, entry in enumerate(group['tiles']):
                raw = bytearray(entry)
                pos = struct.unpack_from('<3f', raw)
                struct.pack_into('<3f', raw, 0, *(a + b for a, b in zip(pos, offset)))
                group['tiles'][i] = bytes(raw)
        else:
            raise NeedsEvidence('New road spline/width generation requires Editor evidence; only complete existing groups can be moved/copied/removed')
        self.put('t3HardTile', roads.encode())

    def straight_road(self, template, points):
        """Reuse a native two-endpoint road profile on a gentle, single-level patch."""
        terrain = self.terrain
        if terrain.scale != [1, 1, 1] or terrain.offset != [0, 0, 0]:
            raise NeedsEvidence('Straight roads require unit scale and zero offset')
        if not isinstance(points, list) or len(points) != 2 or any(len(p) != 2 for p in points):
            raise ValueError('Straight road points require exactly two XY pairs')
        points = [[number(v) for v in p] for p in points]
        width, height = terrain.dim[0] - 1, terrain.dim[1] - 1
        if any(not (0 <= x < width and 0 <= y < height) for x, y in points):
            raise ValueError('Road endpoints are outside terrain')
        if len(template['tiles']) != 2:
            raise NeedsEvidence('A native straight two-point template group is required')
        records = [list(struct.unpack('<14fBB', raw)) for raw in template['tiles']]
        if ([v[14:] for v in records] != [[1, 0], [0, 1]]
                or any(not all(math.isfinite(f) for f in v[:12]) or v[5] < 0.99
                       or not 0.99 <= math.sqrt(sum(f*f for f in v[3:6])) <= 1.01 for v in records)):
            raise NeedsEvidence('Road template must have observed flat endpoint records')
        old_delta = [b - a for a, b in zip(records[0][:3], records[1][:3])]
        old_length = math.sqrt(sum(v * v for v in old_delta))
        if old_length < 0.01:
            raise ValueError('Degenerate road template')
        old_direction = [v / old_length for v in old_delta]
        for record in records:
            if any(abs(record[6 + i] + old_direction[i]) > 0.001 or abs(record[9 + i] - old_direction[i]) > 0.001 for i in range(3)):
                raise NeedsEvidence('Curved road templates require separate spline evidence')
        grid = Grid(self.read('t3HeightMap'), b'HMAP', {101}, 32, '<HHH')
        def ground(x, y):
            ix, iy = math.floor(x), math.floor(y)
            fx, fy = x - ix, y - iy
            values = [terrain.local_height(*grid.get(xx, yy)[:2]) for xx, yy in ((ix, iy), (ix+1, iy), (ix, iy+1), (ix+1, iy+1))]
            return (values[0]*(1-fx)+values[1]*fx)*(1-fy)+(values[2]*(1-fx)+values[3]*fx)*fy
        length = math.dist(points[0], points[1])
        if not 0.5 <= length <= 64:
            raise ValueError('Straight road length must be 0.5..64 world units')
        count = max(1, math.ceil(length * 2))
        samples = [[points[0][j] + (points[1][j] - points[0][j]) * i / count for j in range(2)] for i in range(count+1)]
        levels = {grid.get(math.floor(x), math.floor(y))[2] for x, y in samples}
        heights = [ground(x, y) for x, y in samples]
        if len(levels) != 1 or max(heights) - min(heights) > 0.125:
            raise NeedsEvidence('Straight road path must stay on gentle terrain within one cliff level')
        positions = [points[0]+[heights[0]], points[1]+[heights[-1]]]
        delta = [b-a for a,b in zip(*positions)]
        magnitude = math.sqrt(sum(v*v for v in delta))
        direction = [v/magnitude for v in delta]
        angle = math.atan2(delta[1],delta[0])-math.atan2(old_delta[1],old_delta[0])
        group = copy.deepcopy(template)
        for i, record in enumerate(records):
            record[:3] = positions[i]
            nx, ny = record[3:5]
            record[3:5] = [nx*math.cos(angle)-ny*math.sin(angle), nx*math.sin(angle)+ny*math.cos(angle)]
            record[6:9], record[9:12] = [-v for v in direction], direction[:]
            group['tiles'][i] = struct.pack('<14fBB', *record)
        self.notes.append('New straight road reuses native profile width/material and opaque group fields; general curves and width changes remain unsupported')
        return group

    def bounds(self, op):
        require_keys(op, 'rect')
        info = MapInfo(self.read('MapInfo'))
        box = [int(v) for v in op['rect']]
        if len(box) != 4 or list(op['rect']) != box or not (0 <= box[0] < box[2] <= info.width and 0 <= box[1] < box[3] <= info.height):
            raise ValueError('Invalid playable bounds')
        old = info.bounds
        delta = 2 * ((box[2] - box[0]) ** 2 + (box[3] - box[1]) ** 2
                     - (old[2] - old[0]) ** 2 - (old[3] - old[1]) ** 2)
        old_hash = struct.unpack_from('<Q', info.raw, 8)[0]
        new_hash = old_hash + delta
        if not 0 <= new_hash < 2 ** 64:
            raise ValueError('MapInfo integrity hash overflow')
        struct.pack_into('<Q', info.raw, 8, new_hash)
        struct.pack_into('<4I', info.raw, info.bounds_at, *box)
        self.put('MapInfo', info.encode())

    def cliff_stamp(self, op):
        """Transfer a complete isolated cliff patch between compatible flat areas.

        This reuses geometry already authored in the Editor. It is deliberately
        distinct from a general cliff/ramp brush and never invents their topology.
        """
        require_keys(op, 'template source_center center radius')
        donor = TerrainMap(op['template'])
        target = self.terrain
        if int(donor.xml.get('version')) != 115 or int(target.xml.get('version')) != 115:
            raise NeedsEvidence('Cliff stamping requires already-upgraded v115 maps')
        if donor.scale != [1,1,1] or target.scale != [1,1,1] or donor.offset != [0,0,0] or target.offset != [0,0,0]:
            raise NeedsEvidence('Cliff stamping currently requires unit scale and zero offset')
        source_center = [int(v) for v in op['source_center']]
        center = [int(v) for v in op['center']]
        radius = int(op.get('radius',4))
        if (len(center)!=2 or len(source_center)!=2 or radius<2 or radius>16 or radius%2
                or center != list(op['center']) or source_center != list(op['source_center'])
                or any(v%2 for v in center+source_center)):
            raise ValueError('Cliff stamp centers and radius must be even integers; radius 2..16')
        sx,sy = source_center
        tx,ty = center
        sb = [sx-radius,sy-radius,sx+radius,sy+radius]
        tb = [tx-radius,ty-radius,tx+radius,ty+radius]
        region_box({'rect':sb},donor)
        region_box({'rect':tb},target)
        sh = donor.height_grid()
        th = Grid(self.read('t3HeightMap'),b'HMAP',{101},32,'<HHH')
        ss = Grid(donor.read('t3SyncHeightMap'),b'SMAP',{102},64,'<hH')
        ts = Grid(self.read('t3SyncHeightMap'),b'SMAP',{102},64,'<hH')
        sc = Grid(donor.read('t3SyncCliffLevel'),b'CLIF',{100},32,'<H')
        tc = Grid(self.read('t3SyncCliffLevel'),b'CLIF',{100},32,'<H')
        sf = Grid(donor.read('t3CellFlags'),b'LFCT',{101,102},32,'<B',24)
        tf = Grid(self.read('t3CellFlags'),b'LFCT',{101,102},32,'<B',24)
        target_levels = {th.get(x,y)[2] for y in range(tb[1],tb[3]+1) for x in range(tb[0],tb[2]+1)}
        source_edges = {sh.get(x,y)[2] for y in range(sb[1],sb[3]+1) for x in range(sb[0],sb[2]+1)
                        if x in (sb[0],sb[2]) or y in (sb[1],sb[3])}
        source_levels = {sh.get(x,y)[2] for y in range(sb[1],sb[3]+1) for x in range(sb[0],sb[2]+1)}
        if len(target_levels)!=1 or source_edges!=target_levels or len(source_levels)!=2:
            raise NeedsEvidence('Stamp requires a flat destination and an isolated two-level donor with matching flat border')
        level = next(iter(target_levels))
        if source_levels != {level,level+1}:
            raise NeedsEvidence('Only an isolated one-level raised island is supported')
        cliff_names = lambda terrain: [e.get('name') for e in terrain.height.findall('cliffSetList/cliffSet')]
        if cliff_names(donor)!=cliff_names(target) or donor.height.get('tileSet')!=target.height.get('tileSet'):
            raise NeedsEvidence('Cliff palette/tileset must match exactly')
        # A ramp in either patch would require coordinated ramp descriptors and
        # surrounding geometry. Refuse instead of treating it as an island.
        for terrain,box in ((donor,sb),(target,tb)):
            for ramp in terrain.height.findall('rampList/ramp'):
                for value in ramp.attrib.values():
                    for match in re.finditer(r'c=\(([^,]+),\s*([^\)]+)\)',value):
                        if in_box(number(match[1]),number(match[2]),box):
                            raise NeedsEvidence('Stamp intersects an existing ramp descriptor')
        for y in range(tb[1],tb[3]+1):
            for x in range(tb[0],tb[2]+1):
                dx,dy = sx+x-tx,sy+y-ty
                sa,sb_raw,sm = sh.get(dx,dy)
                ta,_,tm = th.get(x,y)
                plateau = sb_raw*donor.quantize-donor.bias
                raw = round((plateau+target.bias)/target.quantize)
                if not 0<=raw<=65535:
                    raise ValueError('Donor plateau exceeds target quantization')
                source_sync,source_mask = ss.get(dx,dy)
                fine_delta = (ta*target.quantize-target.bias)-(sa*donor.quantize-donor.bias)
                new_sync = source_sync+round(fine_delta*256)
                if not -32768<=new_sync<=32767:
                    raise ValueError('Transferred simulation height exceeds range')
                th.set(x,y,(ta,raw,sm))
                ts.set(x,y,(new_sync,source_mask))
                if x<tb[2] and y<tb[3]:
                    if tf.get(x,y)!=(0,) or sf.get(dx,dy)[0] not in (0,1):
                        raise NeedsEvidence('Cell flags need a clear destination and observed 0/1 donor flags')
                    tc.set(x,y,sc.get(dx,dy))
                    tf.set(x,y,sf.get(dx,dy))
        xml = self.xml('t3Terrain.xml')
        cells = xml.find('heightMap/cliffCellList')
        donor_cells = {int(e.get('i')):e for e in donor.height.findall('cliffCellList/cc')}
        if cells is None:
            raise NeedsEvidence('Target has no cliff cell table')
        old = {int(e.get('i')):e for e in cells}
        tw,sw = (target.dim[0]-1)//2,(donor.dim[0]-1)//2
        for y in range(tb[1]//2,tb[3]//2):
            for x in range(tb[0]//2,tb[2]//2):
                target_id=y*tw+x
                source_id=(sy//2+y-ty//2)*sw+sx//2+x-tx//2
                if target_id in old:
                    cells.remove(old[target_id])
                if source_id in donor_cells:
                    node=copy.deepcopy(donor_cells[source_id])
                    node.set('i',str(target_id))
                    cells.append(node)
        cells[:]=sorted(cells,key=lambda e:int(e.get('i')))
        cells.set('numOccupied',str(len(cells)))
        self.put_xml('t3Terrain.xml',xml)
        for name,grid in [('t3HeightMap',th),('t3SyncHeightMap',ts),('t3SyncCliffLevel',tc),('t3CellFlags',tf)]:
            self.put(name,grid.encode())
        self.notes.append('Experimental isolated cliff stamp; vertex-color defaults, procedural pathing and Editor regeneration require validation')

    def apply(self, operations):
        handlers = {'height': self.height, 'texture': self.texture, 'water': self.water,
                    'objects': self.objects, 'regions': self.regions, 'foliage': self.foliage,
                    'roads': self.roads, 'bounds': self.bounds, 'cliff-stamp': self.cliff_stamp,
                    'water-config': self.water_config, 'creep': self.creep,
                    'visibility': self.visibility, 'lighting': self.lighting,
                    'pathing': self.pathing, 'doodad-blockers': self.doodad_blockers}
        if not isinstance(operations, list) or not operations or len(operations) > 1000:
            raise ValueError('Expected 1..1000 operations')
        objects_dirty = False
        for i, op in enumerate(operations):
            if not isinstance(op, dict) or op.get('op') not in handlers:
                raise NeedsEvidence(f'Operation {i}: unsupported operation; consult capabilities and the Editor experiment queue')
            try:
                handlers[op['op']](op)
                if op['op'] == 'objects':
                    objects_dirty = True
                elif op['op'] == 'doodad-blockers':
                    objects_dirty = False
            except (KeyError, TypeError, struct.error) as exc:
                raise ValueError(f'Invalid operation {i} ({op["op"]}): {exc}') from exc
        if objects_dirty and self.blockers and self.blockers.get('recipe'):
            self.doodad_blockers(self.blockers['recipe'])
        # Exclude unchanged files, including no-op operation chains.
        self.changes = {name: data for name, data in self.changes.items() if data != self.original(name)}
        return self.changes
