"""Read-only diagnostics for the binary/XML shell of an SC2 component map.

The shell contains opaque binary files.  This module deliberately reports
observed structure and repair boundaries; it never rebuilds or rewrites a
MapInfo or version sidecar.
"""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import SC2Error
from .storage import digest, safe_path

_CORE_FILES = ("DocumentInfo", "DocumentHeader", "ComponentList.SC2Components")
_KNOWN_FOURCC = {
    # The native sidecar FourCC is cdes + the ComponentList Type reversed.
    "DocumentInfo": b"cdesofni",
    "MapInfo": b"cdesipam",
    "Objects": b"cdesbolp",
    "Regions": b"cdesiger",
    "Triggers": b"cdesgirt",
    "Attributes": b"cdesrtta",
    "GameData": b"cdesadag",
    "GameText": b"cdestxet",
    "t3Terrain.xml": b"cdesrret",
}
_TYPE_TO_NAME = {
    "info": "DocumentInfo",
    "mapi": "MapInfo",
    "plob": "Objects",
    "regi": "Regions",
    "trig": "Triggers",
    "terr": "t3Terrain.xml",
    "attr": "Attributes",
    "gada": "GameData",
    "text": "GameText",
}
_LOCAL_COMPONENTS = {
    "DocumentInfo": "DocumentInfo",
    "MapInfo": "MapInfo",
    "Objects": "Objects",
    "Regions": "Regions",
    "Triggers": "Triggers",
    "Attributes": "Attributes",
    "t3Terrain.xml": "t3Terrain.xml",
}
_SIDECAR_BASE = {
    "DocumentInfo": "DocumentInfo",
    "MapInfo": "MapInfo",
    "Objects": "Objects",
    "Regions": "Regions",
    "Triggers": "Triggers",
    "Attributes": "Attributes",
    "GameData": "GameData",
    "GameText": "GameText",
    "t3Terrain.xml": "t3Terrain",
}


def _path_exists(root: Path, relative: str) -> bool:
    path = safe_path(root, relative)
    return path.is_file() or path.is_dir()


def _localized_path(locale: str | None) -> str | None:
    if not locale or any(ch in locale for ch in "/\\\0"):
        return None
    return f"{locale}.SC2Data/LocalizedData"


def _declared_path(name: str, locale: str | None) -> str | None:
    if name == "GameData":
        return "Base.SC2Data/GameData"
    if name == "GameText":
        return _localized_path(locale)
    return _LOCAL_COMPONENTS.get(name)


def _sidecar_name(name: str) -> str | None:
    base = _SIDECAR_BASE.get(name)
    return f"{base}.version" if base else None


def _inspect_sidecar(root: Path, path: str, expected_name: str) -> dict:
    sidecar = safe_path(root, path)
    item = {
        "path": path,
        "component": expected_name,
        "present": sidecar.is_file(),
        "length": sidecar.stat().st_size if sidecar.is_file() else None,
        "fourcc": None,
        "format": "absent",
        "version": None,
        "sha256": None,
        "format_version": None,
        "build_fields": None,
    }
    if not sidecar.is_file():
        return item
    data = sidecar.read_bytes()
    item["length"] = len(data)
    item["sha256"] = digest(data)
    if len(data) >= 8:
        item["fourcc"] = data[:8].decode("ascii", errors="replace")
    if len(data) == 44 and data[:8] == _KNOWN_FOURCC.get(expected_name):
        item["format"] = "sc2_component_version_v2"
        item["version"] = struct.unpack_from("<I", data, 8)[0]
        item["format_version"] = item["version"]
        item["build_fields"] = [struct.unpack_from("<I", data, 12)[0], struct.unpack_from("<I", data, 28)[0]]
    else:
        item["format"] = "unknown"
    return item


def _append_issue(items: list[dict], code: str, message: str, **details) -> None:
    item = {"code": code, "message": message}
    item.update(details)
    items.append(item)


def _inspect_shell_metadata(root: Path, name: str) -> dict:
    """Inspect metadata without decoding opaque DocumentHeader bytes."""
    path = safe_path(root, name)
    result = {"path": name, "present": path.is_file(), "format": "absent",
              "root": None, "sha256": None}
    if not path.is_file():
        return result
    raw = path.read_bytes()
    result["sha256"] = digest(raw)
    stripped = raw.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not stripped.startswith(b"<"):
        result["format"] = "opaque_binary"
        return result
    try:
        element = ET.fromstring(raw)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        result["format"] = "invalid_xml"
        result["error"] = str(exc)
        return result
    result["format"] = "xml"
    result["root"] = element.tag
    return result


def inspect_map_shell(root: Path) -> dict:
    """Inspect a component-map shell without changing any file."""
    root = Path(root)
    if not root.is_dir():
        raise SC2Error("project_missing", "地图组件目录不存在", path=str(root))

    errors: list[dict] = []
    warnings: list[dict] = []
    safe_repairs: list[dict] = []
    native_repairs: list[dict] = []
    unsupported: list[dict] = []
    present_core = [name for name in _CORE_FILES if safe_path(root, name).is_file()]
    missing_core = [name for name in _CORE_FILES if name not in present_core]
    for name in missing_core:
        _append_issue(errors, "missing_core_shell", "缺少必要地图外壳文件", path=name)

    metadata = {
        "DocumentInfo": _inspect_shell_metadata(root, "DocumentInfo"),
        "DocumentHeader": _inspect_shell_metadata(root, "DocumentHeader"),
    }
    document_info = metadata["DocumentInfo"]
    if document_info["format"] == "invalid_xml":
        _append_issue(errors, "invalid_document_info", "DocumentInfo 不是可解析 XML", path="DocumentInfo",
                      error=document_info.get("error"))
    elif document_info["format"] == "xml" and document_info.get("root") != "DocInfo":
        _append_issue(errors, "invalid_document_info_root", "DocumentInfo 根元素不是 DocInfo",
                      path="DocumentInfo", root=document_info.get("root"))
    if metadata["DocumentHeader"]["format"] == "invalid_xml":
        _append_issue(warnings, "invalid_document_header_xml", "DocumentHeader 以 XML 形式存在但无法解析；二进制头部不会被猜测重建",
                      path="DocumentHeader", error=metadata["DocumentHeader"].get("error"))

    component_path = safe_path(root, "ComponentList.SC2Components")
    declarations: list[dict] = []
    if component_path.is_file():
        try:
            document = ET.fromstring(component_path.read_bytes())
        except (ET.ParseError, UnicodeDecodeError) as exc:
            _append_issue(errors, "invalid_component_list", "ComponentList.SC2Components 无法解析", error=str(exc))
            document = None
        if document is not None and document.tag != "Components":
            _append_issue(errors, "invalid_component_list_root", "组件表根元素不是 Components", root=document.tag)
            document = None
        if document is not None:
            for entry in document.findall("DataComponent"):
                component_type = entry.get("Type") or ""
                raw_name = (entry.text or "").strip()
                name = _TYPE_TO_NAME.get(component_type, raw_name)
                path = _declared_path(name, entry.get("Locale"))
                declarations.append({
                    "type": component_type,
                    "name": name,
                    "locale": entry.get("Locale"),
                    "declared_value": raw_name,
                    "path": path,
                    "known_type": component_type in _TYPE_TO_NAME,
                    "present": _path_exists(root, path) if path else None,
                })
                if path and not declarations[-1]["present"]:
                    if name in {"MapInfo", "Objects", "Regions", "Triggers", "Attributes", "t3Terrain.xml"}:
                        _append_issue(errors, "declared_component_missing", "组件表声明的组件文件不存在", component=name, path=path)
                    else:
                        _append_issue(warnings, "declared_dependency_component_missing", "组件表声明的依赖型组件未在地图根目录找到", component=name, path=path)
                if not path:
                    _append_issue(warnings, "unknown_component_mapping", "无法把组件声明映射到本地路径", type=component_type, value=raw_name)
    declared_names = {item["name"] for item in declarations}

    mapinfo = {
        "path": "MapInfo", "present": False, "length": None, "sha256": None,
        "signature": None, "format": "absent", "payload_version": None,
        "dimensions": None,
    }
    mapinfo_path = safe_path(root, "MapInfo")
    if mapinfo_path.is_file():
        data = mapinfo_path.read_bytes()
        mapinfo.update({
            "present": True,
            "length": len(data),
            "sha256": digest(data),
            "signature": data[:4].decode("ascii", errors="replace"),
        })
        if len(data) == 0:
            mapinfo["format"] = "empty"
            _append_issue(errors, "empty_mapinfo", "MapInfo 是空文件")
        elif len(data) < 8 or data[:4] != b"IpaM":
            mapinfo["format"] = "invalid_signature"
            _append_issue(errors, "invalid_mapinfo", "MapInfo 不是已识别的原生二进制结构", length=len(data), signature=mapinfo["signature"])
        else:
            mapinfo["format"] = "native_mapinfo_binary"
            mapinfo["payload_version"] = struct.unpack_from("<I", data, 4)[0]
            if len(data) >= 24:
                mapinfo["dimensions"] = [struct.unpack_from("<I", data, 16)[0], struct.unpack_from("<I", data, 20)[0]]
    elif "MapInfo" in declared_names or (root / "t3Terrain.xml").exists():
        _append_issue(errors, "missing_mapinfo", "地图声明或地形组件需要 MapInfo，但文件不存在")
    else:
        _append_issue(warnings, "mapinfo_not_proven", "未找到 MapInfo，当前目录可能是简化模组或不完整地图")

    version_sidecars: list[dict] = []
    inspected_sidecars: set[str] = set()
    for declaration in declarations:
        name = declaration["name"]
        if name not in _SIDECAR_BASE or name == "MapInfo" or not declaration["present"]:
            continue
        sidecar_name = _sidecar_name(name)
        if not sidecar_name:
            continue
        if sidecar_name in inspected_sidecars:
            continue
        inspected_sidecars.add(sidecar_name)
        sidecar = _inspect_sidecar(root, sidecar_name, name)
        version_sidecars.append(sidecar)
        if not sidecar["present"]:
            if name in {"Objects", "Regions"}:
                _append_issue(errors, "missing_component_version", "已声明空间组件缺少版本旁车文件", component=name, path=sidecar_name)
                if mapinfo_path.is_file():
                    metadata = _inspect_sidecar(root, "MapInfo.version", "MapInfo")
                    native_repairs.append({
                        "path": sidecar_name,
                        "reason": "必须从同一地图、同一原生保存记录恢复；不能仅改 FourCC 伪造旁车",
                        "mapinfo_version_observed": metadata["format"] == "sc2_component_version_v2",
                    })
            else:
                # MapInfo and the approved native shell samples demonstrate
                # that not every optional component has a sidecar in every
                # historical map.  Only Objects/Regions are fatal here;
                # their missing sidecars are the observed editor-warning
                # failure mode.  An existing sidecar is still validated.
                pass
        elif sidecar["format"] == "unknown":
            _append_issue(warnings, "unknown_component_version", "版本旁车长度或 FourCC 未被核验", component=name, path=sidecar_name, length=sidecar["length"], fourcc=sidecar["fourcc"])
            unsupported.append({"path": sidecar_name, "reason": "未知版本旁车格式，禁止静默修复"})

    for name in ("Objects", "Regions"):
        path = safe_path(root, name)
        if path.exists() and name not in declared_names:
            _append_issue(warnings, "undeclared_component", "发现未在组件表声明的空间组件", component=name, path=name)

    if not mapinfo_path.is_file() or mapinfo.get("format") != "native_mapinfo_binary":
        native_repairs.append({"path": "MapInfo", "reason": "MapInfo 缺失或签名未知，必须从同版本原生编辑器保存样本恢复"})
    if safe_path(root, "MapInfo.version").is_file():
        mapinfo_version = _inspect_sidecar(root, "MapInfo.version", "MapInfo")
        if "MapInfo.version" not in inspected_sidecars:
            version_sidecars.insert(0, mapinfo_version)
            inspected_sidecars.add("MapInfo.version")
        if mapinfo_version["format"] == "unknown":
            _append_issue(warnings, "unknown_mapinfo_version", "MapInfo.version 未通过已知 44 字节格式核验", length=mapinfo_version["length"], fourcc=mapinfo_version["fourcc"])
            unsupported.append({"path": "MapInfo.version", "reason": "未知 MapInfo 版本格式"})

    if errors:
        verdict = "blocked"
    elif warnings or unsupported or native_repairs:
        verdict = "needs_native_editor"
    else:
        verdict = "passed"
    return {
        "schema": "map-shell-audit/1",
        "verdict": verdict,
        "evidence": {"static": "passed" if verdict != "blocked" else "failed", "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed"},
        "engine_parity": False,
        "limitations": ["静态外壳检查不能证明编辑器已载入或运行时行为"],
        "core": {"present": present_core, "missing": missing_core},
        "metadata": metadata,
        "declarations": declarations,
        "mapinfo": mapinfo,
        "version_sidecars": version_sidecars,
        "errors": errors,
        "warnings": warnings,
        "repairability": {
            "safe_static_repair": safe_repairs,
            "requires_native_source": native_repairs,
            "unsupported": unsupported,
        },
    }
