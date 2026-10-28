"""Ordered lexical Galaxy guard; deliberately not a semantic/AST compiler.

Exact edits prove which bytes changed. Ordered controls, declarations, calls and
returns additionally catch full-body deletion/reordering hidden by replacement.
Native compilation and non-author semantic review remain separate requirements.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .errors import SC2Error
from . import script


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf") or b"\x00" in data:
        raise SC2Error("script_guard_encoding", "Galaxy 不允许 BOM/NUL")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SC2Error("script_guard_encoding", "Galaxy 必须为严格 UTF-8", offset=exc.start) from exc


def _subsequence(before: list, after: list) -> bool:
    cursor = iter(after)
    return all(any(candidate == value for candidate in cursor) for value in before)


def _structure(text: str) -> dict:
    masked, diagnostics = script._strip_comments_strings(text)
    diagnostics += script._balance_diagnostics(text, masked)
    if diagnostics:
        raise SC2Error("script_guard_syntax", "Galaxy 词法结构无效", diagnostics=diagnostics)
    info = script._inspect_text(text)
    functions = []
    for match in script._FUNCTION_RE.finditer(masked):
        depth = 1
        index = match.end()
        while depth:
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
            index += 1
        body = masked[match.end():index - 1]
        signature = re.sub(r"\s+", " ", masked[match.start():match.end() - 1]).strip()
        ordered = []
        token_re = re.compile(r"\b(?:if|else|for|while|do|switch|case|default|break|continue|return)\b|"
                              r"\b(?:const\s+)?[A-Za-z_]\w*\s+[A-Za-z_]\w*\s*(?=[=;\[])|"
                              r"\b[A-Za-z_]\w*\s*(?=\()")
        for token in token_re.finditer(body):
            value = re.sub(r"\s+", " ", token.group()).strip()
            if value == "return":
                end = body.find(";", token.end())
                # Return payload is significant: returning a different state is a
                # semantic edit and must be independently inspected, not hidden.
                value = "return " + re.sub(r"\s+", "", body[token.end():end])
            ordered.append(value)
        functions.append({"name": match["name"], "signature": signature, "ordered": ordered})
    literals = []
    for match in re.finditer(r'\b(TriggerCreate|TriggerExecute|Wait|TriggerAddEvent\w*|TriggerAddCondition|TriggerAddAction)\s*\(', masked):
        end = text.find(";", match.end())
        literals.append(re.sub(r"\s+", "", text[match.start():end + 1]))
    return {"functions": functions, "prototypes": [item["name"] for item in info["prototypes"]],
            "declarations": [(item["type"], item["name"]) for item in info["declarations"]],
            "init_calls": [(item["caller"], item["callee"]) for item in info["init_calls"]], "phase_calls": literals}


def _tokens(text: str) -> list[str]:
    """Keep strings and every semantic token, dropping only comments/spacing."""
    pattern = re.compile(r'//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[A-Za-z_]\w*|(?:\d+(?:\.\d*)?)|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\S')
    return [match.group() for match in pattern.finditer(text) if not match.group().startswith(('//','/*'))]


def _structure_fingerprint(value: dict) -> str:
    """Hash the ordered lexical structure, separate from raw source bytes."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def guard(before: bytes, after: bytes, reviewed_edits: list[dict] | None = None) -> dict:
    original = _structure(_decode(before))
    candidate = _structure(_decode(after))
    violations = []
    before_names = [item["name"] for item in original["functions"]]
    after_names = [item["name"] for item in candidate["functions"]]
    if not _subsequence(before_names, after_names):
        violations.append({"code": "function_removed_or_reordered", "before": before_names, "after": after_names})
    after_functions = {item["name"]: item for item in candidate["functions"]}
    if len(after_functions) != len(after_names):
        violations.append({"code": "duplicate_function"})
    for function in original["functions"]:
        other = after_functions.get(function["name"])
        if other is None:
            continue
        if function["signature"] != other["signature"]:
            violations.append({"code": "function_signature_changed", "function": function["name"]})
        if not _subsequence(function["ordered"], other["ordered"]):
            violations.append({"code": "ordered_logic_removed_or_reordered", "function": function["name"],
                               "before": function["ordered"], "after": other["ordered"]})
    for field in ("prototypes", "declarations", "init_calls", "phase_calls"):
        if not _subsequence(original[field], candidate[field]):
            violations.append({"code": field + "_removed_or_reordered"})
    expected = _decode(before)
    for edit in reviewed_edits or []:
        old, new = edit.get('old'), edit.get('new')
        if not isinstance(old,str) or not old or not isinstance(new,str) or expected.count(old) != 1:
            raise SC2Error('script_guard_review_context','审查的精确上下文必须唯一')
        if not edit.get('reviewer') or not edit.get('author') or edit['reviewer'] == edit['author'] or not edit.get('evidence'):
            raise SC2Error('script_guard_review_binding','精确语义变更必须绑定非作者审查与证据')
        # Review exemptions can change a leaf expression, never a whole
        # declaration/statement/function or its scope. This prevents an empty
        # body from becoming accepted merely by listing it as an exact edit.
        forbidden = {'{','}',';','=','+=','-=','++','--','if','else','while','for','return','break','continue'}
        if forbidden.intersection(_tokens(old)) or forbidden.intersection(_tokens(new)):
            raise SC2Error('script_guard_review_scope','审查例外仅支持叶子表达式，禁止覆盖语句/作用域')
        expected = expected.replace(old,new,1)
    if _tokens(expected) != _tokens(_decode(after)):
        violations.append({'code':'unreviewed_semantic_token_change',
                           'note':'所有既有语句、赋值、初始化载荷、作用域和字符串均受保护；仅精确审查叶子表达式可变。'})
    return {"schema": "galaxy-ordered-guard-1", "parser": "lexical_not_ast", "passed": not violations,
            "before_sha256": hashlib.sha256(before).hexdigest(), "after_sha256": hashlib.sha256(after).hexdigest(),
            "before_structure_sha256": _structure_fingerprint(original),
            "after_structure_sha256": _structure_fingerprint(candidate),
            "violations": violations, "semantic_equivalence": "requires_non_author_review",
            "native_compile": "not_run", "runtime": "not_run"}


def plan_guarded_replace(root: Path, old: str, new: str, expected_sha256: str, review: dict | None = None) -> dict[str, bytes | None]:
    changes = script.plan_script_replace(root, old, new, expected_sha256)
    for relative, candidate in changes.items():
        reviewed = [{**review,'old':old,'new':new}] if review is not None else None
        result = guard((Path(root) / relative).read_bytes(), candidate, reviewed)
        if not result["passed"]:
            raise SC2Error("script_guard_rejected", "修改删除或重排既有 Galaxy 结构", report=result)
    return changes
