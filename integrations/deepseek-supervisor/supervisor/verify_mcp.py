"""Use an actual official MCP client to verify all six tools and a real worker."""
import asyncio
import json
import sys
import uuid
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from .runtime import ROOT
from .windows import process_identity


def value(result):
    if result.isError:
        raise RuntimeError(str(result.content))
    return json.loads(next(c.text for c in result.content if c.type == "text"))


async def main():
    test_root = ROOT / "state" / ("mcp-test-" + uuid.uuid4().hex[:8])
    test_root.mkdir(parents=True)
    (test_root / "sample.txt").write_text("old\n", encoding="utf-8")
    parameters = StdioServerParameters(command=sys.executable, args=["-X", "utf8", "-m", "supervisor.server"], cwd=str(ROOT))
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"submit_task", "task_status", "task_result", "cancel_task", "list_tasks", "capabilities"}, names
            task = {"goal": "Change old to new in sample.txt only.", "workspace": str(test_root),
                    "request_id": uuid.uuid4().hex,
                    "input_files": ["sample.txt"], "allowed_files": ["sample.txt"],
                    "acceptance": "sample.txt is new followed by newline; preserve other files."}
            record = value(await session.call_tool("submit_task", {"task": task}))
            completed_id = record["task_id"]
            duplicate = value(await session.call_tool("submit_task", {"task": task}))
            assert duplicate["task_id"] == completed_id
            # Independent second worker is cancelled while the first is allowed to finish.
            second = value(await session.call_tool("submit_task", {"task": {**task,
                "request_id": uuid.uuid4().hex,
                "goal": "Read sample.txt and provide a detailed explanation of every character. Do not edit.",
                "allowed_files": [], "prompts": ["Explain again with different examples."] * 10}}))
            async with asyncio.timeout(90):
                while True:
                    second_status = value(await session.call_tool("task_status", {"task_id": second["task_id"]}))
                    log = ROOT / "state/tasks" / second["task_id"] / "events.jsonl"
                    if log.exists() and '"request/header"' in log.read_text(encoding="utf-8"):
                        break
                    await asyncio.sleep(0.2)
            assert second_status["state"] == "running", second_status
            cancelled = value(await session.call_tool("cancel_task", {"task_id": second["task_id"]}))
            assert cancelled["state"] == "cancelled", cancelled
            assert process_identity(second_status["runtime_pid"]) != second_status["runtime_identity"]
            async with asyncio.timeout(120):
                while True:
                    status = value(await session.call_tool("task_status", {"task_id": completed_id}))
                    if status["state"] not in ("queued", "running"):
                        break
                    await asyncio.sleep(0.3)
            result = value(await session.call_tool("task_result", {"task_id": completed_id}))
            assert status["state"] == "worker_completed", result
            candidate = Path(result["candidate_directory"]) / "sample.txt"
            assert candidate.read_text() == "new\n"
            assert (test_root / "sample.txt").read_text() == "old\n"
            assert len(result["changes"]) == 1 and result["changes"][0]["source_unchanged"]
            value(await session.call_tool("submit_task", {"continue_task_id": completed_id,
                "followup": "Read sample.txt and report its current contents. Do not modify any file."}))
            async with asyncio.timeout(120):
                while True:
                    status = value(await session.call_tool("task_status", {"task_id": completed_id}))
                    if status["state"] not in ("queued", "running"):
                        break
                    await asyncio.sleep(0.2)
            assert status["state"] == "worker_completed", status
            result = value(await session.call_tool("task_result", {"task_id": completed_id}))
            assert len(result["turns"]) == 2 and "new" in result["final"]
            await session.call_tool("list_tasks", {})
            await session.call_tool("capabilities", {})
            disconnected = value(await session.call_tool("submit_task", {"task": {**task,
                "request_id": uuid.uuid4().hex,
                "goal": "Read sample.txt and explain it.", "allowed_files": [],
                "prompts": ["Give another detailed explanation."] * 20}}))
            async with asyncio.timeout(90):
                while True:
                    dis_status = value(await session.call_tool("task_status", {"task_id": disconnected["task_id"]}))
                    if dis_status.get("runtime_pid"):
                        break
                    await asyncio.sleep(0.2)
            report = {"tools": sorted(names), "task_id": completed_id,
                      "cancelled_task_id": second["task_id"], "real_api": True,
                      "candidate_correct": True, "source_unchanged": True,
                      "independent_running_cancellation": True,
                      "explicit_followup_resumed_same_session": True,
                      "idempotent_submission": True,
                      "disconnected_task_id": disconnected["task_id"]}
    async with asyncio.timeout(15):
        while process_identity(dis_status["runtime_pid"]) == dis_status["runtime_identity"]:
            await asyncio.sleep(0.2)
    from .manager import Manager
    manager = Manager()
    state = manager.status(disconnected["task_id"])
    assert state["state"] in ("cancelled", "interrupted"), state
    assert not manager.jobs
    report.update(disconnect_reaped_worker=True, no_automatic_resubmission=True)
    (test_root / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
