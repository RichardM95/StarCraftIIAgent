import hashlib
from pathlib import Path

from sc2_mcp.catalog_patch import plan_catalog_patch, plan_catalog_patch_report
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot


def put(root, raw, kind='Unit'):
    path = root / ('Base.SC2Data/GameData/' + kind + 'Data.xml')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<Catalog>' + raw + '</Catalog>', encoding='utf-8')
    return path


def op(action='set', **parameters):
    return {'operation': action, 'catalog': 'Unit', 'object_id': 'A', **parameters}


def test_numeric_changes_propagate_to_inheritors_and_reverse_references(tmp_path):
    root = tmp_path / 'map'
    put(root, '<CUnit id="A"><LifeMax value="45"/></CUnit><CUnit id="Child" parent="A"/>')
    put(root, '<CEffectCreateUnit id="Spawn"><SpawnUnit value="Child"/></CEffectCreateUnit>', 'Effect')
    original = snapshot(root)
    parameters = [op(field_path='LifeMax', value='60')]
    result = plan_catalog_patch_report(root, [root], parameters)
    assert result['changes'] == plan_catalog_patch(root, [root], parameters)
    report = result['report']
    assert {(row['object_id'], row['field']) for row in report['numeric_changes']} == {('A', 'LifeMax'), ('Child', 'LifeMax')}
    assert {row['object_id'] for row in report['potentially_impacted_objects']} == {'A', 'Child', 'Spawn'}
    assert report['reference_changes']['added'] == report['reference_changes']['removed'] == []
    assert report['engine_parity'] is False
    assert original == snapshot(root)


def test_equal_dependency_override_is_source_only_not_numeric_or_structural(tmp_path):
    dep, root = tmp_path / 'dep', tmp_path / 'map'
    put(dep, '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    root.mkdir()
    result = plan_catalog_patch_report(root, [dep, root], [op(field_path='LifeMax', value='45')])
    report = result['report']
    assert report['value_changes'] == report['numeric_changes'] == report['structural_changes'] == []
    assert len(report['source_only_changes']) == 1
    row = report['source_only_changes'][0]
    assert row['field'] == 'LifeMax'
    assert Path(row['before']['source']['root']) == dep
    assert Path(row['after']['source']['root']) == root


def test_unrelated_fields_do_not_change_ownership_when_file_hash_changes(tmp_path):
    root = tmp_path / 'map'
    put(root, '<CUnit id="A"><LifeMax value="45"/><Speed value="3"/></CUnit><CUnit id="Other"><LifeMax value="99"/></CUnit>')
    report = plan_catalog_patch_report(root, [root], [op(field_path='LifeMax', value='50')])['report']
    assert report['source_only_changes'] == []
    assert [row['field'] for row in report['value_changes']] == ['LifeMax']
    assert [row['object_id'] for row in report['objects']] == ['A']


def test_reference_retarget_and_tombstone_are_separate_from_numeric_changes(tmp_path):
    root = tmp_path / 'map'
    put(root, '<CUnit id="A"><WeaponArray index="0" Link="W1"/><WeaponArray index="1"/></CUnit>')
    put(root, '<CWeapon id="W1"/><CWeapon id="W2"/>', 'Weapon')
    result = plan_catalog_patch_report(root, [root], [op(field_path='WeaponArray[0].Link', value='W2'), op('remove', field_path='WeaponArray[1]')])
    report = result['report']
    assert report['numeric_changes'] == []
    assert report['value_changes'][0]['value_type'] == 'literal'
    assert [row['to']['object_id'] for row in report['reference_changes']['removed']] == ['W1']
    assert [row['to']['object_id'] for row in report['reference_changes']['added']] == ['W2']
    assert any(row['kind'] == 'node_shape' for row in report['structural_changes'])


def test_creating_missing_target_reports_resolution_change_and_impact(tmp_path):
    root = tmp_path / 'map'
    put(root, '<CUnit id="Consumer"><WeaponArray index="0" Link="W"/></CUnit>')
    operation = {'operation':'create', 'catalog':'Weapon', 'object_id':'W', 'class':'CWeapon', 'fields':{'Period':'1'}}
    report = plan_catalog_patch_report(root, [root], [operation])['report']
    assert report['reference_changes']['removed'][0]['resolved'] is False
    assert report['reference_changes']['added'][0]['resolved'] is True
    assert {row['object_id'] for row in report['potentially_impacted_objects']} == {'W', 'Consumer'}
    assert any(row['kind'] == 'exists' for row in report['structural_changes'])


def test_candidate_service_persists_bound_report_and_retains_original_transaction(tmp_path, monkeypatch):
    root = tmp_path / 'map.SC2Map'
    put(root, '<CUnit id="A"><LifeMax value="45"/></CUnit>')
    (root / 'DocumentInfo').write_bytes(b'<DocInfo/>')
    (root / 'MapScript.galaxy').write_bytes(b'void InitMap () {}\n')
    service = Service(tmp_path / 'state')
    monkeypatch.setattr(service, 'editor_conflict', lambda: None)
    project = service.projects.open(str(root), True)
    before = snapshot(root)
    try:
        candidate = service.prepare_catalog_patch(project['project_id'], [op(field_path='LifeMax', value='50')])
        report = candidate['impact_report']
        assert report['source_context_id'] == candidate['source_context_id']
        manifest = service.transactions.read(candidate['change_id'])
        assert manifest['impact_report'] == report
        for path, row in report['candidate_files'].items():
            raw = (service.state / 'changes' / candidate['change_id'] / 'candidate' / path).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
        assert before == snapshot(root)
        applied = service.apply_candidate(project['project_id'], candidate['change_id'])
        assert b'50' in (root / 'Base.SC2Data/GameData/UnitData.xml').read_bytes()
        service.transactions.rollback(applied['change_id'], root)
        assert before == snapshot(root)
    finally:
        service.jobs.shutdown()
