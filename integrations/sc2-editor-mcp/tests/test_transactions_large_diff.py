"""Independent acceptance tests for the worker's transaction diff repair."""
import difflib
import random
import re
from pathlib import Path

import pytest
import sc2_mcp.transactions as m
from sc2_mcp.storage import snapshot


def restore(old, patch):
    if not patch:
        return old
    lines = patch.splitlines(keepends=True)
    assert lines[0].startswith('--- ') and lines[1].startswith('+++ ')
    match = re.fullmatch(r'@@ -(\d+),(\d+) \+(\d+),(\d+) @@\n', lines[2])
    assert match
    os, oc, ns, nc = map(int, match.groups())
    op = os - 1 if oc else os
    np = ns - 1 if nc else ns
    source = old.splitlines(keepends=True)
    assert op == np and 0 <= op <= len(source)
    records = []
    for line in lines[3:]:
        if line == '\\ No newline at end of file\n':
            assert records and records[-1][1].endswith('\n')
            records[-1] = (records[-1][0], records[-1][1][:-1])
        else:
            assert line[:1] in (' ', '+', '-')
            records.append((line[0], line[1:]))
    output = source[:op]
    consumed = produced = 0
    for tag, payload in records:
        if tag in (' ', '-'):
            assert op < len(source) and payload == source[op]
            op += 1
            consumed += 1
        if tag in (' ', '+'):
            output.append(payload)
            produced += 1
    assert (consumed, produced) == (oc, nc)
    return ''.join(output + source[op:])


@pytest.mark.parametrize('old,new', [('', 'x\n'), ('x\n', ''), ('a', 'b'),
    ('a\r', 'b\r'), ('头\r\na\n尾', '头\r\n改\n尾'),
    ('a\nb\nc\n', 'a\nX\nc\n'), ('a\nb\n', 'a\nb\nx\n'),
    ('---\n+++\n', '+++\n---\n'), ('', ''), ('equal', 'equal')])
def test_fallback_exact_reconstruction(old, new):
    a, b = old.splitlines(True), new.splitlines(True)
    before = (a[:], b[:])
    patch = ''.join(m.large_unified_diff(a, b, 'a', 'b'))
    assert restore(old, patch) == new
    assert (a, b) == before


def test_randomized_reconstruction():
    rng = random.Random(760411)
    tokens = ['same\n', 'x\n', '中文\r\n', '\n', '@@ value\n', '---\n', '+++\n']
    for _ in range(3000):
        prefix = ''.join(rng.choices(tokens, k=rng.randrange(12)))
        suffix = ''.join(rng.choices(tokens, k=rng.randrange(12)))
        old = prefix + ''.join(rng.choices(tokens, k=rng.randrange(15))) + suffix
        new = prefix + ''.join(rng.choices(tokens, k=rng.randrange(15))) + suffix
        if old and rng.randrange(3) == 0:
            old = old[:-1]
        if new and rng.randrange(3) == 0:
            new = new[:-1]
        assert restore(old, ''.join(m.large_unified_diff(old.splitlines(True), new.splitlines(True), 'a', 'b'))) == new


def test_small_diff_legacy_bytes():
    for old, new in [('', 'x'), ('a\nb\nc\n', 'a\nX\nc\n'), ('a\r\n', 'b'), ('', '')]:
        assert list(m._unified_diff(old, new, 'a', 'b')) == list(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='a', tofile='b'))


def test_large_preview_and_rollback(tmp_path, monkeypatch):
    old = 'repeated\n' * 110000
    new = old[:55000 * 9] + 'insert\r\n' + old[55000 * 9:]
    def forbidden(*args, **kwargs):
        raise AssertionError('large input entered difflib')
    monkeypatch.setattr(m.difflib, 'unified_diff', forbidden)
    root = tmp_path / 'map.SC2Mod'
    root.mkdir()
    (root / 'Triggers').write_text(old, encoding='utf-8', newline='')
    before = snapshot(root)
    tx = m.Transactions(tmp_path / 'state')
    preview = tx.run(root, lambda: {'Triggers': new.encode()}, preview_only=True)
    assert preview['state'] == 'prepared' and snapshot(root) == before
    patch = Path(preview['diff']).read_bytes().decode()
    assert restore(old, patch) == new
    committed = tx.run(root, lambda: {'Triggers': new.encode()}, candidate_id=preview['change_id'])
    assert committed['state'] == 'committed' and (root / 'Triggers').read_bytes() == new.encode()
    assert tx.rollback(committed['change_id'], root)['state'] == 'rolled_back'
    assert snapshot(root) == before
