"""Durable task records, isolated input copies, cancellation, and conflict-aware integration."""
from __future__ import annotations
import asyncio
import difflib
import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .runtime import ROOT, Harness
from .sc2_bridge import SC2BridgeWorker
from .policy import make_policy
from .windows import process_identity
from .agent_bridge import guard_source_changes, runtime_base
from .concurrency import limited_worker, submission_lock, integration_lock, task_claim
from .configuration import load_config


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def relative_file(name: str):
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized or any(
            part in ("", ".", "..") for part in normalized.split("/")):
        raise ValueError(f"Expected a relative file path: {name}")
    return normalized


def checked_path(root: Path, name: str):
    path = root / relative_file(name)
    current = path
    while current != root:
        if current.exists() and (current.is_symlink() or current.is_junction() or
                                (current.is_file() and current.stat().st_nlink > 1)):
            raise ValueError(f"Linked paths are not accepted: {name}")
        current = current.parent
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes workspace: {name}")
    return path


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1)
    request_id: str | None = Field(default=None, min_length=1, max_length=200)
    workspace: str
    input_files: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    acceptance: str = Field(min_length=1)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    provider: str | None = Field(default=None, min_length=1, max_length=200)
    prompts: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=1200, ge=1, le=86400)
    max_tool_calls: int = Field(default=200, ge=1, le=10000)
    profile: Literal["default", "sc2"] = "default"

    @field_validator("input_files", "allowed_files")
    @classmethod
    def validate_files(cls, files):
        return list(dict.fromkeys(relative_file(name) for name in files))

    @model_validator(mode="after")
    def validate_workspace(self):
        root = Path(self.workspace)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("workspace must be an existing absolute directory")
        self.workspace = str(root.resolve())
        if self.profile == "sc2" and ".sc2-mcp/request.json" not in self.allowed_files:
            self.allowed_files.append(".sc2-mcp/request.json")
        return self


class Manager:
    def __init__(self, state_root: Path | None = None, concurrency: int | None = None):
        self.state_root = state_root or runtime_base() / "deepseek/tasks"
        self.state_root.mkdir(parents=True, exist_ok=True)
        config = load_config()
        self.concurrency = concurrency or config["concurrency"]
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.jobs: dict[str, asyncio.Task] = {}
        self.cancellation_monitors: dict[str, asyncio.Task] = {}
        self.runtimes: dict[str, Harness] = {}
        self.owner = uuid.uuid4().hex
        self.owner_identity = process_identity(os.getpid())

    def directory(self, task_id):
        if len(task_id) != 32 or any(c not in "0123456789abcdef" for c in task_id):
            raise ValueError("Invalid task ID")
        return self.state_root / task_id

    def status(self, task_id):
        path = self.directory(task_id) / "status.json"
        if not path.exists():
            raise ValueError("Unknown task ID")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("state") in ("queued", "running") and record.get("owner_pid") and (
                process_identity(record["owner_pid"]) != record.get("owner_identity")):
            record.update(state="interrupted", worker_completed=False,
                          error="Owning supervisor exited; task was not automatically resubmitted")
            atomic_json(path, record)
        return record

    def save(self, task_id, **updates):
        path = self.directory(task_id) / "status.json"
        record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"task_id": task_id}
        record.update(updates, updated_at=time.time())
        atomic_json(path, record)
        return record

    @submission_lock
    async def submit(self, spec: TaskSpec):
        config = load_config()
        spec = spec.model_copy(update={'model': spec.model or config['model'],
                                      'provider': spec.provider or config['provider']})
        task_id = (uuid.uuid5(uuid.NAMESPACE_URL, "deepseek-supervisor:" + spec.request_id).hex
                   if spec.request_id else uuid.uuid4().hex)
        directory = self.directory(task_id)
        if directory.exists():
            previous = directory / "spec.json"
            if not previous.exists() or not (directory / "status.json").exists():
                raise ValueError("Submission exists but initialization was interrupted; inspect its directory before recovery")
            if json.loads(previous.read_text(encoding="utf-8")) != spec.model_dump():
                raise ValueError("request_id already belongs to a different task specification")
            return self.status(task_id)
        candidate = directory / "workspace"
        directory.mkdir(parents=True, exist_ok=False)
        candidate.mkdir()
        if spec.profile == "sc2":
            (candidate / ".sc2-mcp").mkdir()
        source = Path(spec.workspace)
        inputs = list(spec.input_files)
        # Explicitly allowed existing files are also copied; no unrelated directory traversal.
        inputs += [name for name in spec.allowed_files if (source / name).is_file()]
        if (source / "AGENTS.md").is_file() and "AGENTS.md" not in inputs:
            inputs.append("AGENTS.md")
        baseline = {}
        for name in dict.fromkeys(inputs + spec.allowed_files):
            origin = checked_path(source, name)
            baseline[name] = digest(origin)
            if name in inputs:
                if not origin.is_file():
                    raise ValueError(f"Missing input file: {name}")
                destination = checked_path(candidate, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, destination)
                baseline[name] = digest(destination)
                saved = directory / "original" / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
        atomic_json(directory / "spec.json", spec.model_dump())
        atomic_json(directory / "baseline.json", baseline)
        self.save(task_id, state="queued", owner=self.owner, worker_completed=False,
                  reviewed=False, created_at=time.time(), goal=spec.goal, model=spec.model, provider=spec.provider,
                  profile=spec.profile,
                  owner_pid=os.getpid(), owner_identity=self.owner_identity)
        self._schedule(task_id, self._execute(task_id, spec))
        return self.status(task_id)

    def _schedule(self, task_id, coroutine):
        self.jobs[task_id] = asyncio.create_task(coroutine)
        self.cancellation_monitors[task_id] = asyncio.create_task(self._watch_cancel(task_id))

    async def _watch_cancel(self, task_id):
        job = self.jobs[task_id]
        path = self.directory(task_id) / "cancel-request.json"
        while not job.done():
            if path.exists():
                os.replace(path, self.directory(task_id) / ("cancel-consumed-" + uuid.uuid4().hex + ".json"))
                job.cancel()
                await asyncio.gather(job, return_exceptions=True)
                if self.status(task_id)["state"] in ("queued", "running"):
                    self.save(task_id, state="cancelled", worker_completed=False)
                return
            await asyncio.sleep(0.1)

    @submission_lock
    @task_claim
    async def continue_task(self, task_id, prompt):
        if not prompt.strip():
            raise ValueError("A follow-up instruction is required")
        status = self.status(task_id)
        if status["state"] not in ("worker_completed", "failed"):
            raise ValueError("Only finished, unintegrated work can be explicitly continued")
        existing = self.jobs.get(task_id)
        if existing is not None and not existing.done():
            await asyncio.shield(existing)
            if self.status(task_id)["state"] not in ("worker_completed", "failed"):
                raise ValueError("Another continuation already claimed this task")
        elif status.get("runtime_pid") and process_identity(status["runtime_pid"]) == status.get("runtime_identity"):
            raise ValueError("Previous worker is still closing; query status before continuing")
        directory = self.directory(task_id)
        if not (directory / "home").is_dir():
            raise ValueError("No persisted Harness session to resume")
        spec = TaskSpec.model_validate_json((directory / "spec.json").read_text(encoding="utf-8"))
        atomic_json(directory / ("followup-" + uuid.uuid4().hex + ".json"), {"prompt": prompt})
        self.save(task_id, state="queued", owner=self.owner, owner_pid=os.getpid(),
                  owner_identity=self.owner_identity, worker_completed=False, reviewed=False, error=None)
        self._schedule(task_id, self._execute(task_id, spec, followup=prompt))
        return self.status(task_id)

    @limited_worker
    async def _execute(self, task_id, spec, followup=None):
        directory = self.directory(task_id)
        candidate = directory / "workspace"
        runtime = None
        bridge = SC2BridgeWorker(candidate, directory) if spec.profile == "sc2" else None
        try:
            async with self.semaphore:
                self.save(task_id, state="running")
                if bridge:
                    await bridge.start()
                patch = make_policy(directory, candidate, goal=spec.goal, allowed_files=spec.allowed_files,
                    constraints=spec.constraints, acceptance=spec.acceptance, enhanced=True,
                    max_tool_calls=spec.max_tool_calls, profile=spec.profile,
                    plugin=ROOT / "plugins/sc2-worker-policy.mjs" if spec.profile == "sc2" else None)
                runtime = Harness(candidate, directory, model=spec.model, provider=spec.provider,
                                  patches=[patch], timeout=spec.timeout_seconds)
                self.runtimes[task_id] = runtime
                async with asyncio.timeout(spec.timeout_seconds):
                    await runtime.start()
                    self.save(task_id, runtime_pid=runtime.process.pid,
                              runtime_identity=process_identity(runtime.process.pid))
                    prompt = json.dumps({"goal": spec.goal, "constraints": spec.constraints,
                         "allowed_files": spec.allowed_files, "acceptance": spec.acceptance}, ensure_ascii=False)
                    results = []
                    if followup is not None:
                        old_result = directory / "result.json"
                        if old_result.exists():
                            results = json.loads(old_result.read_text(encoding="utf-8")).get("turns", [])
                        await runtime.resume(task_id)
                        prompt = followup
                    start_index = len(results)
                    results.append(await runtime.run(prompt, task_id))
                    for next_prompt in ([] if followup is not None else spec.prompts):
                        if not results[-1]["runtime_ok"]:
                            break
                        results.append(await runtime.run(next_prompt, task_id))
                    atomic_json(directory / "result.json", {"turns": results, "final": results[-1]["final"],
                        "candidate_directory": str(candidate), "review_required": True})
                    good = all(result["runtime_ok"] for result in results[start_index:])
                    endings = results[-1].get('endings', [])
                    reason = endings[-1].get('reason', {}) if endings else {}
                    self.save(task_id, state="worker_completed" if good else "failed",
                              worker_completed=good, model=runtime.model, provider=runtime.provider,
                              error=None if good else reason.get('error', {'code': 'worker_incomplete', 'message': 'Worker did not complete normally'}))
        except asyncio.CancelledError:
            self.save(task_id, state="cancelled", worker_completed=False)
            raise
        except TimeoutError:
            self.save(task_id, state="timed_out", worker_completed=False,
                      error={'code': 'task_timeout', 'message': 'Worker exceeded the configured task timeout'})
        except Exception as error:
            self.save(task_id, state="failed", worker_completed=False,
                      error={"type": type(error).__name__, "message": str(error)[:2000]})
        finally:
            if bridge:
                await bridge.stop()
            if runtime:
                await asyncio.shield(runtime.close())
            self.runtimes.pop(task_id, None)

    async def cancel(self, task_id):
        job = self.jobs.get(task_id)
        if job and not job.done():
            job.cancel()
            await asyncio.gather(job, return_exceptions=True)
            if self.status(task_id)["state"] in ("queued", "running"):
                self.save(task_id, state="cancelled", worker_completed=False)
        elif self.status(task_id)["state"] in ("queued", "running"):
            if job is not None and job.cancelled():
                self.save(task_id, state="cancelled", worker_completed=False)
            else:
                atomic_json(self.directory(task_id) / "cancel-request.json", {"requested_at": time.time()})
                async with asyncio.timeout(15):
                    while True:
                        status = self.status(task_id)
                        alive = status.get("runtime_pid") and process_identity(status["runtime_pid"]) == status.get("runtime_identity")
                        if status["state"] not in ("queued", "running") and not alive:
                            break
                        await asyncio.sleep(0.1)
        return self.status(task_id)

    async def close(self):
        active = [(task_id, job) for task_id, job in self.jobs.items() if not job.done()]
        jobs = [job for _, job in active]
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        for task_id, _ in active:
            if self.status(task_id)["state"] in ("queued", "running"):
                self.save(task_id, state="cancelled", worker_completed=False)
        await asyncio.gather(*self.cancellation_monitors.values(), return_exceptions=True)

    def list_tasks(self, limit=20):
        paths = sorted(self.state_root.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [self.status(p.parent.name) for p in paths[:limit]]

    def result(self, task_id):
        directory = self.directory(task_id)
        result_path = directory / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
        baseline = json.loads((directory / "baseline.json").read_text(encoding="utf-8"))
        spec = TaskSpec.model_validate_json((directory / "spec.json").read_text(encoding="utf-8"))
        candidate = directory / "workspace"
        names = set(baseline) | {p.relative_to(candidate).as_posix() for p in candidate.rglob("*") if p.is_file()}
        changes = []
        for name in sorted(names):
            if spec.profile == "sc2" and (name == ".sc2-mcp" or name.startswith(".sc2-mcp/")):
                continue
            target = checked_path(candidate, name)
            current = digest(target)
            if current == baseline.get(name):
                continue
            origin = checked_path(Path(spec.workspace), name)
            entry = {"file": name, "allowed": name in spec.allowed_files, "baseline_hash": baseline.get(name),
                     "candidate_hash": current, "source_unchanged": digest(origin) == baseline.get(name)}
            try:
                saved = directory / "original" / name
                if baseline.get(name) is not None and not saved.exists():
                    if not entry["source_unchanged"]:
                        entry["diff_unavailable"] = "Legacy task has no saved original and source has changed"
                        changes.append(entry)
                        continue
                    saved = origin
                old = saved.read_text(encoding="utf-8").splitlines(True) if saved.exists() else []
                new = target.read_text(encoding="utf-8").splitlines(True) if target.exists() else []
                diff = "".join(difflib.unified_diff(old, new, fromfile=name, tofile=name))
                entry.update(diff=diff[:24000], diff_truncated=len(diff)>24000)
            except UnicodeError:
                entry["binary"] = True
            changes.append(entry)
        audit_path = directory / "audit.jsonl"
        attempts = []
        if audit_path.exists():
            for line in audit_path.read_text(encoding="utf-8").splitlines():
                try:
                    item = json.loads(line)
                except ValueError:
                    continue  # An active worker may still be appending the last line.
                if item.get("type") == "tool.attempt":
                    attempts.append(item)
        output = {"status": self.status(task_id), **result, "changes": changes,
                  "tool_calls": len(attempts), "blocked_calls": sum(bool(a.get("denied")) for a in attempts),
                  "denial_reasons": sorted({a["reason"] for a in attempts if a.get("denied")}),
                  "log_directory": str(directory), "review_required": True,
                  "worker_profile": spec.profile}
        if spec.profile == "sc2":
            bridge_log = directory / "sc2-bridge-events.jsonl"
            output["sc2_bridge"] = {
                "request_path": str(candidate / ".sc2-mcp/request.json"),
                "response_path": str(candidate / ".sc2-mcp/response.json"),
                "events_path": str(bridge_log),
                "events": [json.loads(line) for line in bridge_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            } if bridge_log.is_file() else {
                "request_path": str(candidate / ".sc2-mcp/request.json"),
                "response_path": str(candidate / ".sc2-mcp/response.json"),
                "events_path": str(bridge_log), "events": []}
        return output

    @integration_lock
    def integrate(self, task_id, review_note):
        if not review_note.strip():
            raise ValueError("A concrete review note is required")
        result = self.result(task_id)
        if result["status"]["state"] != "worker_completed":
            raise ValueError("Only completed candidates can be integrated")
        changes = result["changes"]
        if any(not c["allowed"] or not c["source_unchanged"] for c in changes):
            raise ValueError("Scope violation or source conflict; no files integrated")
        spec = TaskSpec.model_validate_json((self.directory(task_id) / "spec.json").read_text(encoding="utf-8"))
        guard_source_changes(spec.workspace, [change['file'] for change in changes])
        backup = self.directory(task_id) / "integration-backup"
        if backup.exists():
            backup = self.directory(task_id) / ("integration-backup-" + uuid.uuid4().hex)
        backup.mkdir(exist_ok=False)
        written = []
        try:
            for change in changes:
                name = change["file"]
                target = checked_path(Path(spec.workspace), name)
                source = checked_path(self.directory(task_id) / "workspace", name)
                if not source.is_file():
                    raise ValueError("Deletion candidates require explicit manual integration")
                if digest(target) != change["baseline_hash"]:
                    raise ValueError("Source changed during integration")
                old = backup / name
                if target.exists():
                    old.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, old)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".supervisor-" + uuid.uuid4().hex)
                shutil.copy2(source, temporary)
                if digest(target) != change["baseline_hash"] or digest(temporary) != change["candidate_hash"]:
                    temporary.unlink()
                    raise ValueError("Source or candidate changed while preparing integration")
                os.replace(temporary, target)
                written.append((target, old, change["candidate_hash"]))
        except BaseException:
            conflicts = []
            for target, old, candidate_hash in reversed(written):
                if digest(target) != candidate_hash:
                    conflicts.append(str(target))
                    continue
                if old.exists():
                    shutil.copy2(old, target)
                else:
                    target.unlink()
            if conflicts:
                self.save(task_id, rollback_conflicts=conflicts, backup_directory=str(backup))
            raise
        self.save(task_id, state="integrated", reviewed=True, review_note=review_note,
                  backup_directory=str(backup))
        return self.status(task_id)
