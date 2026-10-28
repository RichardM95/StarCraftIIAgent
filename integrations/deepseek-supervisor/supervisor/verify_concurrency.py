"""Four real isolated workers, with one cancelled independently."""
import asyncio
import json
import subprocess
import sys
import uuid
from pathlib import Path
from .manager import Manager, TaskSpec
from .runtime import ROOT


async def main():
    directory = ROOT / "state" / ("concurrency-test-" + uuid.uuid4().hex[:8])
    source = directory / "source"
    source.mkdir(parents=True)
    (source / "value.txt").write_text("original\n", encoding="utf-8")
    manager = Manager(concurrency=4)
    try:
        records = []
        for index in range(4):
            records.append(await manager.submit(TaskSpec(goal=f"Change only value.txt to exactly marker-{index} followed by newline.",
                workspace=str(source), input_files=["value.txt"], allowed_files=["value.txt"],
                acceptance=f"exact bytes marker-{index} followed by newline",
                prompts=["Read value.txt and report its content without editing."] * (8 if index == 3 else 1))))
        async with asyncio.timeout(90):
            while sum(bool(manager.status(r["task_id"]).get("runtime_pid")) for r in records) < 4:
                await asyncio.sleep(0.1)
        cancellation = await asyncio.create_subprocess_exec(sys.executable, "-X", "utf8", "-m",
            "supervisor.cli", "cancel", records[3]["task_id"], stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        out, err = await asyncio.wait_for(cancellation.communicate(), 30)
        assert cancellation.returncode == 0, err.decode("utf-8", errors="replace")
        assert json.loads(out)["state"] == "cancelled", out
        await asyncio.gather(*(manager.jobs[r["task_id"]] for r in records[:3]))
        for index, record in enumerate(records[:3]):
            result = manager.result(record["task_id"])
            assert result["status"]["state"] == "worker_completed", result
            assert (Path(result["candidate_directory"]) / "value.txt").read_text() == f"marker-{index}\n"
        assert (source / "value.txt").read_text() == "original\n"
        report = {"concurrency": 4, "successful_isolated_workers": 3, "independently_cancelled": 1,
                  "separate_cli_process_cancellation": True,
                  "source_unchanged": True, "task_ids": [r["task_id"] for r in records]}
        (directory / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
