import hashlib
import json

from sc2_mcp import script_build
from sc2_mcp.script_native_validation import inspect_native_gate


def test_native_gate_distinguishes_lexical_roundtrip_from_compile(tmp_path):
    source = b'void Test_Init () { }\n'
    source_dir = tmp_path / 'source'
    source_dir.mkdir()
    (source_dir / 'a.galaxy').write_bytes(source)
    manifest = {'schema': 'sc2-script-build/1',
                'files': [{'path': 'source/a.galaxy', 'sha256': hashlib.sha256(source).hexdigest()}],
                'init_functions': ['Test_Init']}
    (source_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    candidate = script_build.plan_script_build(tmp_path, 'source/manifest.json')
    native = tmp_path / 'native'
    native.mkdir()
    for path, data in candidate.items():
        (native / path).write_bytes(data)
    result = inspect_native_gate(tmp_path, 'source/manifest.json', native, tmp_path / 'installation', 'a' * 64)
    assert result['source_agreement']['source_agreement'] is True
    assert result['source_agreement']['native_compile_verified'] is False
    assert result['compile']['status'] == 'blocked'
    assert result['editor']['status'] == 'blocked'
    json.dumps(result)
