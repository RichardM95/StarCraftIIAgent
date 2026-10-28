import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
import subprocess
import sys
import pytest

from supervisor.agent_bridge import process_lock, runtime_base
from supervisor.concurrency import global_slot
from supervisor.manager import Manager, TaskSpec
from supervisor.router import TaskRouter


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('SC2_AGENT_RUNTIME_ROOT', str(tmp_path / 'runtime'))


@pytest.mark.asyncio
async def test_cross_client_task_index_request_deduplication_and_source_conflict(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a.txt').write_text('before')
    calls = []
    async def fake(self, task_id, spec):
        calls.append(task_id)
        (self.directory(task_id) / 'workspace/a.txt').write_text('candidate')
        self.save(task_id, state='worker_completed', worker_completed=True)
    monkeypatch.setattr(Manager, '_execute', fake)
    first, second = TaskRouter(), TaskRouter()
    spec = TaskSpec(goal='edit', request_id='unique', workspace=str(source), allowed_files=['a.txt'], acceptance='check bytes')
    try:
        record = await first.submit(spec)
        await first.for_task(record['task_id']).jobs[record['task_id']]
        duplicate = await second.submit(spec)
        assert duplicate['task_id'] == record['task_id']
        assert len(calls) == 1
        assert second.result(record['task_id'])['changes'][0]['source_unchanged']
        (source / 'a.txt').write_text('manual change')
        with pytest.raises(ValueError, match='conflict'):
            second.integrate(record['task_id'], 'reviewed')
        assert (source / 'a.txt').read_text() == 'manual change'
    finally:
        await first.close()
        await second.close()


@pytest.mark.asyncio
async def test_generated_galaxy_cannot_integrate(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'MapScript.galaxy').write_text('void InitMap() {}')
    async def fake(self, task_id, spec):
        (self.directory(task_id) / 'workspace/MapScript.galaxy').write_text('void InitMap() { int a; }')
        self.save(task_id, state='worker_completed', worker_completed=True)
    monkeypatch.setattr(Manager, '_execute', fake)
    manager = Manager(tmp_path / 'state')
    try:
        record = await manager.submit(TaskSpec(goal='edit', workspace=str(source), allowed_files=['MapScript.galaxy'], acceptance='review'))
        await manager.jobs[record['task_id']]
        with pytest.raises(ValueError, match='Generated Galaxy'):
            manager.integrate(record['task_id'], 'reviewed')
        assert (source / 'MapScript.galaxy').read_text() == 'void InitMap() {}'
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_four_slots_shared_with_other_process_and_released_on_exit(tmp_path):
    async with AsyncExitStack() as stack:
        for _ in range(4):
            await stack.enter_async_context(global_slot(4))
        code = '''from supervisor.agent_bridge import process_lock,runtime_base
blocked=0
for i in range(4):
    try:
        with process_lock(runtime_base()/'deepseek/slots'/(str(i)+'.lock')): pass
    except BlockingIOError: blocked+=1
print(blocked)
'''
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == '4'
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.2):
                async with global_slot(4):
                    pytest.fail('fifth task was admitted')
    async with global_slot(4):
        pass


def test_competing_integration_lock_is_rejected(tmp_path):
    path = tmp_path / 'integration.lock'
    with process_lock(path):
        code = 'from supervisor.agent_bridge import process_lock\nfrom pathlib import Path\nwith process_lock(Path(' + repr(str(path)) + ')): pass'
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], capture_output=True, text=True)
        assert proc.returncode != 0
        assert 'busy' in proc.stderr


@pytest.mark.asyncio
async def test_cancelled_bridge_reaps_its_python_child(tmp_path, monkeypatch):
    import supervisor.sc2_bridge as bridge_module
    from supervisor.sc2_bridge import SC2BridgeWorker
    from supervisor.windows import process_identity
    marker = tmp_path / 'child.pid'
    command = [getattr(sys, '_base_executable', sys.executable), '-c',
        'import os,time;from pathlib import Path;Path(' + repr(str(marker)) + ').write_text(str(os.getpid()));time.sleep(120)']
    monkeypatch.setattr(bridge_module, 'runtime_command', lambda *args: command)
    source = tmp_path / 'source'
    source.mkdir()
    worker = SC2BridgeWorker(source, tmp_path / 'run')
    task = asyncio.create_task(worker._execute('test-hash'))
    async with asyncio.timeout(10):
        while not marker.exists():
            await asyncio.sleep(0.05)
    pid = int(marker.read_text())
    assert process_identity(pid) is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process_identity(pid) is None
