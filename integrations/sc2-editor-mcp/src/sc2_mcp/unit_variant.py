"""Audit unit data chains and plan the fixed Marauder/Warfield template.

Only candidates are returned. This module never writes a map, modifies a card
production entry, imports resources, or claims runtime/visual acceptance.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .catalog import CatalogSession, _insert_child, _reference_kind, _spans
from .errors import SC2Error

TEMPLATE_VERSION = "marauder-warfield-1"
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_MACRO = re.compile(r"##[^#]+##|\$[^$]+\$|\{[^}]*\}")
_VISUAL_FIELDS = {"Name", "Description", "EditorCategories", "EditorComment"}


def _inputs(base_unit, new_id, visual_source, allowed):
    for value in [base_unit, new_id, visual_source]:
        if not isinstance(value, str) or not _ID.fullmatch(value):
            raise SC2Error("invalid_variant_id", "单位变体标识必须是稳定的 ASCII Catalog ID", value=value)
    if base_unit == new_id:
        raise SC2Error("variant_id_conflict", "新单位 ID 不能与基准相同")
    if allowed is None:
        return set()
    if not isinstance(allowed, (list, tuple, dict)) or any(not isinstance(v, str) for v in allowed):
        raise SC2Error("invalid_variant_differences", "允许的玩法差异必须是精确字段路径列表或字段字典")
    return set(allowed)


def _entries(session, kind, ident):
    entries = _raw_entries(session, kind, ident)
    seen = set()
    for entry in entries:
        key = (entry["file"], ident)
        if key in seen:
            raise SC2Error("ambiguous_variant_source", "同文件存在重复对象，不能自动生成变体", catalog=kind, object_id=ident, file=entry["file"])
        seen.add(key)
    return entries


def _raw_entries(session, kind, ident):
    # Reuse the CatalogSession loaded-source snapshot, but index byte spans
    # once per file. source_entries() otherwise rehashes a multi-MB document
    # once for every object during a whole-catalog reverse binding audit.
    documents = getattr(session, "_variant_source_documents", None)
    if documents is None:
        documents = session._variant_source_documents = {}
    result, occurrences = [], {}
    for patch in session._library.objects[(kind, ident)]:
        if patch.file not in documents:
            raw = patch.file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != patch.sha256:
                raise SC2Error("catalog_source_changed", "审计期间来源文件发生变化", file=str(patch.file))
            index = {}
            for span in _spans(raw).children:
                index.setdefault((span.tag, span.attributes.get("id")), []).append(span)
            documents[patch.file] = (raw, index)
        raw, index = documents[patch.file]
        key = (patch.file, patch.node.tag, ident)
        occurrence = occurrences.get(key, 0)
        span = index[(patch.node.tag, ident)][occurrence]
        occurrences[key] = occurrence + 1
        result.append({**patch.source(), "offset": span.start, "xml": raw[span.start:span.end].decode("utf-8")})
    return result


def _lineage(session, kind, ident, active=()):
    if ident in active:
        raise SC2Error("variant_parent_cycle", "变体来源父链循环", catalog=kind, chain=[*active, ident])
    entries = _entries(session, kind, ident)
    parent = None
    for entry in entries:
        node = ET.fromstring(entry["xml"])
        if "parent" in node.attrib:
            parent = node.get("parent") or None
    result = []
    if parent:
        if parent not in session.object_ids(kind):
            raise SC2Error("variant_source_incomplete", "变体来源父链未物化", catalog=kind, object_id=ident, parent=parent)
        result.extend(_lineage(session, kind, parent, (*active, ident)))
    return result + entries


def _upgrade_additions(session, mapping, *, audit_records=None, unknown=None):
    """Adapt concrete upgrade leaves by exact Reference identity.

    This is the verified Marauder template rule, not the generic Catalog
    indexed-array approximation. Shared Effect damage references are omitted.
    """
    identifiers = session.object_ids("Upgrade")
    parents = set()
    parent_map, relevant = {}, set()
    for ident in identifiers:
        for entry in _raw_entries(session, "Upgrade", ident):
            node = ET.fromstring(entry["xml"])
            if "parent" in node.attrib:
                parent_map[ident] = node.get("parent") or None
            for child in node:
                ref = child.get("Reference", "").split(",")
                if (child.tag == "EffectArray" and len(ref) >= 3 and tuple(ref[:2]) in mapping
                        or child.tag == "AffectedUnitArray" and ("Unit", child.get("value")) in mapping):
                    relevant.add(ident)
    parents.update(p for p in parent_map.values() if p)
    additions = {}
    for ident in identifiers:
        entries = _raw_entries(session, "Upgrade", ident)
        if ident in parents or any(ET.fromstring(e["xml"]).get("default") == "1" for e in entries):
            continue
        ancestry, at = set(), ident
        while at and at not in ancestry:
            ancestry.add(at)
            at = parent_map.get(at)
        # Unrelated legacy duplicate IDs are stable assets; reject ambiguity
        # only when the referenced leaf/parent chain will actually be adapted.
        incomplete_ancestry = any(a not in identifiers for a in ancestry)
        if not ancestry.intersection(relevant) and not incomplete_ancestry:
            continue
        try:
            lineage = _lineage(session, "Upgrade", ident)
        except SC2Error as exc:
            if unknown is None:
                raise
            unknown.append({"upgrade": ident, **exc.as_dict()})
            continue
        effective = {}
        for source in lineage:
            for child in ET.fromstring(source["xml"]):
                if child.tag not in {"EffectArray", "AffectedUnitArray"}:
                    continue
                key = child.get("Reference") if child.tag == "EffectArray" else child.get("value")
                if child.get("removed") not in {None, "0"}:
                    raise SC2Error("unsupported_variant_upgrade_removal", "该科技含未验证的删除槽，拒绝自动适配", upgrade=ident, source=source["file"])
                if key:
                    effective[(child.tag, key)] = (child, source)
        children = []
        for (tag, key), (child, source) in effective.items():
            if tag == "EffectArray":
                ref = key.split(",")
                replacement = mapping.get(tuple(ref[:2])) if len(ref) >= 3 else None
                if replacement is None:
                    continue
                clone = deepcopy(child)
                clone.attrib.pop("index", None)
                ref[1] = replacement
                clone.set("Reference", ",".join(ref))
            elif ("Unit", key) in mapping:
                clone = ET.Element("AffectedUnitArray", {"value": mapping[("Unit", key)]})
            else:
                continue
            clone.tail = None
            new_key = clone.get("Reference") if tag == "EffectArray" else clone.get("value")
            if audit_records is not None:
                audit_records.append({"upgrade": ident, "tag": tag, "original_reference": key,
                                      "variant_reference": new_key, "status": "present" if (tag, new_key) in effective else "missing",
                                      "source": {k: v for k, v in source.items() if k != "xml"},
                                      "shared_damage_chain_duplicated": False})
            if (tag, new_key) in effective:
                # Existing adaptation must match exactly; never add a second
                # copy of the same modifier as an unindexed array append.
                old = effective[(tag, new_key)][0]
                old_attributes = {k: v for k, v in old.attrib.items() if k != "index"}
                if old_attributes != clone.attrib:
                    raise SC2Error("variant_upgrade_conflict", "现有变体科技与基准不一致", upgrade=ident, reference=new_key)
                continue
            children.append({"xml": ET.tostring(clone, encoding="unicode").replace(" />", "/>"),
                             "source": {k: v for k, v in source.items() if k != "xml"},
                             "original_reference": key, "new_reference": new_key})
        if children:
            additions[ident] = children
    return additions


def summarize_runtime_weapons(observations: list[dict]) -> dict:
    """Keep raw engine slots; an explicitly disabled cache is not an attack."""
    enabled, disabled, unknown = [], [], []
    for observation in observations:
        item = deepcopy(observation)
        value = item.get("enabled")
        if value is True or type(value) is int and value == 1:
            enabled.append(item)
        elif value is False or type(value) is int and value == 0:
            disabled.append(item)
        else:
            unknown.append(item)
    return {"raw_count": len(observations), "enabled": enabled, "disabled_cache": disabled,
            "unknown": unknown, "multiple_enabled_weapons": len(enabled) > 1,
            "duplicate_damage": "not_determined_by_weapon_count",
            "reason": "Disabled cached weapons do not count as enabled attacks; damage needs timed observations."}


def _graph(session, seed):
    ids = {kind: set(session.object_ids(kind)) for kind in session.catalog_names()}
    pending, visited = deque(seed), set()
    nodes, edges, missing, macros = [], [], [], []
    # Reverse unit binding and effect launch are explicit Actor attributes;
    # they are not discovered by assuming an Actor shares the Unit ID.
    actor_bindings = []
    for ident in ids.get("Actor", set()):
        attributes, attribute_sources = {}, {}
        for entry in _raw_entries(session, "Actor", ident):
            node = ET.fromstring(entry["xml"])
            for attribute, value in node.attrib.items():
                attributes[attribute] = value
                attribute_sources[attribute] = entry["file"]
        for attribute, kind in [("unitName", "Unit"), ("effectLaunch", "Effect"), ("effectImpact", "Effect")]:
            if attributes.get(attribute):
                actor_bindings.append((ident, attribute, kind, attributes[attribute], attribute_sources[attribute]))
    while pending:
        kind, ident = pending.popleft()
        if (kind, ident) in visited:
            continue
        visited.add((kind, ident))
        if ident not in ids.get(kind, set()):
            missing.append({"catalog": kind, "object_id": ident})
            continue
        effective = session.inspect(kind, ident)
        nodes.append(effective)
        for entry in _raw_entries(session, kind, ident):
            for attribute, value in ET.fromstring(entry["xml"]).attrib.items():
                if _MACRO.search(value):
                    macros.append({"catalog": kind, "object_id": ident, "field": "@" + attribute,
                                   "value": value, "status": "unknown", "reason": "actor_macro_or_token_not_expanded"})
        for actor, attribute, target_kind, target_id, source in actor_bindings:
            if (kind, ident) == (target_kind, target_id):
                edges.append({"from": ["Actor", actor], "to": [kind, ident], "field": "@" + attribute,
                              "confidence": "literal_actor_binding", "source": source})
                pending.append(("Actor", actor))
        for parent in effective["inheritance"]:
            pending.append((kind, parent))
            edges.append({"from": [kind, ident], "to": [kind, parent], "field": "parent", "confidence": "parent"})
        for field, info in effective["fields"].items():
            value = info["value"]
            if not isinstance(value, str) or not value:
                continue
            if _MACRO.search(value) or "Macros" in field or "Macro" == field:
                macros.append({"catalog": kind, "object_id": ident, "field": field, "value": value,
                               "status": "unknown", "reason": "actor_macro_or_token_not_expanded"})
            reference_kind = _reference_kind(field, effective["class"])
            leaf = re.sub(r"\[[^]]*\]", "", field.split(".")[-1])
            if kind == "Actor" and leaf in {"BuildModel", "PlacementModel", "PortraitModel", "ModelLink"}:
                reference_kind = "Model"
            if kind == "Effect" and leaf == "AmmoUnit":
                reference_kind = "Unit"
            if reference_kind:
                if leaf == "AbilCmd":
                    value = value.split(",")[0]
                edge = {"from": [kind, ident], "to": [reference_kind, value], "field": field,
                        "confidence": "typed_static_field", "source": info.get("source")}
                edges.append(edge)
                pending.append((reference_kind, value))
    return {"nodes": nodes, "edges": edges, "missing": missing, "macros": macros,
            "complete": not missing and not macros, "engine_parity": False,
            "limitations": ["Common typed fields and literal reverse Actor bindings are followed.",
                            "Actor events/macros, native defaults and runtime Catalog writes remain unknown."]}


def audit_unit_variant(roots: list[Path], base_unit: str, new_id: str,
                       visual_source: str = "MarineWarfield", model_report: dict | None = None,
                       allowed_gameplay_differences=None) -> dict:
    allowed = _inputs(base_unit, new_id, visual_source, allowed_gameplay_differences)
    if model_report is not None and not isinstance(model_report, dict):
        raise SC2Error("invalid_variant_model_report", "模型报告必须是 JSON 对象")
    session = CatalogSession(roots)
    base = session.inspect("Unit", base_unit)
    present = new_id in session.object_ids("Unit")
    variant = session.inspect("Unit", new_id) if present else None
    supported = base_unit == "Marauder" and visual_source == "MarineWarfield"
    mapping = {("Unit", base_unit): new_id, ("Actor", base_unit): new_id,
               ("Weapon", "PunisherGrenades"): new_id + "Weapon"}
    seeds = [("Unit", base_unit), ("Model", visual_source)]
    if present:
        seeds.append(("Unit", new_id))
    graph = _graph(session, seeds)
    upgrade_unknown = []
    upgrade_references = []
    try:
        upgrades = _upgrade_additions(session, mapping, audit_records=upgrade_references, unknown=upgrade_unknown) if supported else {}
    except SC2Error as exc:
        upgrades = {}
        upgrade_unknown.append(exc.as_dict())
    gameplay = []
    if variant:
        for field in sorted(set(base["fields"]) | set(variant["fields"])):
            old, new = base["fields"].get(field, {}).get("value"), variant["fields"].get(field, {}).get("value")
            if old == new or field in _VISUAL_FIELDS:
                continue
            expected_binding = field.startswith("WeaponArray[") and field.endswith(".Link") and old == "PunisherGrenades" and new == new_id + "Weapon"
            # A removed duplicate/cache slot is disclosed as structure; it is
            # not claimed to have produced two runtime attacks.
            if field.startswith("WeaponArray[") and new is None:
                category = "weapon_slot_removed_requires_runtime"
            elif expected_binding:
                category = "isolated_weapon_entry"
            else:
                category = "unknown_source" if old is None else ("allowed" if field in allowed else "unexpected")
            gameplay.append({"field": field, "base": old, "variant": new, "classification": category})
    incoming = []
    for kind in ["Abil", "Actor", "Effect", "Unit"]:
        for ident in session.object_ids(kind):
            for entry in _raw_entries(session, kind, ident):
                node = ET.fromstring(entry["xml"])
                for child in node.iter():
                    for attribute, value in child.attrib.items():
                        if value in {base_unit, new_id} or any(re.search(r"(?<![A-Za-z0-9_])" + re.escape(v) + r"(?![A-Za-z0-9_])", value) for v in [base_unit, new_id]) and child.tag == "On":
                            incoming.append({"catalog": kind, "object_id": ident, "tag": child.tag,
                                             "attribute": attribute, "value": value, "file": entry["file"],
                                             "action": "audit_only_no_production_or_event_rewrite"})
    script_refs = []
    for root in roots:
        path = Path(root) / "MapScript.galaxy"
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), 1):
                if any('"' + v + '"' in line for v in [base_unit, new_id]):
                    script_refs.append({"file": str(path), "line": number, "text": line,
                                        "action": "audit_only_no_card_flow_rewrite"})
    model_checks = {"status": "unknown", "reason": "model_report_not_supplied"}
    if model_report:
        animation_known = model_report.get("status") in {"supported_metadata", "partial"}
        unavailable_fields = {entry.get("field") for entry in model_report.get("unsupported", [])}
        weapon_attachments = model_report.get("weapon_attachments")
        model_checks = {"status": "static_only", "sha256": model_report.get("sha256"),
                        "weapon_attachments": weapon_attachments,
                        "single_weapon_attachment": len(weapon_attachments) == 1 if animation_known and "attachments" not in unavailable_fields and isinstance(weapon_attachments, list) else None,
                        "has_death_animation": model_report.get("has_death_animation") if animation_known and "animations" not in unavailable_fields else None,
                        "death_strategy": "separate_TerranSmallUnitDeathLow_model",
                        "visual_acceptance": "not_observed"}
    return {"base_unit": base_unit, "new_id": new_id, "visual_source": visual_source,
            "template": TEMPLATE_VERSION if supported else None,
            "generation_support": "supported_restricted_template" if supported else "unsupported",
            "variant_exists": present, "chain": graph, "upgrade_additions": upgrades,
            "upgrade_count": len(upgrades), "upgrade_field_count": sum(map(len, upgrades.values())),
            "upgrade_unknown": upgrade_unknown,
            "upgrade_references": upgrade_references,
            "referenced_upgrade_count": len({r["upgrade"] for r in upgrade_references}),
            "gameplay_differences": gameplay, "production_and_event_impact": incoming,
            "script_references": script_refs, "model_checks": model_checks,
            "runtime_weapon_policy": summarize_runtime_weapons([]),
            "evidence": {"static": "partial" if not graph["complete"] or upgrade_unknown else "checked_supported_fields",
                         "editor": "not_observed", "runtime": "not_observed", "visual": "not_observed"},
            "source_fingerprints": session.file_fingerprints(),
            "limitations": ["Upgrade additions use exact Unit/Actor/Weapon references at concrete leaves; shared damage Effect references are not duplicated.",
                            "Static WeaponArray length cannot prove effective attack count or damage; disabled runtime cache is excluded from enabled attacks.",
                            "Production, add-on and discard events are impact reports only."]}


def _blocks(new_id):
    # Fixed, independently checked template. Stable shared damage/ability IDs
    # remain untouched. The generic Actor parent avoids Marauder's two-muzzle
    # animation/event macros and uses the inherited unitName birth lifecycle.
    return {
        "Unit": f'''<CUnit id="{new_id}" parent="Marauder">
    <Name value="Unit/Name/{new_id}"/>
    <Description value="Button/Tooltip/Marauder"/>
    <WeaponArray index="0" Link="{new_id}Weapon"/>
    <WeaponArray index="1" removed="1"/>
</CUnit>''',
        "Weapon": f'''<CWeaponLegacy id="{new_id}Weapon" parent="PunisherGrenades">
    <Name value="Weapon/Name/PunisherGrenades"/>
    <DisplayName value="Weapon/Name/PunisherGrenades"/>
    <Effect value="{new_id}LM"/>
</CWeaponLegacy>''',
        "Effect": f'''<CEffectLaunchMissile id="{new_id}LM" parent="PunisherGrenadesLM">
    <AmmoUnit value="PunisherGrenadesLMWeapon"/>
    <ImpactEffect value="PunisherGrenadesSet"/>
</CEffectLaunchMissile>''',
        "Model": f'''<CModel id="{new_id}" parent="MarineWarfield">
    <Model value="Assets\\Units\\Terran\\MarineWarfield\\MarineWarfield.m3"/>
</CModel>''',
        "Actor": f'''<CActorUnit id="{new_id}" parent="GenericUnitStandardNoAutoSoundLinks" unitName="{new_id}">
    <Model value="{new_id}"/>
    <BuildModel value="{new_id}"/>
    <PlacementModel value="{new_id}"/>
    <PortraitModel value="WarfieldPortrait"/>
    <WalkAnimMoveSpeed value="2.25"/>
    <StandAnimTurnTime value="5"/>
    <BarWidth value="50"/>
    <BarOffset value="50"/>
    <UnitIcon value="Assets\\Textures\\Wireframe-Terran-Marine-Warfield.dds"/>
    <HeroIcon value="Assets\\Textures\\Wireframe-Terran-Marine-Warfield.dds"/>
    <GroupIcon><Image value="Assets\\Textures\\Wireframe-Terran-Marine-Warfield.dds"/></GroupIcon>
    <Wireframe><Image value="Assets\\Textures\\Wireframe-Terran-Marine-Warfield.dds"/></Wireframe>
    <LifeArmorIcon value="Assets\\Textures\\btn-upgrade-terran-infantryarmorlevel0.dds"/>
    <HighlightTooltip value="Unit/Name/{new_id}"/>
    <SoundArray index="Yes" value="Marauder_Yes"/>
    <SoundArray index="Attack" value="Marauder_Attack"/>
    <DeathArray index="Normal" ModelLink="TerranSmallUnitDeathLow" SoundLink="Raynor_Explode" VoiceLink=""/>
    <DeathArray index="Eat" ModelLink="TerranSmallUnitDeathLow"/>
    <DeathArray index="Eviscerate" ModelLink="TerranSmallUnitDeathLow"/>
    <DeathArray index="Fire" ModelLink="TerranSmallUnitDeathLow"/>
    <DeathArray index="Silentkill" ModelLink="TerranSmallUnitDeathLow"/>
    <DeathArray index="Squish" ModelLink="TerranSmallUnitDeathLow"/>
    <DeathArray index="UnderConstruction" ModelLink="TerranSmallUnitDeathLow"/>
    <Aliases value="_UnitMedium"/>
</CActorUnit>
<CActorAction id="{new_id}Attack" parent="MarauderAttackBase" effectImpact="PunisherGrenadesU" effectLaunch="{new_id}LM">
    <LaunchAttachQuery Methods="AMFilterWeapon"/>
    <On Terms="Effect.{new_id}LM.Start; At Caster; !ValidateEffect PunisherGrenadesResearched" Send="Create"/>
    <ImpactPhysics Name="PunisherGrenadesImpact" MatchKeys="Basic" Physics="MarauderAttackDeathForce"/>
</CActorAction>
<CActorAction id="{new_id}UpgradedAttack" parent="MarauderAttackBase" effectImpact="PunisherGrenadesU" effectLaunch="{new_id}LM">
    <LaunchAttachQuery Methods="AMFilterWeapon"/>
    <ImpactMap index="None" Model="MarauderUpgradedAttackImpact"/>
    <On Terms="Effect.{new_id}LM.Start; At Caster; ValidateEffect PunisherGrenadesResearched" Send="Create"/>
    <LaunchAssets Model="MarauderAttackLaunch"/>
    <ImpactPhysics Name="PunisherGrenadesImpact" MatchKeys="Basic" Physics="MarauderAttackDeathForce"/>
</CActorAction>'''}


def _target(root, kind):
    relative = f"Base.SC2Data/GameData/{kind}Data.xml"
    path = root / relative
    if path.exists() and (path.is_symlink() or not path.resolve().is_relative_to(root)):
        raise SC2Error("unsafe_variant_target", "候选目标路径不安全", path=str(path))
    raw = path.read_bytes() if path.is_file() else b'<?xml version="1.0" encoding="utf-8"?>\n<Catalog>\n</Catalog>\n'
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise SC2Error("unsupported_variant_encoding", "变体候选要求 UTF-8 无 BOM/NUL", path=relative)
    document = _spans(raw)
    if document.tag != "Catalog":
        raise SC2Error("unsupported_variant_document", "变体目标必须是 Catalog", path=relative)
    return relative, raw, document


def plan_unit_variant_report(root: Path, roots: list[Path], base_unit: str, new_id: str,
                             visual_source: str = "MarineWarfield", allowed_gameplay_differences=None) -> dict:
    allowed = _inputs(base_unit, new_id, visual_source, allowed_gameplay_differences)
    if (base_unit, visual_source) != ("Marauder", "MarineWarfield"):
        raise SC2Error("unsupported_unit_variant_template", "首发仅支持 Marauder → MarineWarfield 外观模板", base_unit=base_unit, visual_source=visual_source)
    if allowed:
        raise SC2Error("unsupported_variant_gameplay_edit", "当前生成模板只保持玩法；允许差异用于审计，尚不自动生成玩法改动", fields=sorted(allowed))
    root = Path(root).resolve()
    resolved_roots = [Path(r).resolve() for r in roots]
    if (not root.is_dir() or root not in resolved_roots
            or any(r.parent != root or not r.name.lower().endswith(".sc2data") for r in resolved_roots[resolved_roots.index(root) + 1:])):
        raise SC2Error("variant_root_order", "目标地图必须是共享来源 roots 的最后一个组件目录")
    session = CatalogSession(roots)
    blocks = _blocks(new_id)
    generated = {"Unit": [new_id], "Weapon": [new_id + "Weapon"], "Effect": [new_id + "LM"],
                 "Model": [new_id], "Actor": [new_id, new_id + "Attack", new_id + "UpgradedAttack"]}
    for kind, identifiers in generated.items():
        for ident in identifiers:
            if ident in session.object_ids(kind):
                raise SC2Error("variant_id_conflict", "新变体对象 ID 已存在", catalog=kind, object_id=ident)
    required = {"Unit": ["Marauder", "PunisherGrenadesLMWeapon"], "Weapon": ["PunisherGrenades"],
                "Effect": ["PunisherGrenadesLM", "PunisherGrenadesSet", "PunisherGrenadesU"],
                "Actor": ["Marauder", "GenericUnitStandardNoAutoSoundLinks", "MarauderAttackBase"],
                "Model": ["MarineWarfield", "WarfieldPortrait", "TerranSmallUnitDeathLow", "MarauderUpgradedAttackImpact", "MarauderAttackLaunch"],
                "Validator": ["PunisherGrenadesResearched"], "AttachMethod": ["AMFilterWeapon"],
                "Sound": ["Raynor_Explode", "Marauder_Yes", "Marauder_Attack"]}
    for kind, identifiers in required.items():
        for ident in identifiers:
            if ident not in session.object_ids(kind):
                raise SC2Error("variant_source_incomplete", "受限模板需要真实来源对象", catalog=kind, object_id=ident)
            _lineage(session, kind, ident)
    # Guard the fixed weapon entry instead of silently replacing a different
    # gameplay chain under an object named Marauder.
    unit = session.inspect("Unit", base_unit)
    weapon_slots = {field: info["value"] for field, info in unit["fields"].items() if field.startswith("WeaponArray[") and field.endswith(".Link")}
    weapons = set(weapon_slots.values())
    if weapons != {"PunisherGrenades"} or set(weapon_slots) - {"WeaponArray[0].Link", "WeaponArray[1].Link"}:
        raise SC2Error("unsupported_variant_base_weapons", "基准有效静态武器与受限模板不一致", weapons=sorted(weapons))
    launch = session.inspect("Weapon", "PunisherGrenades")["fields"].get("Effect", {}).get("value")
    if launch != "PunisherGrenadesLM":
        raise SC2Error("unsupported_variant_base_effect", "基准武器发射链与模板不一致", effect=launch)
    impact = session.inspect("Effect", "PunisherGrenadesLM")["fields"].get("ImpactEffect", {}).get("value")
    if impact != "PunisherGrenadesSet":
        raise SC2Error("unsupported_variant_base_effect", "基准发射命中链与模板不一致", effect=impact)
    changes = {}
    for kind, block in blocks.items():
        relative, raw, document = _target(root, kind)
        newline = b"\r\n" if b"\r\n" in raw else b"\n"
        fragment = block.replace("\n", newline.decode()).encode("utf-8")
        indent = b"    "
        if document.children:
            start = document.children[0].start
            existing_indent = raw[raw.rfind(b"\n", 0, start) + 1:start]
            if existing_indent and not existing_indent.strip():
                indent = existing_indent
        fragment = fragment.replace(newline, newline + indent)
        changes[relative] = _insert_child(raw, document, fragment)
    mapping = {("Unit", base_unit): new_id, ("Actor", base_unit): new_id,
               ("Weapon", "PunisherGrenades"): new_id + "Weapon"}
    additions = _upgrade_additions(session, mapping)
    if additions:
        relative, raw, _ = _target(root, "Upgrade")
        for ident, children in additions.items():
            document = _spans(raw)
            matches = [n for n in document.children if n.attributes.get("id") == ident and n.tag == "CUpgrade"]
            if len(matches) > 1:
                raise SC2Error("ambiguous_variant_upgrade", "目标科技有重复声明", upgrade=ident)
            newline = b"\r\n" if b"\r\n" in raw else b"\n"
            fragment = newline.join(c["xml"].encode() for c in children)
            if matches:
                for child in children:
                    document = _spans(raw)
                    target = next(n for n in document.children if n.attributes.get("id") == ident and n.tag == "CUpgrade")
                    raw = _insert_child(raw, target, child["xml"].encode())
            else:
                fragment = newline.join(b"        " + c["xml"].encode() for c in children)
                raw = _insert_child(raw, document, b'<CUpgrade id="' + ident.encode() + b'">' + newline + fragment + newline + b'    </CUpgrade>')
        changes[relative] = raw
    # Name is part of the template and is appended by exact key, preserving
    # all existing localization bytes and line endings.
    relative = "zhCN.SC2Data/LocalizedData/GameStrings.txt"
    path = root / relative
    if path.exists() and not path.resolve().is_relative_to(root):
        raise SC2Error("unsafe_variant_target", "文本目标路径不安全")
    raw = path.read_bytes() if path.is_file() else b""
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise SC2Error("unsupported_variant_encoding", "文本候选要求 UTF-8 无 BOM/NUL")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SC2Error("unsupported_variant_encoding", "文本候选要求 UTF-8") from exc
    key = f"Unit/Name/{new_id}=".encode()
    if any(line.startswith(key) for line in raw.splitlines()):
        raise SC2Error("variant_localization_conflict", "新单位名称键已存在", key=key.decode())
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    changes[relative] = raw + (newline if raw and not raw.endswith(b"\n") else b"") + key + "劫掠者-沃菲尔德".encode() + newline
    for relative, candidate in changes.items():
        if relative.endswith(".xml"):
            ET.fromstring(candidate)
    return {"changes": changes, "template": TEMPLATE_VERSION, "generated_ids": generated,
            "upgrade_additions": additions, "upgrade_count": len(additions),
            "upgrade_field_count": sum(map(len, additions.values())),
            "source_fingerprints": session.file_fingerprints(), "evidence_layer": "static_candidate",
            "shared_damage_chain": "PunisherGrenadesSet", "runtime_acceptance": "not_observed",
            "unchanged_domains": ["MapScript.galaxy", "BankList.xml", "DocumentInfo", "DocumentHeader", "MapInfo", "production", "addon", "discard_events"],
            "warnings": ["Birth lifecycle remains inherited through generic unitName tokens; arbitrary Actor macros are not expanded.",
                         "Resource availability must be inspected with the same SourceContext before central transaction commit."]}


def plan_unit_variant(root: Path, roots: list[Path], base_unit: str, new_id: str,
                      visual_source: str = "MarineWarfield", allowed_gameplay_differences=None) -> dict[str, bytes | None]:
    return plan_unit_variant_report(root, roots, base_unit, new_id, visual_source,
                                    allowed_gameplay_differences)["changes"]
