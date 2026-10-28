import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from supervisor.manager import Manager, TaskSpec, relative_file, checked_path, atomic_json
from supervisor.windows import ProcessJob, process_identity


class Paths(unittest.TestCase):
    def test_escaping_and_windows_aliases_rejected(self):
        for name in ("../outside", "C:/other", "/absolute", "file.txt:secret", "a/../b", "\\\\host\\share"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative_file(name)

    def test_hardlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_text("existing")
            os.link(root / "a", root / "b")
            with self.assertRaises(ValueError):
                checked_path(root, "b")


class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "file.txt").write_bytes(b"original\r\n")
        self.manager = Manager(self.root / "state")
        async def no_worker(task_id, spec):
            self.manager.save(task_id, state="worker_completed", worker_completed=True)
        self.manager._execute = no_worker
        self.record = await self.manager.submit(TaskSpec(goal="Edit", workspace=str(self.source),
            input_files=["file.txt"], allowed_files=["file.txt"], acceptance="exact expected bytes"))
        self.task_id = self.record["task_id"]
        await self.manager.jobs[self.task_id]
        (self.manager.directory(self.task_id) / "workspace/file.txt").write_bytes(b"candidate\r\n")

    async def asyncTearDown(self):
        await self.manager.close()
        self.temp.cleanup()

    async def test_conflict_refuses_without_overwriting_user_change(self):
        (self.source / "file.txt").write_bytes(b"new user change\r\n")
        diff = self.manager.result(self.task_id)["changes"][0]["diff"]
        self.assertIn("-original", diff)
        self.assertNotIn("new user change", diff)
        with self.assertRaises(ValueError):
            self.manager.integrate(self.task_id, "Reviewed candidate")
        self.assertEqual((self.source / "file.txt").read_bytes(), b"new user change\r\n")

    async def test_integration_preserves_bytes_and_backup(self):
        result = self.manager.integrate(self.task_id, "Independent byte check passed")
        self.assertEqual((self.source / "file.txt").read_bytes(), b"candidate\r\n")
        self.assertEqual((Path(result["backup_directory"]) / "file.txt").read_bytes(), b"original\r\n")

    async def test_extra_file_blocks_integration(self):
        (self.manager.directory(self.task_id) / "workspace/unapproved.txt").write_text("extra")
        with self.assertRaises(ValueError):
            self.manager.integrate(self.task_id, "Attempted review")
        self.assertEqual((self.source / "file.txt").read_bytes(), b"original\r\n")

    async def test_previous_backup_does_not_prevent_reviewed_retry(self):
        previous = self.manager.directory(self.task_id) / "integration-backup"
        previous.mkdir()
        (previous / "old-attempt.txt").write_text("keep this recovery evidence")
        result = self.manager.integrate(self.task_id, "Reviewed retry after earlier failure")
        self.assertEqual(result["state"], "integrated")
        self.assertTrue((previous / "old-attempt.txt").exists())


@unittest.skipUnless(os.name == "nt", "Windows Job Object")
class Lifecycle(unittest.TestCase):
    def test_exited_process_with_retained_handle_is_not_alive(self):
        process = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=subprocess.CREATE_NO_WINDOW)
        process.wait(timeout=5)
        self.assertIsNone(process_identity(process.pid))

    def test_job_close_reaps_process(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            job = ProcessJob(process.pid)
            job.close()
            process.wait(timeout=5)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


class Cancellation(unittest.IsolatedAsyncioTestCase):
    async def test_other_connection_cancels_only_requested_task(self):
        with tempfile.TemporaryDirectory() as temp:
            owner = Manager(Path(temp) / "tasks")
            observer = Manager(Path(temp) / "tasks")
            async def pending(task_id, spec):
                await asyncio.sleep(60)
            owner._execute = pending
            first = await owner.submit(TaskSpec(goal="first", workspace=temp, acceptance="cancel"))
            second = await owner.submit(TaskSpec(goal="second", workspace=temp, acceptance="stay alive"))
            await asyncio.sleep(0)
            cancelled = await observer.cancel(first["task_id"])
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertFalse(owner.jobs[second["task_id"]].done())
            await owner.close()
            await observer.close()

    async def test_idempotent_submission_does_not_replay_after_disconnect(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager(Path(temp) / "tasks")
            spec = TaskSpec(goal="Never start", request_id="known-submission", workspace=temp, acceptance="no replay")
            first = await manager.submit(spec)
            repeated = await manager.submit(spec)
            self.assertEqual(first["task_id"], repeated["task_id"])
            self.assertEqual(len(manager.jobs), 1)
            await manager.cancel(first["task_id"])
            new_manager = Manager(Path(temp) / "tasks")
            self.assertEqual((await new_manager.submit(spec))["state"], "cancelled")
            self.assertFalse(new_manager.jobs)
            with self.assertRaises(ValueError):
                await new_manager.submit(spec.model_copy(update={"goal": "Different work"}))
            await manager.close()
            await new_manager.close()

    async def test_already_cancelled_owned_coroutine_is_reconciled(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager(Path(temp) / "tasks")
            record = await manager.submit(TaskSpec(goal="Never start", workspace=temp, acceptance="cancelled"))
            manager.jobs[record["task_id"]].cancel()
            await asyncio.gather(manager.jobs[record["task_id"]], return_exceptions=True)
            self.assertEqual((await manager.cancel(record["task_id"]))["state"], "cancelled")
            await manager.close()

    async def test_close_before_worker_coroutine_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager(Path(temp) / "tasks")
            record = await manager.submit(TaskSpec(goal="Never start", workspace=temp, acceptance="cancelled"))
            await manager.close()
            self.assertEqual(manager.status(record["task_id"])["state"], "cancelled")

    async def test_cancel_before_worker_coroutine_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = Manager(root / "tasks")
            record = await manager.submit(TaskSpec(goal="No execution needed", workspace=temp,
                acceptance="Must not start when immediately cancelled"))
            result = await manager.cancel(record["task_id"])
            self.assertEqual(result["state"], "cancelled")
            self.assertFalse((manager.directory(record["task_id"]) / "events.jsonl").exists())
            await manager.close()

    async def test_dead_owner_is_interrupted_without_resubmit(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Manager(Path(temp))
            task_id = "a" * 32
            manager.directory(task_id).mkdir()
            manager.save(task_id, state="running", owner_pid=os.getpid(), owner_identity="different lifetime")
            self.assertEqual(manager.status(task_id)["state"], "interrupted")
            self.assertEqual(manager.jobs, {})


if __name__ == "__main__":
    unittest.main()
