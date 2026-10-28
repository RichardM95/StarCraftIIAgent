"""Lossless-source Warcraft analysis. This module never writes or translates code.

The index is lexical, not a JASS AST or a proof of gameplay equivalence. Unknown
dynamic callbacks and damaged bytes remain visible and block complete coverage.
"""
from __future__ import annotations

import hashlib
import re
from collections import deque
from pathlib import Path

from .errors import SC2Error

_FUNCTION = re.compile(r"^function\s+(\w+)\s+takes\s+(.+?)\s+returns\s+(\w+)\s*$")
_NATIVE = re.compile(r"^(?:constant\s+)?native\s+(\w+)\s+takes\s+(.+?)\s+returns\s+(\w+)\s*$")
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_CODE_REF = re.compile(r"\bfunction\s+([A-Za-z_]\w*)")
_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|[A-Za-z_]\w*|[^\s]', re.DOTALL)
_CALLBACK_PARAMETERS = {
    "ExecuteFunc": [0], "DzExecuteFunc": [0], "DzFrameSetScript": [2],
    "DzFrameSetUpdateCallback": [0], "DzTriggerRegisterMouseEvent": [4],
    "DzTriggerRegisterKeyEvent": [4], "DzTriggerRegisterMouseWheelEvent": [2],
    "DzTriggerRegisterMouseMoveEvent": [2], "DzTriggerRegisterWindowResizeEvent": [2],
}


def decode_source(data: bytes) -> tuple[str, dict]:
    """Preserve every source byte, with explicit UTF-8 damage diagnostics.

    Surrogateescape is an internal reversible carrier, never a repair. Reports
    expose offending bytes and offsets; source output must remain original bytes.
    """
    text = data.decode("utf-8", errors="surrogateescape")
    errors = []
    offset = 0
    for line_number, line in enumerate(data.splitlines(keepends=True), 1):
        cursor = 0
        while cursor < len(line):
            try:
                line[cursor:].decode("utf-8")
                break
            except UnicodeDecodeError as exc:
                start = cursor + exc.start
                end = cursor + exc.end
                errors.append({"line": line_number, "byte_offset": offset + start,
                               "hex": line[start:end].hex(), "reason": exc.reason})
                cursor = end
        offset += len(line)
    embedded = []
    for match in re.finditer("\ufeff", text):
        embedded.append({"line": text.count("\n", 0, match.start()) + 1,
                         "character_offset": match.start(), "at_start": match.start() == 0})
    return text, {"encoding": "utf-8", "lossless": True, "encoding_valid": not errors,
                  "invalid_bytes": errors, "bom_locations": embedded,
                  "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _masked(line: str) -> str:
    return _TOKEN.sub(lambda m: " " * len(m.group()) if m.group().startswith(('"', "'", "//")) else m.group(), line)


def _display(text: str) -> str:
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def _literal_arguments(line: str, name: str, offset: int = 0) -> list[str] | None:
    """Return balanced actual arguments, respecting strings and rawcodes."""
    masked = _masked(line)
    match = re.compile(r"\b" + re.escape(name) + r"\s*\(").search(masked, offset)
    if not match:
        return None
    start = match.end()
    depth = 1
    args = []
    for index in range(start, len(masked)):
        char = masked[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                args.append(line[start:index].strip())
                return args
        elif char == "," and depth == 1:
            args.append(line[start:index].strip())
            start = index + 1
    raise SC2Error("war3_unbalanced_call", "JASS 调用参数不平衡", call=name, source=_display(line))


def inspect_jass(data: bytes, source: str = "war3map.j") -> dict:
    text, source_info = decode_source(data)
    lines = text.splitlines()
    raw_lines = data.splitlines(keepends=True)
    functions = []
    natives = []
    callback_parameters = {name:list(positions) for name,positions in _CALLBACK_PARAMETERS.items()}
    for line in lines:
        match = _NATIVE.match(_masked(line).strip())
        if match is None:
            continue
        positions = []
        for index, parameter in enumerate(match[2].split(',')):
            tokens = parameter.strip().split()
            if len(tokens) == 2 and (tokens[0] == 'code' or (tokens[0] == 'string' and tokens[1].casefold() in {'func','funcname','functionname','callback'})):
                positions.append(index)
        if positions:
            callback_parameters[match[1]] = positions
    active = None
    names = set()
    unknown = []
    for number, line in enumerate(lines, 1):
        code = _masked(line).strip().lstrip("\ufeff")
        native = _NATIVE.match(code)
        if native:
            natives.append({"name": native[1], "parameters": native[2], "returns": native[3], "line": number})
        match = _FUNCTION.match(code)
        if match:
            if active is not None or match[1] in names:
                raise SC2Error("war3_function_structure", "JASS 函数嵌套或重名", line=number, function=match[1])
            active = {"name": match[1], "parameters": match[2], "returns": match[3], "line_start": number,
                      "calls": [], "code_references": [], "rawcodes": [], "control": [], "random_calls": [], "dynamic_calls": []}
            names.add(match[1])
            continue
        if code == "endfunction":
            if active is None:
                raise SC2Error("war3_function_structure", "孤立 endfunction", line=number)
            active["line_end"] = number
            body = b"".join(raw_lines[active["line_start"] - 1:number])
            active["source_sha256"] = hashlib.sha256(body).hexdigest()
            functions.append(active)
            active = None
            continue
        if active is None:
            continue
        if re.match(r"(?:if\b|elseif\b|else\b|endif\b|loop\b|endloop\b|exitwhen\b|return\b|local\b)", code):
            active["control"].append({"line": number, "source": _display(line)})
        for call in _CALL.finditer(_masked(line)):
            if call[1] in {"if", "elseif", "return"}:
                continue
            item = {"name": call[1], "line": number, "column": call.start() + 1}
            active["calls"].append(item)
            if call[1] in {"GetRandomInt", "GetRandomReal"}:
                active["random_calls"].append({**item, "source": _display(line)})
            if call[1] in callback_parameters:
                args = _literal_arguments(line, call[1], call.start())
                targets = []
                unresolved_arguments = []
                for position in callback_parameters[call[1]]:
                    value = args[position] if args is not None and position < len(args) else None
                    if value is not None and re.fullmatch(r'"[A-Za-z_]\w*"', value):
                        targets.append(value[1:-1])
                    elif value is not None and re.fullmatch(r'function\s+[A-Za-z_]\w*', value):
                        targets.append(value.split()[1])
                    elif value not in {'null','""'}:
                        unresolved_arguments.append({'position':position,'expression':_display(value) if value is not None else None})
                active["dynamic_calls"].append({**item, "literal_candidates": targets, "source": _display(line),
                                                "unresolved_arguments": unresolved_arguments,
                                                "resolution": "unknown_dynamic" if unresolved_arguments else "literal_pending_symbol_check" if targets else "callback_cleared"})
        for ref in _CODE_REF.finditer(code):
            active["code_references"].append({"name": ref[1], "line": number})
        for token in _TOKEN.finditer(line):
            if token.group().startswith("//"):
                break
            if token.group().startswith("'"):
                raw = token.group()[1:-1]
                if len(raw) != 4:
                    unknown.append({"kind": "non_four_byte_rawcode", "line": number, "literal": _display(raw)})
                active["rawcodes"].append({"id": _display(raw), "line": number})
    if active is not None:
        raise SC2Error("war3_function_structure", "JASS 函数缺少 endfunction", function=active["name"])
    by_name = {entry["name"]: entry for entry in functions}
    edges = []
    for entry in functions:
        for kind in ("calls", "code_references"):
            for ref in entry[kind]:
                if ref["name"] in by_name:
                    edges.append({"caller": entry["name"], "callee": ref["name"], "line": ref["line"], "kind": kind})
        for dynamic in entry["dynamic_calls"]:
            targets = [target for target in dynamic["literal_candidates"] if target in by_name]
            for target in targets:
                edges.append({"caller": entry["name"], "callee": target, "line": dynamic["line"], "kind": "literal_callback"})
            missing_targets = [target for target in dynamic['literal_candidates'] if target not in by_name]
            if missing_targets or dynamic['unresolved_arguments']:
                unknown.append({"kind": "dynamic_callback", "caller": entry["name"], **dynamic})
    reachable = set()
    queue = deque(name for name in ("config", "main") if name in by_name)
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["caller"], []).append(edge["callee"])
    while queue:
        name = queue.popleft()
        if name in reachable:
            continue
        reachable.add(name)
        queue.extend(adjacency.get(name, []))
    for entry in functions:
        entry["reachable"] = entry["name"] in reachable
        entry["classification"] = "excluded_cheat_candidate" if entry["name"].startswith("Tka_") else "requires_port"
        entry["implementation"] = None
        entry["validation"] = {"static": "source_indexed", "editor": "not_run", "runtime": "not_run", "visual": "not_run"}
    return {"schema": "war3-analysis-2", "source": {"path": source, **source_info}, "parser": "ordered_lexical_not_ast",
            "functions": functions, "function_count": len(functions), "natives": natives, "edges": edges,
            "callback_parameters": callback_parameters,
            "reachable_count": len(reachable), "unresolved": unknown,
            "complete": False, "limitations": ["Lexical callback reachability is not whole-program semantic proof.",
                                                  "Missing Blizzard common.j/blizzard.j calls remain external.",
                                                  "No generated implementation or native/runtime acceptance."]}


def inspect_races(data: bytes, analysis: dict | None = None) -> dict:
    text, _ = decode_source(data)
    lines = text.splitlines()
    raw_lines = data.splitlines(keepends=True)
    analysis = analysis if analysis is not None else inspect_jass(data)
    races = []
    for function in analysis["functions"]:
        if not any("选择了" in line for line in lines[function["line_start"] - 1:function["line_end"]]):
            continue
        stack = []
        blocks = []
        for number in range(function["line_start"] + 1, function["line_end"]):
            line = lines[number - 1]
            code = _masked(line).strip()
            if re.match(r"if\b", code):
                selector = re.search(r"GetItemTypeId\s*\(.*?==\s*'([^']{4})'", line)
                block = {"line_start": number, "selector": selector[1] if selector else None, "condition": _display(line), "announcements": []}
                stack.append(block)
            if "选择了" in line and not code.startswith("//"):
                match = re.search(r"选择了([^|\"\r\n]+)", line)
                owner = next((block for block in reversed(stack) if block["selector"]), None)
                if match and owner:
                    owner["announcements"].append({"name": _display(match[1]), "line": number})
            if code == "endif":
                if not stack:
                    raise SC2Error("war3_control_structure", "种族入口中存在孤立 endif", line=number)
                block = stack.pop()
                block["line_end"] = number
                blocks.append(block)
        if stack:
            raise SC2Error("war3_control_structure", "种族入口存在未闭合 if", function=function["name"])
        for block in blocks:
            for announcement in block["announcements"]:
                body = "\n".join(lines[block["line_start"] - 1:block["line_end"]])
                created = []
                upgrades = []
                triggers = []
                for number in range(block["line_start"], block["line_end"] + 1):
                    line = lines[number - 1]
                    for name in ("CreateUnit", "CreateNUnitsAtLoc", "CreateNUnitsAtLocFacingLocBJ", "SetPlayerTechResearchedSwap", "EnableTrigger"):
                        args = _literal_arguments(line, name)
                        if args is None:
                            continue
                        record = {"line": number, "call": name, "arguments": [_display(arg) for arg in args]}
                        if name.startswith("Create"):
                            created.append(record)
                        elif name == "EnableTrigger":
                            triggers.append(record)
                        else:
                            upgrades.append(record)
                races.append({"name": announcement["name"], "announcement_line": announcement["line"],
                              "function": function["name"], "selector_rawcode": block["selector"],
                              "line_start": block["line_start"], "line_end": block["line_end"],
                              "source_sha256": hashlib.sha256(b"".join(raw_lines[block["line_start"] - 1:block["line_end"]])).hexdigest(),
                              "created_units": created, "upgrades": upgrades, "enabled_triggers": triggers,
                              "placed_unit_references": list(dict.fromkeys(re.findall(r"\bgg_unit_\w+", _masked(body)))),
                              "random_calls": [call for call in function["random_calls"] if block["line_start"] <= call["line"] <= block["line_end"]],
                              "coverage": "source_indexed_not_implemented"})
    races.sort(key=lambda entry: entry["line_start"])
    return {"schema": "war3-races-2", "races": races, "race_count": len(races), "complete": False}


def inspect_war3(root: Path) -> dict:
    root = Path(root)
    source = root / "war3map.j"
    if not source.is_file():
        raise SC2Error("war3_source_missing", "需要解包目录中的真实 war3map.j", root=str(root))
    data = source.read_bytes()
    result = inspect_jass(data, str(source))
    result["race_roster"] = inspect_races(data, result)
    return result


def inspect_placements(data: bytes, analysis: dict | None = None) -> dict:
    text, _ = decode_source(data)
    lines = text.splitlines()
    analysis = analysis if analysis is not None else inspect_jass(data)
    units, items, regions, unknown = [], [], [], []
    for function in analysis['functions']:
        aliases = {}
        for number in range(function['line_start'] + 1, function['line_end']):
            line = lines[number - 1]
            code = _masked(line)
            alias = re.search(r'\b(?:local\s+player\s+)?(\w+)\s*=\s*Player\(([^)]+)\)', code)
            if alias:
                aliases[alias[1]] = alias[2]
            for name in ('CreateUnit','CreateItem','Rect'):
                args = _literal_arguments(line,name)
                if args is None:
                    continue
                entry = {'line':number,'function':function['name'],'call':name,'arguments':[_display(arg) for arg in args]}
                if name == 'CreateUnit' and len(args) == 5 and re.fullmatch(r"'[^']{4}'",args[1]):
                    coordinate_arguments = args[2:5]
                    entry['rawcode'] = args[1][1:-1]
                    entry['owner_expression'] = args[0]
                    entry['owner_alias'] = aliases.get(args[0])
                    collection = units
                elif name == 'CreateItem' and len(args) == 3 and re.fullmatch(r"'[^']{4}'",args[0]):
                    coordinate_arguments = args[1:3]
                    entry['rawcode'] = args[0][1:-1]
                    collection = items
                elif name == 'Rect' and function['name'] == 'CreateRegions' and len(args) == 4:
                    coordinate_arguments = args
                    collection = regions
                else:
                    unknown.append(entry)
                    continue
                if not all(re.fullmatch(r'-?(?:\d+(?:\.\d*)?|\.\d+)',arg) for arg in coordinate_arguments):
                    unknown.append(entry)
                    continue
                entry['literal_coordinates'] = [float(arg) for arg in coordinate_arguments]
                assignment = re.search(r'\bset\s+(\w+)\s*=',code)
                entry['handle'] = assignment[1] if assignment else None
                collection.append(entry)
    return {'units':units,'items':items,'regions':regions,'unit_count':len(units),'item_count':len(items),
            'region_count':len(regions),'unresolved_creation_calls':unknown,'complete':False,
            'note':'仅字面坐标调用清单；并非全部对象定义数，也非运行时生成数。'}


def inspect_profiles(data: bytes, source: str = '') -> dict:
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise SC2Error('war3_profile_encoding','原始profile必须单独核验编码',source=source,offset=exc.start) from exc
    sections = []
    active = None
    seen = set()
    for number,line in enumerate(text.splitlines(),1):
        value = line.strip()
        if not value or value.startswith((';','//')):
            continue
        if value.startswith('[') and value.endswith(']'):
            rawcode = value[1:-1]
            if rawcode in seen:
                raise SC2Error('war3_profile_duplicate','profile section 重复，不能猜覆盖',source=source,line=number,rawcode=rawcode)
            seen.add(rawcode)
            active = {'id':rawcode,'line':number,'fields':[]}
            sections.append(active)
        elif active is not None and '=' in line:
            key,value = line.split('=',1)
            active['fields'].append({'key':key.strip(),'value':value,'line':number})
        else:
            raise SC2Error('war3_profile_syntax','profile 出现未知行',source=source,line=number)
    return {'source':source,'sha256':hashlib.sha256(data).hexdigest(),'encoding':'utf-8','sections':sections}


def inspect_object_catalog(root: Path) -> dict:
    from .war3_slk import parse_slk_bytes
    root = Path(root)
    tables = {}
    rawcodes = {}
    unknown = []
    files = [('unit_abilities','File00001945.slk','unitAbilID','Unit'),
             ('unit_balance','File00001946.slk','unitBalanceID','Unit'),
             ('unit_data','File00001947.slk','unitID','Unit'),
             ('unit_ui','File00001948.slk','unitUIID','Unit'),
             ('unit_weapons','File00001949.slk','unitWeapID','Unit'),
             ('item_data','File00001950.slk','itemID','Item')]
    for table,name,key,kind in files:
        path = root/name
        data = path.read_bytes()
        parsed = parse_slk_bytes(data,source=str(path),preserve_unknown_columns=True)
        if key not in parsed['columns']:
            raise SC2Error('war3_slk_schema','原始SLK缺少真实rawcode列',source=str(path),expected=key,columns=parsed['columns'])
        tables[table] = {'file':name,'sha256':hashlib.sha256(data).hexdigest(),**parsed}
        unknown.extend({'source':name,'kind':'unlabelled_slk_column',**cell} for cell in parsed['unknown_cells'])
        for index,row in enumerate(parsed['rows']):
            rawcode = row.get(key)
            if rawcode is None:
                unknown.append({'source':name,'kind':'missing_rawcode','row_index':index})
                continue
            entry = rawcodes.setdefault(rawcode,{'id':rawcode,'catalog_kind':kind,'sources':[]})
            if entry['catalog_kind'] != kind:
                raise SC2Error('war3_rawcode_kind_collision','rawcode存在跨类型冲突',rawcode=rawcode)
            entry['sources'].append({'table':table,'row_index':index,'file':name})
    profiles = {}
    for kind,name in [('Unit','File00001931.xxx'),('Item','File00001943.xxx')]:
        parsed = inspect_profiles((root/name).read_bytes(),str(root/name))
        profiles[kind] = parsed
        for section in parsed['sections']:
            rawcode = section['id']
            entry = rawcodes.setdefault(rawcode,{'id':rawcode,'catalog_kind':kind,'sources':[]})
            if entry['catalog_kind'] != kind:
                raise SC2Error('war3_rawcode_kind_collision','profile存在跨类型冲突',rawcode=rawcode)
            entry['sources'].append({'file':name,'line':section['line'],'type':'profile'})
    return {'schema':'war3-object-catalog-2','tables':tables,'profiles':profiles,
            'rawcode_index':rawcodes,'rawcode_count':len(rawcodes),'unknown':unknown,'complete':not unknown,
            'native_parity':'not_validated'}


def coverage(analysis: dict, implementations: list[dict] | None = None) -> dict:
    """Bind reviewed implementation entries to exact original function hashes."""
    functions = {entry["name"]: entry for entry in analysis["functions"]}
    bound = {}
    for entry in implementations or []:
        name = entry.get("source_function")
        if name not in functions or name in bound or entry.get("source_sha256") != functions[name]["source_sha256"]:
            raise SC2Error("war3_coverage_binding", "覆盖记录重复、来源不存在或指纹过期", function=name)
        if not entry.get("implementation_path") or not entry.get("reviewer") or entry.get("reviewer") == entry.get("author"):
            raise SC2Error("war3_coverage_review", "实现需要路径及非作者审查记录", function=name)
        bound[name] = entry
    entries = [{"source_function": name, "source_sha256": function["source_sha256"],
                "reachable": function["reachable"], "classification": function["classification"],
                "implementation": bound.get(name), "status": "bound_requires_native_validation" if name in bound else "missing"}
               for name, function in functions.items()]
    return {"schema": "war3-coverage-2", "entries": entries, "count": len(entries), "bound_count": len(bound),
            "complete": False, "unresolved": analysis["unresolved"], "native": "not_validated"}


def plan(analysis: dict) -> dict:
    return {"schema": "war3-plan-2", "source_sha256": analysis["source"]["sha256"],
            "race_count": analysis.get("race_roster", {}).get("race_count"),
            "reachable_functions": analysis["reachable_count"],
            "encoding_damage": analysis["source"]["invalid_bytes"],
            "blocked": ["native_compile_control_required", "typed_object_mapping_required", "terrain_native_acceptance_required"],
            "complete": False, "changes": {},
            "note": "只读任务清单，不生成占位 Galaxy 或写入地图。"}
