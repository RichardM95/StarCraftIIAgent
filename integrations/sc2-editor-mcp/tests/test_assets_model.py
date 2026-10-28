import hashlib
import json
from pathlib import Path
import struct

import pytest

from sc2_mcp.assets_model import inspect_model, inspect_model_catalog, resolve_assets
from sc2_mcp.errors import SC2Error


def model_bytes(*, version=25, sequence_version=2, texture="Assets/Textures/a.dds"):
    """Small independently assembled MD34 with real record/reference layout."""
    sections = []
    def add(tag, body, count=1, version=0):
        index = len(sections)
        sections.append([tag, bytes(body), count, version])
        return index
    def reference(count, index):
        return struct.pack("<III", count, index, 0)
    add("MD34", b"\0" * 24, version=11)
    add("MODL", b"\0" * 808, version=version)
    name = add("CHAR", b"source.max\0", 11)
    seq = add("SEQS", b"\0" * 92, version=sequence_version)
    stand = add("CHAR", b"Stand\0", 6)
    attach = add("ATT_", b"\0" * 20, version=1)
    muzzle = add("CHAR", b"Ref_Weapon\0", 11)
    layer = add("LAYR", b"\0" * 468, version=25)
    image = add("CHAR", texture.encode() + b"\0", len(texture.encode()) + 1)
    mat = add("MAT_", b"\0" * 280, version=17)
    matname = add("CHAR", b"TestMat\0", 8)
    m = bytearray(sections[1][1]); m[:12] = reference(11, name)
    m[16:28] = reference(1, seq); m[228:240] = reference(1, attach)
    sections[1][1] = bytes(m)
    s = bytearray(sections[seq][1]); s[8:20] = reference(6, stand); sections[seq][1] = bytes(s)
    a = bytearray(sections[attach][1]); a[4:16] = reference(11, muzzle); sections[attach][1] = bytes(a)
    l = bytearray(sections[layer][1]); l[4:16] = reference(len(texture.encode()) + 1, image); sections[layer][1] = bytes(l)
    a = bytearray(sections[mat][1]); a[:12] = reference(8, matname); a[52:64] = reference(1, layer); sections[mat][1] = bytes(a)
    raw, indexes = bytearray(), []
    for tag, body, count, v in sections:
        while len(raw) % 16:
            raw.append(0)
        indexes.append(struct.pack("<4sIII", tag[::-1].encode(), len(raw), count, v))
        raw += body
    while len(raw) % 16:
        raw.append(0)
    table = len(raw); raw += b"".join(indexes)
    struct.pack_into("<4sIIIII", raw, 0, b"43DM", table, len(indexes), 1, 1, 0)
    return bytes(raw)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_model_actual_records_not_string_guessing(tmp_path):
    path = write(tmp_path / "unit.m3", model_bytes())
    raw = path.read_bytes()
    r = inspect_model(path)
    assert r["status"] == "supported_metadata"
    assert r["model_version"] == 25
    assert r["animations"] == ["Stand"]
    assert r["attachments"] == ["Ref_Weapon"]
    assert r["weapon_attachments"] == ["Ref_Weapon"]
    assert r["has_death_animation"] is False
    assert r["materials"] == [{"name": "TestMat", "version": 17, "layer_sections": [7]}]
    assert r["textures"] == ["Assets/Textures/a.dds"]
    assert path.read_bytes() == raw
    json.dumps(r)


@pytest.mark.parametrize("data", [b"", b"MD34", b"33DM" + b"\0" * 32])
def test_unknown_signatures_not_success(tmp_path, data):
    r = inspect_model(write(tmp_path / "bad.m3", data))
    assert r["status"] == "unsupported"
    assert r["unsupported"][0]["reason"] == "unsupported_signature"


def test_official_style_embedded_nul_material_label_is_partial_not_guessed(tmp_path):
    raw = model_bytes().replace(b'TestMat\0', b'Test\0x~\0')
    r = inspect_model(write(tmp_path / 'portrait.m3', raw))
    assert r['status'] == 'partial'
    assert r['materials'][0]['name'] is None
    assert r['textures'] == ['Assets/Textures/a.dds']
    assert any(x['reason'] == 'embedded_nul_material_name' for x in r['unsupported'])
    assert r['engine_parity'] is False


def test_embedded_nul_texture_path_still_rejected(tmp_path):
    raw = model_bytes(texture='Assets/Textures/a.dds').replace(b'Assets/Textures/a.dds', b'Assets/Texture\0/a.dds')
    with pytest.raises(SC2Error) as error:
        inspect_model(write(tmp_path / 'corrupt.m3', raw))
    assert error.value.code == 'invalid_model'


def test_unknown_versions_do_not_claim_absence(tmp_path):
    r = inspect_model(write(tmp_path / "new.m3", model_bytes(version=99)))
    assert r["status"] == "unsupported"
    r = inspect_model(write(tmp_path / "new.m3", model_bytes(sequence_version=99)))
    assert r["status"] == "partial"
    assert any(v.get("field") == "animations" for v in r["unsupported"])
    assert r["has_death_animation"] is None


def test_table_truncated_and_reference_corrupt_are_errors(tmp_path):
    for data in [model_bytes()[:-1], model_bytes()[:20]]:
        with pytest.raises(SC2Error, match="截断|越界"):
            inspect_model(write(tmp_path / "bad.m3", data))
    bad = bytearray(model_bytes())
    struct.pack_into("<I", bad, 32 + 16 + 4, 99999)
    with pytest.raises(SC2Error) as e:
        inspect_model(write(tmp_path / "bad.m3", bad))
    assert e.value.code == "invalid_model"


def test_closure_actual_sources_hashes_priority_and_no_writes(tmp_path):
    low, high = tmp_path / "low", tmp_path / "high"
    write(low / "Base.SC2Assets/Assets/Units/test.m3", model_bytes())
    write(low / "Base.SC2Assets/Assets/Textures/a.dds", b"old")
    chosen = write(high / "Assets/Textures/A.dds", b"new")
    r = resolve_assets([low, high], ["Assets/Units/test.m3"], source_context={"build": "98370", "source_context_id": "fixed", "complete": True})
    assert r["complete"]
    tex = next(n for n in r["nodes"] if n["reference"].endswith(".dds"))
    assert tex["physical_path"] == str(chosen.resolve())
    assert tex["sha256"] == hashlib.sha256(b"new").hexdigest()
    assert tex["build"] == "98370" and tex["source_context_id"] == "fixed"
    assert len(list(high.rglob("*.*"))) == 1


def test_missing_macro_ambiguity_and_context_incomplete(tmp_path):
    write(tmp_path / "Base.SC2Assets/Assets/a.dds", b"a")
    write(tmp_path / "Assets/a.dds", b"b")
    r = resolve_assets([tmp_path], ["Assets/a.dds", "Assets/missing.dds", "Assets/##name##.dds"])
    assert not r["complete"] and len(r["missing"]) == 1
    assert {v["reason"] for v in r["unknown"]} == {"engine_macro", "ambiguous_asset"}
    r = resolve_assets([tmp_path], [], source_context={"complete": False})
    assert not r["complete"]
    with pytest.raises(SC2Error):
        resolve_assets([tmp_path], ["../outside.dds"])
    with pytest.raises(SC2Error):
        resolve_assets([tmp_path], "Assets/a.dds")


def test_catalog_external_animation_cross_pack_is_real_source(tmp_path):
    mod, campaign = tmp_path / "mod", tmp_path / "campaign"
    write(mod / "Base.SC2Data/GameData/ModelData.xml", b'<Catalog><CModel id="Portrait"><Model value="Assets/Portrait.m3"/><RequiredAnims value="Assets/required.m3a"/><AnimProps><Name value="Assets/facial.m3a"/></AnimProps></CModel></Catalog>')
    write(mod / "Base.SC2Assets/Assets/Portrait.m3", model_bytes())
    write(mod / "Base.SC2Assets/Assets/required.m3a", model_bytes())
    cross = write(campaign / "Base.SC2Assets/Assets/facial.m3a", model_bytes())
    write(mod / "Base.SC2Assets/Assets/Textures/a.dds", b"texture")
    r = inspect_model_catalog([campaign, mod], "Portrait")
    assert r["complete"]
    assert next(n for n in r["nodes"] if n["reference"] == "Assets/facial.m3a")["physical_path"] == str(cross.resolve())
    assert len(r["nodes"]) == 4
