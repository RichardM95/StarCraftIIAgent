"""dependencies.py 的行为测试（合成夹具 + 临时目录，不触碰正式地图）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sc2_mcp.dependencies import plan_dependencies, resolve_dependencies  # noqa: E402
from sc2_mcp.errors import SC2Error  # noqa: E402


def _docinfo(refs: list[str]) -> bytes:
    body = "".join(f"    <Value>{ref}</Value>\n" for ref in refs)
    text = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<DocInfo>\n"
        "  <Dependencies>\n"
        f"{body}"
        "  </Dependencies>\n"
        "</DocInfo>\n"
    )
    return text.encode("utf-8")


def _component(base: Path, name: str, refs: list[str]) -> Path:
    directory = base / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "DocumentInfo").write_bytes(_docinfo(refs))
    return directory


def _nrm(path: Path) -> str:
    return str(path.resolve())


# --------------------------------------------------------------------------- #
# 解析：递归顺序、边、来源
# --------------------------------------------------------------------------- #
def test_recursive_load_order_and_edges(tmp_path: Path) -> None:
    libs = tmp_path / "Libs"
    root = _component(tmp_path, "Map.SC2Map", ["file:B.SC2Mod", "file:C.SC2Mod"])
    b = _component(libs, "B.SC2Mod", ["file:D.SC2Mod"])
    c = _component(libs, "C.SC2Mod", [])
    d = _component(libs, "D.SC2Mod", [])

    result = resolve_dependencies(root, [libs])

    assert result["load_order"] == [_nrm(d), _nrm(b), _nrm(c), _nrm(root)]
    assert result["complete"] is True
    assert result["missing"] == []
    assert result["cycles"] == []
    assert len(result["nodes"]) == 4

    root_node = next(n for n in result["nodes"] if n["path"] == _nrm(root))
    assert root_node["kind"] == "root"
    assert root_node["dependencies"] == ["file:B.SC2Mod", "file:C.SC2Mod"]
    assert root_node["resolved_dependencies"] == [_nrm(b), _nrm(c)]

    edge = next(e for e in result["edges"] if e["reference"] == "file:D.SC2Mod")
    assert edge["from"] == _nrm(b)
    assert edge["to"] == _nrm(d)
    assert edge["resolved"] is True
    # 结果必须可 JSON 序列化
    import json

    json.dumps(result)


def test_explicit_listed_order_is_respected(tmp_path: Path) -> None:
    libs = tmp_path / "Libs"
    root = _component(tmp_path, "Map.SC2Map", ["file:Second.SC2Mod", "file:First.SC2Mod"])
    second = _component(libs, "Second.SC2Mod", [])
    first = _component(libs, "First.SC2Mod", [])

    order = resolve_dependencies(root, [libs])["load_order"]

    assert order.index(_nrm(second)) < order.index(_nrm(first)) < order.index(_nrm(root))


def test_case_insensitive_and_extension_fallback(tmp_path: Path) -> None:
    libs = tmp_path / "Libs"
    root = _component(tmp_path, "Map.SC2Map", ["file:liba.sc2mod", "file:Alpha"])
    liba = _component(libs, "LibA.SC2Mod", [])
    alpha = _component(libs, "Alpha.SC2Mod", [])

    result = resolve_dependencies(root, [libs])

    assert result["complete"] is True
    resolved = next(n for n in result["nodes"] if n["path"] == _nrm(root))["resolved_dependencies"]
    assert _nrm(liba) in resolved
    assert _nrm(alpha) in resolved


def test_bnet_and_missing_references_are_not_pretended_resolved(tmp_path: Path) -> None:
    root = _component(tmp_path, "Map.SC2Map", ["file:Missing.SC2Mod", "bnet:Depot/Mod"])

    result = resolve_dependencies(root, [])

    assert result["complete"] is False
    assert [m["kind"] for m in result["missing"]] == ["file", "bnet"]
    assert result["missing"][1]["reason"] == "battle_net_reference_not_resolved"
    assert all(e["to"] is None for e in result["edges"])
    assert any("Battle.net" in w for w in result["warnings"])


def test_cycle_is_reported_and_terminates(tmp_path: Path) -> None:
    libs = tmp_path / "Libs"
    root = _component(tmp_path, "Map.SC2Map", ["file:X.SC2Mod"])
    x = _component(libs, "X.SC2Mod", ["file:Y.SC2Mod"])
    y = _component(libs, "Y.SC2Mod", ["file:X.SC2Mod"])

    result = resolve_dependencies(root, [libs])

    assert result["complete"] is False
    assert result["cycles"], "循环依赖必须被报告"
    cycle = result["cycles"][0]
    assert cycle[0] == cycle[-1]
    assert _nrm(x) in cycle and _nrm(y) in cycle
    assert len(result["nodes"]) == 3


def test_missing_document_info_on_root_raises(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir(parents=True)

    with pytest.raises(SC2Error) as excinfo:
        resolve_dependencies(root, [])

    assert excinfo.value.code == "missing_document_info"


# --------------------------------------------------------------------------- #
# 规划：精确、保字节、安全失败
# --------------------------------------------------------------------------- #
def test_plan_rewrites_dependencies_and_preserves_other_bytes(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()
    original = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<DocInfo>\n"
        "  <!-- 保留 -->\n"
        "  <Name>Fixture</Name>\n"
        "  <Dependencies>\n"
        "    <Value>file:B.SC2Mod</Value>\n"
        "  </Dependencies>\n"
        "</DocInfo>\n"
    ).encode("utf-8")
    (root / "DocumentInfo").write_bytes(original)

    changes = plan_dependencies(root, ["file:B.SC2Mod", "bnet:Depot/Mod"])

    assert set(changes) == {"DocumentInfo"}
    expected = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<DocInfo>\n"
        "  <!-- 保留 -->\n"
        "  <Name>Fixture</Name>\n"
        "  <Dependencies>\n"
        "    <Value>file:B.SC2Mod</Value>\n"
        "    <Value>bnet:Depot/Mod</Value>\n"
        "  </Dependencies>\n"
        "</DocInfo>\n"
    ).encode("utf-8")
    assert changes["DocumentInfo"] == expected
    assert (root / "DocumentInfo").read_bytes() == original  # 纯规划，不写盘


def test_plan_refuses_when_document_header_present(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()
    (root / "DocumentInfo").write_bytes(_docinfo(["file:B.SC2Mod"]))
    original = (root / "DocumentInfo").read_bytes()
    (root / "DocumentHeader").write_bytes(b"\x01\x00\x02")

    with pytest.raises(SC2Error) as excinfo:
        plan_dependencies(root, ["file:C.SC2Mod"])

    assert excinfo.value.code == "unsupported_header"
    assert excinfo.value.details["requirement"] == "document_header_codec"
    assert (root / "DocumentInfo").read_bytes() == original


def test_plan_inserts_dependencies_when_absent(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()
    (root / "DocumentInfo").write_bytes(
        (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<DocInfo>\n"
            "  <Name>Fixture</Name>\n"
            "</DocInfo>\n"
        ).encode("utf-8")
    )

    changes = plan_dependencies(root, ["file:B.SC2Mod"])

    expected = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<DocInfo>\n"
        "  <Name>Fixture</Name>\n"
        "  <Dependencies>\n"
        "    <Value>file:B.SC2Mod</Value>\n"
        "  </Dependencies>\n"
        "</DocInfo>\n"
    ).encode("utf-8")
    assert changes == {"DocumentInfo": expected}


def test_plan_unchanged_values_returns_empty(tmp_path: Path) -> None:
    root = _component(tmp_path, "Map.SC2Map", ["file:B.SC2Mod"])

    assert plan_dependencies(root, ["file:B.SC2Mod"]) == {}


def test_plan_preserves_bom_and_crlf(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()
    text = (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        "<DocInfo>\r\n"
        "  <Name>Fixture</Name>\r\n"
        "  <Dependencies>\r\n"
        '    <Value file="B.SC2Mod"/>\r\n'
        "  </Dependencies>\r\n"
        "</DocInfo>\r\n"
    )
    (root / "DocumentInfo").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

    changes = plan_dependencies(root, ["file:C.SC2Mod"])
    data = changes["DocumentInfo"]

    assert data.startswith(b"\xef\xbb\xbf")
    assert b'    <Value file="C.SC2Mod"/>\r\n' in data
    assert b"B.SC2Mod" not in data
    assert b"  <Name>Fixture</Name>\r\n" in data


def test_plan_replaces_self_closing_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()
    (root / "DocumentInfo").write_bytes(
        (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<DocInfo>\n"
            "  <Dependencies/>\n"
            "</DocInfo>\n"
        ).encode("utf-8")
    )

    changes = plan_dependencies(root, ["file:B.SC2Mod"])

    assert b"<Dependencies>" in changes["DocumentInfo"]
    assert b"    <Value>file:B.SC2Mod</Value>\n" in changes["DocumentInfo"]


@pytest.mark.parametrize("bad", ["", "  ", "bad<value", "line\nbreak"])
def test_plan_rejects_invalid_dependency_value(tmp_path: Path, bad: str) -> None:
    root = _component(tmp_path, "Map.SC2Map", [])

    with pytest.raises(SC2Error) as excinfo:
        plan_dependencies(root, [bad])

    assert excinfo.value.code == "invalid_dependency_value"


def test_plan_missing_document_info_raises(tmp_path: Path) -> None:
    root = tmp_path / "Map.SC2Map"
    root.mkdir()

    with pytest.raises(SC2Error) as excinfo:
        plan_dependencies(root, ["file:B.SC2Mod"])

    assert excinfo.value.code == "missing_document_info"
