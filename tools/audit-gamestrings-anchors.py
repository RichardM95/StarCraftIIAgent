#!/usr/bin/env python3
"""Report catalog Name/Tooltip/Description refs missing from GameStrings.txt."""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_paths import find_project_mods

REPO_ROOT = Path(__file__).resolve().parent.parent

STRING_KEY_PATTERN = (
    r"(?:Button|Unit|Abil|Upgrade|Behavior|Effect|Weapon)/"
    r"(?:Name|Tooltip|Description)/[^\"]+"
)
REF_RE = re.compile(
    rf'<(?:Name|Tooltip|Description)\s+value="({STRING_KEY_PATTERN})"'
)
EFFECT_SET_RE = re.compile(
    rf'<EffectArray\s+Operation="Set"\s+Reference="[^"]+"\s+Value="({STRING_KEY_PATTERN})"'
)
STRING_KEY_RE = re.compile(rf"^{STRING_KEY_PATTERN}$")


def extract_string_references(text: str) -> set[str]:
    """Extract supported player-facing localization keys from catalog XML."""
    refs = set(REF_RE.findall(text))
    refs.update(EFFECT_SET_RE.findall(text))
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return refs
    for elem in root:
        if elem.tag != "CButton" or not elem.attrib.get("id"):
            continue
        for child in elem:
            value = child.get("value")
            if (
                child.tag in ("Name", "Tooltip", "Description")
                and value
                and STRING_KEY_RE.fullmatch(value)
            ):
                refs.add(value)
    return refs


def find_local_mods(explicit: str | None = None) -> list[Path]:
    return find_project_mods(REPO_ROOT, explicit)


def parse_string_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.is_file():
        return keys
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def parse_string_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def fill_from_objectstrings(strings_path: Path, object_path: Path, keys: set[str], missing: list[str]) -> int:
    obj = parse_string_map(object_path)
    game = parse_string_map(strings_path)
    lines = []
    seen: set[str] = set()
    if strings_path.is_file():
        for line in strings_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip() or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key in seen:
                continue
            seen.add(key)
            lines.append(line.lstrip("\ufeff"))

    added = 0
    for key in missing:
        if key in obj:
            lines.append(f"{key}={obj[key]}")
            keys.add(key)
            added += 1
            continue
        if key.startswith("Button/Tooltip/"):
            btn_id = key.removeprefix("Button/Tooltip/")
            name_key = f"Button/Name/{btn_id}"
            if name_key in game:
                lines.append(f"{key}={game[name_key]}")
                keys.add(key)
                added += 1

    if added:
        lines = sorted(set(lines), key=lambda ln: ln.split("=", 1)[0] if "=" in ln else ln)
        strings_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig", newline="\n")
    return added


def audit_mod_localization(mod_dir: Path, fill: bool = False, locale: str = "enUS") -> list[str]:
    issues: list[str] = []
    game_data = mod_dir / "Base.SC2Data" / "GameData"
    strings_path = mod_dir / f"{locale}.SC2Data" / "LocalizedData" / "GameStrings.txt"
    object_path = mod_dir / f"{locale}.SC2Data" / "LocalizedData" / "ObjectStrings.txt"

    if not game_data.is_dir() or not strings_path.is_file():
        return issues

    keys = parse_string_keys(strings_path)
    refs: set[str] = set()

    for xml_file in game_data.glob("*.xml"):
        text = xml_file.read_text(encoding="utf-8", errors="replace")
        refs.update(extract_string_references(text))

    missing = sorted(ref for ref in refs if ref not in keys)
    if missing and fill:
        added = fill_from_objectstrings(strings_path, object_path, keys, missing)
        print(f"[{mod_dir.name}] Auto-filled {added} missing key(s) into GameStrings.txt.")
        missing = sorted(ref for ref in refs if ref not in keys)

    for m in missing:
        issues.append(f"[{mod_dir.name}] Missing GameStrings.txt anchor: {m}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fill", action="store_true", help="Auto-fill missing GameStrings from ObjectStrings")
    parser.add_argument("--mod-dir", help="Explicit path to .SC2Mod directory")
    parser.add_argument("--locale", default="enUS", choices=("enUS", "zhCN", "zhTW", "koKR", "deDE", "esES", "esMX", "frFR", "itIT", "plPL", "ptBR", "ruRU"), help="Localization directory to audit (default: enUS)")
    args = parser.parse_args()

    mods = find_local_mods(args.mod_dir)
    if not mods:
        print("ERROR: No .SC2Mod directory found to audit.")
        print("Pass --mod-dir or correct agent-config.json (SC2_MODS_PATH is a fallback).")
        return 2

    all_issues: list[str] = []
    audited_mods = 0
    for mod in mods:
        game_data = mod / "Base.SC2Data" / "GameData"
        strings_path = mod / f"{args.locale}.SC2Data" / "LocalizedData" / "GameStrings.txt"
        if not game_data.is_dir():
            all_issues.append(f"[{mod.name}] Missing Base.SC2Data/GameData directory.")
            continue
        if not strings_path.is_file():
            all_issues.append(f"[{mod.name}] Missing {args.locale} GameStrings.txt.")
            continue
        audited_mods += 1
        all_issues.extend(audit_mod_localization(mod, fill=args.fill, locale=args.locale))

    print("=" * 60)
    print("GAMESTRINGS ANCHOR AUDIT")
    print("=" * 60)
    print(f"Target: {mods[0]}")
    print(f"Audited mod directories: {audited_mods}")
    if all_issues:
        for issue in all_issues:
            print(f"  [MISSING STRING] {issue}")
        print(f"\nAudit completed with {len(all_issues)} missing string anchor(s).")
        return 1
    else:
        print("All GameData string anchors verified in GameStrings.txt.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
