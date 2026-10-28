"""Independent semantic tests. All artifacts stay below pytest --basetemp."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import struct
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp import source_context as sources
from sc2_mcp.catalog import inspect_catalog
from sc2_mcp.catalog_explain import catalog_explain
from sc2_mcp.catalog_patch import plan_catalog_patch
from sc2_mcp.dependencies import analyze_dependency_impact
from sc2_mcp.errors import SC2Error
from sc2_mcp.migration import inspect_migration
from sc2_mcp.service import Service


def put(root, name, value):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(value.encode('utf-8') if isinstance(value, str) else value)
    return target


def component(root, dependencies=(), objects='<CUnit id="A"><LifeMax value="45"/></CUnit>'):
    put(root, 'DocumentInfo', '<DocInfo><Dependencies>' + ''.join('<Value>' + reference + '</Value>' for reference in dependencies) + '</Dependencies></DocInfo>')
    put(root, 'Base.SC2Data/GameData/UnitData.xml', '<Catalog>' + objects + '</Catalog>')
    return root


def context(root, tmp, search=(), **kwargs):
    return sources.prepare_source_context(root, list(search), tmp / 'cache', **kwargs)


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def operation(action, **kwargs):
    return {'operation': action, 'catalog': 'Unit', 'object_id': 'A', **kwargs}


def materialize(root, changes):
    for name, raw in changes.items():
        put(root, name, raw)


def template(root):
    component(root, objects='')
    put(root, 'DocumentHeader', b'H2CS' + struct.pack('<I', 8) + b'\x15' * 36 + struct.pack('<II', 0, 0))
    put(root, 'ComponentList.SC2Components', '<Components><DataComponent Type="gada">GameData</DataComponent><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    return root


@pytest.mark.parametrize('mutation', ['nested_include_bytes', 'nested_include_removed', 'include_ambiguity_added'])
def test_nested_include_context_invalidates_on_content_presence_and_ambiguity(tmp_path, mutation):
    root = component(tmp_path / 'map')
    put(root, 'Base.SC2Data/GameData.xml', '<Includes><Catalog path="GameData/extra.xml"/></Includes>')
    put(root, 'Base.SC2Data/GameData/extra.xml', '<Catalog><Include path="deep.xml"/></Catalog>')
    target = put(root, 'Base.SC2Data/GameData/deep.xml', '<Catalog><CUnit id="Deep"/></Catalog>')
    saved = json.loads(json.dumps(context(root, tmp_path)))
    assert saved['complete'] and sources.assert_source_context_current(saved)['current']
    if mutation == 'nested_include_bytes':
        target.write_bytes(b'<Catalog><CUnit id="Different"/></Catalog>')
    elif mutation == 'nested_include_removed':
        target.unlink()
    else:
        put(root, 'Base.SC2Data/deep.xml', '<Catalog/>')
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(saved)
    assert error.value.code == 'source_context_stale'
    fresh = context(root, tmp_path)
    assert fresh['source_context_id'] != saved['source_context_id']
    if mutation != 'nested_include_bytes':
        assert not fresh['complete']


def fake_archive(monkeypatch, root, tmp):
    archive = put(tmp, 'external/A.SC2Mod', b'archive source hash version one')
    files = {'DocumentInfo': b'<DocInfo/>', 'Base.SC2Data/GameData/UnitData.xml': b'<Catalog><CUnit id="FromArchive"/></Catalog>'}
    @contextmanager
    def reader(path):
        assert path == archive
        def read(names):
            return {name.casefold(): (actual, raw) for name in names for actual, raw in files.items() if name.casefold() == actual.casefold()}
        yield read
    monkeypatch.setattr(sources, '_archive_reader', reader)
    component(root, ['file:A.SC2Mod'])
    return archive


@pytest.mark.parametrize('mutation', ['add_file', 'remove_file', 'change_manifest_identity'])
def test_sparse_archive_cache_rejects_inventory_and_identity_changes(tmp_path, monkeypatch, mutation):
    root = tmp_path / 'map'
    archive = fake_archive(monkeypatch, root, tmp_path)
    saved = context(root, tmp_path, [archive.parent])
    node = next(item for item in saved['dependency_report']['nodes'] if item['source_kind'] == 'mpq')
    cache = Path(node['materialized_root'])
    if mutation == 'add_file':
        put(cache, 'Base.SC2Data/unrequested.xml', '<Catalog/>')
    elif mutation == 'remove_file':
        target = cache / 'DocumentInfo'
        target.chmod(stat.S_IREAD | stat.S_IWRITE)
        target.unlink()
    else:
        manifest = cache.parent / 'manifest.json'
        data = json.loads(manifest.read_text('utf-8'))
        data['identity']['locale'] = 'enUS'
        manifest.chmod(stat.S_IREAD | stat.S_IWRITE)
        manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(SC2Error) as error:
        context(root, tmp_path, [archive.parent])
    assert error.value.code == 'source_cache_tampered'


def test_archive_hash_changes_create_new_cache_without_reusing_old_content(tmp_path, monkeypatch):
    root = tmp_path / 'map'
    archive = fake_archive(monkeypatch, root, tmp_path)
    first = context(root, tmp_path, [archive.parent])
    archive.write_bytes(b'archive source hash version two')
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(first)
    assert error.value.code == 'source_context_stale'
    second = context(root, tmp_path, [archive.parent])
    assert second['source_context_id'] != first['source_context_id']
    first_roots, second_roots = set(first['inventories']), set(second['inventories'])
    assert first_roots != second_roots


def test_resolved_sibling_dependency_must_not_receive_cache_writes(tmp_path):
    dependency = component(tmp_path / 'Dependency.SC2Mod')
    root = component(tmp_path / 'Map.SC2Map', ['file:Dependency.SC2Mod'])
    before = snapshot(dependency)
    try:
        with pytest.raises(SC2Error) as error:
            sources.prepare_source_context(root, [], dependency / 'cache')
        assert error.value.code == 'source_cache_in_source'
    finally:
        assert snapshot(dependency) == before, 'source preparation wrote a cache/lock into a resolved dependency'


@pytest.mark.parametrize('objects,field', [
    ('<CUnit id="A" parent="Missing"><LifeMax value="45"/></CUnit>', 'LifeMax'),
    ('<CUnit id="A"><WeaponArray Link="W"/></CUnit>', 'WeaponArray[0].Link'),
    ('<CUnit id="A"><WeaponArray index="0" Link="W" removed="0"/></CUnit>', 'WeaponArray[0].Link'),
    ('<CUnit default="1"><LifeMax value="45"/></CUnit><CUnit id="A"/>', 'LifeMax'),
    ('<CUnit id="A"><LifeMax value="$expression"/></CUnit>', 'LifeMax'),
])
def test_unknown_semantics_do_not_become_known_from_matching_caller_data(tmp_path, objects, field):
    root = component(tmp_path / 'map', objects=objects)
    saved = context(root, tmp_path)
    before = catalog_explain([root], 'Unit', 'A', [field], saved)['fields'][field]
    supplied = {'source_context_id': saved['source_context_id'], 'fields': {field: {'value': before['static']['value'], 'evidence_id': 'caller text is not client evidence'}}}
    after = catalog_explain([root], 'Unit', 'A', [field], saved, supplied)['fields'][field]
    assert before['status'] in {'partial', 'unknown'}
    assert after['status'] == before['status']
    assert after['static'] == before['static']


@pytest.mark.parametrize('action', ['set', 'clone'])
def test_missing_parent_rejects_scalar_candidate_and_selected_clone(tmp_path, action):
    dependency = component(tmp_path / 'dependency', objects='<CUnit id="A" parent="Absent"><LifeMax value="45"/></CUnit>')
    root = component(tmp_path / 'map', objects='')
    before = snapshot(root), snapshot(dependency)
    op = operation('set', field_path='LifeMax', value='50') if action == 'set' else operation('clone', object_id='New', source_id='A', fields=['LifeMax'])
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(root, [dependency, root], [op])
    assert error.value.code in {'catalog_structure_unknown', 'catalog_source_incomplete'}
    assert before == (snapshot(root), snapshot(dependency))


def test_array_remove_cannot_succeed_when_locale_restores_slot(tmp_path):
    root = component(tmp_path / 'map', objects='<CUnit id="A"><WeaponArray index="0" Link="W"/></CUnit>')
    put(root, 'zhCN.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="A"><WeaponArray index="0" Link="LocaleW" removed="0"/></CUnit></Catalog>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(root, [root, root / 'zhCN.SC2Data'], [operation('remove', field_path='WeaponArray[0]')])
    assert error.value.code == 'catalog_patch_shadowed'


def test_array_restore_cannot_succeed_when_locale_removes_slot(tmp_path):
    root = component(tmp_path / 'map', objects='<CUnit id="A"><WeaponArray index="0" Link="W"/></CUnit>')
    put(root, 'zhCN.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="A"><WeaponArray index="0" removed="1"/></CUnit></Catalog>')
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(root, [root, root / 'zhCN.SC2Data'], [operation('restore', field_path='WeaponArray[0]', attributes={'Link': 'Restored'})])
    assert error.value.code == 'catalog_patch_shadowed'


def test_empty_tombstones_are_not_reused_or_reindexed(tmp_path):
    root = component(tmp_path / 'map', objects='<CUnit id="A"><WeaponArray index="0"/><WeaponArray index="1" removed="1"/></CUnit>')
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        plan_catalog_patch(root, [root], [operation('append', field_path='WeaponArray[1]', attributes={'Link': 'W'})])
    assert error.value.code == 'catalog_append_index_mismatch'
    changes = plan_catalog_patch(root, [root], [operation('append', field_path='WeaponArray[2]', attributes={'Link': 'W'})])
    assert snapshot(root) == before
    nodes = ET.fromstring(next(iter(changes.values()))).find('CUnit')
    assert [node.get('index') for node in nodes] == ['0', '1', '2']


@pytest.mark.parametrize('bad', ['caller_fields', 'other_project', 'candidate', 'other_source', 'not_runtime', 'not_finished'])
def test_service_refuses_forged_or_wrongly_bound_runtime_observations(tmp_path, bad):
    root = component(tmp_path / 'map')
    saved = context(root, tmp_path)
    service = Service.__new__(Service)
    service.prepare_dependencies = lambda project_id: saved
    manifest = {'project_id': 'mine', 'template': 'catalog_snapshot', 'change_id': None, 'parameters': {'catalog': 'Unit', 'object_id': 'A'}, 'source_context': saved, 'probe_id': 'probe', 'archive_sha256': 'a' * 64, 'launch': {'build': {}}}
    result = {'binding': 'run_bound', 'execution': {'state': 'complete'}, 'run_state': 'finished', 'evidence_status': 'bound_runtime', 'bank': 'bank', 'bank_sha256': 'b' * 64, 'sections': {'Catalog': {'LifeMax': '45'}}}
    observations = {'probe_id': 'probe'}
    if bad == 'caller_fields': observations = {'source_context_id': saved['source_context_id'], 'fields': {'LifeMax': {'value': '45', 'evidence_id': 'fake'}}}
    elif bad == 'other_project': manifest['project_id'] = 'other'
    elif bad == 'candidate': manifest['change_id'] = 'candidate'
    elif bad == 'other_source': manifest['source_context'] = {'source_context_id': 'wrong'}
    elif bad == 'not_runtime': result['evidence_status'] = 'caller_attested'
    else: result['run_state'] = 'running'
    service.probes = SimpleNamespace(read=lambda _: manifest, collect=lambda _: result)
    with pytest.raises(SC2Error) as error:
        service.explain_catalog('mine', 'Unit', 'A', observations=observations)
    assert error.value.code in {'runtime_evidence_required', 'runtime_evidence_mismatch'}


def test_probe_candidate_source_mismatch_is_rejected_before_preparation(tmp_path):
    root = component(tmp_path / 'map')
    saved = context(root, tmp_path)
    service = Service.__new__(Service)
    service.record = lambda _: ({}, root)
    service.source_context = lambda *args: saved
    service.transactions = SimpleNamespace(read=lambda _: {'source_context_id': 'other'})
    def prepare(*args, **kwargs):
        pytest.fail('candidate with wrong source_context reached Probes.prepare')
    service.probes = SimpleNamespace(prepare=prepare)
    with pytest.raises(SC2Error) as error:
        service.prepare_probe('mine', 'catalog_snapshot', {}, saved['source_context_id'], 'candidate')
    assert error.value.code == 'source_context_mismatch'


def test_dependency_impact_uses_localized_materialized_roots_and_declaration_binding(tmp_path):
    dependency = component(tmp_path / 'deps/A.SC2Mod', objects='')
    put(dependency, 'zhCN.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="A"><LifeMax value="77"/></CUnit></Catalog>')
    root = component(tmp_path / 'map', objects='')
    search = [dependency.parent]
    before = context(root, tmp_path, search)
    after = context(root, tmp_path, search, dependency_values=['file:A.SC2Mod'])
    report = analyze_dependency_impact(root, ['file:A.SC2Mod'], search, ['Unit'], before_context=before, after_context=after)
    assert report['counts']['added_objects'] == 1 and report['complete']
    with pytest.raises(SC2Error) as error:
        analyze_dependency_impact(root, [], search, ['Unit'], before_context=before, after_context=after)
    assert error.value.code == 'source_context_declarations_mismatch'


def test_migration_uses_selected_locale_and_retains_incomplete_source_warning(tmp_path):
    root = component(tmp_path / 'map', ['bnet:unverified'], objects='<CUnit id="A"/>')
    put(root, 'zhCN.SC2Data/GameData/UnitData.xml', '<Catalog><CUnit id="A"><LifeMax value="77"/></CUnit></Catalog>')
    selected = context(root, tmp_path)
    report = inspect_migration(root, [{'catalog': 'Unit', 'object_id': 'A'}], template(tmp_path / 'empty.SC2Mod'), source_context=selected)
    assert not report['complete']
    assert any(item['kind'] == 'source_context_unknown' for item in report['unresolved'])
    assert report['source_context_id'] == selected['source_context_id']


def test_service_cross_source_override_rejects_new_missing_weapon_reference(tmp_path):
    dependency = component(tmp_path / 'dependency', objects='<CUnit id="A"><WeaponArray index="0" Link="Good"/></CUnit>')
    put(dependency, 'Base.SC2Data/GameData/WeaponData.xml', '<Catalog><CWeapon id="Good"/></Catalog>')
    root = component(tmp_path / 'map', ['file:dependency'], objects='')
    saved = context(root, tmp_path)
    service = Service.__new__(Service)
    service.state = tmp_path / 'state'
    service._prepare_context = lambda record: saved
    changes = plan_catalog_patch(root, [dependency, root], [operation('set', field_path='WeaponArray[0].Link', value='MissingWeapon')])
    before = snapshot(root), snapshot(dependency)
    with pytest.raises(SC2Error) as error:
        service._validate_candidate({'profile': 'general'}, root, changes, 'catalog')
    assert error.value.code == 'new_missing_references'
    assert before == (snapshot(root), snapshot(dependency))


def test_apply_rechecks_dependency_after_reference_validator_before_transaction_can_commit(tmp_path):
    dependency = component(tmp_path / 'dependency')
    root = component(tmp_path / 'map', ['file:dependency'], objects='')
    saved = context(root, tmp_path)
    service = Service.__new__(Service)
    service.state = tmp_path / 'state'
    service.record = lambda *args: ({'profile': 'general'}, root)
    service.editor_conflict = lambda: None
    payload = b'<Catalog><CUnit id="New"/></Catalog>'
    filename = 'Base.SC2Data/GameData/UnitData.xml'
    target = root / filename
    baseline = {name.replace('\\', '/'): value for name, value in snapshot(root).items()}
    put(service.state, 'changes/change/candidate/' + filename, payload)
    put(service.state, 'source-contexts/' + saved['source_context_id'] + '.json', json.dumps({'project_id': 'mine', 'context': saved}))
    manifest = {'state': 'prepared', 'root': str(root), 'label': 'catalog', 'source_context_id': saved['source_context_id'], 'baseline': baseline,
                'entries': [{'path': filename, 'before': hashlib.sha256(target.read_bytes()).hexdigest(), 'after': hashlib.sha256(payload).hexdigest()}]}
    reached_commit = []
    def validate(*args):
        put(dependency, filename, '<Catalog><CUnit id="ChangedDuringValidation"/></Catalog>')
        return {'static': 'passed'}
    def transaction_run(root, planner, *, validator, **kwargs):
        changes = planner()
        validator(changes)
        reached_commit.append(True)
        pytest.fail('stale dependency escaped to transaction commit')
    service._validate_candidate = validate
    service.transactions = SimpleNamespace(read=lambda _: manifest, run=transaction_run)
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        service.apply_candidate('mine', 'change')
    assert error.value.code == 'source_context_stale'
    assert snapshot(root) == before and not reached_commit


def test_persisted_context_cannot_be_loaded_by_other_project(tmp_path):
    root = component(tmp_path / 'map')
    saved = context(root, tmp_path)
    service = Service.__new__(Service)
    service.state = tmp_path / 'state'
    service.record = lambda _: ({}, root)
    put(service.state, 'source-contexts/' + saved['source_context_id'] + '.json', json.dumps({'project_id': 'original', 'context': saved}))
    with pytest.raises(SC2Error) as error:
        service.source_context('different', saved['source_context_id'])
    assert error.value.code == 'source_context_mismatch'


def test_bom_dependency_name_read_is_bound_readonly_and_local_override_wins(tmp_path):
    from sc2_mcp import keystone
    dependency = component(tmp_path / 'Names.SC2Mod', objects='<CUnit id="A"><Name value="Unit/Name/A"/></CUnit>')
    root = component(tmp_path / 'map', ['file:Names.SC2Mod'], objects='')
    raw = b'\xef\xbb\xbf' + 'Unit/Name/A=官方依赖名字\r\n'.encode('utf-8')
    put(dependency, keystone.TEXT, raw)
    put(root, keystone.TEXT, 'Unused=无关\r\n')
    saved = context(root, tmp_path)
    before = snapshot(root), snapshot(dependency)
    strings = keystone._Strings(root)
    result, identifier = keystone._unit_name_sources(root, strings, {'A'}, saved)
    assert result['A']['value'] == '官方依赖名字'
    assert Path(result['A']['source']) == dependency / keystone.TEXT
    assert identifier == saved['source_context_id']
    with pytest.raises(SC2Error) as error:
        keystone._Strings(dependency, dependency=True).set('Unit/Name/A', '不能改')
    assert error.value.code == 'keystone_dependency_readonly'
    assert before == (snapshot(root), snapshot(dependency))
    put(root, keystone.TEXT, 'Unit/Name/A=本图覆盖\r\n')
    fresh = context(root, tmp_path)
    result, _ = keystone._unit_name_sources(root, keystone._Strings(root), {'A'}, fresh)
    assert result['A']['value'] == '本图覆盖'
    assert Path(result['A']['source']) == root / keystone.TEXT
    assert (dependency / keystone.TEXT).read_bytes() == raw


@pytest.mark.parametrize('dependency,raw', [(False, b'\xef\xbb\xbfKey=Value'), (True, b'\xef\xbb\xbf\xef\xbb\xbfKey=Value'), (True, b'\xff\xfeK\0'), (True, b'Key=Value\0')])
def test_bom_patch_does_not_relax_other_encoding_rejections(tmp_path, dependency, raw):
    from sc2_mcp import keystone
    root = tmp_path / 'map'
    put(root, keystone.TEXT, raw)
    before = snapshot(root)
    with pytest.raises(SC2Error) as error:
        keystone._Strings(root, dependency=dependency)
    assert error.value.code == 'keystone_encoding'
    assert snapshot(root) == before


def test_value_attribute_array_append_remove_restore_remains_supported(tmp_path):
    root = component(tmp_path / 'map', objects='')
    put(root, 'Base.SC2Data/GameData/EffectData.xml', '<Catalog><CEffectSet id="Set"><EffectArray index="0" value="First"/></CEffectSet></Catalog>')
    def op(action, index, attributes=None):
        value = {'operation': action, 'catalog': 'Effect', 'object_id': 'Set', 'field_path': 'EffectArray[' + str(index) + ']'}
        if attributes is not None:
            value['attributes'] = attributes
        return value
    before = snapshot(root)
    changes = plan_catalog_patch(root, [root], [op('remove', 0), op('append', 1, {'value': 'Second'}), op('restore', 0, {'value': 'Restored'})])
    assert snapshot(root) == before
    materialize(root, changes)
    fields = inspect_catalog([root], 'Effect', 'Set')['fields']
    assert fields['EffectArray[0]']['value'] == 'Restored'
    assert fields['EffectArray[1]']['value'] == 'Second'


@pytest.mark.parametrize('middle_kind', ['directory', 'synthetic_archive'])
def test_cache_preflight_recurses_through_sibling_directory_and_archive_metadata_before_writes(tmp_path, monkeypatch, middle_kind):
    leaf = component(tmp_path / 'Leaf.SC2Mod')
    root = component(tmp_path / 'Map.SC2Map', ['file:Middle.SC2Mod'])
    if middle_kind == 'directory':
        middle = component(tmp_path / 'Middle.SC2Mod', ['file:Leaf.SC2Mod'])
    else:
        middle = put(tmp_path, 'Middle.SC2Mod', b'synthetic archive: metadata read mocked')
        @contextmanager
        def reader(path):
            assert path == middle
            yield lambda names: {'documentinfo': ('DocumentInfo', b'<DocInfo><Dependencies><Value>file:Leaf.SC2Mod</Value></Dependencies></DocInfo>')}
        monkeypatch.setattr(sources, '_archive_reader', reader)
    before = snapshot(leaf)
    with pytest.raises(SC2Error) as error:
        sources.prepare_source_context(root, [], leaf / 'cache')
    assert error.value.code == 'source_cache_in_source'
    assert snapshot(leaf) == before
    assert not (leaf / 'cache').exists()


def test_restore_does_not_implicitly_revive_payload_omitted_by_caller(tmp_path):
    root = component(tmp_path / 'map', objects='<CUnit id="A"><WeaponArray index="0" Link="Old" Turret="OldTurret"/></CUnit>')
    operations = [operation('remove', field_path='WeaponArray[0]'),
                  operation('restore', field_path='WeaponArray[0]', attributes={'Link': 'New'})]
    before = snapshot(root)
    try:
        changes = plan_catalog_patch(root, [root], operations)
    except SC2Error as error:
        assert error.code in {'catalog_array_payload_required', 'catalog_array_payload_incomplete'}
        assert snapshot(root) == before
        return
    assert snapshot(root) == before
    materialize(root, changes)
    fields = inspect_catalog([root], 'Unit', 'A')['fields']
    assert fields['WeaponArray[0].Link']['value'] == 'New'
    assert 'WeaponArray[0].Turret' not in fields, 'restore silently revived an omitted old Turret payload'
