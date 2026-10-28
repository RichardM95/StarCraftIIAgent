"""Scoped catalog resolver adapted from SC2EditorTool (MIT).

Copyright (c) 2026 RichardM. See vendor/sc2editortool/LICENSE.
Only catalog semantics are retained; IO, dependencies and publication belong to
StarCraftIIAgent. No Qt, database, cross-language fallback or external imports.
"""
from __future__ import annotations
import copy
import hashlib
import html
import json
import re
from collections import defaultdict, Counter, OrderedDict
from pathlib import Path
from xml.etree import ElementTree as ET

FAMILIES = ("HeroAbil", "HeroStat", "ArtifactSlot", "Artifact", "RequirementNode", "AchievementTerm", "ConversationState",
            "TargetFind", "TargetSort", "ScoreValue", "ScoreResult", "ItemClass",
            "ArmyCategory", "ArmyUnit", "ArmyUpgrade", "DataCollection", "AttachMethod",
            "Abil", "Unit", "Weapon", "Effect", "Behavior", "Actor", "Model",
            "Button", "Upgrade", "Requirement", "Validator", "Mover", "Turret",
            "Footprint", "Sound", "Camera", "Race", "Talent", "Hero", "Item",
            "Campaign", "Commander", "User", "Skin", "Achievement", "Accumulator",
            "Ping", "Tactical", "Kinetic", "Loot", "Reward", "Conversation",
            "Character", "BankCondition", "Config", "Texture", "GameUI")
LINKS = {"AbilArray": "Abil", "WeaponArray": "Weapon", "BehaviorArray": "Behavior",
         "EffectArray": "Effect", "PeriodicEffectArray": "Effect", "CaseDefault": "Effect",
         "InitialEffect": "Effect", "FinalEffect": "Effect", "ExpireEffect": "Effect",
         "ImpactEffect": "Effect", "LaunchEffect": "Effect", "Effect": "Effect",
         "DisplayEffect": "Effect", "EffectInitial": "Effect", "EffectFinal": "Effect",
         "EffectExpire": "Effect", "EffectPeriodic": "Effect", "EffectOn": "Effect",
         "EffectOff": "Effect", "Behavior": "Behavior", "BehaviorLink": "Behavior",
         "ValidatorArray": "Validator", "Validator": "Validator", "Validators": "Validator",
         "Unit": "Unit", "AmmoUnit": "Unit", "SpawnUnit": "Unit", "MorphUnit": "Unit",
         "Model": "Model", "Missile": "Actor", "Mover": "Mover", "Turret": "Turret",
         "Button": "Button", "DefaultButtonFace": "Button", "Face": "Button",
         "Requirement": "Requirement", "Requirements": "Requirement",
         "Footprint": "Footprint", "Actor": "Actor", "Sound": "Sound",
         "UpgradeArray": "Upgrade", "Upgrade": "Upgrade", "ArmyUnitArray": "ArmyUnit"}

# Explicit catalog base classes used by the supported generators. Unknown classes
# receive their exact defaults only; the source document remains fully available.
TYPE_BASES = {
    'CWeaponLegacy': 'CWeapon', 'CWeaponStrafe': 'CWeapon',
    **{ 'CEffect' + s: 'CEffect' for s in ('Damage', 'Set', 'Switch', 'CreatePersistent',
       'ApplyBehavior', 'RemoveBehavior', 'LaunchMissile', 'SearchArea', 'CreateUnit',
       'ModifyUnit', 'EnumArea', 'IssueOrder', 'DestroyPersistent')},
    **{ 'CAbil' + s: 'CAbil' for s in ('Train', 'WarpTrain', 'Build', 'Morph', 'Research',
       'EffectTarget', 'EffectInstant', 'Behavior', 'Merge', 'ArmMagazine', 'Attack', 'Move')},
    'CBehaviorBuff': 'CBehavior', 'CActorUnit': 'CActor', 'CActorMissile': 'CActor',
    'CActorAction': 'CActor', 'CActorModel': 'CActor',
}

def default_types(tag):
    result, seen = [], set()
    while tag and tag not in seen:
        seen.add(tag)
        result.insert(0, tag)
        tag = TYPE_BASES.get(tag)
    return result


SCHEMA_SHAPES = {}


def load_type_bases():
    schema = ET.parse(Path(__file__).with_name('schemas') / 'sc2-xsd' / 'Catalog.xsd')
    ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
    def shape(node, name):
        ext = node.find('xs:complexContent/xs:extension', ns)
        body = ext if ext is not None else node
        attrs = {a.get('name'): a.get('type', '') for a in body.findall('xs:attribute', ns)}
        children = {}
        for group in ('xs:choice', 'xs:sequence', 'xs:all'):
            for child in body.findall(group + '/xs:element', ns):
                cname = child.get('name')
                inline = child.find('xs:complexType', ns)
                ctype = child.get('type', '')
                if inline is not None:
                    ctype = name + '/' + cname
                    shape(inline, ctype)
                children[cname] = ctype
        SCHEMA_SHAPES[name] = (children, attrs, ext.get('base') if ext is not None else None)
    for node in schema.findall('xs:complexType', ns):
        shape(node, node.get('name'))
        ext = node.find('xs:complexContent/xs:extension', ns)
        # The generated schema flattens most catalog classes onto CBase; that
        # does not disprove the explicit runtime base-class defaults above.
        if ext is not None and node.get('name', '').startswith('C') and ext.get('base') != 'CBase':
            TYPE_BASES[node.get('name')] = ext.get('base')
load_type_bases()

def _cache_put(cache, key, value, limit=512):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


def family(tag):
    # Requirement expressions use CRequirementCountUnit/CRequirementAnd/etc.,
    # whereas only CRequirement itself belongs to the Requirement catalog.
    if tag.startswith('CRequirement') and tag != 'CRequirement':
        return 'RequirementNode'
    return next((f for f in sorted(FAMILIES, key=len, reverse=True) if tag.startswith("C" + f)), tag.removeprefix("C"))


def digest(value):
    hashed=hashlib.sha256()
    if isinstance(value,bytes):
        hashed.update(value)
    else:
        encoder=json.JSONEncoder(ensure_ascii=False,separators=(',',':'),sort_keys=True)
        for chunk in encoder.iterencode(value):
            hashed.update(chunk.encode('utf-8'))
    return hashed.hexdigest()



def encode_node(node):
    if node.tag is ET.ProcessingInstruction:
        return {'kind': 'processing_instruction', 'raw': '<?' + (node.text or '') + '?>'}
    if node.tag is ET.Comment:
        return {'kind': 'comment', 'raw': '<!--' + (node.text or '') + '-->'}
    children = []
    if node.text and node.text.strip():
        children.append({'kind': 'text', 'raw': html.escape(node.text)})
    children.extend(encode_node(c) for c in node)
    return {'@tag': node.tag, 'attributes': dict(node.attrib), 'children': children}


def render_node(node):
    if '@tag' not in node:
        return node.get('raw', '')
    attrs = ''.join(' ' + k + '="' + html.escape(str(v), quote=True) + '"' for k,v in node.get('attributes', {}).items())
    children = node.get('children', [])
    return '<' + node['@tag'] + attrs + ('>' + ''.join(render_node(c) for c in children) + '</' + node['@tag'] + '>' if children else '/>')


def semantic_node(node):
    """Comparable effective value, independent of formatting and object identity."""
    if node is None:
        return None
    return {'tag': node['@tag'], 'attributes': {k:v for k,v in node.get('attributes', {}).items()
            if k not in {'id', 'parent', 'default', 'removed'}},
            'children': [semantic_child(c) for c in elements(node)]}


def semantic_child(node):
    return {'tag': node['@tag'], 'attributes': dict(sorted(node.get('attributes', {}).items())),
            'children': [semantic_child(c) for c in elements(node)]}

def root_node(record):
    return next((n for n in record.get("nodes", []) if "@tag" in n), None)


def definitions(files):
    for file_index, record in enumerate(files):
        root = root_node(record)
        if not root or root["@tag"] != "Catalog":
            continue
        for ordinal, node in enumerate(root.get("children", [])):
            if "@tag" not in node or not node["@tag"].startswith("C"):
                continue
            attrs = node.get("attributes", {})
            yield {"family": family(node["@tag"]), "id": attrs.get("id"),
                   "tag": node["@tag"], "source_id": record["source_id"],
                   "file": record["path"], "file_index": file_index, "ordinal": ordinal,
                   "parent": attrs.get("parent"), "default": attrs.get("default") == "1",
                   "node": node}


def elements(node):
    return [n for n in node.get("children", []) if "@tag" in n]


def semantic_index(node):
    attrs = node.get('attributes', {})
    if 'index' in attrs:
        return attrs['index']
    if node['@tag'] in {'Fields', 'Instances'}:
        value = attrs.get('Id') or next((c['attributes'].get('value') for c in elements(node) if c['@tag'] == 'Id'), None)
        return value.removeprefix('[Override]') if value else None
    return next((c['attributes'].get('Id') for c in elements(node) if c['@tag'] == 'Field'), None)


def flatten(node):
    """Literal fields, including every attribute and array slot, never localized."""
    fields = {}
    def visit(parent, prefix):
        counters = defaultdict(int)
        tags = Counter(c["@tag"] for c in elements(parent))
        for c in elements(parent):
            tag, attrs = c["@tag"], c.get("attributes", {})
            index = semantic_index(c)
            array = index is not None or tag.endswith("Array") or tags[tag] > 1
            if array and index is None:
                index = str(counters[tag])
            counters[tag] = max(counters[tag] + 1, int(index) + 1) if index is not None and index.isdigit() else counters[tag] + 1
            segment = tag + ("|" + index if array else "")
            path = prefix + segment
            for key, value in attrs.items():
                if key == "index":
                    continue
                fields[path if key in {"value", "Value", "Link"} else path + "|@" + key] = value
            if not attrs and not elements(c):
                text = "".join(n.get("raw", "") for n in c.get("children", []) if n.get("kind") == "text")
                if text:
                    fields[path] = html.unescape(text)
            visit(c, path + "|")
    visit(node, "")
    return fields


def node_operations(node):
    fields = flatten(node)
    removed = []
    for path in list(fields):
        if path.endswith("|@removed") and fields[path] == "1":
            removed.append(path.removesuffix("|@removed"))
    return fields, removed


def indexed_overlay(base, overlay):
    """Implicit array entries append; explicit indices address existing slots.

    Canonical indices also drive provenance and reference traversal. Empty values
    occupy their slot; only removed=1 deletes a slot, never the entire array.
    """
    result = copy.deepcopy(overlay)
    base_groups, groups = defaultdict(list), defaultdict(list)
    for child in elements(base):
        base_groups[child['@tag']].append(child)
    for child in elements(result):
        groups[child['@tag']].append(child)
    for tag, children in groups.items():
        existing = base_groups[tag]
        is_array = tag.endswith('Array') or len(children) > 1 or len(existing) > 1 or any(
            semantic_index(c) is not None for c in children + existing)
        next_index = max((int(semantic_index(c)) + 1 for c in existing
                          if (semantic_index(c) or '').isdigit()), default=len(existing) if is_array else 0)
        slots = {semantic_index(c): c for c in existing}
        for child in children:
            idx = semantic_index(child)
            if is_array and idx is None:
                idx = str(next_index)
                child.setdefault('attributes', {})['index'] = idx
                child.pop('opening', None)
            if idx is not None and idx.isdigit():
                next_index = max(next_index, int(idx) + 1)
            old = slots.get(idx, {}) if is_array else (existing[0] if existing else {})
            prepared = indexed_overlay(old, child)
            child.clear()
            child.update(prepared)
    return result


def merge_node(base, overlay, *, _owned=False, _indexed=False):
    """Apply ordered field operations; arrays retain explicit and implicit slots."""
    result = base if _owned else copy.deepcopy(base)
    overlay = overlay if _indexed else indexed_overlay(result, overlay)
    result.setdefault("attributes", {}).update(overlay.get("attributes", {}))
    children = elements(result)
    def key_nodes(nodes):
        counters = defaultdict(int)
        grouped = defaultdict(list)
        for n in nodes:
            grouped[n["@tag"]].append(n)
        output = []
        for n in nodes:
            tag, attrs = n["@tag"], n.get("attributes", {})
            idx = semantic_index(n)
            array = idx is not None or tag.endswith("Array") or len(grouped[tag]) > 1
            idx = idx if idx is not None else str(counters[tag]) if array else None
            counters[tag] = max(counters[tag] + 1, int(idx) + 1) if idx is not None and idx.isdigit() else counters[tag] + 1
            output.append(((tag, idx), n))
        return output
    ordered = dict(key_nodes(children))
    for key, child in key_nodes(elements(overlay)):
        attrs = child.get("attributes", {})
        if attrs.get("removed") == "1":
            ordered.pop(key, None)
        elif key in ordered:
            ordered[key] = merge_node(ordered[key], child, _owned=True, _indexed=True)
            ordered[key].get("attributes", {}).pop("removed", None)
        else:
            ordered[key] = copy.deepcopy(child)
    result["children"] = list(ordered.values())
    result["self_closing"] = not result["children"]
    result.pop("opening", None)
    result.pop("closing", None)
    return result


def tokens_from(node):
    values = dict(node.get("attributes", {}))
    for c in node.get("children", []):
        if c.get("kind") == "processing_instruction" and c.get("raw", "").startswith("<?token"):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', c["raw"]))
            if "id" in attrs and "value" in attrs:
                values[attrs["id"]] = attrs["value"]
    return values


class Catalog:
    def __init__(self, sources, files, locale="zhCN", diagnostics=()):
        self.sources, self.files, self.locale = sources, files, locale
        self.diagnostics = list(diagnostics) + [dict(d, source_id=d.get('source_id', s['id']))
                                              for s in sources for d in s.get("diagnostics", [])]
        self.objects = defaultdict(list)
        self.defaults = defaultdict(list)
        self._resolved, self._provenance = OrderedDict(), OrderedDict()
        self._effective, self._relations = OrderedDict(), OrderedDict()
        self.texts = {}
        self.text_sources = {}
        self.constants = {}
        for record in files:
            root = root_node(record)
            if root:
                for n in elements(root):
                    attrs = n.get("attributes", {})
                    if n["@tag"] == "const" and "id" in attrs and "value" in attrs:
                        self.constants[attrs["id"]] = attrs["value"]
        self.definitions = list(definitions(files))
        for d in self.definitions:
            if d["id"]:
                self.objects[(d["family"], d["id"])].append(d)
            elif d["default"]:
                self.defaults[d["tag"]].append(d)
        for (fam, oid), defs in self.objects.items():
            counts = Counter(d['source_id'] for d in defs)
            for sid, count in counts.items():
                if count > 1:
                    self.diagnostics.append({'code': 'duplicate_definition', 'family': fam, 'id': oid,
                                             'source_id': sid, 'count': count})
        self.build_id = digest([(s["id"], s["fingerprint"]) for s in sources])

    @property
    def status(self):
        return "partial" if self.diagnostics else "complete"

    def resolve(self, fam, object_id, stack=()):
        key = fam, object_id
        if key in self._resolved:
            return self._resolved[key]
        if key in stack:
            self.diagnostics.append({"code": "inheritance_cycle", "family": fam, "id": object_id})
            return None
        defs = self.objects.get(key)
        if not defs:
            if stack:
                self.diagnostics.append({"code": "missing_parent", "family": fam, "id": object_id})
            return None
        parent = next((d["parent"] for d in reversed(defs) if d["parent"] is not None), None)
        subtype = defs[-1]["tag"]
        if subtype not in TYPE_BASES and subtype != 'C' + fam and 'C' + fam in self.defaults:
            self.diagnostics.append({'code': 'unverified_type_defaults', 'family': fam, 'id': object_id, 'type': subtype})
        result = {"@tag": subtype, "attributes": {}, "children": []}
        provenance, tokens = {}, {}
        for tag in default_types(subtype):
            if tag in self.defaults:
                for d in self.defaults[tag]:
                    applied = indexed_overlay(result, d['node'])
                    result = merge_node(result, applied, _owned=True, _indexed=True)
                    tokens.update(tokens_from(d["node"]))
                    provenance.update({p: {k: d[k] for k in ("source_id", "file", "ordinal")} for p in flatten(applied)})
        if parent:
            base = self.resolve(fam, parent, stack + (key,))
            if base:
                result = merge_node(result, base, _owned=True)
                tokens.update(base.get("_tokens", {}))
                provenance.update(self._provenance.get((fam, parent), {}))
        for d in defs:
            applied = indexed_overlay(result, d['node'])
            result = merge_node(result, applied, _owned=True, _indexed=True)
            tokens.update(tokens_from(d["node"]))
            fields, removed = node_operations(applied)
            for r in removed:
                provenance = {p: v for p, v in provenance.items() if p != r and not p.startswith(r + "|")}
            provenance.update({p: {k: d[k] for k in ("source_id", "file", "ordinal")} for p in fields if not p.endswith("|@removed")})
        result["@tag"] = subtype
        result['attributes'].pop('default', None)
        result['attributes'].pop('removed', None)
        result["attributes"]["id"] = object_id
        if parent:
            result["attributes"]["parent"] = parent
        result["_tokens"] = tokens
        _cache_put(self._resolved, key, result)
        _cache_put(self._provenance, key, provenance)
        return result

    def effective(self, fam, object_id):
        return copy.deepcopy(self._effective_node(fam, object_id))

    def _effective_node(self, fam, object_id):
        """Internal borrowed view; public callers receive an independent copy."""
        key = fam, object_id
        if key in self._effective:
            self._effective.move_to_end(key)
            return self._effective[key]
        node = self.resolve(fam, object_id)
        if not node:
            return None
        node = copy.deepcopy(node)
        tokens = {**node.pop("_tokens", {}), "id": object_id}
        def expand(n):
            for key, value in n.get("attributes", {}).items():
                for _ in range(len(tokens) + 1):
                    new = re.sub(r"##(\w+)##", lambda m: tokens.get(m[1], m[0]), value)
                    if new == value:
                        break
                    value = new
                if value in self.constants:
                    seen = set()
                    while value in self.constants and value not in seen:
                        seen.add(value)
                        value = self.constants[value]
                n["attributes"][key] = value
                if "##" in value:
                    self.diagnostics.append({"code": "unresolved_token", "family": fam, "id": object_id, "value": value})
            for c in elements(n):
                expand(c)
        expand(node)
        for path, value in flatten(node).items():
            if path.split("|")[-1] in {"Amount", "LifeMax", "LifeStart", "ShieldsMax", "ShieldsStart", "EnergyMax", "EnergyStart", "Range", "Period", "ArmorReduction", "Speed"}:
                try:
                    float(value)
                except (ValueError, TypeError):
                    self.diagnostics.append({"code": "unresolved_expression", "family": fam, "id": object_id, "field": path, "value": value})
        _cache_put(self._effective, key, node)
        return node

    def explain_field(self, fam, object_id, path):
        self.resolve(fam, object_id)
        node = self._effective_node(fam, object_id)
        return {"value": flatten(node).get(path) if node else None,
                "source": self._provenance.get((fam, object_id), {}).get(path),
                "status": self.status}

    def explain_fields(self, fam, object_id):
        """Bulk field evidence for inspectors; independent of source editing."""
        self.resolve(fam, object_id)
        fields = flatten(self._effective_node(fam, object_id)) if (fam, object_id) in self.objects else {}
        provenance = self._provenance.get((fam, object_id), {})
        return {path: {"value": value, "source": copy.deepcopy(provenance.get(path))}
                for path, value in fields.items()}

