"""Read-only component paths: directory files or original MPQ/member identities.

MemberPath has no OS-backed file. Parsers must use .open()/read_bytes(), never
pass str(member) to an external process or a parser that opens OS paths itself.
No extraction, persistent cache, game writes, or network access occurs here.
"""
from __future__ import annotations

import atexit
import base64
import io
import os
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from contextvars import ContextVar
from functools import wraps

from sc2_mpq import MpqProcess, MAX_TOTAL, digest, member_name

SUFFIXES = {'.sc2mod', '.sc2map', '.sc2campaign'}
_sources = {}
_session = ContextVar('sc2_component_readers', default=None)


def readers():
    current = _session.get()
    return _sources if current is None else current


def component_session(function):
    """Scope native handles to one command, including in-process CLI callers."""
    @wraps(function)
    def run(*args, **kwargs):
        if _session.get() is not None:
            return function(*args, **kwargs)
        token = _session.set({})
        try:
            return function(*args, **kwargs)
        finally:
            close_components()
            _session.reset(token)
    return run


def archive_of(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        if parent.suffix.casefold() in SUFFIXES and parent.is_file():
            return parent
    return None


def component_exists(path):
    path = Path(path)
    return path.suffix.casefold() in SUFFIXES and (path.is_dir() or path.is_file())


def require_editable(path):
    if archive_of(path):
        raise ValueError('Packed component is read-only; unpack before editing: python tools/sc2-archive.py unpack "'
                         + str(archive_of(path)) + '" --output "<new Components path>" --apply')


class ArchiveSource:
    def __init__(self, path, timeout=60):
        self.path = Path(path).resolve()
        self.stamp = self.path.stat()
        if self.stamp.st_size > MAX_TOTAL:
            raise ValueError('Archive resource limit exceeded: ' + str(self.path))
        self.sha256 = digest(self.path)
        self.process = MpqProcess(self.path, timeout=timeout)
        self.active = False
        self.consumed = 0
        self.member_digests = {}
        try:
            self.members = {m['name'].casefold(): m for m in self.process.names()}
            self.check(hashes=True)
        except Exception:
            self.close()
            raise

    def check(self, hashes=False):
        current = self.path.stat()
        if ((current.st_size, current.st_mtime_ns, current.st_ino) !=
                (self.stamp.st_size, self.stamp.st_mtime_ns, self.stamp.st_ino)
                or hashes and digest(self.path) != self.sha256):
            raise ValueError('Archive changed during operation; rerun: ' + str(self.path))

    def close(self):
        self.process.close()

    def open(self, name):
        self.check()
        if self.active:
            raise ValueError('Concurrent member streams on one archive are unsupported')
        if name.casefold() not in self.members:
            raise FileNotFoundError(str(self.path / name))
        size = self.process.request('open', name=name)['size']
        self.active = True
        return io.BufferedReader(MemberStream(self, size))


class MemberStream(io.RawIOBase):
    def __init__(self, source, remaining):
        super().__init__()
        self.source, self.remaining = source, remaining

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.closed:
            raise ValueError('Read on closed member')
        if not self.remaining:
            return 0
        self.source.check()
        size = min(len(buffer), self.remaining, 1024 * 1024)
        if self.source.consumed + size > MAX_TOTAL:
            raise ValueError('MPQ cumulative read budget exceeded')
        raw = base64.b64decode(self.source.process.request('chunk', size=size)['data'], validate=True)
        if len(raw) != size:
            raise ValueError('Short MPQ worker response')
        buffer[:size] = raw
        self.remaining -= size
        self.source.consumed += size
        return size

    def close(self):
        if not self.closed:
            try:
                self.source.process.request('close_file')
            finally:
                self.source.active = False
                super().close()


def source_for(path):
    archive = archive_of(path)
    if archive is None:
        return None
    sources = readers()
    if archive not in sources:
        sources[archive] = ArchiveSource(archive)
    sources[archive].check()
    return sources[archive]


def verify_archives():
    for source in readers().values():
        source.check(hashes=True)


def close_components():
    for source in readers().values():
        source.close()
    readers().clear()


atexit.register(close_components)


class MemberPath(type(Path())):
    """Read-only logical path. Display always retains the original archive path."""
    def resolve(self, strict=False):
        absolute = Path(os.path.abspath(self))
        return MemberPath(absolute) if archive_of(absolute) else absolute.resolve(strict=strict)

    def _location(self):
        source = source_for(self)
        if source is None:
            raise ValueError('Archive source disappeared: ' + str(self))
        relative = Path(self).relative_to(source.path).as_posix()
        if relative != '.':
            member_name(relative)
        return source, '' if relative == '.' else relative

    def is_file(self, *, follow_symlinks=True):
        if archive_of(self) is None:
            return Path(self).is_file()
        source, name = self._location()
        return name.casefold() in source.members

    def is_dir(self):
        if archive_of(self) is None:
            return Path(self).is_dir()
        source, name = self._location()
        prefix = name.casefold().rstrip('/') + '/' if name else ''
        return not name or any(n.startswith(prefix) for n in source.members)

    def exists(self, *, follow_symlinks=True):
        return self.is_file() or self.is_dir()

    def stat(self, *, follow_symlinks=True):
        if archive_of(self) is None:
            return Path(self).stat(follow_symlinks=follow_symlinks)
        source, name = self._location()
        if not self.is_file():
            raise FileNotFoundError(str(self))
        return SimpleNamespace(st_size=source.members[name.casefold()]['size'],
                               st_mtime_ns=source.stamp.st_mtime_ns)

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        if archive_of(self) is None:
            if mode not in {'r', 'rb', 'rt'}:
                raise ValueError('MemberPath only supports reading')
            return Path(self).open(mode, buffering, encoding, errors, newline)
        if mode not in {'r', 'rb', 'rt'}:
            require_editable(self)
        source, name = self._location()
        stream = source.open(name)
        return stream if 'b' in mode else io.TextIOWrapper(stream, encoding=encoding, errors=errors, newline=newline)

    def iterdir(self):
        if archive_of(self) is None:
            return Path(self).iterdir()
        source, name = self._location()
        prefix = name.rstrip('/') + '/' if name else ''
        children = {}
        for member in source.members.values():
            if member['name'].casefold().startswith(prefix.casefold()):
                child = member['name'][len(prefix):].split('/')[0]
                children.setdefault(child.casefold(), child)
        return iter(sorted((self / child for child in children.values()), key=str))

    def glob(self, pattern, *, case_sensitive=None):
        # pathlib match preserves segment boundaries; support recursive ** explicitly.
        source, name = self._location()
        prefix = name.rstrip('/') + '/' if name else ''
        def match(relative):
            relative, pat = relative.casefold(), str(pattern).replace('\\', '/').casefold()
            if pat.startswith('**/'):
                return PurePosixPath(relative).match(pat) or PurePosixPath(relative).match(pat[3:])
            return len(relative.split('/')) == len(pat.split('/')) and PurePosixPath(relative).match(pat)
        return iter(sorted((MemberPath(source.path / m['name']) for m in source.members.values()
                            if m['name'].casefold().startswith(prefix.casefold()) and match(m['name'][len(prefix):])), key=str))

    def rglob(self, pattern, *, case_sensitive=None):
        return self.glob('**/' + str(pattern))

    def _reject_write(self, *args, **kwargs):
        raise ValueError('Archive member paths are read-only; use tools/sc2-archive.py unpack before editing')

    mkdir = rename = replace = unlink = rmdir = touch = chmod = symlink_to = hardlink_to = _reject_write


def component_path(path):
    return MemberPath(Path(path).absolute()) if archive_of(path) else Path(path)


def parse_xml(path, **kwargs):
    import xml.etree.ElementTree as ET
    with component_path(path).open('rb') as stream:
        return ET.parse(stream, **kwargs)


def provenance(path, *, member_sha256=None):
    source = source_for(path)
    if source is None:
        return None
    name = Path(path).relative_to(source.path).as_posix()
    key = name.casefold()
    if member_sha256 is not None:
        if key in source.member_digests and source.member_digests[key] != member_sha256:
            raise ValueError('Member changed during operation: ' + str(path))
        source.member_digests[key] = member_sha256
    if key not in source.member_digests:
        source.member_digests[key] = digest(component_path(path))
    return {'container': 'mpq', 'archive': str(source.path), 'archive_sha256': source.sha256,
            'member': source.members[key]['name'], 'locale': source.members[key]['locale'],
            'member_sha256': source.member_digests[key]}
