"""Bind requested dependencies to declarations, not implicit engine bootstrap."""
from copy import deepcopy

import pytest

from sc2_mcp import source_context as sources
from sc2_mcp.dependencies import analyze_dependency_impact
from sc2_mcp.errors import SC2Error


def contexts(tmp_path, explicit):
    root = tmp_path / 'Map.SC2Map'
    root.mkdir()
    (root / 'DocumentInfo').write_text('<DocInfo><Dependencies>' + ''.join(
        '<Value>' + ref + '</Value>' for ref in explicit) + '</Dependencies></DocInfo>')
    for name in ('A.SC2Mod', 'B.SC2Mod', 'Core.SC2Mod'):
        dep = tmp_path / name
        dep.mkdir()
        (dep / 'DocumentInfo').write_text('<DocInfo/>')
    before = sources.prepare_source_context(root, [tmp_path], tmp_path.parent / (tmp_path.name + '-cache'))
    after = sources.prepare_source_context(root, [tmp_path], tmp_path.parent / (tmp_path.name + '-cache'), dependency_values=explicit)
    for ctx in (before, after):
        node = next(n for n in ctx['dependency_report']['nodes'] if n['kind'] == 'root')
        node['dependencies'].insert(0, 'file:Core.SC2Mod')
        ctx['dependency_report']['edges'].insert(0, {
            'from': node['path'], 'to': str(tmp_path / 'Core.SC2Mod'),
            'reference': 'file:Core.SC2Mod', 'resolved': True,
            'source': {'file': str(tmp_path / 'official-cache.json'), 'ordinal': 0, 'line': None}})
        ctx['source_context_id'] = sources._context_id(ctx)
    return root, before, after


@pytest.mark.parametrize('explicit', [[], ['file:A.SC2Mod'], ['file:Core.SC2Mod', 'file:A.SC2Mod']])
def test_implicit_bootstrap_does_not_change_explicit_declaration_contract(tmp_path, explicit):
    root, before, after = contexts(tmp_path, explicit)
    report = analyze_dependency_impact(root, explicit, [tmp_path], ['Unit'], before_context=before, after_context=after)
    assert report['complete']
    assert report['counts']['changed_objects'] == 0


@pytest.mark.parametrize('requested', [[], ['file:B.SC2Mod', 'file:A.SC2Mod'],
                                    ['file:Core.SC2Mod', 'file:A.SC2Mod', 'file:B.SC2Mod']])
def test_bootstrap_does_not_hide_changed_or_reordered_explicit_declarations(tmp_path, requested):
    root, before, after = contexts(tmp_path, ['file:A.SC2Mod', 'file:B.SC2Mod'])
    with pytest.raises(SC2Error) as error:
        analyze_dependency_impact(root, requested, [tmp_path], ['Unit'], before_context=before, after_context=after)
    assert error.value.code == 'source_context_declarations_mismatch'


def test_before_context_still_must_match_real_document_info(tmp_path):
    root, before, after = contexts(tmp_path, ['file:A.SC2Mod', 'file:B.SC2Mod'])
    before = deepcopy(before)
    node = next(n for n in before['dependency_report']['nodes'] if n['kind'] == 'root')
    node['dependencies'][1:] = ['file:B.SC2Mod', 'file:A.SC2Mod']
    edges = [e for e in before['dependency_report']['edges'] if e['from'] == node['path'] and e['source']['file'] == node['metadata_source']]
    edges[0]['reference'], edges[1]['reference'] = edges[1]['reference'], edges[0]['reference']
    before['source_context_id'] = sources._context_id(before)
    with pytest.raises(SC2Error) as error:
        analyze_dependency_impact(root, ['file:A.SC2Mod', 'file:B.SC2Mod'], [tmp_path], ['Unit'], before_context=before, after_context=after)
    assert error.value.code == 'source_context_declarations_mismatch'
