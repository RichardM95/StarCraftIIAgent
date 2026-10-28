import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.storage import digest, snapshot, write_json
from sc2_mcp.transactions import Transactions
import sc2_mcp.transactions as module


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "map.SC2Map"
    root.mkdir()
    (root / "A").write_bytes(b"old-a")
    (root / "B").write_bytes(b"old-b")
    return root, Transactions(tmp_path / "state")


def test_commit_backup_baseline_and_rollback(setup):
    root, transactions = setup
    baseline = snapshot(root)
    result = transactions.run(root, lambda: {"A": b"new-a", "B": None, "Assets/x.dds": b"new"},
                              validator=lambda changes: {"static": "passed"})
    assert result["state"] == "committed"
    manifest = transactions.read(result["change_id"])
    assert manifest["baseline"] == baseline
    assert (Path(result["backup"]) / "A").read_bytes() == b"old-a"
    assert snapshot(root) == {"A": digest(b"new-a"), "Assets/x.dds": digest(b"new")}
    assert transactions.rollback(result["change_id"], root)["state"] == "rolled_back"
    assert snapshot(root) == baseline
    assert transactions.rollback(result["change_id"], root)["state"] == "rolled_back"


def test_preview_is_reviewable_and_does_not_commit(setup):
    root, transactions = setup
    baseline = snapshot(root)
    result = transactions.run(root, lambda: {"A": b"candidate"}, preview_only=True)
    assert result["state"] == "prepared"
    assert (Path(result["candidate"]) / "A").read_bytes() == b"candidate"
    assert Path(result["diff"]).is_file()
    assert snapshot(root) == baseline
    with pytest.raises(SC2Error) as error:
        transactions.rollback(result["change_id"], root)
    assert error.value.code == "invalid_change_state"


@pytest.mark.parametrize("plan", [{"A": "not bytes"}, {"../outside": b"x"}, {"a": b"x"},
                                  {"Assets/x": b"a", "Assets\\x": b"b"},
                                  {"Assets": b"file", "Assets/x": b"child"}, None])
def test_invalid_plans_are_structured_errors(setup, plan):
    root, transactions = setup
    before = snapshot(root)
    with pytest.raises(SC2Error):
        transactions.run(root, lambda: plan)
    assert snapshot(root) == before


def test_baseline_conflict_does_not_overwrite_external_change(setup):
    root, transactions = setup
    def planner():
        (root / "B").write_bytes(b"external")
        return {"A": b"candidate"}
    with pytest.raises(SC2Error) as error:
        transactions.run(root, planner)
    assert error.value.code == "baseline_conflict"
    assert (root / "A").read_bytes() == b"old-a"
    assert (root / "B").read_bytes() == b"external"


def test_validator_failure_does_not_write(setup):
    root, transactions = setup
    with pytest.raises(SC2Error) as error:
        transactions.run(root, lambda: {"A": b"new"}, validator=lambda _: {"static": "failed"})
    assert error.value.code == "validation_failed"
    assert (root / "A").read_bytes() == b"old-a"


def test_validator_cannot_mutate_the_authorized_file_plan(setup):
    root, transactions = setup
    def validator(candidate):
        candidate["B"] = b"not authorized"
        return {"static": "passed"}
    result = transactions.run(root, lambda: {"A": b"new-a"}, validator=validator)
    assert [entry["path"] for entry in result["files"]] == ["A"]
    assert (root / "B").read_bytes() == b"old-b"


def test_existing_directory_is_not_a_file_mutation(setup):
    root, transactions = setup
    (root / "Assets").mkdir()
    with pytest.raises(SC2Error) as error:
        transactions.run(root, lambda: {"Assets": b"wrong"})
    assert error.value.code == "path_collision"
    assert not (root / ".sc2-mcp/active-change.json").exists()


def test_mid_commit_cancel_restores_all_written_files(setup, monkeypatch):
    root, transactions = setup
    before = snapshot(root)
    event = threading.Event()
    original = module.atomic_write
    def intercept(path, data):
        original(path, data)
        if Path(path) == root / "A" and data == b"new-a":
            event.set()
    monkeypatch.setattr(module, "atomic_write", intercept)
    with pytest.raises(SC2Error) as error:
        transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"}, cancel=event)
    assert error.value.code == "cancelled"
    assert snapshot(root) == before
    records = list((transactions.state / "changes").glob("*/manifest.json"))
    assert json.loads(records[0].read_text("utf-8"))["state"] == "reverted"
    assert not (root / ".sc2-mcp/active-change.json").exists()


def test_late_external_edit_causes_recovery_conflict_not_overwrite(setup, monkeypatch):
    root, transactions = setup
    original = module.atomic_write
    def intercept(path, data):
        original(path, data)
        if Path(path) == root / "A" and data == b"new-a":
            (root / "B").write_bytes(b"manual-newer")
    monkeypatch.setattr(module, "atomic_write", intercept)
    with pytest.raises(SC2Error) as error:
        transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"})
    assert error.value.code == "recovery_conflict"
    assert (root / "A").read_bytes() == b"old-a"
    assert (root / "B").read_bytes() == b"manual-newer"
    with pytest.raises(SC2Error) as second:
        Transactions(transactions.state.parent / "different-state").run(root, lambda: {"A": b"another"})
    assert second.value.code == "recovery_required"


def test_rollback_preflights_every_file_before_restoring_any(setup):
    root, transactions = setup
    result = transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"})
    (root / "A").write_bytes(b"human-change")
    with pytest.raises(SC2Error) as error:
        transactions.rollback(result["change_id"], root)
    assert error.value.code == "rollback_conflict"
    assert (root / "B").read_bytes() == b"new-b"
    assert (root / "A").read_bytes() == b"human-change"


def test_corrupt_backup_prevents_any_rollback(setup):
    root, transactions = setup
    result = transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"})
    (Path(result["backup"]) / "A").write_bytes(b"broken")
    with pytest.raises(SC2Error) as error:
        transactions.rollback(result["change_id"], root)
    assert error.value.code == "backup_corrupt"
    assert (root / "A").read_bytes() == b"new-a"
    assert (root / "B").read_bytes() == b"new-b"


def test_failure_during_restore_remains_recoverable(setup, monkeypatch):
    root, transactions = setup
    original = module.atomic_write
    def intercept(path, data):
        original(path, data)
        if Path(path) == root / "A" and data == b"new-a":
            for path in (transactions.state / "changes").glob("*/backup/A"):
                path.unlink()
            raise OSError("injected after first target write")
    monkeypatch.setattr(module, "atomic_write", intercept)
    with pytest.raises(SC2Error) as error:
        transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"})
    assert error.value.code == "recovery_conflict"
    manifest = transactions.read(error.value.details["change_id"])
    assert manifest["state"] == "recovery_conflict"
    assert (root / "A").read_bytes() == b"new-a"
    assert (root / "B").read_bytes() == b"old-b"


def test_cross_process_lock_works_with_different_state_directories(setup):
    root, transactions = setup
    code = """from pathlib import Path
import sys
from sc2_mcp.transactions import Transactions
from sc2_mcp.errors import SC2Error
try:
 Transactions(Path(sys.argv[2])).run(Path(sys.argv[1]), lambda: {'A': b'new'})
 print('unexpected write')
except SC2Error as error:
 print(error.code)
"""
    with transactions.lock(root):
        result = subprocess.run([sys.executable, "-c", code, str(root), str(transactions.state.parent / "state2")],
                                capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "project_busy"
    assert (root / "A").read_bytes() == b"old-a"


def test_real_process_crash_releases_lock_and_recovers_partial_commit(setup):
    root, transactions = setup
    baseline = snapshot(root)
    code = """from pathlib import Path
import os,sys
import sc2_mcp.transactions as module
root=Path(sys.argv[1]); tx=module.Transactions(Path(sys.argv[2]))
original=module.atomic_write
def crash(path,data):
 original(path,data)
 if Path(path)==root/'A':
  os._exit(23)
module.atomic_write=crash
tx.run(root,lambda:{'A':b'new-a','B':b'new-b'})
"""
    child = subprocess.run([sys.executable, "-c", code, str(root), str(transactions.state)], capture_output=True, timeout=15)
    assert child.returncode == 23, child.stderr
    assert (root / "A").read_bytes() == b"new-a"
    assert (root / "B").read_bytes() == b"old-b"
    assert transactions.recover(root)[0]["state"] == "rolled_back"
    assert snapshot(root) == baseline
    assert transactions.recover(root) == []


def test_recover_interrupted_rollback(setup):
    root, transactions = setup
    baseline = snapshot(root)
    result = transactions.run(root, lambda: {"A": b"new-a", "B": b"new-b"})
    code = """from pathlib import Path
import os,sys
import sc2_mcp.transactions as module
root=Path(sys.argv[1]); tx=module.Transactions(Path(sys.argv[2]))
original=module.atomic_write
def crash(path,data):
 original(path,data)
 if Path(path)==root/'B':
  os._exit(24)
module.atomic_write=crash
tx.rollback(sys.argv[3],root)
"""
    child = subprocess.run([sys.executable, "-c", code, str(root), str(transactions.state), result["change_id"]],
                           capture_output=True, timeout=15)
    assert child.returncode == 24, child.stderr
    assert transactions.read(result["change_id"])["state"] == "rolling_back"
    assert transactions.recover(root)[0]["state"] == "rolled_back"
    assert snapshot(root) == baseline


def test_invalid_change_id_and_wrong_project_are_guarded(setup, tmp_path):
    root, transactions = setup
    with pytest.raises(SC2Error) as error:
        transactions.read("../outside")
    assert error.value.code == "invalid_change_id"
    result = transactions.run(root, lambda: {"A": b"new"})
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(SC2Error) as error:
        transactions.rollback(result["change_id"], other)
    assert error.value.code == "project_mismatch"


def test_tampered_manifest_cannot_traverse_outside_map(setup):
    root, transactions = setup
    result = transactions.run(root, lambda: {"A": b"new"})
    manifest = transactions.read(result["change_id"])
    manifest["entries"][0]["path"] = "../outside"
    write_json(transactions.state / "changes" / result["change_id"] / "manifest.json", manifest)
    with pytest.raises(SC2Error):
        transactions.rollback(result["change_id"], root)
    assert (root / "A").read_bytes() == b"new"
