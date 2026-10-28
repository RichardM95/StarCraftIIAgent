"""Read-only MD34 inspection, and source-root based resource closure.

The parser is deliberately a metadata reader, not a mesh decoder or writer.
No old work directory, Blender add-on, or third-party implementation is loaded.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import struct

from . import assets
from .catalog import CatalogSession
from .errors import SC2Error

PARSER_VERSION = "sc2-metadata-md34-2"
_MODEL_SIZES = {20: 748, 21: 760, 23: 784, 24: 796, 25: 808,
                26: 820, 28: 844, 29: 856, 30: 868}
_SIZES = {"SEQS": {1: 96, 2: 92}, "ATT_": {1: 20},
          "MAT_": {15: 268, 16: 280, 17: 280, 18: 280, 19: 340, 20: 352},
          "LAYR": {20: 356, 21: 356, 22: 356, 23: 428, 24: 436, 25: 468, 26: 464}}
_RESOURCE = re.compile(r"(?i)\.(?:dds|tga|png|jpg|m3|m3a)$")


def inspect_model(path: Path) -> dict:
    """Inspect fixed MD34 metadata. Unsupported signatures remain unsupported.

    Structural corruption raises ``invalid_model``. Unknown metadata versions
    return partial evidence with explicit unsupported entries, never absence.
    """
    path = Path(path)
    if not path.is_file():
        raise SC2Error("model_missing", "模型文件不存在", path=str(path))
    raw = path.read_bytes()
    report = {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
              "size": len(raw), "parser_version": PARSER_VERSION, "status": "unsupported",
              "format": None, "model_version": None, "animations": [], "attachments": [],
              "materials": [], "textures": [], "external_animations": [], "model_variants": [],
              "literal_resource_references": [], "unsupported": [], "engine_parity": False,
              "weapon_attachments": None, "has_death_animation": None,
              "evidence_layer": "static", "limitations": [
                  "Only supported metadata is decoded; mesh, physics, animation keyframes and rendering are not validated.",
                  "Catalog RequiredAnims/AnimProps are separate sources; the binary alone is not a complete resource closure."]}
    if raw[:4] != b"43DM":
        report["unsupported"].append({"reason": "unsupported_signature", "signature_hex": raw[:4].hex()})
        return report
    report["format"] = "MD34"
    if len(raw) < 24:
        raise SC2Error("invalid_model", "MD34 文件头被截断", path=str(path))
    table, count = struct.unpack_from("<II", raw, 4)
    if count == 0 or table < 24 or table + count * 16 > len(raw):
        raise SC2Error("invalid_model", "MD34 索引表越界", path=str(path))
    sections = []
    for index in range(count):
        tag, offset, repetitions, version = struct.unpack_from("<4sIII", raw, table + index * 16)
        try:
            tag = tag[::-1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise SC2Error("invalid_model", "MD34 索引标签不是 ASCII", index=index) from exc
        if offset >= table or offset < 0:
            raise SC2Error("invalid_model", "MD34 数据段越界", index=index, offset=offset)
        sections.append({"tag": tag, "offset": offset, "count": repetitions, "version": version, "index": index})
    offsets = sorted({s["offset"] for s in sections} | {table})
    for section in sections:
        section["end"] = next(o for o in offsets if o > section["offset"])
    header = sections[0]
    if header["tag"] != "MD34" or header["offset"] != 0 or header["count"] != 1:
        raise SC2Error("invalid_model", "MD34 首索引未指向唯一文件头", section=header)
    report["header_version"] = header["version"]
    if header["version"] != 11:
        report["unsupported"].append({"reason": "header_version", "version": header["version"]})
        return report

    def data(section, stride):
        if section["count"] * stride > section["end"] - section["offset"]:
            raise SC2Error("invalid_model", "MD34 数据段记录长度越界", section=section)
        return range(section["offset"], section["offset"] + section["count"] * stride, stride)

    def reference(offset, expected):
        if offset + 12 > table:
            raise SC2Error("invalid_model", "MD34 引用越界", offset=offset)
        entries, index, flags = struct.unpack_from("<III", raw, offset)
        if not entries:
            return None
        if index >= len(sections):
            raise SC2Error("invalid_model", "MD34 引用索引越界", offset=offset, index=index)
        section = sections[index]
        if section["tag"] != expected or entries > section["count"]:
            raise SC2Error("invalid_model", "MD34 引用类型或数量错误", offset=offset, expected=expected, section=section)
        if flags:
            report["unsupported"].append({"reason": "reference_flags", "offset": offset, "flags": flags})
        return {**section, "count": entries}

    def string(offset, material_name=False):
        section = reference(offset, "CHAR")
        if section is None:
            return ""
        if section["version"] != 0:
            report["unsupported"].append({"reason": "char_version", "section": section})
            return None
        data(section, 1)
        value = raw[section["offset"]:section["offset"] + section["count"]]
        if material_name and value.endswith(b"\0") and b"\0" in value[:-1]:
            # Official collection portraits can contain stale bytes after the
            # first NUL in a material label. Do not guess the intended label or
            # reject unrelated, independently bounded texture references.
            report["unsupported"].append({"reason": "embedded_nul_material_name", "section": section})
            return None
        if not value.endswith(b"\0") or b"\0" in value[:-1]:
            raise SC2Error("invalid_model", "MD34 字符串未正常终止", section=section)
        try:
            return value[:-1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SC2Error("invalid_model", "MD34 字符串不是 UTF-8", section=section) from exc

    model = reference(12, "MODL")
    if model is None or model["count"] != 1:
        raise SC2Error("invalid_model", "MD34 没有唯一 MODL 记录")
    report["model_version"] = model["version"]
    if model["version"] not in _MODEL_SIZES:
        report["unsupported"].append({"reason": "model_version", "version": model["version"]})
        return report
    list(data(model, _MODEL_SIZES[model["version"]]))
    origin = model["offset"]
    report["model_name"] = string(origin)
    for field, expected, offset, name_offset in [("animations", "SEQS", 16, 8), ("attachments", "ATT_", 228, 4)]:
        section = reference(origin + offset, expected)
        if section is None:
            continue
        stride = _SIZES[expected].get(section["version"])
        if stride is None:
            report["unsupported"].append({"reason": "metadata_version", "field": field, "section": section})
            continue
        for at in data(section, stride):
            name = string(at + name_offset)
            if name is not None:
                report[field].append(name)
    # Standard materials and bitmap layers are indexed structures. Other
    # material families are disclosed below rather than treated as decoded.
    for section in sections:
        tag = section["tag"]
        if tag not in {"MAT_", "LAYR"}:
            continue
        stride = _SIZES[tag].get(section["version"])
        if stride is None:
            report["unsupported"].append({"reason": "metadata_version", "field": tag, "section": section})
            continue
        for at in data(section, stride):
            value = string(at + (4 if tag == "LAYR" else 0), material_name=tag == "MAT_")
            if tag == "LAYR" and value:
                report["textures"].append(value)
            elif tag == "MAT_":
                layer_start = 64 if section["version"] >= 20 else 52
                layer_count = 18 if section["version"] >= 19 else (14 if section["version"] >= 16 else 13)
                layers = []
                for offset in range(layer_start, layer_start + layer_count * 12, 12):
                    layer = reference(at + offset, "LAYR")
                    if layer:
                        layers.append(layer["index"])
                report["materials"].append({"name": value, "version": section["version"], "layer_sections": layers})
    for section in sections:
        if section["tag"] == "CHAR" and section["version"] == 0:
            list(data(section, 1))
            value = raw[section["offset"]:section["offset"] + section["count"]]
            try:
                literal = value.rstrip(b"\0").decode("utf-8")
            except UnicodeDecodeError:
                continue
            if _RESOURCE.search(literal) and "\0" not in literal:
                report["literal_resource_references"].append(literal)
                if literal.lower().endswith(".m3a"):
                    report["external_animations"].append(literal)
                elif literal.lower().endswith(".m3"):
                    report["model_variants"].append(literal)
        elif section["tag"] in {"DIS_", "CMP_", "TER_", "VOL_", "HAI_", "CREP", "VON_", "STBM", "REF_", "LFLR", "MADD"} and section["count"]:
            report["unsupported"].append({"reason": "material_family", "section": section})
    for field in ["textures", "external_animations", "model_variants", "literal_resource_references"]:
        report[field] = list(dict.fromkeys(report[field]))
    unknown_fields = {item.get("field") for item in report["unsupported"]}
    if "attachments" not in unknown_fields:
        report["weapon_attachments"] = [v for v in report["attachments"] if "weapon" in v.casefold()]
    if "animations" not in unknown_fields:
        report["has_death_animation"] = any(re.match(r"(?i)^Death(?:\b|_)", n) for n in report["animations"])
    report["status"] = "partial" if report["unsupported"] else "supported_metadata"
    report["sections"] = [{k: v for k, v in s.items() if k != "end"} for s in sections]
    return report


def resolve_assets(roots: list[Path], references: list[str], *, source_context: dict | None = None) -> dict:
    """Resolve virtual assets only against the shared materialized roots.

    The service owns CASC extraction/cache and supplies their actual component
    roots; this function does not fabricate possible pack names or extract.
    Root order is low-to-high precedence, identical to CatalogSession.
    """
    if not roots:
        raise SC2Error("missing_asset_roots", "需要已物化的来源目录")
    if not isinstance(references, (list, tuple)) or any(not isinstance(v, str) for v in references):
        raise SC2Error("invalid_asset_reference", "资源引用必须是字符串列表")
    if source_context is not None and not isinstance(source_context, dict):
        raise SC2Error("invalid_source_context", "来源上下文必须是共享 JSON 对象")
    available = {}
    for index, root in enumerate(roots):
        for relative, path in assets._files(Path(root)):
            if assets._asset(relative):
                logical = assets._logical(relative)
                available.setdefault(logical.casefold(), []).append({"root": str(Path(root).resolve()),
                    "root_index": index, "relative_path": relative, "logical_path": logical, "physical_path": str(path.resolve())})
    context = source_context or {}
    nodes, edges, missing, unknown = [], [], [], []
    pending = [(value, None) for value in references]
    visited = set()
    while pending:
        value, parent = pending.pop(0)
        if not isinstance(value, str):
            raise SC2Error("invalid_asset_reference", "资源引用必须是字符串")
        edges.append({"from": parent, "to": value})
        if assets._MACROS.search(value):
            unknown.append({"reference": value, "reason": "engine_macro"})
            continue
        logical = assets._logical(assets._relative(value))
        if logical.casefold() in visited:
            continue
        visited.add(logical.casefold())
        choices = available.get(logical.casefold(), [])
        if not choices:
            missing.append({"reference": value, "reason": "not_in_materialized_roots"})
            continue
        level = max(c["root_index"] for c in choices)
        winners = [c for c in choices if c["root_index"] == level]
        if len(winners) != 1:
            unknown.append({"reference": value, "reason": "ambiguous_asset", "sources": winners})
            continue
        node = dict(winners[0])
        path = Path(node["physical_path"])
        content = path.read_bytes()
        node.update(reference=value, sha256=hashlib.sha256(content).hexdigest(), size=len(content),
                    availability="available", build=context.get("build"),
                    source_context_id=context.get("source_context_id"),
                    source_identity_status="materialized_path_verified")
        origins = []
        for origin in context.get("dependency_report", {}).get("nodes", []):
            materialized = origin.get("materialized_root")
            if materialized and path.resolve().is_relative_to(Path(materialized).resolve()):
                origins.append({"source_path": origin.get("path"), "source_kind": origin.get("source_kind"),
                                "materialized_root": materialized, "metadata_complete": origin.get("metadata_complete")})
        if origins:
            node["origin"] = max(origins, key=lambda o: len(Path(o["materialized_root"]).parts))
        else:
            node["origin"] = {"source_path": None, "source_kind": "unknown",
                              "reason": "no_pack_identity_in_supplied_source_context"}
        if path.suffix.lower() in {".m3", ".m3a"}:
            node["model"] = inspect_model(path)
            if node["model"]["sha256"] != node["sha256"]:
                raise SC2Error("asset_source_changed", "资源闭包读取期间模型发生变化", path=str(path))
            if node["model"]["status"] != "supported_metadata":
                unknown.append({"reference": value, "reason": "model_metadata_incomplete", "unsupported": node["model"]["unsupported"]})
            for dependency in set(node["model"]["textures"] + node["model"]["literal_resource_references"]):
                pending.append((dependency, value))
        nodes.append(node)
    return {"nodes": nodes, "edges": edges, "missing": missing, "unknown": unknown,
            "complete": not missing and not unknown and context.get("complete", True),
            "scope": "supplied_materialized_roots_and_supported_model_metadata", "engine_parity": False,
            "source_context_id": context.get("source_context_id"),
            "limitations": ["CASC/build provenance comes from the shared SourceContext; absent metadata is not guessed.",
                            "A binary-only closure excludes Catalog external animation fields; use inspect_model_catalog for those."]}


def inspect_model_assets(roots: list[Path], reference: str, *, source_context: dict | None = None) -> dict:
    return resolve_assets(roots, [reference], source_context=source_context)


def inspect_model_catalog(roots: list[Path], model_id: str, *, source_context: dict | None = None) -> dict:
    """Include Model Catalog external animation and variant literals in closure."""
    model = CatalogSession(roots).inspect("Model", model_id)
    references, macros = [], []
    for field, info in model["fields"].items():
        value = info["value"]
        if isinstance(value, str) and (_RESOURCE.search(value) or assets._MACROS.search(value)):
            if assets._MACROS.search(value):
                macros.append({"field": field, "value": value, "reason": "engine_macro"})
            elif _RESOURCE.search(value):
                references.append(value)
    closure = resolve_assets(roots, list(dict.fromkeys(references)), source_context=source_context)
    closure["catalog"] = model
    closure["catalog_unknown"] = macros
    closure["complete"] = closure["complete"] and not macros and bool(references)
    return closure
