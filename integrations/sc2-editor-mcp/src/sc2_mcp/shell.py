"""Lossless codecs for independently verified portions of SC2 map shells."""
from __future__ import annotations

import struct

from .errors import SC2Error


def header_dependencies(data: bytes):
    # H2CS v8: fixed 44-byte prefix, u32 dependency count, N UTF-8 C strings,
    # then a localization table. Validate its full structure before permitting edits.
    if len(data) < 52 or data[:4] != b"H2CS" or struct.unpack_from("<I", data, 4)[0] != 8:
        raise SC2Error("unsupported_header", "仅支持已验证的 H2CS v8 DocumentHeader")
    count = struct.unpack_from("<I", data, 44)[0]
    if count > 1024:
        raise SC2Error("invalid_header", "依赖数量超出合理范围")
    cursor, values = 48, []
    try:
        for _ in range(count):
            end = data.index(b"\0", cursor)
            value = data[cursor:end].decode("utf-8")
            if not value:
                raise ValueError("empty dependency reference")
            values.append(value)
            cursor = end + 1
        dep_end = cursor
        strings = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if strings > 100000:
            raise ValueError("invalid localization count")
        for _ in range(strings):
            length = struct.unpack_from("<H", data, cursor)[0]
            cursor += 2
            data[cursor:cursor+length].decode("utf-8")
            cursor += length + 4  # locale FourCC
            length = struct.unpack_from("<H", data, cursor)[0]
            cursor += 2
            data[cursor:cursor+length].decode("utf-8")
            cursor += length
        if cursor != len(data):
            raise ValueError("unrecognized trailing header data")
    except (ValueError, UnicodeError, struct.error) as exc:
        raise SC2Error("unsupported_header", "DocumentHeader 结构与已验证格式不一致", reason=str(exc)) from exc
    return {"values": values, "start": 44, "end": dep_end, "version": 8, "strings": strings,
            "prefix_bytes": 44, "suffix_bytes": len(data) - dep_end, "validation": "structure_only"}


def replace_header_dependencies(data: bytes, old: list[str], new: list[str]):
    info = header_dependencies(data)
    if info["values"] != old:
        raise SC2Error("shell_mismatch", "DocumentInfo 和 DocumentHeader 的依赖不一致", header=info["values"], document=old)
    if any(not isinstance(v, str) or not v or "\0" in v for v in new):
        raise SC2Error("invalid_dependency", "依赖名称为空或含 NUL")
    if len(new) > 1024:
        raise SC2Error("invalid_dependency", "依赖数量超出已验证范围")
    payload = struct.pack("<I", len(new)) + b"".join(v.encode("utf-8") + b"\0" for v in new)
    result = data[:44] + payload + data[info["end"]:]
    header_dependencies(result)
    return result


def replace_header_localization(data: bytes, updates: dict[str,str], locale: bytes=b'NChz'):
    """Update existing H2CS8 localized values, preserving all identity bytes."""
    info=header_dependencies(data)
    cursor=info['end']+4
    edits=[];matched=set()
    for _ in range(info['strings']):
        size=struct.unpack_from('<H',data,cursor)[0];cursor+=2
        key=data[cursor:cursor+size].decode('utf-8');cursor+=size
        entry_locale=data[cursor:cursor+4];cursor+=4
        begin=cursor
        size=struct.unpack_from('<H',data,cursor)[0];cursor+=2
        cursor+=size
        if entry_locale==locale and key in updates:
            value=updates[key].encode('utf-8')
            if len(value)>65535 or b'\0' in value or key in matched:
                raise SC2Error('invalid_header_localization','外壳文本过长、含NUL或键不唯一')
            edits.append((begin,cursor,struct.pack('<H',len(value))+value));matched.add(key)
    if matched!=set(updates):
        raise SC2Error('header_text_missing','外壳不存在所选地区的全部文本键',missing=sorted(set(updates)-matched))
    for begin,end,replacement in reversed(edits):data=data[:begin]+replacement+data[end:]
    header_dependencies(data)
    return data
