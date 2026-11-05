import pytest

from copy import deepcopy

from sc2_mcp.catalog import _Library, trace_references
from sc2_mcp.catalog_explain import catalog_explain
from sc2_mcp.catalog_impact import inspect_patch_impact


def component(root, rows):
    path = root / "Base.SC2Data/GameData/ActorData.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<Catalog>" + rows + "</Catalog>", encoding="utf-8")
    return root


@pytest.fixture
def roots(tmp_path):
    # Model fields and Behavior default transcribed from Core ActorData / EffectData.
    base = component(tmp_path / "base", '''
      <CActorAction default="1" id="GenericAttackBase">
        <LaunchAssets Model="##id##Launch"/>
        <ImpactMap index="None" Model="##id##Impact"/>
        <LaunchModel value="GenericAttackLaunchModel"/>
      </CActorAction>
      <CModel id="FooLaunch"/><CModel id="FooImpact"/><CModel id="Fixed"/>
      <CModel id="GenericAttackLaunchModel"/><CActorModel id="GenericAttackLaunchModel"/>
      <CActorAction id="Foo" parent="GenericAttackBase"/>
      <CEffectApplyBehavior default="1"><Behavior value="##id##"/></CEffectApplyBehavior>
      <CBehaviorBuff id="Foo"/><CBehaviorBuff id="Bar"/>
      <CEffectApplyBehavior id="Foo"/>
    ''')
    local = component(tmp_path / "local", '<CActorAction id="Foo"><ImpactMap index="None" Sound="Bang"/></CActorAction>')
    return [base, local]


def test_effective_links_forward_back_and_explanation(roots):
    for kind, field, target_kind, ident, raw in [
        ("Actor", "LaunchAssets.Model", "Model", "FooLaunch", "##id##Launch"),
        ("Actor", "ImpactMap[None].Model", "Model", "FooImpact", "##id##Impact"),
        ("Actor", "LaunchModel", "Actor", "GenericAttackLaunchModel", "GenericAttackLaunchModel"),
        ("Effect", "Behavior", "Behavior", "Foo", "##id##"),
    ]:
        explanation = catalog_explain(roots, kind, "Foo", [field])["fields"][field]
        assert explanation["static"]["value"] == raw
        link = explanation["reference"]
        assert (link["status"], link["catalog"], link["object_id"]) == ("resolved", target_kind, ident)
        edges = [e for e in trace_references(roots, kind, "Foo")["outgoing"] if e["field"] == field]
        assert len(edges) == 1 and edges[0]["reference"] == link
        assert edges[0] in trace_references(roots, target_kind, ident)["incoming"]


def test_overrides_and_impact(roots):
    before = _Library(roots)
    component(roots[-1], '''
      <CEffectApplyBehavior id="Base"><Behavior value="Bar"/></CEffectApplyBehavior>
      <CEffectApplyBehavior id="Foo" parent="Base"/>
      <CActorAction id="FixedBase" parent="GenericAttackBase"><ImpactMap index="None" Model="Fixed"/></CActorAction>
      <CActorAction id="Foo" parent="FixedBase"/>
    ''')
    result = inspect_patch_impact(before, _Library(roots), [{"catalog":"Effect","object_id":"Foo"}], {})
    for direction, expected in [("added", "Bar"), ("removed", "Foo")]:
        assert any(e["from"] == {"catalog":"Effect","object_id":"Foo"} and e["to"] == {"catalog":"Behavior","object_id":expected}
                   for e in result["reference_changes"][direction])
    for child, expected, source in [("", "Fixed", "FixedBase"), ('<ImpactMap index="None" Model="FooLaunch"/>', "FooLaunch", "Foo")]:
        extra = component(roots[-1].parent / "overlay", '<CActorAction id="Foo">' + child + '</CActorAction>')
        link = catalog_explain([*roots, extra], "Actor", "Foo", ["ImpactMap[None].Model"])["fields"]["ImpactMap[None].Model"]["reference"]
        assert (link["object_id"], link["source"]["object_id"]) == (expected, source)


def test_empty_removed_optional_and_unknown(roots):
    component(roots[-1], '''
      <CActorAction id="Foo"><LaunchAssets Model=""/><ImpactMap index="None" removed="1"/></CActorAction>
      <CActorAction id="Unused" parent="GenericAttackBase"/>
      <CEffectApplyBehavior id="Foo"><Behavior value="##other##"/></CEffectApplyBehavior>
      <CEffectApplyBehavior id="MissingParent" parent="Absent"/>
      <CEffectApplyBehavior id="Broken"><Behavior value="InactiveOnly"/></CEffectApplyBehavior>
    ''')
    component(roots[-1].parent / "inactive", '<CBehaviorBuff id="InactiveOnly"/>')
    for kind, owner, field, status in [
        ("Actor", "Foo", "LaunchAssets.Model", "cleared"), ("Actor", "Foo", "ImpactMap[None].Model", "removed"),
        ("Actor", "Unused", "LaunchAssets.Model", "optional_default_absent"),
        ("Effect", "Foo", "Behavior", "unknown"), ("Effect", "MissingParent", "Behavior", "unknown"),
        ("Effect", "Broken", "Behavior", "missing_in_roots"),
    ]:
        assert catalog_explain(roots, kind, owner, [field])["fields"][field]["reference"]["status"] == status
    assert not trace_references(roots, "Actor", "Unused")["missing"]
    assert trace_references(roots, "Effect", "Broken")["missing"][0]["to"]["object_id"] == "InactiveOnly"
    assert not trace_references(roots, "Effect", "Broken", dependencies_complete=False)["missing"]


def test_explicit_effect_clear_and_unknown_input_never_create_edges(roots):
    component(roots[-1], '''
      <CEffectApplyBehavior id="Foo"><Behavior value=""/></CEffectApplyBehavior>
      <CActorAction id="Foo"><LaunchAssets Model="##custom##Launch"/></CActorAction>
    ''')
    assert not trace_references(roots, "Behavior", "Foo")["incoming"]
    explanation = catalog_explain(roots, "Effect", "Foo", ["Behavior"])["fields"]["Behavior"]
    assert [row["value"] for row in explanation["provenance"]] == ["##id##", ""]
    assert explanation["reference"]["status"] == "cleared"
    trace = trace_references(roots, "Actor", "Foo")
    assert not any(e["field"] == "LaunchAssets.Model" for e in trace["missing"] + trace["outgoing"])
    assert any(w.get("reference", {}).get("reason") == "unsupported_token" for w in trace["warnings"])

def test_explanation_with_references_matches_independent_queries(roots):
    joined = catalog_explain(roots, "Effect", "Foo", ["Behavior"], include_references=True)
    assert joined.pop("references") == trace_references(roots, "Effect", "Foo")
    assert joined == catalog_explain(roots, "Effect", "Foo", ["Behavior"])


def _reference_fixture(tmp_path):
    # Defaults, inherited parent, missing parent, real class change (Unit ->
    # ActorAction) and global merge warnings (text/expression) in one fixture.
    base = component(tmp_path / "base", '''
      <CActorAction default="1" id="GraphDefault">
        <LaunchAssets Model="##id##Launch"/>
        <ImpactMap index="None" Model="##id##Impact"/>
      </CActorAction>
      <CModel id="FooLaunch"/><CModel id="FooImpact"/>
      <CActorAction id="Foo" parent="GraphDefault"/>
      <CActorUnit id="Changed"/>
      <CEffectApplyBehavior id="MissingParent" parent="Absent"><Behavior value="Foo"/></CEffectApplyBehavior>
      <CBehaviorBuff id="Foo"/>
    ''')
    component(tmp_path / "local", '''
      <CActorAction id="Changed" parent="Foo"/>
      <CActorAction id="Noisy"><ImpactMap index="None">ignored</ImpactMap></CActorAction>
    ''')
    return [base, tmp_path / "local"]


def test_reference_graph_matches_old_deepcopy_and_rescan_semantics(tmp_path, monkeypatch):
    """Compare the patched graph with the pre-patch warning semantics.

    Old inspect deep-copied global warnings *before* merging; the wrapper instead
    runs the current (shallow, append-only) inspect and deep-copies the result
    warnings *after* merging. _effective/_merge/_effective_link only append new
    warning dicts, so the post-copy values equal the old pre-copy values; the
    wrapper only restores the old deepcopy and per-field warning scan.
    """
    import sc2_mcp.catalog as catalog
    roots = _reference_fixture(tmp_path)

    def graph_with_old_semantics(complete):
        original_inspect = catalog._Library.inspect
        original_link = catalog._effective_link

        def old_inspect(self, *args, **kwargs):
            result = original_inspect(self, *args, **kwargs)
            result["warnings"] = deepcopy(result["warnings"])
            return result

        def old_link(*args, **kwargs):
            # Force the pre-patch per-field owner-warning scan.
            kwargs.pop("inheritance_incomplete", None)
            return original_link(*args, **kwargs)

        library = catalog._Library(roots)
        library.warnings.extend({"code": "bulk_global", "n": index} for index in range(500))
        before = deepcopy(library.warnings)
        with monkeypatch.context() as scope:
            scope.setattr(catalog._Library, "inspect", old_inspect)
            scope.setattr(catalog, "_effective_link", old_link)
            result = catalog.reference_graph(library, complete)
        assert library.warnings == before
        return result, before

    for complete in (True, False):
        baseline, baseline_warnings = graph_with_old_semantics(complete)
        library = catalog._Library(roots)
        library.warnings.extend({"code": "bulk_global", "n": index} for index in range(500))
        assert catalog.reference_graph(library, complete) == baseline
        assert library.warnings == baseline_warnings
    edges, missing, warnings = graph_with_old_semantics(True)[0]
    for owner in ("MissingParent", "Changed"):
        assert any(w["code"] == "catalog_link_unknown" and w.get("object_id") == owner
                   and w.get("reference", {}).get("reason") == "inheritance_incomplete" for w in warnings)
    assert any(edge["from"]["object_id"] == "Foo" and edge.get("reference", {}).get("status") == "resolved"
               for edge in edges)


def test_owner_edges_warning_slice_and_public_inspect_isolation(tmp_path):
    import sc2_mcp.catalog as catalog
    library = catalog._Library(_reference_fixture(tmp_path))
    library.warnings.extend({"code": "bulk_global", "n": index} for index in range(500))
    before = deepcopy(library.warnings)
    *_, appended = catalog._owner_edges(library, ("Effect", "MissingParent"), catalog._id_index(library), True,
                                        include_warnings=True)
    assert appended == [{"code": "missing_catalog_parent", "object_id": "MissingParent", "parent": "Absent"}]
    assert library.warnings == before
    result = library.inspect("Effect", "MissingParent")
    result["warnings"][0]["mutated"] = True
    result["warnings"].append({"code": "external"})
    assert library.warnings == before
