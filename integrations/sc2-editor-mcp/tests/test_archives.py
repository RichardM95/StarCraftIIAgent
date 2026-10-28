"""archives.py 的单元测试。

重点覆盖：格式守卫（拒绝 ZIP / 非法 MPQ）、路径守卫、目标不可覆盖、
成员哈希回读校验，以及在后端可用时的真实 MPQ 往返。所有真实归档往返测试都先做
运行时能力探测，后端缺失时安全失败或跳过，不假设接口一定可用。
"""

from __future__ import annotations

import zipfile
import random
import struct
import threading
from types import SimpleNamespace
from pathlib import Path

import pytest

from sc2_mcp import archives
from sc2_mcp.errors import SC2Error


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _fake_mpq(path: Path) -> Path:
    """写入一个仅通过头部魔数校验的伪 MPQ 文件（用于守卫/假读取器测试）。"""

    return _write(path, archives._MPQ_MAGIC + b"\x00" * 128)


class _FakeReader:
    backend = "fake"

    def __init__(self, members, data=b"<data/>"):
        self._members = list(members)
        self._data = data

    def members(self):
        return list(self._members)

    def read(self, name):
        return self._data


# ---------------------------------------------------------------------------
# inspect / 格式守卫
# ---------------------------------------------------------------------------


def test_inspect_missing_archive(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(tmp_path / "missing.SC2Map")
    assert excinfo.value.code == "missing_source"


def test_inspect_rejects_directory(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(tmp_path)
    assert excinfo.value.code == "invalid_input"


def test_inspect_rejects_zip_without_fallback(tmp_path):
    archive = tmp_path / "fake.SC2Map"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("DocumentInfo", "not a real map")

    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(archive)
    assert excinfo.value.code == "unsupported_format"
    assert "zip" in str(excinfo.value).lower()


def test_inspect_rejects_non_mpq(tmp_path):
    archive = _write(tmp_path / "random.SC2Map", b"not an archive at all")
    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(archive)
    assert excinfo.value.code == "unsupported_format"


def test_inspect_rejects_empty_file(tmp_path):
    archive = _write(tmp_path / "empty.SC2Map", b"")
    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(archive)
    assert excinfo.value.code == "unsupported_format"


def test_inspect_rejects_mpq_magic_beyond_header_window(tmp_path):
    archive = _write(tmp_path / "offset.SC2Map", b"\x00" * 600 + archives._MPQ_MAGIC)
    with pytest.raises(SC2Error) as excinfo:
        archives.inspect_archive(archive)
    assert excinfo.value.code == "unsupported_format"


def test_inspect_with_fake_reader(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / "fake.SC2Map")
    monkeypatch.setattr(
        archives,
        "_open_reader",
        lambda _path: _FakeReader(["Base.SC2Data\\a.xml"], b"<x/>"),
    )

    result = archives.inspect_archive(archive)
    assert result["format"] == "mpq"
    assert result["backend"] == "fake"
    assert result["file_count"] == 1
    assert result["files"][0]["path"] == "Base.SC2Data/a.xml"
    assert result["files"][0]["sha256"] == archives._sha256(b"<x/>")
    assert result["collisions"] == []
    # 返回对象必须可 JSON 序列化。
    import json

    json.dumps(result)


# ---------------------------------------------------------------------------
# 名称/路径守卫
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "../evil",
        "..\\evil",
        "a/../../b",
        "/absolute",
        "\\absolute",
        "C:/drive",
        "C:\\drive",
        "a//b",
        "",
        "Assets/.",
        "Assets/CON",
        "Assets/con.txt",
        "Assets/COM1.dds",
        "Assets/a?.dds",
        "Assets/a<b",
        "Assets/a>b",
        "Assets/a|b",
        'Assets/a"b',
        "Assets/a*b",
        "Assets/trailing.",
        "Assets/trailing ",
        "Assets/nul\x00byte",
        "Assets/control\x01char",
    ],
)
def test_validate_member_name_rejects_unsafe(name):
    with pytest.raises(SC2Error) as excinfo:
        archives._validate_member_name(name)
    assert excinfo.value.code == "unsafe_path"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Base.SC2Data\\Sub\\File.xml", "Base.SC2Data/Sub/File.xml"),
        ("Base.SC2Data/Sub/File.xml", "Base.SC2Data/Sub/File.xml"),
        ("DocumentInfo", "DocumentInfo"),
        ("Assets/Textures/My_Texture.DDS", "Assets/Textures/My_Texture.DDS"),
    ],
)
def test_validate_member_name_normalizes_separators(name, expected):
    assert archives._validate_member_name(name) == expected


def test_casefold_collisions_detects_duplicates():
    collisions = archives._casefold_collisions(["A/x", "a/x", "b/y"])
    assert len(collisions) == 1
    assert collisions[0] == ["A/x", "a/x"]


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


def test_extract_missing_archive(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        archives.extract_archive(tmp_path / "missing.SC2Map", tmp_path / "out")
    assert excinfo.value.code == "missing_source"


def test_extract_rejects_existing_destination(tmp_path):
    archive = _fake_mpq(tmp_path / "fake.SC2Map")
    destination = tmp_path / "out"
    destination.mkdir()

    with pytest.raises(SC2Error) as excinfo:
        archives.extract_archive(archive, destination)
    assert excinfo.value.code == "destination_exists"


def test_extract_rejects_zip_before_writing(tmp_path):
    archive = tmp_path / "fake.SC2Map"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("a.txt", "hello")
    destination = tmp_path / "out"

    with pytest.raises(SC2Error) as excinfo:
        archives.extract_archive(archive, destination)
    assert excinfo.value.code == "unsupported_format"
    assert not destination.exists()


def test_extract_rejects_traversal_member(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / "fake.SC2Map")
    monkeypatch.setattr(
        archives, "_open_reader", lambda _path: _FakeReader(["../evil.txt"])
    )
    destination = tmp_path / "out"

    with pytest.raises(SC2Error) as excinfo:
        archives.extract_archive(archive, destination)
    assert excinfo.value.code == "unsafe_path"
    assert not destination.exists()


def test_extract_rejects_casefold_collision(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / "fake.SC2Map")
    monkeypatch.setattr(
        archives,
        "_open_reader",
        lambda _path: _FakeReader(["Assets/A.dds", "assets/a.dds"]),
    )
    destination = tmp_path / "out"

    with pytest.raises(SC2Error) as excinfo:
        archives.extract_archive(archive, destination)
    assert excinfo.value.code == "name_collision"
    assert not destination.exists()


def test_extract_roundtrip_with_fake_reader(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / "fake.SC2Map")
    monkeypatch.setattr(
        archives,
        "_open_reader",
        lambda _path: _FakeReader(["Base.SC2Data\\a.xml"], b"<x/>"),
    )
    destination = tmp_path / "out"

    result = archives.extract_archive(archive, destination)
    assert result["count"] == 1
    assert result["verified"] is True
    assert result["files"][0]["path"] == "Base.SC2Data/a.xml"
    assert (destination / "Base.SC2Data" / "a.xml").read_bytes() == b"<x/>"


# ---------------------------------------------------------------------------
# export 成员收集
# ---------------------------------------------------------------------------


def test_collect_export_members_excludes_backups_and_tools(tmp_path):
    root = tmp_path / "root"
    _write(root / "DocumentInfo", b"info")
    _write(root / "DocumentHeader", b"header")
    _write(root / "Base.SC2Data" / "a.xml", b"<x/>")
    _write(root / "Base.SC2Data" / "a.xml.bak", b"backup")
    _write(root / "Thumbs.db", b"tool")
    _write(root / ".DS_Store", b"tool")
    _write(root / "~$draft.xml", b"temp")
    _write(root / ".git" / "config", b"tool")
    _write(root / "__pycache__" / "x.pyc", b"tool")

    included, excluded = archives._collect_export_members(root)
    relativized = {rel for rel, _ in included}

    assert "DocumentInfo" in relativized
    assert "DocumentHeader" in relativized
    assert "Base.SC2Data/a.xml" in relativized
    assert not any(rel.endswith(".bak") for rel in relativized)
    assert "Thumbs.db" not in relativized
    assert ".DS_Store" not in relativized
    assert not any(rel.startswith("~$") for rel in relativized)
    assert not any(rel.startswith(".git") for rel in relativized)
    assert not any(rel.startswith("__pycache__") for rel in relativized)

    reasons = {entry["path"]: entry["reason"] for entry in excluded}
    assert reasons["Base.SC2Data/a.xml.bak"] == "backup_file"
    assert reasons["Thumbs.db"] == "tool_file"


def test_export_missing_root(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(tmp_path / "missing", tmp_path / "out.SC2Map")
    assert excinfo.value.code == "missing_source"


def test_export_root_is_file(tmp_path):
    root = _write(tmp_path / "root.bin", b"x")
    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(root, tmp_path / "out.SC2Map")
    assert excinfo.value.code == "invalid_input"


def test_export_rejects_existing_destination(tmp_path):
    root = tmp_path / "root"
    _write(root / "DocumentInfo", b"info")
    destination = _write(tmp_path / "out.SC2Map", b"already here")

    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(root, destination)
    assert excinfo.value.code == "destination_exists"


def test_export_empty_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(root, tmp_path / "out.SC2Map")
    assert excinfo.value.code == "invalid_input"


def test_export_backend_unavailable_is_safe_failure(monkeypatch, tmp_path):
    root = tmp_path / "root"
    _write(root / "DocumentInfo", b"info")
    destination = tmp_path / "out.SC2Map"

    monkeypatch.setattr(
        archives,
        "backend_capabilities",
        lambda: {
            "mpyq_available": False,
            "pympq_available": False,
            "mpyq_read": False,
            "pympq_open": False,
            "read_backend": None,
            "create_backend": None,
            "can_read": False,
            "can_export": False,
            "missing": ["pympq", "mpyq"],
        },
    )

    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(root, destination)
    assert excinfo.value.code == "backend_unavailable"
    assert not destination.exists()


# ---------------------------------------------------------------------------
# 真实后端：能力探测 + 往返（后端缺失时跳过/安全失败）
# ---------------------------------------------------------------------------


def test_export_and_extract_real_roundtrip_or_safe_failure(tmp_path):
    root = tmp_path / "root"
    _write(root / "DocumentInfo", b"info")
    _write(root / "Base.SC2Data" / "a.xml", b"<x/>")
    destination = tmp_path / "out.SC2Map"

    caps = archives.backend_capabilities()

    if not caps["can_export"]:
        with pytest.raises(SC2Error) as excinfo:
            archives.export_archive(root, destination)
        assert excinfo.value.code == "backend_unavailable"
        assert not destination.exists()
        return

    result = archives.export_archive(root, destination)
    assert result["verified"] is True
    assert result["count"] == 2
    assert destination.exists()
    assert {entry["path"] for entry in result["files"]} == {
        "DocumentInfo",
        "Base.SC2Data/a.xml",
    }

    inspected = archives.inspect_archive(destination)
    assert inspected["format"] == "mpq"
    assert inspected["file_count"] == 2

    out_dir = tmp_path / "extracted"
    extracted = archives.extract_archive(destination, out_dir)
    assert extracted["verified"] is True
    assert (out_dir / "DocumentInfo").read_bytes() == b"info"
    assert (out_dir / "Base.SC2Data" / "a.xml").read_bytes() == b"<x/>"


def test_export_refuses_to_overwrite_after_backend_run(tmp_path):
    caps = archives.backend_capabilities()
    if not caps["can_export"]:
        pytest.skip("MPQ export backend unavailable")

    root = tmp_path / "root"
    _write(root / "DocumentInfo", b"info")
    destination = tmp_path / "out.SC2Map"

    archives.export_archive(root, destination)
    with pytest.raises(SC2Error) as excinfo:
        archives.export_archive(root, destination)
    assert excinfo.value.code == "destination_exists"


def _fake_export_backend(monkeypatch, payloads, create=None):
    class Reader:
        backend = 'fake'

        def members(self):
            return list(payloads)

        def read(self, name):
            return payloads[name]

    monkeypatch.setattr(archives, 'backend_capabilities', lambda: {'can_export': True, 'create_backend': 'fake'})
    monkeypatch.setattr(archives, '_open_reader', lambda _path: Reader())
    monkeypatch.setattr(archives, '_create_archive', create or (lambda path, _entries: _fake_mpq(path)))


def test_export_raced_output_is_never_overwritten_or_deleted(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    _write(root / 'DocumentInfo', b'original')
    destination = tmp_path / 'out.SC2Map'

    def create(staged, _entries):
        _fake_mpq(staged)
        destination.write_bytes(b'user-created during export')

    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'}, create)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination)
    assert error.value.code == 'destination_exists'
    assert destination.read_bytes() == b'user-created during export'
    assert Path(error.value.details['candidate']).is_file()


@pytest.mark.parametrize('mutation', ['change', 'add', 'remove'])
def test_export_source_change_rejected_after_archive_roundtrip(monkeypatch, tmp_path, mutation):
    root = tmp_path / 'source'
    source_file = _write(root / 'DocumentInfo', b'original')
    destination = tmp_path / 'out.SC2Map'

    def create(staged, _entries):
        _fake_mpq(staged)
        if mutation == 'change':
            source_file.write_bytes(b'new user edit')
        elif mutation == 'add':
            (root / 'NewFile').write_bytes(b'new user file')
        else:
            source_file.unlink()

    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'}, create)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination)
    assert error.value.code == 'archive_source_changed'
    assert not destination.exists()
    assert Path(error.value.details['candidate']).is_file()
    if mutation == 'change':
        assert source_file.read_bytes() == b'new user edit'


def test_export_backend_failure_preserves_candidate(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    _write(root / 'DocumentInfo', b'original')

    def create(staged, _entries):
        staged.write_bytes(b'partial native archive')
        raise OSError('native creation interrupted')

    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'}, create)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, tmp_path / 'out.SC2Map')
    assert Path(error.value.details['candidate']).read_bytes() == b'partial native archive'
    assert not (tmp_path / 'out.SC2Map').exists()


def test_export_destination_cannot_be_inside_source(tmp_path):
    root = tmp_path / 'source'
    _write(root / 'DocumentInfo', b'original')
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, root / 'out.SC2Map')
    assert error.value.code == 'invalid_destination'


def test_extract_directory_creation_race_does_not_write_into_user_directory(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    destination = tmp_path / 'out'

    class Reader(_FakeReader):
        def members(self):
            destination.mkdir()
            (destination / 'user.txt').write_bytes(b'user')
            return super().members()

    monkeypatch.setattr(archives, '_open_reader', lambda _path: Reader(['DocumentInfo']))
    with pytest.raises(SC2Error) as error:
        archives.extract_archive(archive, destination)
    assert error.value.code == 'destination_exists'
    assert list(destination.iterdir()) == [destination / 'user.txt']


def test_extract_file_creation_race_uses_exclusive_create(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    destination = tmp_path / 'out'

    class Reader(_FakeReader):
        def read(self, name):
            (destination / name).write_bytes(b'user')
            return b'archive'

    monkeypatch.setattr(archives, '_open_reader', lambda _path: Reader(['DocumentInfo']))
    with pytest.raises(SC2Error) as error:
        archives.extract_archive(archive, destination)
    assert error.value.code == 'destination_exists'
    assert (destination / 'DocumentInfo').read_bytes() == b'user'


def test_extract_failure_retains_partial_output_and_closes_reader(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    destination = tmp_path / 'out'

    class Reader(_FakeReader):
        closed = False

        def read(self, name):
            if name == 'Second':
                raise ValueError('bad compressed member')
            return b'first complete'

        def close(self):
            self.closed = True

    reader = Reader(['First', 'Second'])
    monkeypatch.setattr(archives, '_open_reader', lambda _path: reader)
    with pytest.raises(SC2Error) as error:
        archives.extract_archive(archive, destination)
    assert reader.closed
    assert error.value.code == 'archive_extraction_failed'
    assert error.value.details['completed_members'] == 1
    assert (destination / 'First').read_bytes() == b'first complete'


def test_extract_rejects_file_directory_prefix_collision_before_creating_destination(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    destination = tmp_path / 'out'
    monkeypatch.setattr(archives, '_open_reader', lambda _path: _FakeReader(['Assets', 'Assets/x.dds']))
    with pytest.raises(SC2Error) as error:
        archives.extract_archive(archive, destination)
    assert error.value.code == 'name_collision'
    assert not destination.exists()


def test_mpyq_constructor_failure_closes_input_stream(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    streams = []

    def broken_ctor(stream):
        streams.append(stream)
        raise ValueError('invalid table')

    monkeypatch.setattr(archives, '_try_import', lambda name: SimpleNamespace(MPQArchive=broken_ctor) if name == 'mpyq' else None)
    with pytest.raises(SC2Error):
        archives._open_reader(archive)
    assert streams and streams[0].closed


def test_inspect_unsafe_listing_does_not_claim_extractable(monkeypatch, tmp_path):
    archive = _fake_mpq(tmp_path / 'test.SC2Map')
    monkeypatch.setattr(archives, '_open_reader', lambda _path: _FakeReader(['../bad']))
    result = archives.inspect_archive(archive)
    assert result['can_extract'] is False


def test_real_zero_byte_and_multisector_roundtrip_with_userdata_header(tmp_path):
    caps = archives.backend_capabilities()
    if not caps['can_export']:
        pytest.skip('real MPQ native backend unavailable')
    root = tmp_path / 'source'
    # 2 MiB is an exact multiple of the native backend's 4 KiB sectors;
    # the other member exercises a partial last sector.
    payloads = {
        'Empty.bin': b'',
        'Exact.bin': (b'0123456789abcdef' * (2 * 1024 * 1024 // 16)),
        'Partial.bin': random.Random(20261010).randbytes(1024 * 1024 + 137),
    }
    for name, data in payloads.items():
        _write(root / name, data)
    plain = tmp_path / 'plain.SC2Map'
    result = archives.export_archive(root, plain)
    assert result['count'] == 3 and result['verified']
    import mpyq
    with plain.open('rb') as stream:
        raw_archive = mpyq.MPQArchive(stream)
        sector_size = 512 << raw_archive.header['sector_size_shift']
        entry = raw_archive.get_hash_table_entry('Exact.bin')
        block = raw_archive.block_table[entry.block_table_index]
        assert not block.flags & 0x01000000  # genuinely stored in multiple sectors
        assert block.size > sector_size and block.size % sector_size == 0
    offset = 8192
    userdata = b'SC2 user metadata fixture'
    prefix = b'MPQ\x1b' + struct.pack('<III', len(userdata), offset, len(userdata)) + userdata
    wrapped = tmp_path / 'userdata.SC2Map'
    wrapped.write_bytes(prefix + b'\0' * (offset - len(prefix)) + plain.read_bytes())
    inspected = archives.inspect_archive(wrapped)
    assert inspected['file_count'] == 3 and inspected['can_extract']
    destination = tmp_path / 'extracted'
    extracted = archives.extract_archive(wrapped, destination)
    assert extracted['verified']
    for name, data in payloads.items():
        assert (destination / name).read_bytes() == data
    # All native/read handles must be closed; Windows permits exclusive rename
    # only after those readers release their file handles.
    wrapped.rename(tmp_path / 'renamed.SC2Map')


def test_real_unicode_member_names_keep_utf8_hash_bytes_and_payloads(tmp_path):
    if not archives.backend_capabilities()['can_export']:
        pytest.skip('real MPQ native backend unavailable')
    root = tmp_path / '中文组件地图.SC2Map'
    payloads = {
        'DocumentInfo': b'<DocInfo/>',
        'Assets/Textures/中文目录/净化战争使者.png': random.Random(21184).randbytes(9001),
        'Assets/中文空文件.bin': b'',
        'Assets/中文整扇区.bin': b'0123456789abcdef' * 4096,
        # Unicode uppercasing changes these spellings, unlike MPQ byte hashing.
        'Assets/Straße_é_ı.bin': b'non-ASCII letters must not be uppercased as Unicode',
        'Assets/日本語_한글_🚀.bin': b'multilingual member content',
    }
    for name, data in payloads.items():
        _write(root / name, data)
    before = {name: archives._file_sha256(root / name) for name in payloads}
    destination = tmp_path / 'unicode.SC2Map'
    result = archives.export_archive(root, destination)
    assert result['verified'] and result['count'] == len(payloads)
    assert {f['path']: f['sha256'] for f in result['files']} == before
    import mpyq
    with destination.open('rb') as stream:
        raw_archive = mpyq.MPQArchive(stream)
        # This checks the installed native pympq/StormLib writer's actual name
        # encoding, not a mocked assumption about its C extension interface.
        assert set(raw_archive.files) == {name.replace('/', '\\').encode('utf-8') for name in payloads}
        for name in payloads:
            encoded = name.replace('/', '\\').encode('utf-8')
            assert raw_archive.get_hash_table_entry(encoded) is not None
    inspected = archives.inspect_archive(destination)
    assert inspected['file_count'] == len(payloads) and inspected['can_extract']
    extracted = tmp_path / 'extracted'
    assert archives.extract_archive(destination, extracted)['verified']
    for name, data in payloads.items():
        assert (extracted / name).read_bytes() == data
        assert archives._file_sha256(root / name) == before[name]


def test_mpyq_reader_preserves_legacy_listfile_name_bytes():
    raw_name = b'Assets\\caf\xe9.bin'
    seen = []
    archive = SimpleNamespace(files=[raw_name], read_file=lambda name: seen.append(name) or b'payload')
    reader = archives._MpyqReader(archive)
    assert reader.members() == ['Assets\\café.bin']
    assert reader.read(reader.members()[0]) == b'payload'
    assert seen == [raw_name]


def test_mpyq_reader_rejects_ambiguous_decoded_names():
    archive = SimpleNamespace(files=[b'Assets\\caf\xe9.bin', 'Assets\\café.bin'.encode('utf-8')])
    with pytest.raises(SC2Error) as error:
        archives._MpyqReader(archive)
    assert error.value.code == 'ambiguous_archive_name_encoding'


@pytest.mark.parametrize('offset,user_size,header_size', [(999999, 1, 1), (8, 1, 1), (32, 2, 20)])
def test_invalid_userdata_offsets_rejected(tmp_path, offset, user_size, header_size):
    archive = _write(tmp_path / 'bad.SC2Map', b'MPQ\x1b' + struct.pack('<III', user_size, offset, header_size) + b'\0' * 40)
    with pytest.raises(SC2Error) as error:
        archives.inspect_archive(archive)
    assert error.value.code == 'unsupported_format'


def test_export_pre_cancelled_creates_no_output(tmp_path):
    root = tmp_path / 'source'
    source = _write(root / 'DocumentInfo', b'original')
    before = archives._file_sha256(source)
    destination = tmp_path / 'out.SC2Map'
    token = threading.Event()
    token.set()
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination, cancel=token)
    assert error.value.code == 'cancelled'
    assert not destination.exists()
    assert not list(tmp_path.glob('.sc2-export-*'))
    assert archives._file_sha256(source) == before


def test_export_cancelled_during_enumeration_creates_no_output(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    source = _write(root / 'DocumentInfo', b'original')
    token = threading.Event()
    original_walk = archives.os.walk

    def interrupted_walk(*args, **kwargs):
        for item in original_walk(*args, **kwargs):
            token.set()
            yield item

    monkeypatch.setattr(archives.os, 'walk', interrupted_walk)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, tmp_path / 'out.SC2Map', cancel=token)
    assert error.value.code == 'cancelled'
    assert source.read_bytes() == b'original'
    assert not (tmp_path / 'out.SC2Map').exists()
    assert not list(tmp_path.glob('.sc2-export-*'))


def test_hash_cancellation_stops_before_next_block_and_closes_stream(monkeypatch, tmp_path):
    from io import BytesIO

    source = _write(tmp_path / 'Large.bin', b'original')
    token = threading.Event()

    class CancellingStream(BytesIO):
        reads = 0

        def read(self, size=-1):
            self.reads += 1
            result = super().read(size)
            token.set()
            return result

    stream = CancellingStream(b'x' * (3 * 1024 * 1024))
    original_open = Path.open
    monkeypatch.setattr(Path, 'open', lambda path, *args, **kwargs:
                        stream if path == source else original_open(path, *args, **kwargs))
    with pytest.raises(SC2Error) as error:
        archives._file_sha256(source, cancel=token)
    assert error.value.code == 'cancelled'
    assert stream.closed and stream.reads == 1


def test_export_member_write_cancellation_closes_native_archive_and_retains_staging(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    payloads = {'First': b'first', 'Second': b'second'}
    for name, data in payloads.items():
        _write(root / name, data)
    before = {name: archives._file_sha256(root / name) for name in payloads}
    destination = tmp_path / 'out.SC2Map'
    token = threading.Event()

    class NativeArchive:
        closed = False
        writes = []

        def add_file(self, source, name, flags, compression):
            self.writes.append(name)
            token.set()

        def close(self):
            self.closed = True

    native = NativeArchive()

    def create(path, flags, file_count):
        _fake_mpq(Path(path))
        return native

    backend = SimpleNamespace(create_archive=create, open_archive=lambda *args: None,
                              **{name: index for index, name in enumerate(
                                  archives._PYMPQ_CREATE_FLAGS + archives._PYMPQ_ADD_CONSTANTS, 1)})
    monkeypatch.setattr(archives, '_try_import', lambda name: backend if name == 'pympq' else None)
    monkeypatch.setattr(archives, 'backend_capabilities', lambda: {'can_export': True, 'create_backend': 'fake'})
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination, cancel=token)
    assert error.value.code == 'cancelled'
    assert native.closed and native.writes == ['First']
    assert not destination.exists()
    assert Path(error.value.details['staging_directory']).is_dir()
    assert Path(error.value.details['candidate']).is_file()
    assert {name: archives._file_sha256(root / name) for name in payloads} == before


def test_export_readback_cancellation_closes_reader_and_preserves_source(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    source = _write(root / 'DocumentInfo', b'original')
    before = archives._file_sha256(source)
    destination = tmp_path / 'out.SC2Map'
    token = threading.Event()
    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'},
                         lambda path, entries, cancel=None: _fake_mpq(path))

    class Reader(_FakeReader):
        closed = False

        def read(self, name):
            token.set()
            return b'original'

        def close(self):
            self.closed = True

    reader = Reader(['DocumentInfo'])
    monkeypatch.setattr(archives, '_open_reader', lambda path: reader)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination, cancel=token)
    assert error.value.code == 'cancelled'
    assert reader.closed
    assert not destination.exists()
    assert Path(error.value.details['candidate']).is_file()
    assert archives._file_sha256(source) == before


@pytest.mark.parametrize('cancel_at', ['progress', 'publication'])
def test_export_final_cancellation_never_publishes(monkeypatch, tmp_path, cancel_at):
    root = tmp_path / 'source'
    source = _write(root / 'DocumentInfo', b'original')
    before = archives._file_sha256(source)
    destination = tmp_path / 'out.SC2Map'
    token = threading.Event()
    progress = []

    def report(value, message=None):
        progress.append(value)
        if value == 95 and cancel_at == 'progress':
            token.set()

    token.report_progress = report
    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'},
                         lambda path, entries, cancel=None: _fake_mpq(path))
    original_no_links = archives._no_links

    def no_links(path, boundary=None):
        original_no_links(path, boundary)
        if path == destination and progress and progress[-1] == 95 and cancel_at == 'publication':
            token.set()

    monkeypatch.setattr(archives, '_no_links', no_links)
    with pytest.raises(SC2Error) as error:
        archives.export_archive(root, destination, cancel=token)
    assert error.value.code == 'cancelled'
    assert progress == [10, 50, 95]
    assert not destination.exists()
    assert Path(error.value.details['candidate']).is_file()
    assert archives._file_sha256(source) == before


def test_export_cancellation_after_publication_does_not_claim_cancelled(monkeypatch, tmp_path):
    root = tmp_path / 'source'
    source = _write(root / 'DocumentInfo', b'original')
    destination = tmp_path / 'out.SC2Map'
    token = threading.Event()
    progress = []
    token.report_progress = lambda value, message=None: progress.append(value)
    _fake_export_backend(monkeypatch, {'DocumentInfo': b'original'},
                         lambda path, entries, cancel=None: _fake_mpq(path))
    original_link = archives.os.link

    def publish_then_cancel(source, target):
        original_link(source, target)
        token.set()

    monkeypatch.setattr(archives.os, 'link', publish_then_cancel)
    result = archives.export_archive(root, destination, cancel=token)
    assert result['verified'] and destination.is_file() and token.is_set()
    assert progress == [10, 50, 95]
    assert not list(tmp_path.glob('.sc2-export-*'))
    assert source.read_bytes() == b'original'
