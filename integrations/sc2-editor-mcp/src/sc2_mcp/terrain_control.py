"""Experimental protected brush planning and paired native terrain sync.

Source component maps are immutable here. Planners return candidates; native
execution changes only freshly copied archives and newly created evidence.
The service supplies its existing Jobs and shared installation lock state.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from copy import deepcopy

import numpy as np
import psutil

from . import archives, editor, spatial
from .errors import SC2Error
from .spatial_batch import sample_height
from .storage import digest, file_lock, guard_absolute_path, safe_path, snapshot, write_json
from .terrain import Terrain

SUPPORT_VERSION = "skyshield-98370-xml115-experimental-1"
SUPPORTED_EDITOR_SHA256 = "ed6e2636af6dc4cd2dd67c1ed6f6f3d14188628749e1498693cb9f09098eee17"
NATIVE_COMPONENTS = frozenset({"t3Terrain.xml", "t3HeightMap", "t3SyncHeightMap", "t3VertCol", "Minimap.tga"})
_FORMAL = Path("<KEYSTONE_MAP_ROOT>/build")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SC2Error("invalid_terrain_control_number", "参数必须为有限数值", parameter=name)
    return float(value)


def _mask(value, shape):
    if value is None:
        return np.zeros(shape, dtype=bool)
    try:
        mask = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise SC2Error("invalid_protection_mask", "保护掩码必须是规则二维布尔数组") from exc
    if mask.shape != shape or mask.dtype.kind != "b":
        raise SC2Error("invalid_protection_mask", "保护掩码必须与顶点网格同形且只含布尔值", expected=list(shape), actual=list(mask.shape))
    return mask.copy()


def _mask_info(mask):
    return {"shape": list(mask.shape), "protected_vertices": int(np.count_nonzero(mask)),
            "sha256": digest(mask.astype("u1").tobytes())}


def plan_flatten_protected_report(root: Path, rect: list[int], *, protected_rects=None,
                                   protected_mask=None, brush_value: int | None = None) -> dict:
    """Flatten only HMAP brush channel 0; never invent synchronized heights.

    Cliff/ramp structural channels 1/2, topology, pathing and SMAP remain
    untouched. Explicit protected vertices retain their full original bytes.
    The candidate is intentionally awaiting native sync, not playable proof.
    """
    t = Terrain(root)
    x0, y0, x1, y1 = t.rect(rect, vertices=True)
    protected = _mask(protected_mask, (t.height, t.width))
    if protected_rects is not None and not isinstance(protected_rects, list):
        raise SC2Error("invalid_protected_rectangles", "保护选区必须是矩形列表")
    for protected_rect in protected_rects or []:
        ax, ay, bx, by = t.rect(protected_rect, vertices=True)
        protected[ay:by, ax:bx] = True
    selected = np.zeros(protected.shape, dtype=bool)
    selected[y0:y1, x0:x1] = True
    editable = selected & ~protected
    if not np.any(editable):
        raise SC2Error("empty_flatten_selection", "选区没有未受保护的顶点")
    if brush_value is None:
        values, counts = np.unique(t.vertices[:, :, 0][editable], return_counts=True)
        if np.count_nonzero(counts == counts.max()) != 1:
            raise SC2Error("ambiguous_flatten_plateau", "选区主笔刷高度并列，需明确 brush_value")
        brush_value = int(values[np.argmax(counts)])
    if isinstance(brush_value, bool) or not isinstance(brush_value, int) or not 0 <= brush_value <= 65535:
        raise SC2Error("invalid_brush_value", "brush_value 必须是0至65535的原生HMAP整数")
    before = t.vertices.copy()
    t.vertices[:, :, 0][editable] = brush_value
    candidate = t.raw["t3HeightMap"][:32] + t.vertices.tobytes()
    changed = int(np.count_nonzero(before[:, :, 0] != t.vertices[:, :, 0]))
    return {"changes": {"t3HeightMap": candidate} if changed else {}, "status": "awaiting_native_sync" if changed else "unchanged",
            "support": SUPPORT_VERSION, "brush_value": brush_value, "changed_brush_vertices": changed,
            "rect": list(rect), "protection": _mask_info(protected), "source_fingerprint": digest(t.raw["t3HeightMap"]),
            "preserved": ["HMAP channels 1/2", "SMAP", "cliff topology", "rampList", "pathing", "Objects", "scripts", "banks", "identity"],
            "evidence": {"static": "checked_supported_bytes", "native": "required", "runtime": "not_observed", "visual": "not_observed"},
            "playable_delivery": False}


def plan_flatten_protected(root: Path, rect: list[int], *, protected_rects=None,
                            protected_mask=None, brush_value: int | None = None) -> dict[str, bytes | None]:
    return plan_flatten_protected_report(root, rect, protected_rects=protected_rects,
                                        protected_mask=protected_mask, brush_value=brush_value)["changes"]


def plan_ground_offsets_report(root: Path, placements: list[dict], *, terrain_overrides=None) -> dict:
    """Set selected absolute Z to synchronized ground + explicit world offset.

    Offsets must already account for the actual model origin/scale. No default
    zero offset is inferred, and a brush-only candidate is never a new ground.
    """
    if not isinstance(placements, list) or not 1 <= len(placements) <= 10000:
        raise SC2Error("invalid_ground_placements", "贴地对象数量必须为1至10000")
    overrides = terrain_overrides or {}
    if "t3HeightMap" in overrides and "t3SyncHeightMap" not in overrides:
        raise SC2Error("stale_ground_height", "HMAP候选尚未原生同步，不能用旧SMAP冒充新地面")
    t = Terrain(root, overrides)
    original = safe_path(root, "Objects").read_bytes()
    raw, report, seen = original, [], set()
    for specification in placements:
        if not isinstance(specification, dict) or "world_z_offset" not in specification:
            raise SC2Error("ground_offset_required", "每个贴地对象必须显式提供已核对的world_z_offset")
        ident = spatial._id(specification.get("object_id"))
        if ident in seen:
            raise SC2Error("duplicate_ground_object", "同一对象不能重复贴地", object_id=ident)
        seen.add(ident)
        document = spatial._parse(raw, "Objects")
        node = spatial._unique(document.children, ident)
        if node.tag not in {"ObjectDoodad", "ObjectUnit"}:
            raise SC2Error("unsupported_ground_object", "仅对已有单位或装饰物规划贴地", object_id=ident)
        if node.tag == "ObjectDoodad":
            flags = [n for n in node.children if n.tag == "Flag" and n.attrs.get("Index") == "HeightAbsolute"]
            if len(flags) != 1 or flags[0].attrs.get("Value") != "1":
                raise SC2Error("unknown_ground_coordinate_mode", "装饰物必须已有唯一HeightAbsolute=1，不能猜相对坐标语义", object_id=ident)
        position = node.attrs.get("Position", "").split(",")
        if len(position) != 3:
            raise SC2Error("invalid_ground_position", "物件Position不是三元坐标", object_id=ident)
        try:
            x, y, z = map(float, position)
        except ValueError as exc:
            raise SC2Error("invalid_ground_position", "物件Position不是有限数值", object_id=ident) from exc
        if not all(math.isfinite(v) for v in [x, y, z]):
            raise SC2Error("invalid_ground_position", "物件Position不是有限数值", object_id=ident)
        offset = _finite(specification["world_z_offset"], "world_z_offset")
        ground = sample_height(t.heights, x, y)
        target = ground + offset
        raw = spatial._patch_attributes(raw, node, {"Position": f"{position[0]},{position[1]},{target:.6f}"})
        report.append({"object_id": ident, "ground": ground, "world_z_offset": offset, "before_z": z,
                       "candidate_z": target, "offset_evidence": specification.get("offset_evidence"),
                       "offset_evidence_status": "caller_supplied", "visual": "not_observed"})
    return {"changes": {"Objects": raw} if raw != original else {}, "placements": report,
            "sampling": "bilinear_synchronized_SMAP", "support": SUPPORT_VERSION,
            "smap_sha256": digest(t.raw["t3SyncHeightMap"]),
            "evidence": {"static": "checked_position_edits", "runtime": "not_observed", "visual": "not_observed"}}


def plan_ground_offsets(root: Path, placements: list[dict], *, terrain_overrides=None) -> dict[str, bytes | None]:
    return plan_ground_offsets_report(root, placements, terrain_overrides=terrain_overrides)["changes"]


def _dilate(mask, radius):
    result = np.zeros_like(mask)
    h, w = mask.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            sy0, sy1 = max(0, -dy), min(h, h - dy)
            sx0, sx1 = max(0, -dx), min(w, w - dx)
            result[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] |= mask[sy0:sy1, sx0:sx1]
    return result


def _xml_semantic(node):
    if node is None:
        return None
    return [node.tag, sorted(node.attrib.items()), (node.text or "").strip(), [_xml_semantic(c) for c in node]]


def _xml_without_quantization(tree):
    tree = deepcopy(tree)
    for vert in tree.findall("heightMap/vertData"):
        vert.attrib.pop("quantizeBias", None)
        vert.attrib.pop("quantizeScale", None)
    return _xml_semantic(tree)


def plan_native_sync_result_report(root: Path, control_before: Path, control_after: Path,
                                   candidate_before: Path, candidate_after: Path, *,
                                   protected_mask=None, support_radius: int = 3,
                                   max_detail_error: float = .001) -> dict:
    """Select a verified paired terrain delta, stripping every other rewrite.

    Only known terrain components can enter the returned transaction. Pair
    comparison is static evidence; runtime heights/pathing stay unobserved.
    """
    if isinstance(support_radius, bool) or not isinstance(support_radius, int) or not 0 <= support_radius <= 8:
        raise SC2Error("invalid_sync_support_radius", "同步影响邻域半径必须为0至8")
    tolerance = _finite(max_detail_error, "max_detail_error")
    if not 0 <= tolerance <= .01:
        raise SC2Error("invalid_detail_tolerance", "详细高度误差门限必须为0至0.01")
    paths = [control_before, control_after, candidate_before, candidate_after]
    initial = [snapshot(p) for p in paths]
    a, b, c, d = [Terrain(p) for p in paths]
    dimensions = {(t.width, t.height) for t in [a, b, c, d]}
    if len(dimensions) != 1:
        raise SC2Error("native_sync_dimensions", "配对原生同步改变了地形尺寸")
    mask = _mask(protected_mask, (a.height, a.width))
    checks = {}
    checks["input_structural_channels"] = bool(np.array_equal(a.vertices[:, :, 1:], c.vertices[:, :, 1:]))
    checks["input_smap_unchanged"] = bool(np.array_equal(a.sync, c.sync))
    for name, first, second in [("control", a, b), ("candidate", c, d), ("paired", b, d)]:
        checks[name + "_cliffs"] = bool(np.array_equal(first.cliffs, second.cliffs))
        checks[name + "_cell_flags"] = bool(np.array_equal(first.flags, second.flags))
        checks[name + "_height_mask"] = bool(np.array_equal(first.vertices[:, :, 2], second.vertices[:, :, 2]))
        checks[name + "_smap_mask"] = bool(np.array_equal(first.sync[:, :, 1], second.sync[:, :, 1]))
    checks["control_detail_preserved"] = bool(np.max(np.abs(a.detailed_heights - b.detailed_heights)) <= tolerance)
    checks["candidate_detail_preserved"] = bool(np.max(np.abs(c.detailed_heights - d.detailed_heights)) <= tolerance)
    for branch in ["cliffCellList", "rampList", "textureList"]:
        checks["paired_xml_" + branch] = _xml_semantic(b.meta.find(branch)) == _xml_semantic(d.meta.find(branch))
    checks["paired_xml_other_fields"] = _xml_without_quantization(b.tree) == _xml_without_quantization(d.tree)
    checks["input_xml_structure"] = _xml_without_quantization(a.tree) == _xml_without_quantization(c.tree)
    checks["control_xml_structure"] = _xml_without_quantization(a.tree) == _xml_without_quantization(b.tree)
    checks["candidate_xml_structure"] = _xml_without_quantization(c.tree) == _xml_without_quantization(d.tree)
    brush = a.vertices[:, :, 0] != c.vertices[:, :, 0]
    support = _dilate(brush, support_radius)
    delta = np.abs(d.heights - b.heights)
    checks["sync_outside_support"] = bool(np.all(delta[~support] == 0))
    checks["protected_brush"] = bool(np.array_equal(a.vertices[:, :, 0][mask], c.vertices[:, :, 0][mask]))
    checks["protected_sync"] = bool(np.all(delta[mask] == 0))
    applied_delta = np.abs(d.heights - c.heights)
    checks["applied_sync_outside_support"] = bool(np.all(applied_delta[~support] == 0))
    checks["applied_protected_sync"] = bool(np.all(applied_delta[mask] == 0))
    observed = [snapshot(p) for p in paths]
    if initial != observed:
        raise SC2Error("native_sync_source_changed", "配对检查期间来源组件发生变化，需重新规划")
    before_control, after_control, before_candidate, after_candidate = observed
    checks["paired_vertex_color_cache"] = after_control.get("t3VertCol") == after_candidate.get("t3VertCol")
    # All non-whitelisted terrain/topology/pathing layers must agree between
    # the two native outputs. Natural script/shell rewrites are only listed.
    guarded = {name for name in before_control | before_candidate | after_control | after_candidate
               if (name.startswith("t3") or name.startswith("CellAttribute_")) and name not in NATIVE_COMPONENTS
               and not name.endswith(".version")}
    checks["paired_other_terrain"] = all(after_control.get(name) == after_candidate.get(name) for name in guarded)
    target = snapshot(root)
    baseline_layers = NATIVE_COMPONENTS | guarded
    checks["target_terrain_baseline"] = all(target.get(name) == before_candidate.get(name) for name in baseline_layers)
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SC2Error("native_sync_semantic_gate", "原生同步配对语义门禁未通过，保留输出供复核", failed=failed, checks=checks,
                       outside_support_max_delta=float(delta[~support].max()) if np.any(~support) else 0.,
                       applied_outside_support_max_delta=float(applied_delta[~support].max()) if np.any(~support) else 0.)
    changes = {}
    for name in sorted(NATIVE_COMPONENTS):
        if name in target and name not in after_candidate:
            raise SC2Error("native_sync_component_missing", "原生输出缺少必要地形组件", component=name)
        if target.get(name) != after_candidate.get(name) and name in after_candidate:
            data = safe_path(candidate_after, name).read_bytes()
            if digest(data) != after_candidate[name]:
                raise SC2Error("native_sync_source_changed", "读取候选组件期间来源发生变化", component=name)
            changes[name] = data
    control_changed = sorted(n for n in before_control | after_control if before_control.get(n) != after_control.get(n))
    candidate_changed = sorted(n for n in before_candidate | after_candidate if before_candidate.get(n) != after_candidate.get(n))
    return {"changes": changes, "support": SUPPORT_VERSION, "status": "static_pair_checked",
            "checks": checks, "protection": _mask_info(mask), "brush_vertices": int(np.count_nonzero(brush)),
            "support_vertices": int(np.count_nonzero(support)), "sync_changed_vertices": int(np.count_nonzero(delta)),
            "outside_support_max_delta": float(delta[~support].max()) if np.any(~support) else 0.,
            "control_natural_rewrites": control_changed, "candidate_native_rewrites": candidate_changed,
            "excluded_native_rewrites": sorted(set(candidate_changed) - NATIVE_COMPONENTS),
            "accepted_components": sorted(changes), "source_fingerprints": {"target": target,
                "control_before": before_control, "control_after": after_control,
                "candidate_before": before_candidate, "candidate_after": after_candidate},
            "evidence": {"static": "passed_supported_pair_checks", "native": "caller_supplied_outputs",
                         "runtime": "not_observed", "visual": "not_observed"}, "playable_delivery": False}


def plan_native_sync_result(root: Path, control_before: Path, control_after: Path,
                            candidate_before: Path, candidate_after: Path, **kwargs) -> dict[str, bytes | None]:
    return plan_native_sync_result_report(root, control_before, control_after, candidate_before, candidate_after, **kwargs)["changes"]


def _protected(path, roots):
    actual = guard_absolute_path(path).resolve()
    if any(actual.is_relative_to(guard_absolute_path(r).resolve()) for r in [_FORMAL, *(roots or [])]):
        raise SC2Error("native_sync_protected_path", "原生同步不接受正式或受保护路径", path=str(actual))
    return actual


def _archive_input(path, protected_roots):
    if any(c in str(path) for c in "*?\x00\r\n"):
        raise SC2Error("native_sync_explicit_archive", "必须指定单个明确归档，禁止通配和控制字符")
    path = _protected(Path(path), protected_roots)
    if not path.is_file() or path.suffix.casefold() != ".sc2map":
        raise SC2Error("native_sync_explicit_archive", "仅接受明确存在的独立SC2Map归档，不能传目录", path=str(path))
    archives.inspect_archive(path)
    return path


def _cancelled(token):
    return token is not None and token.is_set()


def _running(record):
    try:
        proc = psutil.Process(record["pid"])
        return (abs(proc.create_time() - record["created"]) < .01
                and str(Path(proc.exe()).resolve()).casefold() == record["executable"].casefold()
                and [v.casefold() for v in proc.cmdline()] == [v.casefold() for v in record["argv"]])
    except (psutil.Error, KeyError, OSError):
        return False


def run_native_sync(control_archive: Path, candidate_archive: Path, destination: Path,
                     installation: Path, *, state_root: Path, expected_editor_sha256: str,
                     protected_roots=None, product: str = "s2_cn", timeout: float = 120,
                     cancel=None) -> dict:
    """Run serial paired -resaveall on fresh copies, under the probe lock.

    No process is killed. A timeout/cancellation returns partial ownership
    evidence and prevents the next archive launch. Inputs remain immutable.
    """
    timeout = _finite(timeout, "timeout")
    if not 0 < timeout <= 3600:
        raise SC2Error("invalid_native_timeout", "原生同步超时必须为0至3600秒")
    if product not in {"s2_cn", "s2"}:
        raise SC2Error("unsupported_native_product", "未验证的编辑器产品参数", product=product)
    if expected_editor_sha256 != SUPPORTED_EDITOR_SHA256:
        raise SC2Error("unsupported_native_editor", "该编辑器指纹尚未列入原生同步支持范围")
    installation = guard_absolute_path(Path(installation)).resolve()
    executable = guard_absolute_path(installation / "Support64/SC2Editor_x64.exe").resolve()
    if not executable.is_file() or digest(executable.read_bytes()) != expected_editor_sha256:
        raise SC2Error("native_editor_fingerprint", "编辑器指纹不匹配", executable=str(executable))
    control = _archive_input(control_archive, protected_roots)
    candidate = _archive_input(candidate_archive, protected_roots)
    if control == candidate:
        raise SC2Error("native_sync_pair_required", "对照与候选必须是两份独立归档")
    destination = _protected(Path(destination), protected_roots)
    if destination.exists():
        raise SC2Error("native_sync_output_exists", "原生同步证据目录必须全新，不能覆盖", path=str(destination))
    sources = {"control": control, "candidate": candidate}
    hashes = {key: digest(path.read_bytes()) for key, path in sources.items()}
    lock = _protected(Path(state_root), protected_roots) / "probe-installation-locks" / (digest(str(installation).casefold().encode()) + ".lock")
    with file_lock(lock):
        active = editor.processes(installation)
        if active:
            raise SC2Error("native_sync_editor_busy", "安装目录已有编辑器或游戏实例，保留用户会话", processes=active)
        if _cancelled(cancel):
            raise SC2Error("cancelled", "原生同步启动前已取消")
        destination.mkdir(parents=True, exist_ok=False)
        manifest_path = destination / "native-sync.json"
        manifest = {"support": SUPPORT_VERSION, "state": "prepared", "installation": str(installation),
                    "editor_sha256": expected_editor_sha256, "source_hashes": hashes,
                    "source_archives": {k: str(p) for k, p in sources.items()}, "runs": [],
                    "evidence": {"native": "not_complete", "runtime": "not_observed", "visual": "not_observed"}}
        write_json(manifest_path, manifest)
        for number, key in enumerate(["control", "candidate"]):
            if editor.processes(installation):
                manifest.update(state="partial", reason="editor_became_busy")
                write_json(manifest_path, manifest)
                return manifest
            if _cancelled(cancel):
                manifest.update(state="partial", reason="cancelled_before_next_archive")
                write_json(manifest_path, manifest)
                return manifest
            path = destination / (key + ".SC2Map")
            shutil.copyfile(sources[key], path)
            if digest(path.read_bytes()) != hashes[key]:
                manifest.update(state="partial", reason="source_archive_changed", source_archives_unchanged=False)
                write_json(manifest_path, manifest)
                return manifest
            before = archives.extract_archive(path, destination / (key + "-before.SC2Map"))
            argv = [str(executable), "-resaveall", str(path), "-product", "SC2", "-uid", product]
            stdout_path, stderr_path = destination / (key + "-stdout.log"), destination / (key + "-stderr.log")
            kwargs = {"cwd": destination, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
            if os.name == "nt":
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = 0
                kwargs["startupinfo"] = startup
            with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                try:
                    process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, **kwargs)
                except OSError as exc:
                    manifest.update(state="failed", reason="native_launch_failed", launch_error=str(exc))
                    write_json(manifest_path, manifest)
                    return manifest
                record = {"role": key, "pid": process.pid,
                          "executable": str(executable), "archive": str(path), "argv": argv,
                          "started_at": time.time(), "before_sha256": hashes[key], "before_components": before,
                          "stdout": str(stdout_path), "stderr": str(stderr_path)}
                manifest["runs"].append(record)
                try:
                    record["created"] = psutil.Process(process.pid).create_time()
                    record["ownership_verified"] = _running(record)
                except psutil.Error as exc:
                    record["identity_error"] = type(exc).__name__
                    record["ownership_verified"] = False
                manifest["state"] = "running"
                write_json(manifest_path, manifest)
                if not record["ownership_verified"] and process.poll() is None:
                    manifest.update(state="partial", reason="process_identity_unverified", running_process_retained=True)
                    write_json(manifest_path, manifest)
                    return manifest
                started = time.monotonic()
                while process.poll() is None:
                    if _cancelled(cancel) or time.monotonic() - started >= timeout:
                        record["ownership_verified"] = _running(record)
                        manifest.update(state="partial", reason="cancelled" if _cancelled(cancel) else "timeout",
                                        running_process_retained=True)
                        write_json(manifest_path, manifest)
                        return manifest
                    time.sleep(.1)
                record["exit_code"] = process.returncode
                record["after_sha256"] = digest(path.read_bytes())
            if process.returncode != 0:
                manifest.update(state="failed", reason="native_nonzero_exit")
                write_json(manifest_path, manifest)
                return manifest
            record["after_components"] = archives.extract_archive(path, destination / (key + "-after.SC2Map"))
            record["native_completed"] = True
            if cancel is not None and hasattr(cancel, "report_progress"):
                cancel.report_progress(45 + number * 45, key + " 原生重存输出已回读")
            write_json(manifest_path, manifest)
        unchanged = all(digest(path.read_bytes()) == hashes[key] for key, path in sources.items())
        if not unchanged:
            manifest.update(state="partial", reason="source_archive_changed", source_archives_unchanged=False)
        else:
            manifest.update(state="native_complete", source_archives_unchanged=True,
                            requires_paired_semantic_gate=True)
            manifest["evidence"]["native"] = "paired_native_processes_completed"
        write_json(manifest_path, manifest)
        return manifest
