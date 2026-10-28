from pathlib import Path

import pytest

from sc2_mcp.change_import import plan_import
from sc2_mcp.errors import SC2Error
from sc2_mcp.storage import digest


def test_external_candidate_checks_baseline_candidate_and_does_not_write(tmp_path):
    root = tmp_path / 'map'; root.mkdir()
    (root / 'file.txt').write_bytes(b'old')
    candidate = tmp_path / 'candidate'; candidate.write_bytes(b'new')
    entry = {'path': 'file.txt', 'baseline_sha256': digest(b'old'),
             'candidate_file': str(candidate), 'candidate_sha256': digest(b'new')}
    assert plan_import(root, [entry]) == {'file.txt': b'new'}
    assert (root / 'file.txt').read_bytes() == b'old'
    candidate.write_bytes(b'tampered')
    with pytest.raises(SC2Error, match='指纹不符'):
        plan_import(root, [entry])
    candidate.write_bytes(b'new'); (root / 'file.txt').write_bytes(b'manual')
    with pytest.raises(SC2Error, match='基准'):
        plan_import(root, [entry])


def test_import_rejects_escape_duplicate_unknown_and_own_map_candidate(tmp_path):
    root = tmp_path / 'map'; root.mkdir()
    candidate = tmp_path / 'candidate'; candidate.write_bytes(b'new')
    entry = {'path': 'new.txt', 'baseline_sha256': None,
             'candidate_file': str(candidate), 'candidate_sha256': digest(b'new')}
    for entries in [[{**entry, 'path': '../escape'}], [entry, entry], [{**entry, 'bypass': True}]]:
        with pytest.raises(SC2Error): plan_import(root, entries)
    (root / 'inside').write_bytes(b'new')
    with pytest.raises(SC2Error): plan_import(root, [{**entry, 'candidate_file': str(root / 'inside')}])


def test_delete_and_new_file_are_explicit(tmp_path):
    root = tmp_path / 'map'; root.mkdir(); (root / 'old').write_bytes(b'old')
    assert plan_import(root, [{'path':'old', 'baseline_sha256':digest(b'old'), 'delete':True}]) == {'old':None}
    with pytest.raises(SC2Error): plan_import(root, [{'path':'absent', 'delete':True}])
