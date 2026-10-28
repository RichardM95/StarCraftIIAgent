import json
from pathlib import Path
import stat

import pytest

from sc2_mcp import archives, source_context as sources
from sc2_mcp.catalog import inspect_catalog
from sc2_mcp.errors import SC2Error


def put(root, relative, raw):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw.encode() if isinstance(raw, str) else raw)
    return path


def component(root, dependencies=(), amount="45"):
    put(root, "DocumentInfo", "<DocInfo><Dependencies>" + "".join(f"<Value>{value}</Value>" for value in dependencies) + "</Dependencies></DocInfo>")
    put(root, "Base.SC2Data/GameData/UnitData.xml", f'<Catalog><CUnit id="A"><LifeMax value="{amount}"/></CUnit></Catalog>')
    return root


def prepare(root, tmp_path, **kwargs):
    return sources.prepare_source_context(root, [tmp_path / "deps"], tmp_path / "cache", **kwargs)


def test_recursive_actual_order_locale_and_restart_identity(tmp_path):
    deps = tmp_path / "deps"
    component(deps / "A.SC2Mod", ["file:B.SC2Mod"], "50")
    component(deps / "B.SC2Mod", amount="40")
    root = component(tmp_path / "map.SC2Map", ["file:a.sc2mod"])
    put(root, "zhCN.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="A"><Name value="CN"/></CUnit></Catalog>')
    context = prepare(root, tmp_path)
    assert context["complete"]
    assert [Path(p).name for p in context["dependency_report"]["load_order"]] == ["B.SC2Mod", "A.SC2Mod", "map.SC2Map"]
    persisted = json.loads(json.dumps(context))
    assert sources.assert_source_context_current(persisted)["current"]
    assert inspect_catalog([Path(p) for p in context["roots"]], "Unit", "A")["fields"]["Name"]["value"] == "CN"
    persisted["roots"].reverse()
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(persisted)
    assert error.value.code == "invalid_source_context"


@pytest.mark.parametrize("mutation", ["bytes", "addition", "include", "declaration"])
def test_source_mutations_invalidate_old_context_and_change_id(tmp_path, mutation):
    root = component(tmp_path / "map.SC2Map")
    context = prepare(root, tmp_path)
    if mutation == "bytes":
        put(root, "Base.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="A"><LifeMax value="99"/></CUnit></Catalog>')
    elif mutation == "addition":
        put(root, "Assets/Textures/new.dds", b"new bytes")
    elif mutation == "include":
        put(root, "Base.SC2Data/GameData.xml", '<Includes><Catalog path="GameData/extra.xml"/></Includes>')
        put(root, "Base.SC2Data/GameData/extra.xml", '<Catalog><CUnit id="B"/></Catalog>')
    else:
        component(tmp_path / "deps/X.SC2Mod")
        component(root, ["file:X.SC2Mod"])
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(context)
    assert error.value.code == "source_context_stale"
    assert prepare(root, tmp_path)["source_context_id"] != context["source_context_id"]


def test_missing_cycles_and_unverified_bnet_cannot_be_complete(tmp_path):
    root = component(tmp_path / "map.SC2Map", ["file:A.SC2Mod", "file:Missing.SC2Mod", "bnet:one"])
    component(tmp_path / "deps/A.SC2Mod", ["file:A.SC2Mod", "bnet:id,file:B.SC2Mod"])
    component(tmp_path / "deps/B.SC2Mod")
    result = prepare(root, tmp_path)
    assert not result["complete"]
    assert result["dependency_report"]["cycles"]
    assert {item["kind"] for item in result["dependency_report"]["missing"]} == {"file", "bnet"}
    edge = next(edge for edge in result["dependency_report"]["edges"] if edge["reference"] == "bnet:id,file:B.SC2Mod")
    assert edge["resolved"] and edge["bnet_identity_verified"] is False


@pytest.mark.parametrize("contents,reason", [('<Includes><Catalog path="GameData/Missing.xml"/></Includes>', "missing_catalog_include"), ('<Includes><Catalog path="GameData.xml"/></Includes>', "catalog_include_cycle")])
def test_include_failures_remain_reportable(tmp_path, contents, reason):
    root = component(tmp_path / "map.SC2Map")
    put(root, "Base.SC2Data/GameData.xml", contents)
    result = prepare(root, tmp_path)
    assert not result["complete"]
    assert reason in {item["reason"] for item in result["dependency_report"]["incomplete"]}


def test_cache_must_stay_outside_source(tmp_path):
    root = component(tmp_path / "map.SC2Map")
    with pytest.raises(SC2Error) as error:
        sources.prepare_source_context(root, [], root / "cache")
    assert error.value.code == "source_cache_in_source"


def make_archive(tmp_path, source, destination):
    if not archives.backend_capabilities()["can_export"]:
        pytest.skip("real MPQ backend unavailable")
    archives.export_archive(source, destination)
    return destination


def test_real_mpq_sparse_cache_recursive_dependencies_and_tamper(tmp_path):
    dep_source = component(tmp_path / "dep_source", ["file:B.SC2Mod"], "50")
    put(dep_source, "Assets/Textures/huge.dds", b"not cached")
    put(dep_source, "Base.SC2Data/GameData.xml", '<Includes><Catalog path="GameData/extra.xml"/></Includes>')
    put(dep_source, "Base.SC2Data/GameData/extra.xml", '<Catalog><CUnit id="Extra"/></Catalog>')
    component(tmp_path / "deps/B.SC2Mod", amount="40")
    archive = tmp_path / "deps/A.SC2Mod"
    make_archive(tmp_path, dep_source, archive)
    root = component(tmp_path / "map.SC2Map", ["file:A.SC2Mod"])
    before_archive = archive.read_bytes()
    context = prepare(root, tmp_path)
    assert context["complete"]
    node = next(node for node in context["dependency_report"]["nodes"] if node["source_kind"] == "mpq")
    cached = Path(node["materialized_root"])
    assert not (cached / "Assets").exists()
    assert (cached / "Base.SC2Data/GameData/extra.xml").exists()
    assert prepare(root, tmp_path)["source_context_id"] == context["source_context_id"]
    target = cached / "Base.SC2Data/GameData/UnitData.xml"
    target.chmod(stat.S_IREAD | stat.S_IWRITE)
    target.write_bytes(b"tampered")
    with pytest.raises(SC2Error) as error:
        prepare(root, tmp_path)
    assert error.value.code == "source_cache_tampered"
    assert archive.read_bytes() == before_archive


def test_build_selection_and_change_are_bound(tmp_path, monkeypatch):
    root = component(tmp_path / "map.SC2Map")
    install = tmp_path / "install"
    info = put(install, ".build.info", "build one")
    config = put(install, "config", "config one")
    monkeypatch.setattr(sources.casc, "inspect_installation", lambda path: {"build_info_sha256": sources._hash_file(info)})
    monkeypatch.setattr(sources.casc, "select_build", lambda *args, **kwargs: {"product": "s2_cn", "branch": "cn", "build_key": "a", "build_config": str(config)})
    context = prepare(root, tmp_path, installation=install, product="s2_cn", branch="cn")
    info.write_text("build two")
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(context)
    assert error.value.code == "source_context_stale"
    assert prepare(root, tmp_path, installation=install)["source_context_id"] != context["source_context_id"]


def test_proposed_dependencies_do_not_write_and_shared_impact_uses_materialized_roots(tmp_path):
    from sc2_mcp.dependencies import analyze_dependency_impact
    dep_a = component(tmp_path / "deps/A.SC2Mod", amount="40")
    dep_b = component(tmp_path / "deps/B.SC2Mod", amount="80")
    root = component(tmp_path / "map.SC2Map", ["file:A.SC2Mod"])
    # A dependency-only object remains visibly different after the root layer.
    put(root, "Base.SC2Data/GameData/UnitData.xml", "<Catalog/>")
    original = (root / "DocumentInfo").read_bytes()
    before = prepare(root, tmp_path)
    after = prepare(root, tmp_path, dependency_values=["file:B.SC2Mod"])
    result = analyze_dependency_impact(root, ["file:B.SC2Mod"], [tmp_path / "deps"], ["Unit"], before_context=before, after_context=after)
    assert result["complete"] and result["counts"]["changed_objects"] == 1
    field = result["changed"][0]["fields"][0]
    assert field["before"]["value"] == "40" and field["after"]["value"] == "80"
    assert (root / "DocumentInfo").read_bytes() == original
    assert before["source_context_id"] != after["source_context_id"]


def test_search_shadow_and_parser_changes_invalidate_persisted_context(tmp_path, monkeypatch):
    root = component(tmp_path / "map.SC2Map", ["file:A.SC2Mod"])
    component(tmp_path / "fallback/A.SC2Mod")
    preferred = tmp_path / "preferred"
    preferred.mkdir()
    context = sources.prepare_source_context(root, [preferred, tmp_path / "fallback"], tmp_path / "cache")
    component(preferred / "A.SC2Mod")
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(context)
    assert error.value.code == "source_context_stale"
    fresh = sources.prepare_source_context(root, [preferred, tmp_path / "fallback"], tmp_path / "cache")
    monkeypatch.setattr(sources, "PARSER_VERSION", "changed-parser")
    with pytest.raises(SC2Error) as error:
        sources.assert_source_context_current(fresh)
    assert error.value.code == "source_context_stale"


def test_include_frontiers_are_batched_without_changing_closure(tmp_path):
    files = {"base.sc2data/gamedata.xml": ("Base.SC2Data/GameData.xml", b'<Includes><Catalog path="GameData/A.xml"/><Catalog path="GameData/B.xml"/></Includes>'),
             "base.sc2data/gamedata/a.xml": ("Base.SC2Data/GameData/A.xml", b'<Catalog><Include path="MoreA.xml"/></Catalog>'),
             "base.sc2data/gamedata/b.xml": ("Base.SC2Data/GameData/B.xml", b'<Catalog><Include path="MoreB.xml"/></Catalog>'),
             "base.sc2data/gamedata/morea.xml": ("Base.SC2Data/GameData/MoreA.xml", b'<Catalog><CUnit id="A"/></Catalog>'),
             "base.sc2data/gamedata/moreb.xml": ("Base.SC2Data/GameData/MoreB.xml", b'<Catalog><CUnit id="B"/></Catalog>')}
    calls = []
    def read(names):
        calls.append(names)
        return {name.casefold(): files[name.casefold()] for name in names if name.casefold() in files}
    selected, issues = sources._catalog_closure(read, "zhCN")
    assert not issues and len(selected) == 5
    assert len(calls) == 3
    assert "Base.SC2Data/GameData/A.xml" in calls[1] and "Base.SC2Data/GameData/B.xml" in calls[1]
    assert "Base.SC2Data/GameData/MoreA.xml" in calls[2] and "Base.SC2Data/GameData/MoreB.xml" in calls[2]


def test_casc_optional_missing_still_requires_exact_hash_and_membership(tmp_path, monkeypatch):
    import hashlib
    def extract(_installation, names, destination, **kwargs):
        stage = destination.parent / "diagnostics"
        target = put(stage / "files", names[0], b"official")
        rows = [{"path": names[0], "bytes": 8, "sha256": hashlib.sha256(b"official").hexdigest()}]
        put(stage, "result.json", json.dumps({"files": rows, "missing": [{"path": name} for name in names[1:]]}))
        raise SC2Error("CASC_ASSET_MISSING", "optional missing", diagnostics=str(stage))
    monkeypatch.setattr(sources.casc, "extract_casc", extract)
    build = {"product": "s2_cn", "branch": "cn"}
    result = sources._read_casc_batch(tmp_path / "install", "Mods/A.SC2Mod", ["DocumentInfo", "DocumentHeader"], tmp_path / "cache", build)
    assert result["documentinfo"][1] == b"official"
    def corrupt(_installation, names, destination, **kwargs):
        stage = destination.parent / "diagnostics"
        put(stage / "files", names[0], b"tampered")
        put(stage, "result.json", json.dumps({"files": [{"path": names[0], "bytes": 8, "sha256": "0" * 64}], "missing": []}))
        raise SC2Error("CASC_ASSET_MISSING", "optional missing", diagnostics=str(stage))
    monkeypatch.setattr(sources.casc, "extract_casc", corrupt)
    with pytest.raises(SC2Error) as error:
        sources._read_casc_batch(tmp_path / "install", "Mods/A.SC2Mod", ["DocumentInfo"], tmp_path / "cache", build)
    assert error.value.code == "CASC_OUTPUT_INVALID"
