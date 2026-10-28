"""离线战场通行网格审计（仅静态几何）。

本模块只在给定的布尔通行网格上做几何腐蚀与四邻域 BFS 连通性审计，
不调用、不模拟也不声称 SC2 引擎的寻路结果。结论的作用域固定为
``validation_scope = "offline_grid_only"``。

坐标约定：``walkable`` 形状为 ``(height, width)``，索引为 ``[y, x]``；
``starts`` 中的坐标是 ``[x, y]``，落在浮点位置时向下取整到 tile。
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from sc2_mcp.errors import SC2Error

_VALIDATION_SCOPE = "offline_grid_only"
_NEIGHBORS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _coerce_walkable(walkable: object) -> np.ndarray:
    if not isinstance(walkable, np.ndarray):
        raise SC2Error("bad_walkable", "walkable 必须为 numpy 数组")
    if walkable.ndim != 2:
        raise SC2Error("bad_walkable", "walkable 必须为二维数组", ndim=int(walkable.ndim))
    if walkable.shape[0] == 0 or walkable.shape[1] == 0:
        raise SC2Error(
            "bad_walkable",
            "walkable 的两个维度都必须非空",
            shape=[int(walkable.shape[0]), int(walkable.shape[1])],
        )
    if walkable.dtype != np.dtype(bool):
        raise SC2Error("bad_walkable", "walkable 必须为布尔数组，不能将未知数值当通行")
    return walkable


def _coerce_clearance(clearance: object) -> float:
    if isinstance(clearance, bool) or not isinstance(
        clearance, (int, float, np.integer, np.floating)
    ):
        raise SC2Error("bad_clearance", "clearance 必须为有限非负数值")
    value = float(clearance)
    if not math.isfinite(value) or value < 0.0:
        raise SC2Error("bad_clearance", "clearance 必须为有限非负数值", clearance=value)
    return value


def _coerce_starts(starts: object, height: int, width: int) -> list[tuple[int, int]]:
    if isinstance(starts, np.ndarray):
        sequence = starts.tolist()
    elif isinstance(starts, (list, tuple)):
        sequence = list(starts)
    else:
        raise SC2Error("bad_starts", "starts 必须为坐标序列")
    if len(sequence) < 2:
        raise SC2Error("bad_starts", "starts 至少需要两个坐标", count=int(len(sequence)))

    tiles: list[tuple[int, int]] = []
    for index, item in enumerate(sequence):
        if isinstance(item, np.ndarray):
            item = item.tolist()
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SC2Error("bad_starts", f"第 {index} 个起点必须为 [x, y]", index=index)
        try:
            x = float(item[0])
            y = float(item[1])
        except (TypeError, ValueError) as exc:
            raise SC2Error("bad_starts", f"第 {index} 个起点坐标必须为数值", index=index) from exc
        if not math.isfinite(x) or not math.isfinite(y):
            raise SC2Error("bad_starts", f"第 {index} 个起点坐标必须有限", index=index)
        tile_x = math.floor(x)
        tile_y = math.floor(y)
        if tile_x < 0 or tile_x >= width or tile_y < 0 or tile_y >= height:
            raise SC2Error(
                "bad_starts",
                f"第 {index} 个起点超出网格",
                index=index,
                tile=[int(tile_x), int(tile_y)],
                grid_size=[int(height), int(width)],
            )
        tiles.append((int(tile_x), int(tile_y)))
    return tiles


def _erode(walkable: np.ndarray, clearance: float) -> np.ndarray:
    """半径 clearance 的保守圆形腐蚀，把边界视为障碍。

    以每个 tile 中心为圆心，若任意障碍 tile（含网格外一圈）中心距圆心
    的欧氏距离不超过 clearance，则该 tile 对半径 clearance 的单位不可通行。
    仅使用 numpy 与标准库。
    """

    height, width = int(walkable.shape[0]), int(walkable.shape[1])
    if clearance >= min(height, width):
        return np.zeros_like(walkable)
    radius_sq = clearance * clearance
    pad = int(math.floor(clearance)) + 1

    # 网格外一圈虚拟障碍，从而使边界按同一“中心距离”规则参与腐蚀。
    blocked = np.zeros((height, width), dtype=bool)
    obstacles = np.ones((height + 2 * pad, width + 2 * pad), dtype=bool)
    obstacles[pad : pad + height, pad : pad + width] = ~walkable

    for dy in range(-pad, pad + 1):
        for dx in range(-pad, pad + 1):
            if dy * dy + dx * dx <= radius_sq:
                blocked |= obstacles[
                    pad + dy : pad + dy + height,
                    pad + dx : pad + dx + width,
                ]
    return walkable & ~blocked


def _bfs(passable: np.ndarray, start: tuple[int, int]) -> np.ndarray:
    """从 start 出发的四邻域 BFS，返回步数距离图（不可达为 -1）。"""

    height, width = int(passable.shape[0]), int(passable.shape[1])
    start_x, start_y = start
    distance = np.full((height, width), -1, dtype=np.int64)
    if not bool(passable[start_y, start_x]):
        return distance

    distance[start_y, start_x] = 0
    queue: deque[tuple[int, int]] = deque([(start_y, start_x)])
    while queue:
        y, x = queue.popleft()
        step = int(distance[y, x]) + 1
        for dy, dx in _NEIGHBORS:
            ny, nx = y + dy, x + dx
            if (
                0 <= ny < height
                and 0 <= nx < width
                and bool(passable[ny, nx])
                and int(distance[ny, nx]) < 0
            ):
                distance[ny, nx] = step
                queue.append((ny, nx))
    return distance


def audit_grid(walkable, starts, clearance=1.5) -> dict:
    """审计离线通行网格的几何连通性。

    参数:
        walkable: 二维 bool numpy 数组，形状 ``(height, width)``，索引 ``[y, x]``。
        starts: 至少两个 ``[x, y]`` 有限坐标，向下取整到 tile。
        clearance: 单位半径，有限非负数。

    返回可直接 JSON 序列化的 dict，键包括 ``grid_size``、``clearance``、
    ``starts``、``connected``、``reachable_cells``、``pairs``、
    ``blocked_start_indices`` 与 ``validation_scope``。

    非法维度、非有限或越界起点、负/非有限 clearance 会抛出 ``SC2Error``；
    合法输入即使完全不连通也正常返回 ``connected = False``，不报成功。
    """

    grid = _coerce_walkable(walkable)
    height, width = int(grid.shape[0]), int(grid.shape[1])
    radius = _coerce_clearance(clearance)
    tiles = _coerce_starts(starts, height, width)

    passable = _erode(grid, radius)

    blocked_start_indices = [
        index
        for index, (tile_x, tile_y) in enumerate(tiles)
        if not bool(passable[tile_y, tile_x])
    ]

    distances = [
        _bfs(passable, (tile_x, tile_y)) for (tile_x, tile_y) in tiles
    ]

    reachable = np.zeros((height, width), dtype=bool)
    for distance in distances:
        reachable |= distance >= 0

    pairs: list[dict] = []
    connected = True
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            target_x, target_y = tiles[j]
            length = int(distances[i][target_y, target_x])
            reachable_pair = length >= 0
            if not reachable_pair:
                connected = False
            pairs.append(
                {
                    "a": int(i),
                    "b": int(j),
                    "start": [int(tiles[i][0]), int(tiles[i][1])],
                    "target": [int(target_x), int(target_y)],
                    "connected": bool(reachable_pair),
                    "length": int(length) if reachable_pair else None,
                }
            )

    connected = bool(connected and not blocked_start_indices)

    return {
        "grid_size": [height, width],
        "clearance": float(radius),
        "starts": [[int(tile_x), int(tile_y)] for (tile_x, tile_y) in tiles],
        "connected": connected,
        "reachable_cells": int(np.count_nonzero(reachable)),
        "pairs": pairs,
        "blocked_start_indices": [int(index) for index in blocked_start_indices],
        "validation_scope": _VALIDATION_SCOPE,
    }
