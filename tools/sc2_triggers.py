"""Source-backed trigger lookup. Reference membership never grants target access."""
from __future__ import annotations

import json
import hashlib
import os
import secrets
import sqlite3
import tempfile
import zlib
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from sc2_catalog_inputs import file_digest, inventory
from sc2_dependencies import build_dependency_graph, dependency_problems

VERSION = 2
SEARCH_TYPES = {"FunctionDef", "Trigger", "Preset", "PresetValue", "ParamDef", "SubFuncType", "Variable"}
RESOURCE_TAGS = {"ValueUnit", "ValuePoint", "ValueRegion", "ValueDoodad", "ValueCamera", "ValueObject", "ValueId"}


def child_path(root: Path, relative: str) -> Path:
    """Resolve extract casing portably; reject references outside the component."""
    relative = relative.replace("\\", "/")
    candidate = root.joinpath(*relative.split("/")).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes component: {relative}")
    current = root
    for part in Path(relative).parts:
        if current.is_dir():
            matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous casing: {current / part}")
            current = matches[0] if matches else current / part
        else:
            current = current / part
    return current


def component_of(path: Path) -> Path:
    for p in (path.parent, *path.parents):
        if p.suffix.casefold() in {".sc2map", ".sc2mod", ".sc2campaign"}:
            return p
    raise ValueError(f"No SC2 component owns {path}")


def source_inputs(roots: list[Path]) -> list[Path]:
    files = set()
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"Reference root missing: {root}")
        for directory, dirs, names in os.walk(root):
            dirs[:] = [n for n in dirs if not n.casefold().endswith(".sc2assets")
                       and not Path(n).suffix.casefold().startswith(".storm")
                       and n.casefold() not in {"gamedata", "assets", "ui", ".git"}]
            for name in names:
                p = Path(directory) / name
                if any(x.suffix.casefold().startswith(".storm") for x in p.parents):
                    continue
                if (p.name.casefold() in {"triggers", "librarylist.xml", "triggerstrings.txt", "gamestrings.txt", "documentinfo",
                                     "documentheader", "componentlist.sc2components", "mapscript.galaxy"}
                    or p.suffix.casefold() in {".sc2lib", ".triggerlib"}):
                    try:
                        component_of(p)
                    except ValueError:
                        continue
                    files.add(p.resolve())
    return sorted(files, key=lambda p: str(p).casefold())


def localized_strings(component: Path) -> dict[str, dict[str, str]]:
    result = {}
    for locale in ("zhCN.SC2Data", "enUS.SC2Data"):
        p = child_path(component, locale + "/LocalizedData/TriggerStrings.txt")
        if p.is_file():
            values = result.setdefault(locale.split('.')[0], {})
            for line in p.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = value
    return result


def trigger_strings(component: Path) -> dict[str, str]:
    names = localized_strings(component)
    return names.get('zhCN', {}) | names.get('enUS', {})


class Document:
    def __init__(self, path: Path, raw: bytes | None = None, names: dict | None = None,
                 localized_names: dict | None = None):
        self.path = path.resolve()
        self.component = component_of(path)
        raw = raw if raw is not None else path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.root = ET.fromstring(raw)
        self.localized_names = localized_strings(self.component) if localized_names is None else localized_names
        self.names = (self.localized_names.get('zhCN', {}) | self.localized_names.get('enUS', {})
                      if names is None else names)
        self.elements = {}
        self.duplicates = []
        self.libraries = set()
        standard = self.root.find("Standard")
        self.standard = standard.get("Id", "") if standard is not None else ""
        containers = [(self.root, self.standard)] + [(e, e.get("Id", "")) for e in self.root.findall("Library")]
        for container, library in containers:
            if library:
                self.libraries.add(library)
            for e in container.findall("Element"):
                key = (library, e.get("Type", ""), e.get("Id", ""))
                if key in self.elements:
                    self.duplicates.append(key)
                self.elements[key] = e

    def name(self, key: tuple) -> str:
        library, typ, ident = key
        e = self.elements[key]
        string_key = f"{typ}/Name/" + (f"lib_{library}_" if library else "") + ident
        return e.findtext("Identifier") or self.names.get(string_key) or self.names.get(f"{typ}/Name/{ident}", "")

    def aliases(self, key: tuple) -> dict[str, str]:
        library, typ, ident = key
        result = {}
        identifier = self.elements[key].findtext('Identifier')
        if identifier:
            result['identifier'] = identifier
        for anchor in (f"{typ}/Name/{ident}", f"{typ}/Name/lib_{library}_{ident}"):
            for locale, values in self.localized_names.items():
                if anchor in values:
                    result[locale] = values[anchor]
        return result

    def matches(self, key: tuple, term: str) -> bool:
        return any(term.casefold() in value.casefold() for value in [self.name(key), *self.aliases(key).values()])


def ref_key(e: ET.Element, owner: tuple) -> tuple:
    return e.get("Library", owner[0]), e.get("Type", ""), e.get("Id", "")


def references(element: ET.Element, owner: tuple):
    for e in element.iter():
        if e is not element and e.tag != "Element" and e.get("Type") and e.get("Id"):
            yield ref_key(e, owner)


def xml(e: ET.Element) -> str:
    return ET.tostring(e, encoding="unicode")


def registered_files(component: Path) -> tuple[list[Path], list[str]]:
    files, problems = [], []
    listing = child_path(component, "ComponentList.SC2Components")
    if listing.is_file():
        tree = ET.parse(listing).getroot()
        if any(e.get('Type') == 'trig' and not (e.text or '').strip() for e in tree.findall('DataComponent')):
            problems.append(f"{listing}: empty trigger component registration")
        files.extend(child_path(component, e.text.strip()) for e in tree.findall("DataComponent")
                     if e.get("Type") == "trig" and e.text)
    elif (component / "Triggers").is_file():
        files.append(component / "Triggers")
    liblist = child_path(component, "Base.SC2Data/TriggerLibs/LibraryList.xml")
    if not listing.is_file() and not files and not liblist.is_file():
        problems.append(f"{component}: missing trigger registration metadata; absence cannot be confirmed")
    if liblist.is_file():
        for e in ET.parse(liblist).getroot():
            external = e.get("external")
            if external:
                stem = "Base.SC2Data/" + external
                options = [child_path(component, stem + ext) for ext in (".SC2Lib", ".TriggerLib")]
                found = [p for p in options if p.is_file()]
                if len(found) != 1:
                    problems.append(f"{liblist}: missing or ambiguous registered library {external}")
                else:
                    files.append(found[0])
            elif e.tag.casefold() == "library":
                problems.append(f"{liblist}: unsupported inline library registration {e.attrib}")
    for p in files:
        if not p.is_file():
            problems.append(f"{component}: missing registered trigger source {p}")
    return list(dict.fromkeys(p for p in files if p.is_file())), problems


class Target:
    def __init__(self, path: Path, mods: Path, campaigns: Path | None):
        self.path = path.resolve()
        if not self.path.is_dir() or self.path.suffix.casefold() not in {".sc2mod", ".sc2map", ".sc2campaign"}:
            raise ValueError(f"Not a Components target: {path}")
        self.graph = build_dependency_graph(self.path, mods, campaigns_dir=campaigns,
                                            allow_unpacked=True, strict_external=True)
        self.problems = dependency_problems(self.graph)
        self.documents = []
        self.providers = defaultdict(list)
        self.routes = {str(self.path).casefold(): [str(self.path)]}
        pending = deque([self.graph["primary"]])
        while pending:
            source = pending.popleft()
            for e in self.graph["edges"]:
                if e["source"] == source and e.get("exists") and e["target"] not in self.routes:
                    self.routes[e["target"]] = self.routes[source] + [e["target_path"]]
                    pending.append(e["target"])
        for node in self.graph["nodes"].values():
            component = Path(node["path"])
            try:
                files, errors = registered_files(component)
                self.problems.extend(errors)
                for p in files:
                    d = Document(p)
                    self.documents.append(d)
                    if "Ntve" in d.libraries and (d.component.name.casefold() != "core.sc2mod"
                            or d.path != child_path(d.component, "Base.SC2Data/TriggerLibs/NativeLib.TriggerLib")):
                        self.problems.append(f"{p}: Ntve requires the registered Core NativeLib source, not a local namespace substitute")
                    self.problems.extend(f"{p}: duplicate element {k}" for k in d.duplicates)
                    for key, element in d.elements.items():
                        # Map-local empty-library references are scoped to their document.
                        scope = str(d.path) if not key[0] else ""
                        self.providers[(scope, *key)].append((d, element))
            except (ValueError, OSError, ET.ParseError) as exc:
                self.problems.append(f"{component}: {exc}")
        for key, providers in self.providers.items():
            if len(providers) > 1:
                self.problems.append(f"Ambiguous definition {key}: " + ", ".join(str(d.path) for d, _ in providers))
        self.input_candidates = {d.path for d in self.documents}
        for node in self.graph["nodes"].values():
            component = Path(node["path"])
            for relative in ("ComponentList.SC2Components", node.get("info_component") or "DocumentInfo",
                             "Base.SC2Data/TriggerLibs/LibraryList.xml",
                             "enUS.SC2Data/LocalizedData/TriggerStrings.txt", "zhCN.SC2Data/LocalizedData/TriggerStrings.txt"):
                self.input_candidates.add(child_path(component, relative))
        self.inputs = inventory(sorted(p for p in self.input_candidates if p.is_file()))
        for d in self.documents:
            if self.inputs[d.path.as_posix()]["sha256"] != d.sha256:
                self.problems.append(f"Target source changed while loading: {d.path}")

    def refresh(self):
        current = inventory(sorted(p for p in self.input_candidates if p.is_file()))
        if current != self.inputs and "Target inputs changed; rerun the query" not in self.problems:
            self.problems.append("Target inputs changed; rerun the query")

    def resolve(self, key: tuple, document: Document) -> tuple[Document, ET.Element]:
        scope = str(document.path) if not key[0] else ""
        providers = self.providers.get((scope, *key), [])
        if len(providers) != 1:
            raise ValueError(f"{'ambiguous' if providers else 'missing/unloaded'} {':'.join(key)} from {document.path}")
        return providers[0]

    def libraries(self) -> dict:
        self.refresh()
        return {"target": str(self.path), "status": "unconfirmed" if self.problems else "confirmed",
                "problems": self.problems,
                "libraries": [{"library": lib, "source": str(d.path), "sha256": d.sha256,
                               "source_class": "target_local" if d.component == self.path else "active_dependency",
                               "dependency_path": self.routes.get(str(d.component).casefold(), [])}
                              for d in self.documents for lib in sorted(d.libraries)]}


def validate_call(element: ET.Element, key: tuple, d: Document, resolve) -> list[str]:
    problems = []
    definition_ref = element.find("FunctionDef")
    if definition_ref is None:
        return ["FunctionCall has no FunctionDef"]
    fd, definition = resolve(ref_key(definition_ref, key), d)
    expected = [ref_key(e, ref_key(definition_ref, key)) for e in definition.findall("Parameter")]
    actual = []
    for p in element.findall("Parameter"):
        pd, param = resolve(ref_key(p, key), d)
        binding = param.find("ParameterDef")
        if binding is None:
            problems.append(f"Param {p.get('Id')} has no ParameterDef")
        else:
            bound_key = ref_key(binding, ref_key(p, key))
            actual.append(bound_key)
            bd, bound = resolve(bound_key, pd)
            declared = bound.find("ParameterType/Type")
            literal = param.find("ValueType")
            expected_type = declared.get("Value") if declared is not None else None
            if literal is not None and literal.get("Type") == "difficulty" and param.find("ValueId") is None:
                problems.append(f"Param {p.get('Id')} difficulty literal requires ValueId")
            if (literal is not None and expected_type in {"int", "fixed", "bool", "string", "text", "gamelink", "difficulty", "filepath"}
                    and literal.get("Type") != expected_type
                    and not (expected_type == "fixed" and literal.get("Type") == "int")):
                problems.append(f"Param {p.get('Id')} type: expected {expected_type}, got {literal.get('Type')}")
            if literal is not None and literal.get("Type") == "gamelink":
                game_type = param.find("ValueGameType")
                expected_game = bound.find("ParameterType/GameType")
                if game_type is None or (expected_game is not None and game_type.get("Type") != expected_game.get("Value")):
                    problems.append(f"Param {p.get('Id')} missing/mismatched ValueGameType")
            preset_type = bound.find("ParameterType/TypeElement")
            preset_value = param.find("Preset")
            if preset_type is not None and preset_value is not None and preset_type.get("Type") == "Preset":
                sd, group = resolve(ref_key(preset_type, bound_key), bd)
                allowed_values = [ref_key(r, ref_key(preset_type, bound_key)) for r in group.findall("Item")]
                if ref_key(preset_value, ref_key(p, key)) not in allowed_values:
                    problems.append(f"Param {p.get('Id')} preset is not in its declared preset type")
            # Explicit values still required even when ParamDef has a Default.
            if not any(c.tag not in {"ParameterDef", "Comment"} for c in param):
                problems.append(f"Param {p.get('Id')} has no value")
    # GUI calls bind by ParameterDef, not XML sibling order. Official maps
    # routinely serialize these references in a different order than the signature.
    if Counter(expected) != Counter(actual):
        # Repeated parameters are explicitly flagged by their definition.
        counts = []
        for k in expected:
            _, paramdef = resolve(k, fd)
            counts.append(paramdef.find("ParamFlagMultiple") is not None)
        if not any(counts):
            problems.append(f"parameter ownership/coverage: expected {expected}, got {actual}")
        elif (any(k not in expected for k in actual) or any(k not in actual for k in expected)
              or any(not multiple and actual.count(k) != expected.count(k) for k, multiple in zip(expected, counts))):
            problems.append(f"variadic parameter ownership: expected {expected}, got {actual}")
    allowed = [ref_key(e, ref_key(definition_ref, key)) for e in definition.findall("SubFunctionType")]
    for c in element.findall("FunctionCall"):
        cd, child = resolve(ref_key(c, key), d)
        subtype = child.find("SubFunctionType")
        if subtype is None or ref_key(subtype, ref_key(c, key)) not in allowed:
            problems.append(f"child {c.get('Id')} has an invalid SubFunctionType")
    return problems


def walk(start: list[tuple[Document, tuple]], resolve, *, validate: bool = True,
         node_limit: int | None = None) -> dict:
    """Follow referenced GUI bodies, parameter defaults and variables with cycle protection."""
    pending = deque((d, k, [f"{d.path.name}:{':'.join(k)}"], True) for d, k in start)
    seen, recorded, errors, nodes, resources = set(), set(), [], [], []
    resource_count, libraries, external_libraries = 0, set(), set()
    start_paths = {d.path for d, _ in start}
    resolve = lru_cache(maxsize=4096)(resolve)
    while pending:
        d, key, chain, executable = pending.popleft()
        marker = (str(d.path), key, executable)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            owner, element = resolve(key, d)
            if validate and key[1] == "Trigger" and element.find("Event") is not None and element.find("Action") is None:
                errors.append(" -> ".join(chain) + ": event trigger has no action")
            if validate and executable and key[1] == "FunctionCall":
                errors.extend(" -> ".join(chain) + ": " + p for p in validate_call(element, key, owner, resolve))
        except ValueError as exc:
            errors.append(" -> ".join(chain) + ": " + str(exc))
            continue
        unique = (str(owner.path), key)
        if unique not in recorded:
            recorded.add(unique)
            if key[0]:
                libraries.add(key[0])
                if owner.path not in start_paths:
                    external_libraries.add(key[0])
            if node_limit is None or len(nodes) < node_limit:
                nodes.append({"source": str(owner.path), "component": str(owner.component),
                          "library": key[0], "type": key[1], "id": key[2],
                          "name": owner.name(key), "references": [list(r) for r in references(element, key)]})
            for e in element.iter():
                if e.tag in RESOURCE_TAGS or e.tag in {"ValueGameType", "Value", "ValueType"}:
                    resource_count += 1
                    if node_limit is None or len(resources) < node_limit:
                        resources.append({"source": str(owner.path), "owner": list(key), "xml": xml(e)})
        for ref in element.iter():
            if ref is element or ref.tag == "Element" or not ref.get("Type") or not ref.get("Id"):
                continue
            r = ref_key(ref, key)
            # Labels only control editor grouping, not callable definitions.
            if r[1] == "Label":
                continue
            # Defaults are definition metadata, not implicitly executed GUI calls.
            # Resolve their references, but lint the caller's explicit argument tree.
            pending.append((owner, r, chain + [": ".join(r)], executable and ref.tag != "Default"))
    return {"errors": list(dict.fromkeys(errors)), "nodes": nodes, "resources": resources,
            "total_nodes": len(recorded), "total_resources": resource_count,
            "required_libraries": sorted(libraries), "external_libraries": sorted(external_libraries),
            "truncated": len(nodes) < len(recorded) or len(resources) < resource_count}


def check(target: Target) -> dict:
    target.refresh()
    starts = [(d, k) for d in target.documents if d.component == target.path
              for k in d.elements if k[1] in {"Trigger", "FunctionDef", "Variable", "Preset", "FunctionCall"}]
    result = walk(starts, target.resolve)
    target.refresh()
    result["errors"] = target.problems + result["errors"]
    result["status"] = "failed" if result["errors"] else ("not_applicable" if not starts else "static validation passed")
    if result["status"] == "not_applicable":
        result["note"] = "No checkable GUI definitions in the target; dependency registration and metadata confirmed"
    result["target"] = str(target.path)
    return result


def build_index(db: Path, roots: list[Path]) -> dict:
    files = source_inputs(roots)
    before = inventory(files)
    db.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(prefix=".trigger-index-", dir=db.parent, delete=False)
    stage = Path(temporary.name)
    temporary.close()
    counts = {"documents": 0, "Triggers": 0, "definitions": 0}
    try:
        with closing(sqlite3.connect(stage)) as connection, connection:
            connection.executescript("""
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE documents (path TEXT PRIMARY KEY, component TEXT, raw BLOB, names TEXT);
                CREATE TABLE elements (source TEXT, library TEXT, type TEXT, id TEXT, name TEXT, names TEXT, search_name TEXT);
                CREATE INDEX element_ref ON elements(library,type,id);
                CREATE INDEX element_name ON elements(type,name);
            """)
            for p in files:
                if p.name.casefold() != "triggers" and p.suffix.casefold() not in {".sc2lib", ".triggerlib"}:
                    continue
                raw = p.read_bytes()
                d = Document(p, raw)
                if d.duplicates:
                    raise ValueError(f"{p}: duplicate definitions: {d.duplicates[:5]}")
                connection.execute("INSERT INTO documents VALUES (?,?,?,?)",
                                   (str(p), str(d.component), zlib.compress(raw), json.dumps(d.localized_names, ensure_ascii=False)))
                connection.executemany("INSERT INTO elements VALUES (?,?,?,?,?,?,?)",
                                       [(str(p), *key, d.name(key), json.dumps(d.aliases(key), ensure_ascii=False),
                                         '\n'.join([d.name(key), *d.aliases(key).values()]).casefold())
                                        for key in d.elements if key[1] in SEARCH_TYPES])
                counts["documents"] += 1
                counts["Triggers"] += p.name.casefold() == "triggers"
                counts["definitions"] += sum(k[1] == "FunctionDef" for k in d.elements)
            if before != inventory(source_inputs(roots)):
                raise ValueError("Sources changed during build; previous index retained")
            metadata = {"version": VERSION, "roots": [str(p.resolve()) for p in roots], "inputs": before, "counts": counts}
            connection.executemany("INSERT INTO meta VALUES (?,?)", [(k, json.dumps(v)) for k, v in metadata.items()])
        stage.replace(db)
    finally:
        stage.unlink(missing_ok=True)
    return {"db": str(db), **counts}


class Index:
    def __init__(self, db: Path, verify_hashes: bool = False):
        if not db.is_file():
            raise ValueError(f"Trigger index missing: {db}; run build")
        self.connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.cache = {}
        self.provider_cache = {}
        self.parsed_documents = 0
        try:
            self.meta = {row["key"]: json.loads(row["value"]) for row in self.connection.execute("SELECT * FROM meta")}
            if self.meta.get("version") != VERSION:
                raise ValueError("Unsupported trigger index; rebuild")
            current = source_inputs([Path(r) for r in self.meta["roots"]])
            previous = self.meta["inputs"]
            if set(str(p.as_posix()) for p in current) != set(previous):
                raise ValueError("Trigger index stale: input membership changed; rebuild")
            for p in current:
                old = previous[p.as_posix()]
                stat = p.stat()
                if (stat.st_size != old["size"] or stat.st_mtime_ns != old["mtime_ns"]
                        or (verify_hashes and file_digest(p) != old["sha256"])):
                    raise ValueError(f"Trigger index stale: {p}; rebuild")
        except Exception:
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def document(self, source: str) -> Document:
        if source not in self.cache:
            row = self.connection.execute("SELECT * FROM documents WHERE path=?", (source,)).fetchone()
            if row is None:
                raise ValueError(f"Not indexed: {source}")
            # Bound parsed XML memory while querying the full official campaign.
            if len(self.cache) >= 8:
                self.cache.pop(next(iter(self.cache)))
            names = json.loads(row['names'])
            self.cache[source] = Document(Path(source), zlib.decompress(row["raw"]), localized_names=names)
            self.parsed_documents += 1
        return self.cache[source]

    def resolve(self, key: tuple, d: Document) -> tuple[Document, ET.Element]:
        if key in d.elements:
            return d, d.elements[key]
        if not key[0]:
            raise ValueError(f"Missing map-local {key} in {d.path}")
        if key in self.provider_cache:
            candidate = self.document(self.provider_cache[key])
            return candidate, candidate.elements[key]
        rows = self.connection.execute("SELECT DISTINCT source FROM elements WHERE library=? AND type=? AND id=?", key).fetchall()
        # Non-searchable references (Param/FunctionCall) belong to their GUI library file.
        if not rows:
            rows = self.connection.execute("SELECT DISTINCT source FROM elements WHERE library=? AND type='FunctionDef'", (key[0],)).fetchall()
        found = []
        for row in rows:
            candidate = self.document(row["source"])
            if key in candidate.elements:
                found.append((candidate, candidate.elements[key]))
        if len(found) != 1:
            raise ValueError(f"{'Ambiguous' if found else 'Missing'} reference {key}; provider component required")
        self.provider_cache[key] = str(found[0][0].path)
        return found[0]


def describe(d: Document, key: tuple, resolve) -> dict:
    element = d.elements[key]
    details = {"source": str(d.path), "component": str(d.component), "library": key[0],
               "type": key[1], "id": key[2], "name": d.name(key), "names": d.aliases(key), "xml": xml(element),
               "flags": [e.tag for e in element if e.tag.startswith("Flag")],
               "return_type": xml(element.find("ReturnType")) if element.find("ReturnType") is not None else None,
               "sha256": d.sha256, "parameters": [], "subfunctions": [], "presets": [], "errors": []}
    for tag, output in (("Parameter", "parameters"), ("SubFunctionType", "subfunctions"), ("Item", "presets")):
        for ref in element.findall(tag):
            if not ref.get("Type"):
                continue
            try:
                owner, e = resolve(ref_key(ref, key), d)
                item = {"reference": list(ref_key(ref, key)), "source": str(owner.path), "xml": xml(e)}
                default = e.find("Default")
                if default is not None:
                    dd, value = resolve(ref_key(default, ref_key(ref, key)), owner)
                    item["default"] = {"source": str(dd.path), "xml": xml(value)}
                item["type_definitions"] = []
                for typed in e.findall("ParameterType/TypeElement"):
                    td, te = resolve(ref_key(typed, ref_key(ref, key)), owner)
                    type_item = {"reference": list(ref_key(typed, ref_key(ref, key))),
                                 "source": str(td.path), "xml": xml(te), "values": []}
                    for member in te.findall("Item"):
                        vd, ve = resolve(ref_key(member, ref_key(typed, ref_key(ref, key))), td)
                        type_item["values"].append({"source": str(vd.path), "xml": xml(ve)})
                    item["type_definitions"].append(type_item)
                details[output].append(item)
            except ValueError as exc:
                details["errors"].append(str(exc))
    return details


def remap_local_ids(raw: bytes, strings: dict[str, str], occupied: set[str]) -> tuple[bytes, dict[str, str]]:
    """Pure migration helper for map-local fragments; also remap localized text anchors."""
    root = ET.fromstring(raw)
    if root.find("Standard") is not None or root.find("Library") is not None:
        raise ValueError("This helper accepts map-local fragments; library migration requires explicit ownership")
    identifiers = {e.get("Id") for e in root.findall("Element")}
    anchors = {k.rsplit("/", 1)[-1] for k in strings}
    mapping = {}
    used = set(occupied) | identifiers | anchors
    for old in sorted(identifiers | anchors):
        while True:
            fresh = secrets.token_hex(4).upper()
            if fresh not in used:
                break
        mapping[old] = fresh
        used.add(fresh)
    for e in root.iter():
        if e.get("Id") in mapping and not e.get("Library"):
            e.set("Id", mapping[e.get("Id")])
        if e.tag == "Value" and e.text in strings:
            prefix, old = e.text.rsplit("/", 1)
            e.text = prefix + "/" + mapping[old]
    new_strings = {k.rsplit("/", 1)[0] + "/" + mapping[k.rsplit("/", 1)[-1]]: v for k, v in strings.items()}
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), new_strings


def validate_templates(index: Index, directory: Path, target: Target | None = None) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    template = Document(directory / "GuiPatterns.SC2Map/Triggers")
    rows = index.connection.execute("SELECT DISTINCT source FROM elements WHERE library='Ntve' AND type='FunctionDef'").fetchall()
    native = [index.document(r["source"]) for r in rows
              if Path(r["source"]).as_posix().casefold().endswith(manifest["native_source"].casefold())]
    if len(native) != 1 or file_digest(native[0].path) != manifest["native_sha256"]:
        raise ValueError("Template native source changed/missing; revalidate definitions and templates")
    game = {}
    p = template.component / "enUS.SC2Data/LocalizedData/GameStrings.txt"
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            game[k] = v
    errors = [f"Duplicate template {key}" for key in template.duplicates]
    for key, e in template.elements.items():
        if key[1] in {"Trigger", "Variable", "ParamDef", "FunctionDef"} and not template.name(key):
            errors.append(f"Missing template display name: {key}")
        for value in e.findall("Value"):
            if value.text and value.text.startswith("Param/Value/") and value.text not in game:
                errors.append(f"Missing template GameStrings: {value.text}")
    def resolve(key, owner):
        if owner.path == template.path and key in template.elements:
            return template, template.elements[key]
        return index.resolve(key, owner)
    patterns = {}
    for name, record in manifest["patterns"].items():
        result = walk([(template, ("", "Trigger", ident)) for ident in record["triggers"]], resolve)
        patterns[name] = {"status": "failed" if result["errors"] else "static validation passed",
                          "errors": result["errors"], "elements": len(result["nodes"]),
                          "required_libraries": sorted({n["library"] for n in result["nodes"] if n["library"]})}
        errors.extend(result["errors"])
        if target is not None:
            def active(k, owner):
                if owner.path == template.path and k in template.elements:
                    return template, template.elements[k]
                return target.resolve(k, owner)
            compatibility = walk([(template, ("", "Trigger", ident)) for ident in record["triggers"]], active)
            target.refresh()
            patterns[name]["target_errors"] = target.problems + compatibility["errors"]
            errors.extend(patterns[name]["target_errors"])
    return {"status": "failed" if errors else "static validation passed", "errors": errors, "patterns": patterns,
            "purpose": "GUI fragment structure; map resources and Editor/runtime behavior remain unverified"}
