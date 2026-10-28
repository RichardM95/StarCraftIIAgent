"""Read-only parser for Warcraft III binary object-data ("object editor") files.

Shared container layout (w3a/w3b/w3d/w3h/w3q/w3u/w3t):

    i32 version                       (only 1 and 2 are known)
    original table: i32 count, then count objects
    custom table:   i32 count, then count objects
    object: 4-byte old_id rawcode, 4-byte new_id rawcode, i32 modification_count
    mod:    4-byte field_id rawcode, i32 value_type
            (abilities/upgrades only) i32 level, i32 column
            value: type 0 -> i32, type 1/2 -> float32, type 3 -> NUL-terminated bytes
            4-byte end marker after EACH modification

No filesystem or network access. Unknown/corrupt content is reported through
``diagnostics`` (``complete`` becomes False) or raises :class:`SC2Error` with a
specific ``code``. This module does not claim the data is playable.
"""

from __future__ import annotations

import hashlib
import math
import struct
from .errors import SC2Error

__all__ = ["SC2Error", "parse_object_bytes", "KNOWN_KINDS", "EXTENSIONS", "VALUE_TYPES"]


KNOWN_KINDS = frozenset(
    {"abilities", "upgrades", "destructables", "doodads", "buffs", "units", "items"}
)
EXTENSIONS = {
    "abilities": "w3a",
    "destructables": "w3b",
    "doodads": "w3d",
    "buffs": "w3h",
    "upgrades": "w3q",
    "units": "w3u",
    "items": "w3t",
}
_LEVEL_COLUMN_KINDS = frozenset({"abilities", "upgrades"})
VALUE_TYPES = {0: "int", 1: "float", 2: "float", 3: "string"}
_STRING_TYPE = 3
_NULL_RAWCODE = b"\x00\x00\x00\x00"


def _diag(code: str, message: str, offset: int, raw: bytes = b"") -> dict:
    entry = {"code": code, "message": message, "offset": offset}
    if raw:
        entry["raw_hex"] = raw.hex()
    return entry


def _resolve_kind(kind: str) -> str:
    if not isinstance(kind, str):
        raise SC2Error("unsupported_kind", f"kind must be str, got {type(kind).__name__}")
    key = kind.strip().lower()
    if key in KNOWN_KINDS:
        return key
    if key in EXTENSIONS:
        return EXTENSIONS[key]
    raise SC2Error("unsupported_kind", f"unsupported kind {kind!r}")


def _decode_text(raw: bytes) -> tuple[str | None, str]:
    """Strict UTF-8 first, then strict GB18030. Never replaces/ignores bytes."""
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030"), "gb18030"
    except UnicodeDecodeError:
        return None, "unknown"


def _decode_rawcode(raw: bytes, diagnostics: list, offset: int, label: str) -> tuple[str | None, str]:
    if raw == _NULL_RAWCODE:
        return None, "null"
    try:
        return raw.decode("ascii"), "ascii"
    except UnicodeDecodeError:
        diagnostics.append(
            _diag("rawcode_not_ascii", f"{label} rawcode is not valid ASCII", offset, raw)
        )
        return None, "unknown"


def _check_count(value: int, minimum_bytes: int, remaining: int, what: str, offset: int) -> None:
    if value < 0:
        raise SC2Error("negative_count", f"{what} is negative: {value}", offset=offset)
    if minimum_bytes > 0:
        maximum = remaining // minimum_bytes
        if value > maximum:
            raise SC2Error(
                "count_out_of_range",
                f"{what}={value} exceeds maximum {maximum} implied by {remaining} remaining bytes",
                offset=offset,
            )


class _Reader:
    __slots__ = ("data", "pos", "size")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.size = len(data)

    def remaining(self) -> int:
        return self.size - self.pos

    def need(self, n: int, what: str) -> None:
        if n < 0 or self.remaining() < n:
            raise SC2Error(
                "out_of_bounds",
                f"need {n} bytes for {what} at offset {self.pos}, only {self.remaining()} left",
                offset=self.pos,
            )

    def i32(self, what: str) -> int:
        self.need(4, what)
        (value,) = struct.unpack_from("<i", self.data, self.pos)
        self.pos += 4
        return value

    def raw4(self, what: str) -> bytes:
        self.need(4, what)
        raw = self.data[self.pos : self.pos + 4]
        self.pos += 4
        return raw

    def f32(self, what: str) -> float:
        self.need(4, what)
        (value,) = struct.unpack_from("<f", self.data, self.pos)
        self.pos += 4
        return value


def _parse_modification(reader: _Reader, diagnostics: list, has_level_column: bool) -> dict:
    field_offset = reader.pos
    field_raw = reader.raw4("field_id")
    field_id, field_encoding = _decode_rawcode(field_raw, diagnostics, field_offset, "field_id")

    type_offset = reader.pos
    value_type = reader.i32("value_type")
    if value_type not in VALUE_TYPES:
        raise SC2Error(
            "unknown_value_type",
            f"unknown modification value type {value_type}",
            offset=type_offset,
        )

    level = None
    column = None
    if has_level_column:
        level = reader.i32("level")
        column = reader.i32("column")

    value_offset = reader.pos
    if value_type == 0:
        value = reader.i32("int value")
        raw = reader.data[value_offset : reader.pos]
        encoding = None
    elif value_type in (1, 2):
        value = reader.f32("float value")
        raw = reader.data[value_offset : reader.pos]
        encoding = None
        if not math.isfinite(value):
            diagnostics.append(
                _diag("non_finite_float", f"non-finite float32 {value!r}", value_offset, raw)
            )
            value = None
            encoding = "unknown"
    else:  # _STRING_TYPE
        nul = reader.data.find(b"\x00", value_offset)
        if nul == -1:
            raise SC2Error(
                "unterminated_string",
                f"string at offset {value_offset} has no NUL terminator",
                offset=value_offset,
            )
        raw = reader.data[value_offset:nul]
        reader.pos = nul + 1
        value, encoding = _decode_text(raw)
        if value is None:
            diagnostics.append(
                _diag(
                    "undecodable_string",
                    f"string at offset {value_offset} is neither valid UTF-8 nor GB18030",
                    value_offset,
                    raw,
                )
            )

    end_offset = reader.pos
    end_marker = reader.raw4('modification end_marker')
    return {
        "field_id": field_id,
        "field_id_raw_hex": field_raw.hex(),
        "field_id_encoding": field_encoding,
        "type": value_type,
        "type_name": VALUE_TYPES[value_type],
        "level": level,
        "column": column,
        "value": value,
        "encoding": encoding,
        "raw_hex": raw.hex(),
        "end_marker_raw_hex": end_marker.hex(),
        "end_marker_offset": end_offset,
        "byte_offset": value_offset,
        "size": reader.pos - field_offset,
    }


def _parse_table(reader: _Reader, name: str, diagnostics: list, has_level_column: bool) -> dict:
    count_offset = reader.pos
    count = reader.i32(f"{name} table count")
    _check_count(count, 12, reader.remaining(), f"{name} table count", count_offset)

    min_mod = 8 + (8 if has_level_column else 0) + 1 + 4
    objects = []
    for _ in range(count):
        object_offset = reader.pos
        old_raw = reader.raw4("old_id")
        old_id, old_encoding = _decode_rawcode(old_raw, diagnostics, object_offset, "old_id")

        new_offset = reader.pos
        new_raw = reader.raw4("new_id")
        new_id, new_encoding = _decode_rawcode(new_raw, diagnostics, new_offset, "new_id")

        mod_count_offset = reader.pos
        mod_count = reader.i32("modification count")
        _check_count(mod_count, min_mod, reader.remaining(), "modification count", mod_count_offset)

        modifications = [
            _parse_modification(reader, diagnostics, has_level_column) for _ in range(mod_count)
        ]
        for modification in modifications:
            if bytes.fromhex(modification['end_marker_raw_hex']) not in {_NULL_RAWCODE, old_raw, new_raw}:
                diagnostics.append(_diag('unexpected_end_marker','modification end marker is neither zero nor its object ID',
                                         modification['end_marker_offset'],bytes.fromhex(modification['end_marker_raw_hex'])))
        objects.append(
            {
                "old_id": old_id,
                "old_id_raw_hex": old_raw.hex(),
                "old_id_encoding": old_encoding,
                "new_id": new_id,
                "new_id_raw_hex": new_raw.hex(),
                "new_id_encoding": new_encoding,
                "new_id_present": new_raw != _NULL_RAWCODE,
                "byte_offset": object_offset,
                "modifications": modifications,
            }
        )

    return {"name": name, "count": count, "objects": objects}


def parse_object_bytes(data: bytes, *, kind: str, source: str = "") -> dict:
    """Parse one Warcraft III object-data payload without touching the disk."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise SC2Error("bad_input", f"data must be bytes-like, got {type(data).__name__}")
    payload = bytes(data)
    kind_name = _resolve_kind(kind)

    reader = _Reader(payload)
    diagnostics: list = []

    version_offset = reader.pos
    version = reader.i32("version")
    if version not in (1, 2):
        raise SC2Error(
            "unsupported_version",
            f"unsupported object-data version {version} (known: 1, 2)",
            offset=version_offset,
        )

    has_level_column = kind_name in _LEVEL_COLUMN_KINDS
    tables = [
        _parse_table(reader, "original", diagnostics, has_level_column),
        _parse_table(reader, "custom", diagnostics, has_level_column),
    ]

    if reader.remaining() > 0:
        tail_offset = reader.pos
        tail = reader.data[reader.pos :]
        reader.pos = reader.size
        diagnostics.append(
            _diag("trailing_bytes", f"{len(tail)} trailing unparsed bytes", tail_offset, tail)
        )

    return {
        "source": source,
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "kind": kind_name,
        "wanted_extension": EXTENSIONS.get(kind_name),
        "version": version,
        "has_level_column": has_level_column,
        "tables": tables,
        "diagnostics": diagnostics,
        "complete": len(diagnostics) == 0,
    }
