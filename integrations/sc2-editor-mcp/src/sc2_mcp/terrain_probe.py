"""Fixed isolated terrain diagnostics; render only, never launch or write maps.

The complete historical row sampler and three Thor event functions retain
their control-flow structure. New placement stages record native observations,
not worker-construction success or user-visible acceptance.
"""
from __future__ import annotations

import math
import re

from .errors import SC2Error
from .validation import lexical_balance

TEMPLATE_VERSION = "terrain-20261016.1"
PHASES = ["Height", "movement", "Buildings", "Boundary"]
MAX_GRID_POINTS = 65536
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")


def _error(message, **details):
    raise SC2Error("invalid_terrain_probe_parameter", message, **details)


def _number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        _error("数值必须有限且位于支持范围", parameter=name, minimum=low, maximum=high)
    return float(value)


def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        _error("坐标必须为明确的 [x,y]", parameter=name)
    return [_number(v, name, -4096, 4096) for v in value]


def _id(value, name):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        _error("名称或单位ID只接受ASCII标识符", parameter=name)
    return value


def _fixed(value):
    return f"{value:.6f}"


def _point_text(value):
    return "Point(" + _fixed(value[0]) + ", " + _fixed(value[1]) + ")"


def _parameters(parameters):
    if not isinstance(parameters, dict):
        _error("参数必须为对象")
    allowed = {"rect", "bounds", "thor", "building_points", "boundary_points", "row_interval", "placement_tolerance"}
    unknown = set(parameters) - allowed
    if unknown:
        _error("包含不支持的参数，不能注入脚本或Native调用", unknown=sorted(unknown))
    if ("rect" in parameters) == ("bounds" in parameters):
        _error("必须且只能指定 rect 或 bounds")
    rect = parameters.get("rect")
    if "bounds" in parameters:
        bounds = parameters["bounds"]
        names = ["min_x", "min_y", "max_x", "max_y"]
        if not isinstance(bounds, dict) or set(bounds) != set(names):
            _error("bounds 必须明确提供 min_x/min_y/max_x/max_y")
        rect = [bounds[key] for key in names]
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        _error("采样选区必须为 [x0,y0,x1,y1]，包含全部边界顶点")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 4096 for v in rect):
        _error("全网格选区必须使用0至4096的整数顶点坐标")
    x0, y0, x1, y1 = rect
    if x0 >= x1 or y0 >= y1 or x1 - x0 + 1 > 2049 or y1 - y0 + 1 > 2049:
        _error("选区必须为非空二维网格，单边顶点数不超过2049")
    if (x1 - x0 + 1) * (y1 - y0 + 1) > MAX_GRID_POINTS:
        _error("网格采样超过65536点上限，不能截断或跳点", maximum=MAX_GRID_POINTS)
    thor = parameters.get("thor")
    points = ["up_start", "up_end", "down_start", "down_end"]
    if not isinstance(thor, dict) or set(thor) - set(points + ["outbound_seconds", "return_seconds"]) or any(key not in thor for key in points):
        _error("thor 必须明确提供两只Thor的起终点，仅可另设outbound_seconds/return_seconds")
    thor = dict(thor)
    for key in points:
        thor[key] = _point(thor[key], "thor." + key)
    for direction in ("up", "down"):
        start = [float(_fixed(v)) for v in thor[direction + "_start"]]
        end = [float(_fixed(v)) for v in thor[direction + "_end"]]
        if max(abs(a - b) for a, b in zip(start, end)) < 1 / 4096:
            _error("Thor起终点渲染后至少一轴须相差1/4096，不能以退化路线冒充坡道往返")
    thor["outbound_seconds"] = _number(thor.get("outbound_seconds", 22), "thor.outbound_seconds", .25, 120)
    thor["return_seconds"] = _number(thor.get("return_seconds", 20), "thor.return_seconds", .25, 120)
    records = {}
    for name, minimum in [("building_points", 2), ("boundary_points", 4)]:
        values = parameters.get(name)
        if not isinstance(values, list) or not minimum <= len(values) <= 32:
            _error("必须显式指定受控检测点数量", parameter=name, minimum=minimum, maximum=32)
        seen = set()
        records[name] = []
        for spec in values:
            keys = {"id", "point", "unit_id", "expected_exact_placeable"}
            if not isinstance(spec, dict) or set(spec) - keys or any(key not in spec for key in ["id", "point", "expected_exact_placeable"]):
                _error("检测点必须提供id/point/expected_exact_placeable，可选unit_id", parameter=name)
            ident = _id(spec["id"], name + ".id")
            if len(ident) > 48 or ident in seen:
                _error("检测点ID必须唯一且不超过48字符", parameter=name, point_id=ident)
            seen.add(ident)
            if not isinstance(spec["expected_exact_placeable"], bool):
                _error("检测点预期必须是显式bool，不能把0/1当真值", parameter=name)
            records[name].append({"id": ident, "point": _point(spec["point"], name + ".point"),
                "unit_id": _id(spec.get("unit_id", "SupplyDepot"), name + ".unit_id"),
                "expected_exact_placeable": spec["expected_exact_placeable"]})
    if {item["expected_exact_placeable"] for item in records["building_points"]} != {True, False}:
        _error("建筑检测必须同时含调用者标注的合法点和非法点，不能只测正例")
    return {"rect": list(rect), "thor": thor, **records,
        "row_interval": _number(parameters.get("row_interval", .1), "row_interval", .05, .25),
        "placement_tolerance": _number(parameters.get("placement_tolerance", .001), "placement_tolerance", 0, .05)}


_GALAXY = r'''include "TriggerLibs/NativeLib"

trigger gt_HeightStart;
trigger gt_HeightRows;
bank gv_HeightBank;
int gv_HeightRow = __Y0__;
bool gv_HeightReady = false;
bool gv_HeightFinished = false;
bool gv_MovementFinished = false;
bool gv_BuildingsFinished = false;
bool gv_BoundaryFinished = false;
bool gv_RunFinished = false;
unit gv_ProbeUp;
unit gv_ProbeDown;
trigger gt_ProbeMoveStart;
trigger gt_ProbeMoveReturn;
trigger gt_ProbeMoveFinish;
trigger gt_ProbeBuildings;
trigger gt_ProbeBoundary;

void ProbeTryFinish () {
    if (!gv_HeightFinished) { return; }
    if (!gv_MovementFinished) { return; }
    if (!gv_BuildingsFinished) { return; }
    if (!gv_BoundaryFinished) { return; }
    if (gv_RunFinished) { return; }
    gv_RunFinished = true;
    BankValueSetFromFixed(gv_HeightBank, "Run", "FinishedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Run", "Status", "FINISHED");
    BankSave(gv_HeightBank);
}

bool HeightStart (bool testConds, bool runActions) {
    int lp_player;
    if (!runActions) { return true; }
    VisEnable(c_visTypeFog, false);
    VisEnable(c_visTypeMask, false);
    gv_HeightBank = BankLoad("__BANK__", 1);
    BankValueSetFromString(gv_HeightBank, "Run", "RunId", "__RUN_ID__");
    BankValueSetFromString(gv_HeightBank, "Run", "Status", "STARTED");
    BankValueSetFromFixed(gv_HeightBank, "Run", "StartedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Run", "TemplateVersion", "__VERSION__");
    BankValueSetFromString(gv_HeightBank, "Height", "StageStatus", "STARTED");
    BankValueSetFromFixed(gv_HeightBank, "Height", "StartedGameTime", GameGetMissionTime());
    BankValueSetFromInt(gv_HeightBank, "Height", "MinX", __X0__);
    BankValueSetFromInt(gv_HeightBank, "Height", "MinY", __Y0__);
    BankValueSetFromInt(gv_HeightBank, "Height", "MaxX", __X1__);
    BankValueSetFromInt(gv_HeightBank, "Height", "MaxY", __Y1__);
    BankValueSetFromInt(gv_HeightBank, "Height", "ExpectedRows", __ROWS__);
    BankValueSetFromInt(gv_HeightBank, "Height", "ExpectedColumns", __COLS__);
    BankValueSetFromString(gv_HeightBank, "meta", "experiment", "Controlled isolated terrain diagnostics; no production initialization");
    BankValueSetFromInt(gv_HeightBank, "meta", "ground_type", c_heightMapGround);
    BankValueSetFromInt(gv_HeightBank, "meta", "air_type", c_heightMapAir);
    BankValueSetFromInt(gv_HeightBank, "meta", "glide_type", c_heightMapGlide);
    BankValueSetFromString(gv_HeightBank, "meta", "placement_api", "UnitTypePlacementFromPoint");
    BankValueSetFromString(gv_HeightBank, "meta", "placement_evidence", "native_declaration_checked; new_stage_runtime_unverified");
    BankValueSetFromString(gv_HeightBank, "meta", "placement_scope", "zero_search_range_query_and_style_zero_spawn; not_worker_construction");
    BankValueSetFromFixed(gv_HeightBank, "meta", "placement_tolerance", __PLACEMENT_TOLERANCE__);
    BankSave(gv_HeightBank);
    lp_player = 1;
    while (lp_player <= 15) {
        CameraSetValue(lp_player, c_cameraValueDistance, 100.0, 0.0, -1.0, 10.0);
        CameraPan(lp_player, __CAMERA_POINT__, 0.0, -1.0, 10.0, false);
        lp_player = lp_player + 1;
    }
    gv_HeightReady = true;
    return true;
}

bool HeightRow (bool testConds, bool runActions) {
    int lv_x;
    point lv_point;
    string lv_ground;
    string lv_air;
    string lv_glide;
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    if (gv_HeightRow > __Y1__) { return true; }
    lv_x = __X0__;
    lv_ground = "";
    lv_air = "";
    lv_glide = "";
    while (lv_x <= __X1__) {
        lv_point = Point(IntToFixed(lv_x), IntToFixed(gv_HeightRow));
        lv_ground = lv_ground + FixedToString(WorldHeight(c_heightMapGround, lv_point), 6) + ",";
        lv_air = lv_air + FixedToString(WorldHeight(c_heightMapAir, lv_point), 6) + ",";
        lv_glide = lv_glide + FixedToString(WorldHeight(c_heightMapGlide, lv_point), 6) + ",";
        lv_x = lv_x + 1;
    }
    BankValueSetFromString(gv_HeightBank, "ground", IntToString(gv_HeightRow), lv_ground);
    BankValueSetFromString(gv_HeightBank, "air", IntToString(gv_HeightRow), lv_air);
    BankValueSetFromString(gv_HeightBank, "glide", IntToString(gv_HeightRow), lv_glide);
    gv_HeightRow = gv_HeightRow + 1;
    if (gv_HeightRow == __Y_AFTER__) {
        BankValueSetFromInt(gv_HeightBank, "meta", "rows_complete", gv_HeightRow - __Y0__);
        BankValueSetFromInt(gv_HeightBank, "Height", "RowsComplete", gv_HeightRow - __Y0__);
        BankValueSetFromFixed(gv_HeightBank, "Height", "FinishedGameTime", GameGetMissionTime());
        BankValueSetFromString(gv_HeightBank, "Height", "StageStatus", "FINISHED");
        BankSave(gv_HeightBank);
        TriggerEnable(gt_HeightRows, false);
        UIDisplayMessage(PlayerGroupAll(), c_messageAreaObjective, StringToText("高度研究采样完成；这是研究图，不是玩法交付。"));
        gv_HeightFinished = true;
        ProbeTryFinish();
    }
    return true;
}

void HeightProbeInit () {
    gt_HeightStart = TriggerCreate("HeightStart");
    TriggerAddEventTimeElapsed(gt_HeightStart, 2.0, c_timeGame);
    gt_HeightRows = TriggerCreate("HeightRow");
    TriggerAddEventTimePeriodic(gt_HeightRows, __ROW_INTERVAL__, c_timeGame);
}

bool ProbeMoveStart (bool testConds, bool runActions) {
    bool lv_order;
    unitgroup lv_createdUp;
    unitgroup lv_createdDown;
    int lv_upCount;
    int lv_downCount;
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    BankValueSetFromFixed(gv_HeightBank, "movement", "StartedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "movement", "StageStatus", "STARTED");
    lv_createdUp = UnitCreate(1, "Thor", 0, 1, __UP_START__, 90.0);
    gv_ProbeUp = UnitLastCreated();
    lv_createdDown = UnitCreate(1, "Thor", 0, 1, __DOWN_START__, 270.0);
    gv_ProbeDown = UnitLastCreated();
    lv_upCount = UnitGroupCount(lv_createdUp, c_unitCountAll);
    lv_downCount = UnitGroupCount(lv_createdDown, c_unitCountAll);
    BankValueSetFromInt(gv_HeightBank, "movement", "up_created_count", lv_upCount);
    BankValueSetFromInt(gv_HeightBank, "movement", "down_created_count", lv_downCount);
    if (lv_upCount != 1) { gv_ProbeUp = null; }
    if (lv_downCount != 1) { gv_ProbeDown = null; }
    BankValueSetFromFlag(gv_HeightBank, "movement", "up_valid", UnitIsValid(gv_ProbeUp));
    BankValueSetFromFlag(gv_HeightBank, "movement", "down_valid", UnitIsValid(gv_ProbeDown));
    if (UnitIsValid(gv_ProbeUp)) {
        BankValueSetFromString(gv_HeightBank, "movement", "up_type", UnitGetType(gv_ProbeUp));
    }
    if (UnitIsValid(gv_ProbeDown)) {
        BankValueSetFromString(gv_HeightBank, "movement", "down_type", UnitGetType(gv_ProbeDown));
    }
    if (UnitIsValid(gv_ProbeUp)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "up_start_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeUp), __UP_START__));
    }
    if (UnitIsValid(gv_ProbeDown)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "down_start_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeDown), __DOWN_START__));
    }
    if (UnitIsValid(gv_ProbeUp)) {
        lv_order = UnitIssueOrder(gv_ProbeUp, OrderTargetingPoint(AbilityCommand("move", 0), __UP_END__), c_orderQueueReplace);
        BankValueSetFromFlag(gv_HeightBank, "movement", "up_order", lv_order);
    }
    if (UnitIsValid(gv_ProbeDown)) {
        lv_order = UnitIssueOrder(gv_ProbeDown, OrderTargetingPoint(AbilityCommand("move", 0), __DOWN_END__), c_orderQueueReplace);
        BankValueSetFromFlag(gv_HeightBank, "movement", "down_order", lv_order);
    }
    BankSave(gv_HeightBank);
    return true;
}

bool ProbeMoveReturn (bool testConds, bool runActions) {
    bool lv_order;
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    if (UnitIsValid(gv_ProbeUp)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "up_outbound_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeUp), __UP_END__));
    }
    if (UnitIsValid(gv_ProbeDown)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "down_outbound_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeDown), __DOWN_END__));
    }
    if (UnitIsValid(gv_ProbeUp)) {
        lv_order = UnitIssueOrder(gv_ProbeUp, OrderTargetingPoint(AbilityCommand("move", 0), __UP_START__), c_orderQueueReplace);
        BankValueSetFromFlag(gv_HeightBank, "movement", "up_return_order", lv_order);
    }
    if (UnitIsValid(gv_ProbeDown)) {
        lv_order = UnitIssueOrder(gv_ProbeDown, OrderTargetingPoint(AbilityCommand("move", 0), __DOWN_START__), c_orderQueueReplace);
        BankValueSetFromFlag(gv_HeightBank, "movement", "down_return_order", lv_order);
    }
    BankSave(gv_HeightBank);
    return true;
}

bool ProbeMoveFinish (bool testConds, bool runActions) {
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    if (UnitIsValid(gv_ProbeUp)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "up_return_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeUp), __UP_START__));
    }
    if (UnitIsValid(gv_ProbeDown)) {
        BankValueSetFromFixed(gv_HeightBank, "movement", "down_return_error", DistanceBetweenPoints(UnitGetPosition(gv_ProbeDown), __DOWN_START__));
    }
    if (UnitIsValid(gv_ProbeUp)) {
        BankValueSetFromFlag(gv_HeightBank, "movement", "up_alive", UnitIsAlive(gv_ProbeUp));
    }
    if (UnitIsValid(gv_ProbeDown)) {
        BankValueSetFromFlag(gv_HeightBank, "movement", "down_alive", UnitIsAlive(gv_ProbeDown));
    }
    BankValueSetFromFlag(gv_HeightBank, "movement", "complete", true);
    BankValueSetFromFixed(gv_HeightBank, "movement", "FinishedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "movement", "StageStatus", "FINISHED");
    BankSave(gv_HeightBank);
    gv_MovementFinished = true;
    ProbeTryFinish();
    return true;
}

void ProbeMovementInit () {
    gt_ProbeMoveStart = TriggerCreate("ProbeMoveStart");
    TriggerAddEventTimeElapsed(gt_ProbeMoveStart, 3.0, c_timeGame);
    gt_ProbeMoveReturn = TriggerCreate("ProbeMoveReturn");
    TriggerAddEventTimeElapsed(gt_ProbeMoveReturn, __MOVE_RETURN__, c_timeGame);
    gt_ProbeMoveFinish = TriggerCreate("ProbeMoveFinish");
    TriggerAddEventTimeElapsed(gt_ProbeMoveFinish, __MOVE_FINISH__, c_timeGame);
}

void ProbePlacementSample (string section, string prefix, string unitType, point requested, bool expected) {
    point lv_placement;
    bool lv_exact;
    BankValueSetFromString(gv_HeightBank, section, prefix + ".UnitType", unitType);
    BankValueSetFromFixed(gv_HeightBank, section, prefix + ".RequestX", PointGetX(requested));
    BankValueSetFromFixed(gv_HeightBank, section, prefix + ".RequestY", PointGetY(requested));
    BankValueSetFromFixed(gv_HeightBank, section, prefix + ".Ground", WorldHeight(c_heightMapGround, requested));
    BankValueSetFromFixed(gv_HeightBank, section, prefix + ".Air", WorldHeight(c_heightMapAir, requested));
    BankValueSetFromFixed(gv_HeightBank, section, prefix + ".Glide", WorldHeight(c_heightMapGlide, requested));
    BankValueSetFromFlag(gv_HeightBank, section, prefix + ".ExpectedExactPlaceable", expected);
    lv_placement = UnitTypePlacementFromPoint(unitType, 1, requested, 0.0);
    BankValueSetFromFlag(gv_HeightBank, section, prefix + ".QueryReturned", lv_placement != null);
    lv_exact = false;
    if (lv_placement != null) {
        BankValueSetFromFixed(gv_HeightBank, section, prefix + ".QueryX", PointGetX(lv_placement));
        BankValueSetFromFixed(gv_HeightBank, section, prefix + ".QueryY", PointGetY(lv_placement));
        BankValueSetFromFixed(gv_HeightBank, section, prefix + ".QueryError", DistanceBetweenPoints(lv_placement, requested));
        lv_exact = DistanceBetweenPoints(lv_placement, requested) <= __PLACEMENT_TOLERANCE__;
    }
    BankValueSetFromFlag(gv_HeightBank, section, prefix + ".ExactPlaceable", lv_exact);
}

void ProbeBuildingSample (string prefix, string unitType, point requested, bool expected) {
    unitgroup lv_created;
    unit lv_building;
    int lv_count;
    int lv_index;
    ProbePlacementSample("Buildings", prefix, unitType, requested, expected);
    lv_created = UnitCreate(1, unitType, 0, 1, requested, 270.0);
    lv_count = UnitGroupCount(lv_created, c_unitCountAll);
    BankValueSetFromInt(gv_HeightBank, "Buildings", prefix + ".CreatedCount", lv_count);
    if (lv_count == 1) {
        lv_building = UnitGroupUnit(lv_created, 1);
        BankValueSetFromFlag(gv_HeightBank, "Buildings", prefix + ".CreatedValid", UnitIsValid(lv_building));
        if (UnitIsValid(lv_building)) {
            BankValueSetFromString(gv_HeightBank, "Buildings", prefix + ".CreatedType", UnitGetType(lv_building));
            BankValueSetFromFixed(gv_HeightBank, "Buildings", prefix + ".CreatedX", PointGetX(UnitGetPosition(lv_building)));
            BankValueSetFromFixed(gv_HeightBank, "Buildings", prefix + ".CreatedY", PointGetY(UnitGetPosition(lv_building)));
            BankValueSetFromFixed(gv_HeightBank, "Buildings", prefix + ".CreatedError", DistanceBetweenPoints(UnitGetPosition(lv_building), requested));
            BankValueSetFromFlag(gv_HeightBank, "Buildings", prefix + ".CreatedExact", DistanceBetweenPoints(UnitGetPosition(lv_building), requested) <= __PLACEMENT_TOLERANCE__);
            BankValueSetFromFlag(gv_HeightBank, "Buildings", prefix + ".CreatedAlive", UnitIsAlive(lv_building));
        }
    }
    lv_index = lv_count;
    while (lv_index >= 1) {
        lv_building = UnitGroupUnit(lv_created, lv_index);
        if (UnitIsValid(lv_building)) {
            UnitRemove(lv_building);
        }
        lv_index = lv_index - 1;
    }
}

bool ProbeBuildings (bool testConds, bool runActions) {
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    BankValueSetFromFixed(gv_HeightBank, "Buildings", "StartedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Buildings", "StageStatus", "STARTED");
    BankSave(gv_HeightBank);
__BUILDING_CALLS__
    BankValueSetFromFixed(gv_HeightBank, "Buildings", "FinishedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Buildings", "StageStatus", "FINISHED");
    BankSave(gv_HeightBank);
    gv_BuildingsFinished = true;
    ProbeTryFinish();
    return true;
}

void ProbeBoundarySample (string prefix, string unitType, point requested, bool expected) {
    region lv_entire;
    region lv_playable;
    point lv_min;
    point lv_max;
    lv_entire = RegionEntireMap();
    lv_playable = RegionPlayableMap();
    lv_min = RegionGetBoundsMin(lv_entire);
    lv_max = RegionGetBoundsMax(lv_entire);
    ProbePlacementSample("Boundary", prefix, unitType, requested, expected);
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".InsideEntire", RegionContainsPoint(lv_entire, requested));
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".InsidePlayable", RegionContainsPoint(lv_playable, requested));
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".OnWestEdge", PointGetX(requested) == PointGetX(lv_min) && PointGetY(requested) >= PointGetY(lv_min) && PointGetY(requested) <= PointGetY(lv_max));
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".OnEastEdge", PointGetX(requested) == PointGetX(lv_max) && PointGetY(requested) >= PointGetY(lv_min) && PointGetY(requested) <= PointGetY(lv_max));
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".OnSouthEdge", PointGetY(requested) == PointGetY(lv_min) && PointGetX(requested) >= PointGetX(lv_min) && PointGetX(requested) <= PointGetX(lv_max));
    BankValueSetFromFlag(gv_HeightBank, "Boundary", prefix + ".OnNorthEdge", PointGetY(requested) == PointGetY(lv_max) && PointGetX(requested) >= PointGetX(lv_min) && PointGetX(requested) <= PointGetX(lv_max));
}

bool ProbeBoundary (bool testConds, bool runActions) {
    point lv_min;
    point lv_max;
    point lv_playMin;
    point lv_playMax;
    if (!runActions) { return true; }
    if (!gv_HeightReady) { return true; }
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "StartedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Boundary", "StageStatus", "STARTED");
    BankSave(gv_HeightBank);
    lv_min = RegionGetBoundsMin(RegionEntireMap());
    lv_max = RegionGetBoundsMax(RegionEntireMap());
    lv_playMin = RegionGetBoundsMin(RegionPlayableMap());
    lv_playMax = RegionGetBoundsMax(RegionPlayableMap());
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "EntireMinX", PointGetX(lv_min));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "EntireMinY", PointGetY(lv_min));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "EntireMaxX", PointGetX(lv_max));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "EntireMaxY", PointGetY(lv_max));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "PlayableMinX", PointGetX(lv_playMin));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "PlayableMinY", PointGetY(lv_playMin));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "PlayableMaxX", PointGetX(lv_playMax));
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "PlayableMaxY", PointGetY(lv_playMax));
__BOUNDARY_CALLS__
    BankValueSetFromFixed(gv_HeightBank, "Boundary", "FinishedGameTime", GameGetMissionTime());
    BankValueSetFromString(gv_HeightBank, "Boundary", "StageStatus", "FINISHED");
    BankSave(gv_HeightBank);
    gv_BoundaryFinished = true;
    ProbeTryFinish();
    return true;
}

void ProbePlacementInit () {
    gt_ProbeBuildings = TriggerCreate("ProbeBuildings");
    TriggerAddEventTimeElapsed(gt_ProbeBuildings, __BUILDINGS_TIME__, c_timeGame);
    gt_ProbeBoundary = TriggerCreate("ProbeBoundary");
    TriggerAddEventTimeElapsed(gt_ProbeBoundary, __BOUNDARY_TIME__, c_timeGame);
}

void InitMap () {
    libNtve_InitLib();
    HeightProbeInit();
    ProbeMovementInit();
    ProbePlacementInit();
}
'''


def render_terrain_probe(parameters: dict, run_id: str) -> tuple[bytes, list[str]]:
    """Render the complete fixed probe and expected Bank phases, without I/O.

    Integer grid rectangles are inclusive. All movement/placement points and
    both positive/negative placement expectations must be caller supplied.
    No user code, native name, event definition or arbitrary Bank name enters
    the template. Lexical balance is a static check, not Galaxy compilation.
    """
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise SC2Error("invalid_probe_id", "探针ID必须是32位小写十六进制")
    values = _parameters(parameters)
    x0, y0, x1, y1 = values["rect"]
    thor = values["thor"]
    move_return = 3.0 + thor["outbound_seconds"]
    move_finish = move_return + thor["return_seconds"]
    substitutions = {"__RUN_ID__": run_id, "__BANK__": "SC2MCPProbe_" + run_id, "__VERSION__": TEMPLATE_VERSION,
        "__X0__": str(x0), "__Y0__": str(y0), "__X1__": str(x1), "__Y1__": str(y1),
        "__ROWS__": str(y1 - y0 + 1), "__COLS__": str(x1 - x0 + 1), "__Y_AFTER__": str(y1 + 1),
        "__CAMERA_POINT__": _point_text([(x0 + x1) / 2, (y0 + y1) / 2]),
        "__ROW_INTERVAL__": _fixed(values["row_interval"]),
        "__PLACEMENT_TOLERANCE__": _fixed(values["placement_tolerance"]),
        "__UP_START__": _point_text(thor["up_start"]), "__UP_END__": _point_text(thor["up_end"]),
        "__DOWN_START__": _point_text(thor["down_start"]), "__DOWN_END__": _point_text(thor["down_end"]),
        "__MOVE_RETURN__": _fixed(move_return), "__MOVE_FINISH__": _fixed(move_finish),
        "__BUILDINGS_TIME__": _fixed(move_finish + 1), "__BOUNDARY_TIME__": _fixed(move_finish + 2)}
    for group, function, token in [("building_points", "ProbeBuildingSample", "__BUILDING_CALLS__"),
                                   ("boundary_points", "ProbeBoundarySample", "__BOUNDARY_CALLS__")]:
        substitutions[token] = "\n".join('    ' + function + '("' + item["id"] + '", "' + item["unit_id"] + '", '
            + _point_text(item["point"]) + ', ' + str(item["expected_exact_placeable"]).lower() + ');' for item in values[group])
    text = re.sub(r"__[A-Z_0-9]+__", lambda match: substitutions[match[0]], _GALAXY)
    raw = text.encode("utf-8")
    lexical_balance(raw)
    return raw, list(PHASES)
