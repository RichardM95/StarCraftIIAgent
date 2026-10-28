"""Independent named-chain review; pure snapshots and temporary maps only."""
import importlib.util
import json
import os
from pathlib import Path

import pytest
from sc2_mcp.errors import SC2Error
from sc2_mcp.source_context import prepare_source_context


PROJECT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file() and (parent / "src/sc2_mcp").is_dir())
TASK = PROJECT / "workspace/enhancement-20261016/tasks/secret_hangar_audit"
TARGET = Path(os.environ.get("SC2_SECRET_AUDIT_REVIEW_TARGET", str(PROJECT / "src/sc2_mcp/secret_hangar_audit.py")))
spec = importlib.util.spec_from_file_location("secret_hangar_review_target", TARGET)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURE = Path(os.environ.get("SC2_SECRET_AUDIT_REVIEW_FIXTURE", str(PROJECT / "tests/fixtures/secret_hangar/named_chain_fixture.galaxy")))
RAW = FIXTURE.read_bytes()
PROFILE = json.loads((TARGET.parent / "profiles/secret_hangar_profile.json").read_text(encoding="utf-8"))


def replace_inside(name, old, new):
    parsed = module.parse_script(RAW)
    function = parsed.function(name)
    code = parsed.text[function.start:function.end]
    assert old in code
    return (parsed.text[:function.start] + code.replace(old, new, 1) + parsed.text[function.end:]).encode("utf-8")


@pytest.mark.parametrize("name,statement", [
    ("lib1_gt_UnitFinishesTraining_Init", "TriggerAddEventUnitTrainProgress(lib1_gt_UnitFinishesTraining, null, c_unitProgressStageComplete);"),
    ("lib1_InitTriggers", "lib1_gt_UnitFinishesTraining_Init();"),
])
def test_unreachable_initializer_wiring_never_retains_recognized_profile(name, statement):
    baseline = module.audit_script(RAW, PROFILE)
    assert baseline["profile_recognized"], baseline["unknown"]
    raw = replace_inside(name, statement, "if (false) { " + statement + " }")
    result = module.audit_script(raw, PROFILE)
    assert not result["profile_recognized"], result["registrations"]
    assert result["unknown"]


def temporary_map(tmp_path):
    root = tmp_path / "named.SC2Map"
    root.mkdir()
    baseline = module.audit_script(RAW, PROFILE)
    assert baseline["profile_recognized"], baseline["unknown"]
    names = ["Secret Hangar", "Reactor", "Tech Lab", "Physics Lab", "Underground Base"]
    script = RAW + b"\nconst int lib1_gv_mAX_CARD_ID = 946;\n"
    (root / "MapScript.galaxy").write_bytes(script)
    (root / "DocumentInfo").write_bytes(b"<DocInfo/>")
    text = root / "zhCN.SC2Data/LocalizedData/GameStrings.txt"
    text.parent.mkdir(parents=True)
    text.write_text("".join(f"Card/Name/{name.replace(' ', '_')}=Old {name}\nCard/Describe/{name.replace(' ', '_')}=Description\n" for name in names), encoding="utf-8")
    catalog = root / "Base.SC2Data/GameData/AbilData.xml"
    catalog.parent.mkdir(parents=True)
    catalog.write_text('<Catalog><CAbilTrain id="StarportTrainSecretHangar"><InfoArray index="Train2"><Unit index="0" value="RavenSecretHangarCovertOps"/></InfoArray><InfoArray index="Train4"><Unit index="0" value="BattlecruiserSecretHangarCovertOps"/></InfoArray><InfoArray index="Train6"><Unit index="0" value="Wraith"/></InfoArray></CAbilTrain></Catalog>', encoding="utf-8")
    return root, text, catalog


def mutate_after_last_card(monkeypatch, mutation):
    real = module.inspect_keystone_card
    def inspect(root, name):
        result = real(root, name=name)
        if name == "Underground Base":
            mutation()
        return result
    monkeypatch.setattr(module, "inspect_keystone_card", inspect)


def test_unbound_text_drift_cannot_bind_old_card_text_to_new_hash(tmp_path, monkeypatch):
    root, text, _ = temporary_map(tmp_path)
    mutate_after_last_card(monkeypatch, lambda: text.write_text(text.read_text(encoding="utf-8").replace("Old", "New"), encoding="utf-8"))
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(root)
    assert error.value.code == "secret_hangar_source_changed"


def test_script_drift_after_final_card_read_is_rejected(tmp_path, monkeypatch):
    root, _, _ = temporary_map(tmp_path)
    def mutate():
        path = root / "MapScript.galaxy"
        path.write_bytes(path.read_bytes() + b"\n// external modification\n")
    mutate_after_last_card(monkeypatch, mutate)
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(root)
    assert error.value.code == "secret_hangar_source_changed"


def test_catalog_drift_after_parse_is_rejected(tmp_path, monkeypatch):
    root, _, catalog = temporary_map(tmp_path)
    real = module.audit_catalog
    def audit(session):
        report = real(session)
        catalog.write_bytes(catalog.read_bytes() + b"\n<!-- external modification -->\n")
        return report
    monkeypatch.setattr(module, "audit_catalog", audit)
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(root)
    assert error.value.code == "secret_hangar_source_changed"


def test_bound_context_detects_unrelated_source_addition(tmp_path, monkeypatch):
    root, _, _ = temporary_map(tmp_path)
    context = prepare_source_context(root, [], tmp_path / "cache")
    mutate_after_last_card(monkeypatch, lambda: (root / "new-component.txt").write_bytes(b"externally added"))
    with pytest.raises(SC2Error) as error:
        module.audit_secret_hangar(root, source_context=context)
    assert error.value.code == "source_context_stale"


def test_v2_baseline_is_recognized_static_only_and_keeps_missing_context(tmp_path):
    root, text, catalog = temporary_map(tmp_path)
    before = {p.relative_to(root).as_posix():module._hash(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
    report = module.audit_secret_hangar(root)
    assert report["script"]["profile_recognized"]
    assert report["static_profile_recognized"]
    assert report["overall"] == "observed_static_with_unknowns"
    assert {c["name"]:c["card_id"] for c in report["cards"]} == {"Secret Hangar":195,"Reactor":34,"Tech Lab":45,"Physics Lab":305,"Underground Base":318}
    assert any(row["code"] == "source_context_missing" for row in report["source_unknown"])
    assert report["source_context_complete"] is False
    assert report["acceptance"] == {"static":"performed","editor":"not_run","runtime":"not_run","visual":"not_run"}
    assert report["source_file_sha256"][str(text)] == before[text.relative_to(root).as_posix()]
    assert report["source_file_sha256"][str(catalog)] == before[catalog.relative_to(root).as_posix()]
    json.dumps(report, allow_nan=False)
    assert before == {p.relative_to(root).as_posix():module._hash(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
