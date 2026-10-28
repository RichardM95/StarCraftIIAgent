import hashlib

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.war3 import coverage, decode_source, inspect_jass, inspect_races


def test_jass_callbacks_source_hash_order_and_damaged_text():
    data = (b'globals\nstring title="bad\xef\xbc"\nendglobals\n'
            b'function child takes nothing returns nothing\ncall GetRandomInt(1,3)\nendfunction\n'
            b'function cb takes nothing returns nothing\ncall GetRandomInt(1,2)\nendfunction\n'
            b'function main takes nothing returns nothing\ncall child()\n'
            b'call TriggerAddAction(t,function cb)\ncall ExecuteFunc("cb")\nendfunction\n')
    text, report = decode_source(data)
    assert text.encode('utf-8', 'surrogateescape') == data
    assert report['invalid_bytes'][0]['hex'] == 'efbc'
    assert report['invalid_bytes'][0]['line'] == 2
    result = inspect_jass(data)
    assert result['reachable_count'] == 3
    assert result['functions'][0]['source_sha256'] == hashlib.sha256(data.split(b'function child')[1].split(b'function cb')[0].join([b'function child', b''])).hexdigest()
    assert [edge['kind'] for edge in result['edges']] == ['calls', 'code_references', 'literal_callback']
    assert result['complete'] is False


def test_literal_function_text_is_not_code_and_unknown_callback_remains():
    result = inspect_jass(b'function main takes nothing returns nothing\ncall Display("function fake call x()")\ncall ExecuteFunc(var)\nendfunction\n')
    assert [call['name'] for call in result['functions'][0]['calls']] == ['Display', 'ExecuteFunc']
    assert result['unresolved'][0]['kind'] == 'dynamic_callback'


def test_all_declared_string_and_code_callback_positions_are_traced():
    data = b'''native DzNewEvent takes integer id,string func returns nothing
native DzNewEventByCode takes integer id,code funcHandle returns nothing
function cb takes nothing returns nothing
endfunction
function main takes nothing returns nothing
call DzFrameSetScript(1,2,"cb",true)
call DzFrameSetUpdateCallback("cb")
call DzNewEvent(1,"cb")
call DzNewEventByCode(1,function cb)
call DzFrameSetScript(1,2,"",false)
call DzFrameSetUpdateCallback(var)
call DzTriggerRegisterSyncData(t,"prefix_not_a_callback",true)
endfunction
'''
    result = inspect_jass(data)
    assert result['reachable_count'] == 2
    assert result['callback_parameters']['DzNewEvent'] == [1]
    assert len(result['unresolved']) == 1
    assert result['unresolved'][0]['name'] == 'DzFrameSetUpdateCallback'


def test_race_uses_complete_selector_branch_and_nested_random_order():
    data = '''function main takes nothing returns nothing
if GetItemTypeId(GetManipulatedItem())=='gcel' then
call SetPlayerTechResearchedSwap('Rnsb',1,p)
if GetRandomInt(1,3)==1 then
call CreateNUnitsAtLoc(1,'H020',p,loc,0)
else
if GetRandomInt(1,2)==1 then
call CreateNUnitsAtLoc(1,'Hvsh',p,loc,0)
endif
endif
call SetUnitOwner(gg_unit_nnsa_0012,p,true)
call EnableTrigger(gg_trg_NJZL_00)
call Display("选择了栖浅娜迦|r")
else
endif
endfunction
'''.encode()
    result = inspect_races(data)
    assert result['race_count'] == 1
    race = result['races'][0]
    assert race['selector_rawcode'] == 'gcel'
    assert race['line_start'] == 2 and race['line_end'] == 15
    assert len(race['created_units']) == 2
    assert [call['line'] for call in race['random_calls']] == [4, 7]
    assert race['upgrades'][0]['arguments'] == ["'Rnsb'", '1', 'p']
    assert race['placed_unit_references'] == ['gg_unit_nnsa_0012']


def test_coverage_never_accepts_stale_or_self_review():
    result = inspect_jass(b'function main takes nothing returns nothing\nendfunction\n')
    record = {'source_function':'main','source_sha256':result['functions'][0]['source_sha256'],
              'implementation_path':'Scripts/main.galaxy','author':'a','reviewer':'a'}
    with pytest.raises(SC2Error, match='非作者'):
        coverage(result,[record])
    record['reviewer'] = 'b'
    assert coverage(result,[record])['bound_count'] == 1
    record['source_sha256'] = '0' * 64
    with pytest.raises(SC2Error):
        coverage(result,[record])


@pytest.mark.parametrize('data', [b'function main takes nothing returns nothing\n',
                                b'endfunction\n',
                                b'function main takes nothing returns nothing\nfunction sub takes nothing returns nothing\n'])
def test_malformed_functions_rejected(data):
    with pytest.raises(SC2Error):
        inspect_jass(data)
