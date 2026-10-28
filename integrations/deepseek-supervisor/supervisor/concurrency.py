"""Cross-process limits and short claims shared by CLI and MCP managers."""
import asyncio
from contextlib import asynccontextmanager
import functools
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
from .agent_bridge import process_lock, runtime_base


@asynccontextmanager
async def global_slot(limit):
    while True:
        for number in range(limit):
            claim = process_lock(runtime_base() / 'deepseek/slots' / (str(number) + '.lock'))
            try:
                claim.__enter__()
            except BlockingIOError:
                continue
            try:
                yield
            finally:
                claim.__exit__(None, None, None)
            return
        await asyncio.sleep(0.1)


def submission_lock(fn):
    @functools.wraps(fn)
    async def invoke(self, *args, **kwargs):
        with process_lock(self.state_root / 'submission.lock'):
            return await fn(self, *args, **kwargs)
    return invoke


def limited_worker(fn):
    @functools.wraps(fn)
    async def invoke(self, *args, **kwargs):
        # Retain the slot through the worker's finally/child-process cleanup.
        async with global_slot(self.concurrency):
            return await fn(self, *args, **kwargs)
    return invoke


def task_claim(fn):
    @functools.wraps(fn)
    async def invoke(self, task_id, *args, **kwargs):
        with process_lock(self.state_root / 'claims' / (task_id + '.lock')):
            return await fn(self, task_id, *args, **kwargs)
    return invoke


def integration_lock(fn):
    @functools.wraps(fn)
    def invoke(self, task_id, *args, **kwargs):
        spec = json.loads((self.directory(task_id) / 'spec.json').read_text('utf-8'))
        key = hashlib.sha256(str(Path(spec['workspace']).resolve()).casefold().encode()).hexdigest()
        with ExitStack() as stack:
            stack.enter_context(process_lock(self.state_root / 'claims' / (task_id + '.lock')))
            stack.enter_context(process_lock(runtime_base() / 'deepseek/integration-locks' / (key + '.lock')))
            source = Path(spec['workspace'])
            if (source / 'DocumentInfo').is_file():
                stack.enter_context(process_lock(source / '.sc2-mcp/transaction.lock'))
            return fn(self, task_id, *args, **kwargs)
    return invoke
