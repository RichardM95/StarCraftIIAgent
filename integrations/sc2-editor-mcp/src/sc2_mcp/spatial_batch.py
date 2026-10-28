"""Bulk placement with explicit terrain grounding; all output is transactional."""
from __future__ import annotations

import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import SC2Error
from . import spatial
from .storage import safe_path
from .terrain import Terrain


def sample_height(heights, x: float, y: float) -> float:
    """Bilinear height sampling in native map coordinates (not screen pixels)."""
    h, w = heights.shape
    if not math.isfinite(x) or not math.isfinite(y) or not 0 <= x <= w-1 or not 0 <= y <= h-1:
        raise SC2Error('placement_outside_map', '物件位置超出地形范围', x=x, y=y)
    x0, y0 = int(x), int(y)
    x1, y1 = min(x0+1, w-1), min(y0+1, h-1)
    fx, fy = x-x0, y-y0
    return float((1-fy)*((1-fx)*heights[y0,x0]+fx*heights[y0,x1])+
                 fy*((1-fx)*heights[y1,x0]+fx*heights[y1,x1]))


def plan_place_objects(root: Path, objects: list[dict], ground_doodads: bool=True) -> dict[str, bytes]:
    """Place observed unit/point/doodad schemas; doodad Z is terrain + offset.

    A grounded doodad gets the observed HeightAbsolute flag. This removes
    ambiguity about relative coordinates but still requires engine visual QA.
    Component registration uses the native 'plob' identifier.
    """
    if not isinstance(objects, list) or not 1 <= len(objects) <= 10000:
        raise SC2Error('invalid_placements', '批量放置数量必须为1至10000')
    path = safe_path(root, 'Objects')
    data = path.read_bytes() if path.exists() else b'<?xml version="1.0" encoding="utf-8"?>\n<PlacedObjects Version="27">\n</PlacedObjects>\n'
    document = spatial._parse(data, 'Objects')
    if document.tag != 'PlacedObjects':
        raise SC2Error('unsupported_spatial_format', '未知空间组件根节点')
    spatial._check_ids(document.children)
    used = {int(n.attrs['Id']) for n in document.children}
    next_id = max(used, default=0)+1
    terrain = Terrain(root)
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    lines = []
    for specification in objects:
        kind = spatial._ALIASES.get(specification.get('kind'), specification.get('kind'))
        if kind not in {'ObjectUnit','ObjectPoint','ObjectDoodad'}:
            raise SC2Error('unsupported_spatial_kind','批量放置仅支持单位、点和装饰物')
        attrs = dict(specification.get('attributes', {}))
        if 'Id' not in attrs:
            attrs = {'Id':str(next_id), **attrs}
            next_id += 1
        spatial._attributes(kind, attrs, set())
        identity = spatial._id(attrs['Id'])
        if identity in used:
            raise SC2Error('ambiguous_spatial_id', '物件ID重复', object_id=identity)
        used.add(identity)
        next_id=max(next_id,identity+1)
        required={'Position', 'UnitType' if kind=='ObjectUnit' else 'Type'}
        if not required.issubset(attrs):
            raise SC2Error('missing_spatial_attributes', '物件缺少位置或类型')
        x,y,z = [float(value) for value in attrs['Position'].split(',')]
        height=sample_height(terrain.heights,x,y)
        grounded=kind=='ObjectDoodad' and ground_doodads
        if grounded:
            attrs['Position']=f'{x:.6f},{y:.6f},{height+z:.6f}'
        opening=b'    <'+kind.encode('ascii')
        for key,value in attrs.items():
            opening+=b' '+key.encode('ascii')+b'="'+spatial._value(value).encode('utf-8')+b'"'
        if grounded:
            opening+=b'>'+newline+b'        <Flag Index="HeightAbsolute" Value="1"/>'+newline+b'    </'+kind.encode('ascii')+b'>'
        else:
            opening+=b'/>'
        lines.append(opening)
    insertion=newline.join(lines)+newline
    if data[document.start:document.open_end].rstrip().endswith(b'/>'):
        result=data[:document.open_end-2]+b'>'+newline+insertion+b'</PlacedObjects>'+data[document.end:]
    else:
        result=data[:document.close_start]+insertion+data[document.close_start:]
    ET.fromstring(result)
    changes={'Objects':result}
    if not safe_path(root, 'Objects.version').exists():
        # Native v2 sidecars share the same opaque save metadata; only the
        # component FourCC differs (observed MapInfo/Objects pair, build 97579).
        metadata_path = safe_path(root, 'MapInfo.version')
        metadata = metadata_path.read_bytes() if metadata_path.is_file() else b''
        if len(metadata) != 44 or metadata[:8] != b'cdesipam' or struct.unpack_from('<I', metadata, 8)[0] != 2:
            raise SC2Error('unsupported_component_version', '新建物件组件需要已验证格式的 MapInfo.version 保存记录')
        changes['Objects.version'] = b'cdesbolp' + metadata[8:]
    component_path=safe_path(root,'ComponentList.SC2Components')
    component_bytes=component_path.read_bytes()
    component_tree=ET.fromstring(component_bytes)
    entries=[e for e in component_tree.findall('DataComponent') if e.get('Type')=='plob' or (e.text or '').strip()=='Objects']
    if entries:
        if len(entries)!=1 or entries[0].get('Type')!='plob' or (entries[0].text or '').strip()!='Objects':
            raise SC2Error('spatial_component_conflict', '已有空间组件登记不一致')
    else:
        end=b'</Components>'
        if component_bytes.count(end)!=1:
            raise SC2Error('ambiguous_component_context', '组件表关闭标签不唯一')
        nl=b'\r\n' if b'\r\n' in component_bytes else b'\n'
        changes['ComponentList.SC2Components']=component_bytes.replace(end,b'    <DataComponent Type="plob">Objects</DataComponent>'+nl+end,1)
    return changes
