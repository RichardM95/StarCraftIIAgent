"""Independent semantic-gate regressions; synthetic terrain, no native launch.

The required result is rejection when applying the returned whole component
would change protected ground, out-of-support ground, or ramp/tileset data.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from sc2_mcp import terrain_control as tc
from sc2_mcp.errors import SC2Error
from sc2_mcp.terrain import Terrain


_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("terrain_control_review_fixture", _ROOT / "tests/test_terrain_control.py")
_FIXTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURE)


def run_or_rejected(a, b, c, d, **kwargs):
    try:
        return tc.plan_native_sync_result_report(c, a, b, c, d, **kwargs)
    except SC2Error as error:
        assert error.code == "native_sync_semantic_gate", error.as_dict()
        return None


def test_existing_supported_pair_is_still_accepted(tmp_path):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    report = tc.plan_native_sync_result_report(c, a, b, c, d)
    assert report["checks"] and all(report["checks"].values())
    assert set(report["changes"]) == {"t3SyncHeightMap"}


@pytest.mark.parametrize("protect", [False, True])
def test_common_native_sync_drift_cannot_enter_returned_component(tmp_path, protect):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    before = Terrain(c).heights.copy()
    for path in (b, d):
        terrain = Terrain(path)
        terrain.sync[0, 0, 0] += 256
        (path / "t3SyncHeightMap").write_bytes(terrain.raw["t3SyncHeightMap"][:64] + terrain.sync.tobytes())
    mask = np.zeros((9, 9), dtype=bool)
    mask[0, 0] = protect
    report = run_or_rejected(a, b, c, d, protected_mask=mask)
    if report is None:
        return
    applied = Terrain(c, report["changes"])
    evidence = {"checks": report["checks"], "accepted": report["accepted_components"],
                "protected": protect, "source_height": float(before[0, 0]),
                "returned_height": float(applied.heights[0, 0]),
                "reported_outside_support_max_delta": report["outside_support_max_delta"]}
    assert applied.heights[0, 0] == before[0, 0], json.dumps(evidence)


@pytest.mark.parametrize("old,new", [(b'lo="2"', b'lo="1"'), (b'tileSet="Test"', b'tileSet="Other"')])
def test_common_native_xml_semantic_drift_cannot_enter_returned_component(tmp_path, old, new):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    original = (c / "t3Terrain.xml").read_bytes()
    for path in (b, d):
        file = path / "t3Terrain.xml"
        assert old in file.read_bytes()
        file.write_bytes(file.read_bytes().replace(old, new))
    report = run_or_rejected(a, b, c, d)
    if report is None:
        return
    accepted = report["changes"].get("t3Terrain.xml", original)
    evidence = {"checks": report["checks"], "accepted": report["accepted_components"],
                "original": original.decode(), "candidate": accepted.decode()}
    assert accepted == original, json.dumps(evidence)


def test_common_sync_drift_on_protected_vertex_inside_support_is_rejected(tmp_path):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    for path in (b, d):
        terrain = Terrain(path)
        terrain.sync[4, 3, 0] += 256
        (path / "t3SyncHeightMap").write_bytes(terrain.raw["t3SyncHeightMap"][:64] + terrain.sync.tobytes())
    mask = np.zeros((9, 9), dtype=bool)
    mask[4, 3] = True
    assert Terrain(b).heights[4, 3] == Terrain(d).heights[4, 3] == 9
    assert Terrain(c).heights[4, 3] == 8
    with pytest.raises(SC2Error) as caught:
        tc.plan_native_sync_result_report(c, a, b, c, d, protected_mask=mask)
    error = caught.value
    assert error.code == "native_sync_semantic_gate"
    assert error.details["failed"] == ["applied_protected_sync"], error.as_dict()
    assert error.details["checks"]["sync_outside_support"]
    assert error.details["checks"]["applied_sync_outside_support"]
    assert error.details["checks"]["protected_sync"]


@pytest.mark.parametrize("input_name,required_failure", [
    ("control", "control_xml_structure"),
    ("candidate", "candidate_xml_structure"),
])
def test_input_xml_semantics_cannot_be_erased_by_matching_outputs(tmp_path, input_name, required_failure):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    path = a if input_name == "control" else c
    file = path / "t3Terrain.xml"
    file.write_bytes(file.read_bytes().replace(b'tileSet="Test"', b'tileSet="Other"'))
    assert (b / "t3Terrain.xml").read_bytes() == (d / "t3Terrain.xml").read_bytes()
    with pytest.raises(SC2Error) as caught:
        tc.plan_native_sync_result_report(c, a, b, c, d)
    error = caught.value
    assert error.code == "native_sync_semantic_gate"
    assert required_failure in error.details["failed"], error.as_dict()
    assert "input_xml_structure" in error.details["failed"], error.as_dict()
    assert error.details["checks"]["paired_xml_other_fields"]


def test_normal_requantization_with_unchanged_physical_heights_is_accepted(tmp_path):
    a, b, c, d = _FIXTURE.paired(tmp_path)
    for before, after in ((a, b), (c, d)):
        original = Terrain(before)
        terrain = Terrain(after)
        xml = after / "t3Terrain.xml"
        xml.write_bytes(xml.read_bytes().replace(b'quantizeScale="0.001"', b'quantizeScale="0.002"'))
        terrain.vertices[:, :, :2] //= 2
        (after / "t3HeightMap").write_bytes(terrain.raw["t3HeightMap"][:32] + terrain.vertices.tobytes())
        assert np.array_equal(original.detailed_heights, Terrain(after).detailed_heights)
    report = tc.plan_native_sync_result_report(c, a, b, c, d)
    assert all(report["checks"].values()), report["checks"]
    assert set(report["changes"]) == {"t3HeightMap", "t3SyncHeightMap", "t3Terrain.xml"}
    applied = Terrain(c, report["changes"])
    assert np.array_equal(applied.detailed_heights, Terrain(c).detailed_heights)
    assert applied.heights[4, 4] == 9
    assert np.count_nonzero(applied.heights != Terrain(c).heights) == 1
