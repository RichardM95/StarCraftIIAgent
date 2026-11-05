"""Project-aware, read-only talent discovery and spreadsheet export."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from sc2_components import component_path, component_session
from sc2_dependencies import build_dependency_graph, resolve_dependency_root
from sc2_migrate import ComponentLoader
from sc2_migrate_catalog import Catalog, elements, flatten
from sc2_paths import find_project_mods, load_project_config, project_data_dir
from sc2_talent_text import plain_text, render_description
from sc2_triggers import Document, registered_files, ref_key

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"name": "Name", "name_key": "NameStr", "description": "Description",
         "rarity": "Rarity", "category": "Type", "class": "Class", "max": "Max",
         "upgrade": "Upgrade", "icon": "Image", "banned": "Banned", "requirement": "Requirement"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def field_values(instance):
    result = {}
    for node in elements(instance):
        field = next((c["attributes"].get("Id") for c in elements(node) if c["@tag"] == "Field"), None)
        if field:
            index = node["attributes"].get("Index", node["attributes"].get("index", "0"))
            result[f"{field}[{index}]"] = node["attributes"].get(node["@tag"], "")
    return result


class Study:
    def __init__(self, mod, mods_dir):
        self.mod = mod
        self.graph = build_dependency_graph(mod, mods_dir, allow_unpacked=True)
        self.problems = []
        self.inputs = []
        self.texts = {}
        self.documents = []
        self.files = []
        sources = []
        loader = ComponentLoader()
        for problem in self.graph["errors"] + self.graph.get("official_problems", []):
            self.issue("dependency", problem)
        for missing in self.graph["missing"]:
            self.issue("missing_dependency", missing)
        if self.graph["loading_order"]["status"] != "confirmed":
            self.issue("loading_order_unconfirmed", self.graph["loading_order"])
        for key in self.graph["traversal_order"]:
            node = self.graph["nodes"][key]
            path = component_path(node["path"])
            try:
                source, files, texts, inputs = loader.read(path)
                sources.append(source)
                self.files.extend(files)
                self.inputs.extend(inputs)
                self.texts.update(texts)
                registered, problems = registered_files(path, official_absence=node.get("origin") == "casc")
                for problem in problems:
                    self.issue("trigger_registration", problem)
                for trigger in registered:
                    doc = Document(trigger)
                    self.documents.append(doc)
                    self.inputs.append({"path": str(trigger), "sha256": doc.sha256})
            except (OSError, ValueError) as exc:
                self.issue("source_read", str(exc))
        self.catalog = Catalog(sources, self.files)
        self.sources = sources
        self.tables = {}
        for family, ident in self.catalog.objects:
            if family == "User":
                self.tables[ident] = self.catalog.effective("User", ident)
        self.fingerprint = digest(self.inputs)
        self.structure = digest({k: [n["attributes"] for n in elements(v) if n["@tag"] == "Fields"]
                                 for k, v in self.tables.items()})

    def issue(self, code, detail):
        self.problems.append({"code": code, "detail": detail})

    def inspect(self):
        candidates = []
        for ident, table in self.tables.items():
            fields = {n["attributes"].get("Id"): n["attributes"].get("Type") for n in elements(table) if n["@tag"] == "Fields"}
            score = sum(f in fields for f in ("Description", "Rarity", "Upgrade", "Max", "NameStr"))
            if score >= 3:
                instances = [n for n in elements(table) if n["@tag"] == "Instances"]
                candidates.append({"table": ident, "fields": fields, "count": len(instances),
                                   "samples": [field_values(n) for n in instances[:3]]})
        functions = [{"source": str(d.path), "library": k[0], "id": k[2], "name": d.name(k)}
                     for d in self.documents for k in d.elements
                     if k[1] == "FunctionDef" and any(t in d.name(k).lower() for t in ("talent", "天赋", "register", "rarity"))]
        return {"mod": str(self.mod), "source_fingerprint": self.fingerprint,
                "structure_fingerprint": self.structure, "sources": self.sources,
                "candidates": candidates, "trigger_candidates": functions,
                "languages": sorted({k[0] for k in self.texts}), "diagnostics": self.problems}

    def auto_mapping(self):
        candidates = self.inspect()["candidates"]
        if len(candidates) != 1:
            raise ValueError("Choose tables in a mapping JSON after inspect: " + str([c["table"] for c in candidates]))
        return {"version": 1, "project": str(self.mod), "tables": [
            {"id": candidates[0]["table"], "roles": ROLES, "default_ids": ["[Default]"]}],
            "rarity_labels": {}, "triggers": [], "relations": [],
            "structure_fingerprint": self.structure}

    def text(self, locale, key, row):
        if not key:
            return ""
        matches = [self.texts[(locale, file, key)] for file in ("GameStrings.txt", "TriggerStrings.txt", "ObjectStrings.txt")
                   if (locale, file, key) in self.texts]
        if not matches:
            self.issue("missing_text", {"row": row, "locale": locale, "key": key})
            return ""
        if len({m["value"] for m in matches}) > 1:
            self.issue("ambiguous_text", {"row": row, "locale": locale, "key": key})
        return matches[0]["value"]

    def user_rows(self, mapping):
        rows = []
        for spec in mapping.get("tables", []):
            ident = spec["id"]
            if ident not in self.tables:
                raise ValueError("Mapped table missing: " + ident)
            table = self.tables[ident]
            provenance = self.catalog.explain_fields("User", ident)
            fields = {n["attributes"]["Id"]: n for n in elements(table) if n["@tag"] == "Fields"}
            for instance in elements(table):
                if instance["@tag"] != "Instances":
                    continue
                raw = field_values(instance)
                instance_id = instance["attributes"].get("Id", instance["attributes"].get("index", ""))
                row = {"id": instance_id, "table": ident, "raw": raw, "locations": [
                    {"source": d["source_id"], "file": d["file"], "table": ident,
                     "instance": instance_id} for d in self.catalog.objects[("User", ident)]]}
                defaults = {}
                for role, field in spec["roles"].items():
                    if f"{field}[0]" in raw:
                        row[role] = raw[f"{field}[0]"]
                    elif field in fields:
                        default = next((c["attributes"].get("value") for c in elements(fields[field])
                                        if c["@tag"] == "Default"), None)
                        # CUser scalar primitive defaults; preserve missing vs default provenance.
                        if default is None:
                            default = "0" if fields[field]["attributes"].get("Type") in ("Int", "Fixed") else ""
                        row[role] = default
                        defaults[role] = "field default or scalar type default"
                row["defaults"] = defaults
                row["status"] = "default" if instance_id in spec.get("default_ids", []) else "availability_unconfirmed"
                if row.get("banned") not in (None, "", "0"):
                    row["status"] = "disabled"
                row["effective_fields"] = flatten(instance)
                row["field_sources"] = {key: value for key, value in provenance.items()
                                        if key.startswith("Instances|" + instance_id + "|")}
                rows.append(row)
        return rows

    def trigger_rows(self, mapping):
        rows = {}
        for spec in mapping.get("triggers", []):
            for doc in self.documents:
                for owner, call in doc.elements.items():
                    if owner[1] != "FunctionCall":
                        continue
                    function = call.find("FunctionDef")
                    if function is None or ref_key(function, owner) != (spec["library"], "FunctionDef", spec["function"]):
                        continue
                    params = {}
                    for ref in call.findall("Parameter"):
                        param = doc.elements.get(ref_key(ref, owner))
                        if param is not None and param.find("ParameterDef") is not None:
                            params[param.find("ParameterDef").get("Id")] = param
                    if spec.get("variable"):
                        targets = [p.find("Variable") for p in params.values()]
                        if not any(v is not None and v.get("Id") == spec["variable"] for v in targets):
                            continue
                    values = {}
                    for role, parameter in spec["roles"].items():
                        selector = parameter if isinstance(parameter, dict) else {"parameter": parameter}
                        param = params.get(selector["parameter"])
                        if param is not None and selector.get("array_index"):
                            array = param.find("Array")
                            param = doc.elements.get(ref_key(array, owner)) if array is not None else None
                        kind = param.find("ValueType") if param is not None else None
                        if param is not None and kind is not None and kind.get("Type") == "text" and param.find("Value") is None and param.find("FunctionCall") is None:
                            values[role] = "Param/Value/" + ("lib_" + owner[0] + "_" if owner[0] else "") + param.get("Id", "")
                        elif param is not None and param.find("Value") is not None and len(param.findall("Value")) == 1 and param.find("FunctionCall") is None and param.find("Variable") is None:
                            values[role] = param.findtext("Value", "")
                        elif param is not None:
                            self.issue("dynamic_trigger_value", {"source": str(doc.path), "element": owner, "role": role})
                    if "array_index" in spec["roles"] and "array_index" not in values:
                        self.issue("dynamic_array_index", {"source": str(doc.path), "element": owner})
                        continue
                    if "array_index" in values:
                        index = values.pop("array_index")
                        if not index.isdecimal():
                            self.issue("dynamic_array_index", {"element": owner, "value": index})
                            continue
                        values["id"] = spec.get("array_id", "array") + "[" + index + "]"
                    if not values.get("id"):
                        self.issue("trigger_missing_id", {"source": str(doc.path), "element": owner})
                        continue
                    ident = values["id"]
                    scope = spec.get("namespace", spec["library"])
                    row = rows.setdefault((scope, ident), {"id": ident, "table": scope, "raw": {}, "locations": [],
                                                           "status": "availability_unconfirmed"})
                    for role, value in values.items():
                        if role in row and role not in ("id",) and row[role] != value:
                            self.issue("trigger_conflict", {"id": ident, "role": role, "values": [row[role], value]})
                        row[role] = value
                        row["raw"][role] = value
                    row["locations"].append({"source": str(doc.path), "library": owner[0], "element": owner[2]})
        return list(rows.values())

    def gui_labels(self, spec):
        """Read literal cases of a verified switch leading to return/set-dialog-text."""
        owner = (spec["library"], "FunctionCall", spec["switch"])
        docs = [d for d in self.documents if owner in d.elements]
        if len(docs) != 1:
            raise ValueError("品质分支无法唯一定位: " + str(owner))
        doc = docs[0]
        def children(node, tag):
            return [doc.elements[ref_key(ref, owner)] for ref in node.findall(tag)]
        def native(node):
            ref = node.find("FunctionDef")
            return ref.get("Id") if ref is not None and ref.get("Library") == "Ntve" else None
        switch = doc.elements[owner]
        if native(switch) != "91C49196":
            raise ValueError("映射入口不是 GUI Switch: " + str(owner))
        labels = {}
        for case in children(switch, "FunctionCall"):
            if native(case) != "3A1227AB":
                continue
            params = children(case, "Parameter")
            actions = children(case, "FunctionCall")
            if actions and native(actions[0]) == "00000097":
                # An unconditional Return ends this arm even if the GUI retains
                # a trailing Break after it.
                actions = actions[:1]
            if len(params) != 1 or len(actions) != 1 or native(actions[0]) not in ("00000097", "BA583993"):
                continue
            value = params[0].findtext("Value")
            texts = [p for p in children(actions[0], "Parameter") if p.find("ValueType[@Type='text']") is not None
                     and all(p.find(t) is None for t in ("Value", "Variable", "FunctionCall"))]
            if value is None or len(texts) != 1:
                continue
            if value in labels:
                raise ValueError("重复的 GUI case: " + value)
            param = texts[0].get("Id")
            key = f"Param/Value/lib_{owner[0]}_{param}"
            labels[value] = {"label": plain_text(self.text("zhCN", key, case.get("Id"))),
                             "text_key": key, "evidence": {"library": owner[0], "switch": owner[2],
                             "case": case.get("Id"), "action": actions[0].get("Id"), "parameter": param}}
        return labels

    def rows(self, mapping):
        rows = self.user_rows(mapping)
        trigger = self.trigger_rows(mapping)
        for row in trigger:
            links = [r for r in rows if mapping.get("merge_on") in ("id", "upgrade")
                     and r.get(mapping["merge_on"]) and r.get(mapping["merge_on"]) == row.get(mapping["merge_on"])]
            if len(links) == 1:
                for key, value in row.items():
                    if key not in ("id", "locations", "raw", "status", "table") and value not in ("", None):
                        if links[0].get(key) not in ("", None, value):
                            self.issue("mixed_conflict", {"id": row["id"], "field": key})
                        elif key not in links[0] or links[0][key] == "":
                            links[0][key] = value
                links[0]["locations"].extend(row["locations"])
            else:
                rows.append(row)
                if links:
                    self.issue("ambiguous_merge", row["id"])
        labels = mapping.get("rarity_labels", {})
        switches = mapping.get("rarity_gui", {})
        if switches:
            labels = mapping["rarity_labels"] = self.gui_labels(switches["rarity"])
        category_labels = {}
        if switches.get("category"):
            category_labels = mapping["category_labels"] = self.gui_labels(switches["category"])
        self.reference_counts = {loc: {"resolved": 0, "unresolved": 0} for loc in ("zhCN", "enUS")}
        related = {}
        for ident, table in self.tables.items():
            if ident not in {s["id"] for s in mapping.get("tables", [])}:
                related[ident] = [{"id": n["attributes"].get("Id"), "fields": field_values(n)}
                                  for n in elements(table) if n["@tag"] == "Instances"]
        for row in rows:
            row["related_objects"] = {}
            for link in mapping.get("relations", []):
                matches = [r for r in related.get(link["table"], [])
                           if row.get(link["role"]) and row[link["role"]] ==
                           (r["id"] if link["field"] == "$id" else r["fields"].get(link["field"] + "[0]"))]
                if matches:
                    row["related_objects"][link["table"]] = matches
            row["rarity_label"] = ""
            rarity = row.get("rarity", "")
            if rarity and row.get("status") not in ("default", "disabled"):
                try:
                    int(rarity)
                except ValueError:
                    self.issue("invalid_rarity", {"id": row["id"], "value": rarity})
                label = labels.get(rarity)
                if rarity in switches.get("display_category_for", []):
                    label = category_labels.get(row.get("category"))
                if label and label.get("evidence") and label.get("label"):
                    row["rarity_label"] = label["label"]
                else:
                    row["rarity_label"] = f"待确认（{rarity}）"
                    self.issue("rarity_label_unconfirmed", {"id": row["id"], "value": rarity})
            for locale in ("zhCN", "enUS"):
                row[locale + "_name"] = plain_text(self.text(locale, row.get("name_key"), row["id"]))
                if row.get("status") not in ("default", "disabled"):
                    value = self.text(locale, row.get("description"), row["id"])
                    row[locale + "_description"] = render_description(
                        value, self.catalog, locale, row["id"], self.reference_counts[locale], self.issue)
            category = row.get("category", "")
            row["audience"] = row.get("class") or category_labels.get(category, {}).get("label") or category
            requirements = [row.get("requirement"), row.get("raw", {}).get("Requirement 2[0]")]
            row["conditions"] = "、".join(v for v in requirements if v)
            upgrade = row.get("upgrade")
            if upgrade and ("Upgrade", upgrade) not in self.catalog.objects:
                self.issue("unresolved_upgrade", {"id": row["id"], "upgrade": upgrade})
        for diagnostic in self.catalog.diagnostics:
            if diagnostic.get("family") == "User" and diagnostic.get("id") in {s["id"] for s in mapping.get("tables", [])}:
                self.issue("catalog", diagnostic)
        return rows


def write_workbook(path, study, rows, mapping):
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font
    book = Workbook()
    sheet = book.active
    sheet.title = "天赋清单"
    columns = [("zhCN_name", "中文名称", 26), ("rarity_label", "品质", 16),
               ("zhCN_description", "效果（未计入玩家额外升级的基础值）", 70),
               ("audience", "职业、兵种或类别", 24), ("max", "层数上限（原值）", 18),
               ("conditions", "获取条件", 28), ("enUS_name", "英文名称", 32),
               ("enUS_description", "英文说明", 70), ("id", "天赋 ID", 32)]
    player = [r for r in rows if r["status"] not in ("default", "disabled")]
    sheet.append([heading for _, heading, _ in columns])
    for number, record in enumerate(player, 2):
        for col, (key, _, _) in enumerate(columns, 1):
            value = str(record.get(key, ""))
            if len(value) > 32767:
                raise ValueError("Excel cell exceeds text limit: " + key)
            cell = sheet.cell(number, col, value)
            cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell, (_, _, width) in zip(sheet[1], columns):
        cell.font = Font(bold=True)
        sheet.column_dimensions[cell.column_letter].width = width
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
    os.close(handle)
    stage = Path(name)
    try:
        book.save(stage)
        check = load_workbook(stage)
        try:
            if check.sheetnames != ["天赋清单"] or check.active.max_row != len(player) + 1:
                raise ValueError("Workbook read-back failed")
        finally:
            check.close()
        stage.replace(path)
    finally:
        stage.unlink(missing_ok=True)


@component_session
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inspect", "export"])
    parser.add_argument("--mod")
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ui-language", default="zh-CN", choices=["zh-CN", "en"])
    args = parser.parse_args()
    config = load_project_config(ROOT)
    mods = find_project_mods(ROOT, args.mod, config=config)
    if len(mods) != 1:
        raise ValueError("Select one readable mod")
    study = Study(mods[0], resolve_dependency_root(ROOT, mods[0], config))
    if args.command == "inspect":
        print(json.dumps(study.inspect(), ensure_ascii=False, indent=2))
        return 0
    data = project_data_dir(ROOT, config, mods[0])
    profile = args.mapping or data / "docs/implementation/talent-export-mapping.json"
    if args.mapping and not profile.is_file():
        raise ValueError("Explicit mapping missing: " + str(profile))
    mapping = json.loads(profile.read_text(encoding="utf-8-sig")) if profile.is_file() else study.auto_mapping()
    if mapping.get("version") != 1:
        raise ValueError("Unsupported mapping version")
    if mapping.get("project") != str(mods[0]):
        raise ValueError("Mapping belongs to another project")
    if mapping.get("structure_fingerprint") != study.structure:
        raise ValueError("Table structure changed; run inspect and review mapping")
    if mapping.get("source_fingerprint") and mapping["source_fingerprint"] != study.fingerprint:
        study.issue("mapping_source_changed", "Review source-backed labels and trigger mappings against the new source fingerprint")
    rows = study.rows(mapping)
    if not rows:
        raise ValueError("No talent definitions; run inspect")
    output = args.output or data / "runtime/reports/rogue-talents.xlsx"
    # Source hash recheck also covers changes during discovery.
    for item in study.inputs:
        current = hashlib.sha256(component_path(item["path"]).read_bytes()).hexdigest()
        if current != item["sha256"]:
            raise ValueError("Source changed during export: " + item["path"])
    write_workbook(output, study, rows, mapping)
    profile.parent.mkdir(parents=True, exist_ok=True)
    mapping["source_fingerprint"] = study.fingerprint
    profile.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"output": str(output), "definitions": len(rows),
               "player_rows": sum(r["status"] not in ("default", "disabled") for r in rows),
               "diagnostics": len(study.problems), "diagnostic_codes": sorted({p["code"] for p in study.problems}),
               "mapping": str(profile), "source_fingerprint": study.fingerprint,
               "structure_fingerprint": study.structure}
    summary["description_references"] = study.reference_counts
    if study.problems:
        summary["issues"] = study.problems
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
