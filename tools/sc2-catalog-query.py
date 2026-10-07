#!/usr/bin/env python3
"""Token-efficient lookup over the generated SC2 catalog graph."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Iterable

from sc2_dependencies import build_dependency_graph, resolve_dependency_root, dependency_state, IncompleteDependenciesError, RECURSION_DISABLED
from sc2_catalog_inputs import changed_input, index_inputs, manifest_path, read_manifest
from sc2_paths import catalog_output_dir, find_project_mods, load_project_config, resolve_configured_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "sc2-catalog-graph-out" / "graph.json"
DEFAULT_DB = ROOT / "sc2-catalog-graph-out" / "catalog.sqlite"


def label(node: dict | None, fallback: str) -> str:
    return str((node or {}).get("label") or fallback)


def compact_file(path: str) -> str:
    return path.replace("\\", "/")


def object_id_from_node_id(node_id: str) -> str:
    if node_id.startswith("object:") and ":" in node_id.removeprefix("object:"):
        return node_id.removeprefix("object:").split(":", 1)[1]
    return ""


def edge_sort_key(edge: dict) -> tuple[str, str, str, str]:
    return (
        edge.get("type", ""),
        edge.get("target", ""),
        edge.get("source", ""),
        edge.get("source_file", ""),
    )


def print_edge(edge: dict, store: "CatalogStore", direction: str) -> None:
    if direction == "out":
        other = edge["target"]
        prefix = "->"
    else:
        other = edge["source"]
        prefix = "<-"
    print(
        f"- {prefix} {edge.get('type')} `{label(store.get_node(other), other)}` "
        f"[{edge.get('source_class')}; {compact_file(edge.get('source_file', ''))}; {edge.get('evidence', '')}]"
    )


def node_family(store: "CatalogStore", node_id: str) -> str:
    return str((store.get_node(node_id) or {}).get("catalog_family") or "")


def edge_target_family(store: "CatalogStore", edge: dict) -> str:
    return node_family(store, edge.get("target", ""))


def edge_source_family(store: "CatalogStore", edge: dict) -> str:
    return node_family(store, edge.get("source", ""))


def emit_node_header(store: "CatalogStore", node_id: str) -> None:
    node = store.get_node(node_id) or {}
    print(f"# {label(node, node_id)}")
    print(f"- id: `{node_id}`")
    if node.get("catalog_family"):
        print(f"- family: `{node.get('catalog_family')}`")
    if node.get("source_classes"):
        print(f"- sources: {', '.join(node.get('source_classes', []))}")
    definitions = node.get("definitions", [])
    if definitions:
        print("- definitions:")
        for definition in definitions[:4]:
            print(
                f"  - {compact_file(definition.get('file', ''))} "
                f"`{definition.get('tag', '')}` parent `{definition.get('parent') or ''}`"
            )
        if len(definitions) > 4:
            print(f"  - ... {len(definitions) - 4} more")


def dedupe_edges(edges: Iterable[dict]) -> list[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    result = []
    for edge in sorted(edges, key=edge_sort_key):
        key = (
            edge.get("source", ""),
            edge.get("target", ""),
            edge.get("type", ""),
            edge.get("source_file", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def filter_source_class(edges: Iterable[dict], source_class: str | None) -> list[dict]:
    if not source_class:
        return list(edges)
    return [edge for edge in edges if edge.get("source_class") == source_class]


def print_group(title: str, edges: Iterable[dict], store: "CatalogStore", direction: str, limit: int) -> None:
    rows = dedupe_edges(edges)
    print(f"\n## {title} ({len(rows)})")
    if not rows:
        print("- None")
        return
    for edge in rows[:limit]:
        print_edge(edge, store, direction)
    if len(rows) > limit:
        print(f"- ... {len(rows) - limit} more")


class CatalogStore:
    def stats(self) -> tuple[int, int, Counter, Counter, Counter]:
        raise NotImplementedError

    def get_node(self, node_id: str) -> dict | None:
        raise NotImplementedError

    def find_candidates(self, text: str, family: str | None = None) -> list[str]:
        raise NotImplementedError

    def edges_out(self, node_id: str) -> list[dict]:
        raise NotImplementedError

    def edges_in(self, node_id: str) -> list[dict]:
        raise NotImplementedError

    def unresolved_edges(self, source_class: str, contains: str | None) -> list[dict]:
        raise NotImplementedError

    def resolve_one(self, text: str, family: str | None = None) -> str:
        if self.get_node(text):
            return text
        if ":" in text and not text.startswith(("object:", "asset:", "loc:")):
            candidate = f"object:{text}"
            if self.get_node(candidate):
                return candidate
        candidates = self.find_candidates(text, family)
        if not candidates:
            raise SystemExit(f"no graph node found for `{text}`")
        return candidates[0]


class SqliteCatalogStore(CatalogStore):
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _node_from_row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return json.loads(row["data"])

    @staticmethod
    def _edge_from_row(row: sqlite3.Row) -> dict:
        return {
            "source": row["source"],
            "target": row["target"],
            "type": row["type"],
            "evidence": row["evidence"],
            "source_file": row["source_file"],
            "source_class": row["source_class"],
        }

    def stats(self) -> tuple[int, int, Counter, Counter, Counter]:
        nodes = self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        kinds = Counter(dict(self.conn.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall()))
        families = Counter(
            dict(
                self.conn.execute(
                    "SELECT catalog_family, COUNT(*) FROM nodes WHERE kind = 'catalog_object' GROUP BY catalog_family"
                ).fetchall()
            )
        )
        sources = Counter()
        for row in self.conn.execute("SELECT source_classes FROM nodes"):
            for source in json.loads(row["source_classes"] or "[]"):
                sources[source] += 1
        return nodes, edges, kinds, families, sources

    def get_node(self, node_id: str) -> dict | None:
        row = self.conn.execute("SELECT data FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return self._node_from_row(row)

    def find_candidates(self, text: str, family: str | None = None) -> list[str]:
        query = text.lower()
        params: list[str] = []
        sql = "SELECT id, label FROM nodes"
        where = []
        if family:
            where.append("lower(catalog_family) = ?")
            params.append(family.lower())
        where.append("(lower(id) = ? OR lower(label) = ? OR lower(id) LIKE ? OR lower(label) LIKE ?)")
        params.extend([query, query, f"%{query}%", f"%{query}%"])
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self.conn.execute(sql, params).fetchall()
        exact = [row["id"] for row in rows if row["id"].lower() == query or row["label"].lower() == query]
        if exact:
            return exact[:1]
        candidates = [row["id"] for row in rows]
        candidates.sort(key=lambda nid: (0 if nid.lower().endswith(query) else 1, len(nid), nid))
        return candidates

    def edges_out(self, node_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT source, target, type, evidence, source_file, source_class FROM edges WHERE source = ?",
            (node_id,),
        ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def edges_in(self, node_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT source, target, type, evidence, source_file, source_class FROM edges WHERE target = ?",
            (node_id,),
        ).fetchall()
        return [self._edge_from_row(row) for row in rows]

    def unresolved_edges(self, source_class: str, contains: str | None) -> list[dict]:
        query = (contains or "").lower()
        rows = self.conn.execute(
            """
            SELECT e.source, e.target, e.type, e.evidence, e.source_file, e.source_class
            FROM edges e
            LEFT JOIN nodes n ON n.id = e.target
            WHERE e.source_class = ?
              AND e.target LIKE 'object:%'
              AND n.id IS NULL
            ORDER BY e.source_file, e.source, e.target
            """,
            (source_class,),
        ).fetchall()
        result = []
        for row in rows:
            edge = self._edge_from_row(row)
            haystack = " ".join([edge["source"], edge["target"], edge["type"], edge["source_file"]]).lower()
            if query and query not in haystack:
                continue
            result.append(edge)
        return result


class JsonCatalogStore(CatalogStore):
    def __init__(self, path: Path):
        if not path.exists():
            raise SystemExit(f"missing graph: {path}. Run `python tools/build-sc2-catalog-graph.py` first.")
        self.path = path
        data = json.loads(path.read_text(encoding="utf-8"))
        self.build_id = data.get("build_id")
        self.nodes = {node["id"]: node for node in data.get("nodes", [])}
        self.edges = data.get("edges", [])
        self.outgoing: dict[str, list[dict]] = defaultdict(list)
        self.incoming: dict[str, list[dict]] = defaultdict(list)
        for edge in self.edges:
            self.outgoing[edge["source"]].append(edge)
            self.incoming[edge["target"]].append(edge)

    def stats(self) -> tuple[int, int, Counter, Counter, Counter]:
        kinds = Counter(node.get("kind", "?") for node in self.nodes.values())
        families = Counter(node.get("catalog_family", "?") for node in self.nodes.values() if node.get("kind") == "catalog_object")
        sources = Counter()
        for node in self.nodes.values():
            for source in node.get("source_classes", []):
                sources[source] += 1
        return len(self.nodes), len(self.edges), kinds, families, sources

    def get_node(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def find_candidates(self, text: str, family: str | None = None) -> list[str]:
        query = text.lower()
        candidates = []
        for node_id, node in self.nodes.items():
            if family and node.get("catalog_family", "").lower() != family.lower():
                continue
            node_label = label(node, node_id).lower()
            if query == node_id.lower() or query == node_label:
                return [node_id]
            if query in node_id.lower() or query in node_label:
                candidates.append(node_id)
        candidates.sort(key=lambda nid: (0 if label(self.nodes[nid], nid).lower().endswith(query) else 1, len(nid), nid))
        return candidates

    def edges_out(self, node_id: str) -> list[dict]:
        return list(self.outgoing.get(node_id, []))

    def edges_in(self, node_id: str) -> list[dict]:
        return list(self.incoming.get(node_id, []))

    def unresolved_edges(self, source_class: str, contains: str | None) -> list[dict]:
        rows = []
        query = (contains or "").lower()
        for edge in self.edges:
            if edge.get("source_class") != source_class:
                continue
            target = edge.get("target", "")
            if not target.startswith("object:") or target in self.nodes:
                continue
            haystack = " ".join([edge.get("source", ""), target, edge.get("type", ""), edge.get("source_file", "")]).lower()
            if query and query not in haystack:
                continue
            rows.append(edge)
        rows.sort(key=lambda e: (e.get("source_file", ""), e.get("source", ""), e.get("target", "")))
        return rows


def stale_default_index_input(store: CatalogStore, *, verify_hashes: bool = False, allow_incomplete_dependencies: bool = False) -> Path | None:
    """Find a changed default-index input, including added or removed files."""
    if not isinstance(store, (SqliteCatalogStore, JsonCatalogStore)):
        return None
    manifest = read_manifest(store.path)
    if manifest.get("version") != 3:
        return manifest_path(store.path)
    selection = manifest["selection"]
    workspace = Path(selection["workspace_root"])
    if not workspace.is_dir():
        raise ValueError("Recorded index workspace is missing: " + str(workspace))
    primary = Path(selection["primary"]) if selection.get("primary") else None
    mods = []
    if primary:
        if not primary.is_dir():
            raise ValueError("Recorded index primary component is missing: " + str(primary))
        mods = [primary]
        if not selection.get("recursive", True):
            if not allow_incomplete_dependencies:
                raise IncompleteDependenciesError(RECURSION_DISABLED)
            print("WARNING: PARTIAL current dependency investigation: " + RECURSION_DISABLED, file=sys.stderr)
        else:
            graph = build_dependency_graph(primary, Path(selection["mods_dir"]))
            state = dependency_state(graph)
            if state["status"] == "partial":
                if not allow_incomplete_dependencies:
                    raise IncompleteDependenciesError("Incomplete active dependencies: " + "; ".join(state["problems"]))
                print("WARNING: PARTIAL current dependency investigation: " + "; ".join(state["problems"]), file=sys.stderr)
            mods = [Path(node["path"]) for node in graph["nodes"].values()]
    return changed_input(store.path, index_inputs(workspace, mods), verify_hashes=verify_hashes)


def load_store(args: argparse.Namespace) -> CatalogStore:
    default_out = catalog_output_dir(ROOT) if not args.db and not args.graph else None
    db_path = Path(args.db) if args.db else (default_out / "catalog.sqlite" if default_out else None)
    graph_path = Path(args.graph) if args.graph else (db_path.with_name("graph.json") if db_path else default_out / "graph.json")
    if db_path and db_path.exists():
        store: CatalogStore = SqliteCatalogStore(db_path)
    else:
        sibling_db = graph_path.with_name("catalog.sqlite")
        if sibling_db.exists():
            store = SqliteCatalogStore(sibling_db)
        else:
            store = JsonCatalogStore(graph_path)
    allow_partial = getattr(args, "allow_incomplete_dependencies", False)
    def reject(message):
        if isinstance(store, SqliteCatalogStore):
            store.close()
        raise SystemExit(message)
    if isinstance(store, SqliteCatalogStore):
        try:
            row = store.conn.execute("SELECT value FROM metadata WHERE key='build_id'").fetchone()
            artifact_id = row[0] if row else None
        except sqlite3.Error:
            artifact_id = None
    else:
        artifact_id = store.build_id
    try:
        manifest = read_manifest(store.path)
    except ValueError as exc:
        if artifact_id or not args.allow_stale:
            reject("Index/manifest integrity cannot be verified; rebuild required: " + str(exc))
        print("WARNING: Historical legacy index only; no verified manifest: " + str(exc), file=sys.stderr)
        return store
    state = manifest["dependencies"]
    if state["status"] == "partial":
        if not allow_partial:
            reject("Partial dependency index requires --allow-incomplete-dependencies: " + "; ".join(state["problems"]))
        print("WARNING: PARTIAL dependency index, investigation only: " + "; ".join(state["problems"]), file=sys.stderr)
    if manifest["version"] != 3:
        if artifact_id:
            reject("Bound index is paired with a legacy manifest; rebuild required")
        if not args.allow_stale:
            reject("Legacy manifest requires rebuild; --allow-stale permits historical inspection only")
        print("WARNING: Historical legacy index only; build identity is unverified; rebuild required", file=sys.stderr)
        return store
    selection = manifest.get("selection")
    if (not isinstance(artifact_id, str) or not artifact_id or artifact_id != manifest.get("build_id")
            or not isinstance(selection, dict) or not isinstance(selection.get("workspace_root"), str)
            or (selection.get("primary") and not selection.get("mods_dir"))):
        reject("Index/manifest build_id or input identity mismatch; rebuild required (cannot be waived by --allow-stale)")
    print("Index scope: " + str(selection.get("primary") or "reference-only") + " [build_id=" + artifact_id + "]", file=sys.stderr)
    try:
        stale_input = stale_default_index_input(store, verify_hashes=getattr(args, "verify_input_hashes", False),
                                                allow_incomplete_dependencies=allow_partial)
        message = f"Catalog index is stale; changed input: {stale_input}" if stale_input is not None else None
    except IncompleteDependenciesError as exc:
        reject(str(exc) + "; use --allow-incomplete-dependencies only for partial investigation")
    except ValueError as exc:
        message = f"Cannot verify current catalog index: {exc}"
    if message:
        if args.allow_stale:
            print("WARNING: Historical inspection only. " + message, file=sys.stderr)
        else:
            reject(message + "\nRebuild the selected index, or pass --allow-stale only for historical inspection")

    return store


def command_stats(args: argparse.Namespace) -> None:
    store = load_store(args)
    nodes, edges, kinds, families, sources = store.stats()
    print(f"Nodes: {nodes}")
    print(f"Edges: {edges}")
    print("Node kinds: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common(8)))
    print("Catalog families: " + ", ".join(f"{k}={v}" for k, v in families.most_common(12)))
    print("Source classes: " + ", ".join(f"{k}={v}" for k, v in sources.most_common()))


def command_find(args: argparse.Namespace) -> None:
    store = load_store(args)
    candidates = store.find_candidates(args.query, args.family)
    if args.kind:
        candidates = [nid for nid in candidates if (store.get_node(nid) or {}).get("kind") == args.kind]
    if args.source_class:
        candidates = [nid for nid in candidates if args.source_class in (store.get_node(nid) or {}).get("source_classes", [])]
    for nid in candidates[: args.limit]:
        node = store.get_node(nid) or {}
        detail = []
        if node.get("catalog_family"):
            detail.append(node["catalog_family"])
        if node.get("source_classes"):
            detail.append(",".join(node["source_classes"]))
        print(f"- `{label(node, nid)}` id=`{nid}` {'; '.join(detail)}")
    if len(candidates) > args.limit:
        print(f"... {len(candidates) - args.limit} more")


def command_show(args: argparse.Namespace) -> None:
    store = load_store(args)
    nid = store.resolve_one(args.id, args.family)
    node = store.get_node(nid) or {}
    print(f"# {label(node, nid)}")
    print(f"- id: `{nid}`")
    print(f"- kind: `{node.get('kind', '')}`")
    if node.get("catalog_family"):
        print(f"- family: `{node.get('catalog_family')}`")
    if node.get("source_classes"):
        print(f"- sources: {', '.join(node.get('source_classes', []))}")
    definitions = node.get("definitions", [])
    if definitions:
        print("- definitions:")
        for definition in definitions[: args.definitions]:
            print(
                f"  - {compact_file(definition.get('file', ''))} "
                f"`{definition.get('tag', '')}` parent `{definition.get('parent') or ''}`"
            )
        if len(definitions) > args.definitions:
            print(f"  - ... {len(definitions) - args.definitions} more")

    out_edges = sorted(store.edges_out(nid), key=edge_sort_key)
    in_edges = sorted(store.edges_in(nid), key=edge_sort_key)
    if args.source_class:
        out_edges = [edge for edge in out_edges if edge.get("source_class") == args.source_class]
        in_edges = [edge for edge in in_edges if edge.get("source_class") == args.source_class]
    print(f"\n## Outgoing ({len(out_edges)})")
    for edge in out_edges[: args.limit]:
        print_edge(edge, store, "out")
    if len(out_edges) > args.limit:
        print(f"- ... {len(out_edges) - args.limit} more")
    print(f"\n## Incoming ({len(in_edges)})")
    for edge in in_edges[: args.limit]:
        print_edge(edge, store, "in")
    if len(in_edges) > args.limit:
        print(f"- ... {len(in_edges) - args.limit} more")

    if args.depth > 1:
        print(f"\n## Reachable depth {args.depth}")
        seen = {nid}
        queue = deque([(nid, 0)])
        emitted = 0
        while queue and emitted < args.limit:
            current, depth = queue.popleft()
            if depth >= args.depth:
                continue
            for edge in sorted(store.edges_out(current), key=edge_sort_key):
                target = edge["target"]
                if target in seen:
                    continue
                seen.add(target)
                queue.append((target, depth + 1))
                print(f"- d{depth + 1}: `{label(store.get_node(target), target)}` via {edge.get('type')}")
                emitted += 1
                if emitted >= args.limit:
                    break


def command_providers(args: argparse.Namespace) -> None:
    store = load_store(args)
    nid = store.resolve_one(args.id, args.family)
    node = store.get_node(nid) or {}
    print(f"# Providers for {label(node, nid)}")
    definitions = node.get("definitions", [])
    if not definitions:
        print("- No catalog definitions on this node.")
        return
    for definition in definitions:
        print(
            f"- {definition.get('source_class')} `{definition.get('source_name')}`: "
            f"{compact_file(definition.get('file', ''))} `{definition.get('tag', '')}` "
            f"parent `{definition.get('parent') or ''}`"
        )


def command_unresolved(args: argparse.Namespace) -> None:
    store = load_store(args)
    rows = store.unresolved_edges(args.source_class, args.contains)
    print(f"Unresolved {args.source_class} object refs: {len(rows)}")
    for edge in rows[: args.limit]:
        print(
            f"- `{label(store.get_node(edge['source']), edge['source'])}` --{edge.get('type')}--> "
            f"`{edge['target']}` [{compact_file(edge.get('source_file', ''))}; {edge.get('evidence', '')}]"
        )
    if len(rows) > args.limit:
        print(f"... {len(rows) - args.limit} more")


def iter_neighbors(store: CatalogStore, node_id: str, directed: bool) -> Iterable[tuple[str, dict]]:
    for edge in store.edges_out(node_id):
        yield edge["target"], edge
    if not directed:
        for edge in store.edges_in(node_id):
            yield edge["source"], edge


def command_path(args: argparse.Namespace) -> None:
    store = load_store(args)
    start = store.resolve_one(args.source, args.source_family)
    goal = store.resolve_one(args.target, args.target_family)
    queue = deque([(start, [])])
    seen = {start}
    found = None
    while queue:
        current, path = queue.popleft()
        if len(path) >= args.max_depth:
            continue
        for nxt, edge in iter_neighbors(store, current, args.directed):
            if nxt in seen:
                continue
            next_path = path + [(current, nxt, edge)]
            if nxt == goal:
                found = next_path
                queue.clear()
                break
            seen.add(nxt)
            queue.append((nxt, next_path))
    if not found:
        print(f"No path within depth {args.max_depth}: `{label(store.get_node(start), start)}` -> `{label(store.get_node(goal), goal)}`")
        return
    print(f"Path length {len(found)}")
    for source, target, edge in found:
        arrow = "->" if edge["source"] == source else "<-"
        print(f"- `{label(store.get_node(source), source)}` {arrow} {edge.get('type')} `{label(store.get_node(target), target)}`")


def command_unit_chain(args: argparse.Namespace) -> None:
    store = load_store(args)
    unit_id = store.resolve_one(args.id, "Unit")
    emit_node_header(store, unit_id)

    out_edges = filter_source_class(store.edges_out(unit_id), args.source_class)
    in_edges = filter_source_class(store.edges_in(unit_id), args.source_class)
    print_group(
        "Abilities",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Abil"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Weapons",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Weapon"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Behaviors",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Behavior"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Command Buttons",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Button"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Production Abilities Targeting This Unit",
        (edge for edge in in_edges if edge_source_family(store, edge) == "Abil" and edge.get("type") == "references_unit"),
        store,
        "in",
        args.limit,
    )
    print_group(
        "Actors Listening To This Unit",
        (
            edge
            for edge in in_edges
            if edge_source_family(store, edge) == "Actor"
            and (edge.get("type", "").startswith("actor_event_") or edge.get("type") == "references_unit")
        ),
        store,
        "in",
        args.limit,
    )


def command_ability_chain(args: argparse.Namespace) -> None:
    store = load_store(args)
    abil_id = store.resolve_one(args.id, "Abil")
    emit_node_header(store, abil_id)

    out_edges = filter_source_class(store.edges_out(abil_id), args.source_class)
    in_edges = filter_source_class(store.edges_in(abil_id), args.source_class)
    print_group(
        "Units Using This Ability",
        (edge for edge in in_edges if edge_source_family(store, edge) == "Unit"),
        store,
        "in",
        args.limit,
    )
    print_group(
        "Produced Or Referenced Units",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Unit"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Buttons",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Button"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Requirements",
        (edge for edge in out_edges if edge_target_family(store, edge) in {"Requirement", "RequirementNode"}),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Effects",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Effect"),
        store,
        "out",
        args.limit,
    )
    print_group(
        "Validators",
        (edge for edge in out_edges if edge_target_family(store, edge) == "Validator"),
        store,
        "out",
        args.limit,
    )


def actor_seed_ids(store: CatalogStore, raw_id: str, source_class: str | None) -> list[str]:
    try:
        actor_id = store.resolve_one(raw_id, "Actor")
        if node_family(store, actor_id) == "Actor":
            return [actor_id]
    except SystemExit:
        pass
    unit_id = store.resolve_one(raw_id, "Unit")
    actors = [
        edge["source"]
        for edge in store.edges_in(unit_id)
        if edge_source_family(store, edge) == "Actor"
        and (not source_class or edge.get("source_class") == source_class)
        and (edge.get("type", "").startswith("actor_event_") or edge.get("type") == "references_unit")
    ]
    return sorted(set(actors))


def command_actor_chain(args: argparse.Namespace) -> None:
    store = load_store(args)
    actor_ids = actor_seed_ids(store, args.id, args.source_class)
    if not actor_ids:
        print(f"No actors found for `{args.id}`")
        return
    print(f"# Actor Chain: {args.id}")
    for actor_id in actor_ids[: args.actors]:
        emit_node_header(store, actor_id)
        out_edges = filter_source_class(store.edges_out(actor_id), args.source_class)
        print_group(
            "Unit/Ability/Effect/Weapon/Behavior Event Targets",
            (
                edge
                for edge in out_edges
                if edge_target_family(store, edge) in {"Unit", "Abil", "Effect", "Weapon", "Behavior", "Validator"}
            ),
            store,
            "out",
            args.limit,
        )
        print_group(
            "Models",
            (edge for edge in out_edges if edge_target_family(store, edge) == "Model"),
            store,
            "out",
            args.limit,
        )
        print_group(
            "Sounds",
            (edge for edge in out_edges if edge_target_family(store, edge) == "Sound"),
            store,
            "out",
            args.limit,
        )
        print_group(
            "Created Or Messaged Actors",
            (edge for edge in out_edges if edge_target_family(store, edge) == "Actor"),
            store,
            "out",
            args.limit,
        )
    if len(actor_ids) > args.actors:
        print(f"\n... {len(actor_ids) - args.actors} more actors omitted")


def command_production_chain(args: argparse.Namespace) -> None:
    store = load_store(args)
    try:
        start = store.resolve_one(args.id, "Unit")
    except SystemExit:
        start = store.resolve_one(args.id, "Abil")
    family = node_family(store, start)
    emit_node_header(store, start)

    if family == "Unit":
        producer_edges = [
            edge
            for edge in filter_source_class(store.edges_in(start), args.source_class)
            if edge_source_family(store, edge) == "Abil" and edge.get("type") == "references_unit"
        ]
        print_group("Production Abilities", producer_edges, store, "in", args.limit)
        for edge in dedupe_edges(producer_edges)[: args.expand]:
            abil_id = edge["source"]
            print(f"\n# Production Ability Detail: {label(store.get_node(abil_id), abil_id)}")
            abil_edges = filter_source_class(store.edges_out(abil_id), args.source_class)
            print_group(
                "Produced Units",
                (e for e in abil_edges if edge_target_family(store, e) == "Unit"),
                store,
                "out",
                args.limit,
            )
            print_group(
                "Buttons",
                (e for e in abil_edges if edge_target_family(store, e) == "Button"),
                store,
                "out",
                args.limit,
            )
            print_group(
                "Requirements",
                (e for e in abil_edges if edge_target_family(store, e) in {"Requirement", "RequirementNode"}),
                store,
                "out",
                args.limit,
            )
        return

    if family == "Abil":
        out_edges = filter_source_class(store.edges_out(start), args.source_class)
        in_edges = filter_source_class(store.edges_in(start), args.source_class)
        print_group(
            "Producer Units",
            (edge for edge in in_edges if edge_source_family(store, edge) == "Unit"),
            store,
            "in",
            args.limit,
        )
        print_group(
            "Produced Units",
            (edge for edge in out_edges if edge_target_family(store, edge) == "Unit"),
            store,
            "out",
            args.limit,
        )
        print_group(
            "Buttons",
            (edge for edge in out_edges if edge_target_family(store, edge) == "Button"),
            store,
            "out",
            args.limit,
        )
        print_group(
            "Requirements",
            (edge for edge in out_edges if edge_target_family(store, edge) in {"Requirement", "RequirementNode"}),
            store,
            "out",
            args.limit,
        )
        return

    raise SystemExit(f"`{args.id}` resolved to {family or 'unknown'}, expected Unit or Abil")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=None, help="Graph path; default: selected project catalog, or sibling of explicit --db")
    parser.add_argument("--db", default=None, help="SQLite path; default: selected project catalog (explicit --graph keeps its own scope)")
    parser.add_argument("--allow-incomplete-dependencies", action="store_true", help="Explicitly permit marked partial dependency investigation; independent of --allow-stale")
    parser.add_argument("--allow-stale", action="store_true", help="Permit explicitly marked historical inspection when the default index is outdated or current project configuration cannot be verified")
    parser.add_argument("--verify-input-hashes", action="store_true", help="Hash indexed inputs to detect same-size edits with restored timestamps")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats")

    find = sub.add_parser("find", help="Find graph nodes by substring")
    find.add_argument("query")
    find.add_argument("--family")
    find.add_argument("--kind")
    find.add_argument("--source-class")
    find.add_argument("--limit", type=int, default=30)

    show = sub.add_parser("show", help="Show one object and bounded references")
    show.add_argument("id")
    show.add_argument("--family")
    show.add_argument("--source-class")
    show.add_argument("--limit", type=int, default=40)
    show.add_argument("--definitions", type=int, default=8)
    show.add_argument("--depth", type=int, default=1)

    providers = sub.add_parser("providers", help="Show which dumps define an object")
    providers.add_argument("id")
    providers.add_argument("--family")

    unresolved = sub.add_parser("unresolved", help="List unresolved object references")
    unresolved.add_argument("--contains")
    unresolved.add_argument("--source-class", default="local_mod")
    unresolved.add_argument("--limit", type=int, default=80)

    path = sub.add_parser("path", help="Shortest path between two graph nodes")
    path.add_argument("source")
    path.add_argument("target")
    path.add_argument("--source-family")
    path.add_argument("--target-family")
    path.add_argument("--max-depth", type=int, default=5)
    path.add_argument("--directed", action="store_true")

    unit_chain = sub.add_parser("unit-chain", help="Curated unit dependencies: production, abilities, weapons, actors")
    unit_chain.add_argument("id")
    unit_chain.add_argument("--source-class")
    unit_chain.add_argument("--limit", type=int, default=12)

    ability_chain = sub.add_parser("ability-chain", help="Curated ability dependencies: producer units, targets, buttons, requirements, effects")
    ability_chain.add_argument("id")
    ability_chain.add_argument("--source-class")
    ability_chain.add_argument("--limit", type=int, default=12)

    actor_chain = sub.add_parser("actor-chain", help="Curated actor presentation chain for an actor or unit")
    actor_chain.add_argument("id")
    actor_chain.add_argument("--source-class")
    actor_chain.add_argument("--limit", type=int, default=12)
    actor_chain.add_argument("--actors", type=int, default=6, help="Maximum actors to expand when the input is a unit")

    production_chain = sub.add_parser("production-chain", help="Curated production chain for a produced unit or train/build ability")
    production_chain.add_argument("id")
    production_chain.add_argument("--source-class")
    production_chain.add_argument("--limit", type=int, default=12)
    production_chain.add_argument("--expand", type=int, default=4, help="Production abilities to expand when the input is a unit")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "stats": command_stats,
        "find": command_find,
        "show": command_show,
        "providers": command_providers,
        "unresolved": command_unresolved,
        "path": command_path,
        "unit-chain": command_unit_chain,
        "ability-chain": command_ability_chain,
        "actor-chain": command_actor_chain,
        "production-chain": command_production_chain,
    }
    commands[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
