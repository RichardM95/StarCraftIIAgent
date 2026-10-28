from pathlib import Path

from sc2_mcp.worker_bridge import PROTOCOL, execute_envelope


def _request(operation, request_id="test-1", **arguments):
    return {"protocol": PROTOCOL, "id": request_id, "operation": operation, "arguments": arguments}


def test_capabilities_and_cliff_boundary_are_explicit(tmp_path):
    capabilities = execute_envelope(tmp_path, _request("capabilities"))
    assert capabilities["ok"] is True
    assert "data_warnings_plan" in capabilities["result"]["operations"]

    cliff = execute_envelope(tmp_path, _request("cliff_capability_status", request_id="cliff"))
    assert cliff["ok"] is True
    assert cliff["result"]["native_cliff_topology_generation"] == "blocked"


def test_warning_plan_materializes_candidate_without_touching_source(tmp_path):
    (tmp_path / "Base.SC2Data/GameData").mkdir(parents=True)
    actor = tmp_path / "Base.SC2Data/GameData/ActorData.xml"
    actor.write_text(
        '<Catalog>\n'
        '  <CActorUnit id="ScientistNarud">\n'
        '    <Model value="DrNarud"/>\n'
        '    <ModelBuild value="DrNarud"/>\n'
        '    <ModelPlacement value="DrNarud"/>\n'
        '  </CActorUnit>\n'
        '</Catalog>\n', encoding="utf-8")
    log = tmp_path / "editor.log"
    log.write_text(
        "[10/27/2026 7:54:04 上午] 警告: XML: "
        f"{actor}(4,9) : Unable to find field ModelBuild  Source: {tmp_path}/"
        "  Entry: ScientistNarud  Scope: CActorUnit\n"
        "[10/27/2026 7:54:04 上午] 警告: XML: "
        f"{actor}(5,9) : Unable to find field ModelPlacement  Source: {tmp_path}/"
        "  Entry: ScientistNarud  Scope: CActorUnit\n", encoding="utf-8")
    before = actor.read_bytes()
    result = execute_envelope(tmp_path, _request("data_warnings_plan", request_id="repair-1",
                                                  log_path="editor.log"))
    assert result["ok"] is True
    payload = result["result"]
    assert payload["source_modified"] is False
    assert payload["materialized_candidate"]["candidate_relative"] == ".sc2-mcp/candidates/repair-1"
    assert actor.read_bytes() == before
    candidate = tmp_path / ".sc2-mcp/candidates/repair-1/Base.SC2Data/GameData/ActorData.xml"
    assert b"<BuildModel value=\"DrNarud\"/>" in candidate.read_bytes()


def test_bridge_rejects_unknown_and_unsafe_operations(tmp_path):
    bad = execute_envelope(tmp_path, {"protocol": PROTOCOL, "id": "bad", "operation": "cliff_write", "arguments": {}})
    assert bad["ok"] is False
    assert bad["error"]["code"] == "bridge_operation_blocked"

    malformed = execute_envelope(tmp_path, {"protocol": "wrong", "id": "bad", "operation": "capabilities"})
    assert malformed["ok"] is False
    assert malformed["error"]["code"] == "bridge_protocol_mismatch"
