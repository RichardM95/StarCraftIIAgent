"""Host side file bridge between a DeepSeek worker and SC2 Editor MCP."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from .runtime import ROOT
from .agent_bridge import runtime_command


def _json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class SC2BridgeWorker:
    """Poll one task-local request file and execute it with the SC2 MCP venv.

    The worker can only invoke the fixed module entry point.  The request
    itself is validated again by ``sc2_mcp.worker_bridge``; this layer owns
    process identity, timeout, idempotence and the task-local audit record.
    """

    def __init__(self, workspace: Path, run_dir: Path, *, interval: float = 0.15, timeout: float = 120.0):
        self.workspace = Path(workspace).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.bridge_dir = self.workspace / ".sc2-mcp"
        self.request_path = self.bridge_dir / "request.json"
        self.response_path = self.bridge_dir / "response.json"
        self.status_path = self.bridge_dir / "bridge-status.json"
        self.interval = interval
        self.timeout = timeout
        self.task: asyncio.Task | None = None
        self.closed = False
        self.last_digest: str | None = None
        self.process_count = 0

    @staticmethod
    def python_path() -> Path | None:
        configured = os.environ.get("SC2_EDITOR_MCP_PYTHON")
        candidates = [Path(configured)] if configured else []
        candidates.append((ROOT.parent / "sc2-editor-mcp" / ".venv" / "Scripts" / "python.exe").resolve())
        for candidate in candidates:
            if candidate and candidate.is_file():
                return candidate.resolve()
        return None

    async def start(self) -> None:
        if self.task is not None:
            return
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        if self.request_path.is_file() and self.response_path.is_file():
            try:
                response = json.loads(self.response_path.read_text(encoding="utf-8"))
                request_hash = hashlib.sha256(self.request_path.read_bytes()).hexdigest()
                if response.get("request_sha256") == request_hash:
                    self.last_digest = request_hash
            except (OSError, ValueError, KeyError):
                pass
        _json_write(self.status_path, {"state": "ready", "protocol": "sc2-worker-bridge/1"})
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.closed = True
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        _json_write(self.status_path, {"state": "stopped", "processed": self.process_count,
                                       "protocol": "sc2-worker-bridge/1"})

    async def _run(self) -> None:
        while not self.closed:
            try:
                if self.request_path.is_file():
                    current = hashlib.sha256(self.request_path.read_bytes()).hexdigest()
                    if current != self.last_digest:
                        self.last_digest = current
                        response = await self._execute(current)
                        _json_write(self.response_path, response)
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                response = {"protocol": "sc2-worker-bridge/1", "ok": False,
                            "error": {"code": "bridge_host_error", "message": str(exc)}}
                _json_write(self.response_path, response)
                await asyncio.sleep(self.interval)

    async def _execute(self, request_hash: str) -> dict:
        self.process_count += 1
        started = time.time()
        python = self.python_path()
        if python is None:
            result = {"protocol": "sc2-worker-bridge/1", "ok": False,
                      "error": {"code": "bridge_runtime_missing",
                                "message": "SC2_EDITOR_MCP_PYTHON 未配置且默认 SC2 MCP 虚拟环境不存在"}}
            result["request_sha256"] = request_hash
            self._audit(request_hash, result, started)
            return result
        args = [str(python), "-X", "utf8", "-m", "sc2_mcp.worker_bridge_cli",
                "--root", str(self.workspace), "--request", str(self.request_path)]
        local_environment = ROOT.parent / 'sc2-editor-mcp/.venv/Scripts/python.exe'
        if python.resolve() == local_environment.resolve():
            args = runtime_command('sc2-editor-mcp', 'sc2_mcp.worker_bridge_cli',
                                   ['--root', str(self.workspace), '--request', str(self.request_path)])
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        process = None
        spawning = None
        try:
            spawning = asyncio.create_task(asyncio.create_subprocess_exec(
                *args, cwd=str(python.parent.parent.parent), env=environment,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ))
            process = await asyncio.shield(spawning)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            if process.returncode != 0:
                result = {"protocol": "sc2-worker-bridge/1", "ok": False,
                          "error": {"code": "bridge_process_failed", "message": stderr.decode("utf-8", errors="replace")[-4000:],
                                    "exit_code": process.returncode}}
            else:
                try:
                    result = json.loads(stdout.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    result = {"protocol": "sc2-worker-bridge/1", "ok": False,
                              "error": {"code": "bridge_invalid_response", "message": str(exc),
                                        "stdout_tail": stdout.decode("utf-8", errors="replace")[-2000:]}}
        except asyncio.CancelledError:
            if process is None and spawning is not None:
                process = await spawning
            if process is not None:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await asyncio.shield(process.wait())
            raise
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            result = {"protocol": "sc2-worker-bridge/1", "ok": False,
                      "error": {"code": "bridge_timeout", "message": "SC2 MCP 请求超时"}}
        except OSError as exc:
            result = {"protocol": "sc2-worker-bridge/1", "ok": False,
                      "error": {"code": "bridge_spawn_failed", "message": str(exc)}}
        result["request_sha256"] = request_hash
        self._audit(request_hash, result, started)
        return result

    def _audit(self, request_hash: str, result: dict, started: float) -> None:
        path = self.run_dir / "sc2-bridge-events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"request_sha256": request_hash, "ok": result.get("ok"),
                                     "code": (result.get("error") or {}).get("code"),
                                     "elapsed_seconds": round(time.time() - started, 3)}, ensure_ascii=False) + "\n")


__all__ = ["SC2BridgeWorker"]
