from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath

from .errors import SC2Error

EXCLUDED = {"_codex_backups", ".git", ".venv", "__pycache__", ".pytest_cache", ".sc2-mcp"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guard_absolute_path(path: Path) -> Path:
    """Check existing ancestors before resolving away junctions and symlinks."""
    target = Path(os.path.abspath(path))
    for member in (target, *target.parents):
        if member.is_symlink() or (hasattr(member, "is_junction") and member.is_junction()):
            raise SC2Error("linked_path", "不通过符号链接或目录联接访问工作文件", path=str(member))
        if member != target and member.exists() and not member.is_dir():
            raise SC2Error("path_collision", "路径的父级被文件占用", path=str(member))
    if target.is_file() and target.stat().st_nlink > 1:
        raise SC2Error("hardlinked_file", "文件含硬链接，请使用独立副本", path=str(target))
    return target


def normalize_relative_path(relative: str) -> str:
    if not isinstance(relative, str) or not relative:
        raise SC2Error("unsafe_path", "地图相对路径必须为非空字符串")
    win = PureWindowsPath(relative)
    parts = relative.replace("\\", "/").split("/")
    if (win.is_absolute() or win.drive or not relative or
            any(p in ("", ".", "..") or p.casefold() in EXCLUDED or
                re.search(r'[<>:"|?*\x00-\x1f]', p) or p.endswith((" ", ".")) or
                re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', p) for p in parts)):
        raise SC2Error("unsafe_path", "无效的地图相对路径", path=relative)
    return "/".join(parts)


def safe_path(root: Path, relative: str) -> Path:
    parts = normalize_relative_path(relative).split("/")
    base = guard_absolute_path(Path(root)).resolve()
    if not base.is_dir():
        raise SC2Error("project_missing", "地图组件目录不存在", path=str(base))
    target = base.joinpath(*parts)
    resolved = target.resolve()
    if not resolved.is_relative_to(base):
        raise SC2Error("path_escape", "路径越出地图目录", path=relative)
    current = target
    while current != base:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise SC2Error("linked_path", "不通过符号链接或目录联接修改地图", path=relative)
        current = current.parent
    if target.is_file() and target.stat().st_nlink > 1:
        raise SC2Error("hardlinked_file", "地图文件含硬链接，请使用独立副本", path=relative)
    parent = base
    for part in parts:
        if not parent.exists():
            break
        if not parent.is_dir():
            raise SC2Error("path_collision", "组件父路径被文件占用", path=relative)
        aliases = [child.name for child in parent.iterdir() if child.name.casefold() == part.casefold()]
        if len(aliases) > 1 or (aliases and aliases[0] != part):
            raise SC2Error("case_collision", "路径大小写与已有组件冲突", path=relative, existing=aliases)
        parent /= part
    return target


def map_files(root: Path):
    root = guard_absolute_path(Path(root)).resolve()
    if not root.is_dir():
        raise SC2Error("project_missing", "地图组件目录不存在", path=str(root))
    def walk_error(exc):
        raise SC2Error("snapshot_failed", "不能完整读取地图目录", error=str(exc)) from exc
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d.casefold() not in EXCLUDED)
        names = dirs + files
        if len({name.casefold() for name in names}) != len(names):
            raise SC2Error("case_collision", "地图目录中存在大小写冲突", path=str(directory))
        for name in dirs:
            normalize_relative_path((Path(directory) / name).relative_to(root).as_posix())
            guard_absolute_path(Path(directory) / name)
        for name in sorted(files):
            rel = (Path(directory) / name).relative_to(root).as_posix()
            normalize_relative_path(rel)
            yield rel, guard_absolute_path(Path(directory) / name)


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    names = set()
    for rel, path in map_files(root):
        if rel.casefold() in names:
            raise SC2Error("case_collision", "组件文件名大小写冲突", path=rel)
        names.add(rel.casefold())
        result[rel] = digest(path.read_bytes())
    return result


def atomic_write(path: Path, data: bytes):
    if not isinstance(data, bytes):
        raise SC2Error("invalid_content", "原子写入内容必须为 bytes")
    path = guard_absolute_path(path)
    if path.exists() and not path.is_file():
        raise SC2Error("path_collision", "文件目标被目录占用", path=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sc2-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        guard_absolute_path(path)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: Path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))


@contextlib.contextmanager
def file_lock(path: Path):
    path = guard_absolute_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("a+b")
    acquired = False
    try:
        if f.seek(0, 2) == 0:
            f.write(b"\0")
            f.flush()
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise SC2Error("project_busy", "另一个操作正在使用此项目，请稍后重试") from exc
        yield
    finally:
        if acquired:
            f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()
