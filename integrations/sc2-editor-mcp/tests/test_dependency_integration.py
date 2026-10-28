"""Regression fixtures for real SC2 combined depot/file dependency syntax."""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.dependencies import plan_dependencies, resolve_dependencies
from sc2_mcp.errors import SC2Error


def component(root: Path, name: str, xml: str = '<DocInfo/>') -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / 'DocumentInfo').write_bytes(xml.encode('utf-8'))
    return path


def test_actual_keystone_combined_dependency_syntax(tmp_path):
    first = 'bnet:Co-op Mission/0.0/999,file:Mods/StarCoop/StarCoop.SC2Mod'
    second = 'bnet:Void Multi (Mod)/0.0/999,file:Mods/VoidMulti.SC2Mod'
    root = component(tmp_path, 'test.SC2Map', f'<DocInfo><Dependencies><Value>{first}</Value><Value>{second}</Value></Dependencies></DocInfo>')
    coop = component(tmp_path, 'Mods/StarCoop/StarCoop.SC2Mod')
    multi = component(tmp_path, 'Mods/VoidMulti.SC2Mod')
    result = resolve_dependencies(root, [tmp_path])
    assert result['complete']
    assert result['load_order'] == [str(coop.resolve()), str(multi.resolve()), str(root.resolve())]
    assert result['edges'][0]['declared_sources']['bnet'] == 'Co-op Mission/0.0/999'
    assert result['edges'][0]['resolved_via'] == 'file'
    assert result['edges'][0]['bnet_identity_verified'] is False
    assert result['edges'][1]['source']['ordinal'] == 1
    assert result['edges'][0]['source']['file'].endswith('DocumentInfo')


def test_comments_and_entities_read_correctly_and_plan_preserves_comments(tmp_path):
    original = '''<?xml version="1.0" encoding="utf-8"?>
<DocInfo>
<!-- <Dependencies><Value>file:Fake.SC2Mod</Value></Dependencies> -->
  <Name>A &amp; B</Name>
  <Dependencies>
    <!-- Keep this explanation and fake <Value>file:Wrong.SC2Mod</Value>. -->
    <Value custom="keep">file:A&amp;B.SC2Mod</Value>
    <!-- Keep trailing metadata. -->
  </Dependencies>
</DocInfo>
'''
    root = component(tmp_path, 'map.SC2Map', original)
    target = component(tmp_path, 'A&B.SC2Mod')
    result = resolve_dependencies(root, [tmp_path])
    assert result['complete']
    assert result['load_order'][0] == str(target.resolve())
    assert result['edges'][0]['reference'] == 'file:A&B.SC2Mod'
    assert plan_dependencies(root, ['file:A&B.SC2Mod']) == {}
    candidate = plan_dependencies(root, ['file:C&D.SC2Mod'])['DocumentInfo'].decode()
    assert candidate == original.replace('file:A&amp;B.SC2Mod', 'file:C&amp;D.SC2Mod')
    ET.fromstring(candidate)
    assert (root / 'DocumentInfo').read_text(encoding='utf-8') == original


def test_entity_attribute_and_combined_attributes(tmp_path):
    root = component(tmp_path, 'map.SC2Map', '<DocInfo><Dependencies><Value file="Mods/A&amp;B.SC2Mod" bnet="A &amp; B/0.0/999" custom="keep"/></Dependencies></DocInfo>')
    component(tmp_path, 'Mods/A&B.SC2Mod')
    assert resolve_dependencies(root, [tmp_path])['complete']
    changed = plan_dependencies(root, ['bnet:C/0.0/999,file:Mods/C.SC2Mod'])['DocumentInfo']
    document = ET.fromstring(changed)
    value = document.find('Dependencies/Value')
    assert value.get('custom') == 'keep'
    assert value.get('value') == 'bnet:C/0.0/999,file:Mods/C.SC2Mod'


@pytest.mark.parametrize('reference', ['file:../Outside.SC2Mod', 'file:Mods/../../Outside.SC2Mod', 'file:C:/Outside.SC2Mod', 'file://server/Outside.SC2Mod'])
def test_dependency_traversal_is_rejected(tmp_path, reference):
    root = component(tmp_path, 'map.SC2Map', f'<DocInfo><Dependencies><Value>{reference}</Value></Dependencies></DocInfo>')
    with pytest.raises(SC2Error) as error:
        resolve_dependencies(root, [tmp_path])
    assert error.value.code == 'unsafe_dependency_path'


def test_missing_dependency_metadata_marks_incomplete(tmp_path):
    root = component(tmp_path, 'map.SC2Map', '<DocInfo><Dependencies><Value>file:NoInfo.SC2Mod</Value></Dependencies></DocInfo>')
    (tmp_path / 'NoInfo.SC2Mod').mkdir()
    result = resolve_dependencies(root, [tmp_path])
    assert result['complete'] is False
    assert result['incomplete'][0]['reason'] == 'missing_document_info'
    assert result['nodes'][1]['metadata_complete'] is False


def test_unreadable_archive_marks_incomplete(tmp_path):
    root = component(tmp_path, 'map.SC2Map', '<DocInfo><Dependencies><Value>file:Broken.SC2Mod</Value></Dependencies></DocInfo>')
    (tmp_path / 'Broken.SC2Mod').write_bytes(b'PK not an MPQ')
    result = resolve_dependencies(root, [tmp_path])
    assert result['complete'] is False
    assert result['incomplete'][0]['reason'] == 'archive_metadata_unreadable'


def test_archive_metadata_read_recurses_without_extraction(tmp_path, monkeypatch):
    import mpyq
    root = component(tmp_path, 'map.SC2Map', '<DocInfo><Dependencies><Value>file:A.SC2Mod</Value></Dependencies></DocInfo>')
    archive_path = tmp_path / 'A.SC2Mod'
    archive_path.write_bytes(b'fixture: backend is mocked')
    nested = component(tmp_path, 'B.SC2Mod')

    class Archive:
        def __init__(self, stream, listfile):
            assert listfile is False
            assert stream.readable()

        def read_file(self, member):
            assert member == 'DocumentInfo'
            return b'<DocInfo><Dependencies><Value>file:B.SC2Mod</Value></Dependencies></DocInfo>'

    monkeypatch.setattr(mpyq, 'MPQArchive', Archive)
    result = resolve_dependencies(root, [tmp_path])
    assert result['complete']
    assert result['load_order'] == [str(nested.resolve()), str(archive_path.resolve()), str(root.resolve())]
    assert result['nodes'][1]['metadata_source'].endswith('!DocumentInfo')


def test_malformed_duplicate_or_external_entity_metadata_fails(tmp_path):
    root = component(tmp_path, 'map.SC2Map')
    for xml, code in [
        ('<DocInfo><Dependencies>', 'malformed_document_info'),
        ('<DocInfo><Dependencies/><Dependencies/></DocInfo>', 'ambiguous_dependencies'),
        ('<!DOCTYPE DocInfo [<!ENTITY x SYSTEM "file:///etc/passwd">]><DocInfo/>', 'unsafe_document_info'),
    ]:
        (root / 'DocumentInfo').write_text(xml, encoding='utf-8')
        with pytest.raises(SC2Error) as error:
            resolve_dependencies(root, [])
        assert error.value.code == code


def test_append_and_remove_values_preserve_interleaved_comments(tmp_path):
    original = '<DocInfo>\n  <Dependencies>\n    <!-- before -->\n    <Value>file:A.SC2Mod</Value>\n    <!-- after -->\n  </Dependencies>\n</DocInfo>\n'
    root = component(tmp_path, 'map.SC2Map', original)
    candidate = plan_dependencies(root, ['file:A.SC2Mod', 'file:B.SC2Mod'])['DocumentInfo'].decode()
    assert '<!-- before -->' in candidate and '<!-- after -->' in candidate
    assert [e.text for e in ET.fromstring(candidate).findall('Dependencies/Value')] == ['file:A.SC2Mod', 'file:B.SC2Mod']
    candidate = plan_dependencies(root, [])['DocumentInfo'].decode()
    assert '<!-- before -->' in candidate and '<!-- after -->' in candidate
    assert ET.fromstring(candidate).findall('Dependencies/Value') == []
