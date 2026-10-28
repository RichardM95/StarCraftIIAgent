"""Versioned static field coverage, with explicit evidence limits.

These rules describe narrow XML operations exercised by repository fixtures.
They do not certify native defaults, unindexed append order or engine parity.
Runtime evidence remains attached to each queried field and source context.
"""
from __future__ import annotations

import re

RULES_VERSION = "catalog-rules-1"
SCALARS = {
    "Unit": {"LifeMax", "LifeStart", "LifeArmor", "ShieldMax", "ShieldStart", "ShieldArmor", "EnergyMax", "EnergyStart", "Speed", "Acceleration", "Sight", "Radius", "Name", "Description"},
    "Weapon": {"Range", "MinRange", "Period", "DamagePoint", "Backswing", "Effect", "Name"},
    "Effect": {"Amount", "ArmorReduction", "VitalFractionCurrent", "VitalFractionMax", "Name"},
    "Behavior": {"Duration", "Period", "MaxStackCount", "Name"},
    "Model": {"Model", "Radius", "Scale", "Name"},
    "Button": {"Name", "Tooltip", "Icon", "Hotkey"},
    "Abil": {"Name", "Range", "Effect", "Arc"},
}
# Exact indexed syntax only. Unindexed declarations make these rules partial.
INDEXED_ARRAYS = {
    ("Unit", "WeaponArray"), ("Unit", "AbilArray"), ("Unit", "BehaviorArray"),
    ("Effect", "EffectArray"), ("Upgrade", "EffectArray"),
}
INDEXED_FIELDS = {
    ("Unit", "WeaponArray"): {"Link", "Turret"},
    ("Unit", "AbilArray"): {"Link"},
    ("Unit", "BehaviorArray"): {"Link"},
    ("Effect", "EffectArray"): {"value"},
    ("Upgrade", "EffectArray"): {"Reference", "Operation", "Value"},
}


def field_rule(catalog: str, path: str) -> dict:
    top = path.split(".", 1)[0]
    name = re.sub(r"\[[^\]]*\]", "", top)
    leaf = path.split(".", 1)[1] if "." in path else "value"
    if "[" not in path and "." not in path and name in SCALARS.get(catalog, set()):
        kind = "explicit_scalar_overlay"
        covered = True
    elif ((catalog, name) in INDEXED_ARRAYS and "[" in top
          and leaf in INDEXED_FIELDS[(catalog, name)]):
        kind = "explicit_indexed_overlay"
        covered = True
    else:
        kind, covered = "uncovered_field", False
    return {"version": RULES_VERSION, "kind": kind, "covered": covered,
            "evidence": "repository_static_fixtures", "engine_verified": False,
            "native_defaults": "unknown", "unindexed_append": "unknown"}


def rule_profile() -> dict:
    return {"rules_version": RULES_VERSION,
            "scalars": {kind: sorted(paths) for kind, paths in SCALARS.items()},
            "indexed_arrays": [{"catalog": kind, "field": path} for kind, path in sorted(INDEXED_ARRAYS)],
            "engine_parity": False, "evidence": "repository_static_fixtures",
            "limitations": ["不展开原生默认、类层次、token 或 Actor 宏", "无索引追加与移除/恢复的引擎效果仍需绑定实机观测"]}
