import hashlib
import os
import re

import pytest

from sc2_mcp import reference_index
from sc2_mcp.catalog import trace_references
from sc2_mcp.errors import SC2Error
from sc2_mcp.service import Service


def test_current_references_publish_context_only_after_final_verification(tmp_path, monkeypatch):
    root = tmp_path / "Pending.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    (data / "UnitData.xml").write_text('<Catalog><CUnit id="Marine"/></Catalog>')
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root))["project_id"]
        def reject(context):
            raise SC2Error("source_context_stale", "changed during query")
        with monkeypatch.context() as patch:
            patch.setattr(reference_index, "assert_source_context_current", reject)
            with pytest.raises(SC2Error) as error:
                reference_index.query(service, pid, "Unit", "Marine", None, "full")
        assert error.value.code == "source_context_stale"
        assert not list((service.state / "source-contexts").glob("*.json"))
        result = reference_index.query(service, pid, "Unit", "Marine", None, "full")
        assert result["index_status"] == "refreshed"
        context = service.source_context(pid, result["source_context_id"])
        assert context["root"] == str(root.resolve())
    finally:
        service.jobs.shutdown()


def test_same_file_edit_rebinds_all_sources_and_skips_unchanged_declarations(
    tmp_path, monkeypatch
):
    root = tmp_path / "Many.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    (data / "BehaviorData.xml").write_text(
        '<Catalog><CBehaviorBuff id="Bar"/><CBehaviorBuff id="Baz"/></Catalog>'
    )
    effects = data / "EffectData.xml"
    xml = (
        "<Catalog>"
        + "".join(
            f'<CEffectApplyBehavior id="E{i}"><Behavior value="Bar"/></CEffectApplyBehavior>'
            for i in range(128)
        )
        + "</Catalog>"
    )
    effects.write_text(xml)
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root), writable=True)["project_id"]
        monkeypatch.setattr(service, "editor_conflict", lambda: None)

        def query(identifier, context=None):
            return reference_index.query(
                service, pid, "Behavior", identifier, context, "full"
            )

        first = query("Bar")
        candidate = service.edit(
            pid,
            "catalog_set",
            {
                "catalog": "Effect",
                "object_id": "E1",
                "field_path": "Behavior",
                "expected": "Bar",
                "value": "Baz",
            },
            preview_only=True,
        )
        stamp = effects.stat()
        xml = xml.replace('value="Bar"', 'value="Baz"', 1)
        effects.write_text(xml)
        os.utime(effects, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with pytest.raises(SC2Error) as stale:
            query("Bar", first["source_context_id"])
        assert stale.value.code == "source_context_stale"
        changed = query("Baz")
        with pytest.raises(SC2Error) as rejected:
            service.apply_candidate(pid, candidate["change_id"])
        assert rejected.value.code in {"source_context_stale", "baseline_conflict"}
        assert effects.read_text() == xml
        assert changed["recomputed_objects"] == 1
        assert [edge["from"]["object_id"] for edge in changed["incoming"]] == ["E0"]
        service.jobs.shutdown()
        service = Service(tmp_path / "state")
        unchanged = query("Bar")
        assert len(unchanged["incoming"]) == 127
        assert unchanged["index_status"] == "hit"
        for identifier in ["Bar", "Baz"]:
            result = query(identifier)
            assert all(
                result[k] == v
                for k, v in trace_references([root], "Behavior", identifier).items()
            )

        effects.write_text(xml.replace("><", ">\n  <"))
        refreshed = query("Bar")
        assert refreshed["recomputed_objects"] == 0
        assert refreshed["source_context_id"] != unchanged["source_context_id"]
        assert {e["source"]["sha256"] for e in refreshed["incoming"]} == {
            hashlib.sha256(effects.read_bytes()).hexdigest()
        }
    finally:
        service.jobs.shutdown()


def test_default_array_override_and_reused_diagnostics_match_full_scan(tmp_path):
    root = tmp_path / "Parents.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    actors = data / "ActorData.xml"
    actors.write_text(
        '<Catalog><CActorAction default="1"><ImpactMap index="None" Model="##id##Impact"/></CActorAction>'
        '<CActorAction id="Base"/><CActorAction id="Child" parent="Base"/>'
        '<CActorAction id="Override" parent="Base"><ImpactMap index="None" Model="Fixed"/></CActorAction>'
        '<CActorAction id="Missing"><LaunchModel value="Ghost"/></CActorAction>'
        '<CActorAction id="Unknown"><LaunchModel value="$unknown"/></CActorAction></Catalog>'
    )
    models = data / "ModelData.xml"
    models.write_text(
        '<Catalog><CModel id="ChildImpact"/><CModel id="Fixed"/></Catalog>'
    )
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root))["project_id"]

        def check(kind, obj):
            actual = reference_index.query(service, pid, kind, obj, None, "full")
            oracle = trace_references([root], kind, obj)
            assert all(actual[k] == v for k, v in oracle.items())
            return actual

        check("Model", "ChildImpact")
        actors.write_text(
            actors.read_text().replace(
                'id="Base"/>',
                'id="Base"><ImpactMap index="None" Model="Fixed"/></CActorAction>',
            )
        )
        assert check("Model", "Fixed")["recomputed_objects"] == 3
        assert check("Actor", "Missing")["missing"]
        assert check("Actor", "Unknown")["warnings"]
        actors.write_text(
            actors.read_text().replace('Model="##id##Impact"', 'Model="###unknown"')
        )
        check("Actor", "Unknown")
        models.write_text(models.read_text().replace('id="Fixed"', 'id="Renamed"'))
        assert check("Actor", "Override")["missing"]
        actors.write_text(
            actors.read_text().replace(
                'index="None" Model="Fixed"', 'index="None" removed="1"'
            )
        )
        assert not check("Actor", "Override")["missing"]
    finally:
        service.jobs.shutdown()


def test_hot_refresh_restart_and_atomic_stale_rejection(tmp_path, monkeypatch):
    root = tmp_path / "map.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    effects = data / "EffectData.xml"
    effects.write_text(
        '<Catalog><CEffectApplyBehavior id="Foo"><Behavior value="Bar"/></CEffectApplyBehavior><CEffectApplyBehavior id="Child" parent="Foo"/></Catalog>'
    )
    behaviors = data / "BehaviorData.xml"
    behaviors.write_text(
        '<Catalog><CBehaviorBuff id="Bar"/><CBehaviorBuff id="Baz"/></Catalog>'
    )
    (data / "UnitData.xml").write_text('<Catalog><CUnit id="Marine"/></Catalog>')
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root))["project_id"]

        def query(ident, mode="full", ctx=None):
            return reference_index.query(service, pid, "Behavior", ident, ctx, mode)

        cold = query("Bar", "direct")
        assert {e["from"]["object_id"] for e in cold["incoming"]} == {"Foo", "Child"}
        first = query("Bar")
        expected = trace_references([root], "Behavior", "Bar")
        assert all(first[k] == v for k, v in expected.items())
        service.jobs.shutdown()
        service = Service(tmp_path / "state")
        assert query("Bar", "direct")["index_status"] == "hit"
        effects.write_bytes(
            effects.read_bytes().replace(b'value="Bar"', b'value="Baz"')
        )
        with pytest.raises(SC2Error) as stale:
            query("Bar", ctx=first["source_context_id"])
        assert stale.value.code == "source_context_stale"
        from sc2_mcp import catalog as catalog_module

        parsed = []
        original_xml = catalog_module._xml

        def recording_xml(path):
            parsed.append(path)
            return original_xml(path)

        with monkeypatch.context() as patch:
            patch.setattr(catalog_module, "_xml", recording_xml)
            refreshed = query("Baz")
        assert parsed == [effects.resolve()]
        assert refreshed["recomputed_objects"] == 2
        assert (
            refreshed["incoming"]
            == trace_references([root], "Behavior", "Baz")["incoming"]
        )
        assert not query("Bar", "direct")["incoming"]
        effects.write_bytes(
            effects.read_bytes().replace(b'value="Baz"', b'value="Bar"')
        )
        verify = reference_index.assert_source_context_current
        calls = []

        def racing(ctx):
            if not calls:
                effects.write_bytes(
                    effects.read_bytes().replace(b'value="Bar"', b'value="Baz"')
                )
            calls.append(1)
            return verify(ctx)

        monkeypatch.setattr(reference_index, "assert_source_context_current", racing)
        assert query("Baz")["incoming"] == refreshed["incoming"]
        assert len(calls) == 2
        behaviors.write_text('<Catalog><CBehaviorBuff id="Bar"/></Catalog>')
        reference_index.query(service, pid, "Effect", "Foo", None, "full")
        restored = (
            '<Catalog><CBehaviorBuff id="Bar"/><CBehaviorBuff id="Baz"/></Catalog>'
        )
        behaviors.write_text(restored)
        assert (
            query("Baz")["incoming"]
            == trace_references([root], "Behavior", "Baz")["incoming"]
        )
        effects.write_text(
            effects.read_text().replace('parent="Foo"', 'parent="Other"')
        )
        assert {edge["from"]["object_id"] for edge in query("Baz")["incoming"]} == {
            "Foo"
        }

        def save_again(ctx):
            effects.write_bytes(effects.read_bytes() + b" ")
            return verify(ctx)

        with monkeypatch.context() as patch:
            patch.setattr(reference_index, "assert_source_context_current", save_again)
            with pytest.raises(SC2Error) as changing:
                query("Baz")
            assert changing.value.code == "source_context_stale"
        assert (
            query("Baz")["incoming"]
            == trace_references([root], "Behavior", "Baz")["incoming"]
        )
    finally:
        service.jobs.shutdown()


def test_direct_matches_full_for_inherited_id_and_budget(tmp_path, monkeypatch):
    root = tmp_path / "map.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    (data / "ActorData.xml").write_text(
        '<Catalog><CActorAction id="Base"><ImpactMap index="None" Model="##id##Impact"/></CActorAction><CActorAction id="Foo" parent="Base"><ImpactMap index="None" Sound="Bang"/></CActorAction></Catalog>'
    )
    (data / "ModelData.xml").write_text('<Catalog><CModel id="FooImpact"/></Catalog>')
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root))["project_id"]
        legacy = trace_references([root], "Model", "FooImpact")
        assert len(legacy["incoming"]) == 1
        for mode in ("direct", "full", "direct"):
            result = reference_index.query(
                service, pid, "Model", "FooImpact", None, mode
            )
            assert result["incoming"] == legacy["incoming"]
        monkeypatch.setattr(reference_index, "BUDGET", 1024)
        result = reference_index.query(
            service, pid, "Model", "FooImpact", None, "direct"
        )
        assert result["index_status"].startswith("uncached")
        assert result["incoming"] == legacy["incoming"]
    finally:
        service.jobs.shutdown()


def test_requirement_node_index_version_retires_same_generation_cache(
    tmp_path, monkeypatch
):
    from sc2_mcp import catalog as catalog_module

    root = tmp_path / "map.SC2Map"
    data = root / "Base.SC2Data/GameData"
    data.mkdir(parents=True)
    (root / "DocumentInfo").write_text("<DocInfo/>")
    requirements = data / "RequirementData.xml"
    requirements.write_text(
        '<Catalog><CRequirement id="Req"><NodeArray index="Use" Link="UpNode"/>'
        '<NodeArray index="Show" Link="AbsentNode"/></CRequirement></Catalog>'
    )
    nodes = data / "RequirementNodeData.xml"
    nodes.write_text(
        '<Catalog><CRequirementCountUpgrade id="UpNode">'
        '<Count Link="TestUpgrade" State="CompleteOnly"/></CRequirementCountUpgrade></Catalog>'
    )
    upgrades = data / "UpgradeData.xml"
    upgrades.write_text('<Catalog><CUpgrade id="TestUpgrade"/></Catalog>')
    source_bytes = {
        path: path.read_bytes() for path in (requirements, nodes, upgrades)
    }
    service = Service(tmp_path / "state")
    try:
        pid = service.projects.open(str(root))["project_id"]

        def query():
            return reference_index.query(service, pid, "Requirement", "Req", None, "full")

        def targets(rows):
            return {(row["catalog"], row["object_id"]) for row in rows}

        # Pre-fix mapping (every CRequirement* tag was a Requirement) plus the
        # pre-fix exact-slot rule, building a real on-disk v4 index from the
        # unchanged sources.
        old_type_catalog = catalog_module._type_catalog
        old_reference_kind = catalog_module._reference_kind

        def legacy_type_catalog(tag):
            if tag.startswith("CRequirement"):
                return "Requirement"
            return old_type_catalog(tag)

        def legacy_reference_kind(path, owner_class):
            tags = [re.sub(r"\[[^\]]*\]", "", part) for part in path.split(".")]
            if (
                owner_class == "CRequirement"
                and tags[-1] == "Link"
                and len(tags) >= 2
                and tags[-2] == "NodeArray"
            ):
                return None
            return old_reference_kind(path, owner_class)

        with monkeypatch.context() as patch:
            patch.setattr(catalog_module, "_type_catalog", legacy_type_catalog)
            patch.setattr(catalog_module, "_reference_kind", legacy_reference_kind)
            patch.setattr(reference_index, "INDEX_VERSION", "4")
            stale = query()
        assert ("Requirement", "UpNode") in targets(stale["reachable"])
        assert ("RequirementNode", "UpNode") not in targets(stale["reachable"])
        assert stale["missing"] == []
        generation = stale["source_context_id"]

        # A real tool upgrade starts a fresh process, so the in-memory library
        # built under the old rules must not be reused. _query_index is a
        # process-level Service attribute that __init__ never clears, so reset
        # it as a new process would. Restart on the same state directory and
        # project record, leaving graph.sqlite, source_contexts and the sources
        # untouched; this simulates an upgrade restart, not hot reload.
        service.jobs.shutdown()
        monkeypatch.setattr(Service, "_query_index", None)
        service = Service(tmp_path / "state")

        # Unchanged bytes and the same source_context: only the index version
        # may retire the stale rows.
        refreshed = query()
        assert refreshed["index_status"] == "refreshed"
        assert refreshed["source_context_id"] == generation
        assert ("RequirementNode", "UpNode") in targets(refreshed["reachable"])
        assert (
            {(edge["to"]["catalog"], edge["to"]["object_id"]) for edge in refreshed["missing"]}
            == {("RequirementNode", "AbsentNode")}
        )
        oracle = trace_references([root], "Requirement", "Req")
        assert all(refreshed[k] == v for k, v in oracle.items())
        hit = query()
        assert hit["index_status"] == "hit"
        assert all(hit[k] == v for k, v in oracle.items())
        assert {path: path.read_bytes() for path in source_bytes} == source_bytes
    finally:
        service.jobs.shutdown()
