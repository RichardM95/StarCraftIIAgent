from __future__ import annotations

import copy
import hashlib
import time
import json
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import psutil

from .errors import SC2Error
from .storage import guard_absolute_path, write_json, file_lock

_ACTIVE = {"queued", "running", "cancelling"}


class _Cancellation(threading.Event):
    """Cooperative token that also observes cancellation by another process."""

    def __init__(self, marker: Path, reporter):
        super().__init__()
        self.marker = marker
        self.report_progress = reporter

    def is_set(self):
        if super().is_set():
            return True
        return guard_absolute_path(self.marker).exists()


class Jobs:
    def __init__(self, state: Path):
        self.state = guard_absolute_path(Path(state)).resolve()
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="sc2-job")
        self.items = {}
        self.futures = {}
        self.lock = threading.RLock()
        self.closed = False
        self.owner = {"pid": os.getpid(), "started": psutil.Process().create_time()}

    @staticmethod
    def _key(key):
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{32}", key):
            raise SC2Error("invalid_job_id", "任务 ID 不正确")
        return key

    def _path(self, key, suffix=".json"):
        return guard_absolute_path(self.state / "jobs" / (self._key(key) + suffix))

    @staticmethod
    def _owner_alive(item):
        owner = item.get("owner", {})
        try:
            pid, started = owner["pid"], owner["started"]
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                return False
            process = psutil.Process(pid)
            return process.is_running() and abs(process.create_time() - started) < 0.001
        except (psutil.Error, KeyError, TypeError, ValueError):
            return False

    def _save(self, item):
        # A reader holding the state file open without FILE_SHARE_DELETE makes the
        # atomic replace fail transiently on Windows (winerror 5/32/33). Retry that
        # narrow case only, with bounded backoff; anything else fails immediately.
        path = self._path(item["job_id"])
        attempts = 5
        for attempt in range(attempts):
            try:
                write_json(path, item)
                return
            except PermissionError as exc:
                if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == attempts - 1:
                    raise
                time.sleep(0.02 * 2 ** attempt)

    def submit(self, operation, fn):
        if not isinstance(operation, str) or not operation.strip() or not callable(fn):
            raise SC2Error("invalid_job", "任务名称必须非空且执行器必须可调用")
        key = uuid.uuid4().hex
        item = {"job_id": key, "operation": operation, "state": "queued", "progress": 0,
                "created_at": datetime.now(timezone.utc).isoformat(), "owner": dict(self.owner)}
        token = _Cancellation(self._path(key, ".cancel"),
                              lambda value, message=None: self.update_progress(key, value, message))

        def work():
            try:
                with self.lock:
                    if token.is_set():
                        raise SC2Error("cancelled", "操作已取消")
                    item.update(state="running", progress=1)
                    self._save(item)
                from .progress import current
                context = current.set(token)
                token.report_details = lambda **details: self.update_details(key, **details)
                try:
                    result = fn(token)
                finally:
                    current.reset(context)
                # A completed operation may have committed before cancellation
                # arrived. Record the late request without claiming a rollback.
                json.dumps(result, allow_nan=False)
                with self.lock:
                    item.update(state="completed", progress=100, result=result)
            except BaseException as exc:
                error = exc.as_dict() if isinstance(exc, SC2Error) else {"code": "internal_error", "message": str(exc)}
                with self.lock:
                    item.update(state="cancelled" if error["code"] == "cancelled" else "failed", error=error)
            finally:
                with self.lock:
                    item["cancel_requested"] = token.is_set()
                    item["finished_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(item)
                    self._path(key, ".cancel").unlink(missing_ok=True)

        with self.lock:
            if self.closed:
                raise SC2Error("jobs_closed", "任务管理器已关闭")
            self._save(item)
            self.items[key] = (item, token)
            try:
                self.futures[key] = self.pool.submit(work)
            except RuntimeError as exc:
                item.update(state="failed", error={"code": "jobs_closed", "message": str(exc)})
                self._save(item)
                raise SC2Error("jobs_closed", "任务执行器已关闭") from exc
            return copy.deepcopy(item)

    def submit_once(self, operation, request_id, binding, fn):
        identity = hashlib.sha256((operation + ':' + request_id).encode()).hexdigest()
        path = self.state / 'requests' / (identity + '.json')
        with file_lock(path.with_suffix('.lock')):
            if path.is_file():
                previous = json.loads(path.read_text('utf-8'))
                if previous['binding'] != binding:
                    raise SC2Error('request_conflict', '同一 request_id 的输入不能改变')
                job = self.status(previous['job_id'])
                if job['state'] not in {'interrupted', 'cancelled', 'failed'}:
                    return job
            job = self.submit(operation, fn)
            write_json(path, {'binding': binding, 'job_id': job['job_id']})
            return job

    def update_details(self, key, **details):
        with self.lock:
            item, _ = self.items[key]
            item.update(details, last_progress_at=datetime.now(timezone.utc).isoformat())
            item['elapsed_seconds'] = (datetime.now(timezone.utc)-datetime.fromisoformat(item['created_at'])).total_seconds()
            self._save(item)

    def update_progress(self, key, progress: int, message: str | None = None):
        self._key(key)
        if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 99:
            raise SC2Error("invalid_progress", "运行进度必须是 0 至 99 的整数")
        if message is not None and not isinstance(message, str):
            raise SC2Error("invalid_progress", "进度说明必须为字符串")
        with self.lock:
            if key not in self.items:
                raise SC2Error("job_not_local", "只能更新当前进程执行的任务进度")
            item, token = self.items[key]
            if item["state"] not in _ACTIVE:
                raise SC2Error("job_finished", "任务已结束")
            item["progress"] = max(item["progress"], progress)
            if message is not None:
                item["message"] = message
            if token.is_set():
                item["state"] = "cancelling"
            self._save(item)
            return copy.deepcopy(item)

    def status(self, key):
        self._key(key)
        with self.lock:
            if key in self.items:
                result = copy.deepcopy(self.items[key][0])
                if result["state"] in _ACTIVE and self.items[key][1].is_set():
                    result.update(state="cancelling", cancel_requested=True)
                return result
        path = self._path(key)
        if not path.is_file():
            raise SC2Error("job_not_found", "任务不存在")
        try:
            result = json.loads(path.read_text("utf-8"))
            if not isinstance(result, dict) or result.get("job_id") != key or not isinstance(result.get("state"), str):
                raise ValueError("invalid job record")
        except (OSError, ValueError) as exc:
            raise SC2Error("invalid_job_record", "任务记录损坏", job_id=key) from exc
        if result["state"] in _ACTIVE:
            if not self._owner_alive(result):
                result.update(state="interrupted", recovery="检查修改记录并调用 sc2_changes_recover")
            elif self._path(key, ".cancel").exists():
                result.update(state="cancelling", cancel_requested=True)
        return result

    def cancel(self, key):
        self._key(key)
        with self.lock:
            if key not in self.items:
                result = self.status(key)
                if result["state"] in _ACTIVE:
                    write_json(self._path(key, ".cancel"), {"requested_at": datetime.now(timezone.utc).isoformat()})
                    result.update(state="cancelling", cancel_requested=True)
                return result
            item, event = self.items[key]
            if item["state"] in _ACTIVE:
                event.set()
                item["cancel_requested"] = True
                future = self.futures.get(key)
                if future is not None and future.cancel():
                    item.update(state="cancelled", finished_at=datetime.now(timezone.utc).isoformat(),
                                error={"code": "cancelled", "message": "操作在开始前已取消"})
                else:
                    item["state"] = "cancelling"
                self._save(item)
            return copy.deepcopy(item)

    def shutdown(self, wait=True, cancel_pending=False):
        with self.lock:
            self.closed = True
            if cancel_pending:
                for key in tuple(self.items):
                    self.cancel(key)
        self.pool.shutdown(wait=wait)
