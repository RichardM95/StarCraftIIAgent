#!/usr/bin/env python3
"""Query GUI trigger definitions, official cases and target dependency compatibility."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_paths import catalog_output_dir, find_project_mods, load_project_config, resolve_configured_path
from sc2_dependencies import RECURSION_DISABLED
from sc2_triggers import Index, Target, build_index, check, describe, validate_templates, walk

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "wiki/reference/trigger-cases.json"


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, help="SQLite index; default follows project/reference runtime paths")
    p.add_argument("--target", type=Path, help="Explicit Components map/mod/campaign; defaults to configured editing source")
    p.add_argument("--mods-dir", type=Path, help="Dependency Mods root")
    p.add_argument("--campaigns-dir", type=Path, help="Dependency Campaigns root")
    p.add_argument("--reference", action="store_true", help="Explicit reference research, never certifies target availability")
    p.add_argument("--verify-input-hashes", action="store_true")
    commands = p.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--reference-root", type=Path, action="append", required=True,
                       help="Repeat for official Mods and Campaigns roots")
    commands.add_parser("libraries")
    checker = commands.add_parser("check")
    checker.add_argument("--templates", action="store_true", help="Validate bundled GUI fragments against the indexed native source; optionally also against --target")
    find = commands.add_parser("find")
    find.add_argument("term")
    find.add_argument("--type", default="FunctionDef")
    find.add_argument("--limit", type=int, default=20)
    show = commands.add_parser("show")
    show.add_argument("element_ref", help="Library:Type:Id; use local:Type:Id for a map-local definition")
    show.add_argument("--source", type=Path, help="Disambiguate a reference provider by its source path")
    cases = commands.add_parser("examples")
    cases.add_argument("mechanism", choices=("initialization", "objectives", "victory-defeat", "regions", "timers", "waves", "difficulty", "transmissions", "conversations", "dialogs", "cinematics"))
    cases.add_argument("--case", dest="case_id", help="Select one curated case by case_id or exact element ID")
    cases.add_argument("--summary", action="store_true", help="Omit the full closure and raw resource values")
    cases.add_argument("--max-nodes", type=int, default=200, help="Bound displayed closure nodes/resources; 0 displays all")
    return p


def target_for(args, config):
    path = args.target
    configured_sources = find_project_mods(ROOT, config=config)
    if path is None:
        path = configured_sources[0] if configured_sources else None
    if path is None:
        return None
    path = path.resolve()
    settings = config.get("paths", {})
    configured_mods = resolve_configured_path(ROOT, settings["mods_dir"]) if settings.get("mods_dir") else None
    install = resolve_configured_path(ROOT, settings["sc2_install_dir"]) if settings.get("sc2_install_dir") else None
    use_config = (args.target is None or path in configured_sources
                  or (configured_mods is not None and path.is_relative_to(configured_mods))
                  or (install is not None and path.is_relative_to(install)))
    mods = args.mods_dir
    ancestor_mods = next((p for p in path.parents if p.name.casefold() == "mods"), None)
    if mods is None and path not in configured_sources and ancestor_mods is not None:
        mods = ancestor_mods
    if mods is None and use_config:
        mods = configured_mods
    if mods is None:
        mods = ancestor_mods
    if mods is None or not mods.is_dir():
        raise ValueError("Pass --mods-dir for this target; no dependency installation will be guessed")
    campaigns = args.campaigns_dir
    if (campaigns is None and use_config and install is not None
            and configured_mods == mods.resolve()):
        campaigns = install / "Campaigns"
    target = Target(path, mods, campaigns)
    if path in configured_sources and config.get("project", {}).get("resolve_dependencies_recursive") is False:
        target.problems.append(RECURSION_DISABLED)
    return target


def compatibility(target, d, key, *, case=None):
    if target is None:
        return {"status": "reference_only", "problems": ["No target selected"]}
    target.refresh()
    allowed = {(n['library'], n['type'], n['id']) for n in case['local_graph']} if case else set()
    # Core provenance is required even if reference XML embeds a copied Ntve definition.
    map_libraries = {e.get('Id') for e in d.root.findall('Library')}
    allowed = {k for k in allowed if not k[0] or (k[0] in map_libraries and k[0] != 'Ntve')}
    problems = []
    if case and (d.component.suffix.casefold() != '.sc2map' or d.sha256 != case['sha256']):
        problems.append(f"Unreviewed case provenance: {d.path}")
        allowed.clear()
    def resolve(k, owner):
        if owner.path == d.path and k in allowed and k in d.elements:
            return d, d.elements[k]
        return target.resolve(k, owner)
    if case:
        starts = [(d, key)]
    else:
        try:
            active, _ = target.resolve(key, d)
            if active.sha256 != d.sha256:
                problems.append(f"Reference source differs for {':'.join(key)}: {d.path} ({d.sha256}) -> {active.path} ({active.sha256})")
            starts = [(active, key)]
        except ValueError as exc:
            problems.append(str(exc))
            starts = []
    result = walk(starts, resolve, validate=False, node_limit=0)
    target.refresh()
    problems = target.problems + problems + result["errors"]
    return {"status": "unconfirmed" if target.problems else ("incompatible" if problems else "libraries_compatible"),
            "problems": problems,
            "note": "Map objects, resource links and local IDs require migration; library compatibility is not runtime acceptance"}


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    index = None
    try:
        config = load_project_config(ROOT)
        db = args.db or catalog_output_dir(ROOT, config) / "triggers.sqlite"
        if args.command == "build":
            emit(build_index(db, [r.resolve() for r in args.reference_root]))
            return 0
        target = target_for(args, config)
        if args.command == "check" and args.templates:
            index = Index(db, args.verify_input_hashes)
            result = validate_templates(index, ROOT / "wiki/reference/trigger-templates", target)
            emit(result)
            return int(bool(result["errors"]))
        if args.command in {"libraries", "check"}:
            if target is None:
                raise ValueError("No target selected; pass --target or initialize a project")
            result = target.libraries() if args.command == "libraries" else check(target)
            emit(result)
            return int(bool(result.get("problems") or result.get("errors")))
        if target is None and not args.reference:
            raise ValueError("No target selected; use --reference for reference-only research")
        if target is not None and target.problems and not args.reference:
            emit(target.libraries())
            return 1
        if args.command in {"find", "show"} and not args.reference:
            if args.command == "find" and args.limit < 1:
                raise ValueError("--limit must be positive")
            if args.command == "show":
                wanted = args.element_ref.split(":")
                if len(wanted) != 3:
                    raise ValueError("Use Library:Type:Id")
                wanted[0] = "" if wanted[0] == "local" else wanted[0]
            matches = []
            for d in target.documents:
                for key in d.elements:
                    if args.command == "find":
                        selected = key[1] == args.type and d.matches(key, args.term)
                    else:
                        selected = list(key) == wanted
                        if args.source:
                            selected = selected and d.path == args.source.resolve()
                    if selected:
                        matches.append((d, key))
        else:
            index = Index(db, args.verify_input_hashes)
            if args.command == "find":
                if args.limit < 1:
                    raise ValueError("--limit must be positive")
                rows = index.connection.execute("SELECT source,library,type,id,name,names FROM elements WHERE type=? AND instr(search_name,?)>0 ORDER BY source,name LIMIT ?",
                                                (args.type, args.term.casefold(), args.limit)).fetchall()
                emit([{**dict(r), "names": json.loads(r['names']), "source_class": "official_reference", "compatibility": compatibility(target, index.document(r["source"]), (r["library"], r["type"], r["id"]))} for r in rows])
                return 0
            if args.command == "examples":
                if args.max_nodes < 0:
                    raise ValueError("--max-nodes cannot be negative")
                records = json.loads(CASES.read_text(encoding="utf-8"))
                output = []
                for case in records["cases"]:
                    if case["mechanism"] != args.mechanism:
                        continue
                    if args.case_id and args.case_id not in {case.get('case_id'), case['id']}:
                        continue
                    rows = index.connection.execute("SELECT * FROM elements WHERE type=? AND id=?", (case["type"], case["id"])).fetchall()
                    rows = [r for r in rows if Path(r["source"]).as_posix().casefold().endswith(case["source"].casefold())]
                    if len(rows) != 1:
                        raise ValueError(f"Curated case missing/ambiguous: {case['source']}:{case['id']}")
                    row = rows[0]
                    d = index.document(row["source"])
                    if case["sha256"] != index.meta["inputs"][d.path.as_posix()]["sha256"]:
                        raise ValueError(f"Curated case changed; review tags and provenance: {d.path}")
                    key = (row["library"], row["type"], row["id"])
                    closure = walk([(d, key)], index.resolve, validate=False,
                                   node_limit=0 if args.summary else (args.max_nodes or None))
                    item = {**case, "source": str(d.path), "source_class": "official_reference",
                            "compatibility": compatibility(target, d, key, case=case), "closure": closure,
                            "required_libraries": closure['external_libraries'],
                            "generated_galaxy": str(d.component / "MapScript.galaxy")}
                    if args.summary:
                        item.pop("local_graph", None)
                        item["closure"] = {"errors": closure["errors"], "elements": closure['total_nodes'], "resources": closure['total_resources']}
                    elif args.max_nodes and 'local_graph' in item:
                        item['local_graph_total_nodes'] = len(item['local_graph'])
                        item['local_graph_truncated'] = len(item['local_graph']) > args.max_nodes
                        item['local_graph'] = item['local_graph'][:args.max_nodes]
                    item['analysis'] = {'parsed_documents': index.parsed_documents}
                    output.append(item)
                if args.case_id and not output:
                    raise ValueError(f"Unknown curated case for {args.mechanism}: {args.case_id}")
                emit(output)
                return 0
            wanted = args.element_ref.split(":")
            if len(wanted) != 3:
                raise ValueError("Use Library:Type:Id")
            wanted[0] = "" if wanted[0] == "local" else wanted[0]
            if args.source:
                d = index.document(str(args.source.resolve()))
                matches = [(d, tuple(wanted))] if tuple(wanted) in d.elements else []
            else:
                rows = index.connection.execute("SELECT DISTINCT source FROM elements WHERE library=? AND type=? AND id=?", wanted).fetchall()
                if not rows and wanted[0]:
                    rows = index.connection.execute("SELECT DISTINCT source FROM elements WHERE library=? AND type='FunctionDef'", (wanted[0],)).fetchall()
                matches = [(index.document(r["source"]), tuple(wanted)) for r in rows
                           if tuple(wanted) in index.document(r["source"]).elements]
        if args.command == "show":
            if len(matches) != 1:
                raise ValueError(f"Expected one definition, found {len(matches)}; specify --source for reference research")
            d, key = matches[0]
            result = describe(d, key, index.resolve if index else target.resolve)
            result["compatibility"] = compatibility(target, d, key)
            emit(result)
            return int(bool(result["errors"] or (not args.reference and result["compatibility"]["problems"])))
        available = []
        rejected = []
        for d, key in matches:
            state = compatibility(target, d, key)
            if state["problems"]:
                rejected.append({"source": str(d.path), "reference": list(key), "problems": state["problems"]})
            else:
                available.append((d, key))
                if len(available) >= args.limit:
                    break
        if rejected:
            print(json.dumps({"rejected_unconfirmed_definitions": rejected}, ensure_ascii=False), file=sys.stderr)
        emit([{ "source": str(d.path), "library": k[0], "type": k[1], "id": k[2], "name": d.name(k),
                "names": d.aliases(k), "source_class": "target_local" if d.component == target.path else "active_dependency"}
              for d, k in available[:args.limit]])
        return 0
    except (ValueError, OSError, ET.ParseError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if index:
            index.close()


if __name__ == "__main__":
    raise SystemExit(main())
