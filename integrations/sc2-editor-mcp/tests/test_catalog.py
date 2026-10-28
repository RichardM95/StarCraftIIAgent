from pathlib import Path
import json
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.catalog import inspect_catalog, plan_catalog_set, search_catalog, trace_references
from sc2_mcp.errors import SC2Error


def put(root: Path, relative: str, content: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


def cat(root: Path, text: str, kind: str = "Unit") -> Path:
    return put(root, f"Base.SC2Data/GameData/{kind}Data.xml", f"<Catalog>{text}</Catalog>")


def val(result: dict, path: str) -> str:
    return result["fields"][path]["value"]


def test_standard_files_and_manifest_includes_exclude_unattached_and_backups(tmp_path):
    cat(tmp_path, '<CUnit id="Marine"><LifeMax value="45"/></CUnit>')
    put(tmp_path, 'Base.SC2Data/GameData.xml', '<Includes><Catalog path="GameData/Custom.xml"/></Includes>')
    put(tmp_path, 'Base.SC2Data/GameData/Custom.xml', '<Catalog><CUnit id="Marine"><LifeMax value="50"/></CUnit><CUnit id="Custom"/></Catalog>')
    put(tmp_path, 'Base.SC2Data/GameData/Unattached.xml', '<Catalog><CUnit id="Inactive"/></Catalog>')
    put(tmp_path, '_codex_backups/Base.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="Backup"/></Catalog>')
    put(tmp_path, 'Base.SC2Data/GameData/UnitData.backup.xml', '<Catalog><CUnit id="OtherBackup"/></Catalog>')
    put(tmp_path, 'zhCN.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="Marine"><LifeMax value="80"/></CUnit></Catalog>')
    result = inspect_catalog([tmp_path], 'Unit', 'Marine')
    assert val(result, 'LifeMax') == '50'
    assert result['fields']['LifeMax']['source']['file'].endswith('Custom.xml')
    assert result['fields']['LifeMax']['history'][0]['value'] == '45'
    assert {entry['object_id'] for entry in search_catalog([tmp_path], 'Unit')} == {'Marine', 'Custom'}
    assert any(w['code'] == 'locale_not_selected' for w in result['warnings'])
    assert val(inspect_catalog([tmp_path, tmp_path / 'zhCN.SC2Data'], 'Unit', 'Marine'), 'LifeMax') == '80'
    assert result['engine_parity'] is False
    json.dumps(result)


def test_includes_nested_case_insensitive_and_missing(tmp_path):
    put(tmp_path, 'base.sc2data/GameData.xml', '<Includes><Catalog path="gamedata/Custom.XML"/></Includes>')
    put(tmp_path, 'base.sc2data/GameData/custom.xml', '<Catalog><Include path="More.xml"/><CUnit id="A"/></Catalog>')
    put(tmp_path, 'base.sc2data/GameData/More.xml', '<Catalog><CUnit id="B"/></Catalog>')
    assert {e['object_id'] for e in search_catalog([tmp_path], 'Unit')} == {'A', 'B'}
    (tmp_path / 'base.sc2data/GameData/More.xml').unlink()
    with pytest.raises(SC2Error) as error:
        search_catalog([tmp_path], 'Unit')
    assert error.value.code == 'missing_catalog_include'


@pytest.mark.parametrize('include,code', [('../outside.xml', 'unsafe_catalog_path'), ('GameData.xml', 'catalog_include_cycle')])
def test_unsafe_or_cyclic_include_rejected(tmp_path, include, code):
    put(tmp_path, 'Base.SC2Data/GameData.xml', f'<Includes><Catalog path="{include}"/></Includes>')
    with pytest.raises(SC2Error) as error:
        search_catalog([tmp_path], 'Unit')
    assert error.value.code == code


def test_class_defaults_templates_inheritance_and_overlay(tmp_path):
    base, patch = tmp_path / 'base', tmp_path / 'patch'
    cat(base, '''<CUnit default="1"><LifeMax value="1"/><Speed value="2"/></CUnit>
        <CUnit default="1" id="Template"><LifeMax value="300"/></CUnit>
        <CUnit id="Parent"><LifeMax value="45"/><WeaponArray Link="Rifle"/><CostResource index="Minerals" value="50"/></CUnit>
        <CUnit id="Child" parent="Parent"><LifeMax value="55"/></CUnit>
        <CUnit id="Unrelated"/>
        <CUnit id="UsesTemplate" parent="Template"/>''')
    cat(patch, '<CUnit id="Parent"><LifeMax value="60"/></CUnit><CUnit id="Child"><Speed value="4"/></CUnit>')
    result = inspect_catalog([base, patch], 'Unit', 'Child')
    assert val(result, 'LifeMax') == '55'
    assert val(result, 'Speed') == '4'
    assert val(result, 'WeaponArray[0].Link') == 'Rifle'
    assert val(result, 'CostResource[Minerals]') == '50'
    assert result['inheritance'] == ['Parent']
    assert result['fields']['CostResource[Minerals]']['source']['object_id'] == 'Parent'
    assert val(inspect_catalog([base, patch], 'Unit', 'Unrelated'), 'LifeMax') == '1'
    assert val(inspect_catalog([base, patch], 'Unit', 'UsesTemplate'), 'LifeMax') == '300'
    assert next(e for e in search_catalog([base], 'Unit') if e['object_id'] == 'Template')['template']


def test_array_merge_append_remove_tombstone_and_nested_fields(tmp_path):
    base, patch = tmp_path / 'base', tmp_path / 'patch'
    cat(base, '''<CUnit id="A"><WeaponArray Link="W1"/><WeaponArray Link="W2"/>
        <CardLayouts index="0"><LayoutButtons index="0" Face="Attack" Row="0"/></CardLayouts></CUnit>''')
    cat(patch, '''<CUnit id="A"><WeaponArray index="1" removed="1"/>
        <WeaponArray Link="W3"/><WeaponArray index="0" Turret="T"/>
        <CardLayouts index="0"><LayoutButtons index="0" Column="2"/></CardLayouts></CUnit>''')
    result = inspect_catalog([base, patch], 'Unit', 'A')
    assert val(result, 'WeaponArray[0].Link') == 'W1'
    assert val(result, 'WeaponArray[0].Turret') == 'T'
    assert val(result, 'WeaponArray[2].Link') == 'W3'
    assert 'WeaponArray[1].Link' not in result['fields']
    assert result['removed'][0]['path'] == 'WeaponArray[1]'
    assert result['removed'][0]['source']['operation'] == 'remove'
    assert val(result, 'CardLayouts[0].LayoutButtons[0].Face') == 'Attack'
    assert val(result, 'CardLayouts[0].LayoutButtons[0].Column') == '2'


def test_effect_array_without_array_suffix_and_revival(tmp_path):
    base, patch = tmp_path / 'base', tmp_path / 'patch'
    cat(base, '<CEffectSet id="S"><EffectArray value="A"/><EffectArray value="B"/></CEffectSet>', 'Effect')
    cat(patch, '<CEffectSet id="S"><EffectArray index="0" removed="1"/><EffectArray index="0" value="C"/></CEffectSet>', 'Effect')
    result = inspect_catalog([base, patch], 'Effect', 'S')
    assert val(result, 'EffectArray[0]') == 'C'
    assert not result['removed']


def test_parent_missing_cycle_and_uninterpreted_token(tmp_path):
    cat(tmp_path, '<CUnit id="A" parent="Missing"><Name value="Unit/Name/##id##"/></CUnit>')
    result = inspect_catalog([tmp_path], 'Unit', 'A')
    assert {w['code'] for w in result['warnings']} >= {'missing_catalog_parent', 'unevaluated_catalog_expression'}
    cat(tmp_path, '<CUnit id="A" parent="B"/><CUnit id="B" parent="A"/>')
    with pytest.raises(SC2Error) as error:
        inspect_catalog([tmp_path], 'Unit', 'A')
    assert error.value.code == 'catalog_parent_cycle'


def test_reference_chain_and_missing_typed_reference(tmp_path):
    cat(tmp_path, '<CUnit id="Marine"><WeaponArray Link="Rifle"/><AbilArray Link="MissingAbility"/></CUnit>')
    cat(tmp_path, '<CWeaponLegacy id="Rifle"><Effect value="Hit"/></CWeaponLegacy>', 'Weapon')
    cat(tmp_path, '<CEffectDamage id="Hit"><Amount value="6"/></CEffectDamage>', 'Effect')
    result = trace_references([tmp_path], 'Unit', 'Marine')
    assert result['outgoing'][0]['to'] == {'catalog': 'Weapon', 'object_id': 'Rifle'}
    assert {'catalog': 'Effect', 'object_id': 'Hit'} in result['reachable']
    assert result['missing'][0]['to'] == {'catalog': 'Abil', 'object_id': 'MissingAbility'}
    assert trace_references([tmp_path], 'Effect', 'Hit')['incoming'][0]['from']['object_id'] == 'Rifle'
    json.dumps(result)


def test_edit_preserves_every_unrelated_byte_and_does_not_write(tmp_path):
    before = ('<?xml version="1.0" encoding="utf-8"?>\r\n<Catalog>\r\n'
              '  <!-- 中文 <CUnit id="Marine"><LifeMax value="0"/></CUnit> -->\r\n'
              '  <CUnit id="Other"><LifeMax value="45"/></CUnit>\r\n'
              '  <CUnit custom="preserve" id="Marine">\r\n'
              '    <LifeMax tooltip="value=\'pretend\'" value = \'45\'/>\r\n'
              '    <Unknown data="keep"/>\r\n'
              '  </CUnit>\r\n</Catalog>\r\n').encode()
    path = put(tmp_path, 'Base.SC2Data/GameData/UnitData.xml', before)
    changes = plan_catalog_set(tmp_path, 'Unit', 'Marine', 'LifeMax', '60', expected='45')
    assert changes == {'Base.SC2Data/GameData/UnitData.xml': before.replace(b"value = '45'", b"value = '60'")}
    assert path.read_bytes() == before
    assert plan_catalog_set(tmp_path, 'Unit', 'Marine', 'LifeMax', '45') == {}


def test_indexed_attribute_and_nested_value_edits(tmp_path):
    before = b'<Catalog><CUnit id="A"><WeaponArray index="0" Link="Old"/><Cost index="0"><Cooldown TimeUse="10"/></Cost></CUnit></Catalog>'
    put(tmp_path, 'Base.SC2Data/GameData/UnitData.xml', before)
    changes = plan_catalog_set(tmp_path, 'Unit', 'A', 'WeaponArray[0].Link', 'New')
    assert next(iter(changes.values())) == before.replace(b'Link="Old"', b'Link="New"')
    changes = plan_catalog_set(tmp_path, 'Unit', 'A', 'Cost[0].Cooldown.TimeUse', '12')
    assert next(iter(changes.values())) == before.replace(b'TimeUse="10"', b'TimeUse="12"')
    changes = plan_catalog_set(tmp_path, 'Unit', 'A', 'Cost[0].Cooldown.@Custom', 'A&B"<')
    parsed = ET.fromstring(next(iter(changes.values())))
    assert parsed.find('.//Cooldown').get('Custom') == 'A&B"<'


def test_add_missing_scalar_and_nested_path_to_self_closing_object(tmp_path):
    before = b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>\r\n<Catalog>\r\n    <CUnit id="A"/>\r\n</Catalog>\r\n'
    path = put(tmp_path, 'Base.SC2Data/GameData/UnitData.xml', before)
    changes = plan_catalog_set(tmp_path, 'Unit', 'A', 'LifeMax', '80')
    candidate = next(iter(changes.values()))
    assert candidate.startswith(b'\xef\xbb\xbf')
    assert b'\n' not in candidate.replace(b'\r\n', b'')
    assert ET.fromstring(candidate).find('.//LifeMax').get('value') == '80'
    assert path.read_bytes() == before
    changes = plan_catalog_set(tmp_path, 'Unit', 'A', 'Cost[0].Cooldown.TimeUse', '12')
    assert ET.fromstring(next(iter(changes.values()))).find('.//Cost/Cooldown').get('TimeUse') == '12'


def test_ascii_declaration_uses_character_references(tmp_path):
    put(tmp_path, 'Base.SC2Data/GameData/UnitData.xml', b'<?xml version="1.0" encoding="us-ascii"?><Catalog><CUnit id="A"><Name value="old"/></CUnit></Catalog>')
    candidate = next(iter(plan_catalog_set(tmp_path, 'Unit', 'A', 'Name', '中文').values()))
    candidate.decode('ascii')
    assert ET.fromstring(candidate).find('.//Name').get('value') == '中文'


@pytest.mark.parametrize('body,path,code', [
    ('<CUnit id="A"/><CUnit id="A"/>', 'LifeMax', 'ambiguous_catalog_object'),
    ('<CUnit id="A"><LifeMax value="1"/><LifeMax value="2"/></CUnit>', 'LifeMax', 'ambiguous_catalog_field'),
    ('<CUnit id="A"><WeaponArray Link="One"/></CUnit>', 'WeaponArray[0].Link', 'ambiguous_unindexed_array'),
    ('<CUnit id="A"><WeaponArray index="0" Link="One"/></CUnit>', 'WeaponArray.Link', 'catalog_array_index_required'),
    ('<CUnit id="A"><WeaponArray index="0" removed="1"/></CUnit>', 'WeaponArray[0].Link', 'catalog_field_removed'),
    ('<CUnit id="A"/>', 'parent', 'catalog_identity_edit_forbidden'),
    ('<CUnit id="A"/>', '@id', 'catalog_identity_edit_forbidden'),
    ('<CUnit id="A"/>', 'LifeMax[', 'invalid_catalog_field_path'),
    ('<CUnit id="A"/>', 'WeaponArray[0].@removed', 'catalog_identity_edit_forbidden'),
])
def test_ambiguous_and_identity_edits_fail(tmp_path, body, path, code):
    cat(tmp_path, body)
    with pytest.raises(SC2Error) as error:
        plan_catalog_set(tmp_path, 'Unit', 'A', path, '2')
    assert error.value.code == code


def test_expected_value_check_uses_local_value(tmp_path):
    cat(tmp_path, '<CUnit id="A"><LifeMax value="40"/></CUnit>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_set(tmp_path, 'Unit', 'A', 'LifeMax', '60', expected='45')
    assert error.value.code == 'catalog_expected_mismatch'
    with pytest.raises(SC2Error) as error:
        plan_catalog_set(tmp_path, 'Unit', 'A', 'Speed', '2', expected='1')
    assert error.value.details['actual'] is None


def test_missing_object_unsupported_type_limit_and_entity_rejected(tmp_path):
    cat(tmp_path, '<CUnit id="A"/>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_set(tmp_path, 'Unit', 'Absent', 'LifeMax', '1')
    assert error.value.code == 'catalog_object_not_found'
    with pytest.raises(SC2Error) as error:
        search_catalog([tmp_path], 'NoSuchCatalog')
    assert error.value.code == 'unsupported_catalog'
    with pytest.raises(SC2Error) as error:
        search_catalog([tmp_path], 'Unit', limit=0)
    assert error.value.code == 'invalid_catalog_limit'
    put(tmp_path, 'Base.SC2Data/GameData/UnitData.xml', '<!DOCTYPE x [<!ENTITY e "bad">]><Catalog><CUnit id="A"/></Catalog>')
    with pytest.raises(SC2Error) as error:
        inspect_catalog([tmp_path], 'Unit', 'A')
    assert error.value.code == 'unsafe_xml'


def test_mixed_catalog_entries_are_read_by_type_not_filename(tmp_path):
    cat(tmp_path, '<CUnit id="A"/><CSound id="Voice"/><CTerrainTex id="Sand"/>')
    assert inspect_catalog([tmp_path], 'Sound', 'Voice')['class'] == 'CSound'
    assert inspect_catalog([tmp_path], 'TerrainTex', 'Sand')['class'] == 'CTerrainTex'


def test_search_filter_limit_and_stable_sort(tmp_path):
    cat(tmp_path, '<CUnit id="Zulu"/><CUnit id="Alpha"/><CUnit id="alphabet"/>')
    result = search_catalog([tmp_path], 'unit', query='ALP', limit=1)
    assert result[0]['object_id'] == 'Alpha'


def test_reference_trace_uses_final_parent_and_reports_transitive_missing(tmp_path):
    base, patch = tmp_path / 'base', tmp_path / 'patch'
    cat(base, '<CUnit id="A" parent="Old"/><CUnit id="Old"/><CUnit id="New"><WeaponArray Link="Gun"/></CUnit>')
    cat(base, '<CWeaponLegacy id="Gun"><Effect value="MissingDamage"/></CWeaponLegacy>', 'Weapon')
    cat(patch, '<CUnit id="A" parent="New"/>')
    result = trace_references([base, patch], 'Unit', 'A')
    assert {'catalog': 'Unit', 'object_id': 'Old'} not in result['reachable']
    assert any(item['from']['object_id'] == 'Gun' and item['to']['object_id'] == 'MissingDamage' for item in result['missing'])
