"""StormLib boundary. Native code runs only in a child process, never at import.

Archive ABI and streaming writer adapted from SC2EditorTool (RichardM, MIT,
2026). See vendor/stormlib/TOOLBOX-LICENSE.txt and provenance.json.
"""
from __future__ import annotations

import base64
import ctypes as C
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

from sc2_casc import CascProcess, pe_bits

VENDOR = Path(__file__).parent / 'vendor/stormlib'
DLL = VENDOR / 'StormLib.dll'
DLL_SHA256 = 'b8de24ca85b0b1919cf76d01394feef4d4cb065eb0df3a7480e3b2a1145aae79'
CHUNK = 1024 * 1024
MAX_MEMBERS, MAX_FILE, MAX_TOTAL = 200_000, 2 * 1024**3, 16 * 1024**3
INTERNAL = {'(listfile)', '(attributes)', '(signature)'}
EXCLUDED = {'.git', '.hg', '.svn', '.sc2editortool'}


def member_name(name):
    """Validate before normalization, including Windows aliases and devices."""
    name = name.replace('\\', '/')
    if not name or len(name) > 4096 or name.startswith('/'):
        raise ValueError('Unsafe archive member: ' + name)
    for part in name.split('/'):
        if (part in {'', '.', '..'} or part != part.rstrip(' .') or len(part) > 100
                or re.search(r'[<>:"|?*\x00-\x1f]', part)
                or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])', part.split('.')[0], re.I)):
            raise ValueError('Unsafe archive member: ' + name)
    return name


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dll_info():
    if os.name != 'nt':
        raise ValueError('Bundled StormLib requires Windows x64')
    info = {'path': str(DLL.resolve()), 'version': '9.26.0.3',
            'sha256': digest(DLL), 'bits': pe_bits(DLL), 'charset': 'Unicode archive / UTF-8 member'}
    if info['sha256'] != DLL_SHA256:
        raise ValueError('Bundled StormLib fingerprint mismatch: ' + str(DLL))
    return info


class MpqProcess(CascProcess):
    def __init__(self, source=None, timeout=60):
        dll_info()
        super().__init__(DLL, Path(source) if source else Path('.'), timeout=timeout,
            _command=[sys.executable, '-B', str(Path(__file__).resolve()), str(source or '')], _label='MPQ')

    def names(self):
        return self.request('list')['members']


class NativeStorm:
    def __init__(self, source=None):
        dll_info()
        self.dll = C.WinDLL(str(DLL), use_last_error=True)
        h, u, p = C.c_void_p, C.c_uint32, C.POINTER(C.c_void_p)
        specs = {
            'SFileOpenArchive': (C.c_bool, C.c_wchar_p, u, u, p),
            'SFileCloseArchive': (C.c_bool, h),
            'SFileOpenFileEx': (C.c_bool, h, C.c_char_p, u, p),
            'SFileCloseFile': (C.c_bool, h),
            'SFileGetFileSize': (u, h, C.POINTER(u)),
            'SFileReadFile': (C.c_bool, h, h, u, C.POINTER(u), h),
            'SFileFindFirstFile': (h, h, C.c_char_p, h, C.c_wchar_p),
            'SFileFindNextFile': (C.c_bool, h, h), 'SFileFindClose': (C.c_bool, h),
            'SFileEnumLocales': (u, h, C.c_char_p, C.POINTER(u), C.POINTER(u), u),
            'SFileSetLocale': (u, u),
            'SFileGetFileInfo': (C.c_bool, h, u, h, u, C.POINTER(u)),
            'SFileCreateArchive': (C.c_bool, C.c_wchar_p, u, u, p),
            'SFileCreateFile': (C.c_bool, h, C.c_char_p, C.c_uint64, u, u, u, p),
            'SFileWriteFile': (C.c_bool, h, h, u, u),
            'SFileFinishFile': (C.c_bool, h),
        }
        for name, signature in specs.items():
            setattr(self, name, C.WINFUNCTYPE(*signature, use_last_error=True)((name, self.dll)))
        self.archive, self.file = h(), h()
        self.remaining = 0
        self.members = None
        if source:
            self.require(self.SFileOpenArchive(str(Path(source).resolve()), 0, 0x00100100, C.byref(self.archive)), 'open archive')

    @staticmethod
    def require(ok, action):
        if not ok:
            raise OSError(f'StormLib {action} failed (error {C.get_last_error()})')

    def names(self):
        if self.members is not None:
            return self.members
        class Find(C.Structure):
            _fields_ = [('name', C.c_char * 260), ('plain', C.c_void_p),
                       *[(n, C.c_uint32) for n in ('hash', 'block', 'size', 'flags', 'compressed', 'low', 'high', 'locale')]]
        data, seen, members, total = Find(), set(), [], 0
        search = self.SFileFindFirstFile(self.archive, b'*', C.byref(data), None)
        self.require(search not in {None, 0, C.c_void_p(-1).value}, 'enumeration')
        try:
            while True:
                name = member_name(data.name.decode('utf-8', errors='strict'))
                if re.fullmatch(r'File[0-9a-f]{8}\..+', name, re.I):
                    raise ValueError('Unknown archive filename; complete enumeration unavailable: ' + name)
                if name.casefold() in seen:
                    raise ValueError('Duplicate/case/locale archive member: ' + name)
                seen.add(name.casefold())
                locales = (C.c_uint32 * 16)()
                count = C.c_uint32(16)
                error = self.SFileEnumLocales(self.archive, name.replace('/', '\\').encode('utf-8'), locales, C.byref(count), 0)
                if error or count.value != 1:
                    raise ValueError('Ambiguous/unknown archive locales: ' + name)
                total += data.size
                if len(members) >= MAX_MEMBERS or data.size > MAX_FILE or total > MAX_TOTAL:
                    raise ValueError('Archive resource limit exceeded: ' + name)
                members.append({'name': name, 'size': data.size, 'locale': locales[0]})
                C.set_last_error(0)
                if not self.SFileFindNextFile(search, C.byref(data)):
                    if C.get_last_error() not in {0, 18}:
                        raise OSError('Interrupted MPQ enumeration: ' + str(C.get_last_error()))
                    break
        finally:
            self.SFileFindClose(search)
        count = C.c_uint32()
        # StormLib v9.26 SFileInfoClass: SFileMpqNumberOfFiles = 36.
        self.require(self.SFileGetFileInfo(self.archive, 36, C.byref(count), C.sizeof(count), None), 'file count')
        if count.value != len(members):
            raise ValueError('MPQ enumeration incomplete: named members differ from archive file count')
        for name in seen:
            if any(str(p) in seen for p in PurePosixPath(name).parents if str(p) != '.'):
                raise ValueError('MPQ file/directory path collision: ' + name)
        self.members = members
        return members

    def open_file(self, name):
        self.close_file()
        member = next((m for m in self.names() if m['name'].casefold() == name.casefold()), None)
        if member is None:
            raise FileNotFoundError(name)
        self.SFileSetLocale(member['locale'])
        self.require(self.SFileOpenFileEx(self.archive, member['name'].replace('/', '\\').encode('utf-8'), 0, C.byref(self.file)), 'open ' + name)
        high = C.c_uint32()
        size = self.SFileGetFileSize(self.file, C.byref(high))
        if high.value or size == 0xFFFFFFFF or size != member['size'] or size > MAX_FILE:
            self.close_file()
            raise ValueError('Invalid MPQ member size: ' + name)
        self.remaining = size
        return size

    def chunk(self, size):
        size = min(size, CHUNK, self.remaining)
        if not size:
            return b''
        buffer, received = C.create_string_buffer(size), C.c_uint32()
        self.require(self.SFileReadFile(self.file, buffer, size, C.byref(received), None), 'read member')
        if received.value != size:
            raise ValueError('Short MPQ read')
        self.remaining -= size
        return buffer.raw

    def close_file(self):
        if self.file.value:
            self.SFileCloseFile(self.file)
            self.file = C.c_void_p()

    def pack(self, source, output, members):
        archive = C.c_void_p()
        # MPQ v2, regenerated listfile and attributes; no copied signature.
        flags = 0x01000000 | 0x00100000 | 0x00200000
        capacity = max(4, 1 << (len(members) + 2).bit_length())
        self.require(self.SFileCreateArchive(str(output), flags, capacity, C.byref(archive)), 'create archive')
        try:
            for name, entry in members.items():
                member_name(name)
                handle = C.c_void_p()
                self.require(self.SFileCreateFile(archive, name.replace('/', '\\').encode('utf-8'), 0,
                    entry['size'], 0, 0x80000200, C.byref(handle)), 'create ' + name)
                try:
                    with (Path(source) / name).open('rb') as stream:
                        while chunk := stream.read(CHUNK):
                            self.require(self.SFileWriteFile(handle, C.c_char_p(chunk), len(chunk), 0x02), 'write ' + name)
                finally:
                    self.require(self.SFileFinishFile(handle), 'finish ' + name)
        finally:
            self.SFileCloseArchive(archive)

    def close(self):
        self.close_file()
        if self.archive.value:
            self.SFileCloseArchive(self.archive)
            self.archive = C.c_void_p()


def worker(source):
    native = None
    try:
        native = NativeStorm(source or None)
        print(json.dumps({'ready': True}), flush=True)
        for line in sys.stdin:
            try:
                req = json.loads(line)
                op = req['op']
                if op == 'list':
                    result = {'members': native.names()}
                elif op == 'open':
                    result = {'size': native.open_file(member_name(req['name']))}
                elif op == 'chunk':
                    result = {'data': base64.b64encode(native.chunk(int(req['size']))).decode('ascii')}
                elif op == 'close_file':
                    native.close_file()
                    result = {}
                elif op == 'pack':
                    native.pack(req['source'], req['output'], req['members'])
                    result = {'written': True}
                else:
                    raise ValueError('Unknown MPQ operation')
            except Exception as exc:
                result = {'request_error': str(exc)}
            print(json.dumps(result), flush=True)
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), flush=True)
    finally:
        if native:
            native.close()


if __name__ == '__main__':
    worker(sys.argv[1])
