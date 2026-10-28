"""Read-only Keystone inspection and byte-preserving candidate workflows.

No function in this module writes a map or applies a candidate. Recognized
Galaxy syntax is intentionally bounded; unknown control flow is not evaluated.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from copy import deepcopy
from datetime import date as Date
from functools import lru_cache
import hashlib
import io
import re
import struct
from pathlib import Path

from .errors import SC2Error
from .script import _strip_comments_strings, _balance_diagnostics
from .storage import guard_absolute_path, safe_path

SCRIPT = "MapScript.galaxy"
TEXT = "zhCN.SC2Data/LocalizedData/GameStrings.txt"
KEYSTONE_PROFILE_VERSION = "keystone-20261016-1"
# Complex generated loops are recognized by complete token fingerprints.
# Ignore comments and whitespace outside strings, retain every semantic token.
# A new implementation requires explicit profile review, never anchor guessing.
_FUNCTION_FINGERPRINTS = {
    "lib1_gf_GetUnitTextForCollectionCard": "dac3edf8e6c1d8d35de2b6988fe1f058d99f4ccea467d1dbfbe13e097528b5d9",
    "lib1_gf_GetCardSpecificUnitDisplayName": "28f66fb69b1af102cae0bdcd9abfb5603cea773f2da4434880a12842de29d5d9",
    "lib1_gf_GetUnitDisplayNameasString": "cf523ac82a28cff51ab7ef70ab55fddb50f54a556836b9fcd3a80dc406d77d74",
    "lib1_gf_PortraitsPerPage": "b4c8cd10a655a8a637e242d82b3c7714a2b2953c9c54c63421a79ba3e125d6d4",
    "lib1_gf_PlayerPortraitRowCount": "d2528fe29646cf8bf6d2b6de5dc7e0d92aa1f277b717f591c34b063f38eaccfe",
    "lib1_gf_MaxPortraitPage": "7e8ab0bceda84e1b0362a4b439efed4755f680865f2579bfbe23e26b151a9998",
    "lib1_gf_OpenPortraitPicker": "3d0bbf4133673fb8d00a38677144e2275e86dc505c07edbafaca01c97c88f9b9",
}
_TOKEN = re.compile(r'(?P<comment>//[^\r\n]*|/\*[\s\S]*?\*/)|(?P<string>"(?:\\[^\r\n]|[^"\\\r\n])*")')
_FUNCTION = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?:void|bool|int|fixed|string|text|unit|trigger|point|region|soundlink)[ \t]+(?P<name>\w+)[ \t]*\([^)]*\)[ \t]*\{")
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_CONTROL = {"if", "for", "while", "switch"}
_CATEGORY = {"global": ("GLOBAL", "Global", "全局改动"),
             "protoss": ("PROTOSS", "Protoss", "神族改动"),
             "terran": ("TERRAN", "Terran", "人族改动"),
             "zerg": ("ZERG", "Zerg", "虫族改动")}


def _fail(message, **details):
    raise SC2Error("keystone_structure_unknown", message, **details)


def _decode(raw: bytes, path: str) -> str:
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise SC2Error("keystone_encoding", "组件必须为无 BOM/NUL 的 UTF-8", path=path)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SC2Error("keystone_encoding", "组件不是有效 UTF-8", path=path) from exc


def _string(value: str) -> str:
    if not re.fullmatch(r'"(?:\\[^\r\n]|[^"\\\r\n])*"', value):
        _fail("需要明确的 Galaxy 字符串常量", expression=value)
    escapes = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}
    def unescape(match):
        if match[1] not in escapes:
            _fail("未知 Galaxy 字符串转义", escape=match[0])
        return escapes[match[1]]
    return re.sub(r"\\(.)", unescape, value[1:-1])


def _int(value: str) -> int:
    if not re.fullmatch(r"-?\d+", value):
        _fail("需要明确的 Galaxy 整数常量", expression=value)
    return int(value)


def _input_int(value, name: str, minimum=0) -> int:
    if type(value) is not int or value < minimum or value > 2_147_483_647:
        raise SC2Error("keystone_invalid_input", "参数必须为范围内整数", parameter=name, minimum=minimum)
    return value


def _compact(text):
    return re.sub(r"\s+", "", text)


@dataclass(frozen=True)
class _Function:
    name: str
    start: int
    opening: int
    end: int


@dataclass(frozen=True)
class _Call:
    name: str
    start: int
    end: int
    args: tuple[tuple[int, int], ...]


class _Script:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.text = _decode(raw, SCRIPT)
        self.mask, diagnostics = _strip_comments_strings(self.text)
        diagnostics += _balance_diagnostics(self.text, self.mask)
        if diagnostics:
            raise SC2Error("keystone_script_invalid", "Galaxy 词法或括号检查失败", diagnostics=diagnostics)
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.pairs = {}
        self.opens = []
        self.closes = []
        stack = []
        for pos, char in enumerate(self.mask):
            if char in "({[":
                stack.append(pos)
                if char == "{":
                    self.opens.append(pos)
            elif char in ")}]":
                self.pairs[stack.pop()] = pos
                if char == "}":
                    self.closes.append(pos)
        self.strings = [(m.start(), m.end(), _string(m["string"]))
                        for m in _TOKEN.finditer(self.text) if m["string"]]
        self.functions = {}
        for match in _FUNCTION.finditer(self.mask):
            name = match["name"]
            if name in self.functions:
                _fail("函数定义不唯一", function=name)
            opening = self.mask.index("{", match.start(), match.end())
            self.functions[name] = _Function(name, match.start(), opening, self.pairs[opening] + 1)
        self._calls = {}
        self._cards = None

    def function(self, name):
        if name not in self.functions:
            _fail("缺少已识别的函数定义", function=name)
        return self.functions[name]

    def depth(self, pos):
        return bisect_right(self.opens, pos) - bisect_right(self.closes, pos)

    def line(self, pos):
        return self.text.count("\n", 0, pos) + 1

    def arguments(self, opening, closing):
        spans = []
        start = opening + 1
        pos = start
        while pos < closing:
            if self.mask[pos] in "([{":
                pos = self.pairs[pos] + 1
            elif self.mask[pos] == ",":
                spans.append(self.trim(start, pos))
                start = pos + 1
                pos += 1
            else:
                pos += 1
        if self.text[start:closing].strip() or spans:
            spans.append(self.trim(start, closing))
        return tuple(spans)

    def trim(self, start, end):
        while start < end and self.text[start].isspace():
            start += 1
        while end > start and self.text[end - 1].isspace():
            end -= 1
        return start, end

    def calls(self, function):
        if function.name not in self._calls:
            calls = []
            for match in _CALL.finditer(self.mask, function.opening + 1, function.end - 1):
                if match[1] in _CONTROL:
                    continue
                opening = self.mask.index("(", match.start(), match.end())
                closing = self.pairs[opening]
                calls.append(_Call(match[1], match.start(), closing + 1, self.arguments(opening, closing)))
            self._calls[function.name] = calls
        return self._calls[function.name]

    def arg(self, call, index):
        start, end = call.args[index]
        return self.text[start:end]

    def code(self, function):
        return self.text[function.opening + 1:function.end - 1]

    def clean_code(self, function):
        return _TOKEN.sub(lambda m: " " * len(m[0]) if m["comment"] else m[0], self.code(function))

    def known_function(self, name):
        function = self.functions.get(name)
        if function is None:
            return False
        return hashlib.sha256(self.normalized_code(function).encode("utf-8")).hexdigest() == _FUNCTION_FINGERPRINTS.get(name)

    def normalized_code(self, function):
        code = self.code(function)
        pieces = []
        start = 0
        for token in _TOKEN.finditer(code):
            pieces.append(_compact(code[start:token.start()]))
            if token["string"]:
                pieces.append(token[0])
            start = token.end()
        pieces.append(_compact(code[start:]))
        return "".join(pieces)

    def constant(self, name):
        matches = list(re.finditer(r"\bconst\s+int\s+" + re.escape(name) + r"\s*=\s*(-?\d+)\s*;", self.mask))
        if len(matches) != 1 or self.depth(matches[0].start()) != 0:
            _fail("常量缺失、重复或结构未知", constant=name)
        return int(matches[0][1]), matches[0].span(1)

    def candidate(self, replacements):
        # Offsets are Python Unicode offsets; encoding each unchanged slice
        # preserves the original UTF-8 bytes, including mixed line endings.
        ordered = sorted(replacements, key=lambda row: (row[0], row[1]))
        cursor = 0
        pieces = []
        for start, end, value in ordered:
            if start < cursor or end < start or end > len(self.text):
                _fail("候选修改区间重叠或越界")
            pieces.extend((self.text[cursor:start], value))
            cursor = end
        pieces.append(self.text[cursor:])
        raw = "".join(pieces).encode("utf-8")
        # The syntax guard is re-run on every script candidate.
        text = _decode(raw, SCRIPT)
        mask, errors = _strip_comments_strings(text)
        errors += _balance_diagnostics(text, mask)
        if errors:
            raise SC2Error("keystone_candidate_invalid", "候选 Galaxy 结构检查失败", diagnostics=errors)
        return raw


def _fingerprint(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


@lru_cache(maxsize=2)
def _cached_script(path: str, raw: bytes):
    return _Script(raw)


def _load(root):
    root = guard_absolute_path(Path(root)).resolve()
    path = safe_path(root, SCRIPT)
    if not path.is_file():
        raise SC2Error("keystone_script_missing", "目标缺少 MapScript.galaxy")
    fingerprint = _fingerprint(path)
    raw = path.read_bytes()  # Exactly one read per workflow; parse cache uses content, never timestamps alone.
    if _fingerprint(path) != fingerprint:
        raise SC2Error("keystone_source_changed", "读取脚本时文件已变化")
    return root, _cached_script(str(path), raw)


class _Strings:
    def __init__(self, root, *, dependency=False):
        file = safe_path(root, TEXT)
        if not file.is_file():
            raise SC2Error("keystone_text_missing", "缺少中文 GameStrings.txt", path=str(file))
        self.raw = file.read_bytes()
        self.dependency = dependency
        decode_raw = self.raw[3:] if dependency and self.raw.startswith(b"\xef\xbb\xbf") else self.raw
        self.text = _decode(decode_raw, TEXT)
        self.rows = {}
        offset = 0
        for match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", self.text):
            line = match[0]
            content = line.rstrip("\r\n")
            if "=" in content and not content.startswith("//"):
                key, value = content.split("=", 1)
                self.rows.setdefault(key, []).append((value, offset + len(key) + 1, offset + len(content)))
            offset += len(line)

    def value(self, key):
        rows = self.rows.get(key, [])
        if len(rows) > 1:
            raise SC2Error("keystone_text_ambiguous", "文本键不唯一", key=key)
        return rows[0][0] if rows else None

    def set(self, key, value):
        if self.dependency:
            raise SC2Error("keystone_dependency_readonly", "依赖文本只读，不能生成写入候选")
        if any(c in value for c in "\r\n\x00") or "=" in key:
            raise SC2Error("keystone_invalid_input", "文本值不得注入物理换行或 NUL")
        old = self.value(key)
        if old is not None:
            _, start, end = self.rows[key][0]
            return (self.text[:start] + value + self.text[end:]).encode("utf-8")
        newline = "\r\n" if self.text.count("\r\n") > self.text.count("\n") / 2 else "\n"
        separator = "" if not self.text or self.text.endswith(("\n", "\r")) else newline
        return (self.text + separator + key + "=" + value + newline).encode("utf-8")


def _text_expression(expression, strings):
    match = re.fullmatch(r'StringExternal\s*\(\s*("(?:\\.|[^"\\])*")\s*\)', expression)
    if match:
        key = _string(match[1])
        return key, strings.value(key)
    match = re.fullmatch(r'StringToText\s*\(\s*("(?:\\.|[^"\\])*")\s*\)', expression)
    if match:
        return None, _string(match[1])
    return None, None


def _resolved_ids(script, function, variable, calls):
    unsupported = re.compile(r"\b" + re.escape(variable) + r"\s*(?:\+\+|--|[+*/%\-]=)")
    if unsupported.search(script.mask, function.opening + 1, function.end - 1):
        _fail("注册 ID 使用了未识别的写入形式", function=function.name)
    assignments = list(re.compile(r"\b" + re.escape(variable) + r"\s*=(?!=)\s*([^;]+);").finditer(
        script.mask, function.opening + 1, function.end - 1))
    current = None
    events = [(m.start(), "assign", m) for m in assignments] + [(c.start, "call", c) for c in calls]
    result = {}
    for _, kind, event in sorted(events, key=lambda row: row[0]):
        if kind == "assign":
            if script.depth(event.start()) != script.depth(function.opening):
                current = None
                continue
            expr = _compact(event[1])
            if re.fullmatch(r"-?\d+", expr):
                current = int(expr)
            elif re.fullmatch(r"\(" + re.escape(variable) + r"\+\d+\)", expr) and current is not None:
                current += int(expr.split("+")[1][:-1])
            else:
                current = None
        else:
            arg = script.arg(event, 0)
            value = _int(arg) if re.fullmatch(r"-?\d+", arg) else current if arg == variable else None
            if value is None or script.depth(event.start) != script.depth(function.opening):
                _fail("注册 ID 不属于已识别的顺序赋值", function=function.name, line=script.line(event.start))
            result[event.start] = value
    return result


def _cards(script):
    if script._cards is not None:
        return script._cards
    cards = {}
    maximum, _ = script.constant("lib1_gv_mAX_CARD_ID")
    for function in script.functions.values():
        calls = script.calls(function)
        defines = [c for c in calls if c.name == "lib1_gf_DefineCard"]
        if not defines:
            continue
        ids = _resolved_ids(script, function, "lv_id", defines)
        for index, call in enumerate(defines):
            if len(call.args) != 14:
                _fail("DefineCard 参数结构不匹配", line=script.line(call.start))
            card_id = ids[call.start]
            name = _string(script.arg(call, 3))
            if card_id < 0 or card_id > maximum or card_id in cards:
                raise SC2Error("keystone_card_conflict", "卡牌 ID 冲突或超出上限", card_id=card_id, name=name)
            end = defines[index + 1].start if index + 1 < len(defines) else function.end
            registrations = [c for c in calls if call.end <= c.start < end and
                             (c.name.startswith("lib1_gf_Add") or c.name == "lib1_gf_DefineCardUnit") and
                             c.args and script.arg(c, 0) == script.arg(call, 0)]
            # A new lv_id assignment ends this card even before the next DefineCard.
            intervening = re.search(r"\blv_id\s*=", script.mask[call.end:end])
            if intervening:
                boundary = call.end + intervening.start()
                registrations = [c for c in registrations if c.start < boundary]
            units = []
            effects = []
            if script.arg(call, 10) != "null":
                effects.append({"phase": "default", "trigger": script.arg(call, 10), "line": script.line(call.start)})
            for registration in registrations:
                if registration.name == "lib1_gf_DefineCardUnit":
                    if len(registration.args) != 3:
                        _fail("DefineCardUnit 参数结构不匹配")
                    count_expr = script.arg(registration, 2)
                    units.append({"unit_id": _string(script.arg(registration, 1)),
                                  "count": int(count_expr) if re.fullmatch(r"-?\d+", count_expr) else None,
                                  "count_expression": count_expr, "line": script.line(registration.start)})
                elif registration.name == "lib1_gf_AddEffecttoCardDefinition":
                    if len(registration.args) != 3:
                        _fail("效果注册参数结构不匹配")
                    effects.append({"phase": script.arg(registration, 1), "trigger": script.arg(registration, 2),
                                    "line": script.line(registration.start)})
            cards[card_id] = {"card_id": card_id, "name": name, "max_card_id": maximum,
                              "mineral": _int(script.arg(call, 8)), "gas": _int(script.arg(call, 9)),
                              "set": script.arg(call, 1), "race": script.arg(call, 2),
                              "type": script.arg(call, 5), "subtype": script.arg(call, 6),
                              "rarity": script.arg(call, 7), "units": units, "effects": effects,
                              "registration_function": function.name, "line": script.line(call.start),
                              "_call": call, "_registrations": registrations}
    if not cards:
        _fail("没有找到钥石卡牌注册")
    script._cards = cards
    return cards


def _select(script, card_id=None, name=None):
    cards = _cards(script)
    if card_id is not None:
        _input_int(card_id, "card_id")
    selected = [c for c in cards.values() if (card_id is None or c["card_id"] == card_id) and
                (name is None or c["name"] == name)]
    if len(selected) != 1:
        raise SC2Error("keystone_card_not_unique", "卡牌选择必须精确匹配一个真实注册", card_id=card_id, name=name, matches=len(selected))
    return selected[0]


def _public_card(script, strings, card):
    result = deepcopy({key: value for key, value in card.items() if not key.startswith("_")})
    for field, index in (("display_name", 4), ("base_text", 11)):
        key, value = _text_expression(script.arg(card["_call"], index), strings)
        result[field] = value
        result[field + "_key"] = key
    result["validation"] = "static"
    result["units_scope"] = "DefineCardUnit registrations only; effect-spawned units require effect inspection"
    return result


def _effect_graph(script, effects):
    roots = []
    queue = []
    for effect in effects:
        trigger = effect["trigger"]
        handler, init = trigger + "_Func", trigger + "_Init"
        binding = False
        init_function = script.functions.get(init)
        if init_function:
            binding = any(c.name == "TriggerCreate" and len(c.args) == 1 and
                          script.arg(c, 0) == '"' + handler + '"' for c in script.calls(init_function))
        callers = []
        for function in script.functions.values():
            callers.extend({"function": function.name, "line": script.line(c.start)} for c in script.calls(function) if c.name == init)
        roots.append({**effect, "handler": handler, "handler_exists": handler in script.functions,
                      "init": init, "handler_binding_verified": binding, "init_callers": callers})
        if handler in script.functions:
            queue.append((handler, 0))
    nodes = []
    visited = set()
    truncated = False
    while queue:
        name, depth = queue.pop(0)
        if name in visited:
            continue
        if len(visited) >= 128:
            truncated = True
            break
        visited.add(name)
        function = script.functions[name]
        calls = script.calls(function)
        nodes.append({"function": name, "line": script.line(function.start),
                      "calls": list(dict.fromkeys(c.name for c in calls))})
        children = [c.name for c in calls if c.name in script.functions and c.name not in visited]
        if depth >= 3:
            truncated |= bool(children)
        else:
            queue.extend((child, depth + 1) for child in children)
    return {"roots": roots, "functions": nodes, "truncated": truncated,
            "scope": "static direct calls, depth 3, at most 128 functions; dynamic trigger execution is not evaluated"}


def inspect_keystone_card(root: Path, card_id: int | None = None, name: str | None = None) -> dict:
    """Exact card query, or a bounded metadata index when no selector is given."""
    root, script = _load(root)
    strings = _Strings(root)
    if card_id is None and name is None:
        return {"script_sha256": script.sha256, "validation": "static",
                "cards": [_public_card(script, strings, c) for c in sorted(_cards(script).values(), key=lambda c: c["card_id"])]}
    card = _select(script, card_id, name)
    return {"script_sha256": script.sha256, **_public_card(script, strings, card),
            "effect_chain": _effect_graph(script, card["effects"])}


def plan_keystone_card_cost(root: Path, card_id: int, mineral: int, gas: int) -> dict[str, bytes | None]:
    """Change literal registered costs and the recognized Triple Strike previews."""
    _input_int(mineral, "mineral")
    _input_int(gas, "gas")
    if mineral + gas > 2_147_483_647:
        raise SC2Error("keystone_invalid_input", "费用总和超出 Galaxy 整数范围")
    _, script = _load(root)
    card = _select(script, card_id)
    replacements = [(*card["_call"].args[8], str(mineral)), (*card["_call"].args[9], str(gas))]
    for function_name in ("lib1_gf_HoverStructureDamagingCard", "lib1_gf_StopHoveringStructureDamagingCard"):
        function = script.function(function_name)
        references = [row for row in script.strings if function.opening < row[0] < function.end and row[2] == card["name"]]
        if card["name"] == "Triple Strike":
            # The selected branch must retain its direct remaining-resource
            # reads. Only the unselected literal deduction is replaceable.
            selected_shape = ('if(((lp_removal_card_name=="Precision Airstrike")||((lp_removal_card_name=="Triple Strike")&&(lp_card_is_selected==true)))){'
                              'lv_unspent_resources=(lib1_gf_MineralsRemaining(EventPlayer())+lib1_gf_GasRemaining(EventPlayer()));'
                              'lp_max_targetable_structure_cost=lv_unspent_resources;}')
            if selected_shape not in script.normalized_code(function):
                _fail("三重击已选中预览分支结构未知", function=function_name)
            pattern = re.compile(r'else\s+if\s*\(\(lp_removal_card_name\s*==\s*"Triple Strike"\)\s*&&\s*\(lp_card_is_selected\s*==\s*false\)\)\s*\{\s*'
                                 r'lv_unspent_resources\s*=\s*\(lib1_gf_MineralsRemaining\(EventPlayer\(\)\)\s*\+\s*lib1_gf_GasRemaining\(EventPlayer\(\)\)\);\s*'
                                 r'lp_max_targetable_structure_cost\s*=\s*MaxI\(\(lv_unspent_resources\s*-\s*(\d+)\),\s*0\);\s*\}')
            matches = [m for m in pattern.finditer(script.text, function.opening + 1, function.end - 1)
                       if script.mask[m.start():m.start() + 4] == "else"]
            if len(matches) != 1 or len(references) != 2:
                _fail("三重击悬停预览结构未知", function=function_name)
            match = matches[0]
            if int(match[1]) != card["mineral"] + card["gas"]:
                raise SC2Error("keystone_preview_mismatch", "现有预览费用与注册总费不一致", function=function_name)
            replacements.append((*match.span(1), str(mineral + gas)))
        elif references:
            _fail("卡名出现在尚未识别的费用预览分支", function=function_name, card=card["name"])
    candidate = script.candidate(replacements)
    return {} if candidate == script.raw else {SCRIPT: candidate}


def _description_shape(script):
    if not all(script.known_function(name) for name in (
        "lib1_gf_GetUnitTextForCollectionCard", "lib1_gf_GetCardSpecificUnitDisplayName",
        "lib1_gf_GetUnitDisplayNameasString",
    )):
        return False
    join = ('if((StringLength(lp_unit_text)>=1)&&(StringLength(lp_base_text)>=1)){'
            'lv_unparsed_text=(lp_unit_text+" "+lp_base_text);}'
            'elseif((StringLength(lp_unit_text)>=1)){lv_unparsed_text=lp_unit_text;}'
            'elseif(true){lv_unparsed_text=lp_base_text;}')
    for name in ("lib1_gf_GetCardText", "lib1_gf_GetCardString"):
        function = script.functions.get(name)
        if function is None or join not in script.normalized_code(function):
            return False
    function = script.functions.get("lib1_gf_GetUnitTextForCollectionCard")
    if function is None:
        return False
    code = _compact(script.clean_code(function))
    return all(_compact(part) in code for part in ('lv_text="派出 ";', 'lv_text=(lv_text+"、");',
                                         'lv_text=(lv_text+IntToString(lv_unit_type_count[lv_unit_type_index]));',
                                         'lv_text=(lv_text+" ");', 'lv_text=(lv_text+"。");',
                                         'lib1_gf_GetCardSpecificUnitDisplayName('))


def _unit_name_sources(root, strings, unit_ids, source_context):
    roots = [root]
    context_id = None
    if source_context is not None:
        from .source_context import assert_source_context_current
        assert_source_context_current(source_context)
        if Path(source_context.get("root", "")).resolve() != root:
            raise SC2Error("source_context_roots_mismatch", "描述来源上下文不属于目标地图")
        if source_context.get("locale") != "zhCN":
            raise SC2Error("keystone_invalid_input", "钥石中文描述审计需要 zhCN 来源上下文")
        roots = [Path(path) for path in source_context["roots"]]
        context_id = source_context["source_context_id"]
    from .catalog import _Library
    library = _Library(roots)
    locales = []
    for component in roots:
        file = component / TEXT
        if file.is_file():
            locales.append((str(file), strings if component == root else _Strings(component, dependency=True)))
    result = {}
    for identifier in unit_ids:
        key = None
        field_source = None
        try:
            field = library.inspect("Unit", identifier)["fields"].get("Name")
            if field:
                key, field_source = field["value"], field["source"]
        except SC2Error as exc:
            if exc.code != "catalog_object_not_found":
                # Missing catalog data is an uncertainty, never a name guess.
                result[identifier] = {"value": None, "status": "unknown", "reason": exc.code}
                continue
        implicit = key is None
        key = key or "Unit/Name/" + identifier
        value, source = None, None
        if isinstance(key, str) and not any(token in key for token in ("##", "$")):
            for source_file, locale in locales:
                found = locale.value(key)
                if found is not None:
                    value, source = found, source_file
        result[identifier] = {"value": value, "key": key, "source": source, "field_source": field_source,
            "status": "partial" if value and (implicit or source_context is not None and not source_context.get("complete")) else "known_static" if value else "unknown",
                              "reason": "implicit_engine_name_path" if implicit else None}
    return result, context_id


def audit_keystone_descriptions(root: Path, card_ids: list[int] | None = None, *, source_context: dict | None = None) -> dict:
    """Expand the verified unit-text/base-text composition, without semantic edits.

    ``composed_text`` is before keyword formatting and engine line wrapping.
    Missing dependency names remain explicit placeholders and partial status.
    """
    root, script = _load(root)
    strings = _Strings(root)
    cards = _cards(script)
    if card_ids is not None and (not isinstance(card_ids, list) or any(type(i) is not int for i in card_ids) or len(set(card_ids)) != len(card_ids)):
        raise SC2Error("keystone_invalid_input", "card_ids 必须为无重复整数列表")
    selected = [cards[i] if i in cards else _select(script, i) for i in card_ids] if card_ids is not None else list(cards.values())
    shape_known = _description_shape(script)
    maximum_units, _ = script.constant("lib1_gv_mAX_UNIT_TYPE_PER_CARD")
    if maximum_units < 0:
        _fail("卡牌单位数组容量无效")
    unit_ids = {u["unit_id"] for card in selected for u in card["units"]}
    names, context_id = _unit_name_sources(root, strings, unit_ids, source_context)
    rows = []
    for card in selected:
        public = _public_card(script, strings, card)
        units = []
        grouped = {}
        for unit in card["units"][:maximum_units + 1]:
            # The real collection builder stops at the first nonpositive
            # count, even when a later slot has a registered unit type.
            if unit["count"] is not None and unit["count"] <= 0:
                break
            info = dict(names[unit["unit_id"]])
            # These exact current overrides are recognized only if their
            # guarded returns still exist in the source function.
            override = script.functions.get("lib1_gf_GetCardSpecificUnitDisplayName")
            code = _compact(script.clean_code(override)) if override else ""
            if card["card_id"] == 877 and unit["unit_id"] == "ColossusPurifier2" and 'lp_card_id==877' in code and 'return"巨像-战争使者";' in code:
                info = {"value": "巨像-战争使者", "status": "known_static", "source": override.name}
            if card["card_id"] == 919 and unit["unit_id"] in {"Cyclone", "CycloneMakeshift"} and 'lp_card_id==919' in code and 'Card/Name/Makeshift_Cyclones' in code:
                info = {"value": strings.value("Card/Name/Makeshift_Cyclones"), "status": "known_static", "source": override.name}
            units.append({**unit, "display_name": info})
            label = info["value"] or "[" + unit["unit_id"] + "]"
            grouped.setdefault(label, 0)
            grouped[label] = grouped[label] + unit["count"] if grouped[label] is not None and unit["count"] is not None else None
        unit_text = ("派出 " + "、".join(f"{count if count is not None else '?'} {label}" for label, count in grouped.items()) + "。") if grouped else ""
        base = public["base_text"]
        composed = " ".join(p for p in (unit_text, base) if p) if shape_known and base is not None else None
        duplicates = []
        if base is not None and shape_known:
            plain = re.sub(r"<[^>]*>", "", base)
            if unit_text and _compact(unit_text) in _compact(plain):
                duplicates.append({"status": "exact_duplicate", "text": unit_text})
            else:
                for label, count in grouped.items():
                    if not label.startswith("[") and count is not None:
                        pattern = r"(?<!\d)" + str(count) + r"\s*(?:名|台|只|架|个|艘|座)?\s*" + re.escape(label)
                        match = re.search(pattern, plain)
                        if match:
                            duplicates.append({"status": "possible_duplicate", "text": match[0], "unit_name": label,
                                               "reason": "same count and name; effect semantics require review"})
        status = "known_static" if shape_known and base is not None and all(u["count"] is not None and u["display_name"]["value"] and u["display_name"]["status"] == "known_static" for u in units) else "partial" if shape_known else "unknown"
        rows.append({"card_id": card["card_id"], "name": card["name"], "base_text_key": public["base_text_key"],
                     "base_text": base, "automatic_unit_text": unit_text if shape_known else None,
                     "composed_text": composed, "composition_status": status, "units": units,
                     "duplicates": duplicates, "keyword_registrations": [c.name for c in card["_registrations"] if "toCardDefinition" in c.name],
                     "final_render_status": "not_observed"})
    return {"script_sha256": script.sha256, "source_context_id": context_id, "validation": "static",
            "composition_shape_recognized": shape_known, "cards": rows,
            "limitations": ["输出为自动单位文本与 base_text 拼接，不模拟引擎换行、关键词后处理及界面渲染。", "重复提示不自动改写卡效；未解析单位名称、动态数量和依赖保持 partial/unknown。"]}


def _news_structure(script, category):
    if not isinstance(category, str) or category not in _CATEGORY:
        raise SC2Error("keystone_invalid_input", "公告分类必须为 global/protoss/terran/zerg")
    function = script.function("lib1_gf_SetMainMenuNewsPage")
    token = "lib1_gv_nEWS_CATEGORY_" + _CATEGORY[category][0]
    pattern = re.compile(r"\bif\s*\(\(lp_news_category\s*==\s*" + token + r"\)\)\s*\{")
    branches = []
    for match in pattern.finditer(script.mask, function.opening + 1, function.end - 1):
        opening = script.mask.index("{", match.start(), match.end())
        branches.append((opening, script.pairs[opening]))
    if len(branches) != 2:
        _fail("公告分类计数/映射分支不唯一", category=category)
    count_open, count_close = branches[0]
    count_match = re.fullmatch(r"\s*lv_page_count\s*=\s*(\d+)\s*;\s*", script.mask[count_open + 1:count_close])
    if not count_match:
        _fail("公告页数分支结构未知", category=category)
    count_span = tuple(count_open + 1 + p for p in count_match.span(1))
    mapping_open, mapping_close = branches[1]
    pages = []
    page_pattern = re.compile(r"\bif\s*\(\(lv_page\s*==\s*(\d+)\)\)\s*\{")
    for match in page_pattern.finditer(script.mask, mapping_open + 1, mapping_close):
        opening = script.mask.index("{", match.start(), match.end())
        closing = script.pairs[opening]
        if script.depth(opening) != script.depth(mapping_open) + 1:
            _fail("公告页包含未知嵌套结构", category=category)
        calls = [c for c in script.calls(function) if opening < c.start < closing]
        if len(calls) != 1 or calls[0].name != "StringExternal" or len(calls[0].args) != 1:
            _fail("公告页不是单一文本映射", category=category)
        key = _string(script.arg(calls[0], 0))
        expected = "lv_news_text=StringExternal(" + script.arg(calls[0], 0) + ");"
        if _compact(script.text[opening + 1:closing]) != _compact(expected):
            _fail("公告页包含额外语义", category=category)
        pages.append({"number": int(match[1]), "number_span": match.span(1), "key": key,
                      "start": match.start(), "opening": opening, "closing": closing})
    count = int(count_match[1])
    if not pages or [p["number"] for p in pages] != list(range(1, count + 1)) or len({p["key"] for p in pages}) != len(pages):
        _fail("公告页数、顺序或唯一键不一致", category=category)
    cursor = mapping_open + 1
    for index, page in enumerate(pages):
        between = _compact(script.mask[cursor:page["start"]])
        if between != ("" if index == 0 else "else"):
            _fail("公告页之间包含未知语义", category=category)
        cursor = page["closing"] + 1
    if script.mask[cursor:mapping_close].strip():
        _fail("公告页尾包含未知语义", category=category)
    return {"count": count, "count_span": count_span, "pages": pages, "mapping": (mapping_open, mapping_close)}


def inspect_keystone_news(root: Path, category: str = "global") -> dict:
    root, script = _load(root)
    strings = _Strings(root)
    structure = _news_structure(script, category)
    return {"category": category, "page_count": structure["count"], "script_sha256": script.sha256,
            "pages": [{"page": row["number"], "key": row["key"], "text": strings.value(row["key"])} for row in structure["pages"]],
            "validation": "static"}


def plan_keystone_news(root: Path, category: str, date: str, body: str) -> dict[str, bytes | None]:
    """Append to an existing dated page, otherwise insert a new latest page.

    body is user wording (newlines become <n/>). No other category is touched.
    Backdated insertion is refused; an existing older dated page may be appended.
    """
    try:
        day = Date.fromisoformat(date)
        if day.isoformat() != date:
            raise ValueError
    except (ValueError, TypeError):
        raise SC2Error("keystone_invalid_input", "日期必须为 YYYY-MM-DD") from None
    if not isinstance(body, str) or not body.strip() or "\x00" in body:
        raise SC2Error("keystone_invalid_input", "公告正文必须为非空且无 NUL 的文字")
    body = body.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<n/>")
    root, script = _load(root)
    strings = _Strings(root)
    structure = _news_structure(script, category)
    for page in structure["pages"]:
        if strings.value(page["key"]) is None:
            _fail("历史公告页缺少唯一文本", key=page["key"])
    key = "Param/Value/KSCG2News" + _CATEGORY[category][1] + day.strftime("%Y%m%d")
    current = strings.value(key)
    matching = [p for p in structure["pages"] if p["key"] == key]
    if matching:
        if current is None:
            _fail("同日期公告映射缺少文本", key=key)
        return {TEXT: strings.set(key, current + "<n/>" + body)}
    if current is not None:
        raise SC2Error("keystone_news_key_conflict", "日期文本键存在但不属于本分类分页", key=key)
    dated = [re.search(r"(\d{8})$", p["key"]) for p in structure["pages"]]
    if any(match and match[1] > day.strftime("%Y%m%d") for match in dated):
        raise SC2Error("keystone_news_backdated", "新日期必须晚于现有日期页；历史同日可追加")
    # Shift the exact old page-number tokens and add one branch before the
    # original first if. All old branch bodies, comments and bytes survive.
    first = structure["pages"][0]
    line_start = script.text.rfind("\n", 0, first["start"]) + 1
    indent = script.text[line_start:first["start"]]
    if indent.strip():
        _fail("公告首分支必须独占一行")
    line_end = script.text.find("\n", first["start"])
    newline = "\r\n" if script.text[line_end - 1:line_end + 1] == "\r\n" else "\n"
    unit_indent = re.match(r"[ \t]*", script.text[script.text.find("\n", first["opening"]) + 1:])[0]
    new_branch = (f"if ((lv_page == 1)) {{{newline}{unit_indent}lv_news_text = StringExternal(\"{key}\");{newline}"
                  f"{indent}}}{newline}{indent}else ")
    replacements = [(*structure["count_span"], str(structure["count"] + 1)),
                    (first["start"], first["start"], new_branch)]
    replacements.extend((*page["number_span"], str(page["number"] + 1)) for page in structure["pages"])
    candidate = script.candidate(replacements)
    # Reparse the candidate to establish that all historical keys moved intact.
    checked = _news_structure(_Script(candidate), category)
    if [p["key"] for p in checked["pages"]] != [key] + [p["key"] for p in structure["pages"]]:
        _fail("候选公告历史页核验失败")
    title = f"{day.month}.{day.day} 更新公告<n/>{_CATEGORY[category][2]}<n/>"
    return {SCRIPT: candidate, TEXT: strings.set(key, title + body)}


def _portrait_structure(script):
    for name in ("lib1_gf_PortraitsPerPage", "lib1_gf_PlayerPortraitRowCount",
                 "lib1_gf_MaxPortraitPage", "lib1_gf_OpenPortraitPicker"):
        if not script.known_function(name):
            _fail("头像分页函数语义不属于当前已验证静态配置", function=name, profile=KEYSTONE_PROFILE_VERSION)
    function = script.function("lib1_gt_InitializeCosmeticPortraits_Func")
    calls = [c for c in script.calls(function) if c.name == "lib1_gf_DefineCosmeticPortrait"]
    ids = _resolved_ids(script, function, "lv_display_id", calls)
    entries = []
    for call in calls:
        if len(call.args) != 7:
            _fail("头像注册参数结构未知")
        values = [script.arg(call, i) for i in range(7)]
        if values[0] != "lv_display_id":
            _fail("头像显示索引未沿现有递增变量注册")
        preceding = list(re.finditer(r"\blv_display_id\s*=(?!=)[^;]+;", script.mask[function.opening + 1:call.start]))
        if not preceding or _compact(preceding[-1][0]) != "lv_display_id=(lv_display_id+1);":
            _fail("头像注册前缺少完整显示索引递增")
        if values[4] not in {"true", "false"}:
            _fail("头像专属参数不是布尔常量")
        entries.append({"display_id": ids[call.start], "save_id": _int(values[1]), "image": _string(values[2]),
                        "nemesis_unlock_id": _int(values[3]), "backer_exclusive": values[4] == "true",
                        "support_months_required": _int(values[5]), "standard_wins_required": _int(values[6]),
                        "line": script.line(call.start)})
    if not entries or [e["display_id"] for e in entries] != list(range(len(entries))) or len({e["save_id"] for e in entries}) != len(entries) or any(e["save_id"] < 0 for e in entries):
        raise SC2Error("keystone_portrait_id_conflict", "头像显示索引不连续或持久化 ID 冲突")
    limit, limit_span = script.constant("lib1_gv_pORTRAIT_LIMIT")
    columns, _ = script.constant("lib1_gv_pORTRAIT_PICKER_MAX_COLUMN")
    rows, _ = script.constant("lib1_gv_pORTRAIT_PICKER_MAX_ROW")
    if limit < len(entries) - 1 or min(columns, rows) < 0:
        _fail("头像容量不足或分页常量无效")
    expected = "return((lib1_gv_pORTRAIT_PICKER_MAX_COLUMN+1)*(lib1_gv_pORTRAIT_PICKER_MAX_ROW+1));"
    if expected not in _compact(script.code(script.function("lib1_gf_PortraitsPerPage"))):
        _fail("头像每页容量函数未知")
    row_code = _compact(script.code(script.function("lib1_gf_PlayerPortraitRowCount")))
    page_code = _compact(script.code(script.function("lib1_gf_MaxPortraitPage")))
    picker = script.function("lib1_gf_OpenPortraitPicker")
    picker_calls = {c.name for c in script.calls(picker)}
    if not all(token in row_code for token in ("lib1_gv_pORTRAIT_LIMIT", "lib1_gf_PortraitVisible(", "lib1_gv_pORTRAIT_PICKER_MAX_COLUMN+1")) or not all(token in page_code for token in ("lib1_gf_PlayerPortraitRowCount(", "lib1_gv_pORTRAIT_PICKER_MAX_ROW+1", "returnMaxI((lv_page_count-1),0);")) or not {"lib1_gf_PortraitsPerPage", "lib1_gf_MaxPortraitPage", "lib1_gf_PortraitVisible"}.issubset(picker_calls):
        _fail("头像动态可见性/分页调用链未知")
    # Only a direct final return is accepted after the last registration.
    suffix = script.mask[calls[-1].end:function.end - 1]
    if not re.fullmatch(r"\s*;\s*return\s+true\s*;\s*", suffix):
        _fail("头像注册尾部包含未知语义")
    return {"entries": entries, "limit": limit, "limit_span": limit_span,
            "rows": rows + 1, "columns": columns + 1, "per_page": (rows + 1) * (columns + 1),
            "function": function, "last_call": calls[-1]}


def inspect_keystone_portraits(root: Path) -> dict:
    _, script = _load(root)
    structure = _portrait_structure(script)
    return {"script_sha256": script.sha256, "validation": "static", "entries": structure["entries"],
            "registered_count": len(structure["entries"]), "limit": structure["limit"],
            "next_save_id": max(e["save_id"] for e in structure["entries"]) + 1,
            "next_display_id": len(structure["entries"]), "rows": structure["rows"], "columns": structure["columns"],
            "per_page": structure["per_page"],
            "all_registered_page_count": (len(structure["entries"]) + structure["per_page"] - 1) // structure["per_page"],
            "player_visible_page_count": None, "pagination_status": "dynamic_visibility_chain_recognized"}


def plan_keystone_portrait(root: Path, image: bytes, *, save_id: int | None = None,
                           nemesis_unlock_id: int = -1, backer_exclusive: bool = False,
                           support_months_required: int = 0, standard_wins_required: int = 0) -> dict[str, bytes | None]:
    """Append one portrait with a new stable ID and verified 152² DXT5 bytes."""
    _input_int(nemesis_unlock_id, "nemesis_unlock_id", -1)
    _input_int(support_months_required, "support_months_required")
    _input_int(standard_wins_required, "standard_wins_required")
    if type(backer_exclusive) is not bool or not isinstance(image, bytes) or not image:
        raise SC2Error("keystone_invalid_input", "图片需为非空 bytes，专属参数需为 bool")
    root, script = _load(root)
    structure = _portrait_structure(script)
    if nemesis_unlock_id != -1:
        maximum, _ = script.constant("lib1_gv_mAX_NEMESIS_ID")
        if nemesis_unlock_id > maximum:
            raise SC2Error("keystone_invalid_input", "宿敌解锁 ID 超出真实注册上限", maximum=maximum)
    next_save = max(e["save_id"] for e in structure["entries"]) + 1
    if save_id is None:
        save_id = next_save
    _input_int(save_id, "save_id")
    if save_id != next_save:
        raise SC2Error("keystone_portrait_id_conflict", "新头像持久化 ID 必须追加到真实最大值之后", expected=next_save)
    display_id = len(structure["entries"])
    destination = f"Assets/Textures/custom_portrait_{save_id}.dds"
    path = safe_path(root, destination)
    if path.exists() or any(value.replace("\\", "/").casefold() == destination.casefold() for _, _, value in script.strings):
        raise SC2Error("keystone_asset_collision", "新头像资源路径已存在或已注册", path=destination)
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise SC2Error("keystone_image_backend_missing", "头像转换需要 Pillow DDS/DXT5 支持") from exc
    try:
        with Image.open(io.BytesIO(image)) as source:
            if source.width * source.height > 40_000_000 or getattr(source, "n_frames", 1) != 1:
                raise SC2Error("keystone_image_invalid", "头像需为不超过 4000 万像素的单帧图片")
            source.load()
            rgba = ImageOps.exif_transpose(source).convert("RGBA")
        edge = min(rgba.size)
        left, top = (rgba.width - edge) // 2, (rgba.height - edge) // 2
        result = rgba.crop((left, top, left + edge, top + edge)).resize((152, 152), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        result.save(output, format="DDS", pixel_format="DXT5")
        dds = output.getvalue()
        if len(dds) != 128 + 38 * 38 * 16 or dds[:4] != b"DDS " or dds[84:88] != b"DXT5" or struct.unpack_from("<II", dds, 12) != (152, 152):
            raise SC2Error("keystone_dds_invalid", "DDS header/尺寸/格式/长度验证失败")
        with Image.open(io.BytesIO(dds)) as decoded:
            decoded.load()
            if decoded.size != (152, 152) or decoded.mode != "RGBA":
                raise SC2Error("keystone_dds_invalid", "DDS 重解码验证失败")
    except SC2Error:
        raise
    except Exception as exc:
        raise SC2Error("keystone_image_invalid", "图片解码或 DDS DXT5 转换失败", error=str(exc)) from exc
    last_call = structure["last_call"]
    end = script.text.find("\n", last_call.end)
    if end < 0:
        _fail("头像注册尾行缺少换行")
    newline = "\r\n" if script.text[end - 1:end + 1] == "\r\n" else "\n"
    indent_start = script.text.rfind("\n", 0, last_call.start) + 1
    indent = script.text[indent_start:last_call.start]
    if indent.strip():
        _fail("头像注册必须独占一行")
    asset = destination.replace("/", "\\\\")
    addition = (f"{indent}lv_display_id = (lv_display_id + 1);{newline}"
                f'{indent}lib1_gf_DefineCosmeticPortrait(lv_display_id, {save_id}, "{asset}", {nemesis_unlock_id}, '
                f'{str(backer_exclusive).lower()}, {support_months_required}, {standard_wins_required});{newline}')
    replacements = [(end + 1, end + 1, addition)]
    if display_id > structure["limit"]:
        replacements.append((*structure["limit_span"], str(display_id)))
    candidate = script.candidate(replacements)
    checked = _portrait_structure(_Script(candidate))
    if checked["entries"][:-1] != structure["entries"]:
        # Line numbers of registrations can shift if the limit grows digits;
        # its replacement never adds lines, so they must remain identical.
        _fail("候选头像旧条目保持验证失败")
    return {SCRIPT: candidate, destination: dds}
