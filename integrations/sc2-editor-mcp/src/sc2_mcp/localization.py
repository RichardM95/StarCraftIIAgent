"""Localization domain API for SC2 component maps.

Pure read-only inspection and byte-preserving candidate planning.  No function
writes to disk: every planner returns ``{map_relative_posix_path: bytes}``.

Localized text lives in ``<locale>.SC2Data/LocalizedData`` style directories as
``Key=Value`` text files.  We edit a single matched line, preserve the file's
BOM policy and newline convention, and reject duplicate keys, malformed input
and newline injection.
"""

from __future__ import annotations

import re
from pathlib import Path

from sc2_mcp.errors import SC2Error

_BOM = b"\xef\xbb\xbf"
_BOM_CHAR = "\ufeff"
_BACKUP_PARTS = {"backup", "backups", "_codex_backups", ".git", "__pycache__", ".pytest_cache", "node_modules"}
_LOCALE_RE = re.compile(r"^[a-z]{2}[A-Z]{2}$")
_KEY_RE = re.compile(r"^[^\s=\x00\r\n]+$")


# ---------------------------------------------------------------------------
# discovery / decoding helpers
# ---------------------------------------------------------------------------

def _is_backup(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    for part in rel.parts:
        low = part.lower()
        if low in _BACKUP_PARTS or low.startswith("~") or low.endswith(".bak") or low.endswith(".orig"):
            return True
    return False


def _find_localization_files(root: Path, locale: str) -> list[Path]:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        raise SC2Error("LOCALIZATION_ROOT_MISSING", f"component root does not exist: {root}", root=str(root))
    token = locale.lower()
    matched: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_backup(path, root):
            continue
        if path.suffix.lower() != ".txt":
            continue
        rel = path.relative_to(root)
        parts = [p.lower() for p in rel.parts]
        in_locale_dir = any(
            p == token or p == token + ".sc2data" or p.startswith(token + ".") for p in parts[:-1]
        )
        if in_locale_dir:
            matched.append(path)
    if not matched:
        raise SC2Error(
            "LOCALIZATION_SOURCE_MISSING",
            f"no localization text files found for locale {locale!r}",
            root=str(root),
            locale=locale,
        )
    return matched


def _decode(data: bytes, relpath: str) -> tuple[str, bool, str]:
    """Return (text, had_bom, newline) after validating the encoding."""
    if b"\x00" in data:
        raise SC2Error("LOCALIZATION_ENCODING_INVALID", f"NUL byte in {relpath}", path=relpath)
    had_bom = data.startswith(_BOM)
    body = data[len(_BOM):] if had_bom else data
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SC2Error(
            "LOCALIZATION_ENCODING_INVALID",
            f"{relpath} is not valid UTF-8: {exc}",
            path=relpath,
        ) from exc
    newline = "\r\n" if "\r\n" in text else ("\r" if "\r" in text else "\n")
    return text, had_bom, newline


def _encode(text: str, had_bom: bool) -> bytes:
    body = text.encode("utf-8")
    return (_BOM + body) if had_bom else body


def _line_starts(text: str, newline: str) -> list[int]:
    starts = [0]
    pos = 0
    while True:
        nxt = text.find(newline, pos)
        if nxt < 0:
            break
        starts.append(nxt + len(newline))
        pos = nxt + len(newline)
    return starts


def _split_lines(text: str, newline: str) -> list[str]:
    return text.split(newline)


def _parse_file(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix()
    text, had_bom, newline = _decode(path.read_bytes(), rel)
    lines = _split_lines(text, newline)
    pairs: list[dict] = []
    malformed: list[dict] = []
    keys: dict[str, list[dict]] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or stripped.startswith("//"):
            continue
        if "=" not in line:
            malformed.append({"path": rel, "line": index + 1, "text": line, "reason": "missing '=' separator"})
            continue
        eq = line.index("=")
        key = line[:eq].strip()
        if key == "":
            malformed.append({"path": rel, "line": index + 1, "text": line, "reason": "empty key"})
            continue
        if not _KEY_RE.match(key):
            malformed.append({"path": rel, "line": index + 1, "text": line, "reason": "key contains whitespace or control characters"})
            continue
        value = line[eq + 1:]
        entry = {"path": rel, "line": index + 1, "key": key, "value": value}
        pairs.append(entry)
        keys.setdefault(key, []).append(entry)
    return {
        "path": path,
        "relpath": rel,
        "text": text,
        "had_bom": had_bom,
        "newline": newline,
        "lines": lines,
        "pairs": pairs,
        "malformed": malformed,
        "keys": keys,
    }


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def inspect_localization(root, locale: str = "zhCN") -> dict:
    """Inspect ``Key=Value`` localization tables for a locale."""
    if not isinstance(locale, str) or not _LOCALE_RE.match(locale):
        raise SC2Error("LOCALIZATION_INVALID_LOCALE", f"invalid locale: {locale!r}", locale=locale)
    root = Path(root)
    files = [_parse_file(p, root) for p in _find_localization_files(root, locale)]

    all_pairs: list[dict] = []
    all_malformed: list[dict] = []
    key_occurrences: dict[str, list[dict]] = {}
    for info in files:
        for entry in info["pairs"]:
            pub = {"key": entry["key"], "value": entry["value"], "path": entry["path"], "line": entry["line"]}
            all_pairs.append(pub)
            key_occurrences.setdefault(entry["key"], []).append(pub)
        all_malformed.extend(info["malformed"])

    duplicates = [
        {"key": key, "count": len(occ), "occurrences": occ}
        for key, occ in sorted(key_occurrences.items())
        if len(occ) > 1
    ]

    return {
        "locale": locale,
        "files": [info["relpath"] for info in files],
        "keys": sorted(key_occurrences),
        "key_count": len(key_occurrences),
        "card_pairs": card_pair_status(key_occurrences),
        "pairs": all_pairs,
        "entry_count": len(all_pairs),
        "duplicates": duplicates,
        "malformed": all_malformed,
        "bom": {info["relpath"]: info["had_bom"] for info in files},
        "newlines": {info["relpath"]: ("crlf" if info["newline"] == "\r\n" else "lf") for info in files},
        "warnings": [],
    }


def card_pair_status(keys):
    names={key[len('Card/Name/'):] for key in keys if key.startswith('Card/Name/')}
    descriptions={key[len('Card/Describe/'):] for key in keys if key.startswith('Card/Describe/')}
    return {'paired':sorted(names&descriptions),
            'missing':[{'card':key,'key':'Card/Describe/'+key} for key in sorted(names-descriptions)]+
                      [{'card':key,'key':'Card/Name/'+key} for key in sorted(descriptions-names)]}


def _find_occurrences(files: list[dict], key: str) -> list[dict]:
    found: list[dict] = []
    for info in files:
        for entry in info["pairs"]:
            if entry["key"] == key:
                found.append({"info": info, "entry": entry})
    return found


def _validate_key(key) -> str:
    if not isinstance(key, str) or not _KEY_RE.match(key):
        raise SC2Error("LOCALIZATION_INVALID_KEY", f"invalid localization key: {key!r}", key=repr(key))
    if key != key.strip():
        raise SC2Error("LOCALIZATION_INVALID_KEY", f"key has surrounding whitespace: {key!r}", key=key)
    return key


def _validate_value(value) -> str:
    if not isinstance(value, str):
        raise SC2Error("LOCALIZATION_INVALID_VALUE", f"value must be a string: {value!r}", value=repr(value))
    if "\n" in value or "\r" in value:
        raise SC2Error("LOCALIZATION_NEWLINE_INJECTION", "localization value must not contain newlines", value=value)
    if "\x00" in value or _BOM_CHAR in value:
        raise SC2Error("LOCALIZATION_INVALID_VALUE", "localization value contains a control character", value=value)
    return value


def plan_localization_set(root, updates: dict[str, str], locale: str = "zhCN") -> dict:
    """Plan precise line edits / appends for localization keys.

    Returns ``{relative_posix_path: bytes}`` and never writes changes.
    """
    if not isinstance(updates, dict):
        raise SC2Error("LOCALIZATION_INVALID_UPDATES", "updates must be a dict[str, str]", type=type(updates).__name__)
    if not updates:
        return {}
    if not isinstance(locale, str) or not _LOCALE_RE.match(locale):
        raise SC2Error("LOCALIZATION_INVALID_LOCALE", f"invalid locale: {locale!r}", locale=locale)

    root = Path(root)
    files = [_parse_file(p, root) for p in _find_localization_files(root, locale)]

    # Primary table for brand new keys: prefer GameStrings.txt, else first file.
    primary = None
    for info in files:
        if info["path"].name.lower() == "gamestrings.txt":
            primary = info
            break
    if primary is None:
        primary = files[0]

    # edits[relpath] -> list of (start, end, replacement) or append payloads
    edits: dict[str, list[tuple[int, int, str]]] = {}
    appends: dict[str, list[str]] = {}

    for key, value in updates.items():
        key = _validate_key(key)
        value = _validate_value(value)
        occurrences = _find_occurrences(files, key)
        if len(occurrences) > 1:
            raise SC2Error(
                "LOCALIZATION_DUPLICATE_KEY",
                f"key {key!r} appears {len(occurrences)} times; refusing ambiguous edit",
                key=key,
                occurrences=[{"path": o["entry"]["path"], "line": o["entry"]["line"]} for o in occurrences],
            )
        if len(occurrences) == 1:
            info = occurrences[0]["info"]
            entry = occurrences[0]["entry"]
            line_index = entry["line"] - 1
            starts = _line_starts(info["text"], info["newline"])
            line_start = starts[line_index]
            raw_line = info["lines"][line_index]
            eq = raw_line.index("=")
            value_start = eq + 1
            while value_start < len(raw_line) and raw_line[value_start] in " \t":
                value_start += 1
            lead = raw_line[eq + 1:value_start]
            abs_start = line_start + value_start
            abs_end = line_start + len(raw_line)
            edits.setdefault(info["relpath"], []).append((abs_start, abs_end, value))
        else:
            appends.setdefault(primary["relpath"], []).append(f"{key}={value}")

    changes: dict[str, bytes] = {}
    for info in files:
        rel = info["relpath"]
        if rel not in edits and rel not in appends:
            continue
        text = info["text"]
        file_edits = list(edits.get(rel, []))
        for new_line in appends.get(rel, []):
            if text and not text.endswith(info["newline"]):
                text = text + info["newline"]
            text = text + new_line + info["newline"]
        file_edits.sort(key=lambda item: item[0])
        prev_end = -1
        for start, end, replacement in file_edits:
            if start < prev_end:
                raise SC2Error("LOCALIZATION_OVERLAP", "overlapping localization edits", path=rel)
            prev_end = end
        for start, end, replacement in sorted(file_edits, key=lambda item: item[0], reverse=True):
            text = text[:start] + replacement + text[end:]
        changes[rel] = _encode(text, info["had_bom"])
    return changes
