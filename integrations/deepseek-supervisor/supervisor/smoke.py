"""Real API smoke, using the same transport as production."""
import asyncio
import json
import uuid
from .runtime import ROOT, Harness


async def main():
    target = ROOT / "state" / ("smoke-" + uuid.uuid4().hex[:10])
    runtime = Harness(target / "workspace", target)
    try:
        print(json.dumps({"run_dir": str(target), "handshake": await runtime.start()}), flush=True)
        result = await runtime.run("这是后台连通测试。不要调用任何工具。记住校验词 ALPHA-739。只回复 READY。")
        print(json.dumps(result, ensure_ascii=False), flush=True)
        result = await runtime.run("不要调用工具。上一轮要求记住的校验词是什么？只回复校验词。")
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
