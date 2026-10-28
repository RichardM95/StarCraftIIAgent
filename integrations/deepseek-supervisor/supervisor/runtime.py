"""Owned stdio JSON-RPC sessions; never treat enqueue or output truncation as success."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from .windows import ProcessJob
from .runtime_root import ROOT
from .configuration import load_config, provider_definition



class HarnessError(RuntimeError):
    pass


class Harness:
    def __init__(self, workspace: Path, run_dir: Path, *, model: str | None = None, provider: str | None = None,
                 patches: list[Path] | None = None, timeout: float = 1200):
        self.config = load_config()
        self.workspace = workspace.resolve()
        self.run_dir = run_dir.resolve()
        self.model = model or self.config["model"]
        self.provider = provider or self.config['provider']
        self.reasoning_effort = self.config.get('reasoning_effort')
        self.patches = patches or []
        self.timeout = timeout
        self.process = None
        self.pending: dict[int, asyncio.Future] = {}
        self.notifications: asyncio.Queue = asyncio.Queue()
        self.serial = 0
        self.tasks: list[asyncio.Task] = []
        self.stderr_tail: list[str] = []
        self.lock = asyncio.Lock()
        self.closed = False
        self.job = None
        self.resumed_sessions = set()
        self.control_revision = 0

    async def start(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ELECTRON_RUN_AS_NODE"] = "1"
        # The SDK file worker needs only the caller's rights. Do not inherit the
        # interactive GUI application's per-user RUNASADMIN compatibility flag.
        env["__COMPAT_LAYER"] = "RunAsInvoker"
        env["DSH_HOME"] = str(self.run_dir / "home")
        env["DSH_PERMISSION_MODE"] = "workspace-write"
        env["DSH_MAX_TOKENS_AS_SUCCESS"] = "false"
        # Secrets are resolved by the Harness credential provider, never inherited by tools.
        for key in list(env):
            if any(word in key.upper() for word in ("API_KEY", "ACCESS_TOKEN", "AUTH_TOKEN")):
                env.pop(key)
        args = [self.config["harness_exe"], "--expose-internals", self.config["harness_cli"],
                "--profile", "sdk", "--patch", str(self.config.get('profile_path', ROOT / "profiles/base.patch.yml"))]
        definition = provider_definition(self.provider, self.model)
        if definition is not None:
            import yaml
            provider_patch = self.run_dir / 'provider.patch.yml'
            provider_patch.write_text(yaml.safe_dump([{'id': 'llm-pi-ai', 'disabled': False,
                'config': {'providers': {self.provider: definition}}}], allow_unicode=True, sort_keys=False), encoding='utf-8')
            args += ['--patch', str(provider_patch)]
            models = definition.get('models', [])
            selected = models.get(self.model, {}) if isinstance(models, dict) else next(
                (item for item in models if item['id'] == self.model), {})
            # Custom routes must advertise reasoning before receiving an effort;
            # the official route's default must not leak into other protocols.
            if not selected.get('reasoning'):
                self.reasoning_effort = None
        for patch in self.patches:
            args += ["--patch", str(patch.resolve())]
        spawning = asyncio.create_task(asyncio.create_subprocess_exec(
            *args, cwd=self.workspace, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            limit=32 * 1024 * 1024))
        try:
            self.process = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            self.process = await spawning
            if self.process.returncode is None:
                try:
                    self.job = ProcessJob(self.process.pid)
                except Exception:
                    # close() also uses taskkill /T if ownership could not be attached.
                    pass
            await asyncio.shield(self.close())
            raise
        self.tasks = [asyncio.create_task(self._stdout()), asyncio.create_task(self._stderr())]
        try:
            self.job = ProcessJob(self.process.pid)
            options = {
                "cwd": str(self.workspace), "provider": self.provider,
                "model": self.model, "maxTokens": self.config["max_tokens"]}
            if self.reasoning_effort:
                options['reasoningEffort'] = self.reasoning_effort
            result = await self.request("initialize", options, timeout=90)
            if result.get("serverInfo", {}).get("name") != "deepseek-harness-sdk-runtime":
                raise HarnessError("Unexpected SDK server identity")
            return result
        except BaseException:
            await self.close()
            raise

    def _log(self, name: str, data: Any):
        with (self.run_dir / name).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(data, ensure_ascii=False) + "\n")

    async def _stdout(self):
        try:
            while line := await self.process.stdout.readline():
                try:
                    item = json.loads(line)
                except (ValueError, UnicodeError):
                    self._log("protocol-errors.jsonl", {"error": "Non-JSON stdout", "bytes": len(line)})
                    continue
                self._log("events.jsonl", item)
                if "id" in item and "method" not in item:
                    future = self.pending.pop(item["id"], None)
                    if future and not future.done():
                        if "error" in item:
                            future.set_exception(HarnessError(str(item["error"])))
                        else:
                            future.set_result(item.get("result", {}))
                elif "method" in item:
                    await self.notifications.put(item)
        finally:
            error = HarnessError("Harness transport closed; " + "\n".join(self.stderr_tail[-8:]))
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(error)
            self.pending.clear()
            await self.notifications.put({"method": "transport.closed"})

    async def _stderr(self):
        while line := await self.process.stderr.readline():
            text = line.decode("utf-8", errors="replace").rstrip()
            self.stderr_tail.append(text)
            self.stderr_tail = self.stderr_tail[-30:]
            self._log("stderr.jsonl", {"text": text})

    async def request(self, method: str, params=None, timeout: float = 30):
        if not self.process or self.process.returncode is not None:
            raise HarnessError("Harness is not running")
        self.serial += 1
        request_id = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(request_id, None)

    async def run(self, prompt: str, session_id: str = "task"):
        async with self.lock:
            while not self.notifications.empty():
                self.notifications.get_nowait()
            start = time.monotonic()
            if session_id in self.resumed_sessions:
                receipt = await self.control("prompt", session_id, prompt=prompt)
            else:
                receipt = await self.request("session/prompt", {
                    "sessionId": session_id, "contentBlocks": [{"type": "text", "text": prompt}]})
            events = []
            admitted = False
            async with asyncio.timeout(self.timeout):
                while True:
                    item = await self.notifications.get()
                    if item["method"] == "transport.closed":
                        raise HarnessError("Transport closed during task")
                    params = item.get("params", {})
                    if params.get("sessionId") != session_id:
                        continue
                    if item["method"] == "session.event":
                        event = params["event"]
                        events.append(event)
                        if event.get("type") == "agent/inbox/spliced" and any(
                            m.get("id") == receipt["messageId"] for m in event.get("data", {}).get("inserted", [])):
                            admitted = True
                    if admitted and item["method"] == "session.status" and params.get("status") == "idle":
                        break
            messages = [e for e in events if e.get("type") == "assistant/message"]
            final = ""
            if messages:
                final = "\n".join(b.get("text", "") for b in messages[-1]["data"]["message"]["content"] if b.get("type") == "text")
            endings = [e.get("data", {}) for e in events if e.get("type") == "turn/end"]
            result = {"session_id": session_id, "provider": self.provider, "model": self.model, "final": final,
                      "elapsed_seconds": round(time.monotonic()-start, 3),
                      "endings": endings, "event_count": len(events)}
            result["runtime_ok"] = bool(final and endings and endings[-1].get("reason", {}).get("kind") == "completed")
            result["usage"] = {key: sum(e.get("data", {}).get("usage", {}).get(key, 0) for e in messages)
                               for key in ("inputTokens", "outputTokens", "cacheReadTokens", "totalTokens")}
            result["event_types"] = sorted(set(e.get("type", "") for e in events))
            self._log("turns.jsonl", result)
            return result

    async def control(self, operation, session_id="task", **kwargs):
        existing = self.run_dir / "control.json"
        previous = json.loads(existing.read_text(encoding="utf-8")).get("revision", 0) if existing.exists() else 0
        revision = max(time.time_ns() // 1_000_000, previous + 1, self.control_revision + 1)
        self.control_revision = revision
        path = self.run_dir / "control.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"revision": revision, "operation": operation, "session_id": session_id, **kwargs}), encoding="utf-8")
        os.replace(temp, path)
        async with asyncio.timeout(self.timeout):
            while True:
                result_path = self.run_dir / "control-result.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    if result["revision"] == revision:
                        if not result["ok"]:
                            raise HarnessError(result.get("error", "Control request failed"))
                        return result
                await asyncio.sleep(0.1)

    async def compact(self, session_id="task"):
        return await self.control("compact", session_id)

    async def resume(self, session_id="task"):
        options = {
            "provider": self.provider, "model": self.model,
            "maxTokens": self.config["max_tokens"]}
        if self.reasoning_effort:
            options['reasoningEffort'] = self.reasoning_effort
        result = await self.control("resume", session_id, agent_options=options)
        self.resumed_sessions.add(session_id)
        return result

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process and self.process.returncode is None:
            try:
                await self.request("shutdown", timeout=3)
                await asyncio.wait_for(self.process.wait(), 3)
            except (Exception, asyncio.CancelledError):
                if self.process.returncode is None:
                    if os.name == "nt":
                        killer = await asyncio.create_subprocess_exec("taskkill", "/PID", str(self.process.pid), "/T", "/F",
                            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        await killer.wait()
                    else:
                        self.process.kill()
                    await self.process.wait()
        if self.job:
            self.job.close()
        if self.process and self.process.stdin:
            self.process.stdin.close()
            try:
                await self.process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass
        for task in self.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
