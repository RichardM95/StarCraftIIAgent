"""Bank 预载重命名的纯 planner 单元测试。

worker 未运行这些测试；Codex 在完整隔离环境中执行。
- ``plan_bank_preload_rename`` 只依赖 ``dependencies`` / ``errors`` / ``shell``，
  可直接在临时组件根上测试，不写正式模组、测试地图或玩家 Bank。
- 真实样例形态：``BankList.xml`` 中全是自闭合 ``<Bank ... />``，
  ``DocumentInfo`` 的 ``Preload`` 可混有非 Bank 预载。
- 公共 operation 测试只检查路由参数（``prepare_domain`` label / planner / source_context_id），
  **不是**完整事务；真实 Service 的 prepare/apply/rollback 与 Editor 保护由 Codex 回归。
"""

import struct

import pytest

from sc2_mcp.bank_preload import plan_bank_preload_rename
from sc2_mcp.errors import SC2Error
from sc2_mcp.shell import header_dependencies

DEPENDENCIES = ["file:Mods/Liberty.SC2Mod", "bnet:合作/0.0/999,file:Mods/Coop.SC2Mod"]
NAME_OLD = "LibBank"
NAME_NEW = "LibBank_private"
# BOM 必须与实际编码一致：UTF-16 用 FFFE/FEFF，EFBBBF 只属于 UTF-8。
BOM = {"utf-8": b"\xef\xbb\xbf", "utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}


def make_header(values, strings=(("DocInfo/Name", b"NCzh", "中文名称"),)):
    prefix = b"H2CS" + struct.pack("<I", 8) + bytes(range(36))
    payload = struct.pack("<I", len(values)) + b"".join(value.encode() + b"\0" for value in values)
    suffix = struct.pack("<I", len(strings))
    for key, locale, value in strings:
        encoded_key, encoded_value = key.encode(), value.encode()
        suffix += struct.pack("<H", len(encoded_key)) + encoded_key + locale + struct.pack("<H", len(encoded_value)) + encoded_value
    return prefix + payload + suffix


def document_info(preloads, *, newline="\n", other_values=(), comment="<!-- 保留：Preload 注释 -->"):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<DocInfo>",
        "  <Dependencies>",
        *[f"    <Value>{value}</Value>" for value in DEPENDENCIES],
        "  </Dependencies>",
        "  <!-- 依赖顺序必须保持 -->",
        "  <Preload>",
    ]
    if comment is not None:
        lines.append(f"    {comment}")
    lines += [f"    <Value>Bank;{preload}</Value>" for preload in preloads]
    lines += [f"    <Value>{value}</Value>" for value in other_values]
    lines += ["  </Preload>", "  <Name>翠影遗庭：林间遗迹战场</Name>", "</DocInfo>", ""]
    return newline.join(lines)


def bank_list(banks, *, newline="\n"):
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<BankList>"]
    lines += [f"  {entry}" for entry in banks]
    lines += ["</BankList>", ""]
    return newline.join(lines)


def bank(name, player="1", extra='User="0"'):
    """真实样例的自闭合形态。"""
    return f'<Bank Name="{name}" Player="{player}" {extra} />'


def document_info_text(body, *, dependencies=DEPENDENCIES):
    """自定义 DocInfo 正文，依赖列表可显式为空以隔离目标错误。"""
    lines = ['<?xml version="1.0"?>', "<DocInfo>"]
    if dependencies:
        lines.append("  <Dependencies>")
        lines += [f"    <Value>{value}</Value>" for value in dependencies]
        lines.append("  </Dependencies>")
    lines += body
    lines += ["</DocInfo>", ""]
    return "\n".join(lines)


@pytest.fixture
def project(tmp_path):
    """写入临时组件根；返回 (root, {名字: 原始字节})。BOM 与编码保持一致。"""
    def build(docinfo_text, banklist_text, *, header=None, header_values=DEPENDENCIES,
              encoding="utf-8", bom=False, omit=()):
        root = tmp_path / "map.SC2Map"
        root.mkdir()
        def write(name, text):
            data = text.encode(encoding)
            if bom:
                data = BOM[encoding] + data
            (root / name).write_bytes(data)
            return data
        originals = {"DocumentInfo": write("DocumentInfo", docinfo_text),
                     "BankList.xml": write("BankList.xml", banklist_text)}
        if header is not False:
            (root / "DocumentHeader").write_bytes(
                header if header is not None else make_header(header_values))
        for name in omit:
            (root / name).unlink()
        return root, originals
    return build


def plan(root, old=NAME_OLD, new=NAME_NEW):
    return plan_bank_preload_rename(root, [], old, new)


# --------------------------------------------------------------------------- #
# 真实自闭合 Bank 形态
# --------------------------------------------------------------------------- #
def test_self_closing_banks_are_supported(project):
    """回归：真实样例 BankList 全为自闭合 <Bank/> 时必须能定位。"""
    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD), bank("OtherBank", "2")]))
    changes, report = plan(root)
    assert sorted(changes) == ["BankList.xml", "DocumentInfo"]
    assert f'Name="{NAME_NEW}"'.encode() in changes["BankList.xml"]
    assert report["components"]["BankList.xml"]["banks"] == 2
    assert (root / "BankList.xml").read_bytes() == originals["BankList.xml"]


def test_empty_element_form_also_supported(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        '<?xml version="1.0"?>\n<BankList>\n  <Bank Name="LibBank" Player="1"></Bank>\n</BankList>\n')
    changes, _report = plan(root)
    assert b'Name="LibBank_private"' in changes["BankList.xml"]


# --------------------------------------------------------------------------- #
# 普通重命名与字节保全
# --------------------------------------------------------------------------- #
def test_rename_touches_only_selected_bank_and_preload(project):
    root, originals = project(
        document_info([NAME_OLD, "OtherBank"], other_values=["Unit", "Abil"],),
        bank_list([bank(NAME_OLD), bank(NAME_NEW, "2"), bank("OtherBank", "3")]),
    )
    header_before = (root / "DocumentHeader").read_bytes()
    changes, report = plan(root)
    assert sorted(changes) == ["BankList.xml", "DocumentInfo"]
    assert report["header_modified"] is False and report["dependencies_modified"] is False
    assert report["empty"] is False
    # 非 Bank 预载与其他 Bank 预载原样保留
    expected = originals["DocumentInfo"].replace(
        f"<Value>Bank;{NAME_OLD}</Value>".encode(), f"<Value>Bank;{NAME_NEW}</Value>".encode())
    assert changes["DocumentInfo"] == expected
    assert b"<Value>Unit</Value>" in expected and b"<Value>Abil</Value>" in expected
    assert b"<Value>Bank;OtherBank</Value>" in expected
    assert report["components"]["DocumentInfo"]["non_bank_values"] == 2
    # 其他 Player / 其他 Bank 原样
    assert bank(NAME_NEW, "2").encode() in changes["BankList.xml"]
    assert bank("OtherBank", "3").encode() in changes["BankList.xml"]
    assert (root / "DocumentHeader").read_bytes() == header_before
    assert header_dependencies(header_before)["values"] == DEPENDENCIES


def test_unknown_attributes_and_comments_are_preserved(project):
    root, originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, extra='User="7" FutureAttr="keep"')]),
    )
    changes, _report = plan(root)
    candidate = changes["BankList.xml"].decode()
    assert 'User="7"' in candidate and 'FutureAttr="keep"' in candidate and 'Player="1"' in candidate
    assert "<!-- 保留：Preload 注释 -->" in changes["DocumentInfo"].decode()
    # 方向：候选 == 原文（已把旧名替换为新名）；不能对候选再做 old->new。
    expected = originals["DocumentInfo"].replace(NAME_OLD.encode(), NAME_NEW.encode())
    assert changes["DocumentInfo"] == expected
    assert expected.count(NAME_NEW.encode()) == 1


def test_single_quote_attribute_and_utf16_bom(project):
    root, originals = project(
        document_info([NAME_OLD]).replace('encoding="utf-8"', 'encoding="utf-16"'),
        "<?xml version='1.0' encoding='utf-16'?>\n<BankList>\n  <Bank Name='LibBank' Player='1' />\n</BankList>\n",
        encoding="utf-16-le", bom=True,
    )
    # fixture 与真实 UTF-16 一致：FFFE BOM + UTF-16LE 数据，且 XML 声明同步为 utf-16。
    assert originals["BankList.xml"].startswith(b"\xff\xfe")
    assert originals["DocumentInfo"].startswith(b"\xff\xfe")
    assert originals["BankList.xml"][2:].decode("utf-16-le").startswith("<?xml version='1.0' encoding='utf-16'?>")
    changes, _report = plan(root)
    assert changes["BankList.xml"].startswith(b"\xff\xfe")
    decoded = changes["BankList.xml"][2:].decode("utf-16-le")
    assert "Name='LibBank_private'" in decoded
    assert decoded.count("encoding='utf-16'") == 1
    assert changes["DocumentInfo"].startswith(b"\xff\xfe")


# --------------------------------------------------------------------------- #
# 同 Player 去重 / 独立 Player 身份
# --------------------------------------------------------------------------- #
def test_actual_double_entry_same_player_deduplicates(project):
    """真实验收场景：old/new 均 Player=1、无子内容的两个自闭合 <Bank ... />。"""
    old_entry, new_entry = bank(NAME_OLD), bank(NAME_NEW)
    assert old_entry.endswith(" />") and new_entry.endswith(" />")
    root, originals = project(document_info([NAME_OLD]), bank_list([old_entry, new_entry]))
    _changes, report = plan(root)
    assert report["components"]["BankList.xml"]["actions"] == [
        {"action": "deduplicate", "name": NAME_NEW, "player": "1"}]
    assert report["components"]["BankList.xml"]["removed"] == 1


def test_same_player_self_closing_old_and_new_dedup_is_accepted(project):
    """最小回归：profile 不含 Name、body 为空串，因此同名 Player 的旧项可安全去重。"""
    old_entry, new_entry = bank(NAME_OLD), bank(NAME_NEW)
    root, originals = project(document_info([NAME_OLD]), bank_list([old_entry, new_entry]))
    changes, report = plan(root)
    assert report["components"]["BankList.xml"]["actions"] == [
        {"action": "deduplicate", "name": NAME_NEW, "player": "1"}]
    assert report["components"]["BankList.xml"]["removed"] == 1
    # 整行删除：条目独占一行，删除范围包含行首两个空格与该行换行。
    removed_line = f"  {old_entry}\n".encode()
    assert removed_line in originals["BankList.xml"]
    assert changes["BankList.xml"] == originals["BankList.xml"].replace(removed_line, b"")
    assert b'Name="LibBank_private"' in changes["BankList.xml"]
    assert b'Name="LibBank"' not in changes["BankList.xml"]
    # 规格与报告一致：只剩一条同 Player 的新名 Bank
    assert changes["BankList.xml"].count(b"<Bank ") == 1


def test_dedup_ignores_only_name_when_other_attributes_match(project):
    """除 Name 外属性一致（不同书写顺序）仍应判定等价。"""
    root, _originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, extra='User="0"'), bank(NAME_NEW, extra='User="0"')]),
    )
    _changes, report = plan(root)
    assert report["components"]["BankList.xml"]["removed"] == 1


def test_same_player_conflict_on_unknown_attribute_rejected(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, extra='User="1"'), bank(NAME_NEW, extra='User="2"')]),
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "bank_list_conflict"


def test_deduplicate_rejected_when_child_content_differs(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        '<?xml version="1.0"?>\n<BankList>\n'
        f'  <Bank Name="{NAME_OLD}" Player="1"><Header version="1" /></Bank>\n'
        f'  <Bank Name="{NAME_NEW}" Player="1"><Header version="2" /></Bank>\n'
        '</BankList>\n',
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "bank_list_conflict"


def test_old_player2_and_new_player1_is_independent_identity(project):
    """old 在 Player 2、new 在 Player 1：独立身份，旧条目直接重命名，不算凭空创建。"""
    root, _originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, "2"), bank(NAME_NEW, "1"), bank("OtherBank", "3")]),
    )
    changes, report = plan(root)
    assert report["components"]["BankList.xml"]["removed"] == 0
    assert report["components"]["BankList.xml"]["actions"] == [
        {"action": "rename", "from": NAME_OLD, "to": NAME_NEW, "player": "2"}]
    assert changes["BankList.xml"].count(f'Name="{NAME_NEW}"'.encode()) == 2
    assert f'Name="{NAME_OLD}"'.encode() not in changes["BankList.xml"]
    assert bank("OtherBank", "3").encode() in changes["BankList.xml"]


def test_other_players_follow_same_rule_independently(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, "1"), bank(NAME_NEW, "1"), bank(NAME_OLD, "2"), bank(NAME_OLD, "3")]),
    )
    changes, report = plan(root)
    actions = report["components"]["BankList.xml"]["actions"]
    assert {"action": "deduplicate", "name": NAME_NEW, "player": "1"} in actions
    assert {"action": "rename", "from": NAME_OLD, "to": NAME_NEW, "player": "2"} in actions
    assert {"action": "rename", "from": NAME_OLD, "to": NAME_NEW, "player": "3"} in actions
    assert changes["BankList.xml"].count(f'Name="{NAME_NEW}"'.encode()) == 3


# --------------------------------------------------------------------------- #
# 幂等 / 缺失 / 部分状态
# --------------------------------------------------------------------------- #
def test_second_run_is_empty(project):
    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    first, _report = plan(root)
    (root / "DocumentInfo").write_bytes(first["DocumentInfo"])
    (root / "BankList.xml").write_bytes(first["BankList.xml"])
    second, report = plan(root)
    assert second == {} and report["empty"] is True and report["changed_files"] == []


def test_neither_name_present_is_an_error(project):
    root, _originals = project(document_info(["OtherBank"]), bank_list([bank("OtherBank")]))
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code in {"bank_preload_not_found", "bank_list_not_found"}


@pytest.mark.parametrize("doc_preloads,bank_names", [([NAME_NEW], [NAME_NEW]), ([NAME_NEW], [NAME_OLD])])
def test_partial_state_is_checked_across_both_files(project, doc_preloads, bank_names):
    root, _originals = project(document_info(doc_preloads), bank_list([bank(names) for names in bank_names]))
    changes, report = plan(root)
    if doc_preloads == bank_names == [NAME_NEW]:
        assert changes == {}
        assert report["components"]["BankList.xml"]["actions"] == [
            {"action": "already_renamed", "name": NAME_NEW, "player": "1"}]
    else:
        assert sorted(changes) == ["BankList.xml"]
        assert report["components"]["BankList.xml"]["actions"][0]["action"] == "rename"


def test_only_new_bank_is_empty_change(project):
    root, _originals = project(document_info([NAME_NEW]), bank_list([bank(NAME_NEW)]))
    changes, report = plan(root)
    assert changes == {} and report["empty"] is True


# --------------------------------------------------------------------------- #
# 编码 / 换行 / Unicode
# --------------------------------------------------------------------------- #
def test_utf8_bom_and_crlf_are_preserved(project):
    root, originals = project(
        document_info([NAME_OLD], newline="\r\n"),
        bank_list([bank(NAME_OLD)], newline="\r\n"),
        bom=True,
    )
    changes, _report = plan(root)
    for name in ("DocumentInfo", "BankList.xml"):
        candidate = changes[name]
        assert candidate.startswith(b"\xef\xbb\xbf")
        assert b"\n" not in candidate.replace(b"\r\n", b"")
        assert candidate.count(b"\r\n") == originals[name].count(b"\r\n")


def test_unicode_outside_bank_fields_is_untouched(project):
    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    changes, _report = plan(root)
    candidate = changes["DocumentInfo"].decode()
    assert "翠影遗庭：林间遗迹战场" in candidate
    expected = originals["DocumentInfo"].replace(NAME_OLD.encode(), NAME_NEW.encode())
    assert changes["DocumentInfo"] == expected
    assert "翠影遗庭：林间遗迹战场".encode() in changes["DocumentInfo"]
    assert expected.count(NAME_NEW.encode()) == 1


def test_unicode_name_is_rejected(project):
    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    with pytest.raises(SC2Error) as error:
        plan(root, new="银行")
    assert error.value.code == "invalid_bank_name"


# --------------------------------------------------------------------------- #
# 危险名字
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [
    NAME_OLD + "/../../escape",
    NAME_OLD + ".SC2Bank",
    "",
    "a" * 129,
    "Lib Bank",
    NAME_OLD + "\n",
])
@pytest.mark.parametrize("field", ["old", "new"])
def test_dangerous_names_are_rejected(project, bad, field):
    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    old, new = (bad, NAME_NEW) if field == "old" else (NAME_OLD, bad)
    with pytest.raises(SC2Error) as error:
        plan_bank_preload_rename(root, [], old, new)
    assert error.value.code == "invalid_bank_name"
    assert error.value.details["field"] == ("old_name" if field == "old" else "new_name")
    assert (root / "DocumentInfo").read_bytes() == originals["DocumentInfo"]
    assert (root / "BankList.xml").read_bytes() == originals["BankList.xml"]


def test_identical_names_rejected(project):
    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    with pytest.raises(SC2Error) as error:
        plan_bank_preload_rename(root, [], NAME_OLD, NAME_OLD)
    assert error.value.code == "invalid_bank_rename"


# --------------------------------------------------------------------------- #
# 畸形 / 不安全输入
# --------------------------------------------------------------------------- #
def test_malformed_bank_list_rejected_without_writes(project):
    root, originals = project(document_info([NAME_OLD]), '<?xml version="1.0"?><BankList><Bank Name="x">')
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "malformed_bank_list"
    assert (root / "DocumentInfo").read_bytes() == originals["DocumentInfo"]


def test_dtd_rejected(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        f'<?xml version="1.0"?>\n<!DOCTYPE BankList>\n<BankList>\n  {bank(NAME_OLD)}\n</BankList>\n',
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "unsafe_bank_metadata"


def test_duplicate_preload_rejected(project):
    # DocInfo 无依赖，Header 也写空依赖，才能先走到 Preload 结构检查而不是 shell_mismatch。
    root, _originals = project(
        document_info_text([
            "  <Preload><Value>Bank;A</Value></Preload>",
            "  <Preload><Value>Bank;A</Value></Preload>",
        ], dependencies=[]),
        bank_list([bank(NAME_OLD)]),
        header_values=[],
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "ambiguous_bank_preload"


def test_nested_value_rejected(project):
    root, _originals = project(
        document_info_text([
            "  <Preload><Value>Bank;LibBank<Bank/></Value></Preload>",
        ], dependencies=[]),
        bank_list([bank(NAME_OLD)]),
        header_values=[],
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code in {"nested_bank_preload_value", "unsupported_bank_preload"}


@pytest.mark.parametrize("value", ['<Value file="Bank;LibBank"/>', "<Value/>"])
def test_unsupported_preload_forms_rejected(project, value):
    root, _originals = project(
        document_info_text([f"  <Preload>{value}</Preload>"], dependencies=[]),
        bank_list([bank(NAME_OLD)]),
        header_values=[],
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "unsupported_bank_preload"


def test_duplicate_bank_identity_rejected(project):
    root, _originals = project(
        document_info([NAME_OLD]),
        bank_list([bank(NAME_OLD, "1"), bank(NAME_OLD, "1")]),
    )
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "duplicate_bank_identity"


@pytest.mark.parametrize("header,code", [
    (b"", "unsupported_header"),
    (make_header(["file:Other.SC2Mod"]), "shell_mismatch"),
    (b"bogus", "unsupported_header"),
])
def test_header_problems_are_rejected(project, header, code):
    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]), header=header)
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == code
    assert (root / "DocumentInfo").read_bytes() == originals["DocumentInfo"]


def test_missing_components_are_rejected(project):
    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]), omit=("BankList.xml",))
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "missing_bank_list"
    (root / "DocumentInfo").unlink()
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "missing_document_info"
    assert originals["DocumentInfo"]


def test_missing_header_rejected(project):
    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]), omit=("DocumentHeader",))
    with pytest.raises(SC2Error) as error:
        plan(root)
    assert error.value.code == "missing_document_header"


def test_dependencies_triggers_script_and_player_banks_untouched(project):
    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    header = (root / "DocumentHeader").read_bytes()
    (root / "Tenant.SC2Bank").write_bytes(b"\x00player-bank-bytes\x00")
    triggers = b'<?xml version="1.0"?>\n<TriggerData><Root/></TriggerData>\n'
    script = b'void MapInit() { BankPreloadLoad(1, 1, "LibBank", "", false); }\n'
    (root / "Triggers").write_bytes(triggers)
    (root / "MapScript.galaxy").write_bytes(script)
    changes, _report = plan(root)
    assert sorted(changes) == ["BankList.xml", "DocumentInfo"]
    assert (root / "Tenant.SC2Bank").read_bytes() == b"\x00player-bank-bytes\x00"
    assert (root / "Triggers").read_bytes() == triggers
    assert (root / "MapScript.galaxy").read_bytes() == script
    assert (root / "DocumentHeader").read_bytes() == header


# --------------------------------------------------------------------------- #
# 公共 operation：只验证路由，不是完整事务
# --------------------------------------------------------------------------- #
class FakeService:
    """只实现 prepare_domain 路由；在给定根上真实执行 planner，不写盘、不建事务。"""

    def __init__(self, root, roots=None, source_context_id="c" * 64):
        self.root = root
        self.roots = roots if roots is not None else []
        self.context = {"source_context_id": source_context_id, "roots": [str(item) for item in self.roots]}
        self.calls = []

    def prepare_domain(self, project_id, label, planner, source_context_id=None):
        self.calls.append({"project_id": project_id, "label": label,
                           "source_context_id": source_context_id, "planner": planner})
        changes = planner(self.root, self.roots, self.context)
        return {"state": "prepared", "change_id": "candidate", "changes": sorted(changes)}


def test_public_operation_routes_through_prepare_domain(project):
    from sc2_mcp.operations import create_operations

    root, originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    service = FakeService(root)
    function, readonly = create_operations(service)["sc2_bank_preload_rename"]
    assert readonly is False
    result = function("project-1", NAME_OLD, NAME_NEW, "c" * 64)
    assert result["state"] == "prepared"
    assert result["changes"] == ["BankList.xml", "DocumentInfo"]
    call = service.calls[0]
    assert call["label"] == "bank_preload_rename"
    assert call["project_id"] == "project-1"
    assert call["source_context_id"] == "c" * 64
    # operation 报告即 planner 的真实报告；未写盘。
    report = result["impact_report"]
    assert report["old_name"] == NAME_OLD and report["new_name"] == NAME_NEW
    assert report["changed_files"] == ["BankList.xml", "DocumentInfo"]
    assert report["scope"] == "metadata_preload_only"
    assert report["components"]["DocumentInfo"]["actions"][0]["action"] == "rename"
    assert (root / "DocumentInfo").read_bytes() == originals["DocumentInfo"]
    assert (root / "BankList.xml").read_bytes() == originals["BankList.xml"]


def test_public_operation_source_context_is_optional(project):
    from sc2_mcp.operations import create_operations

    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    service = FakeService(root)
    function, _readonly = create_operations(service)["sc2_bank_preload_rename"]
    result = function(project_id="p", old_name=NAME_OLD, new_name=NAME_NEW)
    assert service.calls[0]["source_context_id"] is None
    assert "impact_report" in result


def test_public_operation_planner_shape(project):
    from sc2_mcp.operations import create_operations

    root, _originals = project(document_info([NAME_OLD]), bank_list([bank(NAME_OLD)]))
    captured = {}

    class Capture(FakeService):
        def prepare_domain(self, project_id, label, planner, source_context_id=None):
            captured["changes"] = planner(root, [], {"source_context_id": "c" * 64})
            return {"state": "prepared", "changes": sorted(captured["changes"])}

    create_operations(Capture(root))["sc2_bank_preload_rename"][0](
        project_id="p", old_name=NAME_OLD, new_name=NAME_NEW)
    assert sorted(captured["changes"]) == ["BankList.xml", "DocumentInfo"]
    assert isinstance(captured["changes"]["DocumentInfo"], bytes)
