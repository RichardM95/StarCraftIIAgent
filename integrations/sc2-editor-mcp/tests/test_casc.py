import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from sc2_mcp import casc
from sc2_mcp.errors import SC2Error


def installation(tmp_path: Path):
    root = tmp_path / "StarCraft II"
    root.mkdir()
    header = "Branch!STRING:0|Active!DEC:1|Build Key!HEX:16|CDN Key!HEX:16|Version!STRING:0|Product!STRING:0\n"
    key, cdn = "a" * 32, "b" * 32
    (root / ".build.info").write_text(header + f"cn|1|{key}|{cdn}|5.0.17.98370|\nkr|1|{'c'*32}|{cdn}|5.0.17.98310|\n")
    for digest, uid in [(key, "s2c"), ("c" * 32, "s2")]:
        p = root / "SC2Data" / "config" / digest[:2] / digest[2:4] / digest
        p.parent.mkdir(parents=True)
        p.write_text(f"build-uid = {uid}\n")
    return root


def test_multi_region_selection_does_not_choose_highest_base(tmp_path):
    root = installation(tmp_path)
    info = casc.inspect_installation(root)
    assert info["warnings"]
    assert casc.select_build(info, product="s2_cn")["version"] == "5.0.17.98370"
    assert casc.select_build(info, product="s2")["version"] == "5.0.17.98310"
    assert casc.select_build(info, branch="cn")["build_uid"] == "s2c"
    with pytest.raises(SC2Error, match="唯一"):
        casc.select_build(info)


@pytest.mark.parametrize("path", ["../secret", "C:/bad", "/absolute", "a//b", "a/./b", "a/CON.txt", "a/LPT1", "a/file.", "a/file ", "a\x00b", "a:b", "", "a/../b"])
def test_unsafe_virtual_names_rejected(path):
    with pytest.raises(SC2Error):
        casc._asset_path(path)


def test_missing_build_config_is_not_resolved(tmp_path):
    root = installation(tmp_path)
    info = casc.inspect_installation(root)
    Path(info["builds"][0]["build_config"]).unlink()
    with pytest.raises(SC2Error) as err:
        casc.select_build(casc.inspect_installation(root), product="s2_cn")
    assert err.value.code == "BUILD_CONFIG_MISSING"


def test_extraction_checks_target_before_invoking_backend(tmp_path):
    root = installation(tmp_path)
    with pytest.raises(SC2Error) as err:
        casc.extract_casc(root, ["mods/core.SC2Mod/DocumentInfo"], root / "new", product="s2_cn")
    assert err.value.code == "INVALID_DESTINATION"
    with pytest.raises(SC2Error) as err:
        casc.extract_casc(root, ["a/b", "A/B"], tmp_path / "out", product="s2_cn")
    assert err.value.code == "ASSET_COLLISION"


def test_extraction_rehashes_output_before_publish(tmp_path, monkeypatch):
    root = installation(tmp_path)
    tools = tmp_path / "tools"
    helper = tools / "bin/Release/net6.0/Sc2Casc.dll"
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b"helper")
    monkeypatch.setattr(casc, "_TOOLS", tools)
    monkeypatch.setattr(casc, "_verify_vendor", lambda: {})
    monkeypatch.setattr(casc.shutil, "which", lambda _: "dotnet")
    def run(argv, **kwargs):
        assert kwargs["shell"] is False
        req = json.loads(Path(argv[-1]).read_text())
        output = Path(req["destination"]) / "mods/core/DocumentInfo"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"official")
        (Path(kwargs["cwd"]) / "result.json").write_text(json.dumps({"files": [{"path": "mods/core/DocumentInfo", "bytes": 8, "sha256": "0"*64}], "missing": []}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(casc.subprocess, "run", run)
    with pytest.raises(SC2Error) as err:
        casc.extract_casc(root, ["mods/core/DocumentInfo"], tmp_path / "out", product="s2_cn")
    assert err.value.code == "CASC_OUTPUT_INVALID"
    assert not (tmp_path / "out").exists()


def test_successful_extraction_does_not_modify_installation(tmp_path, monkeypatch):
    root = installation(tmp_path)
    before = (root / ".build.info").read_bytes()
    tools = tmp_path / "tools"
    helper = tools / "bin/Release/net6.0/Sc2Casc.dll"
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b"helper")
    monkeypatch.setattr(casc, "_TOOLS", tools)
    monkeypatch.setattr(casc, "_verify_vendor", lambda: {})
    monkeypatch.setattr(casc.shutil, "which", lambda _: "dotnet")
    def run(argv, **kwargs):
        req = json.loads(Path(argv[-1]).read_text())
        output = Path(req["destination"]) / "mods/core/DocumentInfo"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"official")
        (Path(kwargs["cwd"]) / "result.json").write_text(json.dumps({"files": [{"path": "mods/core/DocumentInfo", "bytes": 8, "sha256": hashlib.sha256(b"official").hexdigest()}], "missing": []}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(casc.subprocess, "run", run)
    result = casc.extract_casc(root, ["mods/core/DocumentInfo"], tmp_path / "out", product="s2_cn")
    assert Path(result["destination"]).is_dir()
    assert (root / ".build.info").read_bytes() == before


def test_malformed_build_key_cannot_escape_installation(tmp_path):
    root = installation(tmp_path)
    p = root / ".build.info"
    p.write_text(p.read_text().replace("a" * 32, "../outside"))
    with pytest.raises(SC2Error) as err:
        casc.inspect_installation(root)
    assert err.value.code == "INVALID_BUILD_INFO"


def _cancellable_backend(tmp_path, monkeypatch, script, token):
    root = installation(tmp_path)
    tools = tmp_path / "tools"
    helper = tools / "bin/Release/net6.0/Sc2Casc.dll"
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b"synthetic helper")
    monkeypatch.setattr(casc, "_TOOLS", tools)
    monkeypatch.setattr(casc, "_verify_vendor", lambda: {})
    monkeypatch.setattr(casc.shutil, "which", lambda _: "dotnet")
    real_popen = casc.subprocess.Popen
    spawned = []
    def popen(argv, **kwargs):
        assert argv[:2] == ["dotnet", str(helper)]
        assert Path(argv[2]).name == "request.json"
        assert kwargs["shell"] is False
        token.stage = Path(kwargs["cwd"])
        process = real_popen([sys.executable, "-u", "-c", script], **kwargs)
        spawned.append(process)
        return process
    monkeypatch.setattr(casc.subprocess, "Popen", popen)
    return root, spawned


_RUNNING_HELPER = """
from pathlib import Path
import sys,time
root=Path.cwd()
(root/'files').mkdir()
(root/'files'/'partial.bin').write_bytes(b'partial data stays in staging')
print('helper standard output preserved',flush=True)
print('helper diagnostic preserved',file=sys.stderr,flush=True)
(root/'ready').write_text('ready')
time.sleep(60)
"""


def test_cancel_stops_only_started_helper_preserves_logs_and_never_publishes(tmp_path, monkeypatch):
    class CancelOnReady(threading.Event):
        stage = None
        def is_set(self):
            if self.stage and (self.stage / "ready").exists():
                self.set()
            return super().is_set()
    token = CancelOnReady()
    root, spawned = _cancellable_backend(tmp_path, monkeypatch, _RUNNING_HELPER, token)
    baseline = (root / ".build.info").read_bytes()
    with pytest.raises(SC2Error) as error:
        casc.extract_casc(root, ["mods/core/DocumentInfo"], tmp_path / "out", product="s2_cn", cancel=token)
    assert error.value.code == "cancelled"
    assert len(spawned) == 1 and spawned[0].poll() is not None
    stage = Path(error.value.details["diagnostics"])
    assert (stage / "files/partial.bin").read_bytes() == b"partial data stays in staging"
    assert "helper standard output preserved" in (stage / "helper.stdout.log").read_text("utf-8")
    assert "helper diagnostic preserved" in (stage / "helper.stderr.log").read_text("utf-8")
    assert not (tmp_path / "out").exists()
    assert (root / ".build.info").read_bytes() == baseline


def test_cancel_after_verification_preserves_complete_staging_before_publish(tmp_path, monkeypatch):
    class CancelBeforePublish(threading.Event):
        def __init__(self):
            super().__init__()
            self.progress = []
        def report_progress(self, value, message):
            self.progress.append(value)
            if value == 99:
                self.set()
    token = CancelBeforePublish()
    script = """
from pathlib import Path
import json,hashlib
root=Path.cwd(); data=b'official'
target=root/'files/mods/core/DocumentInfo'; target.parent.mkdir(parents=True); target.write_bytes(data)
(root/'result.json').write_text(json.dumps({'files':[{'path':'mods/core/DocumentInfo','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}],'missing':[]}))
print('complete helper output',flush=True)
"""
    root, spawned = _cancellable_backend(tmp_path, monkeypatch, script, token)
    with pytest.raises(SC2Error) as error:
        casc.extract_casc(root, ["mods/core/DocumentInfo"], tmp_path / "out", product="s2_cn", cancel=token)
    assert error.value.code == "cancelled"
    assert spawned[0].poll() == 0
    assert not (tmp_path / "out").exists()
    stage = Path(error.value.details["diagnostics"])
    assert (stage / "files/mods/core/DocumentInfo").read_bytes() == b"official"
    assert "complete helper output" in (stage / "helper.stdout.log").read_text("utf-8")
    assert token.progress == [5, 10, 80, 95, 99]


def test_cancellable_timeout_stops_helper_and_preserves_stdout(tmp_path, monkeypatch):
    token = threading.Event()
    root, spawned = _cancellable_backend(tmp_path, monkeypatch, _RUNNING_HELPER, token)
    with pytest.raises(SC2Error) as error:
        casc.extract_casc(root, ["mods/core/DocumentInfo"], tmp_path / "out", product="s2_cn", timeout=1, cancel=token)
    assert error.value.code == "CASC_TIMEOUT"
    assert spawned[0].poll() is not None
    stage = Path(error.value.details["diagnostics"])
    assert "helper standard output preserved" in (stage / "helper.stdout.log").read_text("utf-8")
    assert not (tmp_path / "out").exists()


def test_already_cancelled_does_not_launch_or_create_output(tmp_path, monkeypatch):
    token = threading.Event()
    token.set()
    def no_launch(*args, **kwargs):
        pytest.fail("Already-cancelled operation must not start the helper")
    monkeypatch.setattr(casc.subprocess, "Popen", no_launch)
    with pytest.raises(SC2Error) as error:
        casc.extract_casc(tmp_path / "not-read", ["a"], tmp_path / "out", cancel=token)
    assert error.value.code == "cancelled"
    assert not (tmp_path / "out").exists()
