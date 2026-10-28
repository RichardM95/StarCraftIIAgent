"""Independent Service/Server glue review; all map writes target tmp_path fixtures.

Keystone domain functions are stubbed only at their boundary. This exercises
transaction routing and guards, without reviewing the author's own domain code.
"""
import asyncio
import json
import os
from pathlib import Path

import pytest

from sc2_mcp import keystone
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
    (root / "MapScript.galaxy").write_bytes(b"void InitMap () {}\n")
    (root / "zhCN.SC2Data/LocalizedData").mkdir(parents=True)
    (root / "zhCN.SC2Data/LocalizedData/GameStrings.txt").write_bytes(b"review=before\n")
    service = Service(tmp_path / "state")
    monkeypatch.setattr(service, "editor_conflict", lambda: None)
    project = service.projects.open(str(root), True, search_roots=[str(source)])
    yield service, project["project_id"], root, dependency
    service.jobs.shutdown()


def prepare_three_files(service, key, monkeypatch):
    changes = {"MapScript.galaxy": SCRIPT,
               "zhCN.SC2Data/LocalizedData/GameStrings.txt": STRINGS,
               "Assets/Textures/review.dds": b"synthetic transaction payload"}
    monkeypatch.setattr(keystone, "plan_keystone_card_cost", lambda root, **kwargs: changes)
    prepared = service.prepare_keystone(key, "card_cost", {"card_id": 213, "mineral": 5, "gas": 2})
    return prepared, changes


def change_dependency(dependency):
    path = dependency / "Base.SC2Data/GameData/UnitData.xml"
    path.write_bytes(path.read_bytes().replace(b'"45"', b'"46"'))


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


def test_dependency_change_during_candidate_planning_is_rejected(environment, monkeypatch):
    service, key, root, dependency = environment
    before = snapshot(root)
    def planner(path, **kwargs):
        change_dependency(dependency)
        return {"MapScript.galaxy": SCRIPT}
    monkeypatch.setattr(keystone, "plan_keystone_card_cost", planner)
    with pytest.raises(SC2Error) as caught:
        service.prepare_keystone(key, "card_cost", {"card_id": 213, "mineral": 5, "gas": 2})
    assert caught.value.code == "source_context_stale"
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


@pytest.mark.parametrize("mode,expected", [("wrong_project", "invalid_candidate"),
                                          ("tamper", "candidate_corrupt"),
                                          ("baseline", "baseline_conflict"),
                                          ("pending", "recovery_required")])
def test_existing_transaction_guards_cannot_be_bypassed(environment, tmp_path, mode, expected):
    service, key, root, _ = environment
    prepared = service.transactions.run(root, lambda: {"MapScript.galaxy": SCRIPT}, label="legacy_candidate", preview_only=True)
    if mode == "wrong_project":
        other = tmp_path / "other.SC2Map"
        other.mkdir()
        (other / "DocumentInfo").write_bytes(b"<DocInfo/>")
        key = service.projects.open(str(other), True)["project_id"]
    elif mode == "tamper":
        (Path(prepared["candidate"]) / "MapScript.galaxy").write_bytes(b"void Changed () {}\n")
    elif mode == "baseline":
        (root / "unrelated.txt").write_bytes(b"external newly added component")
    else:
        write_json(root / ".sc2-mcp/active-change.json", {"id": "foreign", "state_directory": str(tmp_path / "other-state")})
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        service.apply_candidate(key, prepared["change_id"], experimental_write=True)
    assert caught.value.code == expected
    assert snapshot(root) == before


@pytest.mark.parametrize("experimental,formal", [(False, False), (True, True)])
@pytest.mark.parametrize("mode", ["terrain_label", "content_label_bypass", "old_terrain_deletion"])
def test_experimental_guard_checks_legacy_labels_and_actual_content(environment, monkeypatch, experimental, formal, mode):
    import sc2_mcp.service as service_module
    service, key, root, _ = environment
    if mode == "terrain_label":
        changes, label = {"MapScript.galaxy": SCRIPT}, "terrain_native_sync"
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
    if formal:
        monkeypatch.setattr(service_module, "KEYSTONE", root)
    prepared = service.transactions.run(root, lambda: changes, label=label, preview_only=True)
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        service.apply_candidate(key, prepared["change_id"], experimental_write=experimental)
    assert caught.value.code == "terrain_not_accepted"
    assert snapshot(root) == before


def test_readonly_and_foreign_source_context_stop_before_keystone_planner(environment, tmp_path, monkeypatch):
    service, key, root, _ = environment
    context = service.prepare_dependencies(key)
    invoked = []
    monkeypatch.setattr(keystone, "plan_keystone_card_cost", lambda *args, **kwargs: invoked.append(True))
    other = tmp_path / "other.SC2Map"
    other.mkdir()
    (other / "DocumentInfo").write_bytes(b"<DocInfo/>")
    other_key = service.projects.open(str(other), True)["project_id"]
    with pytest.raises(SC2Error) as caught:
        service.prepare_keystone(other_key, "card_cost", {}, context["source_context_id"])
    assert caught.value.code == "source_context_mismatch"
    service.projects.open(str(root), False)
    before = snapshot(root)
    with pytest.raises(SC2Error) as caught:
        service.prepare_keystone(key, "card_cost", {})
    assert caught.value.code == "readonly_project"
    assert not invoked and snapshot(root) == before


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


def test_server_exposes_and_dispatches_all_seven_keystone_entries(tmp_path, monkeypatch):
    server = create_server(tmp_path / "server-state")
    service = server.sc2_service
    observed = []
    monkeypatch.setattr(service, "keystone_inspect", lambda *args, **kwargs: observed.append(("inspect", args, kwargs)) or {"marker": "inspected"})
    monkeypatch.setattr(service, "prepare_keystone", lambda *args, **kwargs: observed.append(("prepare", args, kwargs)) or {"marker": "prepared"})
    image = tmp_path / "source-image.bin"
    image.write_bytes(b"image file bytes for glue-only fixture")
    cases = [
        ("sc2_keystone_card_inspect", {"project_id": "key", "card_id": 213}, "inspect", ("key", "card", {"card_id": 213, "name": None})),
        ("sc2_keystone_card_cost", {"project_id": "key", "card_id": 213, "mineral": 4, "gas": 2, "source_context_id": "ctx"}, "prepare", ("key", "card_cost", {"card_id": 213, "mineral": 4, "gas": 2}, "ctx")),
        ("sc2_keystone_descriptions", {"project_id": "key", "card_ids": [213], "source_context_id": "ctx"}, "inspect", ("key", "descriptions", {"card_ids": [213]}, "ctx")),
        ("sc2_keystone_news_inspect", {"project_id": "key", "category": "protoss"}, "inspect", ("key", "news", {"category": "protoss"})),
        ("sc2_keystone_news_update", {"project_id": "key", "category": "global", "date": "20261016", "body": "正文", "source_context_id": "ctx"}, "prepare", ("key", "news", {"category": "global", "date": "20261016", "body": "正文"}, "ctx")),
        ("sc2_keystone_portraits_inspect", {"project_id": "key"}, "inspect", ("key", "portraits")),
        ("sc2_keystone_portrait_import", {"project_id": "key", "image_path": str(image), "save_id": 140, "nemesis_unlock_id": 2, "backer_exclusive": True, "support_months_required": 3, "standard_wins_required": 4, "source_context_id": "ctx"}, "prepare", ("key", "portrait", {"image": image.read_bytes(), "save_id": 140, "nemesis_unlock_id": 2, "backer_exclusive": True, "support_months_required": 3, "standard_wins_required": 4}, "ctx")),
    ]
    async def check():
        registered = {tool.name: tool for tool in await server.list_tools()}
        assert {name for name in registered if name.startswith("sc2_keystone_")} == {case[0] for case in cases}
        for name, parameters, method, expected in cases:
            assert registered[name].annotations.readOnlyHint == (method == "inspect")
            await server.call_tool(name, parameters)
            assert observed[-1] == (method, expected, {})
    try:
        asyncio.run(check())
    finally:
        service.jobs.shutdown()


@pytest.mark.parametrize("kind,expected", [("missing", "keystone_image_invalid"),
                                         ("directory", "keystone_image_invalid"),
                                         ("oversized", "keystone_image_invalid"),
                                         ("hardlink", "hardlinked_file")])
def test_server_image_file_guard_rejects_before_planning(tmp_path, monkeypatch, kind, expected):
    from mcp.server.fastmcp.exceptions import ToolError
    server = create_server(tmp_path / "server-state")
    image = tmp_path / "image.bin"
    called = []
    monkeypatch.setattr(server.sc2_service, "prepare_keystone", lambda *args, **kwargs: called.append(True))
    if kind == "directory":
        image.mkdir()
    elif kind == "oversized":
        with image.open("wb") as handle:
            handle.truncate(64 * 1024 * 1024 + 1)
        original = Path.read_bytes
        def reject_oversized_read(path):
            assert path != image, "oversized file must not be loaded before the size guard"
            return original(path)
        monkeypatch.setattr(Path, "read_bytes", reject_oversized_read)
    elif kind == "hardlink":
        original = tmp_path / "original.bin"
        original.write_bytes(b"small source")
        os.link(original, image)
    async def check():
        with pytest.raises(ToolError, match=expected):
            await server.call_tool("sc2_keystone_portrait_import", {"project_id": "key", "image_path": str(image)})
        assert not called
    try:
        asyncio.run(check())
    finally:
        server.sc2_service.jobs.shutdown()


def test_inspection_glue_uses_requested_project_and_bound_description_context(environment, monkeypatch):
    service, key, root, dependency = environment
    context = service.prepare_dependencies(key)
    observed = []
    def capture(path, **kwargs):
        observed.append((path, kwargs))
        return {"captured": True}
    for function in ("inspect_keystone_card", "inspect_keystone_news", "inspect_keystone_portraits", "audit_keystone_descriptions"):
        monkeypatch.setattr(keystone, function, capture)
    service.projects.open(str(root), False)
    before = snapshot(root)
    service.keystone_inspect(key, "card", {"card_id": 213})
    assert observed[-1] == (root, {"card_id": 213})
    service.keystone_inspect(key, "news", {"category": "terran"})
    assert observed[-1] == (root, {"category": "terran"})
    service.keystone_inspect(key, "portraits")
    assert observed[-1] == (root, {})
    service.keystone_inspect(key, "descriptions", {"card_ids": [213]}, context["source_context_id"])
    assert observed[-1][0] == root
    assert observed[-1][1]["source_context"]["source_context_id"] == context["source_context_id"]
    assert observed[-1][1]["card_ids"] == [213]
    count = len(observed)
    change_dependency(dependency)
    with pytest.raises(SC2Error) as caught:
        service.keystone_inspect(key, "descriptions", {"card_ids": [213]}, context["source_context_id"])
    assert caught.value.code == "source_context_stale" and len(observed) == count
    assert snapshot(root) == before


def test_legacy_terrain_candidate_allows_explicit_independent_experiment(environment):
    service, key, root, _ = environment
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
        assert observed[-1] == ("sources", ("key", None, "enUS", None, None))
        await server.call_tool("sc2_changes_apply", {"project_id": "key", "change_id": "candidate"})
        assert observed[-1] == ("apply", ("key", "candidate", False))
        await server.call_tool("sc2_changes_apply", {"project_id": "key", "change_id": "candidate", "experimental_write": True})
        assert observed[-1] == ("apply", ("key", "candidate", True))
    try:
        asyncio.run(check())
    finally:
        server.sc2_service.jobs.shutdown()
