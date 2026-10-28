"""Non-author terrain probe review; render and parse only, never launch."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.probe_bank import parse_probe_bank


DELIVERY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sc2_mcp.reviewed_terrain_probe", DELIVERY / "src/sc2_mcp/terrain_probe.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RUN = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def parameters():
    return json.loads((DELIVERY / "docs/skyshield-example.json").read_text("utf-8"))


@pytest.mark.parametrize("direction", ["up", "down"])
def test_distinct_raw_endpoints_that_render_identically_are_rejected(parameters, direction):
    start = parameters["thor"][direction + "_start"]
    parameters["thor"][direction + "_end"] = [start[0] + 0.0000001, start[1]]
    with pytest.raises(SC2Error) as caught:
        MODULE.render_terrain_probe(parameters, RUN)
    assert caught.value.code == "invalid_terrain_probe_parameter"


@pytest.mark.parametrize("rect,accepted", [
    ([0,0,255,255], True), ([0,0,255,256], False),
    ([0,0,2048,30], True), ([0,0,2049,1], False),
    ([4094,4094,4096,4096], True), ([4094,4094,4097,4096], False),
    ([-1,0,1,1], False), ([10,20,11,21], True),
])
def test_grid_limits_and_inclusive_offsets(parameters, rect, accepted):
    parameters["rect"] = rect
    if not accepted:
        with pytest.raises(SC2Error) as caught:
            MODULE.render_terrain_probe(parameters, RUN)
        assert caught.value.code == "invalid_terrain_probe_parameter"
        return
    rendered, phases = MODULE.render_terrain_probe(parameters, RUN)
    script = rendered.decode("utf-8")
    y0 = int(re.search(r"int gv_HeightRow = (\d+);", script)[1])
    row = script[script.index("bool HeightRow"):script.index("void HeightProbeInit")]
    x0 = int(re.search(r"lv_x = (\d+);", row)[1])
    x1 = int(re.search(r"while \(lv_x <= (\d+)\)", row)[1])
    y1 = int(re.search(r"if \(gv_HeightRow > (\d+)\)", row)[1])
    assert (x0, y0, x1, y1) == tuple(rect)
    expected = (rect[2]-rect[0]+1) * (rect[3]-rect[1]+1)
    assert sum(1 for y in range(y0,y1+1) for x in range(x0,x1+1)) == expected
    assert f'"ExpectedRows", {y1-y0+1}' in script and f'"ExpectedColumns", {x1-x0+1}' in script
    assert phases == ["Height", "movement", "Buildings", "Boundary"]


@pytest.mark.parametrize("path,value", [
    (("run_id",), 'a'*32+'\nvoid Evil() {}'),
    (("thor", "up_start"), [float("inf"), 2]),
    (("thor", "return_seconds"), True),
    (("building_points", 0, "id"), "合法点"),
    (("building_points", 0, "unit_id"), 'SupplyDepot\\\"\nEvil()'),
    (("boundary_points", 0, "point"), [2, -10**1000]),
    (("placement_tolerance",), float("nan")),
    (("row_interval",), False),
])
def test_nested_injection_and_nonfinite_values_never_become_galaxy(parameters, path, value):
    run = RUN
    if path == ("run_id",):
        run = value
    else:
        target = parameters
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    with pytest.raises(SC2Error) as caught:
        MODULE.render_terrain_probe(parameters, run)
    assert caught.value.code in {"invalid_probe_id", "invalid_terrain_probe_parameter"}


def bank(*, missing_phase=None, observed=True, passing=True):
    root = ET.Element("Bank")
    sections = {"Run": {"RunId": ("string", RUN), "Status": ("string", "FINISHED")}}
    for name in MODULE.PHASES:
        if name != missing_phase:
            sections[name] = {"StageStatus": ("string", "FINISHED")}
    if observed:
        sections.setdefault("Observations", {})["Exact"] = ("flag", "1" if passing else "0")
    for name, values in sections.items():
        section = ET.SubElement(root, "Section", name=name)
        for key, (kind, value) in values.items():
            ET.SubElement(ET.SubElement(section, "Key", name=key), "Value", {kind: value})
    return ET.tostring(root)


@pytest.mark.parametrize("phase", MODULE.PHASES)
def test_finished_run_with_any_missing_stage_stays_partial(phase):
    result = parse_probe_bank(bank(missing_phase=phase), RUN, MODULE.PHASES)
    assert result["execution"]["state"] == "partial" and result["verdict"] == "partial"


@pytest.mark.parametrize("phase", MODULE.PHASES)
def test_observed_failure_outranks_missing_terrain_stage(phase):
    assertion = {"id":"placement", "section":"Observations", "key":"Exact", "operator":"eq", "expected":True}
    result = parse_probe_bank(bank(missing_phase=phase, passing=False), RUN, MODULE.PHASES, [assertion])
    assert result["execution"]["state"] == "partial" and result["verdict"] == "failed"


def test_all_finished_flags_do_not_fill_missing_real_observations():
    assertion = {"id":"placement", "section":"Observations", "key":"Exact", "operator":"eq", "expected":True}
    result = parse_probe_bank(bank(observed=False), RUN, MODULE.PHASES, [assertion])
    assert result["execution"]["state"] == "complete" and result["verdict"] == "partial"
    assert result["assertions"][0]["result"] == "not_observed"


def test_render_is_immutable_and_contains_only_fixed_entrypoints(parameters):
    original = deepcopy(parameters)
    script, _ = MODULE.render_terrain_probe(parameters, RUN)
    assert parameters == original
    assert not script.startswith(b"\xef\xbb\xbf") and b"\0" not in script
    assert script.count(b'"Run", "Status", "FINISHED"') == 1
    for forbidden in (b"UnitSetPosition(", b"TerrainHeight", b"BankRemove(", b"c_unitCreateIgnorePlacement", b"lib1_gt_Initialization"):
        assert forbidden not in script
    assert max(map(len, script.decode("utf-8").splitlines())) < 2048
