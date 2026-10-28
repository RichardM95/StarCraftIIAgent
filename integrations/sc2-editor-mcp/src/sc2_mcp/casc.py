"""Local CASC selection and a pinned, self-contained .NET extraction backend."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from .errors import SC2Error

_TOOLS = Path(__file__).resolve().parents[2] / "tools" / "casc"


def _sha256_file(path: Path, cancel=None, stage: Path | None = None) -> str:
    with path.open("rb") as stream:
        if cancel is None:
            return hashlib.file_digest(stream, "sha256").hexdigest()
        digest = hashlib.sha256()
        while True:
            _check_cancel(cancel, stage)
            block = stream.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def _check_cancel(cancel, stage: Path | None = None) -> None:
    if cancel is not None and cancel.is_set():
        details = {"diagnostics": str(stage)} if stage is not None else {}
        raise SC2Error("cancelled", "CASC 提取已取消，未发布输出。", **details)


def _progress(cancel, value: int, message: str) -> None:
    reporter = getattr(cancel, "report_progress", None)
    if callable(reporter):
        reporter(value, message)


def _save_helper_logs(stage: Path, stdout, stderr) -> None:
    for name, output in (("stdout", stdout), ("stderr", stderr)):
        # TimeoutExpired can contain bytes even when Popen uses text=True.
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        (stage / f"helper.{name}.log").write_text(output or "", encoding="utf-8")


def _run_cancellable(argv: list[str], stage: Path, timeout: int, cancel) -> subprocess.CompletedProcess:
    """Drain pipes while polling cancellation; stop only this exact helper."""
    _check_cancel(cancel, stage)
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(argv, cwd=stage, shell=False, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    stdout, stderr = "", ""
    try:
        while True:
            _check_cancel(cancel, stage)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
            try:
                stdout, stderr = process.communicate(timeout=min(0.25, remaining))
                break
            except subprocess.TimeoutExpired as exc:
                if exc.stdout is not None:
                    stdout = exc.stdout
                if exc.stderr is not None:
                    stderr = exc.stderr
        _check_cancel(cancel, stage)
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    except BaseException:
        # Popen retains the handle of the process we started. Never enumerate or
        # terminate unrelated dotnet processes or any game/editor process.
        if process.poll() is None:
            process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as exc:
            if exc.stdout is not None:
                stdout = exc.stdout
            if exc.stderr is not None:
                stderr = exc.stderr
            if process.poll() is None:
                process.kill()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as final:
                if final.stdout is not None:
                    stdout = final.stdout
                if final.stderr is not None:
                    stderr = final.stderr
        raise
    finally:
        _save_helper_logs(stage, stdout, stderr)


def _read_build_rows(path: Path) -> list[dict[str, str]]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip() and not line.startswith("#")]
    except (OSError, UnicodeError) as exc:
        raise SC2Error("BUILD_INFO_UNREADABLE", "无法读取安装目录中的 .build.info。", path=str(path)) from exc
    if not lines:
        raise SC2Error("INVALID_BUILD_INFO", ".build.info 为空。")
    columns = [column.split("!", 1)[0].replace(" ", "") for column in lines[0].split("|")]
    if len(set(columns)) != len(columns) or not {"BuildKey", "Active", "Version"}.issubset(columns):
        raise SC2Error("INVALID_BUILD_INFO", ".build.info 缺少必要字段或字段重复。")
    rows = []
    for number, line in enumerate(lines[1:], start=2):
        fields = line.split("|")
        if len(fields) != len(columns):
            raise SC2Error("INVALID_BUILD_INFO", ".build.info 字段数量不一致。", line=number)
        row = dict(zip(columns, fields))
        for field in ("BuildKey", "CDNKey"):
            if not re.fullmatch(r"[0-9a-fA-F]{32}", row.get(field, "")):
                raise SC2Error("INVALID_BUILD_INFO", "构建配置键不是 32 位十六进制。", field=field, line=number)
        rows.append(row)
    return rows


def inspect_installation(installation: Path) -> dict[str, Any]:
    root = Path(installation).resolve()
    rows = _read_build_rows(root / ".build.info")
    builds, warnings = [], []
    for row in rows:
        branch = row.get("Branch", "").lower()
        declared = row.get("Product", "")
        product = declared or ("s2_cn" if branch == "cn" else "s2" if branch in {"us", "eu", "kr", "tw", "sea"} else None)
        key = row["BuildKey"].lower()
        config = root / "SC2Data" / "config" / key[:2] / key[2:4] / key
        uid = None
        if config.is_file():
            for line in config.read_text(encoding="utf-8-sig").splitlines():
                if re.match(r"^build-uid\s*=", line):
                    uid = line.split("=", 1)[1].strip()
        builds.append({"branch": branch, "product": product, "product_source": "declared" if declared else "branch_mapping",
                       "active": row["Active"] == "1", "version": row["Version"], "build_key": key,
                       "cdn_key": row["CDNKey"].lower(), "build_uid": uid, "config_exists": config.is_file(),
                       "build_config": str(config)})
    if sum(build["active"] for build in builds) > 1:
        warnings.append("多个构建处于 Active 状态；必须按产品或分支明确选择，不能以最高 Base 目录代替。")
    return {"installation": str(root), "build_info_sha256": hashlib.sha256((root / ".build.info").read_bytes()).hexdigest(),
            "builds": builds, "casc_present": (root / "SC2Data" / "data").is_dir(), "warnings": warnings,
            "backend": {"helper": str(_TOOLS / "bin" / "Release" / "net6.0" / "Sc2Casc.dll"),
                        "compiled": (_TOOLS / "bin" / "Release" / "net6.0" / "Sc2Casc.dll").is_file(), "local_only": True}}


def select_build(inspection: dict, product: str | None = None, branch: str | None = None) -> dict:
    if product is not None and product not in {"s2", "s2_cn"}:
        raise SC2Error("INVALID_PRODUCT", "支持的游戏启动产品为 s2 或 s2_cn。")
    builds = [build for build in inspection["builds"] if build["active"] and
              (product is None or build["product"] == product) and (branch is None or build["branch"] == branch.lower())]
    if len(builds) != 1:
        raise SC2Error("BUILD_SELECTION", "没有唯一匹配的活动构建，请指定实际产品或分支。", matches=builds, product=product, branch=branch)
    if not builds[0]["config_exists"]:
        raise SC2Error("BUILD_CONFIG_MISSING", "活动构建缺少本地配置。", build=builds[0])
    if builds[0]["product"] not in {"s2", "s2_cn"}:
        raise SC2Error("BUILD_PRODUCT_UNKNOWN", "无法根据实际分支或 Product 字段确定 SC2 启动产品。", build=builds[0])
    return builds[0]


def _asset_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise SC2Error("INVALID_ASSET_PATH", "资源路径不能为空或含 NUL。")
    name = raw.replace("\\", "/")
    path = PurePosixPath(name)
    if name.startswith("/") or any(part in {"", ".", ".."} for part in name.split("/")):
        raise SC2Error("INVALID_ASSET_PATH", "资源路径必须是不含跳转的相对路径。", path=raw)
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " ")) or stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise SC2Error("INVALID_ASSET_PATH", "资源路径包含 Windows 非法或保留名称。", path=raw)
    return path.as_posix()


def _verify_vendor() -> dict:
    manifest = _TOOLS / "vendor" / "provenance.json"
    if not manifest.is_file():
        raise SC2Error("CASC_BACKEND_MISSING", "缺少独立 CASC 后端及来源记录。")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for item in data["files"]:
        path = _TOOLS / "vendor" / item["name"]
        if not path.is_file() or _sha256_file(path) != item["sha256"]:
            raise SC2Error("CASC_VENDOR_HASH", "CASC 后端依赖的 SHA-256 不匹配。", path=str(path))
        runtime_copy = _TOOLS / "bin" / "Release" / "net6.0" / item["name"]
        if runtime_copy.is_file() and _sha256_file(runtime_copy) != item["sha256"]:
            raise SC2Error("CASC_VENDOR_HASH", "CASC 后端运行目录依赖不匹配，请重新编译。", path=str(runtime_copy))
    return data


def extract_casc(installation: Path, paths: list[str], destination: Path, product: str | None = None,
                 branch: str | None = None, timeout: int = 180, cancel=None) -> dict:
    """Extract exact official virtual names to a NEW destination. No install writes."""
    _check_cancel(cancel)
    if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
        raise SC2Error("INVALID_TIMEOUT", "超时范围为 1 至 3600 秒。")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 5000:
        raise SC2Error("INVALID_PATHS", "单次提取需要 1 至 5000 个具体资源路径。")
    names = [_asset_path(name) for name in paths]
    if len({name.casefold() for name in names}) != len(names):
        raise SC2Error("ASSET_COLLISION", "资源路径存在大小写冲突或重复。")
    root, output = Path(installation).resolve(), Path(destination).resolve()
    if output.exists() or output.is_relative_to(root):
        raise SC2Error("INVALID_DESTINATION", "提取目标必须是安装目录之外的全新目录。", path=str(output))
    info = inspect_installation(root)
    build = select_build(info, product, branch)
    _verify_vendor()
    helper = _TOOLS / "bin" / "Release" / "net6.0" / "Sc2Casc.dll"
    dotnet = shutil.which("dotnet")
    if not dotnet or not helper.is_file():
        raise SC2Error("CASC_BACKEND_MISSING", "需要 .NET 6 和已经编译的独立后端。", build_command="dotnet build tools/casc/Sc2Casc.csproj -c Release")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".sc2-casc-", dir=output.parent))
    request = {"installation": str(root), "destination": str(stage / "files"), "build_key": build["build_key"],
               "product": build["product"], "paths": names, "build_info_sha256": info["build_info_sha256"]}
    request_path = stage / "request.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    try:
        argv = [dotnet, str(helper), str(request_path)]
        _progress(cancel, 5, "已选定本地构建，准备提取资源")
        _check_cancel(cancel, stage)
        if cancel is None:
            completed = subprocess.run(argv, cwd=stage, shell=False,
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            _progress(cancel, 10, "正在读取本地 CASC 数据")
            completed = _run_cancellable(argv, stage, timeout, cancel)
        _save_helper_logs(stage, completed.stdout, completed.stderr)
        _check_cancel(cancel, stage)
        result_path = stage / "result.json"
        if completed.returncode not in {0, 2} or not result_path.is_file():
            raise SC2Error("CASC_EXTRACTION_FAILED", "本地 CASC 提取失败；保留独立诊断目录。", diagnostics=str(stage), exit_code=completed.returncode)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("missing"):
            raise SC2Error("CASC_ASSET_MISSING", "部分资源不存在或本地数据不完整。", missing=result["missing"], diagnostics=str(stage))
        if completed.returncode:
            raise SC2Error("CASC_EXTRACTION_FAILED", "后端未成功完成提取。", diagnostics=str(stage), exit_code=completed.returncode)
        records = result.get("files", [])
        if {item.get("path") for item in records} != set(names):
            raise SC2Error("CASC_OUTPUT_INVALID", "提取结果与请求不一致。", diagnostics=str(stage))
        reported_progress = 80
        _progress(cancel, reported_progress, "正在验证提取文件的长度与 SHA-256")
        for index, record in enumerate(records):
            _check_cancel(cancel, stage)
            file = stage / "files" / record["path"]
            if not file.is_file() or file.stat().st_size != record["bytes"] or _sha256_file(file, cancel, stage) != record["sha256"]:
                raise SC2Error("CASC_OUTPUT_INVALID", "提取文件哈希验证失败。", path=record["path"], diagnostics=str(stage))
            progress = 80 + (15 * (index + 1) // len(records))
            if progress != reported_progress:
                _progress(cancel, progress, "正在验证提取文件的长度与 SHA-256")
                reported_progress = progress
        if hashlib.sha256((root / ".build.info").read_bytes()).hexdigest() != info["build_info_sha256"]:
            raise SC2Error("CASC_BUILD_CHANGED", "提取期间游戏构建已变化，未发布结果。", diagnostics=str(stage))
        # On Windows os.rename never overwrites an existing destination directory.
        if output.exists():
            raise SC2Error("DESTINATION_CONFLICT", "提取期间目标已被其他程序建立。", diagnostics=str(stage))
        _progress(cancel, 99, "验证已完成，准备发布提取结果")
        _check_cancel(cancel, stage)
        (stage / "files").rename(output)
        return {"destination": str(output), "build": build, "files": records, "diagnostics": str(stage),
                "local_only": True, "source_installation_modified": False, "verified": "sha256"}
    except subprocess.TimeoutExpired as exc:
        raise SC2Error("CASC_TIMEOUT", "本地提取超过时限，未发布结果。", diagnostics=str(stage)) from exc
