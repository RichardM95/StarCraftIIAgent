"""Raw-layer precedence and publication; all targets are isolated fixtures."""
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sc2_mod_layers import build_plan,apply_plan,payload_kind,catalog_rows
from sc2_archive import scan,restore
from sc2_migrate_catalog import Catalog,encode_node
from sc2_migrate_prune import select_overrides


def component(root,name,entries=''):
    p=root/(name+'.SC2Mod');data=p/'Base.SC2Data/GameData';data.mkdir(parents=True)
    if entries:
        (data/'UnitData.xml').write_text('<Catalog>'+entries+'</Catalog>',encoding='utf-8')
    (p/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Void.SC2Mod</Value></Dependencies></DocInfo>')
    (p/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="gada">GameData</DataComponent><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    return p


class LocalLayerTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sc2-layer-test-');self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.low=component(self.root,'Low','<CUnit id="Marine" parent="OfficialParent"><LifeMax value="60"/><AbilArray index="2" removed="1"/></CUnit><CUnit id="OnlyLow"/>')
        self.high=component(self.root,'High','<CUnit id="Marine"><LifeMax value="90"/><AbilArray index="1" removed="1"/></CUnit>')
        self.target=component(self.root,'Target','<CUnit id="Existing"/>')
        for source,value in ((self.low,'low'),(self.high,'high')):
            asset=source/'Assets/UI/icon.dds';asset.parent.mkdir(parents=True);asset.write_text(value)
            strings=source/'zhCN.SC2Data/LocalizedData/GameStrings.txt';strings.parent.mkdir(parents=True)
            strings.write_bytes(b'\xef\xbb\xbf'+('Unit/Name/Marine='+value+'\nUnique/'+value+'='+value+'\n').encode())
            ui=source/'Base.SC2Data/UI/Layout/Test.SC2Layout';ui.parent.mkdir(parents=True);ui.write_text('<Desc/>')
            (source/'Triggers').write_text('<TriggerData/>')
            (source/'Base.SC2Data/LibABC.galaxy').write_text('generated fixture')

    def plan(self):
        return build_plan([self.low,self.high],self.target,self.root/'work')

    def test_local_only_whole_definition_precedence_and_tombstones(self):
        plan=self.plan();stage=Path(plan['stage']);rows,_=catalog_rows(stage)
        node=rows[('Unit','Marine')]['node']
        self.assertEqual(node.find('LifeMax').get('value'),'90')
        self.assertIsNone(node.get('parent'))
        self.assertEqual([(n.get('index'),n.get('removed')) for n in node.findall('AbilArray')],[('1','1')])
        self.assertIn(('Unit','OnlyLow'),rows);self.assertIn(('Unit','Existing'),rows)
        self.assertNotIn(('Unit','OfficialParent'),rows)
        self.assertEqual((stage/'DocumentInfo').read_bytes(),(self.target/'DocumentInfo').read_bytes())
        self.assertFalse(plan['official_dependency_payload_copied'])

    def test_assets_text_priority_and_excluded_wiring(self):
        plan=self.plan();stage=Path(plan['stage'])
        self.assertEqual((stage/'Assets/UI/icon.dds').read_text(),'high')
        text=(stage/'zhCN.SC2Data/LocalizedData/GameStrings.txt').read_text(encoding='utf-8-sig')
        self.assertIn('Unit/Name/Marine=high',text);self.assertIn('Unique/low=low',text)
        self.assertFalse((stage/'Triggers').exists());self.assertFalse((stage/'Base.SC2Data/LibABC.galaxy').exists())
        self.assertFalse((stage/'Base.SC2Data/UI/Layout/Test.SC2Layout').exists())
        self.assertEqual(len(plan['excluded_wiring']),6)

    def test_preview_apply_and_existing_restore(self):
        before=scan(self.target);plan=self.plan();path=self.root/'work/layer-plan.json'
        self.assertFalse(apply_plan(path)['applied']);self.assertEqual(scan(self.target),before)
        result=apply_plan(path,apply=True)
        self.assertTrue(result['applied']);self.assertTrue(Path(result['backup']).is_dir())
        restore(Path(result['backup']),apply=True)
        self.assertEqual(scan(self.target),before)

    def test_inputs_and_stage_changes_block_publication(self):
        plan=self.plan();path=self.root/'work/layer-plan.json'
        (self.high/'Assets/UI/icon.dds').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Input changed'):
            apply_plan(path,apply=True)

    def test_stage_changes_block_publication(self):
        plan=self.plan();path=self.root/'work/layer-plan.json'
        (Path(plan['stage'])/'unplanned').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Staged component changed'):
            apply_plan(path,apply=True)

    def test_failed_publish_rolls_back(self):
        before=scan(self.target);self.plan();path=self.root/'work/layer-plan.json';original=Path.rename
        def fail(path,destination):
            if path.name==self.target.name and '.stage-' in path.parent.name:
                raise OSError('fixture failed publication')
            return original(path,destination)
        with patch.object(Path,'rename',fail):
            with self.assertRaisesRegex(OSError,'fixture failed'):
                apply_plan(path,apply=True)
        self.assertEqual(scan(self.target),before)

    def test_same_source_duplicate_is_not_arbitrarily_ordered(self):
        (self.low/'Base.SC2Data/GameData/Other.xml').write_text('<Catalog><CUnit id="Marine"/></Catalog>')
        with self.assertRaisesRegex(ValueError,'Ambiguous duplicate'):
            self.plan()

    def test_data_assets_with_ui_paths_are_not_treated_as_layout_code(self):
        self.assertEqual(payload_kind('Assets/UI/Icons/test.dds'),'asset')
        self.assertEqual(payload_kind('Base.SC2Data/UI/Layout/Test.SC2Layout'),'wiring')

    def test_official_pruning_uses_inherited_custom_unit_chain_not_identity_tests(self):
        official_xml='''<Catalog>
          <CUnit id="Marine"/><CUnit id="DevilDog"/><CUnit id="Dragoon"/>
          <CUnit id="Parent"><WeaponArray index="0" Link="SharedGun"/></CUnit>
          <CWeapon id="SharedGun"/><CWeapon id="UnrelatedGun"/>
          <CValidatorUnitType id="TypeTest"/>
          <CActorUnit id="CustomActor" unitName="Custom"/>
          <CEffectDamage id="Shot"/>
        </Catalog>'''
        local_xml='''<Catalog>
          <CUnit id="Custom" parent="Parent"><ValidatorArray value="TypeTest"/></CUnit>
          <CUnit id="Marine"/><CUnit id="DevilDog"/><CUnit id="Dragoon"/>
          <CWeapon id="SharedGun"><Effect value="Shot"/></CWeapon>
          <CWeapon id="UnrelatedGun"/>
          <CEffectDamage id="Shot"><Amount value="9"/></CEffectDamage>
          <CValidatorUnitType id="TypeTest"><Value value="Marine"/></CValidatorUnitType>
          <CActorUnit id="CustomActor" unitName="Custom"/>
          <CAbilTrain id="UnrelatedProducer"><InfoArray index="0"><Unit value="DevilDog"/></InfoArray></CAbilTrain>
        </Catalog>'''
        self.assert_pruned(official_xml,local_xml,
                           {'Unit:Marine','Unit:DevilDog','Unit:Dragoon','Weapon:UnrelatedGun'},
                           {'Weapon:SharedGun','Effect:Shot','Validator:TypeTest','Actor:CustomActor'})

    def assert_pruned(self,official_xml,local_xml,expected_removed,expected_kept):
        files=[]
        for source,xml in [('official',official_xml),('local',local_xml)]:
            files.append({'source_id':source,'path':'UnitData.xml','nodes':[encode_node(ET.fromstring(xml))]})
        sources=[{'id':sid,'fingerprint':sid} for sid in ('official','local')]
        cat=Catalog(sources,files)
        official=set(Catalog(sources[:1],files[:1]).objects)
        root=component(self.root,'PruneFixture',local_xml.removeprefix('<Catalog>').removesuffix('</Catalog>'))
        records,_=catalog_rows(root)
        removed,reasons,evidence=select_overrides(records,{'local':cat},{k:'local' for k in records},official)
        self.assertEqual({':'.join(k) for k in removed},expected_removed)
        self.assertTrue(expected_kept <= {':'.join(k) for k in reasons})
        return reasons,evidence

    def test_deleted_array_reference_does_not_keep_an_official_override(self):
        self.assert_pruned('<Catalog><CUnit id="Parent"><WeaponArray index="0" Link="Gun"/></CUnit><CWeapon id="Gun"/></Catalog>',
                           '<Catalog><CUnit id="Custom" parent="Parent"><WeaponArray index="0" removed="1"/></CUnit><CWeapon id="Gun"/></Catalog>',
                           {'Weapon:Gun'},{'Unit:Custom'})

    def test_upgrade_mutation_and_actor_guard_do_not_import_official_units(self):
        self.assert_pruned('<Catalog><CUnit id="Marine"/><CUpgrade id="SharedUpgrade"/></Catalog>',
                           '''<Catalog><CUnit id="Custom"><UpgradeArray Link="SharedUpgrade"/></CUnit>
                           <CUnit id="Marine"/><CUpgrade id="SharedUpgrade"><EffectArray Reference="Unit,Marine,LifeMax" Value="1"/></CUpgrade>
                           <CActorModel id="Presentation"><On Terms="UnitBirth.Custom" Send="Create"/><On Terms="UnitDeath.Marine" Send="Destroy"/></CActorModel></Catalog>''',
                           {'Unit:Marine'},{'Upgrade:SharedUpgrade','Actor:Presentation'})

    def test_regular_train_products_use_official_identity_without_its_local_override(self):
        self.assert_pruned('<Catalog><CUnit id="Dragoon"/><CAbilTrain id="GatewayTrain"/></Catalog>',
                           '''<Catalog><CUnit id="CustomGateway"><AbilArray Link="GatewayTrain"/></CUnit>
                           <CAbilTrain id="GatewayTrain"><InfoArray index="0"><Unit value="Dragoon"/></InfoArray></CAbilTrain>
                           <CUnit id="Dragoon"><ShieldRegenRate value="4"/></CUnit></Catalog>''',
                           {'Unit:Dragoon'},{'Abil:GatewayTrain'})

    def test_shared_actor_events_do_not_own_other_gameplay_sources(self):
        self.assert_pruned('<Catalog><CAbilEffectInstant id="OtherAbility"/></Catalog>',
                           '''<Catalog><CUnit id="Custom"><WeaponArray Link="CustomGun"/></CUnit>
                           <CWeapon id="CustomGun"><Effect value="CustomShot"/></CWeapon><CEffectDamage id="CustomShot"/>
                           <CAbilEffectInstant id="OtherAbility"/>
                           <CActorModel id="Shared"><On Terms="Effect.CustomShot.Start" Send="Create"/>
                           <On Terms="Abil.OtherAbility.Start" Send="Create"/></CActorModel></Catalog>''',
                           {'Abil:OtherAbility'},{'Actor:Shared'})


if __name__=='__main__':
    unittest.main()
