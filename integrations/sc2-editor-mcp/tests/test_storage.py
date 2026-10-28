import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.storage import atomic_write, file_lock, safe_path, snapshot, write_json


@pytest.mark.parametrize("relative", ["../out", "a/../../out", "C:/out", "C:out", "/out", "\\\\host\\share\\out",
                                      "a//b", "a/./b", "a/../b", "a:stream", "NUL.xml", "COM1", "LPT².txt",
                                      "a. ", "a.", "a\x00", "_codex_backups/x", ".sc2-mcp/x", ""])
def test_relative_path_rejects_windows_escapes(tmp_path, relative):
    with pytest.raises(SC2Error):
        safe_path(tmp_path, relative)


def test_path_casing_and_parent_file_are_not_aliases(tmp_path):
    (tmp_path / "Assets").mkdir()
    with pytest.raises(SC2Error) as error:
        safe_path(tmp_path, "assets/x.dds")
    assert error.value.code == "case_collision"
    (tmp_path / "file").write_bytes(b"x")
    with pytest.raises(SC2Error):
        safe_path(tmp_path, "file/child")
    assert safe_path(tmp_path, "Assets\\new.dds") == tmp_path / "Assets/new.dds"


def test_snapshot_excludes_service_state_and_handles_empty_file(tmp_path):
    (tmp_path / "A").write_bytes(b"")
    (tmp_path / ".sc2-mcp").mkdir()
    (tmp_path / ".sc2-mcp/lock").write_bytes(b"busy")
    (tmp_path / "_codex_backups").mkdir()
    (tmp_path / "_codex_backups/A").write_bytes(b"old")
    assert list(snapshot(tmp_path)) == ["A"]


def test_atomic_write_preserves_old_file_on_replace_failure(tmp_path, monkeypatch):
    target = tmp_path / "A"
    target.write_bytes(b"old")
    def failure(*args):
        raise OSError("injected replace failure")
    monkeypatch.setattr(os, "replace", failure)
    with pytest.raises(OSError):
        atomic_write(target, b"new")
    assert target.read_bytes() == b"old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["A"]


def test_hardlink_is_rejected_before_atomic_replace(tmp_path):
    source = tmp_path / "outside"
    source.write_bytes(b"outside")
    target = tmp_path / "linked"
    os.link(source, target)
    with pytest.raises(SC2Error) as error:
        atomic_write(target, b"new")
    assert error.value.code == "hardlinked_file"
    assert source.read_bytes() == target.read_bytes() == b"outside"


def test_cross_process_file_lock_and_release(tmp_path):
    path = tmp_path / "write.lock"
    code = """from pathlib import Path
import sys
from sc2_mcp.storage import file_lock
from sc2_mcp.errors import SC2Error
try:
 with file_lock(Path(sys.argv[1])):
  print('acquired')
except SC2Error as e:
 print(e.code)
"""
    with file_lock(path):
        blocked = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=15)
        assert blocked.returncode == 0, blocked.stderr
        assert blocked.stdout.strip() == "project_busy"
    released = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=15)
    assert released.stdout.strip() == "acquired"


def test_windows_junction_is_rejected_even_when_empty(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction case")
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "map"
    root.mkdir()
    link = root / "Assets"
    script = "New-Item -ItemType Junction -Path $env:SC2_TEST_LINK_PATH -Target $env:SC2_TEST_TARGET_PATH | Out-Null"
    # Environment values are data; no generated path is interpolated as code.
    environment = {**os.environ, "SC2_TEST_LINK_PATH": str(link), "SC2_TEST_TARGET_PATH": str(outside)}
    command = ["powershell", "-NoProfile", "-Command", script]
    created = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=15)
    if created.returncode != 0 or not link.is_junction():
        pytest.skip("Junction creation unavailable")
    try:
        with pytest.raises(SC2Error) as error:
            snapshot(root)
        assert error.value.code == "linked_path"
        with pytest.raises(SC2Error):
            safe_path(root, "Assets/x.dds")
    finally:
        # Remove only the junction entry; never recurse into its target.
        os.rmdir(link)


def test_json_rejects_nonfinite_state_before_writing(tmp_path):
    with pytest.raises(ValueError):
        write_json(tmp_path / "state.json", {"number": float("nan")})
    assert not (tmp_path / "state.json").exists()
