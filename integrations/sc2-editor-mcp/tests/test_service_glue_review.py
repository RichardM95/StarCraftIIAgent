"""Independent Service/Server glue review; all map writes target tmp_path fixtures.

The fixture exercises transaction routing and guards with generic source edits.
"""
import asyncio
import json
import os
from pathlib import Path

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.server import create_server
from sc2_mcp.service import Service
from sc2_mcp.storage import snapshot, write_json


SCRIPT = b"void InitMap () { int marker = 1; }\n"
STRINGS = "review=新候选\n".encode("utf-8")


@pytest.fixture
def environment(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    root = source / "map.SC2Map"
    root.mkdir(parents=True)
    dependency = source / "Mods/A.SC2Mod"
    (dependency / "Base.SC2Data/GameData").mkdir(parents=True)
    (root / "DocumentInfo").write_bytes(b'<DocInfo><Dependencies><Value>file:Mods/A.SC2Mod</Value></Dependencies></DocInfo>')
    (dependency / "DocumentInfo").write_bytes(b"<DocInfo/>")
    (dependency / "Base.SC2Data/GameData/UnitData.xml").write_bytes(b'<Catalog><CUnit id="A"><LifeMax value="45"/></CUnit></Catalog>')
    (root / "GlueFixture.galaxy").write_bytes(b"void InitMap () {}\n")
    (root / "zhCN.SC2Data/LocalizedData").mkdir(parents=True)
    (root / "zhCN.SC2Data/LocalizedData/GameStrings.txt").write_bytes(b"review=before\n")
    service = Service(tmp_path / "state")
    monkeypatch.setattr(service, "editor_conflict", lambda: None)
    project = service.projects.open(str(root), True, search_roots=[str(source)])
    yield service, project["project_id"], root, dependency
    service.jobs.shutdown()


def prepare_three_files(service, key, monkeypatch):
    changes = {"GlueFixture.galaxy": SCRIPT,
               "zhCN.SC2Data/LocalizedData/GameStrings.txt": STRINGS,
               "Assets/Textures/review.dds": b"synthetic transaction payload"}
    prepared = service.prepare_domain(key, "fixture_source_edit", lambda root, roots, context: changes)
    return prepared, changes


def change_dependency(dependency):
    path = dependency / "Base.SC2Data/GameData/UnitData.xml"
    path.write_bytes(path.read_bytes().replace(b'"45"', b'"46"'))


def test_apply_receipt_survives_restart_manual_edits_and_rollback(environment, monkeypatch):
    from sc2_mcp.operations import create_operations
    service, key, root, _ = environment
    candidate, changes = prepare_three_files(service, key, monkeypatch)
    cid = candidate["change_id"]
    applied = service.apply_candidate(key, cid)
    assert applied["candidate_id"] == cid
    reopened = Service(service.state)
    try:
        inspect = create_operations(reopened)["sc2_changes_inspect"][0]
        assert inspect(key, cid)["application"] == {"change_id":applied["change_id"], "state":"committed"}
        target = root / "GlueFixture.galaxy"
        target.write_bytes(b"subsequent manual edit")
        monkeypatch.setattr(reopened, "editor_conflict", lambda: True)
        count = len(list((service.state / "changes").iterdir()))
        assert reopened.apply_candidate(key, cid) == applied
        assert target.read_bytes() == b"subsequent manual edit"
        target.write_bytes(changes["GlueFixture.galaxy"])
        reopened.transactions.rollback(applied["change_id"], root)
        assert inspect(key, cid)["application"]["state"] == "rolled_back"
        assert reopened.apply_candidate(key, cid)["state"] == "rolled_back"
        assert len(list((service.state / "changes").iterdir())) == count
    finally:
        reopened.jobs.shutdown()


def test_dependency_change_during_candidate_planning_is_rejected(environment):
    service, key, root, dependency = environment
    before = snapshot(root)

    def planner(root, roots, context):
        change_dependency(dependency)
        return {"GlueFixture.galaxy": SCRIPT}

    with pytest.raises(SC2Error) as error:
        service.prepare_domain(key, "fixture_source_edit", planner)
    assert error.value.code == "source_context_stale"
    assert snapshot(root) == before


def test_apply_receipt_after_process_exit_before_reply(environment, monkeypatch):
    import subprocess
    import sys

    service, key, root, _ = environment
    candidate, changes = prepare_three_files(service, key, monkeypatch)
    cid = candidate["change_id"]
    child = """
import os, sys
from pathlib import Path
from sc2_mcp.service import Service
s = Service(Path(sys.argv[1]))
s.editor_conflict = lambda: None
s.transactions._clear = lambda manifest: os._exit(17)
s.apply_candidate(sys.argv[2], sys.argv[3])
"""
    proc = subprocess.run([sys.executable, "-c", child, str(service.state), key, cid], timeout=30)
    assert proc.returncode == 17
    recovered, = service.transactions.recover(root)
    assert recovered["state"] == "committed"
    assert service.apply_candidate(key, cid) == recovered
    assert (root / "GlueFixture.galaxy").read_bytes() == changes["GlueFixture.galaxy"]


def test_dependency_change_during_apply_validation_must_not_commit(environment, monkeypatch):
    service, key, root, dependency = environment
    before = snapshot(root)
    prepared, _ = prepare_three_files(service, key, monkeypatch)
    original = service._validate_candidate
    def validation_then_external_dependency_change(*args, **kwargs):
        result = original(*args, **kwargs)
        change_dependency(dependency)
        return result
    monkeypatch.setattr(service, "_validate_candidate", validation_then_external_dependency_change)
    error = None
    committed = None
    try:
        committed = service.apply_candidate(key, prepared["change_id"])
    except SC2Error as caught:
        error = caught
    evidence = {"commit": committed, "error": error.as_dict() if error else None,
                "map_changed": snapshot(root) != before}
    assert error is not None and error.code == "source_context_stale", json.dumps(evidence, ensure_ascii=False)
    assert snapshot(root) == before


def test_three_file_glue_candidate_commits_atomically_and_rolls_back(environment, monkeypatch):
    service, key, root, _ = environment
    before = snapshot(root)
    prepared, changes = prepare_three_files(service, key, monkeypatch)
    assert snapshot(root) == before and prepared["state"] == "prepared"
    manifest = service.transactions.read(prepared["change_id"])
    assert manifest["source_context_id"] == prepared["source_context_id"]
    assert {entry["path"] for entry in manifest["entries"]} == set(changes)
    applied = service.apply_candidate(key, prepared["change_id"])
    assert applied["state"] == "committed"
    for relative, content in changes.items():
        assert (root / relative).read_bytes() == content
    service.transactions.rollback(applied["change_id"], root)
    assert snapshot(root) == before


def test_glue_commit_failure_restores_every_earlier_file(environment, monkeypatch):
    from sc2_mcp import transactions
    service, key, root, _ = environment
    before = snapshot(root)
    prepared, _ = prepare_three_files(service, key, monkeypatch)
    original = transactions.atomic_write
    failed = []
    def fail_second_live_file(path, content):
        if Path(path) == root / "zhCN.SC2Data/LocalizedData/GameStrings.txt" and content == STRINGS and not failed:
            failed.append(str(path))
            raise OSError("independent synthetic second-file write failure")
        return original(path, content)
    monkeypatch.setattr(transactions, "atomic_write", fail_second_live_file)
    with pytest.raises(OSError, match="second-file write failure"):
        service.apply_candidate(key, prepared["change_id"])
    assert failed and snapshot(root) == before
    records = [service.transactions.read(path.parent.name) for path in (service.state / "changes").glob("*/manifest.json")]
    assert sorted(record["state"] for record in records) == ["prepared", "reverted"]
    assert not (root / ".sc2-mcp/active-change.json").exists()


@pytest.mark.parametrize("mode,expected", [("wrong_project", "project_mismatch"),
                                          ("tamper", "candidate_corrupt"),
                                          ("baseline", "baseline_conflict"),
                                          ("pending", "recovery_required")])
def test_existing_transaction_guards_cannot_be_bypassed(environment, tmp_path, mode, expected):
    service, key, root, _ = environment
    prepared = service.transactions.run(root, lambda: {"GlueFixture.galaxy": SCRIPT}, label="legacy_candidate", preview_only=True)
    if mode == "wrong_project":
        other = tmp_path / "other.SC2Map"
        other.mkdir()
        (other / "DocumentInfo").write_bytes(b"<DocInfo/>")
        key = service.projects.open(str(other), True)["project_id"]
    elif mode == "tamper":
        (Path(prepared["candidate"]) / "GlueFixture.galaxy").write_bytes(b"void Changed () {}\n")
    elif mode == "baseline":
        (root / "unrelated.txt").write_bytes(b"external newly added component")
    else:
        write_json(root / ".sc2-mcp/active-change.json", {"id": "foreign", "state_directory": str(tmp_path / "other-state")})
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        service.apply_candidate(key, prepared["change_id"], experimental_write=True)
    assert caught.value.code == expected
    assert snapshot(root) == before


@pytest.mark.parametrize("experimental", [False, True])
@pytest.mark.parametrize("mode", ["terrain_label", "content_label_bypass", "old_terrain_deletion"])
def test_experimental_guard_checks_legacy_labels_and_actual_content(environment, monkeypatch, experimental, mode):
    import sc2_mcp.service as service_module
    service, key, root, _ = environment
    if mode == "terrain_label":
        changes, label = {"GlueFixture.galaxy": SCRIPT}, "terrain_native_sync"
    else:
        relative = "Base.SC2Data/GameData/Unexpected.xml"
        terrain = b'<Catalog><CTerrain id="ReviewTerrain"/></Catalog>'
        if mode == "old_terrain_deletion":
            (root / relative).parent.mkdir(parents=True)
            (root / relative).write_bytes(terrain)
            changes = {relative: None}
        else:
            changes = {relative: terrain}
        label = "legacy_candidate"
    prepared = service.transactions.run(root, lambda: changes, label=label, preview_only=True)
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        service.apply_candidate(key, prepared["change_id"], experimental_write=experimental)
    assert caught.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


def test_editor_started_during_apply_validation_keeps_candidate(environment, monkeypatch):
    service, key, root, _ = environment
    before = snapshot(root)
    prepared, _ = prepare_three_files(service, key, monkeypatch)
    original = service._validate_candidate
    def editor_starts_after_validation(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(service, "editor_conflict", lambda: {"code": "fixture_editor_started"})
        return result
    monkeypatch.setattr(service, "_validate_candidate", editor_starts_after_validation)
    with pytest.raises(SC2Error) as caught:
        service.apply_candidate(key, prepared["change_id"])
    assert caught.value.code == "editor_started_during_plan"
    assert snapshot(root) == before
    assert service.transactions.read(prepared["change_id"])["state"] == "prepared"


def test_source_selection_survives_restart_and_failed_override(environment, monkeypatch):
    from sc2_mcp import source_context
    from sc2_mcp.storage import digest
    service, key, _, _ = environment
    calls = []
    def context(root, search, cache, installation, locale, product, branch, **kwargs):
        if locale == "bad":
            raise SC2Error("invalid_locale", "fixture invalid locale")
        selected = {"installation": str(installation), "locale": locale, "product": product, "branch": branch}
        calls.append(selected)
        return {"source_context_id": digest(json.dumps(selected, sort_keys=True).encode()), "complete": False}
    monkeypatch.setattr(source_context, "prepare_source_context", context)
    service.prepare_dependencies(key, "D:/Verified SC2", "zhCN", "s2_cn", "cn")
    restarted = Service(service.state)
    try:
        restarted.prepare_dependencies(key, locale="enUS")
        restarted.prepare_dependencies(key, product="s2")
        restarted.prepare_dependencies(key, branch="kr")
        assert calls[-1] == {"installation": str(Path("D:/Verified SC2")), "locale": "enUS", "product": "s2", "branch": "kr"}
        selected_file = service.state / "source-selections" / (key + ".json")
        before = selected_file.read_bytes()
        with pytest.raises(SC2Error):
            restarted.prepare_dependencies(key, locale="bad")
        assert selected_file.read_bytes() == before
        restarted.prepare_dependencies(key)
        assert calls[-1] == calls[-2]
    finally:
        restarted.jobs.shutdown()


def test_legacy_terrain_candidate_allows_explicit_independent_experiment(environment):
    service, key, root, _ = environment
    copy = service.projects.clone(key,str(root.parent / "trial.SC2Map"))
    root, key = Path(copy["root"]), copy["project_id"]
    before = snapshot(root)
    relative = "Base.SC2Data/GameData/Unexpected.xml"
    content = b'<Catalog><CTerrain id="ReviewTerrain"/></Catalog>'
    prepared = service.transactions.run(root, lambda: {relative: content}, label="legacy_candidate", preview_only=True)
    applied = service.apply_candidate(key, prepared["change_id"], experimental_write=True)
    assert applied["state"] == "committed" and (root / relative).read_bytes() == content
    service.transactions.rollback(applied["change_id"], root)
    assert snapshot(root) == before


def test_server_preserves_omitted_source_options_and_experimental_default(tmp_path, monkeypatch):
    server = create_server(tmp_path / "server-state")
    observed = []
    monkeypatch.setattr(server.sc2_service, "prepare_dependencies", lambda *args: observed.append(("sources", args)) or {"captured": True})
    monkeypatch.setattr(server.sc2_service, "apply_candidate", lambda *args: observed.append(("apply", args)) or {"captured": True})
    async def check():
        await server.call_tool("sc2_dependencies_prepare", {"project_id": "key", "locale": "enUS", "background": False})
        assert observed[-1] == ("sources", ("key", None, "enUS", None, None, None))
        await server.call_tool("sc2_changes_apply", {"project_id": "key", "change_id": "candidate"})
        assert observed[-1] == ("apply", ("key", "candidate", False))
        await server.call_tool("sc2_changes_apply", {"project_id": "key", "change_id": "candidate", "experimental_write": True})
        assert observed[-1] == ("apply", ("key", "candidate", True))
    try:
        asyncio.run(check())
    finally:
        server.sc2_service.jobs.shutdown()
