from pathlib import Path
import json
import pytest

from sc2_mcp import official_assets as official
from sc2_mcp.errors import SC2Error


def test_real_chinese_name_search_and_unit_not_skin():
    result = official.search('尤摩扬 陆战队员', 'Skin')
    assert [r['id'] for r in result['items']] == ['MarineUmojan']
    assert official.search('MarineUmojan', 'Unit')['count'] == 0
    assert result['map_dependency_status'] == 'not_checked'


def test_literal_asset_path_search_accepts_both_slash_styles():
    forward = official.search('Assets/Buildings/Zerg', 'Model')
    backward = official.search(r'Assets\Buildings\Zerg', 'Model')
    assert forward['count'] > 0
    assert forward == backward


@pytest.mark.parametrize('skin,from_model,to_model', [
    ('SiegeTankUmojan', 'SiegeTankSieged', 'SiegeTank_Umojan_Sieged'),
    ('WarpPrismGolden', 'WarpPrismPhasing', 'WarpPrism_Golden'),
    ('BanelingNestRCZ', 'BanelingNestDeathUnderConstruction', 'BanelingNest_RCZ_DeathUnderConstruction'),
])
def test_real_multiform_and_construction_replacements(skin,from_model,to_model):
    result = official.explain('Skin', skin, 'mods/liberty.sc2mod')
    rows = [r['expanded'] for r in result['replacement_observations']]
    assert any(r.get('From') == from_model and r.get('To') == to_model for r in rows)
    assert result['runtime'] == 'not_tested'
    assert result['array_semantics'] == 'ordered_declarations_only_not_engine_evaluated'


def test_model_template_core_fallback_and_scalar_override():
    result = official.explain('Skin', 'BanelingNestRCZ')
    model = next(m for m in result['target_models'] if m['model_id'] == 'BanelingNest_RCZ_Build')
    assert model['model_path_candidates'] == [r'Assets\Buildings\Zerg\ZergBuilding_RCZ_Build\ZergBuilding_RCZ_Build.m3']
    assert any(p.get('overridden_by_later_scalar') for p in model['paths'])
    marine = official.explain('Skin', 'MarineUmojan')['target_models'][0]
    assert marine['model_path_candidates'] == [r'Assets\Units\Terran\Marine_Umojan\Marine_Umojan.m3']
    assert any(i['code'] == 'core_template_observation' for i in marine['issues'])


def test_component_ambiguity_is_not_silently_merged():
    with pytest.raises(SC2Error, match='同ID') as error:
        official.explain('Unit', 'Marine')
    assert error.value.code == 'official_source_ambiguous'


def test_unindexed_and_bad_request_remain_explicit():
    with pytest.raises(SC2Error) as error:
        official.explain('Skin', 'DefinitelyNoSuchSkin_Validation')
    assert error.value.code == 'official_object_not_indexed'
    with pytest.raises(SC2Error): official.search('', 'Doodad')
    with pytest.raises(SC2Error): official.search('', limit=201)
    with pytest.raises(SC2Error): official.search('', offset=-1)


def test_tokens_cycles_and_missing_parent_do_not_become_facts():
    definitions = [{'tokens':[{'id':'unit'}], 'attributes':{'unit':'A'}}]
    assert official._context(definitions, 'B')['unit'] == 'A'
    assert '##' in official._expand('##a##', {'a':'##b##', 'b':'##a##'})
    row = {'template':False, 'definitions':[{'attributes':{'parent':'A'},'tokens':[],'fields':[]}]}
    _, issues = official._chain({('m','Skin','A'):row}, 'm','Skin','A')
    assert issues[0]['code'] == 'parent_cycle'
    _, issues = official._chain({}, 'm','Skin','Unknown')
    assert issues[0]['code'] == 'parent_not_in_component_snapshot'


def test_snapshot_has_portable_provenance_not_machine_paths():
    data = official._load()
    assert len(data['source_files']) >= 100
    assert data['coverage']['complete_game_asset_inventory'] is False
    raw = json.dumps(data, ensure_ascii=False).casefold()
    for needle in ['c:\\users\\administrator', 'e:\\ai', 'e:/ai', 'd:\\starcraft ii', '.sc2bank', 'api_key=']:
        assert needle not in raw
    assert official.search('战争宝箱', 'WarChest')['count'] == 24
    assert official.search('##', 'Skin')['count'] > 0


def test_pagination_and_returned_definitions_do_not_mutate_cache():
    first = official.search('', 'Skin', limit=2)
    second = official.search('', 'Skin', offset=first['next_offset'], limit=2)
    assert {r['id'] for r in first['items']}.isdisjoint(r['id'] for r in second['items'])
    result = official.explain('Skin','MarineUmojan')
    result['definitions'][0]['attributes']['id'] = 'damaged'
    assert official.explain('Skin','MarineUmojan')['definitions'][0]['attributes']['id'] != 'damaged'


def test_official_audit_keeps_knowledge_separate_from_map_dependency():
    report = official.audit('Skin', 'MarineUmojan')
    assert report['knowledge_status'] == 'passed'
    assert report['map_dependency_status']['status'] == 'not_checked' or report['map_dependency_status']['status'] in {'blocked', 'partial', 'passed'}
    assert report['editor'] == 'not_tested'
    json.dumps(report, ensure_ascii=False)

    context = {
        'complete': False,
        'dependency_report': {
            'complete': False,
            'nodes': [{'name': 'liberty.sc2mod'}],
            'missing': [{'kind': 'bnet', 'reference': 'bnet:unresolved'}],
            'cycles': [], 'incomplete': [],
        },
    }
    blocked = official.audit('Skin', 'MarineUmojan', source_context=context)
    assert blocked['knowledge_status'] == 'passed'
    assert blocked['map_dependency_status']['status'] == 'partial'
    assert blocked['map_dependency_status']['unresolved_bnet_count'] == 1
    assert blocked['blocked'] == []


@pytest.mark.asyncio
async def test_public_tools_are_scoped_readonly_and_do_not_write_map(tmp_path):
    from sc2_mcp.server import create_server
    root = tmp_path/'test.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo/>')
    server = create_server(tmp_path/'state')
    service = server.sc2_service
    try:
        key = service.projects.open(str(root), False)['project_id']
        tools = {t.name:t for t in await server.list_tools()}
        for name in ['sc2_official_assets_search','sc2_official_assets_explain']:
            assert tools[name].annotations.readOnlyHint is True
            from mcp.server.fastmcp.exceptions import ToolError
            with pytest.raises(ToolError):
                await server.call_tool(name, {'project_id': 'invalid', **({'catalog':'Skin','object_id':'MarineUmojan'} if name.endswith('explain') else {})})
        before = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
        response = await server.call_tool('sc2_official_assets_search', {'project_id':key,'query':'尤摩扬 陆战队员','catalog':'Skin'})
        assert 'MarineUmojan' in str(response)
        assert {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    finally:
        service.jobs.shutdown(cancel_pending=True)
