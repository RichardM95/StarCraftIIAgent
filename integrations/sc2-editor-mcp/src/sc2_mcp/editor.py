"""Windows SC2 launch/diagnostics. No input injection or editor-ready claims."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

import psutil

from .errors import SC2Error

_OWNED: dict[int, float] = {}
_NAMES = {"sc2editor_x64.exe", "sc2editor.exe", "sc2_x64.exe", "sc2.exe", "sc2switcher_x64.exe"}


def _windows() -> None:
    if os.name != "nt":
        raise SC2Error("WINDOWS_REQUIRED", "编辑器启动和窗口诊断需要 Windows。")


def _version(path: Path) -> str | None:
    if os.name != "nt" or not path.is_file():
        return None
    from ctypes import wintypes as w
    class Info(ctypes.Structure):
        _fields_ = [(name, w.DWORD) for name in ("signature", "struct", "fileMS", "fileLS", "productMS", "productLS", "mask", "flags", "os", "type", "subtype", "dateMS", "dateLS")]
    lib = ctypes.WinDLL("version", use_last_error=True)
    lib.GetFileVersionInfoSizeW.argtypes = [w.LPCWSTR, ctypes.POINTER(w.DWORD)]
    lib.GetFileVersionInfoW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p]
    lib.VerQueryValueW.argtypes = [ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.UINT)]
    size = lib.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    value, length = ctypes.c_void_p(), w.UINT()
    if not lib.GetFileVersionInfoW(str(path), 0, size, buf) or not lib.VerQueryValueW(buf, "\\", ctypes.byref(value), ctypes.byref(length)):
        return None
    data = ctypes.cast(value, ctypes.POINTER(Info)).contents
    return ".".join(str(x) for x in (data.fileMS >> 16, data.fileMS & 65535, data.fileLS >> 16, data.fileLS & 65535))


def documents_root() -> Path:
    """Use Windows' actual Documents known folder (may be redirected)."""
    if os.name == "nt":
        buf = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
            return Path(buf.value) / "StarCraft II"
    return Path.home() / "Documents" / "StarCraft II"


def _redacted_args(args: list[str]) -> list[str]:
    result, redact_next = [], False
    for arg in args:
        sensitive = re.search(r"(?:token|password|ticket|authcode|sessionkey)", arg, re.I)
        if redact_next:
            result.append("<redacted>")
            redact_next = False
        elif sensitive and arg.startswith("-"):
            if "=" in arg:
                result.append(arg.split("=", 1)[0] + "=<redacted>")
            else:
                result.append(arg)
                redact_next = True
        else:
            result.append(arg)
    return result


def _owned_process(pid: int) -> bool:
    try:
        return pid in _OWNED and abs(psutil.Process(pid).create_time() - _OWNED[pid]) < 0.01
    except (psutil.Error, OSError):
        return False


def processes(installation: Path | None = None) -> list[dict[str, Any]]:
    root = Path(installation).resolve() if installation else None
    result = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time", "status"]):
        try:
            info = proc.info
            if (info["name"] or "").lower() not in _NAMES:
                continue
            exe = Path(info["exe"]).resolve() if info["exe"] else None
            if root and (not exe or not exe.is_relative_to(root)):
                continue
            # Refresh owned children while their parent is still present.
            if _owned_process(proc.pid):
                for child in proc.children(recursive=True):
                    if child.name().lower() in _NAMES:
                        _OWNED[child.pid] = child.create_time()
            result.append({"pid": proc.pid, "name": info["name"], "executable": str(exe) if exe else None,
                           "arguments": _redacted_args(info["cmdline"] or []), "created": info["create_time"],
                           "status": info["status"], "owned": _owned_process(proc.pid)})
        except (psutil.Error, OSError):
            continue
    return result


def log_files(limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise SC2Error("INVALID_LIMIT", "日志数量必须为 1 至 100。")
    files = []
    for category in ("EditorLogs", "GameLogs"):
        directory = documents_root() / category
        if directory.is_dir():
            for p in directory.glob("*.txt"):
                try:
                    stat = p.stat()
                    files.append({"path": str(p), "category": category, "bytes": stat.st_size, "modified": stat.st_mtime})
                except OSError:
                    continue
    return sorted(files, key=lambda f: f["modified"], reverse=True)[:limit]


def read_log(path: Path, max_bytes: int = 32768) -> dict:
    p = Path(path).resolve()
    roots = [(documents_root() / category).resolve() for category in ("EditorLogs", "GameLogs")]
    if not any(p.is_relative_to(root) for root in roots) or p.suffix.lower() != ".txt" or not p.is_file():
        raise SC2Error("INVALID_LOG", "仅允许读取编辑器或游戏日志目录中的文本日志。")
    if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 262144:
        raise SC2Error("INVALID_LIMIT", "日志读取上限必须为 1 至 262144 字节。")
    with p.open("rb") as stream:
        stream.seek(max(0, p.stat().st_size - max_bytes))
        raw = stream.read(max_bytes)
    text = raw.decode("utf-8-sig", errors="replace")
    text = re.sub(r"(?i)((?:token|password|ticket|authcode|sessionkey)\s*[=:]\s*)([^\s\"]+)", r"\1<redacted>", text)
    return {"path": str(p), "tail": text, "truncated": p.stat().st_size > max_bytes,
            "evidence": "log_only", "editor_ready": None, "runtime_passed": None}


def inspect_editor(installation: Path) -> dict:
    from .casc import inspect_installation
    root = Path(installation).resolve()
    state = inspect_installation(root)
    editor = root / "Support64" / "SC2Editor_x64.exe"
    switcher = root / "Support64" / "SC2Switcher_x64.exe"
    running = processes(root)
    windows = []
    for proc in running:
        try:
            windows.extend(inspect_windows(proc["pid"]))
        except SC2Error as exc:
            if exc.code != "PROCESS_UNAVAILABLE":
                raise
    state.update({"editor": {"path": str(editor), "exists": editor.is_file(), "version": _version(editor)},
                  "switcher": {"path": str(switcher), "exists": switcher.is_file(), "version": _version(switcher)},
                  "processes": running, "windows": windows,
                  "logs": log_files(), "documents": str(documents_root()),
                  "editor_ready": None, "unsaved_documents": "unknown", "input_automation": False})
    return state


def _region_product(branch: str | None) -> str | None:
    if not branch:
        return None
    branch = branch.casefold()
    if branch == "cn":
        return "s2_cn"
    if branch in {"us", "eu", "kr", "tw", "sea"}:
        return "s2"
    return None


def _registry_editor_commands() -> dict:
    """Read the two known Windows map-open registrations without changing them."""
    if os.name != "nt":
        return {"available": False, "reason": "WINDOWS_REQUIRED", "entries": []}
    import winreg

    entries = []
    for class_name in ("SC2.Map", "Blizzard.SC2Map"):
        key_path = class_name + r"\shell\open\command"
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
                command, value_type = winreg.QueryValueEx(key, None)
            executable_match = re.match(r'^\s*"([^"]+)"|^\s*([^\s]+)', command)
            executable = (executable_match.group(1) or executable_match.group(2)) if executable_match else None
            entries.append({"class": class_name, "key": key_path, "command": command,
                            "executable": executable, "value_type": value_type, "status": "present"})
        except FileNotFoundError:
            entries.append({"class": class_name, "key": key_path, "command": None,
                            "executable": None, "status": "missing"})
        except OSError as exc:
            entries.append({"class": class_name, "key": key_path, "command": None,
                            "executable": None, "status": "unreadable", "error": str(exc)})
    return {"available": True, "entries": entries}


def _map_region_snapshot(map_path: Path | None, locale: str) -> dict:
    if map_path is None:
        return {"provided": False, "locale": locale, "locale_component": None}
    path = _map_path(map_path, allow_mod=True)
    result = {"provided": True, "path": str(path), "exists": path.exists(), "locale": locale,
              "component_map": path.is_dir(), "document_info": None, "locale_components": [],
              "locale_component": None}
    if not path.is_dir():
        result["format"] = "archive_or_file"
        return result
    result["format"] = "component"
    result["document_info"] = str(path / "DocumentInfo") if (path / "DocumentInfo").is_file() else None
    result["locale_components"] = sorted(p.name for p in path.glob("*.SC2Data") if p.is_dir())
    component = path / f"{locale}.SC2Data"
    result["locale_component"] = {"path": str(component), "exists": component.is_dir()}
    return result


def _region_log_evidence(limit: int = 5) -> list[dict]:
    evidence = []
    marker = re.compile(r"(?i)(?:s2_cn|s2c|\bcn\b|\bkr\b|region|locale|product|build|failed|error|unable|missing|unsupported)")
    for entry in log_files(max(1, min(limit, 20))):
        if entry["category"] != "EditorLogs":
            continue
        try:
            data = read_log(Path(entry["path"]), 65536)
        except SC2Error as exc:
            evidence.append({"path": entry["path"], "status": "unreadable", "error": exc.as_dict()})
            continue
        lines = [line for line in data["tail"].splitlines() if marker.search(line)]
        evidence.append({"path": entry["path"], "modified": entry["modified"], "status": "read",
                         "matched_lines": lines[-20:], "truncated": data["truncated"], "evidence": "log_text"})
    return evidence


def diagnose_editor_region(installation: Path, product: str | None = None, branch: str | None = None,
                           locale: str = "zhCN", map_path: Path | None = None) -> dict:
    """Diagnose CN/international editor mismatches without starting or changing SC2."""
    if product is not None and product not in {"s2", "s2_cn"}:
        raise SC2Error("INVALID_PRODUCT", "支持的游戏启动产品为 s2 或 s2_cn。")
    if branch is not None and (not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", branch)):
        raise SC2Error("INVALID_BRANCH", "分支必须是字母、数字、下划线或短横线。")
    if not isinstance(locale, str) or not re.fullmatch(r"[A-Za-z]{2}[A-Za-z]{2}", locale):
        raise SC2Error("INVALID_LOCALE", "语言需要四字母地区代码。")

    root = Path(installation).resolve()
    checks = []
    recommendations = []

    def check(code: str, status: str, severity: str, message: str, **evidence):
        item = {"code": code, "status": status, "severity": severity, "message": message,
                "evidence": evidence, "confidence": "high" if status in {"pass", "fail"} else "medium"}
        checks.append(item)
        return item

    try:
        from .casc import inspect_installation, select_build
        installation_info = inspect_installation(root)
    except SC2Error as exc:
        check("INSTALLATION_UNREADABLE", "fail", "error", "无法读取客户端构建信息，无法判断国服/亚服构建。", error=exc.as_dict())
        return {"schema": "editor-region-diagnostics/1", "installation": str(root),
                "requested": {"product": product, "branch": branch, "locale": locale},
                "installation_state": None, "selected_build": None, "editor": {}, "registry": _registry_editor_commands(),
                "map": _map_region_snapshot(map_path, locale) if map_path else {"provided": False},
                "checks": checks, "recommendations": ["确认 installation 指向包含 .build.info 的完整 StarCraft II 安装目录。"],
                "log_evidence": _region_log_evidence(), "verdict": "blocked",
                "editor_ready": None, "launch_performed": False}

    selected = None
    selection_error = None
    try:
        selected = select_build(installation_info, product=product, branch=branch)
        check("BUILD_SELECTION", "pass", "info", "已按请求唯一选定活动构建。", product=selected.get("product"), branch=selected.get("branch"), version=selected.get("version"), build_uid=selected.get("build_uid"))
    except SC2Error as exc:
        selection_error = exc.as_dict()
        check("BUILD_SELECTION", "fail", "error", "无法唯一选定与请求匹配的活动构建，不能安全生成编辑器启动结论。", error=selection_error)
        recommendations.append("显式指定与安装实际分支匹配的 product/branch；国服通常为 s2_cn/cn，韩服及国际服通常为 s2/kr 或对应国际分支。")

    active = [item for item in installation_info.get("builds", []) if item.get("active")]
    if len(active) > 1:
        check("MULTIPLE_ACTIVE_BUILDS", "warning", "warning", "安装内存在多个 Active 构建；未指定产品时不能按最高版本猜测。", active_builds=active)
        recommendations.append("保留构建选择为明确的 product/branch，不要让工具或注册表按最高 Base 目录猜地区。")
    else:
        check("MULTIPLE_ACTIVE_BUILDS", "pass", "info", "安装内没有多个活动构建歧义。", active_count=len(active))

    editor_path = root / "Support64" / "SC2Editor_x64.exe"
    switcher_path = root / "Support64" / "SC2Switcher_x64.exe"
    editor_info = {"path": str(editor_path), "exists": editor_path.is_file(), "version": _version(editor_path),
                   "switcher": {"path": str(switcher_path), "exists": switcher_path.is_file(), "version": _version(switcher_path)}}
    check("EDITOR_EXECUTABLE", "pass" if editor_path.is_file() else "fail", "info" if editor_path.is_file() else "error",
          "找到与诊断安装目录相同的官方编辑器程序。" if editor_path.is_file() else "诊断安装目录缺少官方编辑器程序。", path=str(editor_path))
    if not editor_path.is_file():
        recommendations.append("确认使用完整的 64 位 StarCraft II 安装目录，而不是仅有数据文件的副本。")

    expected_product = _region_product((selected or {}).get("branch") if selected else branch)
    if expected_product and product and expected_product != product:
        check("REGION_PRODUCT_MISMATCH", "fail", "error", "请求的产品与分支对应关系冲突。", branch=branch, expected_product=expected_product, requested_product=product)
        recommendations.append("把 product 与 branch 成对设置；不要用 s2_cn 启动 KR/国际构建，也不要用 s2 启动 CN 构建。")
    elif selected and expected_product and selected.get("product") != expected_product:
        check("BUILD_PRODUCT_MISMATCH", "warning", "warning", "安装构建的 Product 与分支推断结果不一致，请以 build-uid 和日志复核。", branch=selected.get("branch"), product=selected.get("product"), expected_product=expected_product)
        recommendations.append("检查 .build.info 的 Product、Branch 与对应 SC2Data/config build-uid，避免混用同目录多地区数据。")
    else:
        check("REGION_PRODUCT_MISMATCH", "pass", "info", "请求产品与分支没有发现明显冲突。", branch=(selected or {}).get("branch") or branch, product=(selected or {}).get("product") or product)

    if selected and selected.get("branch") == "cn" and selected.get("build_uid") not in {None, "s2c"}:
        check("CN_BUILD_UID", "fail", "error", "CN 分支的构建 UID 不是已知的 s2c，可能是地区数据混用。", build_uid=selected.get("build_uid"), build_config=selected.get("build_config"))
        recommendations.append("重新选择或修复 CN B98370 等完整构建，使 .build.info、build 配置和启动 UID 一致。")
    elif selected:
        check("BUILD_UID", "pass", "info", "构建 UID 与当前分支没有发现明确冲突。", branch=selected.get("branch"), build_uid=selected.get("build_uid"))

    registry = _registry_editor_commands()
    if registry.get("available"):
        for entry in registry["entries"]:
            executable = entry.get("executable")
            if entry.get("status") == "missing":
                check("REGISTRY_OPEN_COMMAND_MISSING", "warning", "warning", "地图打开注册项不存在，双击地图可能无法调用编辑器。", class_name=entry["class"], key=entry["key"])
                recommendations.append("优先使用 MCP 的显式 SC2Editor_x64.exe 启动计划，或修复对应 SC2.Map 注册项；不要执行未知来源的注册表脚本。")
            elif executable:
                try:
                    same = Path(executable).resolve() == editor_path.resolve()
                except OSError:
                    same = False
                check("REGISTRY_OPEN_COMMAND_PATH", "pass" if same else "warning", "info" if same else "warning",
                      "注册表打开命令指向当前诊断安装。" if same else "注册表打开命令指向其他安装或无法解析的路径。",
                      class_name=entry["class"], registered_executable=executable, selected_editor=str(editor_path))
                if not same:
                    recommendations.append("检查 SC2.Map/Blizzard.SC2Map 打开命令是否仍指向旧国服或旧亚服 Support64 目录。")
    else:
        check("REGISTRY_OPEN_COMMAND", "unknown", "info", "当前环境不是 Windows，未读取地图打开注册项。", reason=registry.get("reason"))

    map_info = _map_region_snapshot(map_path, locale) if map_path else {"provided": False}
    if map_info.get("provided") and map_info.get("component_map"):
        locale_component = map_info.get("locale_component") or {}
        check("MAP_LOCALE_COMPONENT", "pass" if locale_component.get("exists") else "warning", "info" if locale_component.get("exists") else "warning",
              "地图包含请求语言组件。" if locale_component.get("exists") else "地图缺少请求语言组件，编辑器可能回退或出现文本/依赖显示异常。",
              locale=locale, component=locale_component, available=map_info.get("locale_components", []))
        if not locale_component.get("exists"):
            recommendations.append("确认地图使用的语言组件与编辑器产品匹配；不要把 zhCN.SC2Data 当作 CN 客户端构建本身。")

    logs = _region_log_evidence()
    if any(item.get("matched_lines") for item in logs):
        check("EDITOR_LOG_EVIDENCE", "warning", "warning", "最近编辑器日志包含地区、构建或启动错误关键词，需要结合原文复核。", files=len(logs))
        recommendations.append("优先读取最近 EditorLogs 中匹配的行，核对实际 B 号、Product、Locale 和失败原因；日志证据不能单独证明地图已载入。")
    else:
        check("EDITOR_LOG_EVIDENCE", "unknown", "info", "没有发现可供本次地区诊断使用的日志关键词。", files=len(logs))

    failed = [item for item in checks if item["status"] == "fail"]
    warnings = [item for item in checks if item["status"] == "warning"]
    verdict = "blocked" if failed else "needs_review" if warnings else "no_static_region_conflict_found"
    return {"schema": "editor-region-diagnostics/1", "installation": str(root),
            "requested": {"product": product, "branch": branch, "locale": locale},
            "installation_state": installation_info, "selected_build": selected,
            "editor": editor_info, "registry": registry, "map": map_info, "checks": checks,
            "recommendations": list(dict.fromkeys(recommendations)), "log_evidence": logs,
            "verdict": verdict, "editor_ready": None, "launch_performed": False,
            "limitations": ["这是只读静态与日志诊断，不启动编辑器、不修改注册表、不证明地图已载入。",
                            "PE 文件版本与 SC2 数据构建号可能来自不同版本字段，不能仅凭两者不同判定地区冲突。"]}


def inspect_windows(pid: int) -> list[dict]:
    """Read visible top-level SC2 window metadata, including blocking dialogs."""
    _windows()
    try:
        if psutil.Process(pid).name().lower() not in _NAMES:
            raise SC2Error("INVALID_PROCESS", "窗口诊断仅支持 SC2 官方进程。")
    except psutil.Error as exc:
        raise SC2Error("PROCESS_UNAVAILABLE", "目标进程已退出或不可访问。", pid=pid) from exc
    from ctypes import wintypes as w
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.IsWindowVisible.argtypes = [w.HWND]
    user.IsWindowEnabled.argtypes = [w.HWND]
    user.IsIconic.argtypes = [w.HWND]
    user.IsHungAppWindow.argtypes = [w.HWND]
    user.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    user.GetWindowTextLengthW.argtypes = [w.HWND]
    user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    result = []
    @callback_type
    def enum(hwnd, _):
        found = w.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
        if found.value == pid and user.IsWindowVisible(hwnd):
            rect, class_name = w.RECT(), ctypes.create_unicode_buffer(256)
            title = ctypes.create_unicode_buffer(min(user.GetWindowTextLengthW(hwnd) + 1, 32768))
            user.GetWindowTextW(hwnd, title, len(title))
            user.GetClassNameW(hwnd, class_name, len(class_name))
            user.GetWindowRect(hwnd, ctypes.byref(rect))
            result.append({"handle": hwnd, "pid": pid, "title": title.value, "class": class_name.value,
                           "enabled": bool(user.IsWindowEnabled(hwnd)), "minimized": bool(user.IsIconic(hwnd)),
                           "hung": bool(user.IsHungAppWindow(hwnd)), "rect": [rect.left, rect.top, rect.right, rect.bottom],
                           "owned": _owned_process(pid)})
        return True
    user.EnumWindows(enum, 0)
    return result


def _map_path(map_path: Path, allow_mod: bool = False) -> Path:
    path = Path(map_path).resolve()
    suffixes = {".sc2map", ".sc2mod"} if allow_mod else {".sc2map"}
    if path.suffix.lower() not in suffixes or not path.exists():
        raise SC2Error("INVALID_MAP", "需要现有 SC2Map（编辑器另支持 SC2Mod）路径。", path=str(path))
    if path.is_dir() and not (path / "DocumentInfo").is_file():
        raise SC2Error("INVALID_MAP", "组件地图缺少 DocumentInfo。", path=str(path))
    return path


def build_launch_command(map_path: Path, installation: Path, mode: str = "editor", product: str = "s2_cn") -> dict:
    """Read-only launch plan; executable/argv are fixed, never arbitrary shell."""
    from .casc import inspect_installation, select_build
    if mode not in {"editor", "test"}:
        raise SC2Error("INVALID_MODE", "启动模式必须为 editor 或 test。")
    root = Path(installation).resolve()
    selected = select_build(inspect_installation(root), product=product)
    path = _map_path(map_path, allow_mod=mode == "editor")
    exe = root / "Support64" / ("SC2Editor_x64.exe" if mode == "editor" else "SC2Switcher_x64.exe")
    if not exe.is_file():
        raise SC2Error("EXECUTABLE_MISSING", "缺少指定安装内的官方启动程序。", path=str(exe))
    if mode == "editor":
        # Local HKCR\SC2.Map\shell\open\command uses -loadfile "%1" -product SC2.
        args = [str(exe), "-loadfile", str(path), "-product", "SC2", "-uid", product]
    else:
        # Actual 98370 editor-launched game logs show -run <map>, display/preload/reloadcheck.
        args = [str(exe), "-run", str(path), "-displaymode", "1", "-preload", "1", "-NoUserCheats", "-reloadcheck", "-uid", product]
    version = selected.get("version", "").split(".")[-1]
    client = root / "Versions" / f"Base{version}" / "SC2_x64.exe"
    if mode == "test" and (not version.isdigit() or not client.is_file()):
        raise SC2Error("CLIENT_BUILD_MISSING", "所选产品的数据版本没有对应客户端。", expected=str(client))
    return {"mode": mode, "argv": args, "cwd": str(root), "map": str(path), "build": selected,
            "selected_client": str(client), "syntax_evidence": "installed_registry" if mode == "editor" else "local_editor_test_log",
            "map_load_verified": False, "runtime_verified": False}


def _launch(plan: dict) -> dict:
    _windows()
    names = {"sc2editor_x64.exe", "sc2editor.exe"} if plan["mode"] == "editor" else {"sc2_x64.exe", "sc2.exe"}
    existing = [p for p in processes() if p["name"].lower() in names]
    if existing:
        raise SC2Error("APPLICATION_ALREADY_RUNNING", "已有同类程序运行，无法确认未保存文档或游戏状态；未发出启动请求。", processes=existing)
    try:
        child = subprocess.Popen(plan["argv"], cwd=plan["cwd"], shell=False, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            _OWNED[child.pid] = psutil.Process(child.pid).create_time()
        except psutil.Error:
            pass
    except OSError as exc:
        raise SC2Error("LAUNCH_FAILED", "官方程序启动失败。", error=str(exc)) from exc
    return {**plan, "pid": child.pid, "requested_at": time.time(), "status": "launch_requested",
            "editor_ready": None, "map_load_verified": False, "runtime_verified": False}


def open_editor(map_path: Path, installation: Path, product: str = "s2_cn") -> dict:
    return _launch(build_launch_command(map_path, installation, "editor", product))


def launch_test(map_path: Path, installation: Path, product: str = "s2_cn") -> dict:
    return _launch(build_launch_command(map_path, installation, "test", product))


def capture_window(pid: int, destination: Path, window_handle: int | None = None) -> dict:
    """PrintWindow screenshot of this service's own process; no focus/input."""
    _windows()
    if not _owned_process(pid):
        raise SC2Error("PROCESS_NOT_OWNED", "仅截取本服务启动且身份仍匹配的程序窗口。", pid=pid)
    output = Path(destination).resolve()
    if output.exists() or output.suffix.lower() != ".png":
        raise SC2Error("INVALID_DESTINATION", "截图目标必须是不存在的 PNG 文件。")
    from ctypes import wintypes as w
    from PIL import Image
    user, gdi = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.IsWindowVisible.argtypes = [w.HWND]
    user.IsIconic.argtypes = [w.HWND]
    user.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    user.GetWindowDC.argtypes = [w.HWND]; user.GetWindowDC.restype = w.HDC
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
    gdi.CreateCompatibleDC.argtypes = [w.HDC]; gdi.CreateCompatibleDC.restype = w.HDC
    gdi.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]; gdi.CreateCompatibleBitmap.restype = w.HBITMAP
    gdi.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]; gdi.SelectObject.restype = w.HGDIOBJ
    gdi.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
    gdi.DeleteObject.argtypes = [w.HGDIOBJ]; gdi.DeleteDC.argtypes = [w.HDC]
    windows = []
    @callback_type
    def enum(hwnd, _):
        found = w.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(found))
        if found.value == pid and user.IsWindowVisible(hwnd) and not user.IsIconic(hwnd):
            rect = w.RECT()
            if user.GetWindowRect(hwnd, ctypes.byref(rect)):
                windows.append((hwnd, rect.right - rect.left, rect.bottom - rect.top))
        return True
    user.EnumWindows(enum, 0)
    if not windows:
        raise SC2Error("WINDOW_UNAVAILABLE", "所属进程没有可截取的非最小化可见窗口。")
    if window_handle is not None:
        windows = [window for window in windows if window[0] == window_handle]
        if not windows:
            raise SC2Error("WINDOW_UNAVAILABLE", "指定窗口不属于该进程或当前不可见。")
    hwnd, width, height = max(windows, key=lambda item: item[1] * item[2])
    user.IsHungAppWindow.argtypes = [w.HWND]
    if user.IsHungAppWindow(hwnd):
        raise SC2Error("WINDOW_UNRESPONSIVE", "窗口未响应，未发送同步截图请求。")
    if not 0 < width * height <= 50_000_000:
        raise SC2Error("WINDOW_SIZE", "窗口尺寸无效或过大。")
    class Header(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG), ("planes", w.WORD), ("bits", w.WORD),
                    ("compression", w.DWORD), ("imageSize", w.DWORD), ("xppm", w.LONG), ("yppm", w.LONG), ("used", w.DWORD), ("important", w.DWORD)]
    dc = user.GetWindowDC(hwnd)
    memory, bitmap, old = None, None, None
    try:
        memory = gdi.CreateCompatibleDC(dc)
        bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
        if not dc or not memory or not bitmap:
            raise SC2Error("CAPTURE_FAILED", "无法建立窗口截图缓冲。")
        old = gdi.SelectObject(memory, bitmap)
        if not user.PrintWindow(hwnd, memory, 2):
            raise SC2Error("CAPTURE_FAILED", "PrintWindow 不支持此窗口；未使用输入或焦点操作。")
        gdi.SelectObject(memory, old); old = None
        header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        if gdi.GetDIBits(dc, bitmap, 0, height, buffer, ctypes.byref(header), 0) != height:
            raise SC2Error("CAPTURE_FAILED", "无法读取完整窗口像素。")
        picture = Image.frombuffer("RGB", (width, height), buffer.raw, "raw", "BGRX", 0, 1)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            picture.save(stream, format="PNG")
        return {"path": str(output), "pid": pid, "window_handle": hwnd, "width": width, "height": height, "evidence": "window_pixels",
                "visual_accepted": False, "warning": "DirectX 窗口可能返回空白或旧帧；截图本身不证明地图载入成功。"}
    finally:
        if old and memory: gdi.SelectObject(memory, old)
        if bitmap: gdi.DeleteObject(bitmap)
        if memory: gdi.DeleteDC(memory)
        if dc: user.ReleaseDC(hwnd, dc)


def capture_visible_window(pid: int, destination: Path, window_handle: int | None = None) -> dict:
    """Read screen pixels only when the owned target is already foreground."""
    _windows()
    if not _owned_process(pid):
        raise SC2Error("PROCESS_NOT_OWNED", "仅截取本服务启动且身份仍匹配的程序窗口。", pid=pid)
    output = Path(destination).resolve()
    if output.exists() or output.suffix.lower() != ".png":
        raise SC2Error("INVALID_DESTINATION", "截图目标必须是不存在的 PNG 文件。")
    from ctypes import wintypes as w
    from PIL import ImageGrab
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetForegroundWindow.restype = w.HWND
    user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    user.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    user.IsIconic.argtypes = [w.HWND]
    hwnd = user.GetForegroundWindow()
    actual_pid = w.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(actual_pid))
    if actual_pid.value != pid or (window_handle is not None and hwnd != window_handle):
        raise SC2Error("WINDOW_NOT_FOREGROUND", "目标窗口当前不是前台，未截图且未切换焦点。", pid=pid)
    if user.IsIconic(hwnd):
        raise SC2Error("WINDOW_UNAVAILABLE", "目标窗口已最小化，未还原窗口。")
    previous_context = None
    set_context = getattr(user, "SetThreadDpiAwarenessContext", None)
    if set_context:
        set_context.argtypes = [ctypes.c_void_p]
        set_context.restype = ctypes.c_void_p
        previous_context = set_context(ctypes.c_void_p(-4))
    try:
        rect = w.RECT()
        if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise SC2Error("WINDOW_UNAVAILABLE", "无法读取目标窗口矩形。")
        bounds = (rect.left, rect.top, rect.right, rect.bottom)
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if not 0 < width * height <= 50_000_000:
            raise SC2Error("WINDOW_SIZE", "窗口尺寸无效或过大。")
        picture = ImageGrab.grab(bbox=bounds, all_screens=True)
        if user.GetForegroundWindow() != hwnd or not _owned_process(pid):
            raise SC2Error("FOREGROUND_CHANGED", "截图期间前台或进程身份变化，已丢弃像素。")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            picture.save(stream, format="PNG")
        return {"path": str(output), "pid": pid, "window_handle": hwnd, "width": picture.width,
                "height": picture.height, "evidence": "screen_visible", "visual_accepted": False,
                "foreground_changed": False, "warning": "仅记录当前可见帧，未操作窗口；仍需实际检查图像。"}
    finally:
        if set_context and previous_context:
            set_context(previous_context)
