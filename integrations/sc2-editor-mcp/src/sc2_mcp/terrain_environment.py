"""Narrow, byte-preserving terrain environment candidates; no filesystem writes.

Only presentation fields are supported. Resource IDs are syntactically checked;
their effective dependency availability and engine appearance need validation.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from .catalog import _case_path, _insert_child, _quoted, _replace_attribute, _spans
from .errors import SC2Error


_RESOURCES = {"Lighting", "Ambience", "FixedSkyboxActor", "FixedSkyboxModel", "NonFixedSkyboxModel"}
_BOOLS = {"FogEnabled", "HideLowestLevel"}
_NUMBERS = {"FogDensity", "FogFalloff", "FogStartingHeight"}
_FIELDS = _RESOURCES | _BOOLS | _NUMBERS | {"FogColor"}
_FILE = "Base.SC2Data/GameData/TerrainData.xml"


def _validate(settings):
    if not isinstance(settings, dict):
        raise SC2Error("invalid_environment_settings", "环境设置必须是字段到字符串的字典")
    for key, value in settings.items():
        if key not in _FIELDS:
            raise SC2Error("unsupported_environment_field", "环境工具不支持该字段", field=str(key), supported=sorted(_FIELDS))
        if not isinstance(value, str) or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
            raise SC2Error("invalid_environment_value", "环境值必须是合法 XML 属性字符串", field=key)
        if key in _BOOLS and value not in {"0", "1"}:
            raise SC2Error("invalid_environment_value", "环境布尔值只接受 0 或 1", field=key)
        if key in _NUMBERS:
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
                raise SC2Error("invalid_environment_value", "环境数值必须是十进制或科学计数格式", field=key)
            try:
                number = float(value)
            except ValueError as exc:
                raise SC2Error("invalid_environment_value", "环境数值必须为有限数字", field=key) from exc
            if not math.isfinite(number):
                raise SC2Error("invalid_environment_value", "环境数值必须为有限数字", field=key)
        if key == "FogColor":
            parts = value.split(",")
            if len(parts) != 4 or any(not re.fullmatch(r"[0-9]{1,3}", p.strip()) or int(p) > 255 for p in parts):
                raise SC2Error("invalid_environment_value", "雾颜色必须是四个 0..255 整数", field=key)


def _object(document, terrain_id):
    matches = [child for child in document.children if child.tag == "CTerrain" and child.attributes.get("id") == terrain_id]
    if len(matches) > 1:
        raise SC2Error("ambiguous_environment_terrain", "同 ID 的本地 CTerrain 定义不唯一", terrain_id=terrain_id)
    if matches and matches[0].attributes.get("removed") == "1":
        raise SC2Error("removed_environment_terrain", "不能隐式恢复已删除的地形定义", terrain_id=terrain_id)
    return matches[0] if matches else None


def plan_environment(root: Path, settings: dict[str, str]) -> dict[str, bytes]:
    """Plan overrides on the terrain type actually named by t3Terrain.xml.

    Existing fields and unrelated XML bytes retain their formatting. Missing
    TerrainData.xml or CTerrain can be added as explicit local visual overrides.
    Empty resource values explicitly clear inherited links. This planner does
    not change the terrain type, camera, gravity, topology, pathing or creep.
    """
    _validate(settings)
    root = Path(root).resolve()
    terrain_file = _case_path(root, "t3Terrain.xml")
    if terrain_file is None or not terrain_file.is_file():
        raise SC2Error("terrain_component_missing", "缺少 t3Terrain.xml")
    terrain_doc = _spans(terrain_file.read_bytes())
    height_maps = [n for n in terrain_doc.children if n.tag == "heightMap"]
    if terrain_doc.tag != "terrain" or len(height_maps) != 1:
        raise SC2Error("invalid_terrain_xml", "需要唯一 terrain/heightMap")
    terrain_id = height_maps[0].attributes.get("tileSet", "")
    if not terrain_id or any(ord(c) < 32 for c in terrain_id):
        raise SC2Error("invalid_terrain_xml", "heightMap 缺少有效 tileSet")
    target = _case_path(root, _FILE)
    if target is not None and not target.is_file():
        raise SC2Error("invalid_environment_component", "TerrainData.xml 不是文件")
    original = target.read_bytes() if target else None
    raw = original if original is not None else b'<?xml version="1.0" encoding="utf-8"?>\n<Catalog>\n</Catalog>\n'
    document = _spans(raw)
    if document.tag != "Catalog":
        raise SC2Error("invalid_environment_component", "TerrainData.xml 需要 Catalog 根节点")
    node = _object(document, terrain_id)
    if node is not None:
        for field in _FIELDS:
            matches = [child for child in node.children if child.tag == field]
            if len(matches) > 1:
                raise SC2Error("ambiguous_environment_field", "环境字段出现多重声明", field=field)
    if not settings:
        return {}
    ascii_only = bool(re.match(br"(?:\xef\xbb\xbf)?\s*<\?xml[^>]*encoding\s*=\s*['\"](?:us-ascii|ascii)['\"]", raw, re.I))
    if node is None:
        raw = _insert_child(raw, document, b'<CTerrain id="' + _quoted(terrain_id, ascii_only=ascii_only) + b'"/>')
    for field, value in settings.items():
        document = _spans(raw)
        node = _object(document, terrain_id)
        matches = [child for child in node.children if child.tag == field]
        if matches:
            child = matches[0]
            if "index" in child.attributes or child.attributes.get("removed") == "1" or child.children:
                raise SC2Error("unsupported_environment_field_shape", "环境字段不是可覆盖的简单标量", field=field)
            if child.attributes.get("value") == value:
                continue
            raw = _replace_attribute(raw, child, "value", value, ascii_only)
        else:
            raw = _insert_child(raw, node, b"<" + field.encode("ascii") + b' value="' + _quoted(value, ascii_only=ascii_only) + b'"/>')
    _spans(raw)
    relative = target.relative_to(root).as_posix() if target else _FILE
    return {} if raw == original else {relative: raw}
