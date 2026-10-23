#!/usr/bin/env python3
"""Build a deterministic graph from SC2 catalog XML dumps and local mod data."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from sc2_publication import publish_directory, staged_directory
from sc2_dependencies import build_dependency_graph, resolve_dependency_root, dependency_state, RECURSION_DISABLED, official_research_allowed
from sc2_catalog_inputs import catalog_xml_inputs, index_inputs, inventory, save_manifest
from sc2_paths import find_project_mods, load_project_config, resolve_configured_path, project_data_dir, catalog_output_dir, ensure_project_data, is_project_source
from sc2_components import parse_xml, provenance, verify_archives, component_session

from sc2_i18n import UIArgumentParser, tr, run_cli


ROOT = Path(__file__).resolve().parents[1]
# Default output is resolved from the selected project at invocation time.
BUILD_MOD_DIR = None
BUILD_MODS_DIR = None
BUILD_CAMPAIGNS_DIR = None
OFFICIAL_CACHE = None
ALLOW_PARTIAL_OFFICIAL_CACHE = False
OFFICIAL_RESEARCH = False
DEPENDENCY_NODES = {}
LOCALE = "enUS"
ALLOW_INCOMPLETE_DEPENDENCIES = False
DEPENDENCY_STATE = {"status": "complete", "problems": []}

CATALOG_PREFIX = {
    "Abil": "CAbil",
    "Actor": "CActor",
    "Behavior": "CBehavior",
    "Button": "CButton",
    "Effect": "CEffect",
    "Footprint": "CFootprint",
    "Model": "CModel",
    "Mover": "CMover",
    "Requirement": "CRequirement",
    "RequirementNode": "CRequirement",
    "Sound": "CSound",
    "Turret": "CTurret",
    "Unit": "CUnit",
    "Upgrade": "CUpgrade",
    "Validator": "CValidator",
    "Weapon": "CWeapon",
}

FIELD_TARGETS = {
    "AbilArray": "Abil",
    "Ability": "Abil",
    "Behavior": "Behavior",
    "BehaviorArray": "Behavior",
    "Button": "Button",
    "ButtonFace": "Button",
    "CmdButtonArray": "Button",
    "DefaultButtonFace": "Button",
    "Effect": "Effect",
    "EffectArray": "Effect",
    "ExpireEffect": "Effect",
    "FinalEffect": "Effect",
    "ImpactEffect": "Effect",
    "InitialEffect": "Effect",
    "LaunchEffect": "Effect",
    "PeriodicEffect": "Effect",
    "PrepEffect": "Effect",
    "Validator": "Validator",
    "ValidatorArray": "Validator",
    "AutoCastValidatorArray": "Validator",
    "Model": "Model",
    "ModelLink": "Model",
    "BuildModel": "Model",
    "Sound": "Sound",
    "SoundLink": "Sound",
    "Turret": "Turret",
    "TurretArray": "Turret",
    "Mover": "Mover",
    "MoverLink": "Mover",
    "Footprint": "Footprint",
    "PlacementFootprint": "Footprint",
    "Weapon": "Weapon",
    "WeaponArray": "Weapon",
    "Unit": "Unit",
    "unitName": "Unit",
    "Upgrade": "Upgrade",
    "Requirements": "Requirement",
    "Requirement": "Requirement",
}

ATTR_TARGETS = {
    "Abil": "Abil",
    "Ability": "Abil",
    "Actor": "Actor",
    "Behavior": "Behavior",
    "Button": "Button",
    "DefaultButtonFace": "Button",
    "Effect": "Effect",
    "Face": "Button",
    "Model": "Model",
    "ModelLink": "Model",
    "Requirements": "Requirement",
    "Requirement": "Requirement",
    "Sound": "Sound",
    "SoundLink": "Sound",
    "Subject": "Actor",
    "Target": "Actor",
    "Turret": "Turret",
    "Unit": "Unit",
    "Upgrade": "Upgrade",
    "Validator": "Validator",
    "Weapon": "Weapon",
    "unitName": "Unit",
}

ENUM_ATTRS = {
    "index",
    "State",
    "Row",
    "Column",
    "Count",
    "Time",
    "Value",
    "Operation",
    "Reference",
    "TimeUse",
    "TimeStart",
    "TimeDelay",
    "TimeMax",
    "TimeMin",
    "value",
}

ACTOR_TERM_PATTERNS = [
    (re.compile(r"\bUnit(?:Birth|Revive|Death|Construction)\.([A-Za-z0-9_]+)"), "Unit", "actor_event_unit"),
    (re.compile(r"\bEffect\.([A-Za-z0-9_]+)\.(?:Start|Stop|Finish|Update)"), "Effect", "actor_event_effect"),
    (re.compile(r"\bWeapon(?:Start|Stop|Fired)?\.([A-Za-z0-9_]+)"), "Weapon", "actor_event_weapon"),
    (re.compile(r"\bBehavior\.([A-Za-z0-9_]+)\.(?:On|Off)"), "Behavior", "actor_event_behavior"),
    (re.compile(r"\bAbil(?:Morph)?\.([A-Za-z0-9_]+)\."), "Abil", "actor_event_ability"),
    (re.compile(r"\bMorph(?:To|From)\s+([A-Za-z0-9_]+)"), "Unit", "actor_event_morph_unit"),
    (re.compile(r"\bValidateUnit\s+([A-Za-z0-9_]+)"), "Validator", "actor_event_validator"),
    (re.compile(r"\bValidatePlayer\s+([A-Za-z0-9_]+)"), "Validator", "actor_event_validator"),
]

SEND_CREATE_RE = re.compile(r"\b(?:Create|Destroy)\s+([A-Za-z0-9_]+)")
LOCALIZATION_RE = re.compile(
    r"^(?:Button|Unit|Abil|Upgrade|Behavior|Effect|Weapon|Actor|Model|Sound|Requirement|RequirementNode|Validator|Turret)/"
)
ASSET_RE = re.compile(r"^(?:Assets|Base|Mods)\\", re.IGNORECASE)


@dataclass
class Definition:
    source_class: str
    source_name: str
    file: str
    tag: str
    id: str
    parent: str | None = None
    fields: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    evidence: str
    source_file: str
    source_class: str


def node_id(kind: str, key: str) -> str:
    safe = key.replace("\\", "/")
    return f"{kind}:{safe}"


def object_node_id(catalog_family: str, object_id: str) -> str:
    return node_id("object", f"{catalog_family}:{object_id}")


@lru_cache(maxsize=1)
def find_local_mods() -> tuple[Path, ...]:
    """Return the primary mod followed by active local component dependencies."""
    global DEPENDENCY_STATE, DEPENDENCY_NODES
    DEPENDENCY_NODES = {}
    config = load_project_config(ROOT)
    primary_mods = find_project_mods(ROOT, BUILD_MOD_DIR, config=config)
    DEPENDENCY_STATE = {"status": "complete", "problems": [], "recursive": True}
    if not primary_mods:
        if config or BUILD_MOD_DIR:
            raise ValueError("Configured or explicit project source is missing or invalid")
        return ()
    primary = primary_mods[0].resolve(strict=False)
    project = config.get("project", {}) if is_project_source(ROOT, primary, config) else {}
    recursive = (
        project.get("resolve_dependencies_recursive", True)
        if isinstance(project, dict)
        else True
    )
    if not recursive:
        DEPENDENCY_STATE = {"status": "partial", "problems": [RECURSION_DISABLED], "recursive": False}
        if not ALLOW_INCOMPLETE_DEPENDENCIES:
            raise ValueError(RECURSION_DISABLED + "; use --allow-incomplete-dependencies for partial investigation")
        return (primary,)

    mods_dir = resolve_dependency_root(ROOT, primary, config, BUILD_MODS_DIR)
    graph = build_dependency_graph(primary, mods_dir, campaigns_dir=BUILD_CAMPAIGNS_DIR, official_cache=OFFICIAL_CACHE,
                                   allow_partial_official_cache=ALLOW_PARTIAL_OFFICIAL_CACHE)
    DEPENDENCY_NODES = {**graph['nodes'], **graph.get('research_nodes', {})}
    DEPENDENCY_STATE = dependency_state(graph)
    DEPENDENCY_STATE['recursive'] = recursive
    if (DEPENDENCY_STATE["status"] == "partial" and not ALLOW_INCOMPLETE_DEPENDENCIES
            and not (OFFICIAL_RESEARCH and official_research_allowed(DEPENDENCY_STATE))):
        raise ValueError("Incomplete active dependencies: " + "; ".join(DEPENDENCY_STATE["problems"]))
    # Traversal records declarations; it is not proof of engine override order.
    keys = graph.get('traversal_order', list(graph['nodes'])) + list(graph.get('research_nodes', {}))
    dependencies = list(dict.fromkeys(Path(DEPENDENCY_NODES[key]['path']).resolve(strict=False)
                                     for key in keys if key != graph['primary']))
    return (primary, *dependencies)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _rel_path(path: Path) -> str:
    """Return a stable relative path: prefer workspace-relative, then parent-relative, else absolute."""
    if _is_relative_to(path, ROOT):
        return path.relative_to(ROOT).as_posix()
    if _is_relative_to(path, ROOT.parent):
        return path.relative_to(ROOT.parent).as_posix()
    return path.as_posix()


def source_info(path: Path) -> tuple[str, str]:
    if _is_relative_to(path, ROOT):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("DataEditorXML/"):
            return "reference_export", path.stem
        if rel.startswith("XMLFromDependenciesWeDontUse/"):
            return "inactive_dependency", path.stem
    for index, mod_dir in enumerate(find_local_mods()):
        if _is_relative_to(path, mod_dir):
            if DEPENDENCY_NODES.get(str(mod_dir).casefold(), {}).get('scope') == 'research_only':
                return 'reference_export', mod_dir.stem
            source_class = "local_mod" if index == 0 else "active_component_dependency"
            return source_class, mod_dir.stem
    return "other", path.stem


@lru_cache(maxsize=4096)
def source_provenance(path: Path) -> dict | None:
    for node in DEPENDENCY_NODES.values():
        component = Path(node["path"])
        if node.get("origin") == "casc" and path.is_relative_to(component):
            evidence = node["casc"]
            return {"manifest": evidence["manifest"], "identity": evidence["identity"],
                    'loading_status': 'unconfirmed' if node.get('scope') == 'research_only' else 'confirmed',
                    "path": path.relative_to(Path(evidence["manifest"]).parent).as_posix()}
    return None


@lru_cache(maxsize=4096)
def archive_provenance(path: Path) -> dict | None:
    return provenance(path)


def input_files() -> list[Path]:
    return catalog_xml_inputs(ROOT, find_local_mods(), official_research=OFFICIAL_RESEARCH or ALLOW_PARTIAL_OFFICIAL_CACHE)


def parse_xml_file(path: Path) -> ET.Element:
    try:
        return parse_xml(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse catalog input {_rel_path(path)}: {exc}") from exc


def catalog_family(tag: str) -> str:
    if tag.startswith("CAbil"):
        return "Abil"
    if tag.startswith("CActor"):
        return "Actor"
    if tag.startswith("CBehavior"):
        return "Behavior"
    if tag.startswith("CEffect"):
        return "Effect"
    if tag.startswith("CModel"):
        return "Model"
    if tag.startswith("CRequirement"):
        return "RequirementNode" if tag != "CRequirement" else "Requirement"
    if tag.startswith("CValidator"):
        return "Validator"
    if tag.startswith("CWeapon"):
        return "Weapon"
    if tag.startswith("CFootprint"):
        return "Footprint"
    if tag.startswith("CMover"):
        return "Mover"
    if tag.startswith("CSound"):
        return "Sound"
    if tag.startswith("CTurret"):
        return "Turret"
    if tag == "CButton":
        return "Button"
    if tag == "CUnit":
        return "Unit"
    if tag == "CUpgrade":
        return "Upgrade"
    return tag.removeprefix("C")


def type_matches_family(tag: str, family: str) -> bool:
    prefix = CATALOG_PREFIX.get(family)
    return bool(prefix and tag.startswith(prefix))


def guess_target_family(elem: ET.Element, attr_name: str) -> str | None:
    if attr_name in ENUM_ATTRS and attr_name not in {"value", "Reference"}:
        return None
    if attr_name in ATTR_TARGETS:
        return ATTR_TARGETS[attr_name]
    if attr_name in {"value", "Link"} and elem.tag in FIELD_TARGETS:
        return FIELD_TARGETS[elem.tag]
    if attr_name in {"value", "Link"} and elem.tag.endswith("Array"):
        return FIELD_TARGETS.get(elem.tag.removesuffix("Array"))
    if attr_name == "Link":
        return FIELD_TARGETS.get(elem.tag) or FIELD_TARGETS.get(elem.tag.removesuffix("Array"))
    return None


def is_sc2_id(value: str) -> bool:
    if not value or value in {"0", "1", "-1"}:
        return False
    if "##" in value:
        return False
    if any(ch in value for ch in "\\/:,; "):
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value))


def split_link_values(value: str) -> Iterable[str]:
    for raw in re.split(r"[,\s;]+", value):
        item = raw.strip()
        if is_sc2_id(item):
            yield item


def add_edge(edges: set[Edge], source: str, target: str, edge_type: str, evidence: str, file: str, source_class: str) -> None:
    if source == target:
        return
    edges.add(Edge(source, target, edge_type, evidence[:160], file, source_class))


def collect_references(defn: Definition, elem: ET.Element, object_id: str, edges: set[Edge]) -> None:
    source = object_node_id(catalog_family(defn.tag), object_id)
    source_file = defn.file
    source_class = defn.source_class

    if defn.parent:
        add_edge(edges, source, object_node_id(catalog_family(defn.tag), defn.parent), "parent", "parent attribute", source_file, source_class)

    for child in elem.iter():
        defn.fields[child.tag] += 1
        for attr_name, value in child.attrib.items():
            if not value:
                continue

            if attr_name == "Reference" and "," in value:
                parts = value.split(",", 2)
                family = parts[0].strip()
                target_id = parts[1].strip() if len(parts) > 1 else ""
                if family in CATALOG_PREFIX and is_sc2_id(target_id):
                    add_edge(edges, source, object_node_id(family, target_id), "modifies_field", value, source_file, source_class)
                continue

            if attr_name == "value" and LOCALIZATION_RE.match(value):
                add_edge(edges, source, node_id("loc", value), "references_localization", f"{child.tag}.value", source_file, source_class)
                continue

            if attr_name in {"value", "File", "Icon", "AlertIcon"} and ASSET_RE.match(value):
                add_edge(edges, source, node_id("asset", value), "references_asset", f"{child.tag}.{attr_name}", source_file, source_class)
                continue

            family = guess_target_family(child, attr_name)
            if family:
                for target_id in split_link_values(value):
                    add_edge(edges, source, object_node_id(family, target_id), f"references_{family.lower()}", f"{child.tag}.{attr_name}", source_file, source_class)

        for attr_name in ("Terms", "Send", "Target"):
            value = child.attrib.get(attr_name)
            if not value:
                continue
            for pattern, family, edge_type in ACTOR_TERM_PATTERNS:
                for match in pattern.findall(value):
                    if is_sc2_id(match):
                        add_edge(edges, source, object_node_id(family, match), edge_type, value, source_file, source_class)
            if attr_name in {"Send", "Target"}:
                for match in SEND_CREATE_RE.findall(value):
                    if is_sc2_id(match):
                        add_edge(edges, source, object_node_id("Actor", match), "actor_message_actor", value, source_file, source_class)


def read_localization(path: Path, kind: str, nodes: dict[str, dict]) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip() or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        nid = node_id("loc", key)
        node = nodes.setdefault(nid, {"id": nid, "kind": "localization", "label": key, "locale": LOCALE,
                                     "values": []})
        node["values"].append({"value": value.strip(), "localization_file": kind,
                               "source_file": _rel_path(path), "source_class": source_info(path)[0],
                               "casc": source_provenance(path), "archive": archive_provenance(path)})
        # No proven ordering between sibling dependencies: retain conflicting values.
        priority = {"local_mod": 2, "active_component_dependency": 1}
        highest = max(priority.get(v["source_class"], 0) for v in node["values"])
        candidates = [v for v in node["values"] if priority.get(v["source_class"], 0) == highest]
        node["source_classes"] = sorted({v["source_class"] for v in node["values"]})
        for field in ("value_preview", "localization_file", "source_file", "source_class", "casc", "archive"):
            node.pop(field, None)
        if len({v["value"] for v in candidates}) > 1:
            node["value_status"] = "ambiguous"
        else:
            chosen = candidates[0]
            node.update({k: v for k, v in chosen.items() if k != "value"})
            node["value_preview"] = chosen["value"][:120]
            node["value_status"] = "resolved" if highest else "reference_only"


def build_graph() -> tuple[dict[str, dict], list[Edge], dict[tuple[str, str], list[Definition]]]:
    nodes: dict[str, dict] = {}
    definitions: dict[tuple[str, str], list[Definition]] = defaultdict(list)
    edges: set[Edge] = set()

    for path in input_files():
        root = parse_xml_file(path)
        source_class, source_name = source_info(path)
        if root.tag != 'Catalog':
            if root.tag == 'Includes' or (source_provenance(path) and (OFFICIAL_RESEARCH or ALLOW_PARTIAL_OFFICIAL_CACHE)):
                continue
            raise ValueError('Unsupported catalog input root ' + root.tag + ': ' + _rel_path(path))
        rel = _rel_path(path)
        for elem in root:
            object_id = elem.attrib.get("id")
            if not object_id:
                continue
            family = catalog_family(elem.tag)
            key = (family, object_id)
            defn = Definition(source_class, source_name, rel, elem.tag, object_id, elem.attrib.get("parent"))
            definitions[key].append(defn)
            nid = object_node_id(family, object_id)
            node = nodes.setdefault(
                nid,
                {
                    "id": nid,
                    "kind": "catalog_object",
                    "label": f"{family}:{object_id}",
                    "catalog_family": family,
                    "catalog_tags": sorted({elem.tag}),
                    "definitions": [],
                    "source_classes": [],
                },
            )
            node["catalog_tags"] = sorted(set(node["catalog_tags"]) | {elem.tag})
            node["definitions"].append(
                {
                    "source_class": source_class,
                    "source_name": source_name,
                    "file": rel,
                    "tag": elem.tag,
                    "parent": elem.attrib.get("parent"),
                    "casc": source_provenance(path),
                    "archive": archive_provenance(path),
                }
            )
            node["source_classes"] = sorted(set(node["source_classes"]) | {source_class})
            collect_references(defn, elem, object_id, edges)

    for mod_dir in find_local_mods():
        from sc2_official import component_file
        for name in ("GameStrings", "ObjectStrings", "TriggerStrings"):
            path = component_file(mod_dir, LOCALE + ".SC2Data/LocalizedData/" + name + ".txt")
            read_localization(path, name, nodes)

    for edge in edges:
        if edge.target.startswith("asset:"):
            nodes.setdefault(edge.target, {"id": edge.target, "kind": "asset", "label": edge.target.removeprefix("asset:")})
        elif edge.target.startswith("loc:"):
            nodes.setdefault(edge.target, {"id": edge.target, "kind": "localization", "label": edge.target.removeprefix("loc:")})

    return nodes, sorted(edges, key=lambda e: (e.source, e.type, e.target)), definitions


def outgoing(edges: Iterable[Edge]) -> dict[str, list[Edge]]:
    out: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        out[edge.source].append(edge)
    return out


def incoming(edges: Iterable[Edge]) -> dict[str, list[Edge]]:
    inc: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        inc[edge.target].append(edge)
    return inc


def shortest_reachable(start: str, out_edges: dict[str, list[Edge]], max_depth: int = 2) -> list[tuple[int, Edge]]:
    seen = {start}
    q = deque([(start, 0)])
    found: list[tuple[int, Edge]] = []
    while q:
        node, depth = q.popleft()
        if depth >= max_depth:
            continue
        for edge in out_edges.get(node, []):
            found.append((depth + 1, edge))
            if edge.target not in seen:
                seen.add(edge.target)
                q.append((edge.target, depth + 1))
    return found


def write_json(out_dir: Path, nodes: dict[str, dict], edges: list[Edge], definitions: dict[tuple[str, str], list[Definition]], build_id: str | None = None) -> None:
    data = {
        "build_id": build_id,
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": [edge.__dict__ for edge in edges],
    }
    (out_dir / "graph.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    duplicate_rows = []
    for (family, object_id), defs in sorted(definitions.items()):
        local_defs = [d for d in defs if d.source_class == "local_mod"]
        if len(local_defs) > 1:
            duplicate_rows.append(
                {
                    "catalog_family": family,
                    "id": object_id,
                    "definitions": [d.__dict__ for d in local_defs],
                }
            )
    (out_dir / "duplicates-local.json").write_text(json.dumps(duplicate_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    unresolved = []
    object_nodes = {nid for nid, node in nodes.items() if node.get("kind") == "catalog_object"}
    for edge in edges:
        if edge.source_class != "local_mod":
            continue
        if edge.target.startswith("object:") and edge.target not in object_nodes and actionable_unresolved(edge):
            unresolved.append(edge.__dict__)
    (out_dir / "unresolved-local-references.json").write_text(json.dumps(unresolved, indent=2, ensure_ascii=False), encoding="utf-8")


def write_sqlite(out_dir: Path, nodes: dict[str, dict], edges: list[Edge], build_id: str | None = None) -> None:
    db_path = out_dir / "catalog.sqlite"
    tmp_path = out_dir / "catalog.sqlite.tmp"
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(tmp_path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO metadata VALUES ('build_id', ?)", (build_id,))
        conn.executescript(
            """
            CREATE TABLE nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                catalog_family TEXT,
                source_classes TEXT NOT NULL,
                definitions TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE definitions (
                node_id TEXT NOT NULL,
                catalog_family TEXT,
                object_id TEXT,
                source_class TEXT,
                source_name TEXT,
                file TEXT,
                tag TEXT,
                parent TEXT
            );
            CREATE TABLE edges (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                type TEXT NOT NULL,
                evidence TEXT NOT NULL,
                source_file TEXT NOT NULL,
                source_class TEXT NOT NULL
            );
            """
        )

        node_rows = []
        definition_rows = []
        for node in sorted(nodes.values(), key=lambda n: n["id"]):
            source_classes = node.get("source_classes", [])
            definitions_json = node.get("definitions", [])
            node_rows.append(
                (
                    node["id"],
                    node.get("kind", ""),
                    str(node.get("label") or node["id"]),
                    node.get("catalog_family"),
                    json.dumps(source_classes, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(definitions_json, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(node, ensure_ascii=False, separators=(",", ":")),
                )
            )
            object_id = ""
            if node["id"].startswith("object:") and ":" in node["id"].removeprefix("object:"):
                _, object_id = node["id"].removeprefix("object:").split(":", 1)
            for definition in definitions_json:
                definition_rows.append(
                    (
                        node["id"],
                        node.get("catalog_family"),
                        object_id,
                        definition.get("source_class"),
                        definition.get("source_name"),
                        definition.get("file"),
                        definition.get("tag"),
                        definition.get("parent"),
                    )
                )

        conn.executemany(
            """
            INSERT INTO nodes(id, kind, label, catalog_family, source_classes, definitions, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            node_rows,
        )
        conn.executemany(
            """
            INSERT INTO definitions(node_id, catalog_family, object_id, source_class, source_name, file, tag, parent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            definition_rows,
        )
        conn.executemany(
            """
            INSERT INTO edges(source, target, type, evidence, source_file, source_class)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(e.source, e.target, e.type, e.evidence, e.source_file, e.source_class) for e in edges],
        )
        conn.executescript(
            """
            CREATE INDEX idx_nodes_kind ON nodes(kind);
            CREATE INDEX idx_nodes_family ON nodes(catalog_family);
            CREATE INDEX idx_nodes_label ON nodes(label);
            CREATE INDEX idx_definitions_node ON definitions(node_id);
            CREATE INDEX idx_definitions_source ON definitions(source_class, source_name);
            CREATE INDEX idx_edges_source ON edges(source);
            CREATE INDEX idx_edges_target ON edges(target);
            CREATE INDEX idx_edges_type ON edges(type);
            CREATE INDEX idx_edges_source_class ON edges(source_class);
            CREATE INDEX idx_edges_file ON edges(source_file);
            """
        )
        conn.commit()
    finally:
        conn.close()

    tmp_path.replace(db_path)


def write_graphml(out_dir: Path, nodes: dict[str, dict], edges: list[Edge]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="label" for="node" attr.name="label" attr.type="string"/>',
        '<key id="kind" for="node" attr.name="kind" attr.type="string"/>',
        '<key id="type" for="edge" attr.name="type" attr.type="string"/>',
        '<graph id="SC2CatalogGraph" edgedefault="directed">',
    ]
    for node in sorted(nodes.values(), key=lambda n: n["id"]):
        lines.append(f'  <node id="{escape(node["id"])}">')
        lines.append(f'    <data key="label">{escape(str(node.get("label", node["id"])))}</data>')
        lines.append(f'    <data key="kind">{escape(str(node.get("kind", "")))}</data>')
        lines.append("  </node>")
    for index, edge in enumerate(edges):
        lines.append(f'  <edge id="e{index}" source="{escape(edge.source)}" target="{escape(edge.target)}">')
        lines.append(f'    <data key="type">{escape(edge.type)}</data>')
        lines.append("  </edge>")
    lines.extend(["</graph>", "</graphml>"])
    (out_dir / "graph.graphml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def actionable_unresolved(edge: Edge) -> bool:
    """Filter schema enums and actor aliases out of missing-catalog audits."""
    if edge.type == "actor_message_actor":
        return False
    if edge.target.endswith(":None"):
        return False
    if edge.type == "references_actor":
        target_id = edge.target.rsplit(":", 1)[-1]
        if target_id.startswith("_"):
            return False
    return True


def md_link_for_node(nid: str) -> str:
    return nid.replace(":", "_").replace("/", "_").replace("\\", "_")


def write_summaries(out_dir: Path, nodes: dict[str, dict], edges: list[Edge], definitions: dict[tuple[str, str], list[Definition]], max_pages: int) -> None:
    summaries = out_dir / "summaries"
    (summaries / "objects").mkdir(parents=True, exist_ok=True)

    out = outgoing(edges)
    inc = incoming(edges)
    source_counts = Counter()
    family_counts = Counter()
    for node in nodes.values():
        if node.get("kind") != "catalog_object":
            continue
        family_counts[node.get("catalog_family", "?")] += 1
        for source_class in node.get("source_classes", []):
            source_counts[source_class] += 1

    duplicate_local = [
        (family, object_id, defs)
        for (family, object_id), defs in definitions.items()
        if len([d for d in defs if d.source_class == "local_mod"]) > 1
    ]
    unresolved_local = [
        edge
        for edge in edges
        if edge.source_class == "local_mod"
        and edge.target.startswith("object:")
        and edge.target not in nodes
        and actionable_unresolved(edge)
    ]

    index_lines = [
        "# SC2 Catalog Graph Summary",
        "",
        "Deterministic graph generated from `DataEditorXML/`, `XMLFromDependenciesWeDontUse/`, and active project mod GameData XML.",
        "",
        "## Counts",
        "",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
        f"- Catalog objects: {sum(family_counts.values())}",
        f"- Local duplicate `(catalog family, id)` entries: {len(duplicate_local)}",
        f"- Unresolved local object references: {len(unresolved_local)}",
        "",
        "## Catalog Families",
        "",
    ]
    for family, count in family_counts.most_common():
        index_lines.append(f"- {family}: {count}")
    index_lines.extend(["", "## Source Classes", ""])
    for source, count in source_counts.most_common():
        index_lines.append(f"- {source}: {count}")
    index_lines.extend(
        [
            "",
            "## Files",
            "",
            "- `graph.json`: raw deterministic graph.",
            "- `graph.graphml`: directed graph for Gephi/yEd.",
            "- `duplicates-local.json`: duplicate local catalog rows.",
            "- `unresolved-local-references.json`: local references not resolved by active/inactive/local catalogs.",
            "- `summaries/local-mod-audit.md`: high-signal local mod audit.",
            "- `summaries/object-pages.md`: index of generated local object pages.",
        ]
    )
    (summaries / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    audit_lines = [
        "# Local Mod Catalog Audit",
        "",
        "## Duplicate Local Rows",
        "",
    ]
    if duplicate_local:
        for family, object_id, defs in duplicate_local[:200]:
            audit_lines.append(f"- `{family}:{object_id}`")
            for d in defs:
                if d.source_class == "local_mod":
                    audit_lines.append(f"  - {d.file} `{d.tag}` parent `{d.parent or ''}`")
    else:
        audit_lines.append("- None")
    audit_lines.extend(["", "## Unresolved Local Object References", ""])
    if unresolved_local:
        for edge in unresolved_local[:300]:
            audit_lines.append(f"- `{edge.source}` --{edge.type}--> `{edge.target}` from `{edge.source_file}` ({edge.evidence})")
        if len(unresolved_local) > 300:
            audit_lines.append(f"- ... {len(unresolved_local) - 300} more")
    else:
        audit_lines.append("- None")
    (summaries / "local-mod-audit.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")

    coverage_lines = ["# Catalog Coverage", ""]
    by_source_file = Counter()
    for defs in definitions.values():
        for d in defs:
            by_source_file[(d.source_class, d.source_name)] += 1
    for (source_class, source_name), count in sorted(by_source_file.items()):
        coverage_lines.append(f"- {source_class}: `{source_name}` - {count} objects")
    (summaries / "catalog-coverage.md").write_text("\n".join(coverage_lines) + "\n", encoding="utf-8")

    local_nodes = [
        node
        for node in nodes.values()
        if node.get("kind") == "catalog_object" and "local_mod" in node.get("source_classes", [])
    ]
    local_nodes.sort(key=lambda n: (-(len(out.get(n["id"], [])) + len(inc.get(n["id"], []))), n["id"]))
    page_index = ["# Generated Local Object Pages", ""]
    for node in local_nodes[:max_pages]:
        nid = node["id"]
        filename = md_link_for_node(nid) + ".md"
        page_index.append(f"- [{node['label']}](objects/{filename})")
        lines = [
            f"# {node['label']}",
            "",
            f"- Node: `{nid}`",
            f"- Catalog family: `{node.get('catalog_family', '')}`",
            f"- Source classes: {', '.join(node.get('source_classes', []))}",
            "",
            "## Definitions",
            "",
        ]
        for definition in node.get("definitions", []):
            lines.append(f"- `{definition['file']}` tag `{definition['tag']}` parent `{definition.get('parent') or ''}`")
        lines.extend(["", "## Direct References", ""])
        refs = out.get(nid, [])
        if refs:
            for edge in refs[:120]:
                label = nodes.get(edge.target, {}).get("label", edge.target)
                lines.append(f"- {edge.type}: `{label}` ({edge.evidence})")
        else:
            lines.append("- None")
        lines.extend(["", "## Incoming References", ""])
        incoming_edges = inc.get(nid, [])
        if incoming_edges:
            for edge in incoming_edges[:120]:
                label = nodes.get(edge.source, {}).get("label", edge.source)
                lines.append(f"- {edge.type} from `{label}` ({edge.evidence})")
        else:
            lines.append("- None")
        lines.extend(["", "## Two-Hop Reachable References", ""])
        for depth, edge in shortest_reachable(nid, out, max_depth=2)[:160]:
            label = nodes.get(edge.target, {}).get("label", edge.target)
            lines.append(f"- depth {depth}: {edge.type} -> `{label}`")
        (summaries / "objects" / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (summaries / "object-pages.md").write_text("\n".join(page_index) + "\n", encoding="utf-8")


@component_session
def main() -> int:
    global BUILD_MOD_DIR, BUILD_MODS_DIR, BUILD_CAMPAIGNS_DIR, ALLOW_INCOMPLETE_DEPENDENCIES, OFFICIAL_CACHE, LOCALE, ALLOW_PARTIAL_OFFICIAL_CACHE, OFFICIAL_RESEARCH
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument("--mod-dir", help="Explicit primary component for investigation")
    parser.add_argument("--official-cache", type=Path, help="Read-only official cache")
    parser.add_argument('--official-research', action='store_true', help='Use verified official sources for research; loading uncertainty is never active-value evidence')
    parser.add_argument('--allow-partial-official-cache', action='store_true', help='Explicit partial official source research; also requires --allow-incomplete-dependencies')
    parser.add_argument("--locale", choices=("enUS", "zhCN"), default="enUS", help="Indexed localization language; never fabricate missing text")
    parser.add_argument("--mods-dir", help="Explicit dependency Mods root")
    parser.add_argument("--campaigns-dir", type=Path, help="Explicit dependency Campaigns root")
    parser.add_argument("--allow-incomplete-dependencies", action="store_true", help="Build an explicitly marked partial investigation index; never validates effective values")
    parser.add_argument("--out", default=None, help="Output directory (default: project runtime/catalog, or external reference cache)")
    parser.add_argument("--max-object-pages", type=int, default=350, help="Maximum generated local object summary pages")
    parser.add_argument("--sqlite-only", action="store_true", help="Refresh only the SQLite query index; skip JSON, GraphML, and summary pages")
    args = parser.parse_args()
    if args.allow_partial_official_cache and (not args.official_cache or not args.allow_incomplete_dependencies):
        parser.error('--allow-partial-official-cache requires --official-cache and --allow-incomplete-dependencies')

    BUILD_MOD_DIR, BUILD_MODS_DIR = args.mod_dir, args.mods_dir
    BUILD_CAMPAIGNS_DIR = resolve_configured_path(ROOT, str(args.campaigns_dir)) if args.campaigns_dir is not None else None
    OFFICIAL_CACHE, LOCALE = args.official_cache, args.locale
    ALLOW_PARTIAL_OFFICIAL_CACHE = args.allow_partial_official_cache
    OFFICIAL_RESEARCH = args.official_research
    ALLOW_INCOMPLETE_DEPENDENCIES = args.allow_incomplete_dependencies
    find_local_mods.cache_clear()
    source_provenance.cache_clear()
    archive_provenance.cache_clear()
    try:
        find_local_mods()
    except ValueError as exc:
        print(tr('ERROR: {p0}', p0=exc))
        return 1
    if DEPENDENCY_STATE["status"] == "partial":
        print(tr('WARNING: PARTIAL investigation index: {p0}', p0="; ".join(DEPENDENCY_STATE["problems"])))
    mods = find_local_mods()
    config = load_project_config(ROOT)
    primary = mods[0] if mods else None
    out_dir = Path(args.out) if args.out else catalog_output_dir(ROOT, config, primary)
    if args.out is None:
        data = project_data_dir(ROOT, config, primary)
        if data is not None:
            ensure_project_data(data)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir = out_dir.resolve()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    mods = find_local_mods()
    indexed_files = index_inputs(ROOT, mods, official_research=OFFICIAL_RESEARCH or ALLOW_PARTIAL_OFFICIAL_CACHE)
    input_inventory = inventory(indexed_files)
    selection = {"workspace_root": str(ROOT.resolve()), "primary": str(mods[0]) if mods else None,
                 "mods_dir": DEPENDENCY_STATE.get("mods_dir"),
                 "campaigns_dir": DEPENDENCY_STATE.get("campaigns_dir"),
                 "recursive": DEPENDENCY_STATE['recursive'],
                 "official_cache": (DEPENDENCY_STATE.get('official_cache') or {}).get('root'), "locale": LOCALE,
                 'allow_partial_official_cache': ALLOW_PARTIAL_OFFICIAL_CACHE,
                 'official_research': OFFICIAL_RESEARCH,
                 "explicit": bool(BUILD_MOD_DIR or BUILD_MODS_DIR or BUILD_CAMPAIGNS_DIR)}
    if mods and not selection["mods_dir"]:
        selection["mods_dir"] = str(resolve_dependency_root(ROOT, mods[0], load_project_config(ROOT), BUILD_MODS_DIR))
    if mods and not selection["campaigns_dir"]:
        selection["campaigns_dir"] = str(BUILD_CAMPAIGNS_DIR or Path(selection["mods_dir"]).parent / "Campaigns")
    build_id = uuid.uuid4().hex
    with staged_directory(out_dir) as stage:
        if out_dir.exists():
            shutil.copytree(out_dir, stage, dirs_exist_ok=True)
        try:
            nodes, edges, definitions = build_graph()
        except (ValueError, OSError) as exc:
            print(tr('ERROR: {p0}; previous index was preserved', p0=exc))
            return 1
        if not args.sqlite_only:
            write_json(stage, nodes, edges, definitions, build_id=build_id)
        write_sqlite(stage, nodes, edges, build_id=build_id)
        if not args.sqlite_only:
            write_graphml(stage, nodes, edges)
            write_summaries(stage, nodes, edges, definitions, args.max_object_pages)
        final_inventory = inventory(index_inputs(ROOT, mods, official_research=OFFICIAL_RESEARCH or ALLOW_PARTIAL_OFFICIAL_CACHE))
        if final_inventory != input_inventory:
            changed = [key for key in sorted(set(final_inventory) | set(input_inventory))
                       if final_inventory.get(key) != input_inventory.get(key)]
            print(tr('ERROR: Index inputs changed during build; previous index was preserved: {p0}', p0='; '.join(changed[:8])))
            return 1
        save_manifest(stage / "catalog.sqlite", input_inventory, dependencies=DEPENDENCY_STATE,
                      build_id=build_id, selection=selection)
        if not args.sqlite_only:
            save_manifest(stage / "graph.json", input_inventory, dependencies=DEPENDENCY_STATE,
                          build_id=build_id, selection=selection)
        publish_directory(stage, out_dir, "catalog-index")

    print(tr('nodes: {p0}', p0=len(nodes)))
    print(tr('edges: {p0}', p0=len(edges)))
    if not args.sqlite_only:
        local_duplicates = json.loads((out_dir / "duplicates-local.json").read_text(encoding="utf-8"))
        unresolved = json.loads((out_dir / "unresolved-local-references.json").read_text(encoding="utf-8"))
        print(tr('local duplicate ids: {p0}', p0=len(local_duplicates)))
        print(tr('unresolved local object refs: {p0}', p0=len(unresolved)))
    else:
        print(tr('SQLite query index refreshed; other generated reports were not regenerated'))
    print(tr('output: {p0}', p0=out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
