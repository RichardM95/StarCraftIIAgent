"""Script domain API for SC2 component maps.

Read-only inspection plus byte-preserving, single-match script replacement.
No function executes scripts or writes to disk.  Static brace balance is a
structural guard only and is never reported as compiler success.
"""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_right
from pathlib import Path
from xml.etree import ElementTree as ET

from sc2_mcp.errors import SC2Error

_BOM = b"\xef\xbb\xbf"
_BACKUP_PARTS = {"backup", "backups", "_codex_backups", ".git", "__pycache__", ".pytest_cache", "node_modules"}
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")

_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default", "return",
    "break", "continue", "sizeof", "catch", "new", "delete",
}

_FUNCTION_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:static|native|public|private|protected)[ \t]+)*"
    r"(?P<ret>[A-Za-z_]\w*)[ \t]+(?P<name>[A-Za-z_]\w*)[ \t]*\((?P<params>[^)]*)\)[ \t]*\{"
)
_DECL_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:static|const)[ \t]+)*(?P<type>[A-Za-z_]\w*)[ \t]+"
    r"(?P<name>[A-Za-z_]\w*)[ \t]*(?:=[ \t]*(?P<init>[^;\n]*?))?[ \t]*;[ \t]*$"
)
_CALL_RE = re.compile(r"(?<![\w])(?P<name>[A-Za-z_]\w*)[ \t]*\(")
_SPATIAL_RE = re.compile(
    r"\b(?P<name>(?:Unit|Doodad|Point|Camera|Region)[A-Za-z_]*FromId|RegionGetCenter|RegionGetBounds|"
    r"Point|UnitGetPosition)\s*\((?P<args>[^)]*)\)"
)


# ---------------------------------------------------------------------------
# discovery / decoding
# ---------------------------------------------------------------------------

def _is_backup(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    for part in rel.parts:
        low = part.lower()
        if low in _BACKUP_PARTS or low.startswith("~") or low.endswith(".bak") or low.endswith(".orig"):
            return True
    return False


def _find_script_files(root: Path) -> list[Path]:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        raise SC2Error("SCRIPT_ROOT_MISSING", f"component root does not exist: {root}", root=str(root))
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".galaxy" and not _is_backup(path, root):
            files.append(path)
    return files


def _to_newline(text: str, nl: str) -> str:
    if nl == "\r\n":
        return text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text.replace("\r\n", "\n")


def _detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# lexical guard: blank out comments and strings, keep offsets
# ---------------------------------------------------------------------------

def _strip_comments_strings(text: str) -> tuple[str, list[dict]]:
    out = list(text)
    diagnostics: list[dict] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            if j < 0:
                j = n
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                diagnostics.append({
                    "severity": "error",
                    "code": "SCRIPT_UNTERMINATED_COMMENT",
                    "message": "unterminated block comment",
                    "line": _line_of(text, i),
                })
                j = n
                end = n
            else:
                end = j + 2
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if c == '"':
            j = i + 1
            closed = False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    closed = True
                    j += 1
                    break
                if text[j] == "\n":
                    break
                j += 1
            if not closed:
                diagnostics.append({
                    "severity": "error",
                    "code": "SCRIPT_UNTERMINATED_STRING",
                    "message": "unterminated string literal",
                    "line": _line_of(text, i),
                })
            for k in range(i, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out), diagnostics


def _balance_diagnostics(text: str, stripped: str) -> list[dict]:
    diagnostics: list[dict] = []
    stack=[]
    pairs={'}':'{',')':'(',']':'['}
    for idx,ch in enumerate(stripped):
        if ch in '{([':
            stack.append((ch,idx))
        elif ch in pairs:
            if not stack or stack[-1][0]!=pairs[ch]:
                return [{'severity':'error','code':'SCRIPT_INVALID_NESTING',
                         'message':f"unexpected '{ch}'",'line':_line_of(text,idx)}]
            stack.pop()
    if stack:
        return [{'severity':'error','code':{'{':'SCRIPT_UNBALANCED_BRACES','(':'SCRIPT_UNBALANCED_PARENS','[':'SCRIPT_UNBALANCED_BRACKETS'}[stack[-1][0]],
                 'message':f"unclosed '{stack[-1][0]}'",'line':_line_of(text,stack[-1][1])}]
    for open_ch, close_ch, code in (("{", "}", "SCRIPT_UNBALANCED_BRACES"), ("(", ")", "SCRIPT_UNBALANCED_PARENS")):
        depth = 0
        bad = False
        for idx, ch in enumerate(stripped):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth < 0:
                    bad = True
                    diagnostics.append({
                        "severity": "error",
                        "code": code,
                        "message": f"unexpected '{close_ch}'",
                        "line": _line_of(text, idx),
                    })
                    depth = 0
        if depth != 0 and not bad:
            diagnostics.append({
                "severity": "error",
                "code": code,
                "message": f"unbalanced '{open_ch}' / '{close_ch}'",
                "line": _line_of(text, len(text)),
            })
    return diagnostics


def _balanced(text: str) -> tuple[bool, list[dict]]:
    stripped, lexical = _strip_comments_strings(text)
    diagnostics = lexical + _balance_diagnostics(text, stripped)
    return (not any(d["severity"] == "error" for d in diagnostics), diagnostics)


def _function_ranges(text: str) -> list[dict]:
    """Return function body spans while preserving the original offsets."""
    stripped, _ = _strip_comments_strings(text)
    brace_ends = {}
    stack = []
    for token in re.finditer(r"[{}]", stripped):
        if token.group() == "{":
            stack.append(token.start())
        elif stack:
            brace_ends[stack.pop()] = token.start()
    result = []
    for match in _FUNCTION_RE.finditer(stripped):
        close = brace_ends.get(match.end() - 1, len(text))
        result.append({
            "name": match.group("name"),
            "start": match.start(),
            "body_start": match.end(),
            "body_end": close,
            "line": _line_of(text, match.start()),
            "body": stripped[match.end():close],
        })
    return result


def _matching_parenthesis(masked: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(masked)):
        if masked[index] == "(":
            depth += 1
        elif masked[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_arguments(value: str) -> list[str]:
    result = []
    start = 0
    depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(value):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    tail = value[start:].strip()
    if tail or value.strip():
        result.append(tail)
    return result


def _trigger_call_records(text: str) -> list[dict]:
    """Read trigger calls without trying to become a Galaxy parser."""
    masked, _ = _strip_comments_strings(text)
    ranges = _function_ranges(text)
    records = []
    pattern = re.compile(r"\b(?P<name>TriggerCreate|TriggerExecute|Wait|TriggerAddEvent[A-Za-z_]*)\s*\(")
    for match in pattern.finditer(masked):
        close = _matching_parenthesis(masked, match.end() - 1)
        if close is None:
            continue
        arguments = _split_arguments(text[match.end():close])
        caller = None
        for function in ranges:
            if function["start"] <= match.start() <= function["body_end"]:
                caller = function["name"]
                break
        record = {
            "name": match.group("name"),
            "line": _line_of(text, match.start()),
            "offset": match.start(),
            "arguments": arguments,
            "caller": caller,
            "evidence": text[match.start():close + 1].strip(),
        }
        records.append(record)
    return records


def _parameter_type(parameter: str) -> str:
    value = re.sub(r"\s+", " ", parameter.strip())
    value = re.sub(r"^(?:const|ref)\s+", "", value)
    return value.split(" ", 1)[0] if value else ""


def _handler_status(name: str, functions: list[dict], prototypes: list[dict]) -> tuple[str, str | None]:
    matches = [item for item in functions if item["name"] == name]
    if len(matches) > 1:
        return "duplicate_definition", "TriggerCreate 回调存在重复函数定义"
    if not matches:
        if any(item["name"] == name for item in prototypes):
            return "declared_only", "TriggerCreate 回调只有声明没有定义"
        return "missing", "TriggerCreate 回调函数未找到"
    function = matches[0]
    parameter_types = [_parameter_type(item) for item in function["params"]]
    if function["return_type"] != "bool" or parameter_types != ["bool", "bool"]:
        return "signature_mismatch", "TriggerCreate 回调必须是 bool(bool, bool)"
    return "valid", None


def _analyze_trigger_flow(text: str, info: dict) -> dict:
    """Build conservative trigger relationships from one Galaxy source file."""
    calls = _trigger_call_records(text)
    functions = info["functions"]
    prototypes = info["prototypes"]
    ranges = _function_ranges(text)
    bindings = []
    binding_by_handle = {}
    events = []
    executions = []
    hazards = []
    unresolved = []
    signature_issues = []
    init_chain = []
    static_names = []
    for match in re.finditer(r"(?m)^\s*static\s+[A-Za-z_]\w*\s+(?P<name>[A-Za-z_]\w*)\s*(?:=[^;\n]*)?;", text):
        if not any(item["start"] <= match.start() <= item["body_end"] for item in ranges):
            static_names.append(match.group("name"))

    for call in calls:
        args = call["arguments"]
        if call["name"] == "TriggerCreate":
            target = None
            dynamic = True
            if len(args) == 1:
                literal = re.fullmatch(r'"([^"\\]*(?:\\.[^"\\]*)*)"', args[0].strip())
                if literal:
                    target = bytes(literal.group(1), "utf-8").decode("unicode_escape")
                    dynamic = False
            prefix = text[max(0, call["offset"] - 200):call["offset"]]
            handle_match = re.search(r"([A-Za-z_]\w*)\s*=\s*$", prefix)
            handle = handle_match.group(1) if handle_match else None
            status, reason = ("dynamic", "TriggerCreate 回调不是可解析的字符串字面量") if dynamic else _handler_status(target, functions, prototypes)
            binding = {
                "binding_id": f"{call['line']}:{handle or '<inline>'}",
                "handle": handle,
                "target_function": target,
                "file_line": call["line"],
                "line": call["line"],
                "caller": call["caller"],
                "handler_status": status,
                "evidence": call["evidence"],
                "confidence": "high" if not dynamic else "low",
            }
            if reason:
                binding["reason"] = reason
            bindings.append(binding)
            if handle:
                if handle in binding_by_handle:
                    signature_issues.append({
                        "severity": "warning",
                        "code": "TRIGGER_HANDLE_REASSIGNED",
                        "message": "同一触发器句柄被重复赋予 TriggerCreate 结果，事件关联可能只对应最后一次创建",
                        "symbol": handle,
                        "line": call["line"],
                        "evidence": call["evidence"],
                        "confidence": "high",
                    })
                binding_by_handle[handle] = binding
            if status in {"missing", "declared_only", "dynamic"}:
                unresolved.append({
                    "symbol": target or "<dynamic TriggerCreate>",
                    "kind": "trigger_callback",
                    "line": call["line"],
                    "evidence": call["evidence"],
                    "confidence": binding["confidence"],
                })
            if status == "signature_mismatch":
                signature_issues.append({
                    "severity": "error",
                    "code": "TRIGGER_HANDLER_SIGNATURE",
                    "message": reason,
                    "symbol": target,
                    "line": call["line"],
                    "evidence": call["evidence"],
                    "confidence": "high",
                })
            elif status == "duplicate_definition":
                signature_issues.append({
                    "severity": "error",
                    "code": "TRIGGER_HANDLER_DUPLICATE",
                    "message": reason,
                    "symbol": target,
                    "line": call["line"],
                    "evidence": call["evidence"],
                    "confidence": "high",
                })
        elif call["name"].startswith("TriggerAddEvent"):
            handle = args[0].strip() if args else None
            binding = binding_by_handle.get(handle)
            events.append({
                "event_function": call["name"],
                "trigger_handle": handle,
                "target_function": binding.get("target_function") if binding else None,
                "registration_function": call["caller"],
                "line": call["line"],
                "arguments": args,
                "registration_status": "bound" if binding else "unresolved_handle",
                "evidence": call["evidence"],
                "confidence": "high" if binding else "low",
            })
        elif call["name"] == "TriggerExecute":
            handle = args[0].strip() if args else None
            separate = None
            if len(args) >= 3 and args[2].strip() in {"true", "false"}:
                separate = args[2].strip() == "true"
            binding = binding_by_handle.get(handle)
            execution = {
                "trigger_handle": handle,
                "target_function": binding.get("target_function") if binding else None,
                "caller": call["caller"],
                "line": call["line"],
                "arguments": args,
                "separate_thread": separate,
                "execution_status": "bound" if binding else "unresolved_handle",
                "evidence": call["evidence"],
                "confidence": "high" if binding else "low",
            }
            executions.append(execution)
        elif call["name"] == "Wait":
            continue

    for call in calls:
        if call["name"] != "Wait":
            continue
        function = next((item for item in ranges if item["name"] == call["caller"]), None)
        if function and not any(item.get("target_function") == call["caller"] for item in bindings):
            hazards.append({
                "severity": "warning",
                "code": "WAIT_IN_UNBOUND_FUNCTION",
                "message": "Wait 出现在尚未被 TriggerCreate 绑定的函数中，需确认调用方式",
                "symbol": call["caller"],
                "line": call["line"],
                "evidence": call["evidence"],
                "confidence": "medium",
            })

    for binding in bindings:
        target = binding.get("target_function")
        target_range = next((item for item in ranges if item["name"] == target), None)
        has_event = any(item["trigger_handle"] == binding["handle"] for item in events) if binding["handle"] else False
        has_execution = any(item["trigger_handle"] == binding["handle"] for item in executions) if binding["handle"] else False
        binding["event_count"] = sum(item["trigger_handle"] == binding["handle"] for item in events) if binding["handle"] else 0
        binding["execution_count"] = sum(item["trigger_handle"] == binding["handle"] for item in executions) if binding["handle"] else 0
        binding["has_wait"] = bool(target_range and re.search(r"\bWait\s*\(", target_range["body"]))
        if target_range and binding["has_wait"] and static_names:
            wait_match = re.search(r"\bWait\s*\(", target_range["body"])
            before_wait = target_range["body"][:wait_match.start()] if wait_match else target_range["body"]
            for static_name in static_names:
                if re.search(rf"\b{re.escape(static_name)}\b", target_range["body"]) and not re.search(rf"\b{re.escape(static_name)}\b", before_wait):
                    hazards.append({
                        "severity": "warning",
                        "code": "STATIC_PARAM_NOT_CAPTURED_BEFORE_WAIT",
                        "message": "线程函数在 Wait 前没有读取所引用的静态变量；若它是参数寄存器，可能被并发调用覆盖",
                        "symbol": target,
                        "line": binding["line"],
                        "evidence": f"{target} uses static {static_name} after Wait",
                        "confidence": "medium",
                    })
        if binding["handle"] and not has_event and not has_execution:
            hazards.append({
                "severity": "warning",
                "code": "TRIGGER_NO_EVENT_OR_EXECUTE",
                "message": "Trigger 已创建，但当前文件没有事件注册或 TriggerExecute 调用",
                "symbol": target,
                "line": binding["line"],
                "evidence": binding["evidence"],
                "confidence": "high",
            })

    for execution in executions:
        if execution["separate_thread"] is True:
            target_range = next((item for item in ranges if item["name"] == execution.get("target_function")), None)
            execution["target_has_wait"] = bool(target_range and re.search(r"\bWait\s*\(", target_range["body"]))
            if execution["target_has_wait"]:
                hazards.append({
                    "severity": "warning",
                    "code": "TRIGGER_EXECUTE_THREAD_WITH_WAIT",
                    "message": "独立线程执行的触发器包含 Wait；若使用静态参数寄存器，必须在首行复制到局部变量",
                    "symbol": execution.get("target_function"),
                    "line": execution["line"],
                    "evidence": execution["evidence"],
                    "confidence": "high",
                })
        elif execution["separate_thread"] is None:
            hazards.append({
                "severity": "warning",
                "code": "TRIGGER_EXECUTE_THREAD_MODE_UNKNOWN",
                "message": "无法确定 TriggerExecute 的第三参数，未判断是否独立线程",
                "symbol": execution.get("target_function"),
                "line": execution["line"],
                "evidence": execution["evidence"],
                "confidence": "medium",
            })

    for edge in info["call_graph"]:
        if edge["callee"].endswith("_Init"):
            init_chain.append({
                "caller": edge["caller"],
                "callee": edge["callee"],
                "line": edge["line"],
                "defined_in_file": any(item["name"] == edge["callee"] for item in functions),
                "confidence": "high",
            })
            if not any(item["name"] == edge["callee"] for item in functions) and not any(item["name"] == edge["callee"] for item in prototypes):
                unresolved.append({
                    "symbol": edge["callee"],
                    "kind": "init_function",
                    "line": edge["line"],
                    "evidence": f"{edge['caller']} -> {edge['callee']}",
                    "confidence": "medium",
                })

    style = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if len(line) > 2048:
            style.append({"severity": "warning", "code": "GALAXY_LINE_TOO_LONG", "message": "Galaxy 行超过 2048 字符", "line": line_number, "evidence": line[:80], "confidence": "high"})
    if "/*" in text:
        style.append({"severity": "warning", "code": "GALAXY_BLOCK_COMMENT", "message": "Galaxy 项目规则要求使用行注释，发现块注释", "line": _line_of(text, text.find("/*")), "evidence": "/*", "confidence": "high"})
    masked, _ = _strip_comments_strings(text)
    for match in re.finditer(r"\+\+|--", masked):
        style.append({"severity": "error", "code": "GALAXY_INCREMENT_OPERATOR", "message": "Galaxy 不支持 ++/--，应使用显式加减赋值", "line": _line_of(text, match.start()), "evidence": text[match.start():match.end()], "confidence": "high"})

    return {
        "trigger_bindings": bindings,
        "trigger_events": events,
        "trigger_exec": executions,
        "async_hazards": hazards,
        "init_chain": init_chain,
        "unresolved_symbols": unresolved,
        "signature_issues": signature_issues,
        "galaxy_style_diagnostics": style,
    }


# ---------------------------------------------------------------------------
# inspection
# ---------------------------------------------------------------------------

def _inspect_text(text: str) -> dict:
    stripped, lexical = _strip_comments_strings(text)
    diagnostics = list(lexical) + _balance_diagnostics(text, stripped)

    functions: list[dict] = []
    signature_spans: list[tuple[int, int]] = []
    line_ends=[m.start() for m in re.finditer('\n',text)]
    line_of=lambda offset:bisect_right(line_ends,offset-1)+1
    brace_ends={};stack=[]
    for token in re.finditer(r'[{}]',stripped):
        if token.group()=='{':stack.append(token.start())
        elif stack:brace_ends[stack.pop()]=token.start()
    bodies=[]
    for match in _FUNCTION_RE.finditer(stripped):
        params = [p.strip() for p in match.group("params").split(",") if p.strip()]
        functions.append({
            "name": match.group("name"),
            "return_type": match.group("ret"),
            "params": params,
            "signature": text[match.start():match.end()].strip(),
            "line": line_of(match.start()),
        })
        signature_spans.append((match.start(), match.end()))
        bodies.append((match.start(),brace_ends.get(match.end()-1,len(text)),match.group('name')))

    prototypes=[]
    for match in re.finditer(r'(?m)^\s*(?:native\s+|static\s+)?(?P<type>\w+)\s+(?P<name>\w+)\s*\([^;{}]*\)\s*;',stripped):
        prototypes.append({'name':match.group('name'),'return_type':match.group('type'),'line':line_of(match.start())})
        signature_spans.append((match.start(),match.end()))
    signature_spans.sort()
    signature_starts=[s for s,_ in signature_spans]
    body_starts=[s for s,_,_ in bodies]
    def in_signature(offset):
        index=bisect_right(signature_starts,offset)-1
        return index>=0 and offset<signature_spans[index][1]

    declarations: list[dict] = []
    initializers: list[dict] = []
    for match in _DECL_RE.finditer(stripped):
        start = match.start()
        if in_signature(start):
            continue
        init = match.group("init")
        entry = {
            "name": match.group("name"),
            "type": match.group("type"),
            "initializer": init.strip() if init else None,
            "line": line_of(start),
        }
        declarations.append(entry)
        if init:
            initializers.append(entry)

    calls: dict[str, dict] = {}
    call_graph=[]
    for match in _CALL_RE.finditer(stripped):
        name = match.group("name")
        if name in _KEYWORDS:
            continue
        if in_signature(match.start()):
            continue
        bucket = calls.setdefault(name, {"name": name, "count": 0, "lines": []})
        bucket["count"] += 1
        line=line_of(match.start())
        bucket["lines"].append(line)
        index=bisect_right(body_starts,match.start())-1
        caller=bodies[index][2] if index>=0 and match.start()<=bodies[index][1] else None
        call_graph.append({'caller':caller,'callee':name,'line':line})

    spatial_refs: list[dict] = []
    for match in _SPATIAL_RE.finditer(stripped):
        spatial_refs.append({
            "kind": match.group("name"),
            "args": match.group("args").strip(),
            "line": line_of(match.start()),
        })

    result = {
        "functions": functions,
        "prototypes":prototypes,
        "call_graph":call_graph,
        "init_calls":[x for x in call_graph if x['callee'].endswith('_Init')],
        "declarations": declarations,
        "initializers": initializers,
        "calls": [calls[name] for name in sorted(calls)],
        "spatial_refs": spatial_refs,
        "diagnostics": diagnostics,
        "balanced": not any(d["severity"] == "error" for d in diagnostics),
    }
    result.update(_analyze_trigger_flow(text, result))
    return result


def inspect_script(root, symbol: str = "") -> dict:
    """Inspect Galaxy script files, optionally filtered by a symbol name."""
    if not isinstance(symbol, str):
        raise SC2Error("SCRIPT_INVALID_SYMBOL", "symbol must be a string", symbol=repr(symbol))
    root = Path(root)
    files = _find_script_files(root)
    if not files:
        raise SC2Error("SCRIPT_SOURCE_MISSING", "no .galaxy script files found", root=str(root))

    report = {
        "symbol": symbol,
        "files": [],
        "functions": [],
        "prototypes":[],
        "call_graph":[],
        "init_calls":[],
        "declarations": [],
        "initializers": [],
        "calls": [],
        "spatial_refs": [],
        "diagnostics": [],
        "trigger_bindings": [],
        "trigger_events": [],
        "trigger_exec": [],
        "async_hazards": [],
        "init_chain": [],
        "unresolved_symbols": [],
        "signature_issues": [],
        "galaxy_style_diagnostics": [],
        "balanced": True,
    }
    for path in files:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if data.startswith(_BOM):
            raise SC2Error("SCRIPT_BOM_REJECTED", f"{rel} starts with a UTF-8 BOM", path=rel)
        if b"\x00" in data:
            raise SC2Error("SCRIPT_NUL_REJECTED", f"{rel} contains a NUL byte", path=rel)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SC2Error("SCRIPT_ENCODING_INVALID", f"{rel} is not valid UTF-8: {exc}", path=rel) from exc
        report["files"].append(rel)
        info = _inspect_text(text)
        report["balanced"] = report["balanced"] and info["balanced"]
        for key in ("functions", "prototypes", "call_graph", "init_calls", "declarations", "initializers", "calls", "spatial_refs", "diagnostics",
                    "trigger_bindings", "trigger_events", "trigger_exec", "async_hazards", "init_chain",
                    "unresolved_symbols", "signature_issues", "galaxy_style_diagnostics"):
            for item in info[key]:
                enriched = dict(item)
                enriched.setdefault("file", rel)
                report[key].append(enriched)

    function_definitions: dict[str, list[dict]] = {}
    for function in report["functions"]:
        function_definitions.setdefault(function["name"], []).append(function)
    prototype_names = {item["name"] for item in report["prototypes"]}
    binding_by_id = {}
    for binding in report["trigger_bindings"]:
        binding_by_id[(binding["file"], binding["handle"])] = binding
        target = binding.get("target_function")
        if binding["confidence"] == "low" or not target:
            continue
        matches = function_definitions.get(target, [])
        if len(matches) > 1:
            binding["handler_status"] = "duplicate_definition"
        elif not matches:
            binding["handler_status"] = "declared_only" if target in prototype_names else "missing"
        else:
            parameter_types = [_parameter_type(item) for item in matches[0]["params"]]
            binding["handler_status"] = "valid" if matches[0]["return_type"] == "bool" and parameter_types == ["bool", "bool"] else "signature_mismatch"
            binding["handler_file"] = matches[0]["file"]
            binding["handler_line"] = matches[0]["line"]

    issue_keys = {(item.get("code"), item.get("symbol"), item.get("line")) for item in report["signature_issues"]}
    for binding in report["trigger_bindings"]:
        status = binding.get("handler_status")
        if status not in {"duplicate_definition", "signature_mismatch"}:
            continue
        code = "TRIGGER_HANDLER_DUPLICATE" if status == "duplicate_definition" else "TRIGGER_HANDLER_SIGNATURE"
        key = (code, binding.get("target_function"), binding.get("line"))
        if key not in issue_keys:
            report["signature_issues"].append({
                "severity": "error",
                "code": code,
                "message": "TriggerCreate 回调定义重复" if status == "duplicate_definition" else "TriggerCreate 回调必须是 bool(bool, bool)",
                "symbol": binding.get("target_function"),
                "line": binding.get("line"),
                "file": binding.get("file"),
                "evidence": binding.get("evidence"),
                "confidence": "high",
            })
            issue_keys.add(key)
    for unresolved in report["unresolved_symbols"]:
        if unresolved.get("kind") != "trigger_callback":
            continue
        target = unresolved.get("symbol")
        if target in function_definitions or target in prototype_names:
            unresolved["resolved_in_other_file"] = True
    report["unresolved_symbols"] = [
        item for item in report["unresolved_symbols"]
        if not (item.get("kind") == "trigger_callback" and item.get("resolved_in_other_file"))
    ]

    for event in report["trigger_events"]:
        binding = binding_by_id.get((event["file"], event["trigger_handle"]))
        if binding:
            event["target_function"] = binding.get("target_function")
            event["registration_status"] = "bound"
            event["confidence"] = binding.get("confidence", "high")
    for execution in report["trigger_exec"]:
        binding = binding_by_id.get((execution["file"], execution["trigger_handle"]))
        if binding:
            execution["target_function"] = binding.get("target_function")
            execution["execution_status"] = "bound"
            execution["confidence"] = binding.get("confidence", "high")
    for edge in report["init_chain"]:
        definitions = function_definitions.get(edge["callee"], [])
        edge["defined_in_file"] = bool(definitions)
        edge["definition_lines"] = [item["line"] for item in definitions]
        edge["confidence"] = "high"
        edge["status"] = "resolved" if definitions else "unresolved"
    called_initializers = {edge["callee"] for edge in report["init_chain"] if edge.get("kind", "edge") == "edge"}
    for function in report["functions"]:
        if function["name"].endswith("_Init") and function["name"] not in called_initializers:
            report["init_chain"].append({
                "kind": "definition",
                "function": function["name"],
                "caller": None,
                "callee": function["name"],
                "line": function["line"],
                "file": function["file"],
                "status": "not_called",
                "defined_in_file": True,
                "definition_lines": [function["line"]],
                "confidence": "medium",
                "evidence": function["signature"],
            })
    for unresolved in report["unresolved_symbols"]:
        if unresolved.get("kind") == "init_function" and unresolved.get("symbol") in function_definitions:
            unresolved["resolved_in_other_file"] = True
    report["unresolved_symbols"] = [
        item for item in report["unresolved_symbols"]
        if not (item.get("kind") == "init_function" and item.get("resolved_in_other_file"))
    ]

    if symbol:
        report["functions"] = [f for f in report["functions"] if symbol in f["name"]]
        report["declarations"] = [d for d in report["declarations"] if symbol in d["name"]]
        report["initializers"] = [i for i in report["initializers"] if symbol in i["name"]]
        report["calls"] = [c for c in report["calls"] if symbol in c["name"]]
        report['prototypes']=[p for p in report['prototypes'] if symbol in p['name']]
        report['call_graph']=[c for c in report['call_graph'] if symbol in c['callee'] or symbol in (c['caller'] or '')]
        report['init_calls']=[c for c in report['init_calls'] if symbol in c['callee'] or symbol in (c['caller'] or '')]
        report['trigger_bindings']=[b for b in report['trigger_bindings'] if symbol in (b.get('target_function') or '') or symbol in (b.get('handle') or '') or symbol in (b.get('caller') or '')]
        report['trigger_events']=[e for e in report['trigger_events'] if symbol in (e.get('target_function') or '') or symbol in (e.get('trigger_handle') or '') or symbol in (e.get('registration_function') or '') or symbol in e.get('event_function','')]
        report['trigger_exec']=[e for e in report['trigger_exec'] if symbol in (e.get('target_function') or '') or symbol in (e.get('trigger_handle') or '') or symbol in (e.get('caller') or '')]
        report['async_hazards']=[h for h in report['async_hazards'] if symbol in (h.get('symbol') or '') or symbol in h.get('evidence','')]
        report['init_chain']=[e for e in report['init_chain'] if symbol in (e.get('caller') or '') or symbol in (e.get('callee') or '')]
        report['unresolved_symbols']=[u for u in report['unresolved_symbols'] if symbol in (u.get('symbol') or '') or symbol in u.get('evidence','')]
        report['signature_issues']=[i for i in report['signature_issues'] if symbol in (i.get('symbol') or '') or symbol in i.get('evidence','')]
        report['galaxy_style_diagnostics']=[d for d in report['galaxy_style_diagnostics'] if symbol in d.get('evidence','')]
        report["symbol_found"] = bool(
            report["functions"] or report["declarations"] or report["calls"] or report["trigger_bindings"]
        )
    return report


def _find_triggers_file(root: Path) -> Path:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        raise SC2Error("TRIGGERS_ROOT_MISSING", f"component root does not exist: {root}", root=str(root))
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _is_backup(path, root) and path.name.lower() in {"triggers", "triggers.xml"}:
            return path
    raise SC2Error("TRIGGERS_SOURCE_MISSING", "no Triggers document found", root=str(root))


def inspect_triggers(root) -> dict:
    """Inspect the Triggers XML document (reading only, no serialization)."""
    root_path = Path(root)
    path = _find_triggers_file(root_path)
    rel = path.relative_to(root_path).as_posix()
    data = path.read_bytes()
    if b"\x00" in data:
        raise SC2Error("TRIGGERS_ENCODING_INVALID", f"{rel} contains a NUL byte", path=rel)
    try:
        tree = ET.fromstring(data)
    except ET.ParseError as exc:
        raise SC2Error("TRIGGERS_XML_INVALID", f"cannot parse {rel}: {exc}", path=rel) from exc

    tag_counts: dict[str, int] = {}
    for element in tree.iter():
        tag_counts[element.tag] = tag_counts.get(element.tag, 0) + 1

    def _collect(tag_names):
        out = []
        for element in tree.iter():
            if element.tag in tag_names:
                out.append({"tag": element.tag, "attributes": dict(element.attrib)})
        return out

    return {
        "path": rel,
        "present": True,
        "root_tag": tree.tag,
        "triggers": _collect({"Trigger"}),
        "variables": _collect({"Variable"}),
        "categories": _collect({"Category"}),
        "elements": _collect({"Element"}),
        "tag_counts": tag_counts,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------

def plan_script_replace(root, old: str, new: str, expected_sha256: str) -> dict:
    """Plan an exact single-context replacement of ``old`` with ``new``.

    Returns ``{relative_posix_path: bytes}``; the source file is not modified.
    """
    if not isinstance(old, str) or old == "":
        raise SC2Error("SCRIPT_INVALID_MATCH", "old must be a non-empty string")
    if not isinstance(new, str):
        raise SC2Error("SCRIPT_INVALID_MATCH", "new must be a string", type=type(new).__name__)
    if "\x00" in new or "\ufeff" in new:
        raise SC2Error("SCRIPT_INVALID_REPLACEMENT", "new must not contain NUL or BOM characters")
    if not isinstance(expected_sha256, str) or not _HASH_RE.match(expected_sha256):
        raise SC2Error("SCRIPT_HASH_INVALID", "expected_sha256 must be 64 hex characters", expected=repr(expected_sha256))
    expected_sha256 = expected_sha256.lower()

    root = Path(root)
    files = _find_script_files(root)
    if not files:
        raise SC2Error("SCRIPT_SOURCE_MISSING", "no .galaxy script files found", root=str(root))

    decoded: list[dict] = []
    encoding_errors: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            encoding_errors.append(rel)
            continue
        decoded.append({
            "path": path,
            "rel": rel,
            "data": data,
            "text": text,
            "bom": data.startswith(_BOM),
            "nul": b"\x00" in data,
        })

    matches: list[tuple[dict, int, int]] = []
    for entry in decoded:
        nl = _detect_newline(entry["text"])
        candidates = {old, _to_newline(old, nl)}
        spans: set[tuple[int, int]] = set()
        for candidate in candidates:
            if candidate == "":
                continue
            start = entry["text"].find(candidate)
            while start >= 0:
                spans.add((start, start + len(candidate)))
                start = entry["text"].find(candidate, start + 1)
        for start, end in sorted(spans):
            matches.append((entry, start, end))

    if not matches:
        if encoding_errors:
            raise SC2Error(
                "SCRIPT_ENCODING_INVALID",
                "no valid UTF-8 script file contained the requested context",
                files=encoding_errors,
            )
        raise SC2Error("SCRIPT_MATCH_NOT_FOUND", "the exact context was not found in any script file")
    if len(matches) > 1:
        raise SC2Error(
            "SCRIPT_MATCH_AMBIGUOUS",
            f"the exact context matched {len(matches)} times; refusing ambiguous replacement",
            matches=[{"path": m[0]["rel"], "line": _line_of(m[0]["text"], m[1])} for m in matches],
        )

    entry, start, end = matches[0]
    if entry["bom"]:
        raise SC2Error("SCRIPT_BOM_REJECTED", f"{entry['rel']} starts with a UTF-8 BOM", path=entry["rel"])
    if entry["nul"]:
        raise SC2Error("SCRIPT_NUL_REJECTED", f"{entry['rel']} contains a NUL byte", path=entry["rel"])

    actual_sha256 = hashlib.sha256(entry["data"]).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SC2Error(
            "SCRIPT_HASH_MISMATCH",
            f"expected sha256 {expected_sha256} but {entry['rel']} has {actual_sha256}",
            path=entry["rel"],
            expected=expected_sha256,
            actual=actual_sha256,
        )

    nl = _detect_newline(entry["text"])
    replacement = _to_newline(new, nl)
    new_text = entry["text"][:start] + replacement + entry["text"][end:]

    balanced, diagnostics = _balanced(new_text)
    if not balanced:
        raise SC2Error(
            "SCRIPT_UNBALANCED_SYNTAX",
            "replacement would leave unbalanced braces/parens or unterminated string/comment",
            path=entry["rel"],
            diagnostics=diagnostics,
        )

    return {entry["rel"]: new_text.encode("utf-8")}
