"""Strict, read-only parser for Warcraft III SYLK files.

The parser never writes files, reads the filesystem, or touches the network.
``parse_slk_bytes`` decodes an in-memory byte string and returns the parsed
table; ``source`` is only echoed into error details.

Decoding
--------
UTF-8 (optionally with a leading BOM) is tried first, otherwise strict
GB18030.  ``errors='replace'``/``'ignore'`` are never used: if neither codec
accepts the bytes, ``SC2Error('war3_slk_encoding', ...)`` is raised.

Syntax handled
--------------
* Fields are separated by semicolons that are *outside* double quotes.
* Inside a quoted field a semicolon is data.
* A doubled quote (``""``) and a backslash-escaped quote (``\\"``) both mean
  one literal quote character.
* The ``K`` field content keeps its first character; a quoted ``K`` value is
  unescaped, any other ``K`` value is kept verbatim (numbers stay strings).
* ``X``/``Y`` record fields may be omitted; an omitted coordinate is inherited
  from the most recently seen coordinate on that axis.
* Only records whose type field is exactly ``C`` are read; every other record
  (``ID``, ``B``, ``F``, ``O``, ``E``, ...) is ignored.

Row ``Y == 1`` is the header row.  Rows are returned sparsely: a row mapping
only holds columns that were actually present.  ``cell_count`` is the number
of parsed ``C`` cells, including the header row.

Errors are explicit (``SC2Error`` codes) instead of guessed:
``war3_slk_encoding``, ``war3_slk_unclosed_quote``, ``war3_slk_coordinate``,
``war3_slk_duplicate_cell``, ``war3_slk_header``, ``war3_slk_missing_header``,
``war3_slk_field``.
"""

from __future__ import annotations

import codecs
import re

from .errors import SC2Error

__all__ = ["parse_slk_bytes"]

_INT_RE = re.compile(r"[+-]?[0-9]+")
_LINE_RE = re.compile(r"\r\n|\r|\n")


def _decode(data: bytes, source: str) -> tuple[str, str]:
    if not isinstance(data, (bytes, bytearray)):
        raise SC2Error("war3_slk_encoding", "SYLK source must be bytes", source=source)
    raw = bytes(data)
    has_bom = raw.startswith(codecs.BOM_UTF8)
    try:
        return raw.decode("utf-8-sig"), ("utf-8-sig" if has_bom else "utf-8")
    except UnicodeDecodeError as utf8_error:
        try:
            return raw.decode("gb18030"), "gb18030"
        except UnicodeDecodeError as gb18030_error:
            raise SC2Error(
                "war3_slk_encoding",
                "SYLK bytes are neither valid UTF-8 nor valid GB18030",
                source=source,
                utf8_error=str(utf8_error),
                gb18030_error=str(gb18030_error),
            ) from gb18030_error


def _split_fields(line: str, source: str, line_no: int) -> list[str]:
    """Split on semicolons outside double quotes; keep raw escaped text."""
    fields: list[str] = []
    buf: list[str] = []
    in_quotes = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and in_quotes and i + 1 < n and line[i + 1] == '"':
            buf.append("\\")
            buf.append('"')
            i += 2
            continue
        if ch == '"':
            if in_quotes and i + 1 < n and line[i + 1] == '"':
                buf.append('"')
                buf.append('"')
                i += 2
                continue
            in_quotes = not in_quotes
            buf.append(ch)
            i += 1
            continue
        if ch == ";" and not in_quotes:
            fields.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if in_quotes:
        raise SC2Error(
            "war3_slk_unclosed_quote",
            "unterminated quoted field",
            source=source,
            line=line_no,
        )
    fields.append("".join(buf))
    return fields


def _extract_value(field: str, source: str, line_no: int) -> str:
    """Return the K payload, preserving the first character of the string."""
    content = field[1:]
    if not content.startswith('"'):
        return content
    out: list[str] = []
    i = 1
    n = len(content)
    while i < n:
        ch = content[i]
        if ch == "\\" and i + 1 < n and content[i + 1] == '"':
            out.append('"')
            i += 2
            continue
        if ch == '"':
            if i + 1 < n and content[i + 1] == '"':
                out.append('"')
                i += 2
                continue
            if i + 1 != n:
                raise SC2Error(
                    "war3_slk_field",
                    "trailing data after K string",
                    source=source,
                    line=line_no,
                    field=field,
                )
            return "".join(out)
        out.append(ch)
        i += 1
    raise SC2Error(
        "war3_slk_unclosed_quote",
        "unterminated K string",
        source=source,
        line=line_no,
        field=field,
    )


def _parse_coord(field: str, source: str, line_no: int) -> int:
    raw = field[1:]
    if not _INT_RE.fullmatch(raw):
        raise SC2Error(
            "war3_slk_coordinate",
            "invalid coordinate field",
            source=source,
            line=line_no,
            field=field,
        )
    value = int(raw)
    if value < 1:
        raise SC2Error(
            "war3_slk_coordinate",
            "coordinate must be >= 1",
            source=source,
            line=line_no,
            field=field,
        )
    return value


def parse_slk_bytes(data: bytes, *, source: str = "", preserve_unknown_columns: bool = False) -> dict:
    """Parse SYLK ``data`` into encoding/columns/rows/cell_count."""
    text, encoding = _decode(data, source)
    cells: dict[tuple[int, int], str] = {}
    last_x: int | None = None
    last_y: int | None = None
    cell_count = 0

    for line_no, line in enumerate(_LINE_RE.split(text), start=1):
        if line == "":
            continue
        fields = _split_fields(line, source, line_no)
        if fields[0] != "C":
            continue
        x = last_x
        y = last_y
        value = ""
        seen_k = False
        for field in fields[1:]:
            if field == "":
                continue
            head = field[0]
            if head == "X":
                x = _parse_coord(field, source, line_no)
            elif head == "Y":
                y = _parse_coord(field, source, line_no)
            elif head == "K":
                if seen_k:
                    raise SC2Error(
                        "war3_slk_field",
                        "duplicate K field in C record",
                        source=source,
                        line=line_no,
                    )
                seen_k = True
                value = _extract_value(field, source, line_no)
        if x is None or y is None:
            raise SC2Error(
                "war3_slk_coordinate",
                "C record omits a coordinate with no prior value to inherit",
                source=source,
                line=line_no,
            )
        if (x, y) in cells:
            raise SC2Error(
                "war3_slk_duplicate_cell",
                "duplicate cell coordinate",
                source=source,
                line=line_no,
                x=x,
                y=y,
            )
        cells[(x, y)] = value
        last_x = x
        last_y = y
        cell_count += 1

    header_cells = {x: value for (x, y), value in cells.items() if y == 1}
    if not header_cells:
        raise SC2Error(
            "war3_slk_header",
            "missing header row (Y=1)",
            source=source,
        )

    columns: list[str] = []
    header_by_x: dict[int, str] = {}
    seen_names: set[str] = set()
    for x in sorted(header_cells):
        name = header_cells[x]
        if name == "":
            raise SC2Error(
                "war3_slk_header",
                "empty header cell",
                source=source,
                x=x,
            )
        if name in seen_names:
            raise SC2Error(
                "war3_slk_header",
                "duplicate header name",
                source=source,
                name=name,
            )
        seen_names.add(name)
        header_by_x[x] = name
        columns.append(name)

    row_values: dict[int, dict[str, str]] = {}
    unknown_cells = []
    for (x, y), value in cells.items():
        if y == 1:
            continue
        if x not in header_by_x:
            if preserve_unknown_columns:
                unknown_cells.append({'x':x,'y':y,'value':value})
                continue
            raise SC2Error(
                "war3_slk_missing_header",
                "data column has no header",
                source=source,
                x=x,
                y=y,
            )
        row_values.setdefault(y, {})[header_by_x[x]] = value

    rows = [row_values[y] for y in sorted(row_values)]
    result = {
        "encoding": encoding,
        "columns": columns,
        "rows": rows,
        "cell_count": cell_count,
    }
    if preserve_unknown_columns:
        result['unknown_cells'] = unknown_cells
        result['complete'] = not unknown_cells
    return result
