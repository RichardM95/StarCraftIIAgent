import hashlib

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.script_guard import guard, plan_guarded_replace


SOURCE = b'''bool f(bool testConds, bool runActions) {
    int counter = 0;
    if (testConds) { if (counter < 1) { return false; } }
    if (!runActions) { return true; }
    while (counter < 4) { Counter(counter); counter += 1; }
    Wait(1.0, c_timeGame);
    TriggerExecute(other, true, false);
    return true;
}
void f_Init() { t = TriggerCreate("f"); }
void InitMap() { f_Init(); }
'''


@pytest.mark.parametrize('old,new', [
    (b'int counter = 0;', b''),
    (b'while (counter < 4) { Counter(counter); counter += 1; }', b'Counter(0);'),
    (b'Wait(1.0, c_timeGame);', b''),
    (b'TriggerExecute(other, true, false);', b'TriggerExecute(other, true, true);'),
    (b'TriggerCreate("f")', b'TriggerCreate("missing")'),
    (b'return false;', b'return true;'),
    (b'f_Init();', b''),
])
def test_guard_rejects_simplification_emptying_phase_and_callback_changes(old, new):
    assert guard(SOURCE, SOURCE.replace(old,new))['passed'] is False


def test_reorder_and_empty_function_rejected():
    assert not guard(SOURCE, SOURCE.replace(b'Wait(1.0, c_timeGame);\n    TriggerExecute(other, true, false);',
                                          b'TriggerExecute(other, true, false);\n    Wait(1.0, c_timeGame);'))['passed']
    assert not guard(SOURCE, b'bool f(bool testConds, bool runActions) { return true; }')['passed']


def test_exact_candidate_guard_preserves_unchanged_bytes_and_does_not_write(tmp_path):
    path = tmp_path/'MapScript.galaxy'
    path.write_bytes(SOURCE)
    result = plan_guarded_replace(tmp_path, 'counter < 4', 'counter < 5', hashlib.sha256(SOURCE).hexdigest(),
                                  {'author':'a','reviewer':'b','evidence':'review-leaf-1'})
    assert result['MapScript.galaxy'] == SOURCE.replace(b'counter < 4', b'counter < 5')
    assert path.read_bytes() == SOURCE
    assert not guard(SOURCE, result['MapScript.galaxy'])['passed']
    with pytest.raises(SC2Error):
        plan_guarded_replace(tmp_path, 'Wait(1.0, c_timeGame);', '', hashlib.sha256(SOURCE).hexdigest())


def test_guard_reports_ordered_structure_fingerprints():
    result = guard(SOURCE, SOURCE)
    assert result['passed'] is True
    assert len(result['before_structure_sha256']) == 64
    assert result['before_structure_sha256'] == result['after_structure_sha256']


@pytest.mark.parametrize('before,after',[
    (b'void f(){int x=0; x=x+1;}',b'void f(){int x=0;}'),
    (b'void f(){if(x){A();} B();}',b'void f(){if(x){A();B();}}'),
    (b'void f(){int x=Fetch();}',b'void f(){int x; Fetch();}'),
])
def test_every_assignment_scope_and_initialization_is_protected(before,after):
    assert not guard(before,after)['passed']


def test_review_cannot_exempt_complete_function_deletion():
    with pytest.raises(SC2Error):
        guard(SOURCE,b'', [{'old':SOURCE.decode(),'new':'','author':'a','reviewer':'b','evidence':'x'}])
