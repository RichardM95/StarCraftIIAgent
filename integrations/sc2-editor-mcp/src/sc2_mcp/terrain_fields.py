"""Experimental full-field terrain planners; never write or claim engine parity.

The caller must resolve palette names against its effective TerrainTex catalog.
This codec validates stored slots and names, not external dependency availability.
"""
from __future__ import annotations

import re
from pathlib import Path
from xml.parsers import expat

import numpy as np

from .errors import SC2Error
from .terrain import Terrain


def _array(value, shape, label, integer=False):
    try:
        result = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise SC2Error("invalid_terrain_field", "地形字段不是规则数值数组", field=label) from exc
    if result.shape != shape or result.dtype.kind not in ("iu" if integer else "iuf"):
        raise SC2Error("invalid_terrain_field", "地形字段形状或数值类型不符", field=label,
                       expected_shape=list(shape), actual_shape=list(result.shape))
    if not np.all(np.isfinite(result)):
        raise SC2Error("invalid_terrain_field", "地形字段包含非有限值", field=label)
    return result


def _palette_context(t):
    """Get exact name-attribute byte spans from parsed element context."""
    raw = t.xml
    try:
        raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise SC2Error("unsupported_terrain_xml_encoding", "纹理表仅支持 UTF-8 XML") from exc
    parser = expat.ParserCreate()
    stack, entries, list_count = [], {}, 0

    def start(tag, attributes):
        nonlocal list_count
        stack.append(tag)
        if stack == ["terrain", "heightMap", "textureList"]:
            list_count += 1
        if stack != ["terrain", "heightMap", "textureList", "texture"]:
            return
        try:
            index = int(attributes["i"])
            name = attributes["name"]
        except (KeyError, ValueError) as exc:
            raise SC2Error("invalid_texture_table", "纹理槽位缺少合法 i/name") from exc
        if index < 0 or index in entries:
            raise SC2Error("invalid_texture_table", "纹理槽位重复或无效", slot=index)
        begin = parser.CurrentByteIndex
        # A '>' inside quoted attributes must not terminate the opening tag.
        tag_match = re.match(rb"<texture\b(?:[^\"'>]|\"[^\"]*\"|'[^']*')*>", raw[begin:])
        if tag_match is None:
            raise SC2Error("invalid_texture_table", "无法精确定位纹理元素")
        attrs = list(re.finditer(rb"([^\s=<>/]+)\s*=\s*([\"'])(.*?)\2", tag_match[0], re.S))
        matches = [attr for attr in attrs if attr[1] == b"name"]
        if len(matches) != 1:
            raise SC2Error("invalid_texture_table", "无法精确定位纹理名称")
        attr = matches[0]
        entries[index] = (name, begin + attr.start(3), begin + attr.end(3), attr[2])

    def reject_doctype(*args):
        raise SC2Error("unsupported_terrain_xml", "地形字段修改不支持 DTD 或实体声明")

    def declaration(version, encoding, standalone):
        if encoding and encoding.lower().replace("-", "") != "utf8":
            raise SC2Error("unsupported_terrain_xml_encoding", "纹理表仅支持 UTF-8 XML")

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda tag: stack.pop()
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.XmlDeclHandler = declaration
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as exc:
        raise SC2Error("invalid_terrain_xml", "地形 XML 无法解析") from exc
    if list_count != 1 or any(i >= 8 and item[0] for i, item in entries.items()):
        raise SC2Error("unsupported_texture_layout", "仅支持唯一纹理表与单套八槽纹理")
    for node in t.meta.findall("textureSetList/textureSet"):
        if node.get("i") != "0" and node.get("name"):
            raise SC2Error("unsupported_texture_layout", "XML 使用多个纹理集")
    for node in t.meta.findall("blockTextureSetList/blockTextureSet"):
        if node.get("tileSet") != "0":
            raise SC2Error("unsupported_texture_layout", "XML 包含非零纹理集块")
    return entries


def plan_terrain_fields(root: Path, heights=None, texture_weights=None,
                        texture_palette=None, ground_mask=None, building_mask=None) -> dict[str, bytes]:
    """Plan experimental v115 field changes without mutating source files.

    Heights use vertex (y,x) dimensions and preserve detailed-height residuals.
    Weights use (8,tile_height*8,tile_width*8), integer 0..15, pixel sum 15.
    Palette maps existing slots 0..7 to nonempty effective TerrainTex names.
    Masks use tile (y,x) dimensions and only whole-tile paint values 0/255.
    RTXT dominant selection remains an experimental arithmetic-mean estimate.
    """
    root = Path(root)
    t = Terrain(root)
    changed = {}
    if heights is not None:
        target = _array(heights, (t.height, t.width), "heights").astype(np.float64)
        # Check floating ranges before integer conversion to avoid integer overflow.
        with np.errstate(over="ignore", invalid="ignore"):
            delta = np.rint((target - t.heights) / t.scale)
            base = t.vertices[:, :, 0].astype(np.float64) + delta
            sync = np.rint((t.heights + delta * t.scale) * 256)
        if (not np.all(np.isfinite(base)) or not np.all(np.isfinite(sync)) or
                np.any(base < 0) or np.any(base > 65535) or
                np.any(sync < -32768) or np.any(sync > 32767)):
            raise SC2Error("height_out_of_range", "高度超出当前量化范围，拒绝重新量化整图")
        t.vertices[:, :, 0] = base.astype("<u2")
        t.sync[:, :, 0] = sync.astype("<i2")
        changed["t3HeightMap"] = t.raw["t3HeightMap"][:32] + t.vertices.tobytes()
        changed["t3SyncHeightMap"] = t.raw["t3SyncHeightMap"][:64] + t.sync.tobytes()

    if texture_weights is not None or texture_palette is not None:
        entries = _palette_context(t)
        old_weights = t.texture_weights()
        names, offset, sync = t.sync_textures()
        if any(entries.get(i, ("",))[0] != names[i] for i in range(8)):
            raise SC2Error("texture_table_mismatch", "XML 与 RTXT 纹理名称表不一致")
        palette = {} if texture_palette is None else texture_palette
        if not isinstance(palette, dict):
            raise SC2Error("invalid_texture_palette", "纹理表必须为槽位到名称的字典")
        replacements = []
        for index, name in palette.items():
            if type(index) is not int or index not in range(8) or index not in entries:
                raise SC2Error("texture_unavailable", "仅允许 XML 已声明的 0 至 7 号槽位", slot=str(index))
            if (not isinstance(name, str) or not name.strip() or
                    any(ord(char) < 32 or ord(char) in (0xFFFE, 0xFFFF) for char in name) or
                    any(0xD800 <= ord(char) <= 0xDFFF for char in name)):
                raise SC2Error("invalid_texture_palette", "纹理名称必须为无控制字符的非空名称", slot=index)
            old_name, begin, end, quote = entries[index]
            if name == old_name:
                continue
            escaped = name.replace("&", "&amp;").replace("<", "&lt;").replace(
                '"' if quote == b'"' else "'", "&quot;" if quote == b'"' else "&apos;")
            replacements.append((begin, end, escaped.encode("utf-8")))
            names[index] = name
        updated_xml = t.xml
        for begin, end, data in sorted(replacements, reverse=True):
            updated_xml = updated_xml[:begin] + data + updated_xml[end:]
        weights = old_weights if texture_weights is None else _array(
            texture_weights, old_weights.shape, "texture_weights", integer=True)
        if np.any(weights < 0) or np.any(weights > 15) or np.any(weights.sum(axis=0, dtype=np.int64) != 15):
            raise SC2Error("invalid_texture_weights", "八层纹理整数权重必须在 0..15 且每像素和为 15")
        for index in range(8):
            if not names[index] and np.any(weights[index]):
                raise SC2Error("texture_unavailable", "非零纹理权重引用空槽位", slot=index)
        weights = weights.astype("u1", copy=False)
        changed_tiles = np.any((weights != old_weights).reshape(
            8, t.tile_height, 8, t.tile_width, 8), axis=(0, 2, 4))
        if np.any(changed_tiles):
            dominant = weights.reshape(8, t.tile_height, 8, t.tile_width, 8).mean(axis=(2, 4)).argmax(axis=0)
            sync[changed_tiles] = dominant[changed_tiles]
            changed["t3TextureMasks"] = t.encode_texture_weights(weights)
        if replacements or np.any(changed_tiles):
            # Rebuild only the string table; its variable size moves the payload.
            table = b"".join(name.encode("utf-8") + b"\0" for name in names)
            changed["t3SyncTextureInfo"] = t.raw["t3SyncTextureInfo"][:20] + table + sync.tobytes()
        changed["t3Terrain.xml"] = updated_xml

    for value, component in ((ground_mask, "CellAttribute_Pnp"), (building_mask, "CellAttribute_Pnb")):
        if value is None:
            continue
        t.pathing_layer(component)  # Missing components are rejected, never fabricated.
        layer = _array(value, (t.tile_height, t.tile_width), component, integer=True)
        if np.any((layer != 0) & (layer != 255)):
            raise SC2Error("invalid_pathing_paint", "通行限制仅支持整格 0/255 绘制值", file=component)
        changed[component] = t.raw[component][:4] + layer.astype("u1").tobytes()
    return {name: data for name, data in changed.items() if data != t.raw[name]}
