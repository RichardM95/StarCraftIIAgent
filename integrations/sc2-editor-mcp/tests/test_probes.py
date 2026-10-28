import json
import uuid
from pathlib import Path

import pytest

from sc2_mcp import editor, probes
from sc2_mcp.errors import SC2Error
from sc2_mcp.probe_bank import parse_probe_bank
from sc2_mcp.storage import digest, snapshot


def test_templates_reject_code_and_preserve_independent_initialization():
    run=uuid.uuid4().hex
    for template in ['unit_combat_behavior','variant_upgrade_parity']:
        raw,phases=probes.render_template(template,{},run)
        assert ('SC2MCPProbe_'+run).encode() in raw
        assert b'lib1_gt_Initialization' not in raw
        assert b'BankValueSetFromString' in raw and len(phases)>4
        assert b'while (i <= count)' in raw
    for params in [{'unit_id':'Marine"); RunEvil(); //'}, {'script':'anything'}, {'sample_seconds':float('nan')}]:
        with pytest.raises(SC2Error):probes.render_template('unit_combat_behavior',params,run)
    with pytest.raises(SC2Error):probes.render_template('catalog_snapshot',{'object_id':'HighTemplar','fields':['LifeMax);Evil(']},run)


def test_missing_enabled_and_native_flag_remain_distinct():
    result=parse_probe_bank(b'<Bank><Section name="S"><Key name="Weapon1"><Value string="W"/></Key><Key name="Alive"><Value flag="1"/></Key></Section></Bank>')
    obs=result['weapon_observations']['S']
    assert obs['weapons'][0]['enabled'] is None
    assert obs['enabled_count']==0 and obs['disabled_count']==0 and obs['unknown_enabled_count']==1
    assert result['sections']['S']['Alive'] is True


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    root=tmp_path/'source.SC2Map';root.mkdir()
    (root/'DocumentInfo').write_bytes(b'<DocInfo><Dependencies/></DocInfo>')
    (root/'MapScript.galaxy').write_bytes(b'void InitMap () { ProductionBankLoad(); }\n')
    (root/'BankList.xml').write_bytes(b'<BankList><Bank Name="Production" Player="1"/></BankList>')
    def export(source,destination):
        destination.write_bytes(b'MPQ-fixture');return {'test_backend':True}
    monkeypatch.setattr(probes.archives,'export_archive',export)
    docs=tmp_path/'Documents';(docs/'Banks').mkdir(parents=True)
    monkeypatch.setattr(editor,'documents_root',lambda:docs)
    manager=probes.Probes(tmp_path/'state')
    baseline=snapshot(root)
    manifest=manager.prepare(root,'catalog_snapshot',{'object_id':'HighTemplar','fields':['LifeMax']})
    assert snapshot(root)==baseline
    return manager,manifest,docs


def test_prepare_changes_only_independent_copy_and_bank(prepared):
    manager,manifest,_=prepared
    target=Path(manifest['component_copy'])
    script=(target/'MapScript.galaxy').read_bytes()
    assert b'ProductionBankLoad' not in script
    bank=(target/'BankList.xml').read_bytes()
    assert b'Production' not in bank and manifest['bank_name'].encode() in bank
    assert manifest['transaction']['state']=='committed'


def write_bank(manifest,docs,run_id=None,status='FINISHED',phase='FINISHED',value='150'):
    manager=probes.Probes(Path(manifest['archive']).parents[2])
    current=manager.read(manifest['probe_id'])
    if not current.get('launch'):
        current.update(state='launching',launch={'test_backend':True},launched_at=current['created_at'])
        manager.save(current)
    raw=(f'<Bank><Section name="Run"><Key name="RunId"><Value string="{run_id or manifest["run_id"]}"/></Key>'
        f'<Key name="Status"><Value string="{status}"/></Key></Section><Section name="Catalog">'
        f'<Key name="StageStatus"><Value string="{phase}"/></Key><Key name="LifeMax"><Value string="{value}"/></Key></Section></Bank>').encode()
    (docs/'Banks'/(manifest['bank_name']+'.SC2Bank')).write_bytes(raw)


def test_restarted_collector_assertion_failure_is_failure(prepared):
    manager,manifest,docs=prepared
    manifest['assertions']=[{'id':'life','section':'Catalog','key':'LifeMax','operator':'eq','expected':'999'}]
    manager.save(manifest);write_bank(manifest,docs)
    restarted=probes.Probes(manager.state)
    result=restarted.collect(manifest['probe_id'])
    assert result['execution']['state']=='complete' and result['verdict']=='failed'
    assert result['binding']=='run_bound'
    assert Path(result['bank']).read_bytes()==(docs/'Banks'/(manifest['bank_name']+'.SC2Bank')).read_bytes()


def test_partial_old_run_and_stale_source(prepared):
    manager,manifest,docs=prepared
    write_bank(manifest,docs,status='STARTED',phase='STARTED')
    result=manager.collect(manifest['probe_id'])
    assert result['execution']['state']=='partial' and result['verdict']=='partial'
    (Path(manifest['source'])/'manual.txt').write_bytes(b'new')
    assert manager.collect(manifest['probe_id'])['source_stale'] is True
    write_bank(manifest,docs,run_id='old')
    with pytest.raises(SC2Error,match='does not match'):manager.collect(manifest['probe_id'])


def test_engine_sanitized_bank_filename_still_requires_run_id(prepared):
    manager,manifest,docs=prepared
    write_bank(manifest,docs)
    source=docs/'Banks'/(manifest['bank_name']+'.SC2Bank')
    source.rename(source.with_name(source.name.replace('_','')))
    assert manager.collect(manifest['probe_id'])['execution']['state']=='complete'


def test_archived_bank_survives_external_cleanup_and_timeout_is_not_promoted(prepared):
    manager,manifest,docs=prepared
    write_bank(manifest,docs)
    manager.collect(manifest['probe_id'])
    (docs/'Banks'/(manifest['bank_name']+'.SC2Bank')).unlink()
    manifest=manager.read(manifest['probe_id'])
    manifest['state']='timed_out';manager.save(manifest)
    result=probes.Probes(manager.state).collect(manifest['probe_id'])
    assert result['execution']['state']=='complete'
    assert result['bank_verdict']=='complete' and result['verdict']=='partial'
    assert result['termination_reason']=='timed_out'


def test_unlaunched_probe_never_claims_current_named_bank(prepared):
    manager,manifest,docs=prepared
    write_bank(manifest,docs)
    manager.save(manifest)
    result=manager.collect(manifest['probe_id'])
    assert result['evidence_status']=='not_launched' and 'bank' not in result


def test_automatic_completed_bank_preserves_failed_assertion(prepared,monkeypatch):
    manager,manifest,docs=prepared
    manifest['assertions']=[{'id':'wrong','section':'Catalog','key':'LifeMax','operator':'eq','expected':'999'}]
    manager.save(manifest)
    monkeypatch.setattr(editor,'processes',lambda *args:[])
    monkeypatch.setattr(editor,'log_files',lambda *args:[])
    def launch(*args):
        write_bank(manifest,docs)
        return {'selected_client':'D:/StarCraft II/Versions/Base98370/SC2_x64.exe'}
    monkeypatch.setattr(editor,'launch_test',launch)
    result=manager.run(manifest['probe_id'],Path('D:/StarCraft II'))
    assert result['run_state']=='finished' and result['verdict']=='failed'
    assert manager.read(manifest['probe_id'])['verdict']=='failed'


def test_live_user_client_blocks_without_launch_or_kill(prepared,monkeypatch):
    manager,manifest,_=prepared
    monkeypatch.setattr(editor,'processes',lambda *args:[{'pid':123,'name':'SC2_x64.exe'}])
    monkeypatch.setattr(editor,'launch_test',lambda *args:pytest.fail('must not launch'))
    monkeypatch.setattr(manager,'stop_owned',lambda *args:pytest.fail('must not stop user'))
    result=manager.run(manifest['probe_id'],Path('D:/StarCraft II'))
    assert result['state']=='blocked' and result['execution']=='not_started'


def test_startup_timeout_keeps_missing_and_does_not_mark_success(prepared,monkeypatch):
    manager,manifest,_=prepared
    monkeypatch.setattr(editor,'processes',lambda *args:[])
    monkeypatch.setattr(editor,'log_files',lambda *args:[])
    monkeypatch.setattr(editor,'launch_test',lambda *args:{'selected_client':'D:/StarCraft II/Versions/Base98370/SC2_x64.exe'})
    result=manager.run(manifest['probe_id'],Path('D:/StarCraft II'),startup_timeout=1)
    assert result['execution']=='not_started' and result['verdict']=='partial'
    assert result['run_state']=='timed_out' and 'sections' not in result
