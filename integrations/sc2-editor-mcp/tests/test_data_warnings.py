import json
from pathlib import Path

from sc2_mcp.data_warnings import inspect_data_warnings, plan_warning_repairs


def put(root: Path, relative: str, content: str | bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)


def test_parse_local_dependency_and_user_warnings(tmp_path):
    actor = """<Catalog>
    <CActorUnit id="ScientistNarud" parent="GenericUnitStandard">
        <Model value="DrNarud"/>
        <BuildModel value="DrNarud"/>
        <PlacementModel value="DrNarud"/>
    </CActorUnit>
    <CActorModel id="ViperDeathRagdollSimulant">
        <Model value="Viper"/>
        <BuildModel value="Viper"/>
        <PlacementModel value="Viper"/>
    </CActorModel>
    <CActorUnit id="KSCG2Mothership">
        <On Terms="" Send=""/>
    </CActorUnit>
    </Catalog>"""
    put(tmp_path, "Base.SC2Data/GameData/ActorData.xml", actor)
    put(tmp_path, "Objects", "<PlacedObjects><Object id=\"1a8\" name=\"Aiur_Fireflies\"/></PlacedObjects>")
    log = f"""[10/27/2026 4:25:14 上午] 警告: XML: {tmp_path.as_posix()}/Base.SC2Data/GameData/ActorData.xml(4,9) : Unable to find field ModelBuild  Source: E:/{tmp_path.name}/  Entry: ScientistNarud  Scope: CActorUnit
[10/27/2026 4:25:14 上午] 警告: XML: GameData\\EffectData.xml(3238,9) : Unable to use index: 8  Source: Mods/VoidMulti.SC2Mod/  Entry: VolatileBurst  Scope: CEffectSet  Field: EffectArray[0]
[10/27/2026 4:25:14 上午] 警告: USER: CActorUnit[KSCG2Mothership] Has event without a triggering message. Event[Terms "" Send ""]
[10/27/2026 4:25:14 上午] 警告: USER: [ 1a8    1] CActorDoodad[Aiur_Fireflies] 
"""
    result = inspect_data_warnings(tmp_path, log_text=log)
    assert result["summary"]["warning_count"] == 4
    assert result["summary"]["sources"]["dependency"] == 1
    narud = next(item for item in result["issues"] if item.get("entry") == "ScientistNarud")
    assert narud["diagnostic"] == "invalid_field_name"
    assert narud["disposition"] == "safe_to_patch"
    assert narud["local_evidence"]["probable_alias"] == "BuildModel"
    dependency = next(item for item in result["issues"] if item.get("entry") == "VolatileBurst")
    assert dependency["disposition"] == "requires_dependency_audit"
    assert next(item for item in result["issues"] if item["kind"] == "doodad_user_warning")["local_evidence"]["objects"]["found"]
    json.dumps(result, ensure_ascii=False)


def test_duplicate_catalog_ids_are_reported_without_selecting_a_winner(tmp_path):
    put(tmp_path, "Base.SC2Data/GameData/UpgradeData.xml", """<Catalog>
    <CUpgrade id="ProtossShieldsLevel1"><AffectedUnitArray value="A"/></CUpgrade>
    <CUpgrade id="ProtossShieldsLevel1"><AffectedUnitArray value="B"/></CUpgrade>
    </Catalog>""")
    log = "[x] 警告: XML: UpgradeData.xml(4,5) : Unable to create duplicate entry ProtossShieldsLevel1  Source: E:/map/  Scope: CUpgrade"
    result = inspect_data_warnings(tmp_path, log_text=log)
    assert len(result["duplicate_definitions"]) == 1
    group = result["duplicate_definitions"][0]
    assert group["object_id"] == "ProtossShieldsLevel1"
    assert group["disposition"] == "requires_reference_audit"
    issue = result["issues"][0]
    assert issue["diagnostic"] == "duplicate_id"
    assert len(issue["local_evidence"]["duplicate_definitions"]) == 1


def test_array_index_evidence_and_input_validation(tmp_path):
    put(tmp_path, "Base.SC2Data/GameData/ActorData.xml", """<Catalog>
    <CActorUnit id="MothershipGolden"><WireframeShield><Image value="A"/><Image value="B"/><Image value="C"/></WireframeShield></CActorUnit>
    </Catalog>""")
    log = "[x] 警告: XML: ActorData.xml(2,13) : Unable to use index: 3  Source: E:/map/  Entry: MothershipGolden  Scope: CActorUnit.SLayerIconShield  Field: WireframeShield.Image[0]"
    result = inspect_data_warnings(tmp_path, log_text=log)
    issue = result["issues"][0]
    assert issue["diagnostic"] == "array_index"
    assert issue["local_evidence"]["local_count"] == 3
    assert issue["local_evidence"]["candidate"]


def test_warning_repair_plan_preserves_unrelated_bytes_and_blocks_inference_by_default(tmp_path):
    actor = """<Catalog>\r
  <CActorUnit id="ScientistNarud">\r
    <Model value="DrNarud"/>\r
    <ModelBuild value="DrNarud"/>\r
    <ModelPlacement value="DrNarud"/>\r
    <!-- preserve this comment -->\r
  </CActorUnit>\r
  <CActorModel id="ViperDeathRagdollSimulant">\r
    <Model value="Viper"/>\r
    <BuildModel value="Viper"/>\r
    <PlacementModel value="Viper"/>\r
  </CActorModel>\r
  <CActorUnit id="MothershipGolden">\r
    <WireframeShield>\r
      <Image value="A"/>\r
      <Image value="B"/>\r
      <Image value="C"/>\r
    </WireframeShield>\r
  </CActorUnit>\r
</Catalog>\r
"""
    put(tmp_path, "Base.SC2Data/GameData/ActorData.xml", actor)
    source = (tmp_path / "Base.SC2Data/GameData/ActorData.xml").read_bytes()
    actor_path = (tmp_path / "Base.SC2Data/GameData/ActorData.xml").as_posix()
    log = f"""[x] 警告: XML: {actor_path}(4,5) : Unable to find field ModelBuild  Source: E:/map/  Entry: ScientistNarud  Scope: CActorUnit\n[x] 警告: XML: {actor_path}(5,5) : Unable to find field ModelPlacement  Source: E:/map/  Entry: ScientistNarud  Scope: CActorUnit\n[x] 警告: XML: {actor_path}(8,5) : Unable to find field BuildModel  Source: {tmp_path.as_posix()}/  Entry: ViperDeathRagdollSimulant  Scope: CActorModel\n[x] 警告: XML: {actor_path}(9,5) : Unable to find field PlacementModel  Source: {tmp_path.as_posix()}/  Entry: ViperDeathRagdollSimulant  Scope: CActorModel\n[x] 警告: XML: {actor_path}(13,7) : Unable to use index: 3  Source: {tmp_path.as_posix()}/  Entry: MothershipGolden  Scope: CActorUnit.SLayerIconShield  Field: WireframeShield.Image[0]\n"""

    exact = plan_warning_repairs(tmp_path, log_text=log)
    assert exact["changes"] == {"Base.SC2Data/GameData/ActorData.xml": exact["changes"]["Base.SC2Data/GameData/ActorData.xml"]}
    exact_bytes = exact["changes"]["Base.SC2Data/GameData/ActorData.xml"]
    assert b"<BuildModel value=\"DrNarud\"/>" in exact_bytes
    assert b"<PlacementModel value=\"DrNarud\"/>" in exact_bytes
    assert b"<ModelBuild value=\"DrNarud\"/>" not in exact_bytes
    assert b"<ModelPlacement value=\"DrNarud\"/>" not in exact_bytes
    assert b"<BuildModel value=\"Viper\"/>" in exact_bytes
    assert b'<Image value="A"/>' in exact_bytes
    assert (tmp_path / "Base.SC2Data/GameData/ActorData.xml").read_bytes() == source
    assert any("CActorModel" in item["reason"] or "include_inferred" in item["reason"] for item in exact["blocked"])

    inferred = plan_warning_repairs(tmp_path, log_text=log, include_inferred=True)
    inferred_bytes = inferred["changes"]["Base.SC2Data/GameData/ActorData.xml"]
    assert b"<BuildModel value=\"Viper\"/>" not in inferred_bytes
    assert b"<PlacementModel value=\"Viper\"/>" not in inferred_bytes
    assert b'<Image index="0" value="A"/>' in inferred_bytes
    assert b'<Image index="1" value="B"/>' in inferred_bytes
    assert b'<Image index="2" value="C"/>' in inferred_bytes
    assert b"<!-- preserve this comment -->" in inferred_bytes
    assert inferred["report"]["changes"][0]["baseline_sha256"]

