from pathlib import Path

from sc2_mcp.dependencies import analyze_dependency_impact


def component(root, name, refs=(), units=''):
    path = root / name
    path.mkdir(parents=True)
    (path / 'DocumentInfo').write_text('<DocInfo><Dependencies>' + ''.join(f'<Value>{ref}</Value>' for ref in refs) + '</Dependencies></DocInfo>', encoding='utf-8')
    if units:
        data = path / 'Base.SC2Data/GameData'
        data.mkdir(parents=True)
        (data / 'UnitData.xml').write_text('<Catalog>' + units + '</Catalog>', encoding='utf-8')
    return path


def test_before_after_reports_add_remove_changed_fields_and_sources(tmp_path):
    root = component(tmp_path, 'Map.SC2Map', ['file:A.SC2Mod'], '<CUnit id="Child" parent="Marine"/>')
    a = component(tmp_path, 'A.SC2Mod', units='<CUnit id="Marine"><LifeMax value="40"/></CUnit><CUnit id="Old"/>')
    b = component(tmp_path, 'B.SC2Mod', units='<CUnit id="Marine"><LifeMax value="60"/></CUnit><CUnit id="New"/>')
    result = analyze_dependency_impact(root, ['file:B.SC2Mod'], [tmp_path], ['Unit'])
    assert result['complete']
    assert result['counts']['added_objects'] == result['counts']['removed_objects'] == 1
    assert result['counts']['changed_objects'] == 2
    assert result['added'][0]['object_id'] == 'New'
    assert result['removed'][0]['object_id'] == 'Old'
    child = next(item for item in result['changed'] if item['object_id'] == 'Child')
    life = next(item for item in child['fields'] if item['field'] == 'LifeMax')
    assert life['before']['value'] == '40' and life['after']['value'] == '60'
    assert life['before']['source']['root'] == str(a.resolve())
    assert life['after']['source']['root'] == str(b.resolve())
    assert (root / 'DocumentInfo').read_text(encoding='utf-8').find('file:A.SC2Mod') >= 0


def test_impact_limit_only_truncates_details_not_counts(tmp_path):
    root = component(tmp_path, 'Map.SC2Map', ['file:A.SC2Mod'])
    component(tmp_path, 'A.SC2Mod', units='<CUnit id="A"/><CUnit id="B"/>')
    component(tmp_path, 'B.SC2Mod', units='<CUnit id="C"/><CUnit id="D"/>')
    result = analyze_dependency_impact(root, ['file:B.SC2Mod'], [tmp_path], ['Unit'], limit=1)
    assert result['counts']['added_objects'] == 2
    assert result['counts']['removed_objects'] == 2
    assert len(result['added']) + len(result['removed']) == 1
    assert result['truncated']


def test_impact_unknown_graph_and_unchanged_graph(tmp_path):
    root = component(tmp_path, 'Map.SC2Map', [], '<CUnit id="A"><LifeMax value="1"/></CUnit>')
    unchanged = analyze_dependency_impact(root, [], [], ['Unit'])
    assert unchanged['complete'] and not unchanged['changed']
    changed = analyze_dependency_impact(root, ['bnet:Unavailable'], [], ['Unit'])
    assert not changed['complete']
    assert changed['unresolved'][0]['kind'] == 'missing'
