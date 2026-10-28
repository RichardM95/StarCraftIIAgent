"""Sparse, build-bound asset materialization using the shared source cache."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import assets
from .assets_model import resolve_assets
from .errors import SC2Error
from .source_context import (_canonical, _cache_load, _cache_publish, _read_casc_batch,
                             assert_source_context_current)
from .storage import file_lock


def materialize_assets(context: dict, references: list[str], *, sources=None, cancel=None) -> dict:
    """Resolve only proven dependency packs plus explicitly requested packs.

    Explicit packs have caller-declared order, which is reported separately
    from the dependency graph. The original SourceContext remains immutable.
    """
    assert_source_context_current(context)
    if not isinstance(references,list) or not 1<=len(references)<=500:
        raise SC2Error('invalid_asset_references','请指定1至500个明确资源引用')
    refs=[assets._relative(value) for value in references]
    if sources is not None and (not isinstance(sources,list) or len(sources)>32):
        raise SC2Error('invalid_asset_sources','额外来源必须为不超过32项明确包路径')
    graph=context['dependency_report']
    packs=[]
    for key in graph['load_order']:
        for node in graph['nodes']:
            if node['path']==key and node.get('source_kind')=='casc':
                prefix=assets._relative(node['name'])
                if prefix not in packs:packs.append(prefix)
    explicit=[]
    for prefix in sources or []:
        prefix=assets._relative(prefix)
        if not prefix.lower().endswith(('.sc2mod','.sc2map','.sc2campaign')):
            raise SC2Error('invalid_asset_sources','来源必须是明确SC2Mod/SC2Map/SC2Campaign虚拟包路径')
        if prefix not in packs:packs.append(prefix);explicit.append(prefix)
    roots=[Path(value) for value in context['roots']]
    build=context.get('build')
    if packs and not build:raise SC2Error('asset_build_required','CASC资源物化必须绑定实际构建')
    cache=Path(context['cache_root'])
    locale=context.get('locale')
    if locale is not None and (not isinstance(locale,str) or not re.fullmatch(r'[a-z]{2}[A-Z]{2}',locale)):
        raise SC2Error('invalid_asset_locale','资源地区必须为明确的SC2地区代码')
    components=['Base.SC2Assets']+([locale+'.SC2Assets'] if locale else [])
    materialized,origins=[],[]
    queried=set()
    with file_lock(cache/'source-context.lock'):
        for _depth in range(32):
            if cancel and cancel.is_set():raise SC2Error('cancelled','资源物化已取消')
            closure=resolve_assets(materialized+roots,refs,source_context=context)
            pending=sorted({assets._relative(item['reference']) for item in closure['missing']
                            if item['reason']=='not_in_materialized_roots'}-queried)
            if not pending or not packs:break
            queried.update(pending)
            for prefix in packs:
                for component in components:
                    identity={'kind':'asset-casc-2','source':prefix,'component':component,'build':build,
                              'source_context_id':context['source_context_id'],'names':pending}
                    directory=cache/'assets'/hashlib.sha256(_canonical(identity)).hexdigest()
                    reused=_cache_load(directory,identity)
                    if reused:folder,issues=reused
                    else:
                        # A pack's selected locale overrides its Base component;
                        # do not invent an English or other locale fallback.
                        found=_read_casc_batch(Path(build['installation']),prefix+'/'+component,pending,cache,build)
                        files={relative:raw for relative,raw in found.values()}
                        issues=[{'code':'asset_missing','reference':name} for name in pending if name.casefold() not in found]
                        folder=_cache_publish(directory,identity,files,issues)
                    materialized.append(folder)
                    origins.append({'materialized_root':str(folder),'source_kind':'casc','source_path':prefix,
                                    'component':component,'build':build,'locale':locale,
                                    'order_status':'caller_declared' if prefix in explicit else 'dependency_graph'})
        else:raise SC2Error('asset_closure_limit','模型资源闭包超过32层，请检查循环或异常来源')
    assert_source_context_current(context)
    closure=resolve_assets(materialized+roots,refs,source_context=context)
    for node in closure['nodes']:
        matches=[origin for origin in origins if Path(node['physical_path']).is_relative_to(Path(origin['materialized_root']))]
        if matches:node['origin']=matches[-1]
    closure['asset_sources']=origins
    closure['roots']=[str(path) for path in materialized+roots]
    closure['asset_locale_policy']={'selected_locale':locale,'components_low_to_high':components,
                                    'fallback':'Base.SC2Assets only; no implicit alternate locale'}
    if explicit:
        closure['unknown'].append({'reason':'extra_pack_order_caller_declared','sources':explicit})
        closure['complete']=False
    return closure
