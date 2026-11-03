"""Exercise the shared heavy-task gate with substitute client processes."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sc2_mcp import editor
from sc2_mcp.agent_bridge import sc2_activity as gate


@pytest.fixture
def local_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(gate,"activity_dir",lambda:tmp_path)
    monkeypatch.setattr(gate,"running_games",lambda:[])
    return tmp_path


def test_immediate_conflict_and_owner_crash(local_gate):
    code = """
import sys
from pathlib import Path
import sc2_activity as g
g.activity_dir=lambda:Path(sys.argv[1])
g.running_games=lambda:[]
with g.heavy_activity("regression"):
 print("ready",flush=True)
 sys.stdin.read()
"""
    env={**os.environ,"PYTHONPATH":str(Path(gate.__file__).parent)}
    child=subprocess.Popen([sys.executable,"-c",code,str(local_gate)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env)
    try:
        assert child.stdout.readline().strip()=="ready"
        for task in ("game in A","probe in B"):
            with pytest.raises(gate.ActivityBusy,match="regression"):
                with gate.heavy_activity(task):pytest.fail("admitted")
    finally:
        child.kill()
        child.communicate()
    with gate.heavy_activity("probe"):pass


def test_launch_handoff_and_manual_client(local_gate,monkeypatch):
    with gate.heavy_activity("SC2 运行探针"):
        with gate.heavy_activity("SC2 游戏启动"):
            pending=gate.reserve_start()
    with pytest.raises(gate.ActivityBusy,match="交接"):
        with gate.heavy_activity("integration"):pass
    pending.unlink()
    monkeypatch.setattr(gate,"running_games",lambda:["SC2_x64.exe (PID 123)"])
    with pytest.raises(gate.ActivityBusy,match="123"):
        with gate.heavy_activity("integration"):pass


def test_failed_launch_releases_gate(local_gate,monkeypatch):
    monkeypatch.setattr(editor,"build_launch_command",lambda *a:{})
    def fail(plan):raise OSError("fixture")
    monkeypatch.setattr(editor,"_launch",fail)
    with pytest.raises(OSError):editor.launch_test(Path("map"),Path("install"))
    with gate.heavy_activity("integration"):pass

def test_ignore_only_old_threadless_clients(monkeypatch):
    import psutil
    from types import SimpleNamespace
    now=gate.time.time()
    sample=[(1,0,now-86400),(2,0,now),(3,2,now-86400),(4,None,now-86400)]
    rows=[SimpleNamespace(pid=pid,info={"name":"SC2_x64.exe","create_time":created,"num_threads":threads})
          for pid,threads,created in sample]
    monkeypatch.setattr(psutil,"process_iter",lambda fields:rows)
    seen=" ".join(gate.running_games())
    assert "PID 1" not in seen and all(f"PID {pid}" in seen for pid in (2,3,4))
