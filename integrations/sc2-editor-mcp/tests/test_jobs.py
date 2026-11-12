import json
from pathlib import Path
import threading
import subprocess
import sys

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.jobs import Jobs
from sc2_mcp.storage import write_json


@pytest.fixture
def jobs(tmp_path):
    manager = Jobs(tmp_path / "state")
    yield manager
    manager.shutdown(wait=True, cancel_pending=True)


def test_job_completion_and_result_are_persisted(jobs):
    result = jobs.submit("calculate", lambda cancel: {"value": 42})
    jobs.futures[result["job_id"]].result(timeout=5)
    status = jobs.status(result["job_id"])
    assert status["state"] == "completed"
    assert status["progress"] == 100
    assert status["result"] == {"value": 42}
    status["result"]["value"] = 0
    assert jobs.status(result["job_id"])["result"]["value"] == 42
    disk = json.loads((jobs.state / "jobs" / (result["job_id"] + ".json")).read_text("utf-8"))
    assert disk["state"] == "completed"


def test_running_cancel_is_cooperative_and_terminal(jobs):
    ready, release = threading.Event(), threading.Event()
    def work(cancel):
        cancel.report_progress(25, "reading")
        ready.set()
        release.wait(5)
        if cancel.is_set():
            raise SC2Error("cancelled", "requested")
        return {}
    result = jobs.submit("cancel-me", work)
    assert ready.wait(5)
    assert jobs.status(result["job_id"])["progress"] == 25
    assert jobs.cancel(result["job_id"])["state"] == "cancelling"
    release.set()
    jobs.futures[result["job_id"]].result(timeout=5)
    assert jobs.status(result["job_id"])["state"] == "cancelled"
    assert jobs.status(result["job_id"])["cancel_requested"] is True


def test_cancel_after_success_does_not_claim_revert(jobs):
    result = jobs.submit("quick", lambda cancel: {"state": "committed"})
    jobs.futures[result["job_id"]].result(timeout=5)
    assert jobs.cancel(result["job_id"])["state"] == "completed"


def test_late_cancel_while_work_returns_does_not_misreport_committed_result(jobs):
    committed, release = threading.Event(), threading.Event()
    def work(cancel):
        committed.set()
        release.wait(5)
        return {"state": "committed"}
    result = jobs.submit("late", work)
    assert committed.wait(5)
    jobs.cancel(result["job_id"])
    release.set()
    jobs.futures[result["job_id"]].result(timeout=5)
    status = jobs.status(result["job_id"])
    assert status["state"] == "completed"
    assert status["result"]["state"] == "committed"
    assert status["cancel_requested"] is True


def test_cancel_queued_job_never_calls_function(jobs):
    ready = [threading.Event() for _ in range(3)]
    release = threading.Event()
    active = []
    for event in ready:
        def hold(cancel, event=event):
            event.set()
            release.wait(5)
            return {}
        active.append(jobs.submit("hold", hold))
    assert all(event.wait(5) for event in ready)
    called = threading.Event()
    queued = jobs.submit("queued", lambda cancel: called.set())
    assert jobs.cancel(queued["job_id"])["state"] == "cancelled"
    release.set()
    for result in active:
        jobs.futures[result["job_id"]].result(timeout=5)
    assert not called.is_set()


def test_second_manager_observes_live_owner_and_cancels_via_marker(jobs):
    ready, release = threading.Event(), threading.Event()
    def work(cancel):
        ready.set()
        release.wait(5)
        if cancel.is_set():
            raise SC2Error("cancelled", "remote cancellation")
        return {}
    result = jobs.submit("other-client", work)
    assert ready.wait(5)
    observer = Jobs(jobs.state)
    try:
        assert observer.status(result["job_id"])["state"] == "running"
        assert observer.cancel(result["job_id"])["state"] == "cancelling"
        release.set()
        jobs.futures[result["job_id"]].result(timeout=5)
        assert observer.status(result["job_id"])["state"] == "cancelled"
    finally:
        release.set()
        observer.shutdown()


def test_stale_owner_records_are_interrupted(jobs):
    key = "a" * 32
    write_json(jobs.state / "jobs" / (key + ".json"), {"job_id": key, "state": "running", "owner": {"pid": -1, "started": 1}})
    assert jobs.status(key)["state"] == "interrupted"
    assert jobs.cancel(key)["state"] == "interrupted"
    assert not (jobs.state / "jobs" / (key + ".cancel")).exists()


def test_crashed_worker_process_is_reported_interrupted(jobs):
    code = """from pathlib import Path
import os,sys,threading
from sc2_mcp.jobs import Jobs
gate=threading.Event()
manager=Jobs(Path(sys.argv[1]))
def crash(cancel):
 gate.wait()
 os._exit(25)
result=manager.submit('crash',crash)
print(result['job_id'],flush=True)
gate.set()
manager.futures[result['job_id']].result()
"""
    process = subprocess.run([sys.executable, "-c", code, str(jobs.state)], capture_output=True, text=True, timeout=15)
    assert process.returncode == 25, process.stderr
    key = process.stdout.strip()
    assert jobs.status(key)["state"] == "interrupted"


def test_exception_and_unserializable_result_fail_jobs(jobs):
    for function in (lambda cancel: 1 / 0, lambda cancel: {"data": b"bytes"}):
        result = jobs.submit("fail", function)
        jobs.futures[result["job_id"]].result(timeout=5)
        assert jobs.status(result["job_id"])["state"] == "failed"


@pytest.mark.parametrize("key", ["../x", [], None, "A" * 32])
def test_invalid_ids_are_structured_errors(jobs, key):
    with pytest.raises(SC2Error) as error:
        jobs.status(key)
    assert error.value.code == "invalid_job_id"
    with pytest.raises(SC2Error):
        jobs.cancel(key)


def test_progress_must_be_valid_and_never_go_backward(jobs):
    ready, release = threading.Event(), threading.Event()
    def work(cancel):
        ready.set()
        release.wait(5)
        return {}
    result = jobs.submit("progress", work)
    assert ready.wait(5)
    key = result["job_id"]
    try:
        assert jobs.update_progress(key, 70)["progress"] == 70
        assert jobs.update_progress(key, 50)["progress"] == 70
        for invalid in (-1, 100, float("nan"), True):
            with pytest.raises(SC2Error):
                jobs.update_progress(key, invalid)
    finally:
        release.set()
    jobs.futures[key].result(timeout=5)


def test_shutdown_rejects_new_work(jobs):
    jobs.shutdown()
    with pytest.raises(SC2Error) as error:
        jobs.submit("too late", lambda cancel: {})
    assert error.value.code == "jobs_closed"


def _saved_item(jobs, key):
    return {"job_id": key, "operation": "save", "state": "queued", "progress": 0,
            "created_at": "2026-01-01T00:00:00+00:00", "owner": dict(jobs.owner)}


def test_save_retries_transient_windows_read_lock(jobs, monkeypatch):
    key = "a" * 32
    locked = PermissionError(13, "locked", str(jobs._path(key)), 32)

    real_write = write_json
    calls = []

    def transient(path, item):
        calls.append(path)
        if len(calls) < 3:
            raise locked
        return real_write(path, item)

    monkeypatch.setattr("sc2_mcp.jobs.write_json", transient)
    jobs._save(_saved_item(jobs, key))
    assert len(calls) == 3
    assert json.loads(jobs._path(key).read_text("utf-8"))["job_id"] == key


def test_save_fails_bounded_after_persistent_read_lock(jobs, monkeypatch):
    key = "b" * 32
    item = _saved_item(jobs, key)
    write_json(jobs._path(key), {**item, "state": "old"})
    before = jobs._path(key).read_bytes()
    locked = PermissionError(13, "locked", str(jobs._path(key)), 32)
    calls = []

    def always_locked(path, value):
        calls.append(path)
        raise locked

    monkeypatch.setattr("sc2_mcp.jobs.write_json", always_locked)
    with pytest.raises(PermissionError) as error:
        jobs._save(item)
    assert error.value is locked
    assert getattr(error.value, "winerror") == 32
    assert len(calls) == 5
    assert jobs._path(key).read_bytes() == before


def _denied(path):
    return PermissionError(13, "denied", str(path), 3)


def _denied_without_winerror(path):
    return PermissionError(13, "denied", str(path), None)


def _invalid_argument(path):
    return OSError(22, "invalid argument", str(path), 87)


def _retriable_winerror(path):
    return OSError(13, "locked", str(path), 32)


@pytest.mark.parametrize("factory, expected", [
    (_denied, PermissionError),
    (_denied_without_winerror, PermissionError),
    (_invalid_argument, OSError),
    # OSError(..., winerror=32) is constructed as PermissionError on Windows, and
    # the manager treats winerror 32 as transient, so this is NOT unrelated.
    (_retriable_winerror, PermissionError),
])
def test_save_propagates_unrelated_errors_immediately(jobs, monkeypatch, factory, expected):
    key = "c" * 32
    original = factory(jobs._path(key))
    assert type(original) is expected
    if expected is PermissionError:
        assert getattr(original, "winerror", None) not in (5, 32, 33) or factory is _retriable_winerror
    calls = []

    def failing(path, value):
        calls.append(path)
        raise original

    monkeypatch.setattr("sc2_mcp.jobs.write_json", failing)
    with pytest.raises(expected) as error:
        jobs._save(_saved_item(jobs, key))
    assert error.value is original
    assert len(calls) == (5 if factory is _retriable_winerror else 1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows share-mode semantics only")
def test_save_survives_native_reader_that_blocks_delete(jobs):
    import ctypes
    import time

    key = "d" * 32
    item = _saved_item(jobs, key)
    write_json(jobs._path(key), {**item, "state": "old"})
    path = jobs._path(key)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateFileW(str(path), 0x80000000, 1 | 2, None, 3, 0x80, None)
    assert handle and handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()

    def release():
        try:
            time.sleep(0.08)
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))

    releaser = threading.Thread(target=release)
    releaser.start()
    try:
        jobs._save(item)
    finally:
        releaser.join(5)
    assert json.loads(path.read_text("utf-8"))["state"] == "queued"
