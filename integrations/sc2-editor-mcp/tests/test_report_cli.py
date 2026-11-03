"""Public JSON contracts for job ownership and seekable Unicode reports."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from sc2_mcp import reports
from sc2_mcp.dispatch import Dispatcher


def test_mcp_submission_returns_while_worker_is_active(tmp_path, monkeypatch):
    from sc2_mcp.server import create_server

    server = create_server(tmp_path)
    release = threading.Event()
    monkeypatch.setattr(server.sc2_service, "validate", lambda *args: release.wait(10))

    async def check():
        blocks = await asyncio.wait_for(server.call_tool("sc2_validate_static", {
            "project_id": "fixture", "background": True}), timeout=5)
        content = blocks[0] if isinstance(blocks, tuple) else blocks
        payload = json.loads(next(b.text for b in content if hasattr(b, "text")))
        assert payload["result"]["state"] in {"queued", "running"}
        assert payload["result"]["job_id"]

    try:
        asyncio.run(check())
    finally:
        release.set()
        server.sc2_dispatcher.close()


def cli(tmp, operation, raw, driver=None):
    entry = ["-m", "sc2_mcp.local_cli"] if driver is None else ["-c", driver]
    return [
        sys.executable,
        "-X",
        "utf8",
        *entry,
        "--state",
        str(tmp),
        "call",
        operation,
        "--arguments",
        raw,
    ]


def run(cmd, timeout=15):
    proc = subprocess.run(cmd, capture_output=True, encoding="utf8", timeout=timeout)
    assert not proc.stderr, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


@pytest.mark.parametrize("raw", ["[]", '"text"', "123", "null", "{", ""])
def test_cli_invalid_json(tmp_path, raw):
    code, body = run(cli(tmp_path, "sc2_validate_static", raw))
    assert code == 2 and body["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("background", [False, True])
def test_execution_error_has_nonzero_exit(tmp_path, background):
    code, body = run(
        cli(
            tmp_path,
            "sc2_validate_static",
            json.dumps(dict(project_id="absent", background=background)),
        )
    )
    assert (code, body["ok"], body["error"]["code"]) == (1, False, "project_not_open")
    if background:
        job = body["result"]
        assert job["state"] == "failed"
        code, status = run(
            cli(tmp_path, "sc2_job_status", json.dumps({"job_id": job["job_id"]}))
        )
        assert code == 0 and status["result"]["state"] == "failed"


# Substitute only the expensive worker body; subprocesses use the real CLI,
# dispatcher, on-disk jobs, cancellation markers and polling loop.
DRIVER = """
from sc2_mcp.local_cli import main
from sc2_mcp.service import Service
from sc2_mcp.errors import SC2Error
from sc2_mcp.jobs import Jobs
import time
def worker(self, project_id, cancel):
    if project_id == "crash":
        import os
        os._exit(17)
    if project_id == "oversize_fail":
        raise SC2Error("sample_code", "界"*70000)
    if project_id == "wait":
        for i in range(600):
            if cancel.is_set(): raise SC2Error("cancelled", "cancel observed")
            time.sleep(.05)
        raise RuntimeError("cancel not received")
    return {"text":"界"*70000}
Service.validate = worker
{setup}
raise SystemExit(main())
"""


@pytest.mark.parametrize(
    "project,expected,state",
    [
        ("oversize_ok", 0, "completed"),
        ("oversize_fail", 1, "failed"),
        ("lost", 1, "interrupted"),
    ],
)
def test_cli_terminal_states(tmp_path, project, expected, state):
    setup = ""
    if project == "lost":
        # Fault-inject the terminal interrupted observation into the waiting CLI.
        setup = "Jobs.status=lambda self,key: dict(job_id=key,state='interrupted',recovery='inspect then recover')"
    cmd = cli(
        tmp_path,
        "sc2_validate_static",
        json.dumps(dict(project_id=project, background=True)),
        DRIVER.replace("{setup}", setup),
    )
    code, body = run(cmd)
    assert (code, body["ok"]) == (expected, not expected)
    assert reports.size(body) <= reports.LIMIT
    result = body["result"]
    if project != "lost":
        report = json.loads(Path(result["report_file"]).read_bytes())
        assert report["state"] == state
    if expected:
        assert result["state"] == state
        if project == "oversize_fail":
            assert body["error"]["code"] == "sample_code"
            assert len(report["error"]["message"]) == 70000
        else:
            assert result["recovery"] == "inspect then recover"
    else:
        assert result["summary"]["state"] == state


def test_status_recovers_dead_owner_in_another_process(tmp_path):
    process = subprocess.run(cli(tmp_path, "sc2_validate_static",
                                 '{"project_id":"crash","background":true}', DRIVER.replace("{setup}", "")),
                             timeout=15)
    assert process.returncode == 17
    job, = (tmp_path / "jobs").glob("*.json")
    code, result = run(cli(tmp_path, "sc2_job_status", json.dumps({"job_id": job.stem})))
    assert code == 0
    assert result["result"]["state"] == "interrupted"
    assert result["result"]["recovery"]


def test_second_client_can_observe_and_cancel(tmp_path):
    process = subprocess.Popen(
        cli(
            tmp_path,
            "sc2_validate_static",
            '{"project_id":"wait","background":true}',
            DRIVER.replace("{setup}", ""),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf8",
    )
    try:
        until = time.monotonic() + 10
        while not (jobs := list((tmp_path / "jobs").glob("*.json"))):
            assert time.monotonic() < until
            time.sleep(0.05)
        args = json.dumps(dict(job_id=jobs[0].stem))
        code, body = run(cli(tmp_path, "sc2_job_status", args), timeout=8)
        assert code == 0 and body["result"]["state"] in ("queued", "running")
        code, body = run(cli(tmp_path, "sc2_job_cancel", args), timeout=8)
        assert code == 0 and body["result"]["cancel_requested"]
        stdout, stderr = process.communicate(timeout=10)
        assert not stderr and process.returncode == 1
        assert json.loads(stdout)["result"]["state"] == "cancelled"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.parametrize("legacy", [True, False])
def test_unicode_report_offsets_and_rebuild(tmp_path, legacy):
    report = tmp_path / "example.json"
    value = {"rows": [('中文😀"\\\n' * 10001), "ok"]}
    text = json.dumps(value, indent=2, ensure_ascii=False)
    if legacy:
        report.write_bytes(text.encode())
    else:
        assert reports.write_report(report, value) == len(text)

    def page(offset, limit=100000):
        result = reports.read_page(tmp_path, report.name, offset, limit)
        assert reports.size({"ok": True, "result": result}) <= reports.LIMIT
        assert result["text"] == text[offset : offset + len(result["text"])]
        return result

    for offset in [
        1,
        reports.STEP - 1,
        reports.STEP,
        len(text) - 1,
        len(text),
        len(text) + 100,
    ]:
        page(offset, 23)
    index = report.with_suffix(".ridx")
    index.write_text("invalid")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(page, [7, 2000, 9000]))
    assert all(r["next_offset"] for r in results)
    pos = 0
    parts = []
    while pos is not None:
        item = page(pos)
        pos = item["next_offset"]
        parts.append(item["text"])
    assert "".join(parts) == text


def test_large_warning_summary_and_error(tmp_path):
    dispatcher = Dispatcher(tmp_path)
    try:
        value = {
            "project_id": "sample",
            "state": "failed",
            "error": {"code": "oops", "message": "界" * 60000},
            "warnings": ["\\" * 9000] * 100,
            "limitations": ["example"] * 9000,
        }
        dispatcher.service.capabilities = lambda: value
        result = dispatcher.call("sc2_capabilities", {})
        assert reports.size(result) <= reports.LIMIT
        summary = result["result"]["summary"]
        assert summary["warnings_count"] == 100 and summary["limitations_count"] == 9000
        assert summary["error"]["code"] == "oops"
        path = Path(result["result"]["report_file"])
        assert result["result"]["characters"] == len(path.read_text("utf8"))
        error = dispatcher.error_payload(value["error"])
        assert reports.size(error) <= reports.LIMIT
        assert (
            json.loads((path.parent / error["report_name"]).read_bytes())
            == value["error"]
        )
    finally:
        dispatcher.close()
