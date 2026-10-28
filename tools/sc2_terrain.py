"""Lossless SC2 terrain readers. All offsets are checked against file lengths.

The observed campaign corpus is not an Editor acceptance test. Engine-specific
generation and unknown fields must not be silently replaced with guessed data.
"""
from __future__ import annotations

import hashlib
import math
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from functools import lru_cache
from pathlib import Path

from sc2_components import component_path, parse_xml

TERRAIN_FILES = (
    't3Terrain.xml', 't3HeightMap', 't3SyncHeightMap', 't3SyncCliffLevel',
    't3SyncTextureInfo', 't3TextureMasks', 't3CellFlags', 't3FluffDoodad',
    't3HardTile', 't3VertCol', 't3Water', 'LightingMap.tga',
    'PaintedPathingLayer', 'PaintedCreepLayer',
)
CELL_ATTRIBUTE_FILES = tuple('CellAttribute_' + name for name in ('Pnp', 'Pnb', 'Pgr', 'Pde', 'Cpl', 'Cda', 'Vbl', 'Vur'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Finite numbers are required')
    return value


def vector(text, count=None):
    result = [number(v) for v in text.replace(',', ' ').split()]
    if count is not None and len(result) != count:
        raise ValueError(f'Expected {count} coordinates: {text}')
    return result


def fmt(value):
    # PlacedObjects' fixed/vector schema accepts decimal notation, not exponents.
    return format(number(value), '.9f').rstrip('0').rstrip('.') or '0'


def csv(values):
    return ','.join(fmt(v) for v in values)


class Reader:
    def __init__(self, data):
        self.data, self.at = data, 0

    def take(self, count):
        if count < 0 or self.at + count > len(self.data):
            raise ValueError(f'Truncated component at byte {self.at}; need {count}')
        result = self.data[self.at:self.at + count]
        self.at += count
        return result

    def unpack(self, pattern):
        return struct.unpack(pattern, self.take(struct.calcsize(pattern)))

    def string(self):
        end = self.data.find(b'\0', self.at)
        if end < 0 or end - self.at > 4096:
            raise ValueError('Invalid terminated string')
        return self.take(end - self.at + 1)[:-1].decode('utf-8')

    def end(self):
        if self.at != len(self.data):
            raise ValueError(f'Unexpected trailing bytes: {len(self.data) - self.at}')


class Grid:
    """Fixed-stride grid with byte-for-byte header and unknown-channel retention."""
    def __init__(self, data, magic, versions, offset, pattern, dims_at=8):
        self.raw = bytearray(data)
        if len(data) < offset or data[:4] != magic:
            raise ValueError(f'Invalid {magic!r} header')
        self.version = struct.unpack_from('<I', data, 4)[0]
        if self.version not in versions:
            raise ValueError(f'Unsupported {magic!r} version {self.version}')
        self.width, self.height = struct.unpack_from('<II', data, dims_at)
        self.offset, self.pattern = offset, pattern
        self.stride = struct.calcsize(pattern)
        if not (0 < self.width <= 2048 and 0 < self.height <= 2048):
            raise ValueError('Invalid grid dimensions')
        if len(data) != offset + self.width * self.height * self.stride:
            raise ValueError(f'{magic!r} grid size does not match payload')

    def index(self, x, y):
        if not (isinstance(x, int) and isinstance(y, int)
                and 0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f'Grid coordinate out of bounds: {x}, {y}')
        return self.offset + (y * self.width + x) * self.stride

    def get(self, x, y):
        return struct.unpack_from(self.pattern, self.raw, self.index(x, y))

    def set(self, x, y, values):
        struct.pack_into(self.pattern, self.raw, self.index(x, y), *values)

    def encode(self):
        return bytes(self.raw)


class Masks:
    def __init__(self, data):
        self.raw = bytearray(data)
        if len(data) < 64 or data[:4] != b'MASK':
            raise ValueError('Invalid texture mask header')
        self.version, reserved, self.width, self.height = struct.unpack_from('<4I', data, 4)
        if (self.version != 102 or reserved or not 0 < self.width <= 2048
                or not 0 < self.height <= 2048 or self.width % 64 or self.height % 64
                or len(data) != 64 + self.width * self.height * 4):
            raise ValueError('Unsupported or malformed texture mask')

    def location(self, x, y, layer):
        if not (0 <= x < self.width and 0 <= y < self.height and 0 <= layer < 8):
            raise ValueError('Texture mask coordinate/layer out of bounds')
        tile = (y // 64) * (self.width // 64) + x // 64
        at = 64 + layer * self.width * self.height // 2 + tile * 2048 + y % 64 * 32 + x % 64 // 2
        return at, 4 if x % 2 == 0 else 0

    def get(self, x, y):
        return [(self.raw[at] >> shift) & 15
                for at, shift in (self.location(x, y, layer) for layer in range(8))]

    def set(self, x, y, values):
        if len(values) != 8 or any(not isinstance(v, int) or not 0 <= v <= 15 for v in values):
            raise ValueError('Eight nibble weights are required')
        for layer, value in enumerate(values):
            at, shift = self.location(x, y, layer)
            self.raw[at] = (self.raw[at] & ~(15 << shift)) | value << shift

    def encode(self):
        return bytes(self.raw)


class SyncTextures:
    def __init__(self, data):
        reader = Reader(data)
        magic, self.version, self.width, self.height = reader.unpack('<4sIII')
        if magic != b'RTXT' or self.version not in (100, 101):
            raise ValueError('Unsupported sync texture header')
        self.set_count = reader.unpack('<I')[0] if self.version == 101 else 1
        if not 1 <= self.set_count <= 8 or not 0 < self.width <= 512 or not 0 < self.height <= 512:
            raise ValueError('Invalid sync texture dimensions/sets')
        self.names = [reader.string() for _ in range(8 * self.set_count)]
        self.offset = reader.at
        self.pattern = '<II' if self.version == 101 else '<I'
        self.stride = struct.calcsize(self.pattern)
        if len(data) != self.offset + self.width * self.height * self.stride:
            raise ValueError('Sync texture payload mismatch')
        self.raw = bytearray(data)

    def set(self, x, y, slot):
        if not (0 <= x < self.width and 0 <= y < self.height and 0 <= slot < len(self.names)):
            raise ValueError('Sync texture coordinate/slot out of bounds')
        struct.pack_into('<I', self.raw, self.offset + (y * self.width + x) * self.stride, slot)

    def encode(self):
        return bytes(self.raw)


class Water:
    """v110 rectangle entries; nonempty body records need separate evidence."""
    def __init__(self, data):
        if len(data) < 32 or data[:4] != b'WATR':
            raise ValueError('Invalid water header')
        version, count, bodies = struct.unpack_from('<III', data, 4)
        if version != 110 or bodies or len(data) != 32 + count * 56:
            raise ValueError('Unsupported water bodies/version; preserve original component')
        self.header = data[:32]
        self.entries = []
        for i in range(count):
            entry = data[32 + i * 56:32 + (i + 1) * 56]
            self.entries.append((entry[:40], struct.unpack('<4f', entry[40:])))

    def encode(self):
        header = bytearray(self.header)
        struct.pack_into('<I', header, 8, len(self.entries))
        return bytes(header) + b''.join(name + struct.pack('<4f', *rect) for name, rect in self.entries)

    def describe(self):
        return [{'type': name.split(b'\0')[0].decode('utf-8'), 'rect': list(rect)} for name, rect in self.entries]


class Foliage:
    def __init__(self, data):
        if len(data) < 28 or data[:4] != b'DLFT' or struct.unpack_from('<I', data, 4)[0] != 103:
            raise ValueError('Unsupported foliage header')
        count = struct.unpack_from('<I', data, 24)[0]
        if len(data) != 28 + count * 9:
            raise ValueError('Foliage payload mismatch')
        self.header = data[:28]
        self.entries = [data[28 + i * 9:37 + i * 9] for i in range(count)]

    def positions(self):
        return [struct.unpack('<ffB', e) for e in self.entries]

    def encode(self):
        header = bytearray(self.header)
        struct.pack_into('<I', header, 24, len(self.entries))
        return bytes(header) + b''.join(self.entries)


class HardTiles:
    def __init__(self, data):
        reader = Reader(data)
        self.header = reader.take(24)
        if self.header[:8] != b'HRDTf\0\0\0':
            raise ValueError('Unsupported hard tile header')
        count = reader.unpack('<I')[0]
        if count > len(data) // 12:
            raise ValueError('Invalid hard tile group count')
        self.groups = []
        for _ in range(count):
            n = reader.unpack('<I')[0]
            if n > len(data) // 58:
                raise ValueError('Invalid hard tile count')
            tiles = [reader.take(58) for _ in range(n)]
            flags = reader.take(3)
            name_start = reader.at
            name = reader.string()
            name_raw = data[name_start:reader.at]
            model = reader.take(4)
            self.groups.append({'tiles': tiles, 'flags': flags, 'name': name, 'name_raw': name_raw, 'model': model})
        reader.end()

    def encode(self):
        return self.header + struct.pack('<I', len(self.groups)) + b''.join(
            struct.pack('<I', len(g['tiles'])) + b''.join(g['tiles']) + g['flags'] + g['name_raw'] + g['model']
            for g in self.groups)


class VertexColors:
    """Opaque color records with lossless bounds/field retention."""
    def __init__(self, data):
        reader = Reader(data)
        self.header = reader.take(32)
        magic, self.version, count = struct.unpack_from('<4sII', self.header)
        if magic != b'VTCL' or self.version not in (103, 104):
            raise ValueError('Unsupported vertex color header')
        fixed_size = 32 if self.version == 104 else 24
        if count > len(data) // (fixed_size + 4):
            raise ValueError('Invalid vertex color record count')
        self.entries = []
        for _ in range(count):
            fields = reader.take(fixed_size)
            length = reader.unpack('<I')[0]
            payload = reader.take(length)
            self.entries.append((fields, payload))
        reader.end()

    def encode(self):
        header = bytearray(self.header)
        struct.pack_into('<I', header, 8, len(self.entries))
        return bytes(header) + b''.join(fields + struct.pack('<I', len(payload)) + payload for fields, payload in self.entries)


class CellAttribute:
    """A length-prefixed bitset; catalog-like names do not prove bit semantics."""
    def __init__(self, data):
        if len(data) < 4:
            raise ValueError('Truncated cell attribute')
        self.bits = struct.unpack_from('<I', data)[0]
        if self.bits > 512 * 512 * 8 or len(data) != 4 + (self.bits + 7) // 8:
            raise ValueError('Unsupported cell attribute bitset')
        self.raw = data

    def encode(self):
        return self.raw

    def populated_bits(self):
        """Storage bit indices only; named rules and world ordering need evidence."""
        for index, value in enumerate(self.raw[4:]):
            while value:
                bit = (value & -value).bit_length() - 1
                identity = index * 8 + bit
                if identity < self.bits:
                    yield identity
                value &= value - 1


class LightingMap:
    """Observed uncompressed BGRA TGA; retain ID, orientation and footer bytes."""
    def __init__(self, data):
        if len(data) < 18:
            raise ValueError('Truncated lighting TGA')
        self.width, self.height = struct.unpack_from('<HH', data, 12)
        self.descriptor = data[17]
        if (data[1] != 0 or data[2] != 2 or data[16] != 32
                or self.descriptor & 0xc0 or self.descriptor & 15 != 8
                or not 0 < self.width <= 2048 or not 0 < self.height <= 2048):
            raise ValueError('Unsupported lighting TGA format')
        self.offset = 18 + data[0]
        self.end = self.offset + self.width * self.height * 4
        if self.end > len(data):
            raise ValueError('Truncated lighting TGA pixels')
        self.raw = bytearray(data)

    def get(self, x, y):
        """BGRA channels at an image coordinate measured from the lower left."""
        at = self.index(x, y)
        return tuple(self.raw[at:at + 4])

    def index(self, x, y):
        if not (isinstance(x, int) and isinstance(y, int)
                and 0 <= x < self.width and 0 <= y < self.height):
            raise ValueError('Lighting image coordinate out of bounds')
        column = self.width - 1 - x if self.descriptor & 0x10 else x
        row = self.height - 1 - y if self.descriptor & 0x20 else y
        return self.offset + (row * self.width + column) * 4

    def set(self, x, y, values):
        if len(values) != 4 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in values):
            raise ValueError('Lighting pixels require four byte values')
        at = self.index(x, y)
        self.raw[at:at + 4] = bytes(values)

    def encode(self):
        return bytes(self.raw)

    def describe(self):
        colors = Counter(struct.iter_unpack('<4B', self.raw[self.offset:self.end]))
        return {'dimensions': [self.width, self.height], 'channels': 'BGRA weights; observed Editor region 1 = R, region 2 = G; other region assignments unverified',
                'origin': 'top' if self.descriptor & 0x20 else 'bottom',
                'common_values': [{'bgra': color, 'pixels': count} for color, count in colors.most_common(8)]}


class MapInfo:
    """Known core fields only; the player/variant suffix remains byte-identical."""
    def __init__(self, data):
        self.raw = bytearray(data)
        reader = Reader(data)
        magic, self.version = reader.unpack('<4sI')
        if magic != b'IpaM' or not 31 <= self.version <= 39:
            raise ValueError('Unsupported MapInfo header')
        reader.take(8)  # integrity hash; retained until the hash algorithm is verified
        self.width, self.height = reader.unpack('<II')
        mode = reader.unpack('<I')[0]
        if mode == 2:
            reader.string()
        elif mode not in (0, 1):
            raise ValueError('Invalid MapInfo locale mode')
        preview = reader.unpack('<I')[0]
        if preview == 2:
            reader.string()
        elif preview not in (0, 1):
            raise ValueError('Invalid MapInfo preview mode')
        reader.string()  # minimap path, v28+
        if self.version >= 37:
            reader.string()  # hover image
        reader.take(8)  # export flags, resolution
        self.fog = reader.string()
        self.tileset = reader.string()
        self.bounds_at = reader.at
        self.bounds = reader.unpack('<4I')
        if (not 0 < self.width <= 256 or not 0 < self.height <= 256
                or not 0 <= self.bounds[0] < self.bounds[2] <= self.width
                or not 0 <= self.bounds[1] < self.bounds[3] <= self.height):
            raise ValueError('MapInfo core layout/bounds not recognized')

    def encode(self):
        return bytes(self.raw)


class TerrainMap:
    def __init__(self, path):
        self.path = component_path(path)
        self.xml = parse_xml(self.path / 't3Terrain.xml').getroot()
        if self.xml.tag != 'terrain' or int(self.xml.get('version', '0')) not in (113, 114, 115):
            raise ValueError('Unsupported terrain XML version')
        self.height = self.xml.find('heightMap')
        if self.height is None:
            raise ValueError('Terrain descriptor is missing heightMap')
        self.dim = tuple(int(v) for v in self.height.get('dim', '').split())
        if len(self.dim) != 2 or not all(1 < d <= 513 for d in self.dim):
            raise ValueError('Invalid terrain dimensions')
        self.offset = vector(self.height.get('offset', '0 0 0'), 3)
        self.scale = vector(self.height.get('scale', '1 1 1'), 3)
        self.vert = self.height.find('vertData')
        if self.vert is None:
            raise ValueError('Terrain descriptor is missing vertData')
        self.quantize = number(self.vert.get('quantizeScale'))
        self.bias = number(self.vert.get('quantizeBias'))
        if self.quantize <= 0 or any(v == 0 for v in self.scale):
            raise ValueError('Invalid terrain scale')

    def read(self, name):
        return (self.path / name).read_bytes()

    def height_grid(self):
        grid = Grid(self.read('t3HeightMap'), b'HMAP', {101}, 32, '<HHH')
        if (grid.width, grid.height) != self.dim:
            raise ValueError('XML and height grid dimensions differ')
        return grid

    def local_height(self, a, b):
        # Both quantized channels are retained. This is a diagnostic reconstruction;
        # engine cliff geometry may use additional transformations.
        return (a + b) * self.quantize - 2 * self.bias

    def summary(self, details=False):
        grid = self.height_grid()
        counts = {}
        for file in ('Objects', 'Regions'):
            target = self.path / file
            counts[file] = dict(Counter(e.tag for e in parse_xml(target).getroot())) if target.exists() else {}
        result = {'map': str(self.path), 'terrain_version': int(self.xml.get('version')), 'dimensions': self.dim,
                  'tileset': self.height.get('tileSet'), 'offset': self.offset, 'scale': self.scale,
                  'quantize_scale': self.quantize, 'quantize_bias': self.bias,
                  'objects': counts, 'ramps': len(self.height.find('rampList') or []),
                  'components': {n: (self.path / n).stat().st_size for n in TERRAIN_FILES if (self.path / n).exists()},
                  'dependencies': []}
        if (self.path / 'DocumentInfo').exists():
            result['dependencies'] = [e.text for e in parse_xml(self.path / 'DocumentInfo').getroot().findall('Dependencies/Value')]
        if details:
            result['textures'] = [dict(e.attrib) for e in self.height.findall('textureList/texture')]
            result['cliff_sets'] = [dict(e.attrib) for e in self.height.findall('cliffSetList/cliffSet')]
            result['ramps_detail'] = [dict(e.attrib) for e in self.height.findall('rampList/ramp')]
            result['water'] = Water(self.read('t3Water')).describe()
            roads = HardTiles(self.read('t3HardTile'))
            result['road_groups'] = [
                {'index': i, 'type': group['name'], 'point_count': len(group['tiles']),
                 'points': [list(struct.unpack_from('<3f', raw)) for raw in group['tiles']],
                 'raw_profile_values': [list(struct.unpack_from('<2f', raw, 48)) for raw in group['tiles']]}
                for i, group in enumerate(roads.groups)]
            foliage = Foliage(self.read('t3FluffDoodad')).positions()
            result['foliage'] = {'instances': len(foliage), 'observed_flags': dict(Counter(p[2] for p in foliage)),
                                 'position_examples': foliage[:8]}
            if (self.path / 'LightingMap.tga').exists():
                result['lighting_raster'] = LightingMap(self.read('LightingMap.tga')).describe()
            config=self.path/'Base.SC2Data/GameData/WaterData.xml'
            if config.exists():
                result['local_water_configurations']=[{'id':e.get('id'),'parent':e.get('parent'),
                    'explicit_states':[{'index':s.get('index'),'values':{v.tag:v.get('value') for v in s}} for s in e.findall('State')]}
                    for e in parse_xml(config).getroot().findall('CWater')]
            result['height_range_reconstructed'] = [min(self.local_height(*grid.get(x, y)[:2]) for y in range(grid.height) for x in range(grid.width)),
                                                     max(self.local_height(*grid.get(x, y)[:2]) for y in range(grid.height) for x in range(grid.width))]
        return result


def xml_bytes(root):
    return ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8').encode('ascii', 'xmlcharrefreplace')


def terrain_difference(before, after):
    """Semantic probes for controlled experiments, without interpreting pathing bits."""
    first, second = TerrainMap(before), TerrainMap(after)
    result = {'terrain_versions': [int(first.xml.get('version')), int(second.xml.get('version'))],
              'dimensions': [first.dim, second.dim],
              'quantization': [dict(first.vert.attrib), dict(second.vert.attrib)], 'grids': [], 'xml_lists': []}
    for name, magic, versions, offset, pattern, dims_at in [
        ('t3HeightMap', b'HMAP', {101}, 32, '<HHH', 8),
        ('t3SyncHeightMap', b'SMAP', {102}, 64, '<hH', 8),
        ('t3SyncCliffLevel', b'CLIF', {100}, 32, '<H', 8),
        ('t3CellFlags', b'LFCT', {101, 102}, 32, '<B', 24),
    ]:
        try:
            a = Grid(first.read(name), magic, versions, offset, pattern, dims_at)
            b = Grid(second.read(name), magic, versions, offset, pattern, dims_at)
            if (a.width, a.height) != (b.width, b.height):
                result['grids'].append({'component': name, 'dimensions_changed': True})
                continue
            count, ranges, examples, channel_counts = 0, [a.width, a.height, -1, -1], [], Counter()
            deltas = [Counter() for _ in a.get(0, 0)]
            for y in range(a.height):
                for x in range(a.width):
                    old, new = a.get(x, y), b.get(x, y)
                    if old == new:
                        continue
                    count += 1
                    ranges = [min(ranges[0], x), min(ranges[1], y), max(ranges[2], x), max(ranges[3], y)]
                    if len(examples) < 12:
                        examples.append({'xy': [x, y], 'before': old, 'after': new})
                    for i, (v, w) in enumerate(zip(old, new)):
                        if v != w:
                            channel_counts[i] += 1
                            deltas[i][w - v] += 1
            result['grids'].append({'component': name, 'changed_cells': count,
                                    'inclusive_bounds': ranges if count else None,
                                    'changed_channels': dict(channel_counts),
                                    'common_raw_deltas': [d.most_common(8) for d in deltas], 'examples': examples})
        except (OSError, ValueError) as exc:
            result['grids'].append({'component': name, 'error': str(exc)})
    for tag in ('cliffSetList', 'rampList', 'cliffDoodadList', 'textureList', 'textureSetList', 'blockTextureSetList', 'cliffCellList'):
        a, b = first.height.find(tag), second.height.find(tag)
        old = {e.get('i', str(i)): dict(e.attrib) for i, e in enumerate(a)} if a is not None else {}
        new = {e.get('i', str(i)): dict(e.attrib) for i, e in enumerate(b)} if b is not None else {}
        changes = [{'key': key, 'before': old.get(key), 'after': new.get(key)} for key in sorted(set(old) | set(new)) if old.get(key) != new.get(key)]
        if changes:
            result['xml_lists'].append({'tag': tag, 'changes': len(changes), 'examples': changes[:20]})
    result['migration_confounded'] = result['terrain_versions'][0] != result['terrain_versions'][1]
    result['cell_attributes'] = []
    names = {p.name for terrain in (first, second) for p in terrain.path.glob('CellAttribute_*')}
    for name in sorted(names):
        report = {'component': name}
        try:
            layers = [CellAttribute(terrain.read(name)) if (terrain.path / name).exists() else None for terrain in (first, second)]
            report['bit_counts'] = [layer.bits if layer is not None else None for layer in layers]
            old, new = [set(layer.populated_bits()) if layer is not None else set() for layer in layers]
            report['presence'] = [layer is not None for layer in layers]
            report['changed_storage_bits'] = len(old ^ new)
            report['added_storage_bit_examples'] = sorted(new - old)[:32]
            report['removed_storage_bit_examples'] = sorted(old - new)[:32]
            report['semantics'] = 'Storage indices only; an absent layer is reported separately and is not assumed semantically empty'
        except (OSError, ValueError) as exc:
            report['error'] = str(exc)
        result['cell_attributes'].append(report)
    result['lighting_raster'] = None
    if any((terrain.path / 'LightingMap.tga').exists() for terrain in (first, second)):
        try:
            maps = [LightingMap(terrain.read('LightingMap.tga')) if (terrain.path / 'LightingMap.tga').exists() else None for terrain in (first, second)]
            report = {'before': maps[0].describe() if maps[0] else None, 'after': maps[1].describe() if maps[1] else None}
            if all(maps) and (maps[0].width, maps[0].height) == (maps[1].width, maps[1].height):
                count, examples, box = 0, [], [maps[0].width, maps[0].height, -1, -1]
                for y in range(maps[0].height):
                    for x in range(maps[0].width):
                        a, b = [m.get(x, y) for m in maps]
                        if a == b: continue
                        count += 1
                        box = [min(box[0], x), min(box[1], y), max(box[2], x), max(box[3], y)]
                        if len(examples) < 12: examples.append({'image_xy': [x, y], 'before_bgra': a, 'after_bgra': b})
                report.update(changed_pixels=count, inclusive_image_bounds=box if count else None, examples=examples)
            result['lighting_raster'] = report
        except (OSError, ValueError) as exc:
            result['lighting_raster'] = {'error': str(exc)}
    return result


@lru_cache(maxsize=8)
def object_contract(kind):
    """Read the installed Objects schema instead of maintaining another enum list."""
    tag={'unit':'ObjectUnit','doodad':'ObjectDoodad','point':'ObjectPoint','camera':'ObjectCamera','group':'ObjectGroup'}.get(kind,kind)
    root=ET.parse(Path(__file__).parent/'schemas/sc2-xsd/Objects.xsd').getroot()
    ns={'x':'http://www.w3.org/2001/XMLSchema'}
    types={e.get('name'):e for e in root.findall('x:complexType',ns)}
    simple={e.get('name'):e for e in root.findall('x:simpleType',ns)}
    if tag not in types:
        raise ValueError('Unknown placed object kind')
    def fields(type_name):
        node=types[type_name]
        extension=node.find('x:complexContent/x:extension',ns)
        attrs,children=fields(extension.get('base')) if extension is not None else ({},{})
        attrs.update({e.get('name'):dict(e.attrib) for e in node.findall('.//x:attribute',ns)})
        children.update({e.get('name'):e.get('type') for e in node.findall('.//x:element',ns)})
        return attrs,children
    attrs,children=fields(tag)
    child_fields={name:{e.get('name'):dict(e.attrib) for e in types[type_name].findall('.//x:attribute',ns)} for name,type_name in children.items()}
    enum_names={a.get('type') for a in attrs.values()}|{a.get('type') for f in child_fields.values() for a in f.values()}
    enums={name:[e.get('value') for e in simple[name].findall('.//x:enumeration',ns)] for name in enum_names if name in simple}
    return {'kind':kind,'attributes':attrs,'children':child_fields,'enums':{k:v for k,v in enums.items() if v}}
