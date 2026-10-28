import hashlib
import json
from pathlib import Path
import struct
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.catalog import CatalogSession, inspect_catalog
from sc2_mcp.errors import SC2Error
from sc2_mcp.migration import inspect_migration, plan_migration
from sc2_mcp.shell import header_dependencies


def header(values):
    return b'H2CS' + struct.pack('<I', 8) + b'\x15' * 36 + struct.pack('<I', len(values)) + b''.join(value.encode() + b'\0' for value in values) + struct.pack('<I', 0)


def component(root, name, refs=(), objects=None):
    target = root / name
    target.mkdir(parents=True)
    (target / 'DocumentInfo').write_bytes(('<DocInfo><Dependencies>' + ''.join(f'<Value>{value}</Value>' for value in refs) + '</Dependencies></DocInfo>').encode())
    for kind, content in (objects or {}).items():
        data = target / f'Base.SC2Data/GameData/{kind}Data.xml'
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_bytes(('<Catalog>' + content + '</Catalog>').encode())
    return target


def template(root):
    target = component(root, 'Empty.SC2Mod')
    (target / 'DocumentHeader').write_bytes(header([]))
    (target / 'ComponentList.SC2Components').write_bytes(b'<Components><DataComponent Type="gada">GameData</DataComponent><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    return target


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}


def test_migration_local_catalog_closure_keeps_dependencies_and_exact_entries(tmp_path):
    base = component(tmp_path, 'Official.SC2Mod', objects={'Unit': '<CUnit id="Base"><LifeMax value="45"/></CUnit>'})
    unit = '<CUnit custom="preserve" id="Hero" parent="Base">\n<!-- local comment -->\n<WeaponArray Link="Gun"/>\n</CUnit>'
    source = component(tmp_path, 'Source.SC2Map', ['file:Official.SC2Mod'], {
        'Unit': unit + '<CUnit id="Unselected"/>',
        'Weapon': '<CWeaponLegacy id="Gun"><Effect value="Hit"/></CWeaponLegacy>',
        'Effect': '<CEffectDamage id="Hit"><Amount value="9"/></CEffectDamage>',
    })
    mod_template = template(tmp_path)
    before = snapshot(source), snapshot(mod_template)
    selected = [{'catalog': 'Unit', 'object_id': 'Hero'}]
    report = inspect_migration(source, selected, mod_template, [tmp_path])
    assert report['complete']
    assert {(row['catalog'], row['object_id']) for row in report['copied_objects']} == {('Unit', 'Hero'), ('Weapon', 'Gun'), ('Effect', 'Hit')}
    assert report['retained_dependency_objects'][0]['object_id'] == 'Base'
    changes = plan_migration(source, selected, mod_template, [tmp_path])
    raw = changes['Base.SC2Data/GameData/MigratedSelection.xml']
    assert unit.encode() in raw
    assert b'id="Unselected"' not in raw and b'id="Base"' not in raw
    assert header_dependencies(changes['DocumentHeader'])['values'] == ['file:Official.SC2Mod']
    assert before == (snapshot(source), snapshot(mod_template))
    target = tmp_path / 'TestOutput.SC2Mod'
    for relative, data in changes.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    result = inspect_catalog([base, target], 'Unit', 'Hero')
    assert result['fields']['LifeMax']['value'] == '45'
    assert result['fields']['WeaponArray[0].Link']['value'] == 'Gun'
    json.dumps(report)


def test_template_shell_is_mandatory_and_must_be_empty(tmp_path):
    source = component(tmp_path, 'Source.SC2Map', objects={'Unit': '<CUnit id="A"/>'})
    missing_shell = component(tmp_path, 'Bad.SC2Mod')
    selected = [{'catalog': 'Unit', 'object_id': 'A'}]
    with pytest.raises(SC2Error) as error:
        plan_migration(source, selected, missing_shell, allow_incomplete=True)
    assert error.value.code == 'mod_template_shell_missing'
    mod_template = template(tmp_path)
    data = mod_template / 'Base.SC2Data/GameData/UnitData.xml'
    data.parent.mkdir(parents=True)
    data.write_bytes(b'<Catalog><CUnit default="1"><LifeMax value="7"/></CUnit></Catalog>')
    with pytest.raises(SC2Error) as error:
        inspect_migration(source, selected, mod_template)
    assert error.value.code == 'nonempty_mod_template'


def test_missing_dependency_and_unknown_reference_are_never_complete(tmp_path):
    source = component(tmp_path, 'Source.SC2Map', ['file:Missing.SC2Mod'], {
        'Unit': '<CUnit id="A"><WeaponArray Link="Absent"/><Unknown value="B"/></CUnit><CUnit id="B"/>',
    })
    mod_template = template(tmp_path)
    selected = [{'catalog': 'Unit', 'object_id': 'A'}]
    report = inspect_migration(source, selected, mod_template)
    assert not report['complete']
    kinds = {issue['kind'] for issue in report['unresolved']}
    assert {'dependency_missing', 'missing_catalog_reference', 'unverified_reference_candidate'} <= kinds
    with pytest.raises(SC2Error) as error:
        plan_migration(source, selected, mod_template)
    assert error.value.code == 'migration_incomplete'
    candidate = plan_migration(source, selected, mod_template, allow_incomplete=True)
    assert b'id="A"' in candidate['Base.SC2Data/GameData/MigratedSelection.xml']
    assert b'id="B"' not in candidate['Base.SC2Data/GameData/MigratedSelection.xml']


def test_local_assets_and_referenced_localized_keys_are_copied(tmp_path):
    source = component(tmp_path, 'Source.SC2Map', objects={'Button': '<CButton id="B"><Icon value="Assets\\Textures\\icon.dds"/><Name value="Button/Name/B"/></CButton>'})
    asset = source / 'Assets/Textures/icon.dds'
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'DDS fixture bytes')
    strings = source / 'zhCN.SC2Data/LocalizedData/GameStrings.txt'
    strings.parent.mkdir(parents=True)
    strings.write_bytes('Button/Name/B=按钮\r\nButton/Name/Other=不迁移\r\n'.encode())
    mod_template = template(tmp_path)
    selected = [{'catalog': 'Button', 'object_id': 'B'}]
    report = inspect_migration(source, selected, mod_template)
    assert report['complete']
    candidate = plan_migration(source, selected, mod_template)
    assert candidate['Assets/Textures/icon.dds'] == b'DDS fixture bytes'
    assert candidate['zhCN.SC2Data/LocalizedData/GameStrings.txt'] == 'Button/Name/B=按钮\r\n'.encode()
    components = ET.fromstring(candidate['ComponentList.SC2Components'])
    assert any(item.get('Type') == 'text' and item.get('Locale') == 'zhCN' for item in components)


def test_model_embedded_assets_and_missing_texture_are_explicit(tmp_path):
    source = component(tmp_path, 'Source.SC2Map', objects={
        'Model': '<CModel id="M"><Model value="Assets/Models/Test.m3"/><Texture value="Assets/Textures/Missing.dds"/></CModel>',
    })
    model = source / 'Assets/Models/Test.m3'
    model.parent.mkdir(parents=True)
    model.write_bytes(b'model fixture')
    mod_template = template(tmp_path)
    report = inspect_migration(source, [{'catalog': 'Model', 'object_id': 'M'}], mod_template)
    kinds = {issue['kind'] for issue in report['unresolved']}
    assert not report['complete']
    assert {'embedded_model_assets_unverified', 'missing_asset'} <= kinds
    assert not any(issue['kind'] == 'missing_catalog_reference' and issue['edge']['to']['object_id'].endswith('.m3') for issue in report['unresolved'])


def test_session_source_entries_are_byte_exact_and_detect_late_source_changes(tmp_path):
    source = component(tmp_path, 'Source.SC2Map', objects={'Unit': '<CUnit id="A"><LifeMax value="45"/></CUnit>'})
    session = CatalogSession([source])
    entry = session.source_entries('Unit', 'A')[0]
    assert entry['xml'] == '<CUnit id="A"><LifeMax value="45"/></CUnit>'
    path = source / 'Base.SC2Data/GameData/UnitData.xml'
    path.write_bytes(path.read_bytes().replace(b'value="45"', b'value="60"'))
    with pytest.raises(SC2Error) as error:
        session.source_entries('Unit', 'A')
    assert error.value.code == 'catalog_source_changed'
