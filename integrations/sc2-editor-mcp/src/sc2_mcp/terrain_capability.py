"""Explicit capability boundary for native SC2 cliff work.

This module is deliberately small and read-only.  It prevents ordinary
terrain workflows from accidentally treating height, material, or pathing
experiments as native cliff topology support.
"""
from __future__ import annotations

from copy import deepcopy


_CAPABILITIES = {
    "native_cliff_topology_generation": "blocked",
    "native_ramp_generation": "blocked",
    "cliff_editor_acceptance": "blocked",
}


def capability_status() -> dict:
    """Return the fixed cliff status and the evidence needed to unlock it."""
    return {
        "schema": "sc2-cliff-capability/1",
        "capabilities": deepcopy(_CAPABILITIES),
        "native_cliff_topology_generation": "blocked",
        "native_ramp_generation": "blocked",
        "cliff_editor_acceptance": "blocked",
        "known_completed_work": [
            "existing cliff preservation",
            "height flattening and surface model work",
            "material and texture repair",
            "Galaxy pathing-layer experiments",
        ],
        "known_not_completed": [
            "native cliffCellList topology rewrite",
            "native rampList generation",
            "same-version editor load and resave",
            "in-game pathing and visual acceptance of a newly generated cliff",
        ],
        "blocked_reasons": [
            "没有取得同一版本原生编辑器成对保存样本的完整组件差分",
            "未知 HMAP/SMAP/CLIF/cliffCellList/rampList 字段不能安全猜测",
            "既有实验没有完成编辑器重存、游戏通行和视觉验收闭环",
        ],
        "unlock_requirements": [
            "64x64 或更小的原生最小样本",
            "每次只改变一个悬崖操作并保存前后组件指纹",
            "编辑器重存成功且 MapInfo/旁车可回读",
            "游戏内高低地、坡道、寻路和接缝均有独立证据",
        ],
        "evidence": {
            "static": "known_failed_or_incomplete",
            "editor": "blocked",
            "runtime": "blocked",
            "visual": "blocked",
        },
        "write_policy": "普通施工路径不生成悬崖或原生坡道写入候选",
        "engine_parity": False,
    }
