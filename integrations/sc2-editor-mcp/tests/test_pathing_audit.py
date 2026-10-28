"""离线通行网格审计器的针对性测试。

只验证纯静态几何腐蚀与四邻域 BFS，不涉及 SC2 引擎或任何文件写入。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sc2_mcp.errors import SC2Error  # noqa: E402
from sc2_mcp.pathing_audit import audit_grid  # noqa: E402


def _open_grid(height: int = 8, width: int = 8) -> np.ndarray:
    return np.ones((height, width), dtype=bool)


def _single_gap_grid(height: int = 9, width: int = 9) -> np.ndarray:
    """一列墙把网格分成左右两半，仅在第 4 行留一个单格缺口。"""

    grid = np.ones((height, width), dtype=bool)
    grid[:, 4] = False
    grid[4, 4] = True
    return grid


def test_开放图双向连通且长度对称() -> None:
    grid = _open_grid()
    forward = audit_grid(grid, [[1, 1], [6, 6]], clearance=0.5)
    backward = audit_grid(grid, [[6, 6], [1, 1]], clearance=0.5)

    assert forward["connected"] is True
    assert backward["connected"] is True
    assert forward["blocked_start_indices"] == []
    assert forward["pairs"] == [
        {
            "a": 0,
            "b": 1,
            "start": [1, 1],
            "target": [6, 6],
            "connected": True,
            "length": 10,
        }
    ]
    # 四邻域在无障碍开放图上的最短长度为曼哈顿距离，且与方向无关。
    assert forward["pairs"][0]["length"] == backward["pairs"][0]["length"] == 10
    assert forward["reachable_cells"] == 64
    assert forward["grid_size"] == [8, 8]
    assert forward["validation_scope"] == "offline_grid_only"


def test_窄路小单位通过而大单位阻断() -> None:
    grid = _single_gap_grid()

    small = audit_grid(grid, [[1, 4], [6, 4]], clearance=0.5)
    assert small["connected"] is True
    assert small["blocked_start_indices"] == []
    assert small["pairs"][0]["connected"] is True
    assert small["pairs"][0]["length"] == 5
    assert small["reachable_cells"] == 73

    large = audit_grid(grid, [[1, 4], [6, 4]], clearance=1.5)
    # 单格缺口被半径 1.5 的圆形腐蚀封闭，明确返回 false 且不抛异常。
    assert large["connected"] is False
    assert large["blocked_start_indices"] == []
    assert large["pairs"][0]["connected"] is False
    assert large["pairs"][0]["length"] is None
    assert large["reachable_cells"] < small["reachable_cells"]


def test_起点越界与非法坐标抛错() -> None:
    grid = _open_grid(4, 4)

    with pytest.raises(SC2Error):
        audit_grid(grid, [[-1, 0], [2, 2]])
    with pytest.raises(SC2Error):
        audit_grid(grid, [[0, 0], [4, 1]])
    with pytest.raises(SC2Error):
        audit_grid(grid, [[0, 0], [float("nan"), 1]])
    with pytest.raises(SC2Error):
        audit_grid(grid, [[0, 0], [1, float("inf")]])
    with pytest.raises(SC2Error):
        audit_grid(grid, [[0, 0]])


def test_非法维度与负clearance抛错() -> None:
    with pytest.raises(SC2Error):
        audit_grid(np.ones((4,), dtype=bool), [[0, 0], [1, 1]])
    with pytest.raises(SC2Error):
        audit_grid(np.ones((2, 2, 2), dtype=bool), [[0, 0], [1, 1]])
    with pytest.raises(SC2Error):
        audit_grid(np.ones((0, 4), dtype=bool), [[0, 0], [1, 1]])
    with pytest.raises(SC2Error):
        audit_grid(_open_grid(4, 4), [[0, 0], [2, 2]], clearance=-0.1)
    with pytest.raises(SC2Error):
        audit_grid(_open_grid(4, 4), [[0, 0], [2, 2]], clearance=float("nan"))


def test_边界作为障碍参与腐蚀() -> None:
    grid = _open_grid(5, 5)

    # clearance=1.5 时，边缘 tile 中心到网格外障碍中心的距离为 1，应被判为不可通行。
    large = audit_grid(grid, [[0, 0], [4, 4]], clearance=1.5)
    assert large["connected"] is False
    assert large["blocked_start_indices"] == [0, 1]
    assert large["pairs"][0]["connected"] is False
    assert large["pairs"][0]["length"] is None

    # clearance=0 时边界不腐蚀，开放图完全连通。
    zero = audit_grid(grid, [[0, 0], [4, 4]], clearance=0.0)
    assert zero["connected"] is True
    assert zero["blocked_start_indices"] == []
    assert zero["reachable_cells"] == 25
    assert zero["pairs"][0]["length"] == 8

    # clearance=1.5 的开放图只剩内部 6x6 区域可通行，边界环被腐蚀。
    interior = audit_grid(_open_grid(8, 8), [[1, 1], [6, 6]], clearance=1.5)
    assert interior["connected"] is True
    assert interior["reachable_cells"] == 36


def test_坐标floor到tile() -> None:
    grid = _open_grid(4, 4)
    result = audit_grid(grid, [[1.9, 0.2], [2.7, 3.1]], clearance=0.0)

    assert result["starts"] == [[1, 0], [2, 3]]
    assert result["connected"] is True
    assert result["pairs"][0]["start"] == [1, 0]
    assert result["pairs"][0]["target"] == [2, 3]
    assert result["pairs"][0]["length"] == 4


def test_确定性与输入不变() -> None:
    grid = _single_gap_grid()
    starts = [[1, 4], [6, 4]]
    grid_before = grid.copy()
    starts_before = [list(point) for point in starts]

    first = audit_grid(grid, starts, clearance=1.5)
    second = audit_grid(grid, starts, clearance=1.5)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert np.array_equal(grid, grid_before)
    assert starts == starts_before
    # 返回值必须可 JSON 序列化，且标量为 Python 原生类型。
    assert isinstance(first["clearance"], float)
    assert isinstance(first["connected"], bool)
    assert isinstance(first["reachable_cells"], int)
    assert isinstance(first["grid_size"][0], int)
    assert all(isinstance(value, int) for value in first["blocked_start_indices"])


def test_多起点两两连通对() -> None:
    grid = _open_grid(6, 6)
    result = audit_grid(grid, [[0.0, 0.0], [2.0, 2.0], [5.0, 5.0]], clearance=0.0)

    assert result["connected"] is True
    assert len(result["pairs"]) == 3
    assert all(pair["connected"] is True for pair in result["pairs"])
    lengths = {(pair["a"], pair["b"]): pair["length"] for pair in result["pairs"]}
    assert lengths[(0, 1)] == 4
    assert lengths[(0, 2)] == 10
    assert lengths[(1, 2)] == 6
