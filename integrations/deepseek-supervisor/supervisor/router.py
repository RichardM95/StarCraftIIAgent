"""Persistent task index with per-project managers shared across CLI/MCP."""
import json
from pathlib import Path
import uuid
import threading
from .agent_bridge import project_runtime, runtime_base, process_lock
from .manager import Manager, atomic_json


class TaskRouter:
    def __init__(self):
        self.root = runtime_base() / 'deepseek'
        self.managers = {}
        self.lock = threading.RLock()

    def _index(self):
        path = self.root / 'routing.json'
        return json.loads(path.read_text('utf-8')) if path.exists() else {}

    def _manager(self, state):
        state = str(Path(state).resolve())
        with self.lock:
            if state not in self.managers:
                self.managers[state] = Manager(Path(state))
            return self.managers[state]

    def for_task(self, task_id):
        with process_lock(self.root / 'routing.lock', timeout=2):
            state = self._index().get(task_id)
        if not state:
            raise ValueError('Unknown task ID')
        return self._manager(state)

    async def submit(self, spec):
        # Assign the ID before persisting so interrupted submissions remain discoverable.
        if not spec.request_id:
            spec = spec.model_copy(update={'request_id': uuid.uuid4().hex})
        task_id = uuid.uuid5(uuid.NAMESPACE_URL, 'deepseek-supervisor:' + spec.request_id).hex
        state = project_runtime(spec.workspace) / 'deepseek/tasks'
        with process_lock(self.root / 'routing.lock', timeout=2):
            index = self._index()
            if task_id in index and index[task_id] != str(state):
                raise ValueError('request_id already belongs to a different project')
            index[task_id] = str(state)
            atomic_json(self.root / 'routing.json', index)
        return await self._manager(state).submit(spec)

    async def continue_task(self, task_id, prompt):
        return await self.for_task(task_id).continue_task(task_id, prompt)

    def status(self, task_id):
        return self.for_task(task_id).status(task_id)

    def result(self, task_id):
        return self.for_task(task_id).result(task_id)

    async def cancel(self, task_id):
        return await self.for_task(task_id).cancel(task_id)

    def integrate(self, task_id, review_note):
        return self.for_task(task_id).integrate(task_id, review_note)

    def list_tasks(self, limit=20):
        with process_lock(self.root / 'routing.lock', timeout=2):
            states = set(self._index().values())
        records = [record for state in states for record in self._manager(state).list_tasks(limit)]
        return sorted(records, key=lambda r: r.get('updated_at', 0), reverse=True)[:limit]

    async def close(self):
        for manager in self.managers.values():
            await manager.close()
