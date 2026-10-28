import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.catalog import CatalogSession
from sc2_mcp.errors import SC2Error
from sc2_mcp.unit_variant import audit_unit_variant, plan_unit_variant, plan_unit_variant_report, summarize_runtime_weapons


def put(root, kind, xml):
    path = root / "Base.SC2Data/GameData" / (kind + "Data.xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(('<?xml version="1.0" encoding="utf-8"?>\r\n<Catalog>\r\n' + xml + '\r\n</Catalog>\r\n').encode())
    return path


@pytest.fixture
def fixture(tmp_path):
    dep, root = tmp_path / "dep", tmp_path / "map"
    root.mkdir()
    put(dep, "Unit", '''<CUnit id="Marauder"><LifeMax value="125"/><WeaponArray index="0" Link="PunisherGrenades"/><AbilArray Link="Stimpack"/><AbilArray Link="attack"/></CUnit><CUnit id="PunisherGrenadesLMWeapon"/>''')
    put(dep, "Weapon", '<CWeaponLegacy id="PunisherGrenades"><Effect value="PunisherGrenadesLM"/><Range value="6"/></CWeaponLegacy>')
    put(dep, "Effect", '<CEffectLaunchMissile id="PunisherGrenadesLM"><ImpactEffect value="PunisherGrenadesSet"/><AmmoUnit value="PunisherGrenadesLMWeapon"/></CEffectLaunchMissile><CEffectSet id="PunisherGrenadesSet"><EffectArray value="PunisherGrenadesU"/></CEffectSet><CEffectDamage id="PunisherGrenadesU"><Amount value="10"/></CEffectDamage>')
    put(dep, "Actor", '<CActorUnit id="Marauder" unitName="Marauder"><Model value="Marauder"/></CActorUnit><CActorUnit id="GenericUnitStandardNoAutoSoundLinks"><On Terms="UnitBirth.##unitName##" Send="Create"/></CActorUnit><CActorAction id="MarauderAttackBase"/><CActorModel id="AddonDiscard"><On Terms="UnitDeath.Marauder" Send="Destroy"/></CActorModel>')
    put(dep, "Model", ''.join(f'<CModel id="{i}"/>' for i in ['Marauder', 'MarineWarfield', 'WarfieldPortrait', 'TerranSmallUnitDeathLow', 'MarauderUpgradedAttackImpact', 'MarauderAttackLaunch']))
    put(dep, "Validator", '<CValidator id="PunisherGrenadesResearched"/>')
    put(dep, "AttachMethod", '<CAttachMethod id="AMFilterWeapon"/>')
    put(dep, "Sound", ''.join(f'<CSound id="{i}"/>' for i in ['Raynor_Explode', 'Marauder_Yes', 'Marauder_Attack']))
    put(dep, "Abil", '<CAbilEffectInstant id="Stimpack"/><CAbilAttack id="attack"/><CAbilTrain id="SecretHangar"><InfoArray><Unit value="Marauder"/></InfoArray></CAbilTrain>')
    put(dep, "Upgrade", '''<CUpgrade id="ArmorParent" default="1"><EffectArray Reference="Unit,Marauder,LifeArmor" Operation="Add" Value="1"/><EffectArray Reference="Effect,PunisherGrenadesU,Amount" Operation="Add" Value="1"/></CUpgrade><CUpgrade id="Armor1" parent="ArmorParent"><EffectArray Reference="Weapon,PunisherGrenades,Range" Operation="Add" Value="1"/><EffectArray Reference="Actor,Marauder,BarWidth" Operation="Set" Value="60"/><AffectedUnitArray value="Marauder"/></CUpgrade><CUpgrade id="Armor2" parent="Armor1"/>''')
    put(root, "Unit", '<!-- keep source bytes -->\r\n<CUnit id="Unrelated"><LifeMax value="99"/></CUnit>')
    put(root, "Upgrade", '<!-- untouched comment -->\r\n<CUpgrade id="Armor2" parent="Armor1"><Name value="Upgrade/Name/Armor2"/></CUpgrade>')
    (root / "MapScript.galaxy").write_bytes(b'void Init(){ string u = "Marauder"; }\r\n')
    loc = root / "zhCN.SC2Data/LocalizedData/GameStrings.txt"
    loc.parent.mkdir(parents=True)
    loc.write_bytes('Old/Name=原文\r\n'.encode())
    return dep, root


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def test_plan_complete_chain_and_leaf_upgrades_no_shared_damage_duplication(fixture):
    dep, root = fixture
    before = hashes(root)
    r = plan_unit_variant_report(root, [dep, root], "Marauder", "TestWarfield")
    changes = r["changes"]
    assert len(changes) == 7 and hashes(root) == before
    assert r["upgrade_count"] == 1  # Armor2 is the concrete leaf, parents unchanged.
    assert r["upgrade_field_count"] == 4
    for rel, data in changes.items():
        assert b'\xef\xbb\xbf' not in data and b'\0' not in data
        if (root / rel).is_file():
            assert b'\n' not in data.replace(b'\r\n', b'')
        if rel.endswith('.xml'):
            ET.fromstring(data)
    upgrades = changes['Base.SC2Data/GameData/UpgradeData.xml']
    assert b'Unit,TestWarfield,LifeArmor' in upgrades
    assert b'Weapon,TestWarfieldWeapon,Range' in upgrades
    assert b'Actor,TestWarfield,BarWidth' in upgrades
    assert b'Effect,PunisherGrenadesU,Amount' not in upgrades
    assert b'<!-- untouched comment -->' in upgrades
    assert b'<Name value="Upgrade/Name/Armor2"/>' in upgrades
    assert b'<CUpgrade id="ArmorParent"' not in upgrades
    effect = changes['Base.SC2Data/GameData/EffectData.xml']
    assert b'parent="PunisherGrenadesLM"' in effect and b'ImpactEffect value="PunisherGrenadesSet"' in effect
    actor = changes['Base.SC2Data/GameData/ActorData.xml']
    assert b'unitName="TestWarfield"' in actor
    assert actor.count(b'LaunchAttachQuery Methods="AMFilterWeapon"') == 2
    assert b'DeathArray index="Normal" ModelLink="TerranSmallUnitDeathLow"' in actor
    assert 'MapScript.galaxy' not in changes and 'DocumentInfo' not in changes


def test_audit_reverse_events_production_and_runtime_boundary(fixture):
    dep, root = fixture
    report = audit_unit_variant([dep, root], "Marauder", "NewWarfield", model_report={"status": "supported_metadata", "weapon_attachments": ["Ref_Weapon"], "has_death_animation": False})
    assert report['model_checks']['single_weapon_attachment'] is True
    assert report['model_checks']['has_death_animation'] is False
    assert any(i['object_id'] == 'SecretHangar' for i in report['production_and_event_impact'])
    assert any(i['object_id'] == 'AddonDiscard' for i in report['production_and_event_impact'])
    assert report['script_references'] and report['evidence']['runtime'] == 'not_observed'
    assert report['upgrade_count'] == 1 and report['upgrade_field_count'] == 4
    json.dumps(report)


def test_runtime_cache_never_equals_second_attack():
    r = summarize_runtime_weapons([{'slot': 0, 'weapon': 'Warfield', 'enabled': 1}, {'slot': 1, 'weapon': 'PunisherGrenades', 'enabled': 0}])
    assert r['raw_count'] == 2
    assert not r['multiple_enabled_weapons']
    assert len(r['disabled_cache']) == 1
    assert r['duplicate_damage'] == 'not_determined_by_weapon_count'
    r = summarize_runtime_weapons([{'enabled': 'false'}, {}])
    assert len(r['unknown']) == 2


def test_unsupported_or_incomplete_generation_is_explicit(fixture):
    dep, root = fixture
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marine', 'New')
    assert e.value.code == 'unsupported_unit_variant_template'
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New', allowed_gameplay_differences=['LifeMax'])
    assert e.value.code == 'unsupported_variant_gameplay_edit'
    (dep / 'Base.SC2Data/GameData/ValidatorData.xml').unlink()
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert e.value.code == 'variant_source_incomplete'


def test_conflict_new_id_and_baseline_weapon_changed(fixture):
    dep, root = fixture
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'Unrelated')
    assert e.value.code == 'variant_id_conflict'
    path = dep / 'Base.SC2Data/GameData/UnitData.xml'
    path.write_bytes(path.read_bytes().replace(b'Link="PunisherGrenades"', b'Link="OtherWeapon"'))
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert e.value.code == 'unsupported_variant_base_weapons'


def test_missing_parent_and_ambiguous_sources_refuse_generation(fixture):
    dep, root = fixture
    p = dep / 'Base.SC2Data/GameData/UpgradeData.xml'
    p.write_bytes(p.read_bytes().replace(b'parent="Armor1"', b'parent="Missing"'))
    p = root / 'Base.SC2Data/GameData/UpgradeData.xml'
    p.write_bytes(p.read_bytes().replace(b'parent="Armor1"', b'parent="Missing"'))
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert e.value.code == 'variant_source_incomplete'


def test_candidate_roundtrip_preserves_original_objects_and_audits_existing(fixture):
    dep, root = fixture
    changes = plan_unit_variant(root, [dep, root], 'Marauder', 'NewWarfield')
    original = CatalogSession([dep, root]).source_entries('Unit', 'Unrelated')[0]['xml']
    for rel, data in changes.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    session = CatalogSession([dep, root])
    assert session.source_entries('Unit', 'Unrelated')[0]['xml'] == original
    assert session.inspect('Unit', 'NewWarfield')['fields']['LifeMax']['value'] == '125'
    assert session.inspect('Weapon', 'NewWarfieldWeapon')['fields']['Range']['value'] == '6'
    assert session.inspect('Effect', 'NewWarfieldLM')['fields']['ImpactEffect']['value'] == 'PunisherGrenadesSet'
    report = audit_unit_variant([dep, root], 'Marauder', 'NewWarfield')
    assert report['variant_exists']
    assert report['upgrade_count'] == 0
    assert report['referenced_upgrade_count'] == 1
    assert len(report['upgrade_references']) == 4
    assert {v['status'] for v in report['upgrade_references']} == {'present'}
    assert not [v for v in report['gameplay_differences'] if v['classification'] == 'unexpected']
    assert report['chain']['macros']


def test_unrelated_duplicates_preserved_but_relevant_duplicates_rejected(fixture):
    dep, root = fixture
    p = root / 'Base.SC2Data/GameData/UpgradeData.xml'
    raw = p.read_bytes()
    p.write_bytes(raw.replace(b'</Catalog>', b'<CUpgrade id="UnrelatedDup"/><CUpgrade id="UnrelatedDup"/></Catalog>'))
    result = plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert result['Base.SC2Data/GameData/UpgradeData.xml'].count(b'id="UnrelatedDup"') == 2
    p.write_bytes(raw.replace(b'</Catalog>', b'<CUpgrade id="Armor2"/></Catalog>'))
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert e.value.code == 'ambiguous_variant_source'


def test_unsupported_upgrade_removal_is_not_silently_adapted(fixture):
    dep, root = fixture
    p = dep / 'Base.SC2Data/GameData/UpgradeData.xml'
    p.write_bytes(p.read_bytes().replace(b'Reference="Unit,Marauder,LifeArmor"', b'removed="1" Reference="Unit,Marauder,LifeArmor"'))
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [dep, root], 'Marauder', 'New')
    assert e.value.code == 'unsupported_variant_upgrade_removal'
    r = audit_unit_variant([dep, root], 'Marauder', 'New')
    assert r['upgrade_unknown'] and r['evidence']['static'] == 'partial'


def test_source_locale_root_allowed_and_wrong_order_rejected(fixture):
    dep, root = fixture
    locale = root / 'zhCN.SC2Data'
    assert plan_unit_variant(root, [dep, root, locale], 'Marauder', 'New')
    with pytest.raises(SC2Error) as e:
        plan_unit_variant(root, [root, dep], 'Marauder', 'New')
    assert e.value.code == 'variant_root_order'
