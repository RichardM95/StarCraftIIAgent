import json

from sc2_mcp.terrain_capability import capability_status


def test_native_cliff_capabilities_are_fixed_blocked():
    result = capability_status()
    assert result['native_cliff_topology_generation'] == 'blocked'
    assert result['native_ramp_generation'] == 'blocked'
    assert result['cliff_editor_acceptance'] == 'blocked'
    assert result['write_policy'].startswith('普通施工路径不生成')
    json.dumps(result, ensure_ascii=False)
