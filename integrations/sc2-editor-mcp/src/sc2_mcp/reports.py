"""UTF-8 reports with character-based paging and disposable byte-offset indexes."""

import hashlib
import json
import os
from io import TextIOWrapper

from .errors import SC2Error
from .storage import atomic_writer, guard_absolute_path, safe_path, write_json

LIMIT = 48000  # serialized JSON characters, shared with the dispatcher
STEP = 8192


def size(value):
    return len(json.dumps(value, ensure_ascii=False))


def _identity(stat):
    return [stat.st_size, stat.st_mtime_ns, stat.st_dev, stat.st_ino]


def _checksum(identity, characters, offsets):
    return hashlib.sha256(
        json.dumps([1, STEP, identity, characters, offsets]).encode()
    ).hexdigest()


def _save_index(path, identity, characters, offsets):
    try:
        write_json(
            path, [characters, offsets, _checksum(identity, characters, offsets)]
        )
    except OSError:
        pass  # The report remains usable in read-only stores.


def write_report(path, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    offsets = [0]
    with atomic_writer(path) as stream:
        for pos in range(0, len(text), STEP):
            stream.write(text[pos : pos + STEP].encode("utf-8"))
            offsets.append(stream.tell())
    _save_index(path.with_suffix(".ridx"), _identity(path.stat()), len(text), offsets)
    return len(text)


def _load_index(path, stream):
    identity = _identity(os.fstat(stream.fileno()))
    try:
        if path.stat().st_size > 256 + 32 * (identity[0] // STEP + 1):
            raise ValueError("oversized report index")
        characters, offsets, checksum = json.loads(path.read_bytes())
        if (
            type(characters) is int
            and 0 <= characters <= identity[0]
            and isinstance(offsets, list)
            and len(offsets) == 1 + (characters + STEP - 1) // STEP
            and offsets[0] == 0
            and offsets[-1] == identity[0]
            and all(
                type(b) is int and 0 < b - a <= 4 * STEP
                for a, b in zip(offsets, offsets[1:])
            )
            and checksum == _checksum(identity, characters, offsets)
        ):
            return characters, offsets
    except (OSError, ValueError, TypeError, RecursionError):
        pass
    offsets = [0]
    characters = 0
    reader = TextIOWrapper(stream, encoding="utf-8", newline="")
    try:
        while block := reader.read(STEP):
            offsets.append(offsets[-1] + len(block.encode("utf-8")))
            characters += len(block)
    finally:
        reader.detach()
    _save_index(path, identity, characters, offsets)
    return characters, offsets


def read_page(directory, name, offset, limit):
    if offset < 0 or not 1 <= limit <= 100000:
        raise SC2Error("invalid_range", "报告范围无效")
    path = safe_path(directory, name)
    if path.suffix != ".json":
        raise SC2Error("invalid_report", "需要 JSON 报告名")
    index = guard_absolute_path(path.with_suffix(".ridx"))
    parts = []
    with path.open("rb") as stream:
        characters, offsets = _load_index(index, stream)
        # Use the longest possible cursor when reserving envelope space.
        room = LIMIT - size(
            {"ok": True, "result": {"text": "", "next_offset": max(characters, 1000)}}
        )
        end = min(characters, offset + limit)
        while offset < end and room:
            i, within = divmod(offset, STEP)
            stream.seek(offsets[i])
            block = stream.read(offsets[i + 1] - offsets[i]).decode("utf-8")
            chunk = block[within : within + end - offset]
            if not chunk:
                raise SC2Error("invalid_report", "报告正文与索引不一致")
            cost = size(chunk) - 2
            if cost > room:
                low, high = 0, len(chunk)
                while low < high:
                    mid = (low + high + 1) // 2
                    if size(chunk[:mid]) - 2 <= room:
                        low = mid
                    else:
                        high = mid - 1
                parts.append(chunk[:low])
                offset += low
                break
            parts.append(chunk)
            offset += len(chunk)
            room -= cost
    return {
        "text": "".join(parts),
        "next_offset": offset if offset < characters else None,
    }


def short_error(error):
    if size(error) <= LIMIT // 3:
        return error
    return {
        "code": str(error.get("code", "internal_error"))[:128],
        "message": str(error.get("message", ""))[:1500],
        "truncated": True,
    }


def summary(value):
    result = {}
    if isinstance(value, dict):
        for key in ("project_id", "change_id", "job_id", "state", "count", "recovery"):
            item = value.get(key)
            if isinstance(item, str):
                result[key] = item[:384]
            elif isinstance(item, (int, float)):
                result[key] = item
        for key in ("warnings", "limitations"):
            items = value.get(key)
            if isinstance(items, list):
                result[key + "_count"] = len(items)
                result[key] = [
                    item if size(item) <= 512 else {"truncated": True}
                    for item in items[:4]
                ]
        if isinstance(value.get("error"), dict):
            result["error"] = short_error(value["error"])
    return result
