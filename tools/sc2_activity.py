"""Coordinate game launches and integration regressions across local projects."""
import contextlib
import datetime
import json
import os
from pathlib import Path
import time
import threading

from sc2_integration_runtime import process_lock

_local = threading.local()


def activity_dir():
    return Path.home() / ".sc2-agent" / "activity"


def running_games():
    import psutil
    names = {"sc2.exe", "sc2_x64.exe", "sc2switcher.exe", "sc2switcher_x64.exe"}
    found = []
    for process in psutil.process_iter(["name", "create_time", "num_threads"]):
        if (process.info["name"] or "").lower() in names:
            created = process.info["create_time"]
            if process.info["num_threads"] == 0 and created and time.time()-created > 90:
                continue  # Windows may retain threadless process objects long after exit.
            start = datetime.datetime.fromtimestamp(created).astimezone().isoformat(timespec="seconds") if created else "未知"
            found.append(f"{process.info['name']} (PID {process.pid}，开始于 {start})")
    return found



class ActivityBusy(RuntimeError):
    pass


def metadata(path):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}


def save(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


@contextlib.contextmanager
def heavy_activity(task):
    if getattr(_local,"task",None) in {"SC2 运行探针","归档并启动测试地图"} and task == "SC2 游戏启动":
        yield
        return
    directory = activity_dir()
    info = directory / "owner.json"
    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(process_lock(directory / "heavy.lock"))
        except BlockingIOError as exc:
            owner = metadata(info)
            raise ActivityBusy(f"正在运行 {owner.get('task','其他重任务')}，开始于 {owner.get('started','启动中')}。结束后请重试。") from exc
        pending = directory / "launch.json"
        launch = metadata(pending)
        if launch.get("deadline", 0) > time.time():
            raise ActivityBusy(f"SC2 启动器正在向客户端交接，开始于 {launch.get('started','未知')}。游戏退出后请重试。")
        games = running_games()
        if games:
            raise ActivityBusy("正在运行 " + ", ".join(games) + "。游戏退出后请重试。")
        save(info, {"task":task, "started":datetime.datetime.now().astimezone().isoformat(timespec="seconds"),"pid":os.getpid()})
        _local.task = task
        try:
            yield
        finally:
            _local.task = None


def reserve_start():
    # Survives the launching Python process exiting before SC2Switcher hands off.
    path = activity_dir() / "launch.json"
    save(path, {"deadline":time.time()+90,"started":datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
    return path
