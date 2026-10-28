import asyncio
import json
import uuid
from .runtime import ROOT, Harness
from .policy import make_policy


async def main():
    run_dir = ROOT / "state" / ("policy-smoke-" + uuid.uuid4().hex[:8])
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "sample.txt").write_text("old\n", encoding="utf-8")
    patch = make_policy(run_dir, workspace, goal="Change old to new", allowed_files=["sample.txt"])
    runtime = Harness(workspace, run_dir, patches=[patch])
    try:
        print(await runtime.start(), flush=True)
        print(json.dumps(await runtime.run("Read sample.txt, replace old with new. Do not change other files. Report actual checks."), ensure_ascii=False), flush=True)
        print("CONTENT=" + (workspace / "sample.txt").read_text(), flush=True)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
