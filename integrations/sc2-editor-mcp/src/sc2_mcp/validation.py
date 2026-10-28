from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import SC2Error
from .storage import map_files, safe_path

XML_COMPONENTS = {"DocumentInfo", "ComponentList.SC2Components", "Objects", "Regions", "Triggers", "Attributes"}


def lexical_balance(data: bytes):
    if data.startswith(b"\xef\xbb\xbf") or b"\0" in data:
        raise SC2Error("invalid_script_encoding", "Galaxy 含 BOM 或 NUL")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise SC2Error("invalid_script_encoding", "Galaxy 不是有效 UTF-8") from exc
    from .script import _strip_comments_strings
    cleaned, diagnostics = _strip_comments_strings(text)
    if diagnostics:
        raise SC2Error("invalid_script_lexing", "Galaxy 字符串或注释未正确闭合", diagnostics=diagnostics)
    stack = []
    pairs = {"}": "{", ")": "(", "]": "["}
    for index, char in enumerate(cleaned):
        if char in "{([":
            stack.append((char, index))
        elif char in pairs:
            if not stack or stack[-1][0] != pairs[char]:
                raise SC2Error("unbalanced_script", "Galaxy 括号配对不正确", offset=index)
            stack.pop()
    if stack:
        raise SC2Error("unbalanced_script", "Galaxy 括号未闭合", offset=stack[-1][1])
    return {"balanced": True, "compiler": "not_run"}


def validate_changes(root: Path, changes: dict, profile="generic", domain="general"):
    checked = []
    for relative, data in changes.items():
        safe_path(root, relative)
        if data is None:
            if relative in ("ComponentList.SC2Components", "DocumentInfo", "MapInfo", "BankList.xml"):
                raise SC2Error("protected_component", "不能删除核心组件", path=relative)
            continue
        p = Path(relative)
        if p.suffix.casefold() in (".xml", ".sc2layout", ".sc2components") or relative in XML_COMPONENTS:
            try:
                ET.fromstring(data)
            except ET.ParseError as exc:
                raise SC2Error("invalid_xml", "修改结果 XML 无法解析", path=relative, error=str(exc)) from exc
        if p.suffix.casefold() == ".galaxy":
            lexical_balance(data)
        if p.suffix.casefold() == ".txt":
            try:
                data.decode("utf-8")
            except UnicodeError as exc:
                raise SC2Error("invalid_text", "文本不是 UTF-8", path=relative) from exc
            if b"\0" in data:
                raise SC2Error("invalid_text", "文本含 NUL", path=relative)
        checked.append(relative)
    if profile == "keystone":
        validate_keystone(root, changes, domain)
    if any(rel.startswith('t3') or rel.startswith('CellAttribute_') for rel in changes):
        from .terrain import Terrain
        Terrain(root, changes)
    return {"static": "passed", "scope":"changed-file structure and profile guards",
            "checked_files": checked, "compiler":"not_run", "engine_semantics":"not_verified",
            "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed"}


def validate_keystone(root, changes, domain):
    allowed_shell = {"DocumentInfo", "DocumentHeader"} if domain == "dependencies" else set()
    for rel in {"DocumentInfo", "DocumentHeader", "MapInfo", "BankList.xml"} & changes.keys():
        if rel not in allowed_shell:
            raise SC2Error("keystone_shell_protected", "本操作不能修改钥石地图身份或存档外壳", path=rel)
    for rel in ("MapScript.galaxy", "zhCN.SC2Data/LocalizedData/GameStrings.txt"):
        if rel in changes:
            before, after = (root / rel).read_bytes(), changes[rel]
            if after is None or after.startswith(b"\xef\xbb\xbf") or b"\0" in after:
                raise SC2Error("keystone_encoding", "钥石脚本与文本必须保留 UTF-8 无 BOM")
            old_crlf, old_lf = before.count(b"\r\n"), before.count(b"\n")
            if old_crlf == old_lf and after.count(b"\r\n") != after.count(b"\n"):
                raise SC2Error("newline_changed", "不得改变原有 CRLF 换行")
            if old_crlf == 0 and b"\r\n" in after:
                raise SC2Error("newline_changed", "不得改变原有 LF 换行")
    if "MapScript.galaxy" in changes:
        before = (root / "MapScript.galaxy").read_text("utf-8")
        after = changes["MapScript.galaxy"].decode("utf-8")
        func = r"(?m)^\w[\w \t]*\s+(lib\w+)\s*\([^;\n]*\)\s*\{"
        old_functions, new_functions = re.findall(func, before), re.findall(func, after)
        if [x for x in new_functions if x in set(old_functions)] != old_functions:
            raise SC2Error("keystone_function_order", "钥石既有函数不能删除或重排")
        init = r"(?m)^\s*(lib\w+_Init)\(\);"
        old_init, new_init = re.findall(init, before), re.findall(init, after)
        if [x for x in new_init if x in set(old_init)] != old_init:
            raise SC2Error("keystone_init_order", "钥石既有 Init 调用不能删除或重排")
        for pattern, label in [(r'\bRegionFromId\(\s*\d+\s*\)', "区域绑定"),
                               (r'\b(?:BankVerify|BankSignature|BankOptionSet|BankValue\w+|BankSection\w+|BankLoad|BankOpen)\([^;\n]*', "银行字段与签名")]:
            if re.findall(pattern, before) != re.findall(pattern, after):
                raise SC2Error("keystone_stable_contract", "需要专门迁移工具调整" + label)
        old_cards, old_max = _cards(before)
        new_cards, new_max = _cards(after)
        if old_max is not None and (new_max is None or new_max < old_max):
            raise SC2Error("keystone_card_limit", "不得降低或删除 MAX_CARD_ID")
        for identifier, names in old_cards.items():
            if new_cards.get(identifier) != names:
                raise SC2Error("keystone_card_identity", "既有卡牌编号及内部名称不能改变", card_id=identifier)
        for identifier,names in new_cards.items():
            if len(names)>1 and len(names)>len(old_cards.get(identifier,[])):
                raise SC2Error("keystone_duplicate_card", "新增卡牌 ID 冲突", card_id=identifier)
            if identifier not in old_cards and old_max is not None and identifier<=old_max:
                raise SC2Error("keystone_card_append", "新卡必须追加到原 MAX_CARD_ID 之后", card_id=identifier)
        if new_cards and (new_max is None or max(new_cards)>new_max):
            raise SC2Error("keystone_card_limit", "MAX_CARD_ID 未覆盖全部卡牌")
        old_prototypes=re.findall(r'(?m)^\w+\s+(lib\w+)\s*\([^\n;{}]*\)\s*;',before)
        new_prototypes=re.findall(r'(?m)^\w+\s+(lib\w+)\s*\([^\n;{}]*\)\s*;',after)
        if not set(old_prototypes)<=set(new_prototypes):
            raise SC2Error("keystone_declaration_removed", "不能移除既有函数声明")
        calls=list(re.finditer(init,after))
        anchor=next((m.start() for m in calls if m.group(1)=='lib1_gt_Initialization_Init'),None)
        if anchor is not None:
            for m in calls:
                if m.group(1) not in old_init and m.start()>anchor:
                    raise SC2Error("keystone_late_init", "新 Init 必须在主初始化 Init 之前注册", function=m.group(1))
    # Preserve catalog identifiers even when a caller sends a custom candidate.
    for rel,data in changes.items():
        if '/GameData/' in rel and rel.endswith('.xml') and (root/rel).exists():
            old_ids={(n.tag,n.get('id')) for n in ET.fromstring((root/rel).read_bytes()) if n.get('id')}
            new_ids={(n.tag,n.get('id')) for n in ET.fromstring(data or b'<Catalog/>') if n.get('id')}
            if not old_ids<=new_ids:
                raise SC2Error("keystone_data_identity", "不能移除或改名既有数据 ID", removed=sorted(old_ids-new_ids))
    rel='zhCN.SC2Data/LocalizedData/GameStrings.txt'
    if rel in changes:
        from .localization import card_pair_status
        def keys(data):
            return {line.split('=',1)[0].strip() for line in data.decode('utf-8').splitlines() if '=' in line}
        before_keys=keys((root/rel).read_bytes());after_keys=keys(changes[rel])
        if not before_keys<=after_keys:
            raise SC2Error("keystone_text_key_removed", "不得移除既有内部文本键")
        old_missing={x['key'] for x in card_pair_status(before_keys)['missing']}
        new_missing=card_pair_status(after_keys)['missing']
        if any(x['key'] not in old_missing for x in new_missing):
            raise SC2Error("keystone_card_text_pair", "新增卡名与描述必须成对", missing=new_missing)


def _cards(text):
    # Generated card registration commonly starts at -1 and advances with
    # lv_id = (lv_id + 1). Reading only literal assignments misses most old IDs.
    pattern=(r'(?P<reset>\bint\s+lv_id\s*;)|'
             r'\blv_id\s*(?P<operator>\+=|=)\s*(?P<expression>[^;\n]+);|'
             r'\blib1_gf_DefineCard\s*\(\s*(?P<id>lv_id|\d+)\s*,[^,\n]*,[^,\n]*,\s*"(?P<name>[^"\n]*)"')
    from .script import _strip_comments_strings
    stripped,_=_strip_comments_strings(text)
    cards={}
    current=None
    for m in re.finditer(pattern,text):
        if not stripped[m.start():m.start()+3].strip():
            continue
        if m.group('reset'):
            current=None
        elif m.group('expression') is not None:
            expression=m.group('expression').strip().replace('(','').replace(')','').replace(' ','')
            if re.fullmatch(r'-?\d+',expression):
                value=int(expression)
                current=value if m.group('operator')=='=' else (current+value if current is not None else None)
            elif re.fullmatch(r'lv_id[+-]\d+',expression) and current is not None:
                current+=int(expression[len('lv_id'):])
            else:
                current=None
        else:
            identifier=current if m.group('id')=='lv_id' else int(m.group('id'))
            if identifier is None:
                raise SC2Error('keystone_unknown_card_id','卡牌编号表达式未能静态解析，拒绝推测编号',name=m.group('name'))
            cards.setdefault(identifier,[]).append(m.group('name'))
    maximum=re.search(r'\b(?:lib1_gv_mAX_CARD_ID|MAX_CARD_ID)\s*=\s*(\d+)\s*;',text)
    return cards,int(maximum.group(1)) if maximum else None


def inspect_project(root: Path, profile="generic", cancel=None):
    errors, files = [], 0
    required=['DocumentInfo','DocumentHeader','ComponentList.SC2Components']
    if (root/'t3Terrain.xml').exists():required.append('MapInfo')
    for name in required:
        if not (root/name).is_file():errors.append({'file':name,'code':'missing_component','message':'缺少必要外壳组件'})
    for rel, path in map_files(root):
        if cancel and cancel.is_set():raise SC2Error('cancelled','验证已取消')
        if Path(rel).suffix.casefold() in (".xml", ".sc2layout", ".galaxy", ".sc2components", ".txt") or rel in XML_COMPONENTS:
            files += 1
            try:
                validate_changes(root, {rel: path.read_bytes()}, "generic")
            except SC2Error as exc:
                errors.append({"file": rel, **exc.as_dict()})
    return {"static": "failed" if errors else "passed", "files_checked": files, "errors": errors,
            "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed", "profile": profile}
