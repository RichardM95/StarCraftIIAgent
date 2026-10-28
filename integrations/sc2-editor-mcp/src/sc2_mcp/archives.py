"""MPQ 归档检查、解包与导出（archives.py）。

契约（docs/CONTRACT.md）：
    inspect_archive(path: Path) -> dict
    extract_archive(path, destination: Path) -> dict
    export_archive(root: Path, destination: Path, cancel=None) -> dict

本模块只读归档内容；只有 ``extract_archive`` / ``export_archive`` 会写入新的
输出目录/文件，且永不覆盖已存在的目标。MPQ 通过 mpyq / pympq 处理，明确拒绝
以 ZIP 或其他格式伪装的 SC2Map。后端能力在运行时惰性探测，任何未经验证的接口
都返回具体的 ``SC2Error``，绝不模拟成功。
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import shutil
import struct
import tempfile
import zlib
import bz2
from contextlib import contextmanager
from pathlib import Path

from sc2_mcp.errors import SC2Error

__all__ = [
    "inspect_archive",
    "extract_archive",
    "export_archive",
    "backend_capabilities",
]

_MPQ_MAGIC = b"MPQ\x1a"
_MPQ_USER_DATA_MAGIC = b"MPQ\x1b"
_ZIP_MAGIC_PREFIX = b"PK"
_HEAD_BYTES = 1024

_WINDOWS_INVALID_CHARS = set('<>:"|?*')
_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "conin$",
    "conout$",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}

_EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vs",
    "__pycache__",
    "node_modules",
    "_codex_backups", ".sc2-mcp", ".venv", ".pytest_cache",
}
_EXCLUDED_FILE_NAMES = {"thumbs.db", "desktop.ini", ".ds_store", "ehthumbs.db"}
_EXCLUDED_FILE_SUFFIXES = {
    ".bak",
    ".backup",
    ".old",
    ".orig",
    ".rej",
    ".tmp",
    ".temp",
    ".swp",
    ".swo",
    ".autosave",
    ".log",
}

_PYMPQ_CREATE_FLAGS = ("MPQ_CREATE_ARCHIVE_V2", "MPQ_CREATE_LISTFILE")
_PYMPQ_ADD_CONSTANTS = (
    "MPQ_FILE_COMPRESS",
    "MPQ_FILE_REPLACEEXISTING",
    "MPQ_COMPRESSION_ZLIB",
)


# ---------------------------------------------------------------------------
# 后端探测
# ---------------------------------------------------------------------------


def _try_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:  # pragma: no cover - 取决于运行环境
        return None


def backend_capabilities() -> dict:
    """惰性探测已安装的 MPQ 后端及其能力。

    只根据真实存在的模块/符号报告能力，不猜测缺失接口。``can_export`` 额外要求
    存在 mpyq 读取后端，因为导出后进行成员 SHA256 回读校验。
    """

    caps = {
        "mpyq_available": False,
        "pympq_available": False,
        "mpyq_read": False,
        "pympq_open": False,
        "read_backend": None,
        "create_backend": None,
        "can_read": False,
        "can_export": False,
        "missing": [],
    }

    mpyq = _try_import("mpyq")
    pympq = _try_import("pympq")

    if mpyq is not None:
        caps["mpyq_available"] = True
        if getattr(mpyq, "MPQArchive", None) is not None:
            caps["mpyq_read"] = True

    if pympq is not None:
        caps["pympq_available"] = True
        if getattr(pympq, "open_archive", None) is not None:
            caps["pympq_open"] = True

    if caps["mpyq_read"]:
        caps["read_backend"] = "mpyq"
    elif caps["pympq_open"]:
        caps["read_backend"] = "pympq"
    caps["can_read"] = caps["read_backend"] is not None

    missing: list[str] = []
    if pympq is None:
        missing.append("pympq")
    else:
        for name in (
            "create_archive",
            "open_archive",
            *_PYMPQ_CREATE_FLAGS,
            *_PYMPQ_ADD_CONSTANTS,
        ):
            if getattr(pympq, name, None) is None:
                missing.append(name)

    caps["missing"] = missing
    if not missing and caps["mpyq_read"]:
        caps["create_backend"] = "pympq"
        caps["can_export"] = True

    return caps


class _MpyqReader:
    """基于 mpyq.MPQArchive 的只读读取器。"""

    backend = "mpyq"

    def __init__(self, archive):
        self._archive = archive
        # MPQ hashes filenames as bytes, with ASCII-only uppercasing. mpyq
        # also accepts str but then hashes Unicode codepoints (and applies
        # Unicode uppercasing), which corrupts non-ASCII lookups. Keep each
        # listfile spelling byte-for-byte, including legacy non-UTF8 names.
        self._member_names = []
        self._name_bytes = {}
        raw_names = getattr(archive, "files", None)
        if raw_names is None:
            raw_names = getattr(archive, "file_list", None) or []
        for raw_name in raw_names:
            name = _coerce_name(raw_name)
            encoded = raw_name if isinstance(raw_name, bytes) else name.encode("utf-8")
            if name in self._name_bytes and self._name_bytes[name] != encoded:
                raise SC2Error("ambiguous_archive_name_encoding", "不同成员名原始字节解码后发生冲突", member=name)
            self._member_names.append(name)
            self._name_bytes[name] = encoded

    def members(self) -> list[str]:
        return list(self._member_names)

    def read(self, name: str) -> bytes:
        reader = getattr(self._archive, "read_file", None)
        if reader is None:
            raise SC2Error(
                "backend_unavailable",
                "mpyq archive does not expose read_file().",
            )
        lookup = getattr(self._archive, "get_hash_table_entry", None)
        encoded_name = self._name_bytes.get(name)
        if encoded_name is None:
            encoded_name = name.encode("utf-8")
        entry = lookup(encoded_name) if lookup else None
        block = self._archive.block_table[entry.block_table_index] if entry else None
        # mpyq 0.2.5 uses floor(size / sector_size) + 1 for the number of
        # sectors, which reads one offset too many for exact sector multiples.
        # Decode sector blocks here with ceil division and explicit bounds.
        if block is not None and not block.flags & 0x01000000 and block.size:
            result = self._read_sectors(block, name)
        else:
            result = reader(encoded_name)
        if result is None:
            if block is not None and block.size==0 and block.flags & 0x80000000:
                return b""
            raise SC2Error("archive_member_missing", "归档成员不存在或不可读取", member=name)
        data = bytes(result)
        if block is not None and len(data) != block.size:
            raise SC2Error("archive_member_size_mismatch", "归档成员展开长度不符", member=name, expected=block.size, actual=len(data))
        return data

    def _read_sectors(self, block, name: str) -> bytes:
        if not block.flags & 0x80000000:
            raise SC2Error("archive_member_missing", "归档成员未标记为存在", member=name)
        if block.flags & (0x00010000 | 0x00000100):
            raise SC2Error("unsupported_compression", "尚不支持加密或 PKWARE imploded 成员", member=name)
        archive = self._archive
        archive.file.seek(block.offset + archive.header.get("offset", 0))
        raw = archive.file.read(block.archived_size)
        if len(raw) != block.archived_size:
            raise SC2Error("truncated_archive_member", "归档成员数据不完整", member=name)
        if not block.flags & 0x00000200:
            return raw
        shift = archive.header["sector_size_shift"]
        if not 0 <= shift <= 15:
            raise SC2Error("unsupported_sector_size", "MPQ 扇区大小无效", shift=shift)
        sector_size = 512 << shift
        sectors = (block.size + sector_size - 1) // sector_size
        offset_count = sectors + 1 + bool(block.flags & 0x04000000)
        table_size = 4 * offset_count
        if table_size > len(raw):
            raise SC2Error("truncated_archive_member", "MPQ 扇区偏移表不完整", member=name)
        offsets = struct.unpack_from(f"<{offset_count}I", raw)
        if offsets[0] < table_size or offsets[-1] > len(raw) or any(a > b for a, b in zip(offsets, offsets[1:])):
            raise SC2Error("invalid_sector_offsets", "MPQ 扇区偏移越界或乱序", member=name)
        output = bytearray()
        for index in range(sectors):
            sector = raw[offsets[index]:offsets[index + 1]]
            expected_size = min(sector_size, block.size - len(output))
            if len(sector) < expected_size:
                if not sector:
                    raise SC2Error("truncated_archive_member", "MPQ 扇区为空", member=name)
                method = sector[0]
                try:
                    if method == 2:
                        decoder = zlib.decompressobj()
                        decoded = decoder.decompress(sector[1:], expected_size + 1)
                        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                            raise ValueError("zlib stream incomplete, excessive or has trailing bytes")
                        sector = decoded
                    elif method == 16:
                        decoder = bz2.BZ2Decompressor()
                        sector = decoder.decompress(sector[1:], max_length=expected_size + 1)
                        if not decoder.eof or decoder.unused_data:
                            raise ValueError("bzip2 stream incomplete, excessive or has trailing bytes")
                    elif method == 0:
                        sector = sector[1:]
                    else:
                        raise SC2Error("unsupported_compression", "MPQ 扇区压缩组合尚未支持", member=name, method=method)
                except (ValueError, zlib.error, EOFError) as exc:
                    raise SC2Error("invalid_compressed_sector", "MPQ 扇区解压失败", member=name, reason=str(exc)) from exc
            if len(sector) != expected_size:
                raise SC2Error("archive_member_size_mismatch", "MPQ 扇区展开长度不符", member=name, expected=expected_size, actual=len(sector))
            output.extend(sector)
        return bytes(output)

    def close(self):
        handle=getattr(self._archive,"file",None)
        if handle is not None:
            handle.close()


class _PympqReader:
    """基于 pympq.open_archive 的只读读取器（接口按实际属性惰性使用）。"""

    backend = "pympq"

    def __init__(self, archive):
        self._archive = archive

    def members(self) -> list[str]:
        raw = getattr(self._archive, "files", None)
        if raw is None:
            lister = getattr(self._archive, "list_files", None) or getattr(
                self._archive, "get_files", None
            )
            if not callable(lister):
                raise SC2Error("backend_unavailable", "MPQ 后端无法枚举成员，拒绝空结果冒充成功")
            raw = lister()
        return [_coerce_name(name) for name in (raw or [])]

    def read(self, name: str) -> bytes:
        reader = getattr(self._archive, "read_file", None)
        if reader is None:
            raise SC2Error(
                "backend_unavailable",
                "pympq archive does not expose read_file(); cannot verify members.",
            )
        return bytes(reader(name))

    def close(self):
        closer=getattr(self._archive,"close",None)
        if closer:
            closer()


@contextmanager
def _managed_reader(path):
    reader=_open_reader(path)
    try:
        yield reader
    finally:
        close=getattr(reader,"close",None)
        if close:
            close()


def _coerce_name(name) -> str:
    if isinstance(name, bytes):
        try:
            return name.decode("utf-8")
        except UnicodeDecodeError:
            return name.decode("latin-1")
    return str(name)


def _open_reader(path: Path):
    errors: list[str] = []

    mpyq = _try_import("mpyq")
    if mpyq is not None:
        ctor = getattr(mpyq, "MPQArchive", None)
        if ctor is not None:
            try:
                stream = open(path, "rb")
                try:
                    return _MpyqReader(ctor(stream))
                except BaseException:
                    stream.close()
                    raise
            except Exception as exc:  # pragma: no cover - 后端相关
                errors.append(f"mpyq: {exc}")

    pympq = _try_import("pympq")
    if pympq is not None:
        opener = getattr(pympq, "open_archive", None)
        if opener is not None:
            try:
                archive = opener(str(path), [])
            except Exception as exc:  # pragma: no cover - 后端相关
                errors.append(f"pympq: {exc}")
            else:
                if hasattr(archive, "read_file") or hasattr(archive, "files"):
                    return _PympqReader(archive)
                closer = getattr(archive, "close", None)
                if callable(closer):
                    closer()
                errors.append("pympq: opened archive exposes neither read_file nor files")

    if not errors:
        raise SC2Error(
            "backend_unavailable",
            "No MPQ backend is installed (mpyq or pympq).",
        )
    raise SC2Error(
        "unsupported_format",
        "Archive could not be opened by any available MPQ backend.",
        backend_errors=errors,
    )


# ---------------------------------------------------------------------------
# 路径/名称守卫
# ---------------------------------------------------------------------------


def _validate_member_name(name: str) -> str:
    """校验并把归档成员名规范化为 map 相对 POSIX 路径。

    拒绝绝对路径、盘符、``..``/``.``、空段、Windows 非法字符与保留设备名、
    尾随空格/点、NUL 与控制字符。名称拼写（大小写）保持原样。
    """

    if not isinstance(name, str) or not name:
        raise SC2Error("unsafe_path", "Archive member name must be a non-empty string.")
    if "\x00" in name:
        raise SC2Error("unsafe_path", "Archive member name contains a NUL byte.", name=name)

    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        raise SC2Error("unsafe_path", "Absolute archive member path is rejected.", name=name)
    if re.match(r"^[A-Za-z]:", normalized):
        raise SC2Error("unsafe_path", "Drive-qualified archive member path is rejected.", name=name)

    parts = normalized.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise SC2Error(
                "unsafe_path",
                "Archive member path contains an empty or traversal segment.",
                name=name,
                segment=part,
            )
        if any(ch in _WINDOWS_INVALID_CHARS for ch in part):
            raise SC2Error(
                "unsafe_path",
                "Archive member path contains a Windows-invalid character.",
                name=name,
                segment=part,
            )
        if any(ord(ch) < 32 for ch in part):
            raise SC2Error(
                "unsafe_path",
                "Archive member path contains a control character.",
                name=name,
                segment=part,
            )
        if part.endswith(" ") or part.endswith("."):
            raise SC2Error(
                "unsafe_path",
                "Archive member path has a trailing space or dot.",
                name=name,
                segment=part,
            )
        stem = part.split(".", 1)[0].lower()
        if stem in _RESERVED_NAMES:
            raise SC2Error(
                "unsafe_path",
                "Archive member path uses a reserved Windows device name.",
                name=name,
                segment=part,
            )

    return "/".join(parts)


def _casefold_collisions(names) -> list[list[str]]:
    buckets: dict[str, list[str]] = {}
    for name in names:
        buckets.setdefault(name.casefold(), []).append(name)
    return [sorted(group) for group in buckets.values() if len(group) > 1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_cancel(cancel) -> None:
    if cancel is not None and cancel.is_set():
        raise SC2Error("cancelled", "归档导出已取消，已生成的候选文件予以保留")


def _report_export_progress(cancel, progress: int, message: str) -> None:
    reporter = getattr(cancel, "report_progress", None)
    if callable(reporter):
        reporter(progress, message)
    _check_cancel(cancel)


def _file_sha256(path: Path, cancel=None) -> str:
    _check_cancel(cancel)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            _check_cancel(cancel)
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    _check_cancel(cancel)
    return digest.hexdigest()


def _no_links(path: Path, boundary: Path | None = None) -> None:
    current = path.absolute()
    while True:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise SC2Error("linked_archive_path", "归档读写路径不能穿过链接", path=str(current))
        if current == boundary or current == current.parent:
            break
        current = current.parent


def _validate_member_tree(names: list[str]) -> None:
    keys = {name.casefold() for name in names}
    for name in names:
        parts = name.split("/")
        for index in range(1, len(parts)):
            if "/".join(parts[:index]).casefold() in keys:
                raise SC2Error("name_collision", "归档中的文件与目录名称冲突", member=name)


# ---------------------------------------------------------------------------
# 格式校验
# ---------------------------------------------------------------------------


def _assert_mpq_file(path: Path) -> None:
    try:
        with open(path, "rb") as handle:
            head = handle.read(16)
            if head.startswith(_MPQ_USER_DATA_MAGIC):
                if len(head) < 16:
                    raise SC2Error("unsupported_format", "MPQ 用户数据头不完整", path=str(path))
                _magic, user_size, offset, header_size = struct.unpack("<4sIII", head)
                file_size = path.stat().st_size
                if offset < 16 or offset > file_size - 4 or header_size > offset - 16 or user_size < header_size:
                    raise SC2Error("unsupported_format", "MPQ 用户数据头偏移或长度无效", path=str(path), offset=offset)
                handle.seek(offset)
                if handle.read(4) != _MPQ_MAGIC:
                    raise SC2Error("unsupported_format", "用户数据头没有指向有效 MPQ 头", path=str(path), offset=offset)
                return
    except OSError as exc:
        raise SC2Error("missing_source", f"Cannot read archive: {path}", path=str(path)) from exc

    if not head:
        raise SC2Error("unsupported_format", "Archive is empty.", path=str(path))
    if head[:2] == _ZIP_MAGIC_PREFIX:
        raise SC2Error(
            "unsupported_format",
            "ZIP archives are not supported; expected a real MPQ/SC2Map. "
            "No ZIP fallback is provided.",
            path=str(path),
        )
    if not head.startswith(_MPQ_MAGIC):
        raise SC2Error(
            "unsupported_format",
            "File is not an MPQ archive (MPQ header magic not found).",
            path=str(path),
        )


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def inspect_archive(path: Path) -> dict:
    """只读检查 MPQ 归档，返回可 JSON 序列化的元数据与成员信息。"""

    archive_path = Path(path)
    if not archive_path.exists():
        raise SC2Error("missing_source", "Archive does not exist.", path=str(archive_path))
    if not archive_path.is_file():
        raise SC2Error("invalid_input", "Archive path is not a file.", path=str(archive_path))

    _assert_mpq_file(archive_path)
    size = archive_path.stat().st_size
    caps = backend_capabilities()
    with _managed_reader(archive_path) as reader:
        names = reader.members()

        files: list[dict] = []
        warnings: list[str] = []
        for name in names:
            entry: dict = {"name": name}
            try:
                normalized = _validate_member_name(name)
            except SC2Error as exc:
                entry["path"] = None
                entry["safe_name"] = False
                entry["name_error"] = exc.code
                warnings.append(f"unsafe member name: {name!r} ({exc.code})")
                files.append(entry)
                continue

            entry["path"] = normalized
            entry["safe_name"] = True
            try:
                data = reader.read(name)
            except Exception as exc:  # pragma: no cover - 后端相关
                entry["error"] = str(exc)
                warnings.append(f"could not read member {name!r}: {exc}")
                files.append(entry)
                continue

            entry["size"] = len(data)
            entry["sha256"] = _sha256(data)
            files.append(entry)

        safe_paths = [entry["path"] for entry in files if entry.get("path")]
        collisions = _casefold_collisions(safe_paths)
        try:
            _validate_member_tree(safe_paths)
        except SC2Error as exc:
            warnings.append(str(exc))

        return {
            "path": str(archive_path),
            "format": "mpq",
            "backend": reader.backend,
            "size": size,
            "file_count": len(files),
            "files": files,
            "collisions": collisions,
            "can_extract": not warnings and not collisions,
            "can_export": caps["can_export"],
            "capabilities": caps,
            "warnings": warnings,
        }


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------


def extract_archive(path: Path, destination: Path) -> dict:
    """把 MPQ 成员解包到全新的输出目录，并回读校验 SHA256。

    目标目录必须不存在（永不覆盖）。先校验所有成员名和冲突，再逐个读取并以
    排他创建模式落盘。失败保留已生成内容，并在异常中返回恢复位置；不删除目录。
    """

    archive_path = Path(path)
    destination_path = Path(destination)

    if not archive_path.exists():
        raise SC2Error("missing_source", "Archive does not exist.", path=str(archive_path))
    if not archive_path.is_file():
        raise SC2Error("invalid_input", "Archive path is not a file.", path=str(archive_path))
    if destination_path.exists() or destination_path.is_symlink():
        raise SC2Error(
            "destination_exists",
            "Extraction destination already exists; refusing to overwrite.",
            destination=str(destination_path),
        )

    _assert_mpq_file(archive_path)
    _no_links(destination_path)
    source_digest = _file_sha256(archive_path)
    with _managed_reader(archive_path) as reader:
        names = reader.members()

        plans: list[tuple[str, str]] = []
        seen: dict[str, str] = {}
        for name in names:
            normalized = _validate_member_name(name)
            key = normalized.casefold()
            if key in seen:
                raise SC2Error(
                    "name_collision",
                    "Archive contains case-insensitively colliding member names.",
                    first=seen[key],
                    second=name,
                    normalized=normalized,
                )
            seen[key] = name
            plans.append((name, normalized))
        _validate_member_tree([normalized for _name, normalized in plans])

        created = False
        extracted: list[dict] = []
        try:
            try:
                destination_path.mkdir(parents=True, exist_ok=False)
                created = True
            except FileExistsError as exc:
                raise SC2Error("destination_exists", "解包目标在准备期间已被创建，未写入已有目录", destination=str(destination_path)) from exc
            root_identity = (destination_path.stat().st_dev, destination_path.stat().st_ino)

            for name, normalized in plans:
                _no_links(destination_path)
                if (destination_path.stat().st_dev, destination_path.stat().st_ino) != root_identity:
                    raise SC2Error("destination_changed", "解包目录在操作期间被替换", destination=str(destination_path))
                data = reader.read(name)
                target = destination_path.joinpath(*normalized.split("/"))
                _no_links(target, destination_path.absolute())
                target.parent.mkdir(parents=True, exist_ok=True)
                _no_links(target, destination_path.absolute())
                try:
                    with target.open("xb") as output:
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                except FileExistsError as exc:
                    raise SC2Error("destination_exists", "拒绝覆盖解包期间新出现的文件", path=str(target)) from exc

                digest = _sha256(data)
                actual = _sha256(target.read_bytes())
                if actual != digest:
                    raise SC2Error(
                        "verification_failed",
                        "Extracted member failed SHA256 roundtrip verification.",
                        member=name,
                        expected=digest,
                        actual=actual,
                    )
                extracted.append(
                    {
                        "name": name,
                        "path": normalized,
                        "size": len(data),
                        "sha256": digest,
                        "verified": True,
                    }
                )
            if _file_sha256(archive_path) != source_digest:
                raise SC2Error("archive_source_changed", "解包期间源归档发生变化", source=str(archive_path))
            for item in extracted:
                target = destination_path.joinpath(*item["path"].split("/"))
                _no_links(target, destination_path.absolute())
                if _file_sha256(target) != item["sha256"]:
                    raise SC2Error("destination_changed", "解包结果在完成前被其他写入修改", path=str(target))
        except Exception as exc:
            if isinstance(exc, SC2Error):
                exc.details.update(partial_output=str(destination_path) if created else None, completed_members=len(extracted), recovery="保留输出，检查报告后使用新的目标目录重试")
                raise
            raise SC2Error("archive_extraction_failed", "解包未完成，已保留生成内容", partial_output=str(destination_path) if created else None,
                           completed_members=len(extracted), reason=str(exc)) from exc

        return {
            "archive": str(archive_path),
            "destination": str(destination_path),
            "format": "mpq",
            "backend": reader.backend,
            "count": len(extracted),
            "files": extracted,
            "verified": True,
            "source_sha256": source_digest,
            "warnings": [],
        }


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def _is_excluded(rel_path: str) -> str | None:
    parts = rel_path.split("/")
    for part in parts[:-1]:
        if part.lower() in _EXCLUDED_DIR_NAMES:
            return "excluded_directory"
    filename = parts[-1]
    lowered = filename.lower()
    if lowered in _EXCLUDED_FILE_NAMES:
        return "tool_file"
    if filename.startswith("~$") or filename.endswith("~"):
        return "temporary_file"
    suffix = os.path.splitext(lowered)[1]
    if suffix in _EXCLUDED_FILE_SUFFIXES:
        return "backup_file"
    return None


def _collect_export_members(root: Path, cancel=None) -> tuple[list[tuple[str, Path]], list[dict]]:
    """收集待导出成员，排除备份/工具文件。返回 (包含项, 排除项)。"""

    included: list[tuple[str, Path]] = []
    excluded: list[dict] = []

    _check_cancel(cancel)
    _no_links(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        _check_cancel(cancel)
        dirnames[:] = sorted(
            name for name in dirnames if name.lower() not in _EXCLUDED_DIR_NAMES
        )
        for dirname in dirnames:
            _check_cancel(cancel)
            _no_links(Path(dirpath) / dirname, root.absolute())
        for filename in sorted(filenames):
            _check_cancel(cancel)
            absolute = Path(dirpath) / filename
            rel = os.path.relpath(absolute, root).replace(os.sep, "/")

            reason = _is_excluded(rel)
            if reason is not None:
                excluded.append({"path": rel, "reason": reason})
                continue
            _no_links(absolute, root.absolute())
            try:
                normalized = _validate_member_name(rel)
            except SC2Error as exc:
                excluded.append({"path": rel, "reason": "unsafe_name", "error": exc.code})
                continue
            included.append((normalized, absolute))

    included.sort(key=lambda item: item[0].casefold())
    collisions = _casefold_collisions([relative for relative, _path in included])
    if collisions:
        raise SC2Error("name_collision", "导出源存在大小写冲突", collisions=collisions)
    _validate_member_tree([relative for relative, _path in included])
    _check_cancel(cancel)
    return included, excluded


def _resolve_constant(pympq, archive, name: str):
    value = getattr(pympq, name, None)
    if value is None and archive is not None:
        value = getattr(archive, name, None)
    return value


def _create_archive(destination: Path, entries: list[tuple[str, Path]], cancel=None) -> None:
    """通过 pympq 创建 MPQ。仅使用运行时探测到的真实接口/常量。"""

    _check_cancel(cancel)
    pympq = _try_import("pympq")
    if pympq is None:
        raise SC2Error("backend_unavailable", "pympq is not installed; cannot create MPQ.")

    creator = getattr(pympq, "create_archive", None)
    opener = getattr(pympq, "open_archive", None)
    if creator is None or opener is None:
        raise SC2Error(
            "backend_unavailable",
            "pympq lacks create_archive/open_archive.",
        )

    create_flags = []
    for name in _PYMPQ_CREATE_FLAGS:
        value = getattr(pympq, name, None)
        if value is None:
            raise SC2Error(
                "backend_unavailable",
                f"pympq constant {name} is unavailable.",
                missing=[name],
            )
        create_flags.append(value)

    archive = None
    creation_complete = False
    try:
        _check_cancel(cancel)
        archive = creator(str(destination), create_flags, max(64, len(entries) + 16))
        _check_cancel(cancel)

        add_file = getattr(archive, "add_file", None)
        if add_file is None:
            raise SC2Error("backend_unavailable", "pympq archive lacks add_file().")

        file_flags: list = []
        for name in ("MPQ_FILE_COMPRESS", "MPQ_FILE_REPLACEEXISTING"):
            value = _resolve_constant(pympq, archive, name)
            if value is None:
                raise SC2Error(
                    "backend_unavailable",
                    f"pympq constant {name} is unavailable.",
                    missing=[name],
                )
            file_flags.append(value)

        compression = _resolve_constant(pympq, archive, "MPQ_COMPRESSION_ZLIB")
        if compression is None:
            raise SC2Error(
                "backend_unavailable",
                "pympq constant MPQ_COMPRESSION_ZLIB is unavailable.",
                missing=["MPQ_COMPRESSION_ZLIB"],
            )

        for normalized, absolute in entries:
            _check_cancel(cancel)
            archive_name = normalized.replace("/", "\\")
            add_file(str(absolute), archive_name, list(file_flags), [compression])
            _check_cancel(cancel)
        creation_complete = True
    except SC2Error:
        raise
    except Exception as exc:  # pragma: no cover - 后端相关
        raise SC2Error(
            "backend_error",
            "MPQ backend failed while creating the archive.",
            cause=str(exc),
        ) from exc
    finally:
        close = getattr(archive, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:  # pragma: no cover - 后端相关
                if creation_complete:
                    raise SC2Error("backend_finalize_failed", "MPQ 后端关闭或刷新失败", reason=str(exc)) from exc


def export_archive(root: Path, destination: Path, cancel=None) -> dict:
    """导出新的 MPQ 并回读 SHA256；协作取消保留候选且阻止发布。"""

    _check_cancel(cancel)
    root_path = Path(root)
    destination_path = Path(destination)

    if not root_path.exists():
        raise SC2Error("missing_source", "Export root does not exist.", root=str(root_path))
    if not root_path.is_dir():
        raise SC2Error("invalid_input", "Export root is not a directory.", root=str(root_path))
    if destination_path.exists() or destination_path.is_symlink():
        raise SC2Error(
            "destination_exists",
            "Export destination already exists; refusing to overwrite.",
            destination=str(destination_path),
        )
    if destination_path.resolve().is_relative_to(root_path.resolve()):
        raise SC2Error("invalid_destination", "归档输出不能位于待导出源目录内", destination=str(destination_path))
    _no_links(destination_path)

    entries, excluded = _collect_export_members(root_path, cancel=cancel)
    if not entries:
        raise SC2Error("invalid_input", "No exportable files found under root.", root=str(root_path))

    caps = backend_capabilities()
    if not caps["can_export"]:
        raise SC2Error(
            "backend_unavailable",
            "A verifiable MPQ export backend (pympq create + mpyq read) is unavailable.",
            missing=caps["missing"],
            mpyq_read=caps["mpyq_read"],
        )

    # 记录源文件摘要，供创建后回读校验。
    expected = [(normalized, absolute, _file_sha256(absolute, cancel=cancel)) for normalized, absolute in entries]
    _report_export_progress(cancel, 10, "已完成导出成员枚举与源文件指纹")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sc2-export-", dir=destination_path.parent))
    staged_archive = staging / "candidate.SC2Map"
    cleanup_warnings = []
    try:
        _check_cancel(cancel)
        if cancel is None:
            _create_archive(staged_archive, entries)
        else:
            _create_archive(staged_archive, entries, cancel=cancel)
        _report_export_progress(cancel, 50, "已生成 MPQ 候选，正在回读校验")
        _assert_mpq_file(staged_archive)

        with _managed_reader(staged_archive) as reader:
            member_map: dict[str, str] = {}
            for name in reader.members():
                _check_cancel(cancel)
                try:
                    normalized = _validate_member_name(name)
                except SC2Error:
                    continue
                key = normalized.casefold()
                if key in member_map:
                    raise SC2Error("name_collision", "导出归档出现同名成员", member=name)
                member_map[key] = name
            expected_names = {normalized.casefold() for normalized, _absolute, _digest in expected}
            unexpected = set(member_map) - expected_names - {"(listfile)", "(attributes)", "(signature)"}
            if unexpected:
                raise SC2Error("verification_failed", "导出归档包含未请求成员", unexpected=sorted(unexpected))

            verified: list[dict] = []
            for normalized, _absolute, digest in expected:
                _check_cancel(cancel)
                key = normalized.casefold()
                if key not in member_map:
                    raise SC2Error(
                        "verification_failed",
                        "Exported archive is missing an expected member.",
                        member=normalized,
                    )
                data = reader.read(member_map[key])
                _check_cancel(cancel)
                actual = _sha256(data)
                _check_cancel(cancel)
                if actual != digest:
                    raise SC2Error(
                        "verification_failed",
                        "Exported member failed SHA256 roundtrip verification.",
                        member=normalized,
                        expected=digest,
                        actual=actual,
                    )
                verified.append(
                    {
                        "path": normalized,
                        "size": len(data),
                        "sha256": digest,
                        "verified": True,
                    }
                )
        _check_cancel(cancel)
        final_entries, _final_excluded = _collect_export_members(root_path, cancel=cancel)
        if [relative for relative, _path in final_entries] != [relative for relative, _path in entries]:
            raise SC2Error("archive_source_changed", "导出期间源文件集合变化", root=str(root_path))
        for normalized, absolute, digest in expected:
            _check_cancel(cancel)
            if not absolute.is_file() or _file_sha256(absolute, cancel=cancel) != digest:
                raise SC2Error("archive_source_changed", "导出期间源文件内容变化", member=normalized)
        _report_export_progress(cancel, 95, "归档回读及源文件复核通过，准备发布")
        _no_links(destination_path)
        # Hard-link publication is atomic and refuses an existing name on both
        # Windows and POSIX. Never use replace/rename with overwrite semantics.
        try:
            _check_cancel(cancel)
            os.link(staged_archive, destination_path)
        except FileExistsError as exc:
            raise SC2Error("destination_exists", "归档目标在导出期间出现，未覆盖已有文件", destination=str(destination_path)) from exc
        except OSError as exc:
            raise SC2Error("archive_publish_failed", "无法以不可覆盖方式发布归档；候选已保留", destination=str(destination_path), reason=str(exc)) from exc
    except Exception as exc:
        if isinstance(exc, SC2Error):
            exc.details.update(staging_directory=str(staging), candidate=str(staged_archive), recovery="候选和源数据均保留；检查错误后改用新目标重试")
            raise
        raise SC2Error("archive_export_failed", "导出未完成，候选保留且未删除目标", staging_directory=str(staging), candidate=str(staged_archive), reason=str(exc)) from exc
    # Only remove our successful temporary link and an empty owned directory.
    # Failed output directories and concurrent user-created files are retained.
    try:
        if staged_archive.is_symlink() or not os.path.samefile(staged_archive, destination_path):
            raise OSError("temporary archive identity changed")
        staged_archive.unlink()
        staging.rmdir()
    except OSError:
        cleanup_warnings.append(f"已发布归档；临时目录未清理: {staging}")

    return {
        "root": str(root_path),
        "archive": str(destination_path),
        "format": "mpq",
        "backend": caps["create_backend"],
        "count": len(verified),
        "files": verified,
        "excluded": excluded,
        "verified": True,
        "warnings": cleanup_warnings,
    }
