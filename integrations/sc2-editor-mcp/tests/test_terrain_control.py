import json
from pathlib import Path
import shutil
import struct

import numpy as np
import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.storage import digest, file_lock, snapshot
from sc2_mcp.terrain import Terrain
from sc2_mcp import terrain_control as tc


def terrain(root):
    root.mkdir(parents=True)
    (root / 't3Terrain.xml').write_bytes(b'<terrain version="115"><heightMap dim="9 9" tileSet="Test"><vertData quantizeBias="16" quantizeScale="0.001"/><rampList><ramp dir="1" hi="3" lo="2"/></rampList></heightMap></terrain>')
    def grid(name, magic, version, header, width, height, data, offset=8):
        b = bytearray(header)
        b[:4] = magic
        struct.pack_into('<I', b, 4, version)
        struct.pack_into('<II', b, offset, width, height)
        (root / name).write_bytes(b + data)
    vertices = np.zeros((9, 9, 3), dtype='<u2'); vertices[:] = [20000, 20000, 1]
    sync = np.zeros((9, 9, 2), dtype='<i2'); sync[:] = [2048, 1]
    grid('t3HeightMap', b'HMAP', 101, 32, 9, 9, vertices.tobytes())
    grid('t3SyncHeightMap', b'SMAP', 102, 64, 9, 9, sync.tobytes())
    grid('t3SyncCliffLevel', b'CLIF', 100, 32, 8, 8, np.full((8, 8), 64, dtype='<u2').tobytes())
    grid('t3CellFlags', b'LFCT', 102, 32, 8, 8, np.full((8, 8), 2, dtype='u1').tobytes(), 24)
    (root / 'CellAttribute_Pnp').write_bytes(struct.pack('<I', 8 * 8 * 8) + bytes(64))
    (root / 'Objects').write_bytes(b'<?xml version="1.0" encoding="utf-8"?>\r\n<PlacedObjects Version="27">\r\n<!-- retain comment -->\r\n<ObjectDoodad Id="1" Position="3.5,4,10" Scale="0.351,0.351,0.351" Type="Turret"><Flag Index="HeightAbsolute" Value="1"/></ObjectDoodad>\r\n<ObjectUnit Id="2" Position="2,2,12" UnitType="Thor" Player="1"/>\r\n</PlacedObjects>\r\n')
    (root / 'MapScript.galaxy').write_bytes(b'void InitMap () {}\r\n')
    (root / 'BankList.xml').write_bytes(b'<BankList/>')
    (root / 'DocumentHeader').write_bytes(b'original identity')
    return root


def override(root, name, data):
    (root / name).write_bytes(data)


def test_protected_flatten_changes_only_brush_bytes_and_source_immutable(tmp_path):
    root = terrain(tmp_path / 'root')
    t = Terrain(root)
    t.vertices[3, 3, 0] += 100
    t.vertices[4, 4, 0] += 200
    override(root, 't3HeightMap', t.raw['t3HeightMap'][:32] + t.vertices.tobytes())
    before = snapshot(root)
    mask = np.zeros((9, 9), dtype=bool); mask[4, 4] = True
    r = tc.plan_flatten_protected_report(root, [2, 2, 5, 5], protected_mask=mask)
    assert set(r['changes']) == {'t3HeightMap'}
    after = Terrain(root, r['changes'])
    assert after.vertices[3, 3, 0] == 20000
    assert after.vertices[4, 4, 0] == 20200
    assert np.array_equal(t.vertices[:, :, 1:], after.vertices[:, :, 1:])
    assert np.array_equal(t.sync, after.sync)
    assert snapshot(root) == before and r['changed_brush_vertices'] == 1
    assert r['status'] == 'awaiting_native_sync' and r['playable_delivery'] is False
    json.dumps({k: v for k, v in r.items() if k != 'changes'})


def test_mask_type_selection_and_ambiguous_plateau_rejected(tmp_path):
    root = terrain(tmp_path / 'root')
    for bad in [np.ones((9, 9), dtype='u1'), [[True]], [[0] * 9] * 9]:
        with pytest.raises(SC2Error) as e:
            tc.plan_flatten_protected(root, [1, 1, 2, 2], protected_mask=bad)
        assert e.value.code == 'invalid_protection_mask'
    with pytest.raises(SC2Error) as e:
        tc.plan_flatten_protected(root, [1, 1, 2, 2], protected_rects=[[1, 1, 2, 2]])
    assert e.value.code == 'empty_flatten_selection'
    assert tc.plan_flatten_protected(root, [1, 1, 2, 2]) == {}
    with pytest.raises(SC2Error):
        tc.plan_flatten_protected(root, [1, 1, 2, 2], brush_value=True)
    t = Terrain(root); t.vertices[1:3, 1:3, 0] = [[1, 1], [2, 2]]
    override(root, 't3HeightMap', t.raw['t3HeightMap'][:32] + t.vertices.tobytes())
    with pytest.raises(SC2Error) as e:
        tc.plan_flatten_protected(root, [1, 1, 2, 2])
    assert e.value.code == 'ambiguous_flatten_plateau'


def test_grounding_uses_explicit_model_offset_preserves_xy_and_flags(tmp_path):
    root = terrain(tmp_path / 'root')
    original = (root / 'Objects').read_bytes()
    changes = tc.plan_ground_offsets(root, [{'object_id': 1, 'world_z_offset': .0124475096}, {'object_id': 2, 'world_z_offset': -.25}])
    assert set(changes) == {'Objects'}
    after = changes['Objects']
    assert b'Position="3.5,4,8.012448"' in after
    assert b'Position="2,2,7.750000"' in after
    assert after.replace(b'Position="3.5,4,8.012448"', b'Position="3.5,4,10"').replace(b'Position="2,2,7.750000"', b'Position="2,2,12"') == original
    assert (root / 'Objects').read_bytes() == original
    with pytest.raises(SC2Error) as e:
        tc.plan_ground_offsets(root, [{'object_id': 1}])
    assert e.value.code == 'ground_offset_required'
    with pytest.raises(SC2Error) as e:
        tc.plan_ground_offsets(root, [{'object_id': 1, 'world_z_offset': 0}], terrain_overrides={'t3HeightMap': (root / 't3HeightMap').read_bytes()})
    assert e.value.code == 'stale_ground_height'


def test_unknown_ground_coordinate_mode_refused(tmp_path):
    root = terrain(tmp_path / 'root')
    p = root / 'Objects'; p.write_bytes(p.read_bytes().replace(b'Index="HeightAbsolute" Value="1"', b'Index="HeightAbsolute" Value="0"'))
    with pytest.raises(SC2Error) as e:
        tc.plan_ground_offsets(root, [{'object_id': 1, 'world_z_offset': 0}])
    assert e.value.code == 'unknown_ground_coordinate_mode'


def paired(tmp_path):
    a = terrain(tmp_path / 'control-before')
    b, c, d = [tmp_path / name for name in ['control-after', 'candidate-before', 'candidate-after']]
    for p in [b, c, d]:
        shutil.copytree(a, p)
    t = Terrain(c); t.vertices[4, 4, 0] += 1000
    data = t.raw['t3HeightMap'][:32] + t.vertices.tobytes()
    override(c, 't3HeightMap', data); override(d, 't3HeightMap', data)
    t = Terrain(d); t.sync[4, 4, 0] += 256
    override(d, 't3SyncHeightMap', t.raw['t3SyncHeightMap'][:64] + t.sync.tobytes())
    for p in [b, d]:
        (p / 'MapScript.galaxy').write_bytes(b'native script rewrite')
        (p / 'DocumentHeader').write_bytes(b'native identity rewrite')
        (p / 'BankList.xml').write_bytes(b'native bank rewrite')
        (p / 'MapInfo.version').write_bytes(b'native sidecar')
    return a, b, c, d


def test_paired_native_filters_script_bank_identity_and_sidecars(tmp_path):
    a, b, c, d = paired(tmp_path)
    before = snapshot(c)
    r = tc.plan_native_sync_result_report(c, a, b, c, d)
    assert set(r['changes']) == {'t3SyncHeightMap'}
    assert r['sync_changed_vertices'] == 1 and r['outside_support_max_delta'] == 0
    assert set(r['excluded_native_rewrites']) == {'MapScript.galaxy', 'BankList.xml', 'DocumentHeader', 'MapInfo.version'}
    assert r['evidence']['runtime'] == 'not_observed' and r['playable_delivery'] is False
    assert snapshot(c) == before
    json.dumps({k: v for k, v in r.items() if k != 'changes'})


@pytest.mark.parametrize('failure', ['outside', 'protected', 'cliff', 'water', 'cache', 'xml'])
def test_paired_native_rejects_collateral_terrain_changes(tmp_path, failure):
    a, b, c, d = paired(tmp_path)
    kwargs = {}
    if failure == 'outside':
        t = Terrain(d); t.sync[0, 0, 0] += 1
        override(d, 't3SyncHeightMap', t.raw['t3SyncHeightMap'][:64] + t.sync.tobytes())
    elif failure == 'protected':
        mask = np.zeros((9, 9), dtype=bool); mask[4, 4] = True
        kwargs['protected_mask'] = mask
    elif failure == 'cliff':
        data = bytearray((d / 't3SyncCliffLevel').read_bytes()); data[32] ^= 1
        override(d, 't3SyncCliffLevel', data)
    elif failure == 'water':
        override(d, 't3Water', b'unrequested water')
    elif failure == 'cache':
        override(d, 't3VertCol', b'unverified cache divergence')
    else:
        p = d / 't3Terrain.xml'; p.write_bytes(p.read_bytes().replace(b'tileSet="Test"', b'tileSet="Other"'))
    with pytest.raises(SC2Error) as e:
        tc.plan_native_sync_result(c, a, b, c, d, **kwargs)
    assert e.value.code == 'native_sync_semantic_gate'


def test_unknown_xml_version_and_paired_input_race_rejected(tmp_path, monkeypatch):
    a, b, c, d = paired(tmp_path)
    xml = d / 't3Terrain.xml'
    original = xml.read_bytes()
    xml.write_bytes(original.replace(b'version="115"', b'version="116"'))
    with pytest.raises(SC2Error) as e:
        tc.plan_native_sync_result(c, a, b, c, d)
    assert e.value.code == 'unsupported_terrain_format'
    xml.write_bytes(original)
    original_snapshot = tc.snapshot
    count = 0
    def changing_snapshot(path):
        nonlocal count
        count += 1
        if count == 5:
            (d / 't3VertCol').write_bytes(b'concurrent change')
        return original_snapshot(path)
    monkeypatch.setattr(tc, 'snapshot', changing_snapshot)
    with pytest.raises(SC2Error) as e:
        tc.plan_native_sync_result(c, a, b, c, d)
    assert e.value.code == 'native_sync_source_changed'


def test_target_pathing_baseline_must_match_candidate_input(tmp_path):
    a, b, c, d = paired(tmp_path)
    root = tmp_path / 'target'
    shutil.copytree(c, root)
    (root / 'CellAttribute_Pnp').write_bytes(b'other map pathing')
    with pytest.raises(SC2Error) as e:
        tc.plan_native_sync_result(root, a, b, c, d)
    assert 'target_terrain_baseline' in e.value.details['failed']


@pytest.fixture
def native_env(tmp_path, monkeypatch):
    install = tmp_path / 'installation'
    exe = install / 'Support64/SC2Editor_x64.exe'; exe.parent.mkdir(parents=True); exe.write_bytes(b'fixture-only-exe')
    fingerprint = digest(exe.read_bytes())
    monkeypatch.setattr(tc, 'SUPPORTED_EDITOR_SHA256', fingerprint)
    archive_a, archive_b = tmp_path / 'a.SC2Map', tmp_path / 'b.SC2Map'
    archive_a.write_bytes(b'fixture archive A'); archive_b.write_bytes(b'fixture archive B')
    monkeypatch.setattr(tc.archives, 'inspect_archive', lambda p: {'fixture': True})
    monkeypatch.setattr(tc.editor, 'processes', lambda p: [])
    calls = []
    class FakeProcess:
        def __init__(self, argv, **kwargs):
            self.argv = argv; self.pid = 100 + len(calls); self.returncode = 0; calls.append(self)
            path = Path(argv[2]); path.write_bytes(path.read_bytes() + b' native')
        def poll(self):
            return self.returncode
        def terminate(self):
            raise AssertionError('No native process should be terminated')
    class Identity:
        def __init__(self, pid):
            self.process = next(p for p in calls if p.pid == pid)
        def create_time(self): return 123.
        def exe(self): return str(exe)
        def cmdline(self): return self.process.argv
    monkeypatch.setattr(tc.subprocess, 'Popen', FakeProcess)
    monkeypatch.setattr(tc.psutil, 'Process', Identity)
    template = terrain(tmp_path / 'template')
    def extract(path, destination):
        shutil.copytree(template, destination)
        return {'root': str(destination), 'members': len(snapshot(destination))}
    monkeypatch.setattr(tc.archives, 'extract_archive', extract)
    args = (archive_a, archive_b, tmp_path / 'output', install)
    kwargs = {'state_root': tmp_path / 'state', 'expected_editor_sha256': fingerprint}
    return args, kwargs, calls


def test_native_runner_only_copies_inputs_uses_explicit_argv_and_paired_outputs(native_env):
    args, kwargs, calls = native_env
    a, b, output, install = args
    originals = [a.read_bytes(), b.read_bytes()]
    r = tc.run_native_sync(*args, **kwargs)
    assert r['state'] == 'native_complete' and r['source_archives_unchanged']
    assert [a.read_bytes(), b.read_bytes()] == originals
    assert len(calls) == 2
    for proc in calls:
        assert proc.argv[1] == '-resaveall' and Path(proc.argv[2]).parent == output
        assert '*' not in proc.argv[2]
    assert all((output / (role + suffix + '.SC2Map')).is_dir() for role in ['control', 'candidate'] for suffix in ['-before', '-after'])
    assert (output / 'native-sync.json').is_file()
    json.dumps(r)


def test_native_blocks_busy_editor_and_installation_lock(native_env, monkeypatch):
    args, kwargs, calls = native_env
    monkeypatch.setattr(tc.editor, 'processes', lambda p: [{'pid': 99, 'owned': False}])
    with pytest.raises(SC2Error) as e:
        tc.run_native_sync(*args, **kwargs)
    assert e.value.code == 'native_sync_editor_busy'
    assert not args[2].exists() and not calls
    monkeypatch.setattr(tc.editor, 'processes', lambda p: [])
    lock = kwargs['state_root'] / 'probe-installation-locks' / (digest(str(args[3].resolve()).casefold().encode()) + '.lock')
    with file_lock(lock):
        with pytest.raises(SC2Error) as e:
            tc.run_native_sync(*args, **kwargs)
    assert e.value.code == 'project_busy'


def test_native_rejects_directory_wildcard_protected_and_unknown_editor(native_env):
    args, kwargs, calls = native_env
    a, b, out, install = args
    for path, expected in [(a.parent, 'native_sync_explicit_archive'), (a.parent / '*.SC2Map', 'native_sync_explicit_archive')]:
        with pytest.raises(SC2Error) as e:
            tc.run_native_sync(path, b, out, install, **kwargs)
        assert e.value.code == expected
    with pytest.raises(SC2Error) as e:
        tc.run_native_sync(*args, **kwargs, protected_roots=[a.parent])
    assert e.value.code == 'native_sync_protected_path'
    kwargs['expected_editor_sha256'] = '0' * 64
    with pytest.raises(SC2Error) as e:
        tc.run_native_sync(*args, **kwargs)
    assert e.value.code == 'unsupported_native_editor' and not calls


def test_native_timeout_preserves_owned_process_and_stops_before_candidate(native_env, monkeypatch):
    args, kwargs, calls = native_env
    original = tc.subprocess.Popen
    def running(*a, **kw):
        p = original(*a, **kw); p.returncode = None
        return p
    monkeypatch.setattr(tc.subprocess, 'Popen', running)
    ticks = iter([0., 99.])
    monkeypatch.setattr(tc.time, 'monotonic', lambda: next(ticks))
    r = tc.run_native_sync(*args, **kwargs, timeout=.01)
    assert r['state'] == 'partial' and r['reason'] == 'timeout'
    assert len(calls) == 1 and r['runs'][0]['ownership_verified']
    assert r['running_process_retained']
    assert not (args[2] / 'candidate.SC2Map').exists()


def test_native_fast_exit_identity_race_is_recorded_with_popen_exit_evidence(native_env, monkeypatch):
    args, kwargs, calls = native_env
    def disappeared(pid):
        raise tc.psutil.NoSuchProcess(pid)
    monkeypatch.setattr(tc.psutil, 'Process', disappeared)
    r = tc.run_native_sync(*args, **kwargs)
    assert r['state'] == 'native_complete' and len(calls) == 2
    assert all(p['identity_error'] == 'NoSuchProcess' and not p['ownership_verified'] for p in r['runs'])
    assert all(p['exit_code'] == 0 and p['native_completed'] for p in r['runs'])


@pytest.mark.parametrize('failure', ['exit', 'launch', 'cancel', 'source', 'identity'])
def test_native_failure_or_cancel_retains_evidence_and_never_launches_next(native_env, monkeypatch, failure):
    args, kwargs, calls = native_env
    original = tc.subprocess.Popen
    if failure == 'launch':
        def launch_error(*a, **kw):
            raise OSError('fixture launch failure')
        monkeypatch.setattr(tc.subprocess, 'Popen', launch_error)
    elif failure == 'source':
        original_copy = tc.shutil.copyfile
        def changed_copy(source, destination):
            Path(source).write_bytes(b'changed source')
            return original_copy(source, destination)
        monkeypatch.setattr(tc.shutil, 'copyfile', changed_copy)
    else:
        def failing(*a, **kw):
            p = original(*a, **kw)
            p.returncode = 7 if failure == 'exit' else None
            return p
        monkeypatch.setattr(tc.subprocess, 'Popen', failing)
        if failure == 'cancel':
            class Token:
                def is_set(self): return bool(calls)
            kwargs['cancel'] = Token()
        elif failure == 'identity':
            monkeypatch.setattr(tc, '_running', lambda record: False)
    r = tc.run_native_sync(*args, **kwargs)
    reasons = {'exit': 'native_nonzero_exit', 'launch': 'native_launch_failed', 'cancel': 'cancelled',
               'source': 'source_archive_changed', 'identity': 'process_identity_unverified'}
    assert r['reason'] == reasons[failure]
    assert r['state'] in {'partial', 'failed'} and len(calls) <= 1
    assert json.loads((args[2] / 'native-sync.json').read_text(encoding='utf-8')) == r
    assert not (args[2] / 'candidate.SC2Map').exists()
