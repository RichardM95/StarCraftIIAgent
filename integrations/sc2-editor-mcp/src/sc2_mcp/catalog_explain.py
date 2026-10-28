"""Per-field static provenance and separately bound runtime observations."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from .catalog import _Library, _catalog_name
from .catalog_rules import field_rule, rule_profile
from .errors import SC2Error


def _observation_map(observations, catalog, object_id):
    if observations is None:
        return {}, None
    if not isinstance(observations, dict):
        raise SC2Error("invalid_catalog_observations", "观测必须为带来源绑定的对象")
    rows = observations.get("observations", observations.get("fields", {}))
    if isinstance(rows, dict):
        rows = [{"field": name, **(record if isinstance(record, dict) else {"value": record})}
                for name, record in rows.items()]
    if not isinstance(rows, list):
        raise SC2Error("invalid_catalog_observations", "observations 必须为列表或字段映射")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("field"), str):
            raise SC2Error("invalid_catalog_observations", "每条观测必须指定 field")
        if row.get("catalog", catalog) != catalog or row.get("object_id", object_id) != object_id:
            continue
        if row["field"] in result:
            raise SC2Error("ambiguous_catalog_observation", "同一字段存在多条观测，必须明确选择玩家与升级阶段", field=row["field"])
        result[row["field"]] = dict(row)
    return result, observations.get("source_context_id")


def _compare(static, runtime):
    if static is None or runtime is None or isinstance(runtime, (dict, list, bool)):
        return "unknown"
    if str(static) == str(runtime):
        return "matched"
    try:
        left, right = Decimal(str(static)), Decimal(str(runtime))
        if left.is_finite() and right.is_finite():
            return "matched" if left == right else "mismatched"
    except InvalidOperation:
        pass
    return "mismatched"


def catalog_explain(roots: list[Path], catalog: str, object_id: str, fields: list[str] | None = None,
                    source_context: dict | None = None, observations: dict | None = None) -> dict:
    """Explain candidates without elevating unknown semantics to engine truth.

    ``observations`` is a dict with source_context_id and an observations list
    (catalog/object_id/field/value/evidence or evidence_id/status). A mismatched
    binding is retained as runtime data, with comparison unknown. It never
    replaces the static value or promotes a rule's status.
    """
    kind = _catalog_name(catalog)
    if fields is not None and (not isinstance(fields, list) or any(not isinstance(path, str) or not path for path in fields)):
        raise SC2Error("invalid_catalog_fields", "fields 必须为非空字段路径列表")
    context_current = True
    context_issue = None
    if source_context is not None:
        from .source_context import assert_source_context_current
        if [str(Path(p).resolve()) for p in roots] != source_context.get("roots"):
            raise SC2Error("source_context_roots_mismatch", "查询 roots 与来源上下文不一致")
        try:
            assert_source_context_current(source_context)
        except SC2Error as exc:
            if exc.code != "source_context_stale":
                raise
            context_current, context_issue = False, exc.as_dict()
    rows, observation_context = _observation_map(observations, kind, object_id)
    error = None
    uncertain_arrays = set()
    removal_arrays = set()
    try:
        library = _Library(roots)
        inspected = library.inspect(kind, object_id)
        patches = [patch for identifier in [object_id, *inspected["inheritance"]]
                   for patch in library.objects.get((kind, identifier), [])]
        for class_name in {patch.node.tag for patch in patches}:
            patches.extend(library.defaults.get(class_name, []))
        for patch in patches:
            for child in patch.node:
                if child.get("removed") is not None:
                    removal_arrays.add(child.tag)
                if child.get("index") is None and (child.tag.endswith("Array") or (patch.node.tag, (child.tag,)) in library.arrays):
                    uncertain_arrays.add(child.tag)
    except SC2Error as exc:
        if fields is None:
            raise
        error = exc.as_dict()
        inspected = {"fields": {}, "removed": [], "warnings": [], "sources": [], "inheritance": []}
    paths = list(dict.fromkeys(fields if fields is not None else [*inspected["fields"], *rows]))
    removed_paths = {item["path"]: item for item in inspected["removed"]}
    output = {}
    for path in paths:
        record = inspected["fields"].get(path)
        rule = field_rule(kind, path)
        reasons = []
        status = "known_static" if record and rule["covered"] else "partial" if record else "unknown"
        if not record:
            reasons.append("field_absent_or_native_default_unknown")
        elif not rule["covered"]:
            reasons.append("field_rule_not_covered")
        provenance = [*record.get("history", []), {"value": record["value"], "source": record["source"]}] if record else []
        if record and any("##" in str(item["value"]) or "$" in str(item["value"]) for item in provenance[-1:]):
            status = "unknown"
            reasons.append("macro_or_expression_not_evaluated")
        normalized = re.sub(r"\[[^\]]*\]", "", path)
        for warning in inspected["warnings"]:
            code = warning.get("code")
            affects = code in {"missing_catalog_parent", "catalog_class_changed", "catalog_text_not_evaluated", "unknown_removed_value"}
            if warning.get("path") and normalized.startswith(warning["path"]):
                affects = True
            if affects:
                status = "unknown" if status == "unknown" else "partial"
                reasons.append(code)
        if record and any(item.get("source", {}).get("operation") == "append" for item in provenance):
            status = "unknown" if status == "unknown" else "partial"
            reasons.append("unindexed_append_order_not_engine_verified")
        if record and path.split("[", 1)[0] in uncertain_arrays:
            status = "unknown" if status == "unknown" else "partial"
            reasons.append("unindexed_append_order_not_engine_verified")
        if record and path.split("[", 1)[0] in removal_arrays:
            status = "unknown" if status == "unknown" else "partial"
            reasons.append("array_remove_restore_engine_effect_unverified")
        if record and any(item.get("source", {}).get("kind") == "class_default" for item in provenance):
            status = "unknown" if status == "unknown" else "partial"
            reasons.append("class_default_hierarchy_not_engine_verified")
        if record and source_context is not None and not source_context.get("complete"):
            status = "unknown" if status == "unknown" else "partial"
            reasons.append("source_context_incomplete")
        if not context_current:
            status = "unknown" if not record else "partial"
            reasons.append("source_context_stale")
        if error:
            reasons.append(error["code"])
        tombstone = next((item for prefix, item in removed_paths.items() if path == prefix or path.startswith(prefix + ".")), None)
        if tombstone:
            reasons.append("explicit_array_tombstone_native_effect_unverified")
            provenance = [{"value": None, "source": tombstone["source"]}]
        runtime = rows.get(path)
        comparison = "not_observed"
        if runtime is not None:
            runtime = dict(runtime)
            binding_ok = bool(source_context and context_current and observation_context == source_context["source_context_id"])
            observed_build = observations.get("build") if observations else None
            if observed_build is not None:
                expected_build = source_context.get("build") if source_context else None
                build_keys = ("product", "branch", "version", "build_key", "build_info_sha256")
                if (not isinstance(observed_build, dict) or not expected_build
                        or any(observed_build.get(key) != expected_build.get(key) for key in build_keys if key in observed_build)):
                    binding_ok = False
            evidence_ok = bool(runtime.get("evidence_id") or runtime.get("evidence"))
            runtime["binding_status"] = "bound" if binding_ok and evidence_ok else "unverified"
            if not binding_ok:
                runtime["binding_reason"] = "source_context_missing_or_mismatched_or_stale"
            elif not evidence_ok:
                runtime["binding_reason"] = "runtime_evidence_missing"
            comparison = (_compare(record["value"] if record else None, runtime.get("value"))
                          if binding_ok and evidence_ok and runtime.get("status", "observed") == "observed" and status != "unknown"
                          else "unknown")
        output[path] = {"static": {"value": record["value"] if record else None, "removed": tombstone is not None,
                                    "rule": rule}, "provenance": provenance, "status": status,
                        "reasons": list(dict.fromkeys(reasons)), "runtime": runtime, "comparison": comparison}
    return {"catalog": kind, "object_id": object_id, "fields": output, "sources": inspected["sources"],
            "inheritance": inspected["inheritance"], "warnings": inspected["warnings"],
            "source_context_id": source_context.get("source_context_id") if source_context else None,
            "source_context_current": context_current, "source_context_issue": context_issue,
            "error": error, "rules": rule_profile(), "validation": "static_with_separate_observations", "engine_parity": False}
