import json
import sys
from pathlib import Path

import pytest

from sc2_mcp.secret_hangar_audit import (audit_script, audit_catalog, parse_script,
                                       TRAIN, COMPLETE, DISCARD, _code)
from sc2_mcp.catalog import CatalogSession
from sc2_mcp.errors import SC2Error
import sc2_mcp.secret_hangar_audit as module

RAW=(Path(__file__).parent/'fixtures/secret_hangar/named_chain_fixture.galaxy').read_bytes()
PROFILE=json.loads((Path(module.__file__).parent/'profiles/secret_hangar_profile.json').read_text(encoding='utf-8'))


def change_function(name, old, new):
    script=parse_script(RAW)
    f=script.function(name)
    code=script.text[f.start:f.end]
    assert old in code
    return (script.text[:f.start]+code.replace(old,new,1)+script.text[f.end:]).encode('utf-8')


def test_named_fixture_chain():
    result=audit_script(RAW,PROFILE)
    assert result['profile_recognized'],result['unknown']
    assert result['production']['branches'][0]=={'addon':'Reactor','command_index':5,'slot':'Train6','orders':2}
    assert result['completion']['raven_enters_discard_branch'] is False
    assert result['completion']['building_guard'] is False
    assert len(result['completion']['discard_calls'])==2
    assert any(e['kind']=='queued_trigger_dispatch' for e in result['edges'])
    assert result['risks'][0]['status']=='static_candidate_risk'


def test_unitgroup_definition_is_not_lost():
    script=parse_script(RAW)
    assert '"StarportSecretHangar"' in _code(script,'lib1_gf_GetStarportsWithoutAddons')


def test_comments_and_whitespace_do_not_invalidate_semantics():
    changed=RAW.replace(b'void lib1_gf_BuildStructure',b'// comment\nvoid  lib1_gf_BuildStructure',1)
    assert audit_script(changed,PROFILE)['profile_recognized']


@pytest.mark.parametrize('target,replacement',[
    ('"StarportTrainSecretHangar", 5','"StarportTrain", 5'),
    ('"StarportTrainSecretHangar", 1','"StarportTrainSecretHangar", 2'),
    ('"StarportSecretHangar", c_playerAny','"Starport", c_playerAny'),
])
def test_ordinary_neighbor_or_changed_slot_cannot_satisfy_named_loop(target,replacement):
    result=audit_script(change_function(TRAIN,target,replacement),PROFILE)
    assert result['production']['status']=='unknown'
    assert not result['profile_recognized']


def test_commented_out_second_reactor_order_is_detected():
    statement='UnitIssueOrder(lv_unit, Order(AbilityCommand("StarportTrainSecretHangar", 5)), c_orderQueueReplace);'
    result=audit_script(change_function(TRAIN,statement,'// '+statement),PROFILE)
    assert result['production']['status']=='unknown'
    assert len(result['production']['commands'])==4


@pytest.mark.parametrize('old,new',[
    ('"BattlecruiserSecretHangarCovertOps"','"OtherUnit"'),
    ('lib1_gf_DiscardCardFromHandtoDiscard(', 'lib1_gf_OtherDiscard('),
])
def test_missing_variant_filter_or_discard_does_not_pass(old,new):
    result=audit_script(change_function(COMPLETE,old,new),PROFILE)
    assert result['completion']['status']=='unknown'
    assert not result['profile_recognized']


def test_disconnected_init_keeps_unknown():
    changed=RAW.replace(b'    lib1_gt_UnitFinishesTraining_Init();',b'    // lib1_gt_UnitFinishesTraining_Init();')
    result=audit_script(changed,PROFILE)
    row=next(r for r in result['registrations'] if r['trigger']=='lib1_gt_UnitFinishesTraining')
    assert row['created'] and not row['initialized'] and row['status']=='unknown'


def test_wrong_handle_assignment_keeps_unknown():
    changed=change_function('lib1_gt_UnitFinishesTraining_Init',
                           'lib1_gt_UnitFinishesTraining = TriggerCreate',
                           'lib1_gt_Other = TriggerCreate')
    result=audit_script(changed,PROFILE)
    assert not result['profile_recognized']


def test_wrong_complete_event_keeps_unknown():
    changed=change_function('lib1_gt_UnitFinishesTraining_Init',
                           'c_unitProgressStageComplete','c_unitProgressStageStart')
    assert audit_script(changed,PROFILE)['completion']['status']=='unknown'


def test_changed_discard_body_cannot_retain_behavior_claim():
    changed=change_function(DISCARD,'lp_trigger_when_discarded_effects == true','lp_trigger_when_discarded_effects == false')
    result=audit_script(changed,PROFILE)
    assert result['functions'][DISCARD]['status']=='unknown'
    assert result['risks'][0]['status']=='unknown'


def test_profile_version_drift():
    changed={**PROFILE,'version':'future'}
    assert not audit_script(RAW,changed)['profile_recognized']


def test_fake_comment_definition_is_not_parsed():
    script=parse_script(b'// unitgroup Fake() { return null; }\nvoid Real() {}\n')
    assert 'Fake' not in script.functions and 'Real' in script.functions


def test_ambiguous_unitgroup_definition_rejected():
    with pytest.raises(SC2Error):
        parse_script(b'unitgroup A() {return null;}\nunitgroup A() {return null;}\n')


def fixture_catalog(tmp_path, *, extra='', parent=''):
    folder=tmp_path/'Base.SC2Data/GameData'
    folder.mkdir(parents=True)
    (folder/'AbilData.xml').write_text('<Catalog><CAbilTrain id="StarportTrainSecretHangar" '+parent+'>'
        '<InfoArray index="Train2"><Unit index="0" value="RavenSecretHangarCovertOps"/></InfoArray>'
        '<InfoArray index="Train4"><Unit index="0" value="BattlecruiserSecretHangarCovertOps"/></InfoArray>'
        '<InfoArray index="Train6"><Unit index="0" value="Wraith"/>'+extra+'</InfoArray>'
        '</CAbilTrain></Catalog>',encoding='utf-8')
    (folder/'UnitData.xml').write_text('<Catalog><CUnit id="Reactor"><AddedOnArray index="0" '
        'UnitLink="StarportSecretHangar" BehaviorLink="StarportReactor"/></CUnit></Catalog>',encoding='utf-8')
    return CatalogSession([tmp_path])


def test_one_train6_product_is_distinct_from_two_orders(tmp_path):
    result=audit_catalog(fixture_catalog(tmp_path))
    slot=next(s for s in result['slots'] if s['slot']=='Train6')
    assert slot['status']=='observed_static' and len(slot['products'])==1
    assert next(a for a in result['addons'] if a['addon']=='PhysicsLab')['status']=='unknown'


def test_inherited_extra_product_is_detected(tmp_path):
    result=audit_catalog(fixture_catalog(tmp_path,extra='<Unit index="1" value="Hercules"/>'))
    assert result['slots'][2]['status']=='unknown'
    assert len(result['slots'][2]['products'])==2


def test_missing_parent_does_not_fake_resolved_slot(tmp_path):
    result=audit_catalog(fixture_catalog(tmp_path,parent='parent="MissingOfficialSource"'))
    assert all(s['status']=='unknown' for s in result['slots'])
    assert any(w['code']=='missing_catalog_parent' for w in result['objects']['Abil/StarportTrainSecretHangar']['warnings'])


def test_context_for_wrong_map_is_rejected_before_read(tmp_path):
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(tmp_path,source_context={'root':str(tmp_path/'other')})
    assert error.value.code=='secret_hangar_context_mismatch'


def test_invalid_persisted_context_is_not_trusted(tmp_path):
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(tmp_path,source_context={'root':str(tmp_path),'source_context_id':'forged'})
    assert error.value.code=='invalid_source_context'


def test_missing_context_stays_unknown_and_never_claims_runtime(tmp_path,monkeypatch):
    fixture_catalog(tmp_path)
    (tmp_path/'MapScript.galaxy').write_bytes(RAW)
    text=tmp_path/'zhCN.SC2Data/LocalizedData/GameStrings.txt'
    text.parent.mkdir(parents=True)
    text.write_text('Card/Name/Secret_Hangar=秘密机库\n',encoding='utf-8')
    sha=module._hash(RAW)
    monkeypatch.setattr(module,'inspect_keystone_card',lambda root,name:
        {'script_sha256':sha,'card_id':195,'registration_function':'Unknown_Func'})
    result=module.audit_secret_hangar(tmp_path)
    assert result['source_context_complete'] is False
    assert any(row['code']=='source_context_missing' for row in result['source_unknown'])
    assert result['overall']=='unknown'
    assert result['acceptance']=={'static':'performed','editor':'not_run','runtime':'not_run','visual':'not_run'}


def test_non_missing_catalog_errors_are_not_swallowed():
    class BadCatalog:
        def inspect(self,*args):
            raise SC2Error('catalog_source_changed','source changed')
    with pytest.raises(SC2Error) as error:
        audit_catalog(BadCatalog())
    assert error.value.code=='catalog_source_changed'


@pytest.mark.parametrize('name,statement',[
    ('lib1_gt_UnitFinishesTraining_Init','TriggerAddEventUnitTrainProgress(lib1_gt_UnitFinishesTraining, null, c_unitProgressStageComplete);'),
    ('lib1_InitTriggers','lib1_gt_UnitFinishesTraining_Init();'),
    ('lib1_gt_EffectSecretHangar_Init','lib1_gt_EffectSecretHangar = TriggerCreate("lib1_gt_EffectSecretHangar_Func");'),
    ('lib1_gt_UnnaturalExperimentsUncollectible_Init','TriggerAddEventMapInit(lib1_gt_UnnaturalExperimentsUncollectible);'),
    ('lib1_InitTriggers','lib1_gt_UnnaturalExperimentsUncollectible_Init();'),
    ('lib1_InitLib','lib1_InitTriggers();'),
    ('InitLibs','lib1_InitLib();'),
    ('InitMap','InitLibs();'),
])
def test_unreachable_root_init_event_or_card_registration_is_unknown(name,statement):
    changed=change_function(name,statement,'if (false) { '+statement+' }')
    result=audit_script(changed,PROFILE)
    assert not result['profile_recognized']
    assert name in result['unknown']
    if name in module.ROOT_INITIALIZERS:
        assert result['initialization']['status']=='unknown'
        assert not result['completion']['event_complete']
        assert all(not row['initialized'] for row in result['registrations'])
    if name=='lib1_gt_UnitFinishesTraining_Init':
        assert not result['completion']['event_complete']


@pytest.mark.parametrize('old,new',[
    (b'bool lib1_InitLib_completed = false;',b'bool lib1_InitLib_completed = true;'),
    (b'bool lib1_InitLib_completed = false;',b'bool lib1_InitLib_completed = false;\nvoid ExtraWrite() { lib1_InitLib_completed = true; }'),
])
def test_initialization_once_guard_cannot_be_pre_disabled(old,new):
    result=audit_script(RAW.replace(old,new),PROFILE)
    assert not result['profile_recognized']
    assert result['initialization']['status']=='unknown'
    assert not result['completion']['event_complete']
