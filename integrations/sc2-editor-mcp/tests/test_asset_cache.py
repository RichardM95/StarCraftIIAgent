from pathlib import Path
import pytest
from sc2_mcp import asset_cache
from sc2_mcp.errors import SC2Error


def test_sparse_cache_reuses_verified_files_and_preserves_local_override(tmp_path,monkeypatch):
    root=tmp_path/'map';root.mkdir()
    context={'source_context_id':'bound','cache_root':str(tmp_path/'cache'),'roots':[str(root)],
        'build':{'installation':str(tmp_path/'installation'),'product':'s2_cn','branch':'cn','build_key':'test'},
        'dependency_report':{'load_order':['casc:pack'],'nodes':[{'path':'casc:pack','name':'Mods/Pack.SC2Mod','source_kind':'casc'}]},'complete':True}
    monkeypatch.setattr(asset_cache,'assert_source_context_current',lambda context:{'current':True})
    calls=[]
    def read(installation,prefix,names,cache,build):
        calls.append((prefix,names))
        return {name.casefold():(name,b'asset-content') for name in names if name.endswith('.dds')}
    monkeypatch.setattr(asset_cache,'_read_casc_batch',read)
    report=asset_cache.materialize_assets(context,['Assets/Textures/a.dds'])
    assert report['nodes'][0]['origin']['source_path']=='Mods/Pack.SC2Mod'
    assert report['nodes'][0]['build']['build_key']=='test'
    again=asset_cache.materialize_assets(context,['Assets/Textures/a.dds'])
    assert len(calls)==1 and again['nodes'][0]['sha256']==report['nodes'][0]['sha256']
    local=root/'Assets/Textures/a.dds';local.parent.mkdir(parents=True);local.write_bytes(b'override')
    resolved=asset_cache.materialize_assets(context,['Assets/Textures/a.dds'])
    assert Path(resolved['nodes'][0]['physical_path'])==local
    assert len(calls)==1
    cached=Path(report['nodes'][0]['physical_path']);cached.chmod(0o600);cached.write_bytes(b'tampered')
    local.unlink()
    with pytest.raises(SC2Error) as exc:asset_cache.materialize_assets(context,['Assets/Textures/a.dds'])
    assert exc.value.code=='source_cache_tampered'


def test_explicit_sources_do_not_invent_dependency_order(tmp_path,monkeypatch):
    root=tmp_path/'map';root.mkdir()
    context={'source_context_id':'bound','cache_root':str(tmp_path/'cache'),'roots':[str(root)],
        'build':{'installation':str(tmp_path/'installation'),'product':'s2_cn','branch':'cn'},
        'dependency_report':{'load_order':[],'nodes':[]},'complete':True}
    monkeypatch.setattr(asset_cache,'assert_source_context_current',lambda context:{'current':True})
    monkeypatch.setattr(asset_cache,'_read_casc_batch',lambda *args:{'assets/a.dds':('Assets/a.dds',b'x')})
    result=asset_cache.materialize_assets(context,['Assets/a.dds'],sources=['Campaigns/Liberty.SC2Campaign'])
    assert result['complete'] is False
    assert result['nodes'][0]['origin']['order_status']=='caller_declared'
    assert result['unknown'][-1]['reason']=='extra_pack_order_caller_declared'
    assert context['dependency_report']['nodes']==[]


def test_selected_locale_assets_override_base_and_no_other_locale_is_guessed(tmp_path,monkeypatch):
    root=tmp_path/'map';root.mkdir()
    context={'source_context_id':'bound','cache_root':str(tmp_path/'cache'),'roots':[str(root)],'locale':'zhCN',
        'build':{'installation':str(tmp_path/'installation'),'product':'s2_cn','branch':'cn'},
        'dependency_report':{'load_order':['casc:pack'],'nodes':[{'path':'casc:pack','name':'Mods/War3.SC2Mod','source_kind':'casc'}]},'complete':True}
    monkeypatch.setattr(asset_cache,'assert_source_context_current',lambda context:{'current':True})
    calls=[]
    def read(installation,prefix,names,cache,build):
        calls.append(prefix)
        content=b'chinese' if prefix.endswith('zhCN.SC2Assets') else b'base'
        return {'assets/sound.ogg':('Assets/sound.ogg',content)}
    monkeypatch.setattr(asset_cache,'_read_casc_batch',read)
    result=asset_cache.materialize_assets(context,['Assets/sound.ogg'])
    node=result['nodes'][0]
    assert node['origin']['component']=='zhCN.SC2Assets'
    assert Path(node['physical_path']).read_bytes()==b'chinese'
    assert calls==['Mods/War3.SC2Mod/Base.SC2Assets','Mods/War3.SC2Mod/zhCN.SC2Assets']
    assert result['asset_locale_policy']['selected_locale']=='zhCN'
    again=asset_cache.materialize_assets(context,['Assets/sound.ogg'])
    assert again['nodes'][0]['sha256']==node['sha256'] and len(calls)==2


def test_locale_only_sound_is_not_reported_missing(tmp_path,monkeypatch):
    root=tmp_path/'map';root.mkdir()
    context={'source_context_id':'bound','cache_root':str(tmp_path/'cache'),'roots':[str(root)],'locale':'zhCN',
        'build':{'installation':str(tmp_path/'installation'),'product':'s2_cn','branch':'cn'},
        'dependency_report':{'load_order':['casc:pack'],'nodes':[{'path':'casc:pack','name':'Mods/War3.SC2Mod','source_kind':'casc'}]},'complete':True}
    monkeypatch.setattr(asset_cache,'assert_source_context_current',lambda context:{'current':True})
    monkeypatch.setattr(asset_cache,'_read_casc_batch',lambda installation,prefix,*args:
                        {'assets/sound.ogg':('Assets/sound.ogg',b'locale sound')} if prefix.endswith('/zhCN.SC2Assets') else {})
    result=asset_cache.materialize_assets(context,['Assets/sound.ogg'])
    assert result['missing']==[] and result['nodes'][0]['origin']['component']=='zhCN.SC2Assets'
