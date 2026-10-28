"""Diagnostic SVG preview in SC2 world XY; no renderer-equivalence claim."""
from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET

from sc2_terrain import CellAttribute, Grid, TerrainMap, Water, fmt, vector

LAYERS = {'height', 'cliffs', 'water', 'unit', 'doodad', 'point', 'camera', 'regions', 'grid', 'pathing'}


def render(path, layers=None, step=2):
    terrain = TerrainMap(path)
    layers = set(layers or ('height', 'water', 'point', 'regions', 'grid'))
    if layers - LAYERS:
        raise ValueError('Unknown preview layers: ' + ','.join(sorted(layers - LAYERS)))
    if not isinstance(step, int) or not 1 <= step <= 32:
        raise ValueError('Preview step must be 1..32')
    ox, oy = terrain.offset[:2]
    sx, sy = terrain.scale[:2]
    width, height = (terrain.dim[0] - 1) * sx, (terrain.dim[1] - 1) * sy
    if sx <= 0 or sy <= 0:
        raise ValueError('Preview requires positive XY scale')
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height + 12)}" width="1000" role="img">',
              '<title>SC2 terrain diagnostic preview</title>',
              '<style>text{font:1.5px sans-serif} .marker{stroke:#fff;stroke-width:.12} .region{stroke:#f96;stroke-width:.25;fill:#f963;}</style>',
              f'<rect width="{fmt(width)}" height="{fmt(height + 12)}" fill="#111827"/>',
              f'<g transform="translate({fmt(-ox)},{fmt(height + oy)}) scale(1,-1)">']
    if 'height' in layers:
        grid = terrain.height_grid()
        heights = [terrain.local_height(*grid.get(x, y)[:2]) for y in range(0, grid.height - 1, step) for x in range(0, grid.width - 1, step)]
        low, high = min(heights), max(heights)
        for y in range(0, grid.height - 1, step):
            for x in range(0, grid.width - 1, step):
                z = terrain.local_height(*grid.get(x, y)[:2])
                shade = round(40 + 175 * (z - low) / (high - low or 1))
                result.append(f'<rect x="{fmt(ox + x * sx)}" y="{fmt(oy + y * sy)}" width="{fmt(min(step, grid.width - 1 - x) * sx)}" height="{fmt(min(step, grid.height - 1 - y) * sy)}" fill="rgb({shade},{shade},{shade})"/>')
    if 'cliffs' in layers:
        grid = Grid(terrain.read('t3SyncCliffLevel'), b'CLIF', {100}, 32, '<H')
        for y in range(0, grid.height, step):
            for x in range(0, grid.width, step):
                level = grid.get(x, y)[0]
                for xx, yy, x1, y1, x2, y2 in [(x + step, y, x + step, y, x + step, y + step), (x, y + step, x, y + step, x + step, y + step)]:
                    if xx < grid.width and yy < grid.height and grid.get(xx, yy)[0] != level:
                        result.append(f'<path d="M{fmt(ox+x1*sx)},{fmt(oy+y1*sy)} L{fmt(ox+x2*sx)},{fmt(oy+y2*sy)}" stroke="#ffda44" stroke-width=".25"/>')
    if 'water' in layers:
        for entry in Water(terrain.read('t3Water')).describe():
            a, b, c, d = entry['rect']
            result.append(f'<rect x="{fmt(a)}" y="{fmt(b)}" width="{fmt(c-a)}" height="{fmt(d-b)}" fill="#28afff66"><title>{html.escape(entry["type"])}</title></rect>')
    if 'pathing' in layers:
        pnp = terrain.path / 'CellAttribute_Pnp'
        if pnp.exists():
            data = CellAttribute(pnp.read_bytes())
            cw, ch = terrain.dim[0] - 1, terrain.dim[1] - 1
            if data.bits != cw * ch * 8:
                raise ValueError('Pnp dimensions do not match terrain')
            for index, value in enumerate(data.raw[4:]):
                if value:
                    x, y = index % cw, index // cw
                    result.append(f'<rect x="{fmt(ox+x*sx)}" y="{fmt(oy+y*sy)}" width="{fmt(sx)}" height="{fmt(sy)}" fill="#ff5533" fill-opacity="{fmt(.2+.6*value.bit_count()/8)}"><title>Pnp no-ground-path paint byte {value}; partial sample positions and runtime traversal unverified</title></rect>')
        # Raw paint colors intentionally carry no walkability labels until the
        # Editor's paint-value lookup table is measured.
        file = terrain.path / 'PaintedPathingLayer'
        if file.exists():
            import struct
            data = file.read_bytes()
            if len(data) != 524304:
                raise ValueError('Unsupported painted pathing payload')
            left, bottom, right, top = struct.unpack_from('<4i', data)
            if right-left != 512 or top-bottom != 512:
                raise ValueError('Unsupported painted pathing bounds')
            for y in range(0, min(512, terrain.dim[1] * 2), step):
                for x in range(0, min(512, terrain.dim[0] * 2), step):
                    value = data[16 + (y * 512 + x) * 2]
                    if value != 128:
                        result.append(f'<rect x="{fmt((x+left)/2)}" y="{fmt((y+bottom)/2)}" width="{fmt(step/2)}" height="{fmt(step/2)}" fill="#{value:02x}40ff80"><title>raw pathing paint {value}; semantics unverified</title></rect>')
    if 'regions' in layers and (terrain.path / 'Regions').exists():
        root = ET.fromstring(terrain.read('Regions'))
        for region in root:
            for shape in region.findall('shape'):
                if shape.get('type') == 'circle':
                    x, y = vector(shape.find('center').get('value'), 2)
                    r = float(shape.find('radius').get('value'))
                    result.append(f'<circle class="region" cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r)}"/>')
                elif shape.get('type') == 'rect':
                    a,b,c,d = vector(shape.find('quad').get('value'), 4)
                    result.append(f'<rect class="region" x="{fmt(a)}" y="{fmt(b)}" width="{fmt(c-a)}" height="{fmt(d-b)}"/>')
                elif shape.get('type') == 'diamond':
                    x,y = vector(shape.find('center').get('value'), 2)
                    w,h = float(shape.find('width').get('value'))/2, float(shape.find('height').get('value'))/2
                    result.append(f'<polygon class="region" points="{fmt(x-w)},{fmt(y)} {fmt(x)},{fmt(y+h)} {fmt(x+w)},{fmt(y)} {fmt(x)},{fmt(y-h)}"/>')
    if (terrain.path / 'Objects').exists():
        colors = {'unit':'#f55','doodad':'#4b7','point':'#ff5','camera':'#9af'}
        for e in ET.fromstring(terrain.read('Objects')):
            kind = e.tag.removeprefix('Object').lower()
            if kind not in layers or kind not in colors or not e.get('Position'):
                continue
            x,y,_ = vector(e.get('Position'),3)
            label = ' '.join([e.tag, e.get('Id',''), e.get('Name', e.get('UnitType',e.get('Type','')))])
            result.append(f'<circle class="marker" cx="{fmt(x)}" cy="{fmt(y)}" r=".65" fill="{colors[kind]}"><title>{html.escape(label)}</title></circle>')
            if kind in ('unit', 'doodad'):
                rotation = float(e.get('Rotation', 0))
                tipx, tipy = x + 1.8 * math.cos(rotation), y + 1.8 * math.sin(rotation)
                result.append(f'<path d="M{fmt(x)},{fmt(y)} L{fmt(tipx)},{fmt(tipy)}" stroke="{colors[kind]}" stroke-width=".3"><title>Rotation {fmt(rotation)} radians; placement +X axis</title></path>')
    if 'grid' in layers:
        for x in range(math.ceil(ox/8)*8, math.ceil((ox+width)/8)*8+1,8):
            result.append(f'<path d="M{x},{fmt(oy)} v{fmt(height)}" stroke="#ffffff22" stroke-width=".15"/>')
        for y in range(math.ceil(oy/8)*8, math.ceil((oy+height)/8)*8+1,8):
            result.append(f'<path d="M{fmt(ox)},{y} h{fmt(width)}" stroke="#ffffff22" stroke-width=".15"/>')
    result.extend(['</g>',f'<text x="1" y="{fmt(height+3)}" fill="white">{html.escape(terrain.path.name)} | north = +Y | world extent {fmt(ox)},{fmt(oy)} to {fmt(ox+width)},{fmt(oy+height)}</text>',
                   f'<text x="1" y="{fmt(height+6)}" fill="white">Diagnostic: reconstructed height / raw overlays. Editor appearance and runtime pathing unverified.</text>',
                   '</svg>'])
    return '\n'.join(result)
