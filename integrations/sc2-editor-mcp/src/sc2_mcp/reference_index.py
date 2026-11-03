"""Project-local effective reference index. Candidate libraries never publish here."""

from collections import defaultdict
from contextlib import closing
import hashlib
import json
import sqlite3
import zlib
from xml.etree import ElementTree as ET
from pathlib import Path
from time import perf_counter

from .catalog import (
    _Library,
    _catalog_name,
    _id_index,
    _owner_edges,
    _trace,
    _trace_rows,
    _type_catalog,
)
from .errors import SC2Error
from .source_context import assert_source_context_current
from .storage import guard_absolute_path

INDEX_VERSION = "4"
BUDGET = 256 * 1024 * 1024


def encode(key):
    return json.dumps(key, separators=(",", ":"))


def descendants(library, seeds):
    children = defaultdict(set)
    for key, patches in library.objects.items():
        for patch in patches:
            if patch.node.get("parent"):
                children[(key[0], patch.node.get("parent"))].add(key)
    owners = set(seeds)
    pending = list(owners)
    while pending:
        new = children[pending.pop()] - owners
        owners.update(new)
        pending.extend(new)
    return owners


def possible_owners(library, target_ids):
    """Overselect literal and AbilCmd matches; concrete token owners need no parent scan."""
    seeds, classes, tokens = set(), set(), set()

    def matches(patches):
        found = False
        for patch in patches:
            for node in library.patch_contents(patch).iter():
                for value in node.attrib.values():
                    if value in target_ids or value.partition(",")[0] in target_ids:
                        found = True
                    if "##id##" in value:
                        tokens.add(value)
        return found

    for key, patches in library.objects.items():
        if matches(patches):
            seeds.add(key)
    for cls, patches in library.defaults.items():
        if matches(patches):
            classes.add(cls)
    seeds.update(
        key
        for key, patches in library.objects.items()
        if patches[-1].node.tag in classes
    )
    owners = descendants(library, seeds)
    for token in tokens:
        prefix, _, suffix = token.partition("##id##")
        for target in target_ids:
            if target.startswith(prefix) and target.endswith(suffix):
                ident = target[len(prefix) : len(target) - len(suffix)]
                owners.update(
                    key
                    for key in ((kind, ident) for kind in ("Actor", "Effect"))
                    if key in library.objects
                )
    return owners


def direct_scan(lib, key, target, complete):
    # Missing layers can supply parent or class defaults. Inspect every known
    # owner in this case and keep dependencies_complete false in the response.
    owners = possible_owners(lib, {key[1]}) | {key} if complete else lib.objects.keys()
    ids = _id_index(lib)
    rows = ([], [], [])
    for owner in lib.objects:
        if owner in owners:
            for group, additions in zip(rows, _owner_edges(lib, owner, ids, complete)):
                group.extend(additions)
    return _trace_rows(*key, target, *rows, direct=True), len(owners)


def configure(db):
    # DELETE journal can hold one preimage per database page plus headers.
    # Reserve more than half the total budget for rollback and bookkeeping.
    size = db.execute("pragma page_size").fetchone()[0]
    limit = (BUDGET // 2 - 1024 * 1024) // size
    if limit < 8 or db.execute("pragma page_count").fetchone()[0] > limit:
        raise sqlite3.OperationalError("reference index exceeds disk budget")
    db.execute(f"pragma max_page_count={limit}")
    db.execute("pragma temp_store=MEMORY")
    db.execute(
        "create table if not exists document(path text primary key,sha text,data blob)"
    )
    db.execute("create table if not exists meta (k text primary key,v text)")
    db.execute(
        "create table if not exists document_summary(path text primary key,data blob)"
    )
    db.execute(
        "create table if not exists owner (id text primary key, ord integer,sig text,data blob,cycle integer)"
    )
    db.execute(
        "create table if not exists link (dest text,src text,primary key(src,dest)) without rowid"
    )
    db.execute("create index if not exists incoming on link(dest,src)")


def flatten_xml(node):
    return [node.tag, node.attrib, node.text, node.tail, [flatten_xml(c) for c in node]]


def restore_xml(row):
    tag, attrs, text, tail, children = row
    node = ET.Element(tag, attrs)
    node.text, node.tail = text, tail
    node.extend(restore_xml(child) for child in children)
    return node


class _IndexedLibrary(_Library):
    """Load ordered declaration headers; materialize bodies only when inspected."""

    def __init__(self, db, ctx):
        self.db = db
        self.positions = {}
        self.digests = {}
        self.bodies = {}
        self.restore_ms = 0.0
        super().__init__(
            [Path(p) for p in ctx["roots"]],
            fingerprints=ctx["fingerprints"],
            document_loader=self.cached_headers,
        )

    def cached_headers(self, path, sha):
        row = self.db.execute(
            "select s.data from document_summary s join document d using(path) "
            "where d.path=? and d.sha=?",
            (str(path), sha),
        ).fetchone()
        if not row:
            return None
        tag, hints, declarations = json.loads(zlib.decompress(row[0]))
        self.arrays.update((cls, tuple(prefix)) for cls, prefix in hints)
        header = ET.Element(tag)
        for ordinal, (tag, attrs, digest) in enumerate(declarations):
            node = ET.SubElement(header, tag, attrs)
            self.positions[node] = ordinal
            if digest is not None:
                self.digests[node] = digest
        return sha, header

    def patch_contents(self, patch):
        ordinal = self.positions.get(patch.node)
        if ordinal is None:
            return patch.node
        if patch.file not in self.bodies:
            started = perf_counter()
            (blob,) = self.db.execute(
                "select data from document where path=?", (str(patch.file),)
            ).fetchone()
            self.bodies[patch.file] = restore_xml(json.loads(zlib.decompress(blob)))
            self.restore_ms += (perf_counter() - started) * 1000
        return self.bodies[patch.file][ordinal]


def read_documents(db, ctx):
    library = _IndexedLibrary(db, ctx)
    if any(
        ctx["fingerprints"].get(str(p)) != sha for p, sha in library.file_sha256.items()
    ):
        raise SC2Error("source_context_stale", "读取期间 Catalog 文件已变化")
    return library


def declaration_content(node):
    # Catalog merge ignores indentation. Preserve child and attribute iteration
    # order because both can be observed in ordered edges and diagnostics.
    return [
        node.tag,
        node.attrib,
        node.text if node.text and node.text.strip() else None,
        node.tail if node.tail and node.tail.strip() else None,
        [declaration_content(child) for child in node],
    ]


def update_documents(db, lib, digests, rebuild):
    previous = dict(db.execute("select path,sha from document"))
    for path, (sha, document) in lib.documents.items():
        if previous.pop(str(path), None) != sha or rebuild:
            data = zlib.compress(
                json.dumps(
                    flatten_xml(document), ensure_ascii=False, separators=(",", ":")
                ).encode(),
                1,
            )
            db.execute(
                "insert or replace into document values(?,?,?)", (str(path), sha, data)
            )
            hints = set()
            for node in document:
                if _type_catalog(node.tag):
                    lib._array_hints(node, node.tag, (), hints)
                    if node.get("default") == "1" and node not in digests:
                        # A class may acquire its first concrete object on a later save.
                        digests[node] = signature(declaration_content(node))
            header = [
                document.tag,
                sorted(hints),
                [[node.tag, node.attrib, digests.get(node)] for node in document],
            ]
            db.execute(
                "insert or replace into document_summary values(?,?)",
                (str(path), zlib.compress(encode(header).encode(), 1)),
            )
    db.executemany("delete from document where path=?", ((path,) for path in previous))
    db.executemany(
        "delete from document_summary where path=?", ((path,) for path in previous)
    )


def signature(parts):
    return hashlib.sha256(encode(parts).encode()).hexdigest()


def build(db, lib, ctx, old, timings):
    started = perf_counter()
    scope = signature(
        [
            1,
            ctx["roots"],
            ctx["build"],
            ctx["locale"],
            ctx["parser_version"],
            ctx["rules_version"],
            ctx["complete"],
            ctx.get("official_cache"),
            ctx["dependency_report"]["edges"],
        ]
    )
    digests = getattr(lib, "digests", {})

    def declarations(patches):
        result = []
        for patch in patches:
            if patch.node not in digests:
                digests[patch.node] = signature(declaration_content(lib.patch_contents(patch)))
            result.append((str(patch.file), patch.layer, digests[patch.node]))
        return result

    profiles = {
        cls: signature(
            [
                declarations(lib.defaults.get(cls, [])),
                sorted(path for tag, path in lib.arrays if tag == cls),
            ]
        )
        for cls in {p[-1].node.tag for p in lib.objects.values()}
    }
    previous = {
        tuple(json.loads(key)): (sig, ordinal)
        for key, sig, ordinal in db.execute("select id,sig,ord from owner")
    }
    signatures = {
        key: signature([declarations(patches), profiles[patches[-1].node.tag]])
        for key, patches in lib.objects.items()
    }
    old_keys = set(previous)
    new_keys = set(lib.objects)
    removed = old_keys - new_keys
    changed = {
        key
        for key, sig in signatures.items()
        if key not in previous or previous[key][0] != sig
    }
    if old.get("scope") != scope or old.get("version") != INDEX_VERSION:
        changed = new_keys
    else:
        changed = descendants(lib, changed | removed) & new_keys
        ids = {key[1] for key in old_keys ^ new_keys}
        if ids:
            changed.update(possible_owners(lib, ids))
    ids = _id_index(lib)
    compared = perf_counter()
    compare_restore = getattr(lib, "restore_ms", 0.0)
    timings["compare"] = (compared - started) * 1000 - compare_restore
    for key in removed | changed:
        db.execute("delete from link where src=?", (encode(key),))
        db.execute("delete from owner where id=?", (encode(key),))
    for ordinal, key in enumerate(lib.objects):
        if key not in changed:
            if previous[key][1] != ordinal:
                db.execute("update owner set ord=? where id=?", (ordinal, encode(key)))
            continue
        src = encode(key)
        data = _owner_edges(lib, key, ids, ctx["complete"], include_warnings=True)
        payload = zlib.compress(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(), 1
        )
        db.execute(
            "insert into owner values(?,?,?,?,?)",
            (
                src,
                ordinal,
                signatures[key],
                payload,
                any("reference" not in w for w in data[2]),
            ),
        )
        destinations = {
            encode([e["to"]["catalog"], e["to"]["object_id"]]) for e in data[0]
        }
        db.executemany(
            "insert into link values(?,?)", ((dst, src) for dst in destinations)
        )
    calculated = perf_counter()
    restore_ms = getattr(lib, "restore_ms", 0.0)
    timings["xml"] += restore_ms
    timings["edges"] = (calculated - compared) * 1000 - (restore_ms - compare_restore)
    update_documents(db, lib, digests, old.get("version") != INDEX_VERSION)
    if db.execute("pragma quick_check").fetchone() != ("ok",):
        raise sqlite3.DatabaseError("reference index integrity check failed")
    db.executemany(
        "insert or replace into meta values(?,?)",
        [
            ("scope", scope),
            ("version", INDEX_VERSION),
            ("warnings", json.dumps(lib.warnings)),
            ("generation", ctx["source_context_id"]),
            (
                "inputs",
                json.dumps(
                    {
                        "roots": ctx["roots"],
                        "build": ctx["build"],
                        "rules": ctx["rules_version"],
                        "complete": ctx["complete"],
                        "files": {str(p): h for p, h in lib.file_sha256.items()},
                    },
                    ensure_ascii=False,
                ),
            ),
        ],
    )
    timings["publish"] = (perf_counter() - calculated) * 1000
    return len(changed)


def indexed_trace(db, key, global_warnings, direct, fingerprints):
    def bind_source(record):
        if "sha256" in record and "file" in record:
            record["sha256"] = fingerprints[record["file"]]
        return record

    def decode(blob):
        return json.loads(zlib.decompress(blob), object_hook=bind_source)

    origin = encode(key)
    stored = db.execute("select data from owner where id=?", (origin,)).fetchone()
    if not stored:
        raise SC2Error(
            "catalog_object_not_found",
            "已加载的数据中没有该对象",
            catalog=key[0],
            object_id=key[1],
        )
    record = decode(stored[0])
    if record[3] is None:
        raise SC2Error(
            "catalog_parent_cycle",
            "Catalog parent 出现循环",
            chain=record[2][0]["chain"],
        )
    target = {"warnings": global_warnings + record[3]}
    owners = {origin}
    if not direct:
        owners.update(
            row[0]
            for row in db.execute(
                """with recursive reached(id) as
            (select ? union select dest from link join reached on link.src=reached.id)
            select id from reached""",
                (origin,),
            )
        )
    owners.update(
        row[0] for row in db.execute("select src from link where dest=?", (origin,))
    )
    if not direct:
        owners.update(
            row[0] for row in db.execute("select id from owner where cycle=1")
        )
    rows = ([], [], [])
    # Bound SQL parameters while retaining the original catalog iteration order.
    owners = list(owners)
    records = []
    for start in range(0, len(owners), 500):
        batch = owners[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        records.extend(
            db.execute(
                f"select ord,data from owner where id in ({placeholders})", batch
            )
        )
    for _, blob in sorted(records):
        for group, additions in zip(rows, decode(blob)):
            group.extend(additions)
    return _trace_rows(*key, target, *rows, direct=direct)


def query(service, project_id, catalog, identifier, context_id, mode):
    if mode not in {"direct", "full"}:
        raise SC2Error("invalid_reference_mode", "mode 必须为 direct 或 full")
    key = (_catalog_name(catalog), identifier)
    for attempt in range(2):
        try:
            return _query_current(service, project_id, key, context_id, mode)
        except SC2Error as exc:
            if context_id or exc.code not in {"source_context_stale", "source_changed"}:
                raise
            if attempt:
                raise SC2Error(
                    "source_context_stale",
                    "查询期间来源连续变化，请重新读取",
                    cause=exc.as_dict(),
                ) from exc


def _query_current(service, project_id, key, context_id, mode, *, ctx=None, lib=None):
    started = perf_counter()
    pending_context = ctx is None and not context_id
    if pending_context:
        record, _ = service.record(project_id)
        ctx = service._prepare_context(record, defer_final_check=True)
    elif ctx is None:
        ctx = service.source_context(project_id, context_id)
    timings = {
        "source": (perf_counter() - started) * 1000,
        "xml": 0.0,
        "compare": 0.0,
        "edges": 0.0,
        "publish": 0.0,
    }
    timings["source_prepare"] = timings["source"]

    def verify_current():
        checking = perf_counter()
        assert_source_context_current(ctx)
        timings["source_recheck"] = (perf_counter() - checking) * 1000
        timings["source"] += timings["source_recheck"]
    directory = service.state / "reference-index" / project_id
    path = guard_absolute_path(directory / "graph.sqlite")
    for suffix in ("-journal", "-wal", "-shm"):
        guard_absolute_path(path.with_name(path.name + suffix))

    def library():
        nonlocal lib
        if lib is None:
            lib = service._query_library(ctx, False)
        return lib

    direct = mode == "direct"
    count = 0
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=5)) as db, db:
            configure(db)
            db.execute("begin")
            old = dict(db.execute("select k,v from meta"))
            if (
                old.get("generation") == ctx["source_context_id"]
                and old.get("version") == INDEX_VERSION
            ):
                state = "hit"
            elif direct and not old.get("generation"):
                loading = perf_counter()
                lib = library()
                calculating = perf_counter()
                timings["xml"] = (calculating - loading) * 1000
                result, count = direct_scan(
                    lib, key, lib.inspect(*key), ctx["complete"]
                )
                timings["edges"] = (perf_counter() - calculating) * 1000
                state = "direct_scan"
            else:
                loading = perf_counter()
                if lib is None and old.get("version") == INDEX_VERSION:
                    lib = read_documents(db, ctx)
                lib = library()
                timings["xml"] = (perf_counter() - loading) * 1000
                count = build(db, lib, ctx, old, timings)
                state = "refreshed"
            if state != "direct_scan":
                warnings = (
                    json.loads(old["warnings"]) if state == "hit" else lib.warnings
                )
                result = indexed_trace(db, key, warnings, direct, ctx["fingerprints"])
            verify_current()
            committing = perf_counter()
        timings["publish"] += (perf_counter() - committing) * 1000
    except SC2Error as exc:
        # A lookup error based on a changing source must not be reported as a
        # stable fact. Stale results from the final check already trigger retry.
        if pending_context and exc.code not in {"source_changed", "source_context_stale"}:
            assert_source_context_current(ctx)
        raise
    except (sqlite3.DatabaseError, OSError, zlib.error, json.JSONDecodeError) as exc:
        state = "uncached: " + str(exc)
        if isinstance(lib, _IndexedLibrary):
            lib = None  # Its lazy document reader belonged to the closed transaction.
        try:
            if direct:
                result, count = direct_scan(
                    library(), key, lib.inspect(*key), ctx["complete"]
                )
            else:
                result = _trace(library(), *key, ctx["complete"])
                count = len(lib.objects)
        finally:
            verify_current()
    if pending_context:
        service.save_source_context(project_id, ctx)
    return {
        **result,
        "mode": mode,
        "index_status": state,
        "timings_ms": {key: round(value, 2) for key, value in timings.items()},
        "recomputed_objects": count,
        "index_bytes": path.stat().st_size if path.exists() else 0,
        "source_context_id": ctx["source_context_id"],
        "dependencies_complete": ctx["complete"],
    }
