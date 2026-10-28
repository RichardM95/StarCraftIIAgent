"""Additional terminal verdict checks; no native process is launched."""
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.probe_bank import parse_probe_bank


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("existing_probe_review_fixture", ROOT / "tests/test_probe_independent_review.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    return FIXTURE.prepared.__wrapped__(tmp_path, monkeypatch)


def parsed(manifest, observed):
    root = ET.Element("Bank")
    for section_name, values in {
        "Run": {"RunId": manifest["run_id"], "Status": "STARTED"},
        "Catalog": {"StageStatus": "STARTED", **({"LifeMax": "45"} if observed else {})},
    }.items():
        section = ET.SubElement(root, "Section", name=section_name)
        for key, value in values.items():
            ET.SubElement(ET.SubElement(section, "Key", name=key), "Value", string=value)
    raw = ET.tostring(root)
    assertion = {"id":"life", "section":"Catalog", "key":"LifeMax", "operator":"eq", "expected":"46"}
    return raw, parse_probe_bank(raw, manifest["run_id"], ["Catalog"], [assertion])


@pytest.mark.parametrize("terminal", ["cancelled", "timed_out", "interrupted", "failed"])
def test_terminal_manifest_synchronizes_observed_failure(prepared, terminal):
    manager, manifest, _ = prepared
    manifest.update(state=terminal, execution="partial", verdict="partial")
    manager.save(manifest)
    raw, result = parsed(manifest, True)
    assert result["verdict"] == "failed"
    manager.save(dict(manifest), result, raw)
    stored = manager.read(manifest["probe_id"])
    assert stored["state"] == terminal and stored["verdict"] == "failed"
    assert result["verdict"] == "failed" and result["termination_reason"] == terminal


@pytest.mark.parametrize("terminal", ["cancelled", "timed_out", "interrupted", "failed"])
def test_late_missing_observation_cannot_erase_terminal_failure(prepared, terminal):
    manager, manifest, _ = prepared
    manifest.update(state=terminal, execution="partial", verdict="partial")
    manager.save(manifest)
    failed_raw, failed = parsed(manifest, True)
    manager.save(dict(manifest), failed, failed_raw)
    late_raw, late = parsed(manifest, False)
    assert late["verdict"] == "partial"
    manager.save(dict(manifest), late, late_raw)
    assert manager.read(manifest["probe_id"])["verdict"] == "failed"
    assert late["verdict"] == "failed"
    assert (manager.folder(manifest["probe_id"]) / "result.SC2Bank").read_bytes() == failed_raw


@pytest.mark.parametrize("terminal", ["cancelled", "timed_out", "interrupted", "failed"])
def test_more_complete_evidence_is_accepted_without_promoting_terminated_run(prepared, terminal):
    manager, manifest, _ = prepared
    manifest.update(state=terminal, execution="partial", verdict="partial")
    manager.save(manifest)
    failed_raw, failed = parsed(manifest, True)
    manager.save(dict(manifest), failed, failed_raw)
    root = ET.fromstring(failed_raw)
    root.find('./Section[@name="Run"]/Key[@name="Status"]/Value').set("string", "FINISHED")
    root.find('./Section[@name="Catalog"]/Key[@name="StageStatus"]/Value').set("string", "FINISHED")
    root.find('./Section[@name="Catalog"]/Key[@name="LifeMax"]/Value').set("string", "46")
    raw = ET.tostring(root)
    assertion = {"id":"life", "section":"Catalog", "key":"LifeMax", "operator":"eq", "expected":"46"}
    result = parse_probe_bank(raw, manifest["run_id"], ["Catalog"], [assertion])
    assert result["verdict"] == "complete"
    manager.save(dict(manifest), result, raw)
    assert result["execution"]["state"] == "complete" and result["verdict"] == "partial"
    assert result["assertions"][0]["result"] == "passed"
    assert manager.read(manifest["probe_id"])["state"] == terminal
    assert (manager.folder(manifest["probe_id"]) / "result.SC2Bank").read_bytes() == raw
