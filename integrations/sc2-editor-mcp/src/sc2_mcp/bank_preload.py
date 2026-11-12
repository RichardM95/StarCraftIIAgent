"""Bank 预载元数据重命名（纯库，不写盘）。

范围（元数据预载，**不是**源码 Bank API 重命名）：
- ``DocumentInfo`` 中 ``<DocInfo>`` 直属唯一 ``<Preload>`` 内的 ``<Value>Bank;<old></Value>``；
- ``BankList.xml`` 中 ``<BankList>`` 直属 ``<Bank Name="old">`` 的 Name 属性。

字节定位全部复用 ``dependencies._document_spans``（已处理嵌套/注释/CDATA/自闭合）；
ElementTree 只做严格验证，不做序列化。其余字节、BOM/编码/换行、注释、依赖顺序与
``DocumentHeader`` 原字节保持不变。未选中条目（含非 Bank 预载 Value）原样保留。
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from . import dependencies
from .errors import SC2Error
from .shell import header_dependencies

_NAME_RE = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")
_BANK_PREFIX = "Bank;"
_DTD_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.I)
_ATTR_RE = re.compile(r"""\s+([^\s=<>/]+)\s*=\s*("[^"]*"|'[^']*')""")
_MISSING_CODES = {"DocumentInfo": "missing_document_info", "DocumentHeader": "missing_document_header",
                  "BankList.xml": "missing_bank_list"}


# --------------------------------------------------------------------------- #
# 输入与安全
# --------------------------------------------------------------------------- #
def _validate_name(label: str, value: object) -> str:
    """1..128 个 [A-Za-z0-9_-]；任何路径或后缀操作在此拒绝。"""
    if not isinstance(value, str) or not _NAME_RE.match(value):
        raise SC2Error("invalid_bank_name",
                       f"{label} 必须匹配 [A-Za-z0-9_-] 且长度为 1..128；不接受路径、后缀或文件操作",
                       field=label, value=value if isinstance(value, str) else None)
    return value


def _component(root: Path, name: str) -> Path:
    """项目根内大小写不敏感定位组件；不越过项目根。"""
    matches = [entry for entry in root.iterdir() if entry.name.casefold() == name.casefold()] if root.is_dir() else []
    if len(matches) > 1:
        raise SC2Error("bank_file_case_collision", "组件文件存在大小写冲突", path=str(root), component=name)
    if not matches or not matches[0].is_file():
        raise SC2Error(_MISSING_CODES[name], f"组件根缺少 {name}", path=str(root))
    return matches[0]


def _source(path: Path) -> dict:
    """按依赖层规则解码；拒绝 DTD/ENTITY 与二进制。"""
    data = path.read_bytes()
    text, encoding = dependencies._decode_xml(data, path)
    if _DTD_RE.search(text):
        raise SC2Error("unsafe_bank_metadata", "Bank 元数据不允许 DTD 或实体声明", path=str(path))
    return {"bytes": data, "text": text, "encoding": encoding}


def _parse_xml(text: str, path: Path, code: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise SC2Error(code, "XML 不能解析", path=str(path), reason=str(exc)) from exc


def _check_header(root: Path, document_values: list[str]) -> None:
    """DocumentHeader 必须存在且为已验证 H2CS v8，依赖与 DocInfo 一致；Header 不改。"""
    path = _component(root, "DocumentHeader")
    try:
        info = header_dependencies(path.read_bytes())
    except SC2Error as exc:
        raise SC2Error("unsupported_header", "DocumentHeader 不是已验证的 H2CS v8", path=str(path),
                       reason=getattr(exc, "code", str(exc))) from exc
    if info["values"] != document_values:
        raise SC2Error("shell_mismatch", "DocumentInfo 和 DocumentHeader 的依赖不一致",
                       header=info["values"], document=document_values, path=str(path))


def _apply(source: dict, path: Path, edits: list[tuple[int, int, str]]) -> bytes:
    """不重叠定点替换，再用依赖层编码往返校验落成字节。"""
    ordered = sorted(edits)
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] < previous[1]:
            raise SC2Error("overlapping_bank_edit", "编辑区间重叠，拒绝生成部分候选", path=str(path))
    text = source["text"]
    for start, end, replacement in reversed(ordered):
        text = text[:start] + replacement + text[end:]
    return dependencies._apply_edit(source["bytes"], source["text"], source["encoding"], 0,
                                    len(source["text"]), text, path)


def _attr_span(text: str, span: dict, attribute: str) -> tuple[int, int]:
    """在起始标签区间内定位属性值的绝对范围（span 只定位，值由 ElementTree 验证）。"""
    opening = text[span["start"]:span["open_end"]]
    found = [match for match in _ATTR_RE.finditer(opening) if match.group(1).casefold() == attribute.casefold()]
    if len(found) != 1:
        raise SC2Error("unsupported_bank_metadata", f"{attribute} 属性必须恰好出现一次", offset=span["start"])
    return span["start"] + found[0].start(2) + 1, span["start"] + found[0].end(2) - 1


# --------------------------------------------------------------------------- #
# DocumentInfo：只改 Bank; 预载，其余 Value 原样保留
# --------------------------------------------------------------------------- #
def _bank_name(value_span: dict, text: str) -> str:
    if value_span["self_closing"] or value_span["children"]:
        raise SC2Error("unsupported_bank_preload", "Value 必须是非嵌套的文本元素")
    payload = text[value_span["open_end"]:value_span["close_start"]]
    if "<" in payload or ">" in payload or "&" in payload:
        raise SC2Error("unsupported_bank_preload", "Value 内含标记或字符引用，拒绝编辑", value=payload)
    return payload


def _document_info_plan(path: Path, source: dict, old: str, new: str) -> tuple[bytes, dict]:
    text = source["text"]
    try:
        info = dependencies._parse_document_info(text, path)
    except SC2Error as exc:
        raise SC2Error("malformed_document_info", "DocumentInfo XML 不能解析",
                       path=str(path), reason=getattr(exc, "code", str(exc))) from exc
    root_span = info.get("root_span")
    if not root_span:
        raise SC2Error("malformed_document_info", "DocumentInfo 结构不能解析", path=str(path))
    preloads = [span for span in root_span["children"] if span["tag"] == "Preload"]
    if not preloads:
        raise SC2Error("missing_bank_preload", "DocumentInfo 没有直属 Preload", path=str(path))
    if len(preloads) > 1:
        raise SC2Error("ambiguous_bank_preload", "DocumentInfo 有多个直属 Preload", path=str(path))
    if preloads[0]["self_closing"]:
        raise SC2Error("unsupported_bank_preload", "Preload 为自闭合，不含预载列表", path=str(path))

    banks, others = [], 0
    for span in preloads[0]["children"]:
        if span["tag"] != "Value":
            raise SC2Error("unsupported_bank_preload", "Preload 中包含未知元素", path=str(path), element=span["tag"])
        payload = _bank_name(span, text)
        if not payload.startswith(_BANK_PREFIX):
            others += 1  # 非 Bank 预载不参与，原样保留
            continue
        name = payload[len(_BANK_PREFIX):]
        if not _NAME_RE.match(name):
            raise SC2Error("unsupported_bank_preload", "预载 Bank 名不是受支持的标识符", value=payload)
        start = span["open_end"] + len(_BANK_PREFIX)
        banks.append({"name": name, "start": start, "end": start + len(name), "span": span})

    old_entries = [bank for bank in banks if bank["name"] == old]
    new_entries = [bank for bank in banks if bank["name"] == new]
    if len(new_entries) > 1:
        raise SC2Error("duplicate_bank_preload", "DocumentInfo 已存在重复的新名称预载", path=str(path), name=new)
    edits, actions = [], []
    if old_entries and new_entries:
        edits = [(bank["span"]["start"], bank["span"]["end"], "") for bank in old_entries]
        actions.append({"action": "deduplicate", "name": new, "removed": len(old_entries)})
    elif old_entries:
        edits = [(bank["start"], bank["end"], new) for bank in old_entries]
        actions.append({"action": "rename", "from": old, "to": new, "count": len(old_entries)})
    elif new_entries:
        actions.append({"action": "already_renamed", "name": new, "count": len(new_entries)})
    else:
        raise SC2Error("bank_preload_not_found", "DocumentInfo 的 Preload 既无旧名也无新名 Bank 预载",
                       path=str(path), old_name=old, new_name=new, existing=[bank["name"] for bank in banks])

    if not edits:
        return source["bytes"], {"component": path.name, "actions": actions, "non_bank_values": others,
                                 "entries_before": len(banks), "changed": False}
    candidate = _apply(source, path, edits)
    _verify_document_info(candidate, path, old, new, len(banks) - (1 if old_entries and new_entries else 0))
    return candidate, {"component": path.name, "actions": actions, "non_bank_values": others,
                       "entries_before": len(banks), "changed": candidate != source["bytes"]}


def _verify_document_info(data: bytes, path: Path, old: str, new: str, expected: int) -> None:
    text, _encoding = dependencies._decode_xml(data, path)
    root_span = dependencies._parse_document_info(text, path)["root_span"]
    preloads = [span for span in root_span["children"] if span["tag"] == "Preload"]
    if len(preloads) != 1:
        raise SC2Error("bank_preload_candidate_mismatch", "候选 DocumentInfo 的 Preload 结构变化", path=str(path))
    names = []
    for span in preloads[0]["children"]:
        payload = _bank_name(span, text)
        if payload.startswith(_BANK_PREFIX):
            names.append(payload[len(_BANK_PREFIX):])
    if old in names or names.count(new) != 1 or len(names) != expected:
        raise SC2Error("bank_preload_candidate_mismatch", "候选 DocumentInfo 不符合预期",
                       path=str(path), names=names, expected=expected)


# --------------------------------------------------------------------------- #
# BankList.xml：只改选中 Bank，其他条目标签原样保留
# --------------------------------------------------------------------------- #
def _attribute(element, name):
    return next((value for key, value in element.attrib.items() if key.casefold() == name.casefold()), None)


def _canonical(element, text: str, span: dict) -> tuple:
    """除 Name 外的原属性排序 + 原始 body 字节（自闭合为空串）。

    Name 值本身不参与比较，否则新旧名永远不等；子内容与注释按原始字节精确比较，
    未知内容不得推断等价。
    """
    attributes = tuple(sorted((key, value) for key, value in element.attrib.items() if key.casefold() != "name"))
    return attributes, text[span["open_end"]:span["close_start"]]


def _bank_list_plan(path: Path, source: dict, old: str, new: str) -> tuple[bytes, dict]:
    text = source["text"]
    root_element = _parse_xml(text, path, "malformed_bank_list")
    if root_element.tag != "BankList":
        raise SC2Error("malformed_bank_list", "BankList.xml 根节点必须为 BankList", path=str(path))
    root_span = dependencies._document_spans(text)
    elements = [element for element in root_element if element.tag == "Bank"]
    spans = [span for span in (root_span or {}).get("children", []) if span["tag"] == "Bank"]
    if not elements:
        raise SC2Error("missing_bank_list_entries", "BankList.xml 没有直属 Bank 条目", path=str(path))
    if len(spans) != len(elements):
        raise SC2Error("malformed_bank_list", "Bank 标签结构不能精确定位",
                       path=str(path), parsed=len(elements), located=len(spans))

    records, identities = [], set()
    for element, span in zip(elements, spans):
        name = _attribute(element, "name")
        start, end = _attr_span(text, span, "name")
        if name is None or text[start:end] != name:
            raise SC2Error("unsupported_bank_list_name", "Bank 缺少或无法定位 Name 属性", path=str(path))
        if not _NAME_RE.match(name):
            raise SC2Error("unsupported_bank_list_name", "Bank 名称不是受支持标识符", path=str(path), name=name)
        identity = (name, _attribute(element, "player"))
        if identity in identities:
            raise SC2Error("duplicate_bank_identity", "BankList 存在重复 Bank 身份（Name+Player）",
                           path=str(path), name=name, player=identity[1])
        identities.add(identity)
        records.append({"name": name, "player": identity[1], "span": span,
                        "element": element, "name_span": (start, end), "profile": _canonical(element, text, span)})

    old_records = [record for record in records if record["name"] == old]
    new_records = [record for record in records if record["name"] == new]
    edits, actions, removed = [], [], 0
    if old_records and new_records:
        new_by_player = {record["player"]: record for record in new_records}
        for record in old_records:
            target = new_by_player.get(record["player"])
            if target is None:
                # 该 Player 没有对应新名条目：独立身份，直接重命名旧条目。
                edits.append(record["name_span"] + (new,))
                actions.append({"action": "rename", "from": old, "to": new, "player": record["player"]})
                continue
            if record["profile"] != target["profile"]:
                raise SC2Error("bank_list_conflict", "新旧 Bank 除 Name 外的属性或子内容不同，拒绝去重",
                               path=str(path), player=record["player"],
                               old_attributes=dict(record["element"].attrib),
                               new_attributes=dict(target["element"].attrib))
            edits.append(_removal(text, record["span"]))
            removed += 1
            actions.append({"action": "deduplicate", "name": new, "player": record["player"]})
    elif old_records:
        for record in old_records:
            edits.append(record["name_span"] + (new,))
            actions.append({"action": "rename", "from": old, "to": new, "player": record["player"]})
    elif new_records:
        actions = [{"action": "already_renamed", "name": new, "player": record["player"]} for record in new_records]
    else:
        raise SC2Error("bank_list_not_found", "BankList.xml 既无旧名也无新名 Bank",
                       path=str(path), old_name=old, new_name=new,
                       existing=sorted({record["name"] for record in records}))

    report = {"component": path.name, "actions": actions, "removed": removed,
              "banks": len(records), "changed": bool(edits)}
    if not edits:
        return source["bytes"], report
    candidate = _apply(source, path, edits)
    _verify_bank_list(candidate, path, old, new, len(records) - removed)
    report["changed"] = candidate != source["bytes"]
    return candidate, report


def _removal(text: str, span: dict) -> tuple[int, int, str]:
    """整项删除；条目独占整行时连同换行删除，保持其余布局不变。"""
    line_start = text.rfind("\n", 0, span["start"]) + 1
    line_end = text.find("\n", span["end"])
    if not text[line_start:span["start"]].strip() and line_end >= 0 and not text[span["end"]:line_end].strip():
        return line_start, line_end + 1, ""
    return span["start"], span["end"], ""


def _verify_bank_list(data: bytes, path: Path, old: str, new: str, expected: int) -> None:
    text, _encoding = dependencies._decode_xml(data, path)
    root_element = _parse_xml(text, path, "bank_list_candidate_mismatch")
    names = [_attribute(element, "name") for element in root_element if element.tag == "Bank"]
    if old in names or new not in names or len(names) != expected:
        raise SC2Error("bank_list_candidate_mismatch", "候选 BankList.xml 不符合预期",
                       path=str(path), names=names, expected=expected)


# --------------------------------------------------------------------------- #
# 公共 API
# --------------------------------------------------------------------------- #
def plan_bank_preload_rename(root: Path, roots: list[Path] | None, old_name: str,
                             new_name: str) -> tuple[dict[str, bytes], dict]:
    """返回 ``({组件名: 精确字节}, 报告)``；已完成时为空变更。不写盘。

    ``roots`` 与其他领域 planner 签名一致；它只是依赖搜索根，组件都从 ``root`` 读取。
    """
    old = _validate_name("old_name", old_name)
    new = _validate_name("new_name", new_name)
    if old == new:
        raise SC2Error("invalid_bank_rename", "old_name 与 new_name 相同，不构成重命名")
    root = Path(root)
    if not root.is_dir():
        raise SC2Error("invalid_root", "组件根必须是已存在的目录", path=str(root))
    document_info = _component(root, "DocumentInfo")
    bank_list = _component(root, "BankList.xml")

    document_source = _source(document_info)
    values = dependencies._parse_document_info(document_source["text"], document_info)["values"]
    _check_header(root, values)

    document_candidate, document_report = _document_info_plan(document_info, document_source, old, new)
    bank_source = _source(bank_list)
    bank_candidate, bank_report = _bank_list_plan(bank_list, bank_source, old, new)

    changes = {}
    if document_candidate != document_source["bytes"]:
        changes[document_info.name] = document_candidate
    if bank_candidate != bank_source["bytes"]:
        changes[bank_list.name] = bank_candidate
    report = {
        "format": "sc2-bank-preload-rename/1",
        "old_name": old,
        "new_name": new,
        "components": {document_info.name: document_report, bank_list.name: bank_report},
        "changed_files": sorted(changes),
        "empty": not changes,
        "scope": "metadata_preload_only",
        "not_renamed": ["Triggers", "MapScript", "源码 Bank API 调用"],
        "header_modified": False,
        "dependencies_modified": False,
        "written": False,
    }
    return changes, report
