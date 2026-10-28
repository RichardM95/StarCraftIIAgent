from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import SC2Error
from .storage import digest, file_lock, guard_absolute_path, map_files, safe_path, snapshot, write_json

KEYSTONE = Path(r"<KEYSTONE_MAP_ROOT>\build\kscg2.SC2Map")


class Projects:
    def __init__(self, state: Path):
        self.state = guard_absolute_path(Path(state)).resolve()
        self.registry = self.state / "projects.json"

    def _load(self):
        guard_absolute_path(self.registry)
        if not self.registry.exists():
            return {}
        try:
            records = json.loads(self.registry.read_text("utf-8"))
            if not isinstance(records, dict):
                raise ValueError("registry must be an object")
            for key, record in records.items():
                if (not isinstance(record, dict) or record.get("project_id") != key
                        or not isinstance(record.get("root"), str) or not Path(record["root"]).is_absolute()
                        or not isinstance(record.get("writable"), bool)
                        or record.get("profile") not in {"generic", "keystone"}
                        or not isinstance(record.get("search_roots"), list)):
                    raise ValueError("invalid project record")
            return records
        except (OSError, ValueError, TypeError) as exc:
            raise SC2Error("invalid_registry", "项目注册表损坏，停止自动修改", error=str(exc)) from exc

    def open(self, path: str, writable=False, profile="auto", search_roots=None):
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise SC2Error("invalid_project_path", "地图路径必须为非空字符串")
        if not isinstance(writable, bool):
            raise SC2Error("invalid_writable", "writable 必须为布尔值")
        if search_roots is not None and (not isinstance(search_roots, list) or
                any(not isinstance(p, (str, Path)) or not str(p).strip() for p in search_roots)):
            raise SC2Error("invalid_search_roots", "依赖搜索目录必须为路径列表")
        source = guard_absolute_path(Path(path)).resolve()
        if not source.exists():
            raise SC2Error("project_missing", "地图或模组不存在", path=str(source))
        if profile not in ("auto", "generic", "keystone"):
            raise SC2Error("invalid_profile", "项目适配类型无效")
        with file_lock(self.state / "registry.lock"):
            records = self._load()
            key = digest(str(source).casefold().encode())[:20]
            if source.is_file():
                if source.suffix.casefold() not in {".sc2map", ".sc2mod"}:
                    raise SC2Error("unsupported_project_type", "归档工程必须为 SC2Map 或 SC2Mod")
                from .archives import extract_archive
                # Original archives stay readonly; content-addressed extraction prevents stale reuse.
                archive_hash = digest(source.read_bytes())
                working_name = "mod.SC2Mod" if source.suffix.casefold() == ".sc2mod" else "map.SC2Map"
                root = self.state / "projects" / (key + "_" + archive_hash[:16]) / working_name
                if not root.exists():
                    extract_archive(source, root)
                if digest(source.read_bytes()) != archive_hash:
                    raise SC2Error("archive_changed", "读取期间源归档发生变化，请重试", path=str(source))
            else:
                root = source
            info = safe_path(root, "DocumentInfo")
            if not info.is_file():
                raise SC2Error("not_component_project", "缺少 DocumentInfo，不能识别为组件地图/模组")
            try:
                components = {"DocumentInfo": "DocInfo", "ComponentList.SC2Components": "Components"}
                for filename, expected_tag in components.items():
                    component = safe_path(root, filename)
                    if not component.exists():
                        continue
                    data = component.read_bytes()
                    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                        raise SC2Error("unsupported_xml", "地图外壳不接受 DTD 或实体声明", component=filename)
                    if ET.fromstring(data).tag != expected_tag:
                        raise SC2Error("not_component_project", "地图组件根元素不正确", component=filename)
            except ET.ParseError as exc:
                raise SC2Error("invalid_xml", str(exc)) from exc
            script = safe_path(root, "MapScript.galaxy")
            is_keystone = root == KEYSTONE.resolve() or (script.exists() and b"lib1_gv_mAX_CARD_ID" in script.read_bytes())
            effective_profile = "keystone" if is_keystone else ("generic" if profile == "auto" else profile)
            record = {"project_id": key, "source": str(source), "root": str(root),
                      "writable": writable, "profile": effective_profile,
                      "kind": "mod" if source.suffix.casefold() == ".sc2mod" else "map",
                      "archive_source": source.is_file(),
                      "search_roots": [str(guard_absolute_path(Path(p)).resolve()) for p in (search_roots or [])]}
            shell = ["DocumentInfo", "DocumentHeader", "ComponentList.SC2Components"]
            if record["kind"] == "map":
                shell.append("MapInfo")
            missing = [name for name in shell if not safe_path(root, name).is_file()]
            record["metadata"] = {"present": [name for name in shell if name not in missing], "missing": missing}
            record["warnings"] = ([{"code": "missing_shell_metadata", "files": missing}] if missing else [])
            absent_search = [p for p in record["search_roots"] if not Path(p).is_dir()]
            if absent_search:
                record["warnings"].append({"code": "missing_search_roots", "paths": absent_search})
            records[key] = record
            write_json(self.registry, records)
        return record

    def get(self, project_id: str, write=False):
        if not isinstance(project_id, str) or not project_id or not isinstance(write, bool):
            raise SC2Error("invalid_project_id", "项目 ID 或访问参数无效")
        record = self._load().get(project_id)
        if record is None:
            raise SC2Error("project_not_open", "先调用 sc2_project_open 打开项目")
        if not guard_absolute_path(Path(record["root"])).is_dir():
            raise SC2Error("project_missing", "工作目录已移动或不存在")
        if write and not record["writable"]:
            raise SC2Error("readonly_project", "项目以只读方式打开；写入需明确 writable=true")
        return record

    def list(self):
        return list(self._load().values())

    def clone(self, project_id, destination: str):
        record = self.get(project_id)
        if not isinstance(destination, (str, Path)) or not str(destination).strip():
            raise SC2Error("invalid_destination", "副本目标必须为非空路径")
        source, target = Path(record["root"]), guard_absolute_path(Path(destination)).resolve()
        if target.exists() or target.is_relative_to(source) or source.is_relative_to(target):
            raise SC2Error("invalid_destination", "副本需使用不存在且不嵌套于源图的目录")
        baseline = snapshot(source)
        target.mkdir(parents=True, exist_ok=False)
        try:
            for rel, path in map_files(source):
                out = target / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, out)
            if snapshot(source) != baseline or snapshot(target) != baseline:
                raise SC2Error("copy_verification_failed", "副本指纹与源图不一致；可能源图正在修改")
        except BaseException:
            # Keep partial output as evidence; never delete user data on failure.
            raise
        return self.open(str(target), writable=True, profile=record["profile"], search_roots=record["search_roots"])
