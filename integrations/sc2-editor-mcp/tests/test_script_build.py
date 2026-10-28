import hashlib
import json
from xml.etree import ElementTree as ET

import pytest
from sc2_mcp.errors import SC2Error

from sc2_mcp import script_build as builder

SOURCE=b'''trigger gt_Test;
bool Test (bool testConds, bool runActions) {
    if (!runActions) {
        return true;
    }
    return true;
}
void Test_Init () {
    gt_Test = TriggerCreate("Test");
    TriggerAddEventMapInit(gt_Test);
}
'''


def sha(data):return hashlib.sha256(data).hexdigest()


def fixture(tmp_path, source=SOURCE):
    (tmp_path/'source').mkdir(exist_ok=True)
    (tmp_path/'source/a.galaxy').write_bytes(source)
    manifest={'schema':'sc2-script-build/1','files':[{'path':'source/a.galaxy','sha256':sha(source)}],
              'init_functions':['Test_Init']}
    save(tmp_path,manifest)
    return manifest


def save(root,manifest):
    (root/'source/manifest.json').write_text(json.dumps(manifest),'utf8')


def assert_code(code, fn):
    with pytest.raises(SC2Error) as error:fn()
    assert error.value.code==code


def test_source_bytes_order_xml_and_no_writes(tmp_path):
    source=SOURCE.replace(b'    return true;\n}', '    string lv_display = "保留 <>& 字符";\n    return true;\n}'.encode('utf8'),1)
    fixture(tmp_path,source)
    before={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    candidate=builder.plan_script_build(tmp_path,'source/manifest.json')
    assert candidate['MapScript.galaxy'].count(source)==1
    xml=ET.fromstring(candidate['Triggers'])
    code=xml.findtext('./Element/ScriptCode')
    deindented='\n'.join(line[12:] for line in code.splitlines() if line.strip())
    assert builder.galaxy_tokens(deindented.encode('utf8'))==builder.galaxy_tokens(source+b'void MCP_SourceManifest_Init () { Test_Init(); }\n')
    assert xml.findtext('./Element/InitFunc')=='MCP_SourceManifest_Init'
    assert {p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}==before
    assert builder.inspect_script_build(tmp_path,'source/manifest.json')['native_compile_verified'] is False


def test_files_and_init_lists_keep_order(tmp_path):
    manifest=fixture(tmp_path)
    extra=b'void Last_Init () {\n}\n'
    (tmp_path/'source/b.galaxy').write_bytes(extra)
    manifest['files'].append({'path':'source/b.galaxy','sha256':sha(extra)})
    manifest['init_functions']=['Last_Init','Test_Init']
    save(tmp_path,manifest)
    data=builder.plan_script_build(tmp_path,'source/manifest.json')['MapScript.galaxy']
    assert data.index(SOURCE)<data.index(extra)
    assert b'    Last_Init();\n    Test_Init();' in data


@pytest.mark.parametrize(('source','code'),[
    (SOURCE+SOURCE,'SCRIPT_BUILD_DUPLICATE_FUNCTION'),
    (SOURCE.replace(b'"Test"',b'"Missing"'),'SCRIPT_BUILD_CALLBACK_MISSING'),
    (SOURCE.replace(b'bool Test (bool testConds, bool runActions)',b'int Test (bool testConds, bool runActions)'),'SCRIPT_BUILD_CALLBACK_SIGNATURE'),
    (SOURCE.replace(b'TriggerCreate("Test")',b'TriggerCreate(lv_callback)'),'SCRIPT_BUILD_DYNAMIC_CALLBACK'),
    (SOURCE.replace(b'void Test_Init ()',b'bool Test_Init ()'),'SCRIPT_BUILD_INIT_SIGNATURE'),
    (SOURCE.rstrip(b'\n'),'SCRIPT_BUILD_SOURCE_BOUNDARY'),
    (SOURCE+b'/* never closed\n','SCRIPT_BUILD_UNSUPPORTED_TOKEN'),
    (SOURCE+b'void InitMap () { }\n','SCRIPT_BUILD_RESERVED_FUNCTION'),
    (b'','SCRIPT_BUILD_EMPTY_SOURCE'),
])
def test_invalid_sources_fail_closed(tmp_path,source,code):
    fixture(tmp_path,source)
    assert_code(code,lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


def test_hash_and_manifest_binding(tmp_path):
    fixture(tmp_path)
    manifest_path=tmp_path/'source/manifest.json'
    expected=sha(manifest_path.read_bytes())
    (tmp_path/'source/a.galaxy').write_bytes(SOURCE+b'// changed\n')
    assert_code('SCRIPT_BUILD_SOURCE_STALE',lambda:builder.plan_script_build(tmp_path,'source/manifest.json',expected))
    (tmp_path/'source/a.galaxy').write_bytes(SOURCE)
    manifest_path.write_bytes(manifest_path.read_bytes()+b' ')
    assert_code('SCRIPT_BUILD_MANIFEST_STALE',lambda:builder.plan_script_build(tmp_path,'source/manifest.json',expected))


def bind_existing(root,manifest,old_script,old_triggers=b'<TriggerData/>'):
    (root/'MapScript.galaxy').write_bytes(old_script)
    (root/'Triggers').write_bytes(old_triggers)
    (root/'source/baseline.galaxy').write_bytes(old_script)
    manifest['baseline']={'map_script_sha256':sha(old_script),'triggers_sha256':sha(old_triggers),
                          'files':[{'path':'source/baseline.galaxy','sha256':sha(old_script)}]}
    save(root,manifest)


def test_existing_stable_logic_requires_complete_binding(tmp_path):
    manifest=fixture(tmp_path)
    old=b'include "TriggerLibs/natives"\nvoid Old () { }\nvoid InitMap () { Old(); }\n'
    (tmp_path/'MapScript.galaxy').write_bytes(old)
    assert_code('SCRIPT_BUILD_BASELINE_REQUIRED',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))
    bind_existing(tmp_path,manifest,old)
    assert_code('SCRIPT_BUILD_FUNCTION_REMOVAL',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))
    (tmp_path/'source/baseline.galaxy').write_bytes(b'void InitMap () { }\n')
    manifest['baseline']['files'][0]['sha256']=sha((tmp_path/'source/baseline.galaxy').read_bytes())
    save(tmp_path,manifest)
    assert_code('SCRIPT_BUILD_BASELINE_INCOMPLETE',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


def test_unknown_trigger_layout_never_overwritten(tmp_path):
    manifest=fixture(tmp_path)
    old=b'void InitMap () { }\n'
    bind_existing(tmp_path,manifest,old,b'<TriggerData><Root/><Library Id="PreserveMe"/></TriggerData>')
    assert_code('SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


@pytest.mark.parametrize(('old','candidate','code'),[
    (b'int state = 1;\nvoid Test_Init () { state = 5; }\nvoid InitMap () { }\n',
     b'int state = 1;\nvoid Test_Init () { }\n', 'SCRIPT_BUILD_EXISTING_SOURCE_CHANGED'),
    (b'int state = 1;\nvoid Test_Init () { state = 5; }\nvoid InitMap () { }\n',
     b'int state = 0;\nvoid Test_Init () { state = 5; }\n', 'SCRIPT_BUILD_EXISTING_SOURCE_CHANGED'),
    (b'void Test_Init () { }\nvoid InitMap () { Test_Init(); }\n',
     b'void Test_Init () { }\n', 'SCRIPT_BUILD_INIT_MIGRATION_REQUIRED'),
])
def test_build_cannot_remove_existing_body_globals_or_init(tmp_path,old,candidate,code):
    manifest=fixture(tmp_path,candidate)
    bind_existing(tmp_path,manifest,old)
    assert_code(code,lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


def test_owned_build_allows_append_preserving_all_old_logic_and_init(tmp_path):
    manifest=fixture(tmp_path)
    original=builder.plan_script_build(tmp_path,'source/manifest.json')
    extra=b'void Last_Init () {\n}\n'
    (tmp_path/'source/a.galaxy').write_bytes(SOURCE+extra)
    manifest['files'][0]['sha256']=sha(SOURCE+extra)
    manifest['init_functions'].append('Last_Init')
    bind_existing(tmp_path,manifest,original['MapScript.galaxy'],original['Triggers'])
    result=builder.plan_script_build(tmp_path,'source/manifest.json')
    assert SOURCE+extra in result['MapScript.galaxy']
    manifest['init_functions']=['Last_Init','Test_Init']
    save(tmp_path,manifest)
    assert_code('SCRIPT_BUILD_INIT_REMOVAL',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


@pytest.mark.parametrize('triggers',[
    b'<TriggerData Unknown="keep"/>',
    b'<TriggerData><Root Unknown="keep"/></TriggerData>',
    b'<TriggerData><!--preserve unknown--></TriggerData>',
])
def test_unknown_trigger_metadata_rejected(tmp_path,triggers):
    manifest=fixture(tmp_path)
    bind_existing(tmp_path,manifest,b'void InitMap () { }\n',triggers)
    assert_code('SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))


def test_trigger_roundtrip_tokens_are_not_compiler_success(tmp_path):
    manifest=fixture(tmp_path)
    candidate=builder.plan_script_build(tmp_path,'source/manifest.json')
    native=tmp_path/'native'
    native.mkdir()
    for relative,data in candidate.items():(native/relative).write_bytes(data.replace(b'\n',b'\r\n'))
    evidence=builder.compare_native_roundtrip(tmp_path,'source/manifest.json',native)
    assert evidence['source_agreement'] is True
    assert evidence['native_compile_verified'] is False
    path=native/'MapScript.galaxy'
    path.write_bytes(path.read_bytes().replace(b'return true;',b'return false;',1))
    assert_code('SCRIPT_BUILD_NATIVE_SOURCE_MISMATCH',lambda:builder.compare_native_roundtrip(tmp_path,'source/manifest.json',native))


@pytest.mark.parametrize('path',['../a.galaxy','source/../a.galaxy','source//a.galaxy','C:/a.galaxy','source\\a.galaxy'])
def test_unsafe_source_paths(tmp_path,path):
    manifest=fixture(tmp_path)
    manifest['files'][0]['path']=path
    save(tmp_path,manifest)
    assert_code('SCRIPT_BUILD_PATH',lambda:builder.plan_script_build(tmp_path,'source/manifest.json'))
