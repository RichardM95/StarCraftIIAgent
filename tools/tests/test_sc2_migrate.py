"""Isolated migration fixtures; never reads or writes a real SC2 project.

Cases adapted from SC2EditorTool (c) 2026 RichardM, MIT; see
tools/vendor/sc2editortool/LICENSE.
"""
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sc2_migrate import Context, analyze, model_asset_paths, closure, mapped_id
from sc2_migrate_catalog import Catalog, encode_node, flatten, digest
from sc2_migrate_package import (export_package, preview_import, apply_import,
                                read_package, rewrite_node, rewrite_text)
from sc2_archive import scan


def component(root,name,xml=''):
    path=root/(name+'.SC2Mod')
    data=path/'Base.SC2Data/GameData';data.mkdir(parents=True)
    (data/'UnitData.xml').write_text('<Catalog>'+xml+'</Catalog>',encoding='utf-8')
    (path/'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>',encoding='utf-8')
    (path/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent><DataComponent Type="gada">GameData</DataComponent></Components>',encoding='utf-8')
    return path


def context(path,official=None,partial=False):
    paths=[*( [official] if official else []),path]
    nodes={str(p).casefold():{'path':str(p),'name':p.name,'origin':'local','official':p==official} for p in paths}
    graph={'nodes':nodes,'traversal_order':list(nodes),'edges':[], 'errors':[], 'missing':[]}
    if partial:
        graph['edges']=[{'kind':'external','raw':'file:Campaigns/Missing.SC2Campaign'}]
    return Context(path,graph=graph)


def catalog(xml):
    return Catalog([{'id':'fixture','name':'Fixture','fingerprint':'fixture'}],
                   [{'source_id':'fixture','path':'UnitData.xml','nodes':[encode_node(ET.fromstring('<Catalog>'+xml+'</Catalog>'))]}])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='sc2-migrate-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.official=component(self.root,'Official','<CUnit id="Marine"><LifeMax value="45"/></CUnit>')
        self.source=component(self.root,'Source','''
          <CUnit id="Marine"><LifeMax value="100"/></CUnit>
          <CUnit id="Demo" parent="Marine"><Name value="Unit/Name/Demo"/>
            <AbilArray Link="Cast"/><WeaponArray Link="Gun"/></CUnit>
          <CAbilEffectTarget id="Cast"><Effect value="Hit"/><CmdButtonArray index="Execute" DefaultButtonFace="Cast"/></CAbilEffectTarget>
          <CButton id="Cast"><Tooltip value="Button/Tooltip/Cast"/></CButton>
          <CWeaponLegacy id="Gun"><Effect value="Hit"/></CWeaponLegacy>
          <CEffectDamage id="Hit"><Amount value="10"/></CEffectDamage>
          <CActorUnit id="DemoActor" unitName="Demo"><Model value="Body"/></CActorUnit>
          <CActorAction id="AttackActor" effectAttack="Hit"/>
          <CModel id="Body"><Model value="Assets/Models/Demo.m3"/></CModel>
          <CUnit id="Projectile"><FlagArray index="Missile" value="1"/></CUnit>
          <CUnit id="Uncertain"/>
        ''')
        for locale in ('zhCN','enUS'):
            text=self.source/(locale+'.SC2Data/LocalizedData');text.mkdir(parents=True)
            (text/'GameStrings.txt').write_text('Unit/Name/Demo=Demo '+locale+'\nButton/Tooltip/Cast=<s ref="Button/Hint/Cast"/>\nButton/Hint/Cast=Hint\n',encoding='utf-8-sig')
            (text/'ObjectStrings.txt').write_text('Unit/Name/Demo=Editor\n',encoding='utf-8')
        model=self.source/'Base.SC2Assets/Assets/Models/Demo.m3';model.parent.mkdir(parents=True)
        string=b'Assets/Textures/Demo.dds\0'
        model.write_bytes(b'43DM'+struct.pack('<II',12+len(string),1)+string+struct.pack('<4sIII',b'RAHC',12,len(string),0))
        texture=self.source/'Base.SC2Assets/Assets/Textures/Demo.dds';texture.parent.mkdir(parents=True)
        texture.write_bytes(b'DDS fixture')
        self.target=component(self.root,'Target')

    def plan(self,selection=None,partial=False,source=None):
        source=source or self.source
        contexts=[context(source,self.official,partial),context(self.target,self.official)]
        return analyze([source],self.target,prefix='Target_',selection=selection,contexts=contexts)

    def test_candidates_baseline_auxiliary_and_reverse_actors(self):
        plan=self.plan()
        rows={r['id']:r for r in plan['candidates']}
        self.assertNotIn('Marine',rows)
        self.assertEqual(rows['Projectile']['kind'],'auxiliary')
        self.assertEqual(rows['Uncertain']['kind'],'needs_selection')
        self.assertTrue(rows['Demo']['selected'])
        chain=rows['Demo']['chain']
        self.assertTrue(chain['executable'],chain['issues'])
        self.assertIn('Actor:DemoActor',chain['objects'])
        self.assertIn('Actor:AttackActor',chain['objects'])
        self.assertNotIn('Unit:Marine',chain['objects'])
        self.assertEqual(plan['object_evidence'][str(self.source)]['Unit:Demo']['fields']['LifeMax']['value'],'100')
        self.assertTrue(any(r['path'].endswith('.dds') for r in chain['resources'].values()))

    def test_incomplete_baseline_does_not_certify_novel_id(self):
        plan=self.plan(partial=True)
        demo=next(r for r in plan['candidates'] if r['id']=='Demo')
        self.assertEqual(demo['official_status'],'unconfirmed')
        self.assertFalse(demo['chain']['executable'])
        self.assertTrue(any(r['id']=='Marine' for r in plan['excluded_official']))
        with self.assertRaisesRegex(ValueError,'unresolved'):
            export_package(plan,self.root/'package')

    def test_duplicate_source_requires_choice_and_keeps_graphs_separate(self):
        other=component(self.root,'Other',(self.source/'Base.SC2Data/GameData/UnitData.xml').read_text().removeprefix('<Catalog>').removesuffix('</Catalog>').replace('value="10"','value="30"'))
        cs=[context(self.source,self.official),context(other,self.official),context(self.target,self.official)]
        plan=analyze([self.source,other],self.target,contexts=cs)
        demos=[r for r in plan['candidates'] if r['id']=='Demo']
        self.assertEqual(len(demos),2)
        self.assertTrue(all(r['selection_required'] and not r['selected'] for r in demos))
        values=[plan['object_evidence'][r['source']]['Effect:Hit']['fields']['Amount']['value'] for r in demos]
        self.assertEqual(values,['10','30'])
        plan=analyze([self.source,other],self.target,selection={'units':{'Demo':self.source.name}},contexts=cs)
        self.assertEqual(sum(r['selected'] for r in plan['candidates'] if r['id']=='Demo'),1)

    def test_export_import_and_repeat_preserve_official_unit(self):
        plan=self.plan();pkg=self.root/'package'
        manifest=export_package(plan,pkg)
        mapping=manifest['id_mapping'][str(self.source)]
        self.assertTrue(all(v.startswith('Target_') for v in mapping.values()))
        xml=(pkg/'Base.SC2Data/GameData/UnitData.xml').read_text()
        self.assertNotIn('parent="Marine"',xml)
        self.assertIn('value="100"',xml)
        before=scan(self.target)
        preview=preview_import(pkg)
        self.assertFalse(apply_import(preview)['applied'])
        self.assertEqual(before,scan(self.target))
        result=apply_import(preview,apply=True)
        self.assertTrue(Path(result['backup']).is_dir())
        self.assertEqual(before,scan(Path(result['backup'])))
        validation=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'validate-mod.py'),
                                   '--mod-dir',str(self.target),'--ui-language','zh-CN'],capture_output=True,encoding='utf-8')
        self.assertEqual(validation.returncode,0,validation.stdout+validation.stderr)
        self.assertFalse(apply_import(preview_import(pkg),apply=True)['applied'])

    def test_text_catalog_dependencies_are_traversed_and_rewritten(self):
        p=self.source/'zhCN.SC2Data/LocalizedData/GameStrings.txt'
        p.write_text(p.read_text(encoding='utf-8-sig')+'Button/Hint/Cast=<d ref="Effect,Extra,Amount"/>\n',encoding='utf-8-sig')
        # Replace an existing key rather than create an ambiguous duplicate.
        p.write_text(p.read_text(encoding='utf-8-sig').replace('Button/Hint/Cast=Hint\n',''),encoding='utf-8-sig')
        data=self.source/'Base.SC2Data/GameData/EffectData.xml'
        data.write_text('<Catalog><CEffectDamage id="Extra"><Amount value="17"/></CEffectDamage></Catalog>')
        plan=self.plan();demo=next(r for r in plan['candidates'] if r['id']=='Demo')
        self.assertIn('Effect:Extra',demo['chain']['objects'])
        pkg=self.root/'package';manifest=export_package(plan,pkg)
        new=manifest['id_mapping'][str(self.source)]['Effect:Extra']
        self.assertIn('Effect,'+new+',Amount',(pkg/'zhCN.SC2Data/LocalizedData/GameStrings.txt').read_text(encoding='utf-8-sig'))

    def test_tamper_staleness_and_target_conflicts(self):
        plan=self.plan();pkg=self.root/'package';export_package(plan,pkg)
        with self.assertRaisesRegex(ValueError,'changed|stale'):
            preview=preview_import(pkg)
            (self.target/'extra').write_text('concurrent edit')
            apply_import(preview,apply=True)
        payload=pkg/'Base.SC2Data/GameData/UnitData.xml'
        payload.write_bytes(payload.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'payload changed'):
            read_package(pkg)

    def test_source_edit_blocks_export(self):
        plan=self.plan()
        (self.source/'DocumentInfo').write_text('<DocInfo/>')
        with self.assertRaisesRegex(ValueError,'input changed'):
            export_package(plan,self.root/'package')

    def test_failed_publication_rolls_back(self):
        plan=self.plan();pkg=self.root/'package';export_package(plan,pkg)
        preview=preview_import(pkg);before=scan(self.target)
        original=Path.rename
        def fail_install(path,to):
            if path.name==self.target.name and '.stage-' in str(path.parent):
                raise OSError('simulated publication failure')
            return original(path,to)
        with patch.object(Path,'rename',fail_install):
            with self.assertRaisesRegex(OSError,'simulated'):
                apply_import(preview,apply=True)
        self.assertEqual(before,scan(self.target))

    def test_model_bounds_and_resource_conflict(self):
        with self.assertRaisesRegex(ValueError,'header'):
            model_asset_paths(b'invalid')
        with self.assertRaisesRegex(ValueError,'table'):
            model_asset_paths(b'43DM'+struct.pack('<II',400,90))
        target=self.target/'Base.SC2Assets/Assets/Textures/Demo.dds';target.parent.mkdir(parents=True)
        target.write_bytes(b'other texture')
        demo=next(r for r in self.plan()['candidates'] if r['id']=='Demo')
        self.assertTrue(any(i['code']=='resource_conflict' for i in demo['chain']['issues']))

    def test_external_scripts_and_dynamic_actors_block_completeness(self):
        (self.source/'Triggers').write_text('<TriggerData><Script>UnitCreate(Demo)</Script></TriggerData>')
        demo=next(r for r in self.plan()['candidates'] if r['id']=='Demo')
        self.assertTrue(any(i['code']=='external_mechanism_reference' for i in demo['chain']['issues']))

    def test_arrays_defaults_tokens_and_cycle(self):
        c=catalog('''<CUnit default="1"><LifeMax value="30"/></CUnit>
          <CUnit id="Parent"><AbilArray index="0" Link="Move"/><AbilArray index="1" Link="Attack"/></CUnit>
          <CUnit id="Child" parent="Parent"><AbilArray index="0" Link=""/><AbilArray index="1" removed="1"/><AbilArray Link="Cast"/></CUnit>
          <CActorModel id="ParentActor" unitName="Child"><On Terms="UnitBirth.##unitName##" Send="Create"/></CActorModel>
          <CActorModel id="ChildActor" parent="ParentActor"/>
          <CUnit id="CycleA" parent="CycleB"/><CUnit id="CycleB" parent="CycleA"/>
        ''')
        fields=flatten(c.effective('Unit','Child'))
        self.assertEqual(fields['LifeMax'],'30')
        self.assertEqual(fields['AbilArray|0'],'')
        self.assertEqual(fields['AbilArray|2'],'Cast')
        self.assertNotIn('AbilArray|1',fields)
        self.assertEqual(flatten(c.effective('Actor','ChildActor'))['On|@Terms'],'UnitBirth.Child')
        c.effective('Unit','CycleA')
        self.assertTrue(any(d['code']=='inheritance_cycle' for d in c.diagnostics))

    def test_schema_discovers_nonheuristic_unit_link(self):
        from sc2_migrate_links import links
        node=encode_node(ET.fromstring('<CAbilEffectTarget id="Cast"><PlaceUnit value="Helper"/></CAbilEffectTarget>'))
        self.assertTrue(any(r['target']=='Unit:Helper' for r in links(node,'Abil','Cast')[0]))

    def test_path_escape_in_package_manifest_rejected(self):
        plan=self.plan();pkg=self.root/'package';export_package(plan,pkg)
        manifest=json.loads((pkg/'migration-manifest.json').read_text())
        manifest['files']['../escape']={'sha256':'bad','size':0}
        manifest['package_id']=digest({k:v for k,v in manifest.items() if k!='package_id'})
        (pkg/'migration-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            read_package(pkg)

    def test_added_catalog_invalidates_plan_and_target_default_change_blocks(self):
        plan=self.plan()
        path=self.source/'Base.SC2Data/GameData/NewData.xml'
        path.write_text('<Catalog><CUnit id="Added"/></Catalog>')
        with self.assertRaisesRegex(ValueError,'inventory changed'):
            export_package(plan,self.root/'package')
        path.unlink()
        target=self.target/'Base.SC2Data/GameData/UnitData.xml'
        target.write_text('<Catalog><CUnit default="1"><EnergyMax value="300"/></CUnit></Catalog>')
        with self.assertRaisesRegex(ValueError,'default semantics differ'):
            export_package(self.plan(),self.root/'package')

    def test_target_object_conflict_and_manual_target_change_are_blocked(self):
        plan=self.plan()
        new_id=plan['candidates'][0]['chain']['objects']['Unit:Demo']['id']
        target=self.target/'Base.SC2Data/GameData/UnitData.xml'
        target.write_text('<Catalog><CUnit id="'+new_id+'"><LifeMax value="1"/></CUnit></Catalog>')
        plan=self.plan();pkg=self.root/'package';export_package(plan,pkg)
        preview=preview_import(pkg)
        self.assertTrue(any(c['code']=='target_object_conflict' for c in preview['conflicts']))
        with self.assertRaisesRegex(ValueError,'conflicts'):
            apply_import(preview,apply=True)

    def test_unknown_actor_message_dynamic_token_and_budget_block(self):
        path=self.source/'Base.SC2Data/GameData/ActorData.xml'
        path.write_text('<Catalog><CActorModel id="HelperActor"><On Terms="UnitBirth.Demo" Send="Create"/><On Terms="ActorCreation" Send="UnrecognizedMessage Gun"/></CActorModel></Catalog>')
        demo=next(c for c in self.plan()['candidates'] if c['id']=='Demo')
        self.assertTrue(any(i['code']=='unclassified_actor_reference' for i in demo['chain']['issues']))
        path.write_text('<Catalog><CActorModel id="HelperActor"><On Terms="UnitBirth.Demo" Send="Create"/><On Terms="ActorCreation" Send="Create ##unknown##"/></CActorModel></Catalog>')
        demo=next(c for c in self.plan()['candidates'] if c['id']=='Demo')
        self.assertTrue(any(i['code']=='dynamic_reference' for i in demo['chain']['issues']))
        c=context(self.source,self.official);t=context(self.target,self.official)
        chain=closure(c,('Unit','Demo'),t,'Target_',max_objects=1)
        self.assertTrue(any(i['code']=='object_budget_exceeded' for i in chain['issues']))

    def test_utf16_target_text_and_locale_registration(self):
        text=self.target/'zhCN.SC2Data/LocalizedData/GameStrings.txt';text.parent.mkdir(parents=True)
        text.write_bytes(b'\xff\xfe'+'Existing/Key=宸叉湁\r\n'.encode('utf-16-le'))
        plan=self.plan();pkg=self.root/'package';export_package(plan,pkg)
        apply_import(preview_import(pkg),apply=True)
        raw=text.read_bytes()
        self.assertTrue(raw.startswith(b'\xff\xfe'))
        self.assertIn('Existing/Key=宸叉湁',raw[2:].decode('utf-16-le'))
        locales={n.get('Locale') for n in ET.parse(self.target/'ComponentList.SC2Components').getroot()}
        self.assertTrue({'zhCN','enUS'}<=locales)

    def test_repeated_apply_does_not_hide_later_target_edits(self):
        pkg=self.root/'package';export_package(self.plan(),pkg)
        apply_import(preview_import(pkg),apply=True)
        path=self.target/'Base.SC2Data/GameData/UnitData.xml'
        path.write_text(path.read_text().replace('value="100"','value="1"'))
        with self.assertRaisesRegex(ValueError,'previous import'):
            preview_import(pkg)

    def test_backup_is_restorable_through_existing_archive_interface(self):
        from sc2_archive import restore
        before=scan(self.target);pkg=self.root/'package';export_package(self.plan(),pkg)
        installed=apply_import(preview_import(pkg),apply=True)
        preview=restore(Path(installed['backup']))
        self.assertFalse(preview['applied'])
        restored=restore(Path(installed['backup']),apply=True)
        self.assertTrue(restored['applied'])
        self.assertEqual(before,scan(self.target))

    def test_default_tables_only_block_when_their_order_can_change_values(self):
        a=self.official/'Base.SC2Data/GameData/DefaultA.xml'
        b=self.official/'Base.SC2Data/GameData/DefaultB.xml'
        a.write_text('<Catalog><CUnit default="1"><LifeStart value="40"/></CUnit></Catalog>')
        b.write_text('<Catalog><CUnit default="1"><EnergyMax value="60"/></CUnit></Catalog>')
        c=context(self.source,self.official)
        self.assertFalse(any(i['code']=='ambiguous_default_order' for i in c.component_issues))
        b.write_text('<Catalog><CUnit default="1"><LifeStart value="90"/></CUnit></Catalog>')
        c=context(self.source,self.official)
        self.assertTrue(any(i['code']=='ambiguous_default_order' for i in c.component_issues))
        chain=closure(c,('Unit','Demo'),context(self.target,self.official),'Target_')
        self.assertTrue(any(i['code']=='ambiguous_default_order' for i in chain['issues']))

    def test_identity_predicate_does_not_import_an_unrelated_unit_tree(self):
        path=self.source/'Base.SC2Data/GameData/UnitData.xml'
        xml=path.read_text().replace('<Effect value="Hit"/><CmdButtonArray','<Effect value="Hit"/><AutoCastValidatorArray value="CheckMarine"/><CmdButtonArray')
        xml=xml.replace('</Catalog>','<CValidatorUnitType id="CheckMarine"><Value value="Marine"/></CValidatorUnitType></Catalog>')
        path.write_text(xml)
        plan=self.plan();demo=next(c for c in plan['candidates'] if c['id']=='Demo')
        self.assertIn('Validator:CheckMarine',demo['chain']['objects'])
        self.assertNotIn('Unit:Marine',demo['chain']['objects'])
        self.assertTrue(demo['chain']['executable'],demo['chain']['issues'])
        pkg=self.root/'package';export_package(plan,pkg)
        self.assertIn('value="Marine"',(pkg/'Base.SC2Data/GameData/ValidatorData.xml').read_text())

    def test_underscore_catalog_ids_are_not_assumed_to_be_actor_aliases(self):
        path=self.source/'Base.SC2Data/GameData/UnitData.xml'
        original=path.read_text()
        path.write_text(original.replace('<Effect value="Hit"/>','<Effect value="_Missing"/>'))
        demo=next(c for c in self.plan()['candidates'] if c['id']=='Demo')
        self.assertTrue(any(i.get('object')=='Effect:_Missing' for i in demo['chain']['issues']))
        path.write_text(original.replace('<Effect value="Hit"/>','<Effect value="_Custom"/>').replace(
            '</Catalog>','<CEffectDamage id="_Custom"><Amount value="10"/></CEffectDamage></Catalog>'))
        plan=self.plan();demo=next(c for c in plan['candidates'] if c['id']=='Demo')
        self.assertIn('Effect:_Custom',demo['chain']['objects'])
        self.assertTrue(demo['chain']['executable'],demo['chain']['issues'])


if __name__=='__main__':
    unittest.main()
