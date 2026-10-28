"""Tests for the script domain API (synthetic temporary fixtures only)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sc2_mcp.errors import SC2Error  # noqa: E402
from sc2_mcp import script  # noqa: E402

BOM = b"\xef\xbb\xbf"

SCRIPT_TEXT = (
    "// comment { unbalanced\n"
    "int gf_test(int a) {\n"
    '    string s = "brace } inside string";\n'
    "    return a + 1;\n"
    "}\n"
    "\n"
    "int gv_counter = 0;\n"
    "\n"
    "void init() {\n"
    "    gf_test(3);\n"
    "    UnitFromId(7);\n"
    "}\n"
)


def _write_script(root: Path, text: str, name: str = "MapScript.galaxy") -> Path:
    path = root / name
    path.write_bytes(text.encode("utf-8"))
    return path


def _write_script_bytes(root: Path, data: bytes, name: str = "MapScript.galaxy") -> Path:
    path = root / name
    path.write_bytes(data)
    return path


def test_inspect_script_ignores_strings_and_comments(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)

    result = script.inspect_script(tmp_path)

    assert result["files"] == ["MapScript.galaxy"]
    assert result["balanced"] is True
    assert result["diagnostics"] == []
    assert [f["name"] for f in result["functions"]] == ["gf_test", "init"]
    assert result["functions"][0]["params"] == ["int a"]
    assert result["functions"][0]["file"] == "MapScript.galaxy"

    names = {c["name"]: c for c in result["calls"]}
    assert names["gf_test"]["count"] == 1
    assert names["UnitFromId"]["count"] == 1

    assert [d["name"] for d in result["declarations"]] == ["s", "gv_counter"]
    assert [i["name"] for i in result["initializers"]] == ["gv_counter"]
    assert result["initializers"][0]["initializer"] == "0"

    assert result["spatial_refs"] == [{"kind": "UnitFromId", "args": "7", "line": 11, "file": "MapScript.galaxy"}]

    json.dumps(result)


def test_inspect_script_symbol_filter(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)

    result = script.inspect_script(tmp_path, symbol="gf")

    assert [f["name"] for f in result["functions"]] == ["gf_test"]
    assert [c["name"] for c in result["calls"]] == ["gf_test"]
    assert result["symbol_found"] is True

    missing = script.inspect_script(tmp_path, symbol="zzz")
    assert missing["functions"] == []
    assert missing["symbol_found"] is False


def test_inspect_script_unbalanced_braces_are_diagnostics(tmp_path):
    _write_script(tmp_path, "void init() {\n    gf_test(1);\n")

    result = script.inspect_script(tmp_path)

    assert result["balanced"] is False
    assert any(d["code"] == "SCRIPT_UNBALANCED_BRACES" for d in result["diagnostics"])


def test_plan_script_replace_exact_single_match(tmp_path):
    path = _write_script(tmp_path, SCRIPT_TEXT)
    original = path.read_bytes()
    sha = hashlib.sha256(original).hexdigest()

    changes = script.plan_script_replace(
        tmp_path, "return a + 1;", "return a + 2;", expected_sha256=sha
    )

    assert list(changes) == ["MapScript.galaxy"]
    candidate = changes["MapScript.galaxy"]
    assert b"return a + 2;" in candidate
    assert b"return a + 1;" not in candidate
    # Source untouched.
    assert path.read_bytes() == original


def test_plan_script_replace_preserves_crlf(tmp_path):
    text = "void init() {\r\n    gf_test(3);\r\n}\r\n"
    _write_script(tmp_path, text)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    changes = script.plan_script_replace(
        tmp_path,
        "void init() {\r\n    gf_test(3);\r\n}",
        "void init() {\n    gf_test(4);\n}",
        expected_sha256=sha,
    )

    candidate = changes["MapScript.galaxy"]
    assert candidate == b"void init() {\r\n    gf_test(4);\r\n}\r\n"
    assert b"\n" in candidate and candidate.replace(b"\r\n", b"").count(b"\n") == 0


def test_plan_script_replace_rejects_wrong_hash(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "return a + 1;", "return a + 2;", expected_sha256="0" * 64)

    assert excinfo.value.code == "SCRIPT_HASH_MISMATCH"
    assert excinfo.value.details["actual"] == hashlib.sha256(SCRIPT_TEXT.encode("utf-8")).hexdigest()


def test_plan_script_replace_rejects_missing_and_ambiguous_and_bad_hash(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)
    sha = hashlib.sha256(SCRIPT_TEXT.encode("utf-8")).hexdigest()

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "no_such_context()", "x", expected_sha256=sha)
    assert excinfo.value.code == "SCRIPT_MATCH_NOT_FOUND"

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "gf_test", "gf_other", expected_sha256=sha)
    assert excinfo.value.code == "SCRIPT_MATCH_AMBIGUOUS"

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "return a + 1;", "return a + 2;", expected_sha256="zz")
    assert excinfo.value.code == "SCRIPT_HASH_INVALID"


def test_plan_script_replace_rejects_unbalanced_result(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)
    sha = hashlib.sha256(SCRIPT_TEXT.encode("utf-8")).hexdigest()

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "return a + 1;", "return a + 1; }", expected_sha256=sha)

    assert excinfo.value.code == "SCRIPT_UNBALANCED_SYNTAX"


def test_plan_script_replace_rejects_bom_and_nul(tmp_path):
    _write_script_bytes(tmp_path, BOM + SCRIPT_TEXT.encode("utf-8"))
    sha = hashlib.sha256(BOM + SCRIPT_TEXT.encode("utf-8")).hexdigest()

    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "return a + 1;", "return a + 2;", expected_sha256=sha)
    assert excinfo.value.code == "SCRIPT_BOM_REJECTED"

    _write_script_bytes(tmp_path, b"void init() {\x00\n}\n")
    with pytest.raises(SC2Error) as excinfo:
        script.inspect_script(tmp_path)
    assert excinfo.value.code == "SCRIPT_NUL_REJECTED"


def test_script_source_missing(tmp_path):
    _write_script(tmp_path, SCRIPT_TEXT)
    with pytest.raises(SC2Error) as excinfo:
        script.plan_script_replace(tmp_path, "x", "y", expected_sha256="0" * 64)
    assert excinfo.value.code == "SCRIPT_MATCH_NOT_FOUND"

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SC2Error) as excinfo:
        script.inspect_script(empty)
    assert excinfo.value.code == "SCRIPT_SOURCE_MISSING"


def test_inspect_triggers(tmp_path):
    (tmp_path / "Triggers").write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<TriggerData>\n'
        b'  <Trigger Id="1"><Element Type="1"/></Trigger>\n'
        b'  <Variable Id="2" Type="unit"/>\n'
        b'  <Category Id="3"/>\n'
        b'</TriggerData>\n'
    )

    result = script.inspect_triggers(tmp_path)

    assert result["path"] == "Triggers"
    assert result["present"] is True
    assert result["root_tag"] == "TriggerData"
    assert len(result["triggers"]) == 1
    assert len(result["variables"]) == 1
    assert len(result["categories"]) == 1
    assert len(result["elements"]) == 1
    json.dumps(result)


def test_inspect_triggers_missing_and_invalid(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        script.inspect_triggers(tmp_path)
    assert excinfo.value.code == "TRIGGERS_SOURCE_MISSING"

    (tmp_path / "Triggers.xml").write_bytes(b"<TriggerData><Trigger></TriggerData>")
    with pytest.raises(SC2Error) as excinfo:
        script.inspect_triggers(tmp_path)
    assert excinfo.value.code == "TRIGGERS_XML_INVALID"


def test_inspect_script_reports_trigger_bindings_events_and_async_hazards(tmp_path):
    _write_script(tmp_path, """trigger gTrigger;
static int gParam;
bool GoodHandler(bool testConds, bool runActions) {
    Wait(1.0, c_timeGame);
    int captured = gParam;
    return true;
}
void BadHandler(int value, bool runActions) {
}
void Module_Init() {
    gTrigger = TriggerCreate("GoodHandler");
    TriggerAddEventMapInit(gTrigger);
    TriggerExecute(gTrigger, false, true);
    TriggerCreate("MissingHandler");
    TriggerCreate("BadHandler");
}
void InitMap() {
    Module_Init();
}
""")

    result = script.inspect_script(tmp_path)

    bindings = {item["target_function"]: item for item in result["trigger_bindings"]}
    assert bindings["GoodHandler"]["handler_status"] == "valid"
    assert bindings["GoodHandler"]["event_count"] == 1
    assert bindings["GoodHandler"]["execution_count"] == 1
    assert bindings["MissingHandler"]["handler_status"] == "missing"
    assert bindings["BadHandler"]["handler_status"] == "signature_mismatch"

    assert result["trigger_events"][0]["event_function"] == "TriggerAddEventMapInit"
    assert result["trigger_events"][0]["registration_status"] == "bound"
    assert result["trigger_exec"][0]["separate_thread"] is True
    assert result["trigger_exec"][0]["target_has_wait"] is True
    assert any(item["code"] == "TRIGGER_EXECUTE_THREAD_WITH_WAIT" for item in result["async_hazards"])
    assert any(item["code"] == "STATIC_PARAM_NOT_CAPTURED_BEFORE_WAIT" for item in result["async_hazards"])
    assert any(item["code"] == "TRIGGER_HANDLER_SIGNATURE" for item in result["signature_issues"])
    assert any(item["symbol"] == "MissingHandler" for item in result["unresolved_symbols"])
    assert result["init_chain"][0]["callee"] == "Module_Init"
    json.dumps(result)


def test_inspect_script_reports_unregistered_trigger_and_style_rules(tmp_path):
    _write_script(tmp_path, """void UnusedHandler(bool testConds, bool runActions) {
    return true;
}
void Init() {
    trigger unused;
    unused = TriggerCreate("UnusedHandler");
    int value = 0;
    value++;
}
""")

    result = script.inspect_script(tmp_path)

    assert any(item["code"] == "TRIGGER_NO_EVENT_OR_EXECUTE" for item in result["async_hazards"])
    assert any(item["code"] == "GALAXY_INCREMENT_OPERATOR" for item in result["galaxy_style_diagnostics"])
