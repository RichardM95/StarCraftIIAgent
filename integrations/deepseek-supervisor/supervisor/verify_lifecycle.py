"""Kill a real bridge owner to verify Job Object cleanup and no replay after restart."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from .manager import Manager, TaskSpec
from .runtime import ROOT
from .windows import process_identity


async def child(directory):
    manager = Manager(directory / "tasks")
    source = directory / "source"
    source.mkdir()
    (source / "input.txt").write_text("owned lifecycle fixture\n", encoding="utf-8")
    task = await manager.submit(TaskSpec(goal="Read input.txt and explain its words.", workspace=str(source),
        input_files=["input.txt"], acceptance="Read only", prompts=["Explain in more detail."] * 20))
    async with asyncio.timeout(90):
        while True:
            status = manager.status(task["task_id"])
            if status.get("runtime_pid"):
                print(json.dumps(status), flush=True)
                break
            await asyncio.sleep(0.1)
    try:
        await manager.jobs[task["task_id"]]
    finally:
        await manager.close()


async def parent():
    directory = ROOT / "state" / ("crash-test-" + uuid.uuid4().hex[:8])
    directory.mkdir()
    process = await asyncio.create_subprocess_exec(sys.executable, "-X", "utf8", "-m",
        "supervisor.verify_lifecycle", "--child", str(directory), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        status = json.loads(await asyncio.wait_for(process.stdout.readline(), 90))
        process.kill()
        await process.wait()
        async with asyncio.timeout(15):
            while process_identity(status["runtime_pid"]) == status["runtime_identity"]:
                await asyncio.sleep(0.1)
        manager = Manager(directory / "tasks")
        after = manager.status(status["task_id"])
        assert after["state"] == "interrupted", after
        assert not manager.jobs
        report = {"task_id": status["task_id"], "owner_forcibly_killed": True,
                  "owned_worker_reaped": True, "state_after_restart": after["state"], "automatic_resubmissions": 0}
        (directory / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path)
    args = parser.parse_args()
    asyncio.run(child(args.child) if args.child else parent())
