"""Tests for the localization domain API (synthetic temporary fixtures only)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sc2_mcp.errors import SC2Error  # noqa: E402
from sc2_mcp import localization  # noqa: E402

BOM = b"\xef\xbb\xbf"


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _fixture(root: Path) -> Path:
    text = (
        "KeyA=Value A\r\n"
        "KeyB=Value B\r\n"
        "KeyA=Value A2\r\n"
        "NoEqualsLine\r\n"
        "= EmptyKey\r\n"
        "// a comment line\r\n"
    )
    return _write(root, "zhCN.SC2Data/LocalizedData/GameStrings.txt", BOM + text.encode("utf-8"))


def test_inspect_reports_keys_duplicates_malformed_bom_and_newlines(tmp_path):
    _fixture(tmp_path)

    result = localization.inspect_localization(tmp_path, locale="zhCN")

    assert result["locale"] == "zhCN"
    assert result["files"] == ["zhCN.SC2Data/LocalizedData/GameStrings.txt"]
    assert result["keys"] == ["KeyA", "KeyB"]
    assert result["key_count"] == 2
    assert result["entry_count"] == 3
    assert result["bom"] == {"zhCN.SC2Data/LocalizedData/GameStrings.txt": True}
    assert result["newlines"] == {"zhCN.SC2Data/LocalizedData/GameStrings.txt": "crlf"}

    dupes = {d["key"]: d["count"] for d in result["duplicates"]}
    assert dupes == {"KeyA": 2}
    reasons = {m["reason"] for m in result["malformed"]}
    assert len(result["malformed"]) == 2
    assert any("separator" in r for r in reasons)
    assert any("empty key" in r for r in reasons)

    # Every returned inspection object must be JSON serializable.
    import json

    json.dumps(result)


def test_plan_set_edits_only_matched_line_and_preserves_bom_crlf(tmp_path):
    path = _fixture(tmp_path)
    original = path.read_bytes()

    changes = localization.plan_localization_set(tmp_path, {"KeyB": "New B"}, locale="zhCN")

    assert list(changes) == ["zhCN.SC2Data/LocalizedData/GameStrings.txt"]
    candidate = changes["zhCN.SC2Data/LocalizedData/GameStrings.txt"]
    assert candidate.startswith(BOM)
    text = candidate[len(BOM):].decode("utf-8")
    assert "KeyB=New B\r\n" in text
    assert "KeyA=Value A\r\n" in text
    assert "KeyA=Value A2\r\n" in text
    assert "\n" in text and "\r\n" in text
    # No lone LF was introduced.
    assert text.replace("\r\n", "").count("\n") == 0
    # The planner did not touch the source file.
    assert path.read_bytes() == original


def test_plan_set_appends_new_key_with_existing_newline_convention(tmp_path):
    rel = "enUS.SC2Data/LocalizedData/GameStrings.txt"
    _write(tmp_path, rel, b"A=1\nB=2\n")

    changes = localization.plan_localization_set(tmp_path, {"C": "3"}, locale="enUS")

    assert changes[rel] == b"A=1\nB=2\nC=3\n"


def test_plan_set_appends_to_file_without_trailing_newline(tmp_path):
    rel = "enUS.SC2Data/LocalizedData/GameStrings.txt"
    _write(tmp_path, rel, b"A=1")

    changes = localization.plan_localization_set(tmp_path, {"C": "3"}, locale="enUS")

    assert changes[rel] == b"A=1\nC=3\n"


def test_plan_set_rejects_duplicate_key(tmp_path):
    _fixture(tmp_path)

    with pytest.raises(SC2Error) as excinfo:
        localization.plan_localization_set(tmp_path, {"KeyA": "x"}, locale="zhCN")

    assert excinfo.value.code == "LOCALIZATION_DUPLICATE_KEY"


def test_plan_set_rejects_newline_injection_and_bad_keys(tmp_path):
    _fixture(tmp_path)

    with pytest.raises(SC2Error) as excinfo:
        localization.plan_localization_set(tmp_path, {"KeyB": "line1\nline2"}, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_NEWLINE_INJECTION"

    with pytest.raises(SC2Error) as excinfo:
        localization.plan_localization_set(tmp_path, {"Bad Key": "x"}, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_INVALID_KEY"

    with pytest.raises(SC2Error) as excinfo:
        localization.plan_localization_set(tmp_path, {"Bad=Key": "x"}, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_INVALID_KEY"


def test_missing_source_raises_specific_error(tmp_path):
    with pytest.raises(SC2Error) as excinfo:
        localization.inspect_localization(tmp_path, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_SOURCE_MISSING"

    with pytest.raises(SC2Error) as excinfo:
        localization.plan_localization_set(tmp_path, {"A": "b"}, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_SOURCE_MISSING"


def test_invalid_utf8_is_rejected(tmp_path):
    rel = "zhCN.SC2Data/LocalizedData/GameStrings.txt"
    _write(tmp_path, rel, b"A=\xff\xfe\n")

    with pytest.raises(SC2Error) as excinfo:
        localization.inspect_localization(tmp_path, locale="zhCN")
    assert excinfo.value.code == "LOCALIZATION_ENCODING_INVALID"


def test_empty_updates_plan_nothing(tmp_path):
    _fixture(tmp_path)
    assert localization.plan_localization_set(tmp_path, {}, locale="zhCN") == {}
