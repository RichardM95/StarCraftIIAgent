"""Local CascLib reads isolated from the calling Python process. No online APIs."""
from __future__ import annotations

import base64
import ctypes as C
import json
import os
import queue
import struct
import subprocess
import sys
import threading
from pathlib import Path


def pe_bits(path: Path) -> int:
    with path.open('rb') as f:
        if f.read(2) != b'MZ':
            raise ValueError('Not a PE DLL: ' + str(path))
        f.seek(0x3c)
        offset = struct.unpack('<I', f.read(4))[0]
        f.seek(offset)
        if f.read(4) != b'PE\0\0':
            raise ValueError('Invalid PE signature')
        machine = struct.unpack('<H', f.read(2))[0]
    if machine not in {0x8664, 0x14c}:
        raise ValueError(f'Unsupported PE machine: {machine:x}')
    return 64 if machine == 0x8664 else 32


def wanted(name: str) -> bool:
    name = name.replace('\\', '/').lower()
    parts = name.split('/')
    if len(parts) < 3 or parts[0] not in {'mods', 'campaigns'}:
        return False
    component = next((i for i, p in enumerate(parts[1:], 1) if p.endswith(('.sc2mod', '.sc2campaign'))), None)
    if component is None:
        return False
    relative_parts = parts[component + 1:]
    if not relative_parts or any(p.endswith(('.sc2map', '.sc2maps', '.sc2assets')) for p in relative_parts):
        return False
    relative = '/'.join(relative_parts)
    if parts[-1] in {'documentinfo', 'documentheader', 'componentlist.sc2components', 'standardinfo'}:
        return True
    if relative in {'documentinfo', 'documentheader', 'componentlist.sc2components', 'standardinfo',
                    'base.sc2data/gamedata.xml', 'base.sc2data/triggerlibs/librarylist.xml', 'triggers'}:
        return True
    if relative.startswith('base.sc2data/gamedata/') and relative.endswith('.xml'):
        return True
    if relative.startswith('base.sc2data/') and relative.endswith(('.galaxy', '.sc2lib', '.triggerlib')):
        return True
    return (relative_parts[0] in {'zhcn.sc2data', 'enus.sc2data'} and
            relative.endswith(tuple('/localizeddata/' + n for n in
                                    ('gamestrings.txt', 'objectstrings.txt', 'triggerstrings.txt', 'gamehotkeys.txt'))))


class CascProcess:
    """One storage handle per child; timeout or a native crash kills only the child."""
    def __init__(self, dll: Path, install: Path, encoding='ansi', timeout=60):
        if timeout <= 0:
            raise ValueError('CASC timeout must be positive')
        if pe_bits(dll) != struct.calcsize('P') * 8:
            raise ValueError('CascLib/Python bitness mismatch')
        self.timeout = timeout
        self.messages = queue.Queue()
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        self.process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                                         str(dll), str(install), encoding],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        encoding='utf-8', env=env)
        self.stderr = []
        def receive():
            try:
                for line in self.process.stdout:
                    self.messages.put(json.loads(line))
            except Exception as exc:
                self.messages.put({'error': 'Worker protocol: ' + str(exc)})
            finally:
                self.messages.put({'error': 'CASC child exited; native crash or startup failure'})
        def receive_errors():
            try:
                self.stderr.extend(self.process.stderr)
            except (OSError, ValueError):
                pass  # The child has been reaped and its pipes are closing.
        self.readers = [threading.Thread(target=receive, daemon=True),
                        threading.Thread(target=receive_errors, daemon=True)]
        for thread in self.readers:
            thread.start()
        try:
            self._receive()
        except Exception:
            self.close()
            raise

    def _receive(self):
        try:
            response = self.messages.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise ValueError('CASC child timed out')
        if 'error' in response:
            self.close()
            raise ValueError(response['error'] + '; ' + ''.join(self.stderr)[-1500:])
        return response

    def request(self, op, **kwargs):
        try:
            self.process.stdin.write(json.dumps({'op': op, **kwargs}) + '\n')
            self.process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise ValueError('CASC child pipe closed') from exc
        response = self._receive()
        if response.get('request_error'):
            raise ValueError(response['request_error'])
        return response

    def read(self, name):
        result = self.request('read', name=name)
        return None if result.get('missing') else base64.b64decode(result['data'], validate=True)

    def names(self):
        return self.request('list')['files']

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=5)
        for thread in getattr(self, 'readers', []):
            thread.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream and not stream.closed:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class NativeCasc:
    def __init__(self, dll, install, encoding):
        if os.name != 'nt':
            raise ValueError('This CascLib DLL adapter requires Windows')
        self.dll = C.WinDLL(str(dll), use_last_error=True)
        path_type = C.c_char_p if encoding == 'ansi' else C.c_wchar_p
        signatures = {
            'CascOpenStorage': [path_type, C.c_uint32, C.POINTER(C.c_void_p)],
            'CascCloseStorage': [C.c_void_p],
            'CascOpenFile': [C.c_void_p, C.c_char_p, C.c_uint32, C.c_uint32, C.POINTER(C.c_void_p)],
            'CascGetFileSize64': [C.c_void_p, C.POINTER(C.c_uint64)],
            'CascReadFile': [C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32)],
            'CascCloseFile': [C.c_void_p], 'CascFindClose': [C.c_void_p]}
        for name, args in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, C.c_bool
        for name in ('CascFindFirstFile', 'CascFindNextFile'):
            getattr(self.dll, name)  # Probe verifies enumeration exports before opening storage.
        self.handle = C.c_void_p()
        path = str(install).encode('mbcs') if encoding == 'ansi' else str(install)
        if not self.dll.CascOpenStorage(path, 0xFFFFFFFF, C.byref(self.handle)):
            raise ValueError(f'CascOpenStorage ({encoding}) failed: {C.get_last_error()}')

    def read(self, name):
        handle = C.c_void_p()
        # Strict data checking; never use the flag that replaces encrypted data with zeroes.
        if not self.dll.CascOpenFile(self.handle, name.replace('/', '\\').encode('ascii'),
                                      0xFFFFFFFF, 0x10, C.byref(handle)):
            if C.get_last_error() in {2, 3}:
                return None
            raise ValueError(f'CascOpenFile {name}: {C.get_last_error()}')
        try:
            size = C.c_uint64()
            if not self.dll.CascGetFileSize64(handle, C.byref(size)):
                raise ValueError(f'CascGetFileSize64 {name}: {C.get_last_error()}')
            if size.value > 64 * 1024 * 1024:
                raise ValueError('Oversized CASC file: ' + name)
            chunks, remaining = [], size.value
            while remaining:
                buffer = C.create_string_buffer(min(remaining, 1024 * 1024))
                count = C.c_uint32()
                if not self.dll.CascReadFile(handle, buffer, len(buffer), C.byref(count)) or not count.value:
                    raise ValueError('Short/failed CASC read: ' + name)
                if count.value > min(remaining, len(buffer)):
                    raise ValueError('Invalid CASC read count')
                chunks.append(buffer.raw[:count.value])
                remaining -= count.value
            return b''.join(chunks)
        finally:
            self.dll.CascCloseFile(handle)

    def names(self):
        class FindData(C.Structure):
            _fields_ = [('name', C.c_char * 260), ('ckey', C.c_ubyte * 16), ('ekey', C.c_ubyte * 16),
                        ('tags', C.c_uint64), ('size', C.c_uint64), ('plain', C.c_char_p),
                        ('file_id', C.c_uint32), ('locale', C.c_uint32), ('content', C.c_uint32),
                        ('spans', C.c_uint32), ('available', C.c_uint32, 1), ('name_type', C.c_uint32)]
        first, next_ = self.dll.CascFindFirstFile, self.dll.CascFindNextFile
        first.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(FindData), C.c_void_p]
        first.restype = C.c_void_p
        next_.argtypes, next_.restype = [C.c_void_p, C.POINTER(FindData)], C.c_bool
        result = []
        data = FindData()
        handle = first(self.handle, b'*', C.byref(data), None)
        if handle in {None, 0, C.c_void_p(-1).value}:
            raise ValueError('CASC filename enumeration failed: ' + str(C.get_last_error()))
        try:
            while True:
                name = data.name.decode('ascii', errors='strict').replace('\\', '/')
                if wanted(name):
                    result.append(name)
                if not next_(handle, C.byref(data)):
                    if C.get_last_error() not in {0, 18}:
                        raise ValueError('CASC enumeration interrupted: ' + str(C.get_last_error()))
                    break
        finally:
            self.dll.CascFindClose(handle)
        return sorted(set(result), key=str.casefold)

    def close(self):
        self.dll.CascCloseStorage(self.handle)


def worker(dll, install, encoding):
    store = None
    try:
        store = NativeCasc(dll, install, encoding)
        print(json.dumps({'ready': True}), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if request['op'] == 'list':
                    result = {'files': store.names()}
                elif request['op'] == 'read':
                    data = store.read(request['name'])
                    result = {'missing': True} if data is None else {'data': base64.b64encode(data).decode('ascii')}
                else:
                    raise ValueError('Unknown CASC request')
            except Exception as exc:
                result = {'request_error': str(exc)}
            print(json.dumps(result), flush=True)
    except Exception as exc:
        print(json.dumps({'error': str(exc)}), flush=True)
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    worker(*sys.argv[1:])
