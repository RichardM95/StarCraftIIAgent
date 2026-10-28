"""File based request bridge for a restricted SC2 worker.

The DeepSeek worker does not receive arbitrary shell or desktop access.  It
writes one JSON request in ``.sc2-mcp/request.json``; the supervisor invokes
this module outside the worker session and publishes a JSON response.  All
operations are read-only or produce an isolated candidate folder.  Applying a
candidate remains a supervisor/MCP transaction operation.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import catalog, data_warnings, dependencies, map_shell, script
from .errors import SC2Error
from .storage import digest, safe_path, snapshot
from .validation import inspect_project, validate_changes

PROTOCOL = "sc2-worker-bridge/1"
REQUEST_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
OPERATIONS = {
    "capabilities",
    "workspace_inspect",
    "map_shell_audit",
    "dependencies_inspect",
    "catalog_inspect",
    "catalog_search",
    "script_inspect",
    "trigger_inspect",
    "data_warnings_audit",
    "data_warnings_plan",
    "static_validate",
    "cliff_capability_status",
}
_DENIED_OPERATION_WORDS = {"cliff_write", "ramp_write", "apply", "commit", "rollback", "export"}


def _string(value: Any, name: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SC2Error("bridge_invalid_request", f"{name} 必须是有限的非空字符串", field=name)
    return value


def _root(value: str | Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise SC2Error("bridge_root_missing", "工作区组件文件夹不存在", root=str(root))
    return root


def _request_id(value: Any) -> str:
    value = _string(value, "id", maximum=80)
    if not REQUEST_NAME_RE.fullmatch(value):
        raise SC2Error("bridge_invalid_request_id", "请求 ID 只允许 ASCII 字母、数字、下划线和横线")
    return value


def _arguments(request: dict[str, Any]) -> dict[str, Any]:
    value = request.get("arguments", {})
    if not isinstance(value, dict):
        raise SC2Error("bridge_invalid_arguments", "arguments 必须是 JSON 对象")
    return value


def _relative_file(root: Path, value: Any) -> str:
    relative = _string(value, "path", maximum=1000).replace("\\", "/")
    if relative.startswith("/") or ":" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise SC2Error("bridge_unsafe_path", "桥接路径必须是工作区内相对路径", path=relative)
    path = safe_path(root, relative)
    if not path.is_file():
        raise SC2Error("bridge_file_missing", "请求的工作区文件不存在", path=relative)
    return relative


def _log_input(root: Path, arguments: dict[str, Any]) -> tuple[str | None, Path | None]:
    log_text = arguments.get("log_text")
    log_path = arguments.get("log_path")
    if log_text is not None and log_path is not None:
        raise SC2Error("bridge_ambiguous_log", "log_text 与 log_path 只能提供一个")
    if log_text is not None:
        if not isinstance(log_text, str) or not log_text or len(log_text) > 4_000_000:
            raise SC2Error("bridge_log_too_large", "日志必须是 4 MB 以内的非空文本")
        return log_text, None
    if log_path is None:
        raise SC2Error("bridge_log_missing", "此操作需要 log_text 或工作区内 log_path")
    relative = _relative_file(root, log_path)
    return None, safe_path(root, relative)


def _hash_changes(root: Path, changes: dict[str, bytes | None]) -> list[dict[str, Any]]:
    result = []
    for relative, data in sorted(changes.items()):
        before = safe_path(root, relative)
        result.append({
            "path": relative,
            "before_sha256": digest(before.read_bytes()) if before.is_file() else None,
            "after_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "bytes_before": before.stat().st_size if before.is_file() else None,
            "bytes_after": len(data) if data is not None else None,
        })
    return result


def _internal_path(root: Path, relative: str) -> Path:
    """Resolve bridge-owned hidden state without weakening map safe_path."""
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise SC2Error("bridge_unsafe_path", "桥接内部路径越出工作区", path=relative)
    current = root / relative
    while current != root:
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise SC2Error("bridge_linked_path", "桥接目录不能通过链接访问", path=relative)
        current = current.parent
    return root / relative


def _materialize_candidate(root: Path, request_id: str, changes: dict[str, bytes | None]) -> dict[str, Any]:
    destination = _internal_path(root, f".sc2-mcp/candidates/{request_id}")
    if destination.exists():
        raise SC2Error("bridge_candidate_exists", "相同请求 ID 的候选已存在，拒绝覆盖")
    destination.mkdir(parents=True, exist_ok=False)
    files = []
    try:
        for relative, data in changes.items():
            if data is None:
                continue
            target = _internal_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files.append(relative)
        manifest = {
            "protocol": PROTOCOL,
            "request_id": request_id,
            "source_root": str(root),
            "candidate_root": str(destination),
            "files": files,
            "source_snapshot": snapshot(root),
        }
        (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except BaseException:
        # Keep the partial candidate as evidence; never delete user data.
        raise
    return {
        "candidate_root": str(destination),
        "candidate_relative": f".sc2-mcp/candidates/{request_id}",
        "files": files,
    }


def _validate_request(request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(request, dict):
        raise SC2Error("bridge_invalid_request", "请求必须是 JSON 对象")
    if request.get("protocol") != PROTOCOL:
        raise SC2Error("bridge_protocol_mismatch", "桥接协议版本不匹配", expected=PROTOCOL)
    request_id = _request_id(request.get("id"))
    operation = _string(request.get("operation"), "operation", maximum=80)
    if operation not in OPERATIONS:
        raise SC2Error("bridge_operation_blocked", "请求操作不在桥接白名单中", operation=operation, allowed=sorted(OPERATIONS))
    if any(word in operation.casefold() for word in _DENIED_OPERATION_WORDS):
        raise SC2Error("bridge_operation_blocked", "悬崖写入、提交和回滚操作不通过 DeepSeek 桥接")
    return request_id, _arguments(request)


def execute_request(root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    """Execute one validated bridge request without changing the source root."""
    root = _root(root)
    request_id, arguments = _validate_request(request)
    operation = request["operation"]

    if operation == "capabilities":
        return {
            "protocol": PROTOCOL,
            "operations": sorted(OPERATIONS),
            "write_behavior": "data_warnings_plan creates only .sc2-mcp/candidates/<id>; source apply is blocked",
            "cliff": {
                "native_cliff_topology_generation": "blocked",
                "native_ramp_generation": "blocked",
                "cliff_editor_acceptance": "blocked",
            },
        }
    if operation == "cliff_capability_status":
        return {
            "native_cliff_topology_generation": "blocked",
            "native_ramp_generation": "blocked",
            "cliff_editor_acceptance": "blocked",
            "reason": "原生悬崖拓扑证据不足，DeepSeek 桥接不生成写入候选",
        }
    if operation == "workspace_inspect":
        profile = arguments.get("profile", "generic")
        if profile not in {"generic", "keystone"}:
            raise SC2Error("bridge_invalid_profile", "profile 必须是 generic 或 keystone")
        return inspect_project(root, profile=profile)
    if operation == "map_shell_audit":
        return map_shell.inspect_map_shell(root)
    if operation == "dependencies_inspect":
        return dependencies.resolve_dependencies(root, [root])
    if operation == "catalog_inspect":
        return catalog.inspect_catalog([root], _string(arguments.get("catalog"), "catalog", maximum=80),
                                       _string(arguments.get("object_id"), "object_id", maximum=300))
    if operation == "catalog_search":
        catalog_name = _string(arguments.get("catalog"), "catalog", maximum=80)
        query = arguments.get("query", "")
        if not isinstance(query, str) or len(query) > 300:
            raise SC2Error("bridge_invalid_query", "query 过长或不是字符串")
        limit = arguments.get("limit", 50)
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise SC2Error("bridge_invalid_limit", "limit 必须在 1 到 200 之间")
        return {"catalog": catalog_name, "query": query, "items": catalog.search_catalog([root], catalog_name, query, limit)}
    if operation == "script_inspect":
        symbol = arguments.get("symbol", "")
        if not isinstance(symbol, str) or len(symbol) > 300:
            raise SC2Error("bridge_invalid_symbol", "symbol 过长或不是字符串")
        return script.inspect_script(root, symbol)
    if operation == "trigger_inspect":
        return script.inspect_triggers(root)
    if operation == "data_warnings_audit":
        log_text, log_path = _log_input(root, arguments)
        return data_warnings.inspect_data_warnings(root, log_text=log_text, log_path=log_path)
    if operation == "data_warnings_plan":
        log_text, log_path = _log_input(root, arguments)
        planned = data_warnings.plan_warning_repairs(
            root,
            log_text=log_text,
            log_path=log_path,
            repair_ids=arguments.get("repair_ids"),
            include_inferred=bool(arguments.get("include_inferred", False)),
        )
        changes = planned["changes"]
        validation = validate_changes(root, changes, profile="generic", domain="data_warning_repairs")
        materialized = _materialize_candidate(root, request_id, changes) if changes else None
        return {
            "report": planned["report"],
            "blocked": planned["blocked"],
            "changes": _hash_changes(root, changes),
            "validation": validation,
            "materialized_candidate": materialized,
            "source_modified": False,
        }
    if operation == "static_validate":
        values = arguments.get("paths")
        if not isinstance(values, list) or not values or len(values) > 64:
            raise SC2Error("bridge_invalid_paths", "paths 必须是 1 到 64 个工作区相对路径")
        changes = {_relative_file(root, item): safe_path(root, _relative_file(root, item)).read_bytes() for item in values}
        profile = arguments.get("profile", "generic")
        if profile not in {"generic", "keystone"}:
            raise SC2Error("bridge_invalid_profile", "profile 必须是 generic 或 keystone")
        return validate_changes(root, changes, profile=profile, domain="worker_bridge")
    raise SC2Error("bridge_operation_unreachable", "未处理的桥接操作", operation=operation)


def execute_envelope(root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id") if isinstance(request, dict) else None
    try:
        return {"protocol": PROTOCOL, "id": request_id, "ok": True, "result": execute_request(root, request)}
    except SC2Error as exc:
        return {"protocol": PROTOCOL, "id": request_id, "ok": False, "error": exc.as_dict()}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return {"protocol": PROTOCOL, "id": request_id, "ok": False,
                "error": {"code": "bridge_execution_error", "message": str(exc)}}


__all__ = ["PROTOCOL", "OPERATIONS", "execute_envelope", "execute_request"]
