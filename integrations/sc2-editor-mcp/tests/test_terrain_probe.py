import ast
from copy import deepcopy
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.probe_bank import parse_probe_bank
from sc2_mcp.terrain_probe import render_terrain_probe
from sc2_mcp.validation import lexical_balance

PROJECT = Path(r'<SC2_EDITOR_MCP_ROOT>')
NATIVES = Path(r'<SC2_PROJECT_ROOT>\work\sciencevessel_fix_20261011\live_dependency\mods\core.sc2mod\base.sc2data\TriggerLibs\natives.galaxy')
RUN_ID = '0123456789abcdef0123456789abcdef'


@pytest.fixture
def parameters():
    return {'rect': [0, 0, 144, 120],
        'thor': {'up_start': [71, 61], 'up_end': [71, 76], 'down_start': [73, 76], 'down_end': [73, 61]},
        'building_points': [
            {'id': 'legal_ground', 'point': [60, 58], 'expected_exact_placeable': True},
            {'id': 'illegal_edge', 'point': [0, 0], 'expected_exact_placeable': False}],
        'boundary_points': [
            {'id': 'west', 'point': [0, 60], 'expected_exact_placeable': False},
            {'id': 'east', 'point': [144, 60], 'expected_exact_placeable': False},
            {'id': 'south', 'point': [72, 0], 'expected_exact_placeable': False},
            {'id': 'north', 'point': [72, 120], 'expected_exact_placeable': False}]}


def normalize_numbers(text):
    return re.sub(r'\b\d+\.\d+\b', lambda match: format(float(match[0]), 'g'), text)


def test_complete_historical_row_loop_and_all_three_layers_are_preserved(parameters):
    raw, phases = render_terrain_probe(parameters, RUN_ID)
    text = raw.decode('utf-8')
    old = PROJECT / 'workspace/keystone-skyshield-20261011/research/flatten/native-height-flat-probe.SC2Map/Triggers'
    original = ET.fromstring(old.read_bytes()).find('.//ScriptCode').text
    start = original.index('    lv_x = 0;')
    end = original.index('    if (gv_HeightRow == 121)')
    assert original[start:end] in text
    for statement in ['if (!gv_HeightReady) { return true; }', 'if (gv_HeightRow > 120) { return true; }',
                      'TriggerEnable(gt_HeightRows, false);', 'while (lp_player <= 15)', 'VisEnable(c_visTypeMask, false);']:
        assert statement in text
    assert phases == ['Height', 'movement', 'Buildings', 'Boundary']
    assert lexical_balance(raw)['compiler'] == 'not_run'
    assert ('BankLoad("SC2MCPProbe_' + RUN_ID + '", 1)').encode() in raw
    assert not raw.startswith(b'\xef\xbb\xbf') and b'\x00' not in raw
    assert b'lib1_gt_Initialization' not in raw


def test_historical_thor_observations_orders_and_event_structure_are_preserved(parameters):
    raw, _ = render_terrain_probe(parameters, RUN_ID)
    text = normalize_numbers(raw.decode('utf-8'))
    tree = ast.parse((PROJECT / 'scripts/build_skyshield_release_candidate.py').read_text(encoding='utf-8'))
    assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'movement' for target in node.targets))
    original = ast.literal_eval(assignment.value)
    for line in original.splitlines():
        if any(token in line for token in ['UnitCreate(', 'UnitLastCreated()', 'BankValueSetFrom', 'UnitIssueOrder(',
                                           '= TriggerCreate(', 'TriggerAddEventTimeElapsed(']):
            statement = line.strip()
            if 'UnitCreate(' in statement or 'UnitIssueOrder(' in statement:
                statement = statement[statement.index('UnitCreate(') if 'UnitCreate(' in statement else statement.index('UnitIssueOrder('):]
            assert normalize_numbers(statement) in text, statement
    assert 'up_return_order' in text and 'down_return_order' in text
    assert 'up_created_count' in text and 'down_created_count' in text
    assert 'if (lv_upCount != 1) { gv_ProbeUp = null; }' in text


def test_custom_inclusive_bounds_and_wait_times_are_exact(parameters):
    parameters.pop('rect')
    parameters['bounds'] = {'min_x': 5, 'min_y': 8, 'max_x': 9, 'max_y': 12}
    parameters['thor']['outbound_seconds'] = 10.5
    parameters['thor']['return_seconds'] = 12.25
    parameters['row_interval'] = .2
    raw, _ = render_terrain_probe(parameters, RUN_ID)
    text = raw.decode('utf-8')
    for expected in ['gv_HeightRow = 8;', 'if (gv_HeightRow > 12)', 'lv_x = 5;', 'while (lv_x <= 9)',
                     'if (gv_HeightRow == 13)', 'gv_HeightRow - 8', '"ExpectedColumns", 5', '"ExpectedRows", 5',
                     'gt_ProbeMoveReturn, 13.500000', 'gt_ProbeMoveFinish, 25.750000',
                     'gt_ProbeBuildings, 26.750000', 'gt_ProbeBoundary, 27.750000']:
        assert expected in text


def test_new_placement_observes_relocation_and_missing_values_without_bypass(parameters):
    raw, _ = render_terrain_probe(parameters, RUN_ID)
    text = raw.decode('utf-8')
    assert 'UnitTypePlacementFromPoint(unitType, 1, requested, 0.0)' in text
    assert 'UnitCreate(1, unitType, 0, 1, requested, 270.0)' in text
    assert 'c_unitCreateIgnorePlacement' not in text
    assert 'native_declaration_checked; new_stage_runtime_unverified' in text
    query = text[text.index('void ProbePlacementSample'):text.index('void ProbeBuildingSample')]
    assert 'if (lv_placement != null)' in query
    assert query.index('if (lv_placement != null)') < query.index('prefix + ".QueryError"')
    assert 'prefix + ".QueryError", 0' not in query
    building = text[text.index('void ProbeBuildingSample'):text.index('bool ProbeBuildings')]
    assert building.index('if (lv_count == 1)') < building.index('prefix + ".CreatedType"')
    assert building.index('if (UnitIsValid(lv_building))') < building.index('prefix + ".CreatedX"')
    assert 'while (lv_index >= 1)' in building and 'UnitRemove(lv_building)' in building
    assert text.count('"Run", "Status", "FINISHED"') == 1
    finish = text[text.index('void ProbeTryFinish'):text.index('bool HeightStart')]
    for flag in ['gv_HeightFinished', 'gv_MovementFinished', 'gv_BuildingsFinished', 'gv_BoundaryFinished']:
        assert 'if (!' + flag + ') { return; }' in finish


@pytest.mark.parametrize('case', ['missing_rect', 'both_rects', 'fractional', 'bool_rect', 'oversized', 'empty',
    'missing_thor', 'same_thor_points', 'nan_point', 'injected_unit', 'injected_key', 'unknown_script',
    'duplicate_point', 'not_bool', 'positive_only', 'missing_boundary', 'zero_wait', 'huge_integer', 'bad_bounds'])
def test_invalid_unsafe_or_incomplete_inputs_are_rejected(parameters, case):
    if case == 'missing_rect': parameters.pop('rect')
    elif case == 'both_rects': parameters['bounds'] = {}
    elif case == 'fractional': parameters['rect'][0] = .5
    elif case == 'bool_rect': parameters['rect'][0] = True
    elif case == 'oversized': parameters['rect'] = [0, 0, 512, 512]
    elif case == 'empty': parameters['rect'][2] = 0
    elif case == 'missing_thor': parameters.pop('thor')
    elif case == 'same_thor_points': parameters['thor']['up_end'] = [71, 61]
    elif case == 'nan_point': parameters['thor']['up_end'] = [float('nan'), 61]
    elif case == 'injected_unit': parameters['building_points'][0]['unit_id'] = 'SupplyDepot"); Evil(); //'
    elif case == 'injected_key': parameters['building_points'][0]['id'] = 'x"); Evil(); //'
    elif case == 'unknown_script': parameters['script'] = 'any code'
    elif case == 'duplicate_point': parameters['building_points'][1]['id'] = 'legal_ground'
    elif case == 'not_bool': parameters['building_points'][0]['expected_exact_placeable'] = 1
    elif case == 'positive_only': parameters['building_points'][1]['expected_exact_placeable'] = True
    elif case == 'missing_boundary': parameters['boundary_points'] = []
    elif case == 'zero_wait': parameters['thor']['outbound_seconds'] = 0
    elif case == 'huge_integer': parameters['thor']['outbound_seconds'] = 10 ** 1000
    else:
        parameters.pop('rect')
        parameters['bounds'] = {'min_x': 0, 'max_x': 10}
    with pytest.raises(SC2Error) as exc:
        render_terrain_probe(parameters, RUN_ID)
    assert exc.value.code == 'invalid_terrain_probe_parameter'


def test_run_id_is_exact_and_render_does_not_mutate_caller(parameters):
    before = deepcopy(parameters)
    for invalid in ['old', RUN_ID.upper(), 'a' * 31, 'a' * 33, RUN_ID + '"); Evil(); //']:
        with pytest.raises(SC2Error) as exc:
            render_terrain_probe(parameters, invalid)
        assert exc.value.code == 'invalid_probe_id'
    first = render_terrain_probe(parameters, RUN_ID)
    second = render_terrain_probe(parameters, RUN_ID)
    assert first == second and parameters == before


def call_arities(text, name):
    for match in re.finditer(r'\b' + re.escape(name) + r'\s*\(', text):
        depth, commas, content = 1, 0, False
        quoted, escaped = False, False
        for char in text[match.end():]:
            if quoted:
                if escaped: escaped = False
                elif char == '\\': escaped = True
                elif char == '"': quoted = False
                continue
            if char == '"': quoted = True; content = True
            elif char == '(': depth += 1; content = True
            elif char == ')':
                depth -= 1
                if depth == 0:
                    yield commas + int(content)
                    break
            elif char == ',' and depth == 1: commas += 1
            elif not char.isspace(): content = True


def test_native_call_arities_match_readonly_blizzard_declarations(parameters):
    raw, _ = render_terrain_probe(parameters, RUN_ID)
    text = raw.decode('utf-8')
    native = NATIVES.read_text(encoding='utf-8-sig')
    names = ['WorldHeight', 'UnitTypePlacementFromPoint', 'UnitCreate', 'UnitGroupCount', 'UnitGroupUnit',
        'UnitLastCreated', 'UnitIsValid', 'UnitRemove', 'UnitGetType', 'UnitGetPosition', 'UnitIssueOrder',
        'DistanceBetweenPoints', 'RegionEntireMap', 'RegionPlayableMap', 'RegionContainsPoint',
        'RegionGetBoundsMin', 'RegionGetBoundsMax', 'PointGetX', 'PointGetY', 'TriggerAddEventTimeElapsed',
        'TriggerAddEventTimePeriodic', 'BankValueSetFromFixed', 'BankValueSetFromFlag', 'BankValueSetFromInt',
        'BankValueSetFromString', 'BankSave']
    for name in names:
        declared = list(call_arities(native, name))
        assert declared, name
        assert set(call_arities(text, name)) == {declared[0]}, name


def test_bank_phase_protocol_preserves_missing_observations(parameters):
    _, phases = render_terrain_probe(parameters, RUN_ID)
    root = ET.Element('Bank')
    def section(name, values):
        element = ET.SubElement(root, 'Section', name=name)
        for key, (kind, value) in values.items():
            ET.SubElement(ET.SubElement(element, 'Key', name=key), 'Value', {kind: value})
    section('Run', {'RunId': ('string', RUN_ID), 'Status': ('string', 'FINISHED')})
    for name in phases:
        section(name, {'StageStatus': ('string', 'FINISHED'), 'StartedGameTime': ('fixed', '2.0'), 'FinishedGameTime': ('fixed', '47.0')})
    assertion = {'id': 'created_type', 'section': 'Buildings', 'key': 'legal_ground.CreatedType', 'operator': 'eq', 'expected': 'SupplyDepot'}
    parsed = parse_probe_bank(ET.tostring(root), RUN_ID, phases, [assertion])
    assert parsed['execution']['state'] == 'complete' and parsed['verdict'] == 'partial'
    assert parsed['assertions'][0]['result'] == 'not_observed'
    root.remove(next(element for element in root if element.get('name') == 'Boundary'))
    assert parse_probe_bank(ET.tostring(root), RUN_ID, phases)['execution']['state'] == 'partial'
