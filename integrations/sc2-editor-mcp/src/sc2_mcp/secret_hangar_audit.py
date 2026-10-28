"""Read-only, named Keystone Secret Hangar impact audit.

This is a version-bounded static profile, not a Galaxy interpreter. Whole
function fingerprints guard statements about control flow; parsed calls and
Catalog provenance supply independently inspectable edges. Unknown source or
changed code never becomes engine/runtime acceptance. No map writes occur.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sc2_mcp.catalog import CatalogSession
from sc2_mcp.errors import SC2Error
from sc2_mcp.keystone import _Script, _Function, inspect_keystone_card
from sc2_mcp.source_context import assert_source_context_current

PROFILE_VERSION = 'secret-hangar-static-20261016-2'
TRAIN = 'auto_lib1_gf_OrderStructurestoTrainUnits_TriggerFunc'
COMPLETE = 'lib1_gt_UnitFinishesTraining_Func'
DISCARD = 'lib1_gf_DiscardCardFromHandtoDiscard'
SYMBOLS = [
    'lib1_gt_EffectUndergroundBase_Func', 'lib1_gt_EffectSecretHangar_Func',
    'lib1_gf_BuildStructure', 'lib1_gf_AddBuildertoQueue', 'lib1_gf_ReorderBuilder',
    'lib1_gf_FindStructureBuildTarget', 'lib1_gf_IssueBuildOrder',
    'lib1_gf_StartBattlePhase', 'lib1_gf_OrderStructurestoTrainUnits', TRAIN,
    'lib1_gf_GetStarportsWithoutAddons', 'lib1_gt_EffectReactor_Func',
    'lib1_gt_EffectTechLab_Func', 'lib1_gt_EffectPhysicsLab_Func',
    'lib1_gf_CheapestStructureinUnitGroup', 'lib1_gf_MostExpensiveStructureinUnitGroup',
    COMPLETE, 'lib1_gf_TopofHand', 'lib1_gf_FirstEmptyHandSlotHandCardCount',
    'lib1_gf_PlayerHasCardAtHandIndex', 'lib1_gf_CheapestHandCard',
    'lib1_gf_HandCardTotalCost', 'lib1_gf_HandCardMineralCost', 'lib1_gf_HandCardGasCost',
    DISCARD, 'lib1_gf_HandCardIsTemporary', 'lib1_gf_GenerateCardToDiscard',
    'lib1_gf_RemoveCardFromHand', 'lib1_gf_JunkbossSiggsEffect',
    'lib1_gf_JunkbossSiggsDiscardResponse', 'lib1_gf_AddEffecttoQueue',
    'lib1_gf_ExecuteEffectQueue', 'lib1_gt_EffectJunkbossSiggsDiscardResponse_Func',
    'lib1_gf_ReturnCardFromDiscardtoHand',
    'lib1_gf_TotalCost',
]
TRIGGERS = [
    'EffectSecretHangar', 'EffectUndergroundBase', 'EffectReactor', 'EffectTechLab',
    'EffectPhysicsLab', 'UnitFinishesTraining', 'EffectJunkbossSiggsDiscardResponse',
]
CARD_REGISTRATIONS = [
    'lib1_gt_UnnaturalExperimentsUncollectible_Func', 'lib1_gt_CoreTerran_Func',
    'lib1_gt_UnnaturalExperimentsPromo_Func', 'lib1_gt_UnnaturalExperimentsTerran_Func',
]
ROOT_INITIALIZERS = ['InitMap', 'InitLibs', 'lib1_InitLib', 'lib1_InitTriggers']
SYMBOLS += [f'lib1_gt_{stem}_Init' for stem in TRIGGERS]
SYMBOLS += CARD_REGISTRATIONS
SYMBOLS += [name.removesuffix('_Func')+'_Init' for name in CARD_REGISTRATIONS]
SYMBOLS += ROOT_INITIALIZERS


def parse_script(raw: bytes) -> _Script:
    script = _Script(raw)
    # Local additive support; the shared Keystone parser intentionally stays
    # unchanged. Match definitions in the comment/string mask, never literals.
    pattern = re.compile(r'(?m)^[ \t]*(?:static[ \t]+)?unitgroup[ \t]+(?P<name>\w+)[ \t]*\([^)]*\)[ \t]*\{')
    for match in pattern.finditer(script.mask):
        name = match['name']
        if name in script.functions:
            raise SC2Error('secret_hangar_ambiguous', '函数定义不唯一', function=name)
        opening = script.mask.index('{', match.start(), match.end())
        script.functions[name] = _Function(name, match.start(), opening, script.pairs[opening] + 1)
    return script


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _calls(script, name):
    function = script.functions.get(name)
    return script.calls(function) if function else []


def _code(script, name):
    function = script.functions.get(name)
    return script.normalized_code(function) if function else ''


def _call_record(script, call):
    return {'callee': call.name, 'line': script.line(call.start),
            'arguments': [script.arg(call, index) for index in range(len(call.args))],
            'source': script.text[call.start:call.end]}


def audit_script(raw: bytes, profile: dict) -> dict:
    """Audit a snapshot; changed profiles return unknown, never silent pass."""
    script = parse_script(raw)
    functions = {}
    unknown = []
    for name in SYMBOLS:
        function = script.functions.get(name)
        if function is None:
            functions[name] = {'status': 'unknown', 'reason': 'definition_missing'}
            unknown.append(name)
            continue
        normalized_hash = _hash(script.normalized_code(function).encode('utf-8'))
        recognized = (profile.get('version') == PROFILE_VERSION and
                      profile.get('function_sha256', {}).get(name) == normalized_hash)
        functions[name] = {
            'status': 'observed_profile' if recognized else 'unknown',
            'line': script.line(function.start), 'end_line': script.line(function.end - 1),
            'normalized_sha256': normalized_hash,
            'source_sha256': _hash(script.text[function.start:function.end].encode('utf-8')),
            'source': script.text[function.start:function.end],
            'calls': [_call_record(script, call) for call in script.calls(function)],
        }
        if not recognized:
            unknown.append(name)

    root_guard_known = (
        len(re.findall(r'\blib1_InitLib_completed\b', script.mask)) == 3 and
        len(re.findall(r'(?m)^bool\s+lib1_InitLib_completed\s*=\s*false\s*;',script.mask)) == 1)
    root_profile_known = root_guard_known and all(
        functions[name]['status']=='observed_profile' for name in ROOT_INITIALIZERS)
    if not root_guard_known:
        unknown.append('initialization_once_guard_declaration_or_references')
    initialization = {
        'status':'observed_profile' if root_profile_known else 'unknown',
        'chain':ROOT_INITIALIZERS,
        'once_guard_initial_false_and_references_known':root_guard_known,
        'scope':'Known root entry function bodies and once guard; no engine execution claim',
    }
    edges = []
    for name in SYMBOLS:
        for call in _calls(script, name):
            if call.name in SYMBOLS:
                edges.append({'from': name, 'to': call.name, 'kind': 'call',
                              'line': script.line(call.start),
                              'status':functions[name]['status']})
    registrations = []
    init_calls = _calls(script, 'lib1_InitTriggers')
    for stem in TRIGGERS:
        trigger = f'lib1_gt_{stem}'
        init_name, target = trigger + '_Init', trigger + '_Func'
        creates = [c for c in _calls(script, init_name)
                   if c.name == 'TriggerCreate' and len(c.args) == 1
                   and script.arg(c, 0) == json.dumps(target)]
        initializer_known = functions[init_name]['status']=='observed_profile'
        initialized = (any(c.name == init_name for c in init_calls) and
                       root_profile_known and initializer_known)
        # Also require the assignment to bind this exact trigger handle.
        binding = f'{trigger}=TriggerCreate("{target}");' in _code(script, init_name)
        item = {'trigger': trigger, 'initializer': init_name, 'target': target,
                'created': len(creates) == 1 and binding and initializer_known, 'initialized': initialized,
                'initializer_profile_recognized':initializer_known,
                'root_initialization_profile_recognized':root_profile_known,
                'target_defined': target in script.functions,
                'initializer_source': _code(script, init_name)}
        item['status'] = 'observed' if all(item[k] for k in ('created','initialized','target_defined')) else 'unknown'
        registrations.append(item)
        if item['status'] == 'unknown':
            unknown.append(init_name)
        else:
            edges.append({'from': init_name, 'to': target, 'kind': 'TriggerCreate',
                          'line': script.line(creates[0].start)})

    wrapper = _code(script,'lib1_gf_OrderStructurestoTrainUnits')
    handle = 'auto_lib1_gf_OrderStructurestoTrainUnits_Trigger'
    dispatch_ok = (functions['lib1_gf_OrderStructurestoTrainUnits']['status']=='observed_profile' and
                   f'{handle}=TriggerCreate("{TRAIN}");' in wrapper and
                   f'TriggerExecute({handle},false,false);' in wrapper)
    if dispatch_ok:
        edges.append({'from':'lib1_gf_OrderStructurestoTrainUnits','to':TRAIN,
                      'kind':'lazy_trigger_dispatch','handle':handle})
    else:
        unknown.append('production_trigger_dispatch')
    junk = _code(script,'lib1_gf_JunkbossSiggsEffect')
    queue_code = _code(script,'lib1_gf_ExecuteEffectQueue')
    if (functions['lib1_gf_JunkbossSiggsEffect']['status']=='observed_profile' and
            functions['lib1_gf_ExecuteEffectQueue']['status']=='observed_profile' and
            'lib1_gt_EffectJunkbossSiggsDiscardResponse' in junk and
            'TriggerExecute(lib1_gv_effect_queue[lp_effect_class][lv_effect_index].lv_effect,false,false);' in queue_code):
        edges.append({'from':'lib1_gf_JunkbossSiggsEffect',
                      'to':'lib1_gt_EffectJunkbossSiggsDiscardResponse_Func',
                      'kind':'queued_trigger_dispatch',
                      'via':['lib1_gf_AddEffecttoQueue','lib1_gf_ExecuteEffectQueue'],
                      'condition':'Battle && currently_processing_turn_flow',
                      'effect_class':'lib1_gv_eF_DRAW','card_id':752})

    # Restrict production observations to the lexical loop that uses the
    # Secret Hangar UnitGroup. Ordinary Starport loops cannot satisfy this.
    training = {'status': 'unknown', 'commands': [], 'branches': []}
    calls = _calls(script, TRAIN)
    selectors = [c for c in calls if c.name == 'UnitGroup' and c.args
                 and script.arg(c, 0) == '"StarportSecretHangar"']
    if len(selectors) == 1:
        selector = selectors[0]
        function = script.functions[TRAIN]
        loops = [m for m in re.finditer(r'\bfor\s*\(', script.mask[selector.end:function.end])]
        if loops:
            opening_paren = selector.end + loops[0].end() - 1
            after = script.pairs[opening_paren] + 1
            opening = script.mask.find('{', after, function.end)
            if opening != -1:
                end = script.pairs[opening]
                selected = [c for c in calls if opening < c.start < end]
                commands = [c for c in selected if c.name == 'AbilityCommand']
                training.update({'selector': _call_record(script, selector),
                                 'line': script.line(opening),
                                 'source': script.text[opening:end + 1],
                                 'commands': [_call_record(script,c) for c in commands]})
                expected = [('"StarportTrainSecretHangar"','5'), ('"StarportTrainSecretHangar"','5'),
                            ('"StarportTrainSecretHangar"','1'), ('"StarportTrainSecretHangar"','3'),
                            ('"StarportTrainSecretHangar"','5')]
                actual = [tuple(re.sub(r'\s+', '', script.arg(c,i)) for i in range(len(c.args))) for c in commands]
                training['status'] = 'observed_profile' if actual == expected and functions[TRAIN]['status'] == 'observed_profile' else 'unknown'
                if training['status'] == 'observed_profile':
                    training['branches'] = [
                        {'addon':'Reactor','command_index':5,'slot':'Train6','orders':2},
                        {'addon':'TechLab','command_index':1,'slot':'Train2','orders':1},
                        {'addon':'PhysicsLab','command_index':3,'slot':'Train4','orders':1},
                        {'addon':'default','command_index':5,'slot':'Train6','orders':1}]
    if training['status'] == 'unknown':
        unknown.append('secret_hangar_training_loop')

    completion_code = _code(script, COMPLETE)
    event_code = _code(script, 'lib1_gt_UnitFinishesTraining_Init')
    discarded = [c for c in _calls(script, COMPLETE) if c.name == DISCARD]
    completion = {
        'status': 'observed_profile' if functions[COMPLETE]['status'] == 'observed_profile' else 'unknown',
        'event_complete': (functions['lib1_gt_UnitFinishesTraining_Init']['status']=='observed_profile' and
                           root_profile_known and
                           'TriggerAddEventUnitTrainProgress(lib1_gt_UnitFinishesTraining,null,c_unitProgressStageComplete);' in event_code),
        'discard_calls': [_call_record(script,c) for c in discarded],
        'product_filter': [],
        'building_guard': 'not_evaluated', 'physics_lab_guard': 'not_evaluated',
    }
    if completion['status'] == 'observed_profile':
        completion.update({'product_filter':['ThorAP','Thor','Battlecruiser','BattlecruiserSecretHangarCovertOps'],
                           'building_guard': False, 'physics_lab_guard': False,
                           'raven_enters_discard_branch': False,
                           'hand_threshold': 'TopofHand >= 1; first-empty count minus 1',
                           'fallback': 'kill UnitAddOnChild(EventUnit(),0), subtract TotalCost(Physics Lab)',
                           'each_discard_recomputes_cheapest': True})
    if not completion['event_complete'] or len(discarded) != 2:
        completion['status'] = 'unknown'
        unknown.append('training_complete_event_or_discard_calls')

    discard_code = _code(script, DISCARD)
    remove_at = discard_code.find('lib1_gf_RemoveCardFromHand(')
    subtype_at = discard_code.find('.lv_subtype=="Unchained"')
    risk = {'id':'discard_subtype_read_after_compaction', 'status':'unknown'}
    if (functions[DISCARD]['status'] == 'observed_profile' and
            functions['lib1_gf_RemoveCardFromHand']['status'] == 'observed_profile' and
            0 <= remove_at < subtype_at):
        risk.update({'status':'static_candidate_risk',
                     'observation':'RemoveCardFromHand compacts hand including subtype before Unchained subtype read at the removed index.',
                     'runtime_verified':False, 'map_fix_applied':False})
    return {'validation':'static', 'profile_version':profile.get('version'),
            'script_sha256':script.sha256, 'functions':functions, 'edges':edges,
            'registrations':registrations, 'initialization':initialization,
            'production':training, 'completion':completion,
            'risks':[risk], 'unknown':sorted(set(unknown)),
            'profile_recognized':not unknown,
            'parser_scope':'Galaxy lexical masks, bracket spans, named calls; additive unitgroup definitions; no execution'}


def _catalog_view(session, kind, name):
    try:
        item = session.inspect(kind,name)
    except SC2Error as exc:
        if exc.code != 'catalog_object_not_found':
            raise
        return {'catalog':kind,'object_id':name,'status':'unknown','error':exc.as_dict()}
    return {'catalog':kind,'object_id':name,'status':'observed_static',
            'fields':item['fields'], 'removed':item['removed'],
            'inheritance':item['inheritance'], 'warnings':item['warnings'],
            'source_entries':session.source_entries(kind,name),
            'engine_parity':item.get('engine_parity')}


def audit_catalog(session) -> dict:
    """Resolve exact production slots and indexed addon mappings with provenance."""
    targets = [('Abil','TerranBuild'), ('Abil','StarportTrain'), ('Abil','StarportTrainSecretHangar'),
               ('Unit','StarportSecretHangar'), ('Unit','Starport'),
               ('Unit','Reactor'), ('Unit','TechLab'), ('Unit','PhysicsLab'),
               ('Behavior','StarportReactor'), ('Behavior','StarportTechLab'),
               ('Unit','Wraith'), ('Unit','RavenSecretHangarCovertOps'),
               ('Unit','BattlecruiserSecretHangarCovertOps')]
    objects = {f'{k}/{n}':_catalog_view(session,k,n) for k,n in targets}
    ab = objects['Abil/StarportTrainSecretHangar']
    fields = ab.get('fields',{})
    slots = []
    for slot, expected, index in [('Train2','RavenSecretHangarCovertOps',1),
                                   ('Train4','BattlecruiserSecretHangarCovertOps',3),
                                   ('Train6','Wraith',5)]:
        prefix = f'InfoArray[{slot}]'
        products = {key:value for key,value in fields.items()
                    if re.fullmatch(re.escape(prefix) + r'\.Unit(?:\[\d+\])?',key)}
        warnings = [w for w in ab.get('warnings',[]) if w.get('code') in
                    ('missing_catalog_parent','catalog_class_changed','unknown_removed_value','unevaluated_catalog_expression')]
        slots.append({'slot':slot,'command_index':index,'products':products,
                      'time':fields.get(prefix+'.Time'),
                      'requirements':fields.get(prefix+'.Button.Requirements'),
                      'status':'observed_static' if set(products)=={prefix+'.Unit[0]'} and
                          next(iter(products.values()))['value']==expected and not warnings else 'unknown',
                      'runtime_acceptance':'not_run'})
    addons=[]
    for addon in ['Reactor','TechLab','PhysicsLab']:
        af=objects[f'Unit/{addon}'].get('fields',{})
        links=[{'path':key,'unit':v,'behavior':af.get(key.removesuffix('UnitLink')+'BehaviorLink')}
               for key,v in af.items() if key.endswith('.UnitLink') and key.startswith('AddedOnArray[')
               and v['value']=='StarportSecretHangar']
        addons.append({'addon':addon,'links':links,'duplicate_mapping':len(links)>1,
                       'status':'observed_static' if links else 'unknown'})
    layouts = {key:value for key,value in objects['Unit/StarportSecretHangar'].get('fields',{}).items()
               if '.AbilCmd' in key and value['value'].startswith('StarportTrain,')}
    return {'objects':objects,'slots':slots,'addons':addons,
            'inherited_ordinary_train_button_refs':layouts,
            'layout_note':'Static merged fields only; indexed command-card merge is not UI visibility or engine acceptance.'}


def audit_secret_hangar(root: Path, *, source_context: dict | None = None) -> dict:
    """Public read-only API; context is checked both before and after audit."""
    root = Path(root).resolve()
    profile = json.loads((Path(__file__).parent/'profiles/secret_hangar_profile.json').read_text(encoding='utf-8'))
    if source_context is not None:
        if Path(source_context.get('root','')).resolve()!=root:
            raise SC2Error('secret_hangar_context_mismatch','SourceContext 与地图不匹配')
        before=assert_source_context_current(source_context)
        roots=[Path(p) for p in source_context['roots']]
    else:
        before={'current':None,'source_context_id':None}
        roots=[root]
    text=root/'zhCN.SC2Data/LocalizedData/GameStrings.txt'
    text_sha256=_hash(text.read_bytes())
    script_raw=(root/'MapScript.galaxy').read_bytes()
    script=audit_script(script_raw,profile)
    cards=[]
    for name in ['Secret Hangar','Reactor','Tech Lab','Physics Lab','Underground Base']:
        card=inspect_keystone_card(root,name=name)
        if card['script_sha256']!=script['script_sha256']:
            raise SC2Error('secret_hangar_source_changed','卡牌检查期间脚本已变化')
        cards.append(card)
    parsed = parse_script(script_raw)
    card_registrations=[]
    for card in cards:
        registration = card['registration_function']
        initializer = registration.removesuffix('_Func')+'_Init'
        code = _code(parsed,initializer)
        trigger = registration.removesuffix('_Func')
        registration_known = script['functions'].get(registration,{}).get('status')=='observed_profile'
        initializer_known = script['functions'].get(initializer,{}).get('status')=='observed_profile'
        root_known = script['initialization']['status']=='observed_profile'
        card_registrations.append({'card_id':card['card_id'],'function':registration,
            'initializer':initializer,
            'registration_profile_recognized':registration_known,
            'initializer_profile_recognized':initializer_known,
            'root_initialization_profile_recognized':root_known,
            'trigger_created':initializer_known and registration_known and f'{trigger}=TriggerCreate("{registration}");' in code,
            'map_init_event':initializer_known and f'TriggerAddEventMapInit({trigger});' in code,
            'initialized':root_known and initializer_known and registration_known and any(c.name==initializer for c in _calls(parsed,'lib1_InitTriggers')),
            'initializer_source':code})
    session=CatalogSession(roots)
    catalog=audit_catalog(session)
    fingerprints=session.file_fingerprints()
    fingerprints[str(root/'MapScript.galaxy')]=_hash(script_raw)
    fingerprints[str(text)]=text_sha256
    changed=[path for path,h in fingerprints.items() if _hash(Path(path).read_bytes())!=h]
    if changed:
        raise SC2Error('secret_hangar_source_changed','审计期间来源变化',paths=changed)
    after=assert_source_context_current(source_context) if source_context is not None else before
    unknown=[]
    if source_context is None:
        unknown.append({'code':'source_context_missing','scope':'dependency closure unverified'})
    elif not source_context.get('complete'):
        unknown.extend(source_context.get('unknown',source_context.get('warnings',[])))
        unknown.append({'code':'source_context_incomplete','scope':'dependency identities or metadata unresolved'})
    static_recognized = (script['profile_recognized'] and
        all(slot['status']=='observed_static' for slot in catalog['slots']) and
        all(all(row[key] for key in ('trigger_created','map_init_event','initialized')) for row in card_registrations))
    return {'workflow':'secret_hangar_impact_audit','root':str(root),'validation':'static',
            'source_context_before':before,'source_context_after':after,
            'source_context_complete':source_context.get('complete') if source_context else False,
            'source_unknown':unknown,'cards':cards,'card_registrations':card_registrations,
            'script':script,'catalog':catalog,
            'source_file_sha256':fingerprints,'read_only_verified':True,
            'overall':'observed_static_with_unknowns' if static_recognized else 'unknown',
            'static_profile_recognized':static_recognized,
            'acceptance':{'static':'performed','editor':'not_run','runtime':'not_run','visual':'not_run'},
            'scope':'Card registration -> builder -> battle-phase production -> addon -> train-complete -> discard -> Junkboss queue/direct response. Combat/assets use unit_variant separately.'}
