"""Evidence gate for native Galaxy editor round trips.

The MCP does not drive the editor or claim that a lexical round trip is a
compiler result.  This module only reads an independently produced copy and,
when supplied, a structured evidence record from a fixed editor build.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import script_build
from .errors import SC2Error


def _sha(path: Path) -> str:
    if not path.is_file():
        raise SC2Error("native_gate_file_missing", "原生门禁文件不存在", path=str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_native_gate(root: Path, manifest_path: str, native_root: Path,
                        installation: Path, expected_editor_sha256: str,
                        evidence_path: Path | None = None) -> dict:
    """Check a fixed-build native round-trip record without launching anything."""
    if not isinstance(expected_editor_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_editor_sha256):
        raise SC2Error("invalid_editor_fingerprint", "编辑器 SHA-256 必须是 64 位十六进制字符串")
    root = Path(root).resolve()
    native_root = Path(native_root).resolve()
    installation = Path(installation).resolve()
    editor_path = installation / "Support64" / "SC2Editor_x64.exe"
    editor_sha = _sha(editor_path) if editor_path.is_file() else None
    editor_status = "passed" if editor_sha and editor_sha.casefold() == expected_editor_sha256.casefold() else "blocked"
    editor_reason = "fixed_editor_sha256_matches" if editor_status == "passed" else "fixed_editor_sha256_missing_or_mismatch"

    roundtrip = script_build.compare_native_roundtrip(root, manifest_path, native_root)
    result = {
        "schema": "sc2-script-native-gate/1",
        "editor": {"status": editor_status, "reason": editor_reason,
                   "expected_sha256": expected_editor_sha256.lower(),
                   "observed_sha256": editor_sha},
        "source_agreement": roundtrip,
        "compile": {"status": "blocked", "reason": "没有独立编辑器编译证据"},
        "editor_load": {"status": "blocked", "reason": "没有独立编辑器载入证据"},
        "save": {"status": "blocked", "reason": "没有独立编辑器重存证据"},
        "runtime": {"status": "blocked", "reason": "没有游戏运行证据"},
        "visual": {"status": "blocked", "reason": "没有视觉验收证据"},
        "launch_performed": False,
        "limitations": [
            "词法往返一致不等于 Galaxy 编译成功。",
            "本门禁不控制鼠标键盘，也不启动编辑器或游戏。",
        ],
    }
    if evidence_path is None:
        return result
    evidence_path = Path(evidence_path).resolve()
    if not evidence_path.is_file():
        raise SC2Error("native_gate_evidence_missing", "独立原生门禁证据不存在", path=str(evidence_path))
    try:
        evidence = json.loads(evidence_path.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SC2Error("native_gate_evidence_invalid", "独立原生门禁证据不是有效 JSON", error=str(exc)) from exc
    if not isinstance(evidence, dict):
        raise SC2Error("native_gate_evidence_invalid", "独立原生门禁证据必须是对象")
    result["evidence_file_sha256"] = _sha(evidence_path)
    required = {"compile_exit_code", "editor_loaded", "saved"}
    missing = sorted(required - set(evidence))
    if missing:
        raise SC2Error("native_gate_evidence_incomplete", "独立证据缺少必要字段", missing=missing)
    result["compile"] = {"status": "passed" if evidence["compile_exit_code"] == 0 else "failed",
                          "exit_code": evidence["compile_exit_code"]}
    result["editor_load"] = {"status": "passed" if evidence["editor_loaded"] is True else "failed",
                              "observed": evidence["editor_loaded"]}
    result["save"] = {"status": "passed" if evidence["saved"] is True else "failed",
                       "observed": evidence["saved"]}
    for level in ("runtime", "visual"):
        if level in evidence:
            result[level] = {"status": evidence[level] if evidence[level] in {"passed", "failed", "blocked", "partial"} else "unknown"}
    result["launch_performed"] = True
    result["evidence"] = {key: evidence[key] for key in evidence if key not in {"stdout", "stderr", "logs"}}
    return result
