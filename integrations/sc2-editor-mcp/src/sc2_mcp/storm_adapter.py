"""Adapt the workspace's pinned, process-isolated StormLib implementation."""
import base64
import shutil
import tempfile
from pathlib import Path

from . import agent_bridge  # Install the workspace tools path before imports.
from sc2_mpq import MpqProcess, dll_info, CHUNK, INTERNAL


def capabilities():
    return dll_info()


class Reader:
    backend = 'bundled_stormlib'

    def __init__(self, path):
        self.worker = MpqProcess(path)
        try:
            self.rows = {row['name']: row for row in self.worker.names() if row['name'].casefold() not in INTERNAL}
        except BaseException:
            self.close()
            raise

    def members(self):
        return list(self.rows)

    def read(self, name):
        size = self.worker.request('open', name=name)['size']
        chunks = []
        try:
            while size:
                data = base64.b64decode(self.worker.request('chunk', size=min(size, CHUNK))['data'], validate=True)
                if not data or len(data) > size:
                    raise ValueError('Short or excessive MPQ read')
                chunks.append(data)
                size -= len(data)
            return b''.join(chunks)
        finally:
            self.worker.request('close_file')

    def close(self):
        self.worker.close()


def create(destination, entries, cancel=None):
    from .archives import _check_cancel
    # The native writer consumes an explicit source tree, never arbitrary paths.
    with tempfile.TemporaryDirectory(prefix='sc2-storm-') as temp:
        root = Path(temp)
        members = {}
        for name, source in entries:
            _check_cancel(cancel)
            from sc2_mpq import member_name
            target = root / member_name(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with Path(source).open('rb') as reader, target.open('wb') as writer:
                while chunk := reader.read(CHUNK):
                    _check_cancel(cancel)
                    writer.write(chunk)
            members[name] = {'size': target.stat().st_size}
        with MpqProcess(timeout=1800) as worker:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(worker.request, 'pack', source=str(root), output=str(destination.resolve()), members=members)
                while True:
                    try:
                        future.result(timeout=.1)
                        break
                    except TimeoutError:
                        if cancel is not None and cancel.is_set():
                            worker.process.kill()
                            worker.process.wait(timeout=5)
                            # Unblock the parent's waiting protocol read.
                            worker.messages.put({'error':'MPQ cancelled'})
                            try: future.result(timeout=5)
                            except Exception: pass
                            _check_cancel(cancel)
        _check_cancel(cancel)
