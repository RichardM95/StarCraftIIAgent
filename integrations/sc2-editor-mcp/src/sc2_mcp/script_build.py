"""Ordered Galaxy source/Triggers build planning; no writes or native-success claims.

Manifest schema ``sc2-script-build/1``::

  {"schema":"sc2-script-build/1", "files":[{"path":"source/a.galaxy",
    "sha256":"..."}], "init_functions":["Port_Init"],
    "custom_script_id":"731C0117", "identifier":"PortSource",
    "baseline":{"map_script_sha256":"...", "triggers_sha256":"...",
      "files":[{"path":"source/baseline-full.galaxy","sha256":"..."}]}}

``files`` are ordered complete source fragments, with no generated InitMap,
InitCustomScript or MCP_SourceManifest_Init definitions. Original fragment bytes
are embedded unchanged in MapScript. The baseline files are an ordered COMPLETE
copy of the old MapScript, and are required whenever that component exists.
Existing non-generated source is append-only, including globals and function
bodies. Unknown initialization wrappers require an explicit migration elsewhere.
The caller owns transactions/backups and independent semantic review.
This builder does not certify semantic equivalence or compiler acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from sc2_mcp.errors import SC2Error

_SCHEMA = "sc2-script-build/1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_RESERVED = {"InitMap", "InitCustomScript", "MCP_SourceManifest_Init"}
_TOKENS = re.compile(
    r'(?P<space>\s+)|(?P<line>//[^\r\n]*)|(?P<comment>/\*.*?\*/)|'
    r'(?P<string>"(?:\\[^\r\n]|[^"\\\r\n])*")|'
    r"(?P<char>'(?:\\[^\r\n]|[^'\\\r\n])*')|"
    r'(?P<identifier>[A-Za-z_][A-Za-z_0-9]*)|'
    r'(?P<number>0[xX][0-9a-fA-F]+|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)|'
    r'(?P<operator><<=|>>=|==|!=|<=|>=|&&|\|\||<<|>>|\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|[{}()\[\];,.?:~!+*/%<>=&|^\-])',
    re.S,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(code: str, message: str, **details):
    raise SC2Error(code, message, **details)


def _decode(data: bytes, label: str) -> str:
    if data.startswith(b"\xef\xbb\xbf") or b"\0" in data:
        _fail("SCRIPT_BUILD_ENCODING", "来源必须为无 BOM/NUL 的 UTF-8", source=label)
    try:
        return data.decode("utf8")
    except UnicodeError as exc:
        _fail("SCRIPT_BUILD_ENCODING", "来源不是有效 UTF-8", source=label, reason=str(exc))


def galaxy_tokens(data: bytes) -> list[str]:
    """Lexical comparison only. Strings remain exact; comments/whitespace ignored."""
    text = _decode(data, "Galaxy")
    result = []
    position = 0
    while position < len(text):
        match = _TOKENS.match(text, position)
        if text.startswith("/*", position) and (match is None or match.lastgroup != "comment"):
            _fail("SCRIPT_BUILD_UNSUPPORTED_TOKEN", "Galaxy 块注释未闭合", offset=position)
        if match is None:
            _fail("SCRIPT_BUILD_UNSUPPORTED_TOKEN", "未知或未闭合的 Galaxy 词法元素", offset=position,
                  line=text.count("\n", 0, position) + 1, context=text[position:position+40])
        if match.lastgroup not in {"space", "line", "comment"}:
            result.append(match.group())
        position = match.end()
    stack = []
    pairs = {"}": "{", ")": "(", "]": "["}
    for index, token in enumerate(result):
        if token in {"{", "(", "["}:
            stack.append(token)
        elif token in pairs:
            if not stack or stack.pop() != pairs[token]:
                _fail("SCRIPT_BUILD_BALANCE", "Galaxy 括号不匹配", token_index=index)
    if stack:
        _fail("SCRIPT_BUILD_BALANCE", "Galaxy 存在未闭合括号", remaining=stack)
    return result


def _functions(tokens: list[str]) -> dict[str, dict]:
    functions = {}
    depth = 0
    index = 0
    while index < len(tokens):
        if tokens[index] == "{":
            depth += 1
        elif tokens[index] == "}":
            depth -= 1
        if depth == 0 and index >= 2 and tokens[index] == "(":
            name, result_type = tokens[index-1], tokens[index-2]
            if _ID.fullmatch(name) and _ID.fullmatch(result_type):
                end = index + 1
                nested = 1
                while end < len(tokens) and nested:
                    nested += (tokens[end] == "(") - (tokens[end] == ")")
                    end += 1
                if end < len(tokens) and tokens[end] == "{":
                    if name in functions:
                        _fail("SCRIPT_BUILD_DUPLICATE_FUNCTION", "来源含重复函数定义", function=name)
                    parameters = tokens[index+1:end-1]
                    functions[name] = {"return_type": result_type, "parameters": parameters}
        index += 1
    return functions


def _function_spans(tokens: list[str]) -> list[tuple[str, int, int]]:
    """Find complete top-level function token spans; never alter their bodies."""
    result = []
    depth = 0
    index = 0
    while index < len(tokens):
        if depth == 0 and tokens[index] == "(" and index >= 2:
            name, return_type = tokens[index-1], tokens[index-2]
            if _ID.fullmatch(name) and _ID.fullmatch(return_type):
                end = index + 1
                nested = 1
                while end < len(tokens) and nested:
                    nested += (tokens[end] == "(") - (tokens[end] == ")")
                    end += 1
                if end < len(tokens) and tokens[end] == "{":
                    start = index-2
                    if start and tokens[start-1] in {"static", "native"}:
                        start -= 1
                    body_end = end+1
                    braces = 1
                    while body_end < len(tokens) and braces:
                        braces += (tokens[body_end] == "{") - (tokens[body_end] == "}")
                        body_end += 1
                    result.append((name, start, body_end))
                    index = body_end
                    continue
        if tokens[index] == "{":
            depth += 1
        elif tokens[index] == "}":
            depth -= 1
        index += 1
    return result


def _preserve_existing(old_tokens: list[str], new_tokens: list[str], initializers: list[str]):
    spans = _function_spans(old_tokens)
    wrappers = {name: old_tokens[start:end] for name, start, end in spans if name in _RESERVED}
    owned_init_map = galaxy_tokens(b"void InitMap () { InitCustomScript(); }\n")
    owned_custom = galaxy_tokens(b"void InitCustomScript () { MCP_SourceManifest_Init(); }\n")
    empty_init_map = galaxy_tokens(b"void InitMap () { }\n")
    previous_initializers = []
    if "MCP_SourceManifest_Init" in wrappers:
        if wrappers.get("InitMap") != owned_init_map or wrappers.get("InitCustomScript") != owned_custom:
            _fail("SCRIPT_BUILD_INIT_MIGRATION_REQUIRED", "旧初始化不属于已验证构建器链，禁止自动替换")
        adapter = wrappers["MCP_SourceManifest_Init"]
        prefix = ["void", "MCP_SourceManifest_Init", "(", ")", "{"]
        body = adapter[len(prefix):-1]
        if adapter[:len(prefix)] != prefix or len(body) % 4:
            _fail("SCRIPT_BUILD_INIT_MIGRATION_REQUIRED", "旧构建器初始化含未知结构")
        for offset in range(0, len(body), 4):
            name, *suffix = body[offset:offset+4]
            if not _ID.fullmatch(name) or suffix != ["(", ")", ";"]:
                _fail("SCRIPT_BUILD_INIT_MIGRATION_REQUIRED", "旧构建器初始化含非入口调用逻辑")
            previous_initializers.append(name)
        if initializers[:len(previous_initializers)] != previous_initializers:
            _fail("SCRIPT_BUILD_INIT_REMOVAL", "旧初始化入口必须按原顺序完整保留")
    elif wrappers:
        if wrappers != {"InitMap": empty_init_map}:
            _fail("SCRIPT_BUILD_INIT_MIGRATION_REQUIRED", "旧初始化含业务逻辑，需要独立明确迁移方案")
    removed = {index for name, start, end in spans if name in _RESERVED for index in range(start, end)}
    retained = [token for index, token in enumerate(old_tokens) if index not in removed]
    if retained[:2] == ["include", '"TriggerLibs/natives"']:
        retained = retained[2:]
    if new_tokens[:len(retained)] != retained:
        _fail("SCRIPT_BUILD_EXISTING_SOURCE_CHANGED", "已有全局、函数体和顺序必须完整保留；构建仅支持尾部追加")
    return previous_initializers


def _safe_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or "\\" in value or not value:
        _fail("SCRIPT_BUILD_PATH", "来源路径必须为 map-relative POSIX 路径", path=value)
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(p in {"", ".", ".."} or ":" in p for p in value.split("/")):
        _fail("SCRIPT_BUILD_PATH", "来源路径越界或格式不受支持", path=value)
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root):
        _fail("SCRIPT_BUILD_PATH", "来源解析到了地图外部", path=value)
    if not resolved.is_file():
        _fail("SCRIPT_BUILD_SOURCE_MISSING", "来源文件不存在", path=value)
    return resolved


def _source_files(root: Path, entries, *, allow_empty=False) -> tuple[bytes, list[dict]]:
    if not isinstance(entries, list) or (not entries and not allow_empty):
        _fail("SCRIPT_BUILD_MANIFEST", "有序 files 必须是非空数组")
    pieces, evidence, seen = [], [], set()
    newline = None
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            _fail("SCRIPT_BUILD_MANIFEST", "每个来源必须且只能包含 path 和 sha256")
        if not isinstance(entry["sha256"], str) or not _HASH.fullmatch(entry["sha256"]):
            _fail("SCRIPT_BUILD_MANIFEST", "来源 sha256 格式无效", path=entry.get("path"))
        path = _safe_path(root, entry["path"])
        key = str(path).casefold()
        if key in seen:
            _fail("SCRIPT_BUILD_DUPLICATE_SOURCE", "来源文件重复", path=entry["path"])
        seen.add(key)
        data = path.read_bytes()
        if _sha(data) != entry["sha256"]:
            _fail("SCRIPT_BUILD_SOURCE_STALE", "来源已变化", path=entry["path"], expected=entry["sha256"], actual=_sha(data))
        text = _decode(data, entry["path"])
        # A line separator is required at fragment boundaries; bytes are never
        # silently reformatted or completed by this builder.
        if data and not data.endswith(b"\n"):
            _fail("SCRIPT_BUILD_SOURCE_BOUNDARY", "来源片段必须以换行结束", path=entry["path"])
        actual_nl = b"\r\n" if b"\r\n" in data else b"\n"
        if b"\r" in data.replace(b"\r\n", b"") or (actual_nl == b"\r\n" and b"\n" in data.replace(b"\r\n", b"")):
            _fail("SCRIPT_BUILD_NEWLINE", "来源包含混合或不支持的换行", path=entry["path"])
        if data and newline is not None and newline != actual_nl:
            _fail("SCRIPT_BUILD_NEWLINE", "不同来源片段的换行约定不一致")
        if data:
            newline = actual_nl
        pieces.append(data)
        evidence.append({"path":entry["path"], "sha256":entry["sha256"], "bytes":len(data)})
    return b"".join(pieces), evidence


def _callbacks(tokens: list[str], functions: dict) -> list[str]:
    callbacks = []
    for index, token in enumerate(tokens):
        if token != "TriggerCreate" or index+1 >= len(tokens) or tokens[index+1] != "(":
            continue
        # Ignore a native/prototype declaration; regular source calls must use
        # the exact literal callback convention verified by the native fixture.
        if index and tokens[index-1] == "trigger":
            continue
        if index+3 >= len(tokens) or tokens[index+3] != ")" or not re.fullmatch(r'"[A-Za-z_][A-Za-z_0-9]*"', tokens[index+2]):
            _fail("SCRIPT_BUILD_DYNAMIC_CALLBACK", "不支持动态或转义 TriggerCreate 回调；不得猜测目标", token_index=index)
        name = tokens[index+2][1:-1]
        function = functions.get(name)
        if function is None:
            _fail("SCRIPT_BUILD_CALLBACK_MISSING", "字符串回调没有同源函数定义", function=name)
        parameters = function["parameters"]
        if function["return_type"] != "bool" or len(parameters) != 5 or parameters[0] != "bool" or parameters[2] != "," or parameters[3] != "bool":
            _fail("SCRIPT_BUILD_CALLBACK_SIGNATURE", "触发器回调必须为 bool(bool, bool)", function=name)
        callbacks.append(name)
    return callbacks


def _trigger_shape(data: bytes):
    if b"<!--" in data or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "Triggers 含未知注释或声明，禁止整体替换")
    try:
        xml = ET.fromstring(data)
    except ET.ParseError as exc:
        _fail("SCRIPT_BUILD_TRIGGERS_XML", "Triggers 不是有效 XML", reason=str(exc))
    if xml.tag != "TriggerData" or xml.attrib:
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "未知 Triggers 根元素")
    if not list(xml):
        return xml
    roots = xml.findall("Root")
    elements = xml.findall("Element")
    if any(root.attrib for root in roots):
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "Triggers Root 含未知属性")
    if len(roots) == 1 and not list(roots[0]) and len(list(xml)) == 1:
        return xml
    if len(roots) != 1 or len(elements) != 1 or len(list(xml)) != 2:
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "现有 Triggers 不属于已验证的单 CustomScript 结构；不得覆盖")
    element = elements[0]
    if set(element.attrib) != {"Type", "Id"} or element.get("Type") != "CustomScript" or len(list(roots[0])) != 1:
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "存在未归入来源清单的触发器或库")
    item = list(roots[0])[0]
    if item.tag != "Item" or item.attrib != {"Type":"CustomScript", "Id":element.get("Id")}:
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "CustomScript 引用不一致")
    if [child.tag for child in element] != ["Identifier", "ScriptCode", "InitFunc"]:
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "CustomScript 存在未知或缺失字段；不得覆写")
    if any(child.attrib or list(child) for child in element):
        _fail("SCRIPT_BUILD_TRIGGER_LAYOUT_UNSUPPORTED", "CustomScript 字段含未知结构")
    return xml


def _script_code_tokens(text: str | None) -> list[str]:
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if any(not line.startswith("            ") for line in lines):
        _fail("SCRIPT_BUILD_NATIVE_SCRIPT_INDENT", "ScriptCode 未保留已验证的十二空格 XML 缩进")
    return galaxy_tokens(("\n".join(line[12:] for line in lines)+"\n").encode("utf8"))


def _manifest(root: Path, manifest_path: str, expected_sha256: str | None):
    path = _safe_path(root, manifest_path)
    raw = path.read_bytes()
    if expected_sha256 is not None and _sha(raw) != expected_sha256:
        _fail("SCRIPT_BUILD_MANIFEST_STALE", "来源清单已变化", expected=expected_sha256, actual=_sha(raw))
    try:
        value = json.loads(_decode(raw, manifest_path), object_pairs_hook=_unique_object)
    except (ValueError, TypeError) as exc:
        _fail("SCRIPT_BUILD_MANIFEST", "来源清单不是有效 JSON", reason=str(exc))
    if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
        _fail("SCRIPT_BUILD_MANIFEST", "来源清单 schema 不受支持")
    allowed = {"schema", "files", "init_functions", "custom_script_id", "identifier", "baseline"}
    if set(value)-allowed:
        _fail("SCRIPT_BUILD_MANIFEST", "来源清单含未知字段", fields=sorted(set(value)-allowed))
    return value, _sha(raw)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _build(root: Path, manifest_path: str, expected_manifest_sha256: str | None = None):
    root = Path(root).resolve()
    if not root.is_dir():
        _fail("SCRIPT_BUILD_ROOT", "组件地图根不存在")
    manifest, manifest_hash = _manifest(root, manifest_path, expected_manifest_sha256)
    source, files = _source_files(root, manifest.get("files"))
    tokens = galaxy_tokens(source)
    functions = _functions(tokens)
    if not tokens or not functions:
        _fail("SCRIPT_BUILD_EMPTY_SOURCE", "来源必须包含完整函数，不允许空脚本构建")
    if _RESERVED & functions.keys():
        _fail("SCRIPT_BUILD_RESERVED_FUNCTION", "来源定义了构建器保留函数", functions=sorted(_RESERVED & functions.keys()))
    initializers = manifest.get("init_functions")
    if not isinstance(initializers, list) or not initializers or any(not isinstance(name, str) or not _ID.fullmatch(name) for name in initializers) or len(set(initializers)) != len(initializers):
        _fail("SCRIPT_BUILD_INITIALIZERS", "init_functions 必须为非空、无重复的有序函数名数组")
    for name in initializers:
        definition = functions.get(name)
        if definition != {"return_type":"void", "parameters":[]}:
            _fail("SCRIPT_BUILD_INIT_SIGNATURE", "初始化函数缺失或不是 void(void)", function=name)
    callbacks = _callbacks(tokens, functions)
    script_id = manifest.get("custom_script_id", "731C0117")
    identifier = manifest.get("identifier", "OrderedSource")
    if not isinstance(script_id, str) or not re.fullmatch(r"[0-9A-F]{8}", script_id):
        _fail("SCRIPT_BUILD_MANIFEST", "CustomScript Id 必须为八位大写十六进制")
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        _fail("SCRIPT_BUILD_MANIFEST", "Identifier 必须为 ASCII 标识符")
    nl = b"\r\n" if b"\r\n" in source else b"\n"
    adapter = ("void MCP_SourceManifest_Init () {\n"+"".join("    "+name+"();\n" for name in initializers)+"}\n").encode("utf8").replace(b"\n", nl)
    custom = source + adapter
    wrapper = b'\nvoid InitCustomScript () {\n    MCP_SourceManifest_Init();\n}\n\nvoid InitMap () {\n    InitCustomScript();\n}\n'.replace(b"\n", nl)
    script = b'include "TriggerLibs/natives"'+nl+custom+wrapper
    custom_xml = "".join("            "+escape(line)+nl.decode() for line in custom.decode("utf8").splitlines())
    triggers = ('<?xml version="1.0" encoding="utf-8"?>\n<TriggerData>\n    <Root>\n        <Item Type="CustomScript" Id="'+script_id+'"/>\n    </Root>\n    <Element Type="CustomScript" Id="'+script_id+'">\n        <Identifier>'+identifier+'</Identifier>\n        <ScriptCode>\n').replace("\n", nl.decode())+custom_xml+('        </ScriptCode>\n        <InitFunc>MCP_SourceManifest_Init</InitFunc>\n    </Element>\n</TriggerData>\n').replace("\n", nl.decode())
    trigger_bytes = triggers.encode("utf8")
    _trigger_shape(trigger_bytes)
    old_script = root/"MapScript.galaxy"
    old_triggers = root/"Triggers"
    baseline = manifest.get("baseline")
    if old_script.exists() or old_triggers.exists():
        if not isinstance(baseline, dict) or set(baseline) != {"map_script_sha256", "triggers_sha256", "files"}:
            _fail("SCRIPT_BUILD_BASELINE_REQUIRED", "已有组件必须绑定完整旧脚本有序来源和两组件哈希，禁止覆盖稳定逻辑")
        old_data = old_script.read_bytes() if old_script.is_file() else None
        old_trigger_data = old_triggers.read_bytes() if old_triggers.is_file() else None
        for name, data, expected in [("MapScript.galaxy",old_data,baseline["map_script_sha256"]),("Triggers",old_trigger_data,baseline["triggers_sha256"])]:
            if expected != (_sha(data) if data is not None else None):
                _fail("SCRIPT_BUILD_BASELINE_STALE", "现有组件与来源绑定不一致", component=name)
        baseline_source, _ = _source_files(root, baseline["files"], allow_empty=old_data is None)
        if galaxy_tokens(baseline_source) != galaxy_tokens(old_data or b""):
            _fail("SCRIPT_BUILD_BASELINE_INCOMPLETE", "旧脚本未被完整有序来源覆盖")
        old_functions = _functions(galaxy_tokens(old_data or b""))
        missing = set(old_functions)-_RESERVED-functions.keys()
        if missing:
            _fail("SCRIPT_BUILD_FUNCTION_REMOVAL", "构建将删除已有函数；需要独立明确迁移方案", functions=sorted(missing))
        _preserve_existing(galaxy_tokens(old_data or b""), tokens, initializers)
        if old_trigger_data is not None:
            old_xml = _trigger_shape(old_trigger_data)
            if old_xml.find("Element") is not None:
                old_element = old_xml.find("Element")
                if old_element.get("Id") != script_id:
                    _fail("SCRIPT_BUILD_STABLE_ID", "现有 CustomScript Id 不得改名")
                if old_element.findtext("Identifier") != identifier:
                    _fail("SCRIPT_BUILD_STABLE_ID", "现有 CustomScript Identifier 不得改名")
                if old_element.findtext("InitFunc") != "MCP_SourceManifest_Init":
                    _fail("SCRIPT_BUILD_INIT_MIGRATION_REQUIRED", "旧 Triggers 初始化链不属于构建器")
                old_tokens = galaxy_tokens(old_data or b"")
                excluded = {index for name, start, end in _function_spans(old_tokens)
                            if name in {"InitMap", "InitCustomScript"} for index in range(start, end)}
                old_custom = [token for index, token in enumerate(old_tokens) if index not in excluded]
                if old_custom[:2] == ["include", '"TriggerLibs/natives"']:
                    old_custom = old_custom[2:]
                if _script_code_tokens(old_element.findtext("ScriptCode")) != old_custom:
                    _fail("SCRIPT_BUILD_BASELINE_INCOMPLETE", "旧 Triggers 与完整脚本来源不一致")
    elif baseline is not None:
        _fail("SCRIPT_BUILD_BASELINE_STALE", "清单声明了不存在的基线")
    evidence = {"schema":_SCHEMA,"manifest_sha256":manifest_hash,"files":files,"source_sha256":_sha(source),
                "functions":list(functions),"callbacks":callbacks,"init_functions":initializers,
                "map_script_sha256":_sha(script),"triggers_sha256":_sha(trigger_bytes),
                "validation":"source_hashes_and_lexical_structure_only","native_compile_verified":False}
    return {"MapScript.galaxy":script, "Triggers":trigger_bytes}, evidence


def plan_script_build(root: Path, manifest_path: str, expected_manifest_sha256: str | None = None) -> dict[str, bytes | None]:
    """Return two complete candidate components. This function never writes."""
    return _build(root, manifest_path, expected_manifest_sha256)[0]


def inspect_script_build(root: Path, manifest_path: str, expected_manifest_sha256: str | None = None) -> dict:
    return _build(root, manifest_path, expected_manifest_sha256)[1]


def compare_native_roundtrip(root: Path, manifest_path: str, native_root: Path) -> dict:
    """Read-only source agreement. This is never a native compiler verdict."""
    changes, evidence = _build(root, manifest_path)
    native_root = Path(native_root).resolve()
    script_path = native_root/"MapScript.galaxy"
    triggers_path = native_root/"Triggers"
    if not script_path.is_file() or not triggers_path.is_file():
        _fail("SCRIPT_BUILD_NATIVE_COMPONENT_MISSING", "原生候选缺少脚本或 Triggers")
    native_script = script_path.read_bytes()
    native_triggers = triggers_path.read_bytes()
    xml = _trigger_shape(native_triggers)
    element = xml.find("Element")
    if element is None or element.findtext("InitFunc") != "MCP_SourceManifest_Init":
        _fail("SCRIPT_BUILD_NATIVE_INIT_MISMATCH", "原生候选未保留清单初始化入口")
    expected_element = ET.fromstring(changes["Triggers"]).find("Element")
    if element.get("Id") != expected_element.get("Id"):
        _fail("SCRIPT_BUILD_NATIVE_INIT_MISMATCH", "原生候选改变 CustomScript Id")
    if _script_code_tokens(element.findtext("ScriptCode")) != _script_code_tokens(expected_element.findtext("ScriptCode")):
        _fail("SCRIPT_BUILD_NATIVE_SOURCE_MISMATCH", "原生 Triggers 与清单来源词法内容不一致")
    if galaxy_tokens(native_script) != galaxy_tokens(changes["MapScript.galaxy"]):
        _fail("SCRIPT_BUILD_NATIVE_SOURCE_MISMATCH", "原生 MapScript 与清单来源词法内容不一致")
    return {"source_agreement":True,"native_script_sha256":_sha(native_script),"native_triggers_sha256":_sha(native_triggers),
            "manifest_sha256":evidence["manifest_sha256"],"evidence":"lexical_roundtrip_only","native_compile_verified":False}
