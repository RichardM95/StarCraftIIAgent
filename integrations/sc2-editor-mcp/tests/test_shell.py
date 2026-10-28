import hashlib
import struct
from pathlib import Path

import pytest

from sc2_mcp.dependencies import plan_dependencies
from sc2_mcp.errors import SC2Error
from sc2_mcp.shell import header_dependencies, replace_header_dependencies, replace_header_localization


def make_header(values, strings=(("DocInfo/Name", b"NCzh", "中文名称"),)):
    prefix = b'H2CS' + struct.pack('<I', 8) + bytes(range(36))
    payload = struct.pack('<I', len(values)) + b''.join(value.encode() + b'\0' for value in values)
    suffix = struct.pack('<I', len(strings))
    for key, locale, value in strings:
        encoded_key, encoded_value = key.encode(), value.encode()
        suffix += struct.pack('<H', len(encoded_key)) + encoded_key + locale + struct.pack('<H', len(encoded_value)) + encoded_value
    return prefix + payload + suffix


def test_v8_dependency_replace_preserves_opaque_prefix_and_localization_suffix():
    old = ['bnet:原版/0.0/999,file:Mods/Base.SC2Mod']
    new = ['file:Mods/A.SC2Mod', 'bnet:另一个模组/0.0/999,file:Mods/B.SC2Mod']
    original = make_header(old)
    before = header_dependencies(original)
    candidate = replace_header_dependencies(original, old, new)
    after = header_dependencies(candidate)
    assert after['values'] == new
    assert candidate[:44] == original[:44]
    assert candidate[after['end']:] == original[before['end']:]
    assert replace_header_dependencies(original, old, old) == original


def test_shell_mismatch_refuses_candidate():
    with pytest.raises(SC2Error) as error:
        replace_header_dependencies(make_header(['file:A']), ['file:B'], ['file:C'])
    assert error.value.code == 'shell_mismatch'


@pytest.mark.parametrize('mutation', [lambda data: data[:20], lambda data: data[:-1],
    lambda data: data[:4] + struct.pack('<I', 99) + data[8:],
    lambda data: data[:44] + struct.pack('<I', 2000) + data[48:],
    lambda data: data + b'unsupported-extension'])
def test_unknown_or_truncated_header_fails(mutation):
    with pytest.raises(SC2Error):
        header_dependencies(mutation(make_header(['file:A'])))


def test_plan_synchronizes_both_metadata_files_without_writing(tmp_path):
    old = ['file:A.SC2Mod']
    docinfo = b'<DocInfo><!-- keep --><Dependencies><Value>file:A.SC2Mod</Value></Dependencies><Name>keep</Name></DocInfo>'
    original_header = make_header(old)
    (tmp_path / 'DocumentInfo').write_bytes(docinfo)
    (tmp_path / 'DocumentHeader').write_bytes(original_header)
    result = plan_dependencies(tmp_path, ['file:B.SC2Mod'])
    assert set(result) == {'DocumentInfo', 'DocumentHeader'}
    assert result['DocumentInfo'] == docinfo.replace(b'file:A.SC2Mod', b'file:B.SC2Mod')
    assert header_dependencies(result['DocumentHeader'])['values'] == ['file:B.SC2Mod']
    assert (tmp_path / 'DocumentInfo').read_bytes() == docinfo
    assert (tmp_path / 'DocumentHeader').read_bytes() == original_header


def test_optional_real_keystone_header_readonly():
    root = Path(r'<KEYSTONE_MAP_ROOT>\build\kscg2.SC2Map')
    if not (root / 'DocumentHeader').is_file():
        pytest.skip('real readonly SC2 fixture unavailable on this host')
    before = {name: (root / name).read_bytes() for name in ('DocumentInfo', 'DocumentHeader')}
    parsed = header_dependencies(before['DocumentHeader'])
    if len(parsed['values']) < 2:
        pytest.skip('readonly fixture no longer has two dependencies')
    requested = list(reversed(parsed['values']))
    candidate = plan_dependencies(root, requested)
    after = header_dependencies(candidate['DocumentHeader'])
    assert after['values'] == requested
    assert candidate['DocumentHeader'][:44] == before['DocumentHeader'][:44]
    assert candidate['DocumentHeader'][after['end']:] == before['DocumentHeader'][parsed['end']:]
    for name, data in before.items():
        assert hashlib.sha256((root / name).read_bytes()).digest() == hashlib.sha256(data).digest()


@pytest.mark.parametrize('replacement', ['翠影遗庭：林间遗迹战场', '庭', ''])
def test_localization_variable_utf8_length_preserves_identity_dependencies_and_other_entries(replacement):
    dependencies = ['file:Mods/Liberty.SC2Mod', 'bnet:合作数据/0.0/999,file:Mods/Coop.SC2Mod']
    entries = (
        ('DocInfo/Name', b'SUne', 'Unchanged English title'),
        ('DocInfo/Author', b'NChz', '作者：保持原文'),
        ('DocInfo/Name', b'NChz', '原名称'),
        ('DocInfo/DescLong', b'NChz', '保留描述\n第二行'),
        ('DocInfo/Name', b'WTzh', '繁體標題保持'),
    )
    original = make_header(dependencies, entries)
    candidate = replace_header_localization(original, {'DocInfo/Name': replacement})
    expected_entries = entries[:2] + (('DocInfo/Name', b'NChz', replacement),) + entries[3:]
    assert candidate == make_header(dependencies, expected_entries)
    boundary = header_dependencies(original)['end']
    assert candidate[:boundary] == original[:boundary]
    assert header_dependencies(candidate)['values'] == dependencies
    assert len(candidate) - len(original) == len(replacement.encode('utf-8')) - len('原名称'.encode('utf-8'))


def test_localization_multiple_changed_lengths_do_not_shift_later_edits():
    entries = (
        ('DocInfo/Name', b'NChz', '旧'),
        ('DocInfo/Author', b'NChz', '不应变化的作者'),
        ('DocInfo/DescLong', b'NChz', '原本较长的描述'),
        ('DocInfo/DescLong', b'SUne', 'English description remains'),
    )
    original = make_header(['file:A.SC2Mod'], entries)
    candidate = replace_header_localization(original, {'DocInfo/Name': '翠影遗庭', 'DocInfo/DescLong': '短'})
    assert candidate == make_header(['file:A.SC2Mod'], (
        ('DocInfo/Name', b'NChz', '翠影遗庭'), entries[1],
        ('DocInfo/DescLong', b'NChz', '短'), entries[3],
    ))


def test_localization_noop_preserves_exact_bytes_and_explicit_locale_is_respected():
    original = make_header(['file:A.SC2Mod'])
    assert replace_header_localization(original, {}) == original
    assert replace_header_localization(original, {'DocInfo/Name': '中文名称'}, locale=b'NCzh') == original
    candidate = replace_header_localization(original, {'DocInfo/Name': '翠影遗庭'}, locale=b'NCzh')
    assert candidate == make_header(['file:A.SC2Mod'], (('DocInfo/Name', b'NCzh', '翠影遗庭'),))


@pytest.mark.parametrize('updates', [
    {'DocInfo/NotPresent': '新增不可静默成功'},
    {'DocInfo/Name': '改名', 'DocInfo/NotPresent': '缺失'},
])
def test_localization_missing_key_refuses_whole_update(updates):
    original = make_header([], (('DocInfo/Name', b'NChz', '原名称'),))
    with pytest.raises(SC2Error) as error:
        replace_header_localization(original, updates)
    assert error.value.code == 'header_text_missing'


def test_localization_key_in_other_locale_does_not_satisfy_requested_key():
    original = make_header([], (('DocInfo/Name', b'SUne', 'English only'),))
    with pytest.raises(SC2Error) as error:
        replace_header_localization(original, {'DocInfo/Name': '翠影遗庭'}, locale=b'NChz')
    assert error.value.code == 'header_text_missing'


def test_localization_duplicate_matching_key_is_rejected():
    original = make_header([], (
        ('DocInfo/Name', b'NChz', '第一个'),
        ('DocInfo/Name', b'SUne', 'Different locale'),
        ('DocInfo/Name', b'NChz', '第二个'),
    ))
    with pytest.raises(SC2Error) as error:
        replace_header_localization(original, {'DocInfo/Name': '翠影遗庭'})
    assert error.value.code == 'invalid_header_localization'


@pytest.mark.parametrize('value', ['含\0空字节', '\0', 'x' * 65536, '庭' * 21846],
                         ids=['embedded-nul', 'nul-only', 'ascii-too-long', 'utf8-too-long'])
def test_localization_nul_or_value_exceeding_u16_utf8_bytes_is_rejected(value):
    original = make_header([], (('DocInfo/Name', b'NChz', '原名称'),))
    with pytest.raises(SC2Error) as error:
        replace_header_localization(original, {'DocInfo/Name': value})
    assert error.value.code == 'invalid_header_localization'


def test_localization_exact_u16_utf8_byte_limit_is_accepted():
    value = '庭' * 21845
    assert len(value.encode('utf-8')) == 65535
    original = make_header([], (('DocInfo/Name', b'NChz', '原名称'),))
    candidate = replace_header_localization(original, {'DocInfo/Name': value})
    assert candidate == make_header([], (('DocInfo/Name', b'NChz', value),))
