"""Read-only analysis of StarCraft II Data/Actor XML warning logs.

The editor's warning text is not a compiler database.  This module keeps the
log evidence, binds it to local XML where that is possible, and reports the
boundary between a local candidate fix, dependency merge work, and runtime
verification.  It deliberately never edits a map or rewrites XML.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from .errors import SC2Error
from .storage import digest, safe_path

_EXCLUDED_PARTS = {"_codex_backups", ".git", ".venv", ".pytest_cache", ".sc2-mcp", "__pycache__"}
_XML_WARNING = re.compile(
    r"^\s*\[[^]]+\]\s*警告:\s*XML:\s*(?P<path>.+?)\((?P<line>\d+),(?P<column>\d+)\)\s*:\s*"
    r"(?P<message>.*?)\s{2,}Source:\s*(?P<source>.*?)\s{2,}Entry:\s*(?P<entry>.*?)\s{2,}"
    r"Scope:\s*(?P<scope>.*?)\s*(?:\s{2,}Field:\s*(?P<field>.*?))?\s*$",
    re.IGNORECASE,
)
_XML_WARNING_WITHOUT_ENTRY = re.compile(
    r"^\s*\[[^]]+\]\s*警告:\s*XML:\s*(?P<path>.+?)\((?P<line>\d+),(?P<column>\d+)\)\s*:\s*"
    r"(?P<message>.*?)\s{2,}Source:\s*(?P<source>.*?)\s{2,}Scope:\s*(?P<scope>.*?)\s*$",
    re.IGNORECASE,
)
_USER_ACTOR = re.compile(
    r"^\s*\[[^]]+\]\s*警告:\s*USER:\s*CActor(?P<kind>\w+)\[(?P<entry>[^]]+)\]\s+"
    r"(?P<message>.+?)\s*$",
    re.IGNORECASE,
)
_USER_DOODAD = re.compile(
    r"^\s*\[[^]]+\]\s*警告:\s*USER:\s*\[\s*(?P<object_id>[0-9a-f]+)\s+(?P<index>\d+)\]\s*"
    r"CActorDoodad\[(?P<entry>[^]]+)\]\s*$",
    re.IGNORECASE,
)
_ID_LINE = re.compile(r"<(?P<tag>[A-Za-z_][\w:.-]*)\b[^>]*\bid\s*=\s*['\"](?P<id>[^'\"]+)['\"]")
_FIELD_INDEX = re.compile(r"^(?P<path>[^[]+)\[(?P<index>[^]]+)\]$")
_REFERENCE = re.compile(r"(?:Reference|Link|Actor|Model|Effect|Ability|Upgrade)\s*=\s*['\"]([^'\"]+)['\"]")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _line_texts(raw: bytes) -> list[str]:
    try:
        return raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace").splitlines()


def _relative_path(root: Path, raw: str) -> str | None:
    candidate = Path(raw.replace("/", "\\"))
    try:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root.resolve()):
            return resolved.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    normalized = raw.replace("\\", "/")
    root_text = root.resolve().as_posix().rstrip("/").casefold()
    lower = normalized.casefold()
    marker = root_text + "/"
    if marker in lower:
        return normalized[lower.index(marker) + len(marker):].lstrip("/")
    return None


def _source_class(root: Path, source: str, path: str | None) -> str:
    if path is not None or _relative_path(root, source) is not None:
        return "local_map"
    lower = source.replace("\\", "/").casefold()
    if "/mods/" in lower or lower.startswith("mods/") or ".sc2mod" in lower:
        return "dependency"
    return "external_or_unknown"


def _find_xml_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.xml"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part.casefold() in _EXCLUDED_PARTS for part in relative.parts):
            continue
        # Catalog diagnostics are about map-local data.  Layout and manifest
        # XML is still allowed because Actor/Model overrides may live there.
        result.append(path)
    return sorted(result, key=lambda item: item.as_posix().casefold())


def _line_index(raw: bytes) -> dict[tuple[str, str], list[int]]:
    by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for number, line in enumerate(_line_texts(raw), 1):
        for match in _ID_LINE.finditer(line):
            by_key[(match.group("tag"), match.group("id"))].append(number)
    return by_key


def _object_entries(path: Path) -> tuple[list[dict], list[dict], str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [], [], str(exc)
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        return [], [], str(exc)
    lines = _line_index(raw)
    entries: list[dict] = []
    for element in root.iter():
        object_id = element.attrib.get("id")
        if not object_id:
            continue
        key = (element.tag, object_id)
        line = lines[key].pop(0) if lines.get(key) else None
        entries.append({"tag": element.tag, "id": object_id, "line": line, "element": element})
    return entries, [], None


def _path_values(element: ET.Element, path: str) -> list[ET.Element]:
    current = [element]
    for part in path.split("."):
        current = [child for parent in current for child in list(parent) if child.tag == part]
    return current


def _object_context(inventory: dict[tuple[str, str], list[dict]], entry: str) -> dict | None:
    matches = [item for (tag, object_id), values in inventory.items() if object_id == entry for item in values]
    if not matches:
        return None
    item = matches[0]
    element = item["element"]
    return {
        "tag": item["tag"],
        "id": item["id"],
        "line": item["line"],
        "attributes": dict(element.attrib),
        "children": sorted({child.tag for child in list(element)}),
        "element": element,
    }


def _field_evidence(context: dict | None, field: str | None, message: str) -> dict:
    if context is None:
        return {"found": False}
    evidence: dict = {"found": True, "tag": context["tag"], "line": context["line"], "children": context["children"]}
    if not field and "Unable to find field" in message:
        found = re.search(r"Unable to find field\s+([^\s]+)", message, re.IGNORECASE)
        field = found.group(1) if found else None
    if field and "Unable to use index" in message:
        path = field.split("[", 1)[0]
        if "[" in field:
            path = field.rsplit("[", 1)[0]
        path = path.replace("[0]", "")
        nodes = _path_values(context["element"], path)
        evidence["field_path"] = path
        evidence["local_count"] = len(nodes)
        evidence["local_indexes"] = [node.attrib.get("index") for node in nodes]
        evidence["candidate"] = "为数组项补齐与当前父对象一致的显式 index；修改前需核对依赖合并结果"
    elif field and "Unable to find field" in message:
        field_name = field.rsplit(".", 1)[-1]
        evidence["field"] = field_name
        evidence["present_locally"] = field_name in context["children"]
        aliases = {
            "ModelBuild": "BuildModel",
            "ModelPlacement": "PlacementModel",
            "BuildModel": "ModelBuild",
            "PlacementModel": "ModelPlacement",
        }
        if context["tag"] == "CActorUnit" and field_name in {"ModelBuild", "ModelPlacement"}:
            evidence["probable_alias"] = aliases[field_name]
        elif field_name in aliases and aliases[field_name] in context["children"]:
            evidence["probable_alias"] = aliases[field_name]
    return evidence


def _classify_xml(item: dict, context: dict | None, evidence: dict) -> tuple[str, str, str]:
    message = item["message"]
    source_class = item["source_class"]
    if source_class == "dependency":
        return "dependency_merge", "requires_dependency_audit", "警告来源是 VoidMulti 等依赖项，先核对当前版本与本地覆盖的 Catalog 合并结果"
    if "duplicate entry" in message.lower():
        return "duplicate_id", "requires_reference_audit", "重复 ID 不能直接删除；必须先建立引用闭包并决定稳定的新 ID 或合并方案"
    if "unable to find field" in message.lower():
        if evidence.get("probable_alias"):
            return "invalid_field_name", "safe_to_patch", "本地对象存在对应合法字段名，可生成精确候选替换；仍需编辑器/视觉复核"
        if context and context.get("tag") == "CActorModel":
            return "invalid_actor_model_field", "safe_to_patch", "CActorModel 不应直接承载该 CActorUnit 字段；删除前需确认父 Actor 的模型语义"
        return "invalid_field", "requires_dependency_audit", "当前本地对象未提供足够字段上下文，先核对父对象和依赖字段定义"
    if "unable to use index" in message.lower():
        if evidence.get("local_count") is not None:
            return "array_index", "safe_to_patch", "本地数组结构可定位；补索引前仍需按依赖合并规则核对槽位容量"
        return "array_index", "requires_dependency_audit", "需要父对象和依赖数组容量证据，不能凭日志直接改索引"
    return "xml_warning", "requires_runtime_check", "日志已定位但静态规则不足以证明修复结果"


def _parse_log(root: Path, text: str) -> list[dict]:
    issues: list[dict] = []
    for number, line in enumerate(text.splitlines(), 1):
        match = _XML_WARNING.match(line)
        if not match:
            match = _XML_WARNING_WITHOUT_ENTRY.match(line)
        if match:
            raw_path = match.group("path").strip()
            path = _relative_path(root, raw_path)
            source = match.group("source").strip()
            message = match.group("message").strip()
            entry = _clean(match.groupdict().get("entry"))
            if not entry:
                duplicate = re.search(r"duplicate entry\s+([^\s]+)", message, re.IGNORECASE)
                entry = duplicate.group(1) if duplicate else None
            item = {
                "log_line": number,
                "kind": "xml_warning",
                "severity": "warning",
                "path": path or raw_path,
                "line": int(match.group("line")),
                "column": int(match.group("column")),
                "message": message,
                "source": source,
                "source_class": _source_class(root, source, path),
                "entry": entry,
                "scope": _clean(match.group("scope")),
                    "field": _clean(match.groupdict().get("field")),
            }
            issues.append(item)
            continue
        match = _USER_ACTOR.match(line)
        if match:
            issues.append({
                "log_line": number,
                "kind": "actor_user_warning",
                "severity": "warning",
                "path": "Base.SC2Data/GameData/ActorData.xml",
                "line": None,
                "column": None,
                "message": match.group("message").strip(),
                "source": "USER",
                "source_class": "local_map",
                "entry": match.group("entry").strip(),
                "scope": "CActor" + match.group("kind"),
                "field": None,
            })
            continue
        match = _USER_DOODAD.match(line)
        if match:
            issues.append({
                "log_line": number,
                "kind": "doodad_user_warning",
                "severity": "warning",
                "path": "Objects",
                "line": None,
                "column": None,
                "message": "运行时 ActorDoodad 警告，需要把对象 ID 绑定到 Objects 实例后再判断是否可删除",
                "source": "USER",
                "source_class": "local_map",
                "entry": match.group("entry").strip(),
                "object_id": match.group("object_id").lower(),
                "object_index": int(match.group("index")),
                "scope": "CActorDoodad",
                "field": None,
            })
    return issues


def _objects_evidence(root: Path, object_id: str | None, entry: str | None) -> dict:
    if not object_id:
        return {"found": False}
    path = safe_path(root, "Objects")
    if not path.is_file():
        return {"found": False, "reason": "Objects 不存在"}
    raw = path.read_bytes()
    needle = object_id.encode("ascii", errors="ignore")
    if needle not in raw.lower():
        return {"found": False}
    lines = _line_texts(raw)
    matches = [number for number, line in enumerate(lines, 1) if object_id in line.lower()]
    return {"found": True, "path": "Objects", "object_id": object_id, "entry": entry, "lines": matches[:20]}


def _actor_event_evidence(context: dict | None) -> dict:
    if context is None:
        return {"found": False}
    events = []
    for child in context["element"].iter("On"):
        if not (child.attrib.get("Terms") or "").strip() and not (child.attrib.get("Send") or "").strip():
            events.append({"line": None, "attributes": dict(child.attrib)})
    return {"found": bool(events), "empty_events": events, "check": "父 Actor 继承与同索引覆盖仍需依赖合并或编辑器确认"}


def _object_span(raw: bytes, tag: str, object_id: str) -> tuple[int, int]:
    """Return one local catalog object's byte span without reparsing its bytes."""
    tag_bytes = tag.encode("ascii")
    id_bytes = object_id.encode("utf-8")
    opening = re.compile(
        rb"<" + re.escape(tag_bytes) + rb"\b[^>]*\bid\s*=\s*['\"]"
        + re.escape(id_bytes) + rb"['\"][^>]*>"
    )
    matches = list(opening.finditer(raw))
    if len(matches) != 1:
        raise SC2Error("ambiguous_warning_object", "警告对象在本地 XML 中不是唯一对象", tag=tag, object_id=object_id, count=len(matches))
    start = matches[0].start()
    open_end = matches[0].end()
    if raw[matches[0].start():open_end].rstrip().endswith(b"/>"):
        return start, open_end
    closing = b"</" + tag_bytes + b">"
    end = raw.find(closing, open_end)
    if end < 0:
        raise SC2Error("xml_object_unclosed", "警告对象缺少结束标签", tag=tag, object_id=object_id)
    return start, end + len(closing)


def _replace_scoped(raw: bytes, start: int, end: int, pattern: bytes, replacement: bytes) -> bytes:
    scope = raw[start:end]
    count = len(re.findall(pattern, scope))
    if count != 1:
        raise SC2Error("ambiguous_warning_field", "警告字段在对象内不是唯一字段", count=count)
    candidate = re.sub(pattern, replacement, scope, count=1)
    return raw[:start] + candidate + raw[end:]


def _remove_scoped_line(raw: bytes, start: int, end: int, tag: str) -> bytes:
    scope = raw[start:end]
    pattern = re.compile(rb"(?m)^[ \t]*<" + re.escape(tag.encode("ascii")) + rb"\b[^>]*?/>(?:\r?\n|$)")
    matches = list(pattern.finditer(scope))
    if len(matches) != 1:
        raise SC2Error("ambiguous_warning_field", "待删除字段必须恰好占用一个完整 XML 行", tag=tag, count=len(matches))
    match = matches[0]
    candidate = scope[:match.start()] + scope[match.end():]
    return raw[:start] + candidate + raw[end:]


def _repair_id(kind: str, issue: dict, suffix: str = "") -> str:
    path = issue.get("path") or ""
    entry = issue.get("entry") or ""
    field = issue.get("local_evidence", {}).get("field") or issue.get("field") or ""
    return ":".join((kind, path, entry, field, suffix)).rstrip(":")


def plan_warning_repairs(root: Path, *, log_text: str | None = None, log_path: Path | None = None,
                         repair_ids: list[str] | None = None, include_inferred: bool = False) -> dict:
    """Plan byte-preserving repairs for locally provable XML warnings.

    The returned ``changes`` are complete candidate bytes and are intended for
    the central transaction service.  Dependency merge, duplicate-ID, empty
    event and runtime warnings remain blocked.  Inferred array/index and
    invalid CActorModel repairs require explicit ``include_inferred=True``.
    """
    root = Path(root).resolve()
    audit = inspect_data_warnings(root, log_text=log_text, log_path=log_path)
    selected = set(repair_ids) if repair_ids is not None else None
    original: dict[str, bytes] = {}
    working: dict[str, bytes] = {}
    candidates: list[dict] = []
    blocked: list[dict] = []
    seen_blocked: set[tuple] = set()

    def add_blocked(issue: dict, reason: str, *, repair_id: str | None = None) -> None:
        key = (issue.get("diagnostic"), issue.get("path"), issue.get("entry"), issue.get("field"), reason)
        if key in seen_blocked:
            return
        seen_blocked.add(key)
        blocked.append({
            "repair_id": repair_id,
            "diagnostic": issue.get("diagnostic"),
            "path": issue.get("path"),
            "entry": issue.get("entry"),
            "field": issue.get("field"),
            "reason": reason,
            "requires": "dependency_audit" if issue.get("source_class") == "dependency" else "review",
        })

    def get_bytes(path_text: str) -> bytes:
        if path_text not in original:
            path = safe_path(root, path_text)
            if not path.is_file():
                raise SC2Error("warning_source_missing", "警告指向的本地 XML 不存在", path=path_text)
            original[path_text] = path.read_bytes()
            working[path_text] = original[path_text]
        return working[path_text]

    def add_candidate(issue: dict, repair_id: str, before: bytes, after: bytes, *, kind: str,
                      inferred: bool, requires: str) -> None:
        if selected is not None and repair_id not in selected:
            return
        path = issue["path"]
        working[path] = after
        candidates.append({
            "repair_id": repair_id,
            "kind": kind,
            "path": path,
            "entry": issue.get("entry"),
            "field": issue.get("field") or issue.get("local_evidence", {}).get("field"),
            "inferred": inferred,
            "requires": requires,
            "log_line": issue.get("log_line"),
            "bytes_before": len(before),
            "bytes_after": len(after),
        })

    processed: set[str] = set()
    for issue in audit["issues"]:
        diagnostic = issue.get("diagnostic")
        path = issue.get("path")
        if issue.get("source_class") != "local_map" or not path or not path.lower().endswith(".xml"):
            add_blocked(issue, "来源不是可安全修改的本地 XML")
            continue
        evidence = issue.get("local_evidence") or {}
        local_object = issue.get("local_object") or {}
        tag = local_object.get("tag")
        entry = issue.get("entry")
        if not tag or not entry:
            add_blocked(issue, "缺少唯一的本地对象上下文")
            continue

        if diagnostic == "invalid_field_name" and evidence.get("probable_alias") and evidence.get("field"):
            field = evidence["field"]
            alias = evidence["probable_alias"]
            repair_id = _repair_id("rename_field", issue, alias)
            if repair_id in processed:
                continue
            processed.add(repair_id)
            try:
                before = get_bytes(path)
                start, end = _object_span(before, tag, entry)
                after = _replace_scoped(before, start, end,
                                        (b"<" + field.encode("ascii") + rb"\b"),
                                        b"<" + alias.encode("ascii"))
                add_candidate(issue, repair_id, before, after, kind="field_alias", inferred=False,
                              requires="editor_validation")
            except SC2Error as exc:
                add_blocked(issue, str(exc), repair_id=repair_id)
            continue

        if diagnostic == "invalid_actor_model_field" and evidence.get("field"):
            field = evidence["field"]
            repair_id = _repair_id("remove_actor_model_field", issue)
            if repair_id in processed:
                continue
            processed.add(repair_id)
            if not include_inferred:
                add_blocked(issue, "删除 CActorModel 字段属于推断修复；调用时必须显式 include_inferred=true", repair_id=repair_id)
                continue
            try:
                before = get_bytes(path)
                start, end = _object_span(before, tag, entry)
                after = _remove_scoped_line(before, start, end, field)
                add_candidate(issue, repair_id, before, after, kind="remove_invalid_actor_model_field", inferred=True,
                              requires="editor_validation")
            except SC2Error as exc:
                add_blocked(issue, str(exc), repair_id=repair_id)
            continue

        if diagnostic == "array_index" and (issue.get("field") or "").startswith("WireframeShield.Image"):
            repair_id = _repair_id("index_wireframe_shield", issue)
            if repair_id in processed:
                continue
            processed.add(repair_id)
            if not include_inferred:
                add_blocked(issue, "补数组索引属于依赖敏感的推断修复；调用时必须显式 include_inferred=true", repair_id=repair_id)
                continue
            try:
                before = get_bytes(path)
                start, end = _object_span(before, tag, entry)
                scope = before[start:end]
                blocks = list(re.finditer(rb"<WireframeShield\b[^>]*>(.*?)</WireframeShield>", scope, re.DOTALL))
                if len(blocks) != 1:
                    raise SC2Error("ambiguous_warning_field", "WireframeShield 区块不是唯一区块", count=len(blocks))
                block = blocks[0]
                body = block.group(1)
                images = list(re.finditer(rb"<Image\b[^>]*>", body))
                if not images or any(re.search(rb"\bindex\s*=", image.group(0)) for image in images):
                    raise SC2Error("unsupported_warning_shape", "WireframeShield.Image 已有索引或结构未知")
                rebuilt = body
                for image in reversed(images):
                    old = image.group(0)
                    new = old.replace(b"<Image", b'<Image index="' + str(images.index(image)).encode("ascii") + b'"', 1)
                    rebuilt = rebuilt[:image.start()] + new + rebuilt[image.end():]
                new_scope = scope[:block.start(1)] + rebuilt + scope[block.end(1):]
                after = before[:start] + new_scope + before[end:]
                add_candidate(issue, repair_id, before, after, kind="add_array_indexes", inferred=True,
                              requires="dependency_and_editor_validation")
            except SC2Error as exc:
                add_blocked(issue, str(exc), repair_id=repair_id)
            continue

        add_blocked(issue, "该警告没有已证实的局部修复规则")

    changes = {path: data for path, data in working.items() if data != original.get(path)}
    report_changes = []
    for path, data in changes.items():
        report_changes.append({
            "path": path,
            "baseline_sha256": digest(original[path]),
            "candidate_sha256": digest(data),
            "bytes_before": len(original[path]),
            "bytes_after": len(data),
        })
    report = {
        "schema": "data-warning-repair-plan/1",
        "audit_verdict": audit["verdict"],
        "selected_repair_ids": sorted(selected) if selected is not None else None,
        "include_inferred": include_inferred,
        "candidates": candidates,
        "changes": report_changes,
        "blocked_count": len(blocked),
        "limitations": [
            "候选仍需编辑器加载/重存和运行时验证；规划成功不等于引擎接受",
            "依赖项合并、重复 ID、空 Actor 事件和 Doodad 警告不会自动修改",
        ],
    }
    return {"changes": changes, "report": report, "blocked": blocked}


def inspect_data_warnings(root: Path, *, log_text: str | None = None, log_path: Path | None = None) -> dict:
    """Parse a warning log and bind issues to local component XML evidence."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise SC2Error("project_missing", "地图组件目录不存在", path=str(root))
    if (log_text is None) == (log_path is None):
        raise SC2Error("invalid_warning_input", "必须且只能提供 log_text 或 log_path")
    if log_path is not None:
        log_path = Path(log_path).resolve()
        if not log_path.is_file():
            raise SC2Error("warning_log_missing", "警告日志不存在", path=str(log_path))
        try:
            raw_log = log_path.read_bytes()
            log_text = raw_log.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SC2Error("warning_log_encoding", "警告日志不是可读取的 UTF-8 文本", path=str(log_path)) from exc
    if not isinstance(log_text, str) or len(log_text) > 4_000_000:
        raise SC2Error("warning_log_too_large", "警告日志为空或超过 4 MB")

    inventory: dict[tuple[str, str], list[dict]] = defaultdict(list)
    parse_errors: list[dict] = []
    for path in _find_xml_files(root):
        entries, _, error = _object_entries(path)
        if error:
            parse_errors.append({"path": path.relative_to(root).as_posix(), "error": error})
            continue
        for item in entries:
            item["path"] = path.relative_to(root).as_posix()
            inventory[(item["tag"], item["id"])].append(item)

    issues = _parse_log(root, log_text)
    enriched: list[dict] = []
    for issue in issues:
        context = _object_context(inventory, issue.get("entry"))
        evidence = _field_evidence(context, issue.get("field"), issue["message"])
        if issue["kind"] == "actor_user_warning":
            evidence["actor_event"] = _actor_event_evidence(context)
        if issue["kind"] == "doodad_user_warning":
            evidence["objects"] = _objects_evidence(root, issue.get("object_id"), issue.get("entry"))
        kind, disposition, action = _classify_xml(issue, context, evidence)
        if issue["kind"] == "doodad_user_warning":
            kind, disposition, action = "doodad_runtime_warning", "requires_runtime_check", "核对 Objects 实例、依赖 Actor 和运行时创建/销毁；不要仅凭数量删除装饰物"
        elif issue["kind"] == "actor_user_warning":
            kind, disposition, action = "empty_actor_event", "requires_dependency_audit", "检查本地 On 条目、父 Actor 合并和事件索引；确认继承后再决定删除或补 Send"
        item = dict(issue)
        item.update({"diagnostic": kind, "disposition": disposition, "recommended_action": action, "local_evidence": evidence})
        if context:
            item["local_object"] = {key: value for key, value in context.items() if key != "element"}
        enriched.append(item)

    duplicate_groups: list[dict] = []
    for (tag, object_id), values in sorted(inventory.items()):
        if len(values) < 2:
            continue
        duplicate_groups.append({
            "tag": tag,
            "object_id": object_id,
            "count": len(values),
            "occurrences": [{"path": item["path"], "line": item["line"], "attributes": item["element"].attrib} for item in values],
            "disposition": "requires_reference_audit",
            "recommended_action": "建立入向引用闭包后合并或改用新的稳定 ID；禁止直接删除一组定义",
        })

    # Add duplicate evidence to the matching log warnings without guessing
    # which definition the engine retained.
    duplicate_by_id = {(item["tag"], item["object_id"]): item for item in duplicate_groups}
    for item in enriched:
        if item.get("entry") and any(item["entry"] == group["object_id"] for group in duplicate_groups):
            item.setdefault("local_evidence", {})["duplicate_definitions"] = [
                group for group in duplicate_groups if group["object_id"] == item["entry"]
            ]

    counts = Counter(item["diagnostic"] for item in enriched)
    disposition_counts = Counter(item["disposition"] for item in enriched)
    if parse_errors:
        verdict = "partial"
    elif not enriched:
        verdict = "no_matching_warnings"
    elif disposition_counts.get("safe_to_patch") and len(disposition_counts) == 1:
        verdict = "candidate_repairs_available"
    else:
        verdict = "requires_review"
    source_counts = Counter(item["source_class"] for item in enriched)
    return {
        "schema": "data-warnings-audit/1",
        "verdict": verdict,
        "evidence": {"static": "parsed_and_bound", "editor": "not_run", "runtime": "not_run", "visual": "not_reviewed"},
        "engine_parity": False,
        "root": str(root),
        "input": {"log_path": str(log_path) if log_path else None, "log_sha256": digest(log_text.encode("utf-8")), "log_lines": len(log_text.splitlines())},
        "summary": {"warning_count": len(enriched), "diagnostics": dict(counts), "dispositions": dict(disposition_counts), "sources": dict(source_counts), "parse_error_count": len(parse_errors)},
        "issues": enriched,
        "duplicate_definitions": duplicate_groups,
        "xml_parse_errors": parse_errors,
        "limitations": [
            "依赖项未物化或引擎未运行时，不能证明 Catalog 最终合并结果",
            "日志没有对象行号的 USER 警告只能绑定到对象或 Actor 名称，不能替代编辑器载入验证",
            "本工具只生成证据和候选方向，不修改地图、不自动删除字段或升级定义",
        ],
    }

