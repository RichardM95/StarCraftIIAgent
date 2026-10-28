from pathlib import Path

import pytest

from sc2_mcp import editor
from sc2_mcp.errors import SC2Error


def fixture(tmp_path):
    root = tmp_path / "StarCraft II"
    root.mkdir()
    key = "a" * 32
    (root / ".build.info").write_text(f"Branch|Active|Build Key|CDN Key|Version|Product\ncn|1|{key}|{'b'*32}|5.0.17.98370|\n")
    config = root / "SC2Data" / "config" / "aa" / "aa" / key
    config.parent.mkdir(parents=True)
    config.write_text("build-uid = s2c\n")
    for name in ("Support64/SC2Editor_x64.exe", "Support64/SC2Switcher_x64.exe", "Versions/Base98370/SC2_x64.exe"):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"not executed")
    map_path = tmp_path / "地图 with spaces.SC2Map"
    map_path.mkdir()
    (map_path / "DocumentInfo").write_text("<DocInfo/>")
    return root, map_path


def test_editor_argv_is_structured_and_preserves_spaces(tmp_path):
    root, map_path = fixture(tmp_path)
    plan = editor.build_launch_command(map_path, root)
    assert plan["argv"] == [str(root / "Support64/SC2Editor_x64.exe"), "-loadfile", str(map_path), "-product", "SC2", "-uid", "s2_cn"]
    assert plan["map_load_verified"] is False


def test_test_launch_matches_product_build(tmp_path):
    root, map_path = fixture(tmp_path)
    plan = editor.build_launch_command(map_path, root, "test")
    assert plan["argv"][1:3] == ["-run", str(map_path)]
    assert plan["selected_client"].endswith("Base98370\\SC2_x64.exe") or plan["selected_client"].endswith("Base98370/SC2_x64.exe")
    (root / "Versions/Base98370/SC2_x64.exe").unlink()
    with pytest.raises(SC2Error) as err:
        editor.build_launch_command(map_path, root, "test")
    assert err.value.code == "CLIENT_BUILD_MISSING"


def test_region_diagnose_confirms_cn_build_without_launching(tmp_path, monkeypatch):
    root, map_path = fixture(tmp_path)
    (map_path / "zhCN.SC2Data").mkdir()
    monkeypatch.setattr(editor, "_registry_editor_commands", lambda: {"available": True, "entries": [
        {"class": "SC2.Map", "key": "SC2.Map\\shell\\open\\command", "command": "x",
         "executable": str(root / "Support64/SC2Editor_x64.exe"), "status": "present"}
    ]})
    monkeypatch.setattr(editor, "_region_log_evidence", lambda: [])

    result = editor.diagnose_editor_region(root, product="s2_cn", branch="cn", map_path=map_path)

    assert result["schema"] == "editor-region-diagnostics/1"
    assert result["selected_build"]["product"] == "s2_cn"
    assert result["selected_build"]["branch"] == "cn"
    assert result["verdict"] == "no_static_region_conflict_found"
    assert result["editor"]["exists"] is True
    assert result["map"]["locale_component"]["exists"] is True
    assert result["launch_performed"] is False


def test_region_diagnose_reports_product_branch_conflict(tmp_path, monkeypatch):
    root, _ = fixture(tmp_path)
    monkeypatch.setattr(editor, "_registry_editor_commands", lambda: {"available": False, "reason": "test", "entries": []})
    monkeypatch.setattr(editor, "_region_log_evidence", lambda: [])

    result = editor.diagnose_editor_region(root, product="s2", branch="cn")

    codes = {item["code"] for item in result["checks"] if item["status"] == "fail"}
    assert result["verdict"] == "blocked"
    assert "BUILD_SELECTION" in codes
    assert "REGION_PRODUCT_MISMATCH" in codes
    assert any("product" in item for item in result["recommendations"])


def test_region_diagnose_reports_registry_and_locale_warnings(tmp_path, monkeypatch):
    root, map_path = fixture(tmp_path)
    monkeypatch.setattr(editor, "_registry_editor_commands", lambda: {"available": True, "entries": [
        {"class": "SC2.Map", "key": "SC2.Map\\shell\\open\\command", "command": "old",
         "executable": str(tmp_path / "old/SC2Editor_x64.exe"), "status": "present"}
    ]})
    monkeypatch.setattr(editor, "_region_log_evidence", lambda: [])

    result = editor.diagnose_editor_region(root, product="s2_cn", branch="cn", map_path=map_path)

    codes = {item["code"] for item in result["checks"] if item["status"] == "warning"}
    assert "REGISTRY_OPEN_COMMAND_PATH" in codes
    assert "MAP_LOCALE_COMPONENT" in codes
    assert result["verdict"] == "needs_review"


def test_does_not_reuse_existing_editor(tmp_path, monkeypatch):
    root, map_path = fixture(tmp_path)
    monkeypatch.setattr(editor, "_windows", lambda: None)
    monkeypatch.setattr(editor, "processes", lambda *a: [{"name": "SC2Editor_x64.exe", "pid": 22}])
    def no_launch(*a, **kw):
        pytest.fail("Existing editor must not receive a map open operation")
    monkeypatch.setattr(editor.subprocess, "Popen", no_launch)
    with pytest.raises(SC2Error) as err:
        editor.open_editor(map_path, root)
    assert err.value.code == "APPLICATION_ALREADY_RUNNING"


def test_credentials_redacted_from_diagnostics():
    assert editor._redacted_args(["-uid", "s2_cn", "-accessToken=secret", "-password", "hidden", "-run", "a.SC2Map"]) == ["-uid", "s2_cn", "-accessToken=<redacted>", "-password", "<redacted>", "-run", "a.SC2Map"]


def test_log_read_restricted_and_bounded(tmp_path, monkeypatch):
    docs = tmp_path / "Documents"
    logs = docs / "EditorLogs"
    logs.mkdir(parents=True)
    monkeypatch.setattr(editor, "documents_root", lambda: docs)
    log = logs / "Alerts.txt"
    log.write_text("A" * 30 + "\ntoken=secret\n")
    result = editor.read_log(log, 20)
    assert "secret" not in result["tail"]
    assert result["truncated"]
    assert result["runtime_passed"] is None
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    with pytest.raises(SC2Error):
        editor.read_log(outside)


def test_capture_rejects_nonowned_process_before_creating_file(tmp_path, monkeypatch):
    monkeypatch.setattr(editor, "_windows", lambda: None)
    monkeypatch.setattr(editor, "_owned_process", lambda _: False)
    output = tmp_path / "screen.png"
    with pytest.raises(SC2Error) as err:
        editor.capture_window(1, output)
    assert err.value.code == "PROCESS_NOT_OWNED"
    assert not output.exists()


def test_visible_capture_never_touches_unowned_window(tmp_path, monkeypatch):
    monkeypatch.setattr(editor, "_windows", lambda: None)
    monkeypatch.setattr(editor, "_owned_process", lambda _: False)
    output = tmp_path / "visible.png"
    with pytest.raises(SC2Error) as err:
        editor.capture_visible_window(1, output)
    assert err.value.code == "PROCESS_NOT_OWNED"
    assert not output.exists()
