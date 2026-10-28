#!/usr/bin/env python3
"""Report catalog Name/Tooltip/Description refs missing from GameStrings.txt."""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from sc2_paths import find_project_mods, load_project_config
from sc2_dependencies import build_dependency_graph, dependency_problems, resolve_dependency_root, RECURSION_DISABLED
from sc2_official import catalog_paths, component_file, cache_manifest
from sc2_components import component_path, require_editable, verify_archives, component_session

from sc2_i18n import UIArgumentParser, tr, run_cli

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
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return set(REF_RE.findall(text)) | set(EFFECT_SET_RE.findall(text))
    return catalog_string_references([(root, True)])


def catalog_string_references(documents) -> set[str]:
    """Resolve scalar text fields in dependency order; audit target objects.

    Audit explicit target anchors, target defaults and explicit parent fields.
    Implicit engine/dependency class defaults are outside the existing audit
    scope (many are optional editor names). Explicit nested refs retain scope.
    """
    definitions, defaults = {}, defaultdict(dict)
    targets, changed_defaults, refs = set(), set(), set()
    families = ('RequirementNode', 'ArmyCategory', 'Requirement', 'Footprint', 'Behavior',
                'Validator', 'Upgrade', 'Weapon', 'Turret', 'Button', 'Effect',
                'Actor', 'Model', 'Mover', 'Sound', 'Unit', 'Abil')
    def family(tag):
        return next((f for f in families if tag.startswith('C' + f)), tag)
    for root, is_target in documents:
        for entry in root:
            if not isinstance(entry.tag, str) or not entry.tag.startswith('C'):
                continue
            fam, oid = family(entry.tag), entry.get('id')
            fields = {c.tag: c.get('value') for c in entry if c.tag in ('Name', 'Tooltip', 'Description')}
            if entry.get('default') == '1' and not oid:
                if is_target and fields:
                    defaults[(fam, entry.tag)].update(fields)
                    changed_defaults.add(fam)
            elif oid:
                key = (fam, oid)
                record = definitions.setdefault(key, {'tag': entry.tag, 'fields': {}, 'parent': None})
                record['tag'] = entry.tag
                record['fields'].update(fields)
                if 'parent' in entry.attrib:
                    record['parent'] = entry.get('parent')
                if is_target and (fields or entry.get('parent')):
                    targets.add(key)
            if is_target:
                direct_fields = {id(c) for c in entry if c.tag in ('Name', 'Tooltip', 'Description')}
                for child in entry.iter():
                    if id(child) in direct_fields:
                        continue  # Scalar fields are audited after overrides/inheritance.
                    value = (child.get('value') if child.tag in ('Name', 'Tooltip', 'Description')
                             else child.get('Value') if child.tag == 'EffectArray' and child.get('Operation') == 'Set' else None)
                    if value and STRING_KEY_RE.fullmatch(value):
                        if oid:
                            refs.add(value.replace('##id##', oid))
                        elif '##' not in value:
                            refs.add(value)
    @lru_cache(maxsize=None)
    def effective(key, stack=()):
        if key in stack:
            raise ValueError('Localization inheritance cycle: ' + ':'.join(key))
        if key not in definitions:
            raise ValueError('Missing localization parent: ' + ':'.join(key))
        record = definitions[key]
        base_tag = key[0] if key[0].startswith('C') else 'C' + key[0]
        fields = dict(defaults.get((key[0], base_tag), {}))
        fields.update(defaults.get((key[0], record['tag']), {}))
        if record['parent']:
            fields.update(effective((key[0], record['parent']), stack + (key,)))
        fields.update(record['fields'])
        return fields
    targets.update(k for k in definitions if k[0] in changed_defaults)
    for key in targets:
        refs.update(v.replace('##id##', key[1]) for v in effective(key).values()
                    if v and STRING_KEY_RE.fullmatch(v))
    return refs


def localization_sources(mod_dir, mods_dir=None, campaigns_dir=None, official_cache=None):
    """Return confirmed active components and cache locale coverage."""
    if not (mod_dir / 'ComponentList.SC2Components').is_file() and not (mod_dir / 'DocumentInfo').is_file():
        return [(mod_dir, None)]  # Preserve standalone-directory audits.
    config = load_project_config(REPO_ROOT)
    if config.get('project', {}).get('resolve_dependencies_recursive') is False and mod_dir in find_project_mods(REPO_ROOT):
        raise ValueError(RECURSION_DISABLED)
    mods = resolve_dependency_root(REPO_ROOT, mod_dir, config, str(mods_dir) if mods_dir else None)
    graph = build_dependency_graph(mod_dir, mods, campaigns_dir=campaigns_dir,
                                   allow_unpacked=True, strict_external=True, official_cache=official_cache)
    problems = dependency_problems(graph)
    if problems:
        raise ValueError('; '.join(problems))
    sources, manifests = [], {}
    for key in graph['traversal_order']:
        node = graph['nodes'][key]
        root = component_path(node['path'])
        manifest = cache_manifest(root)
        metadata = None
        if manifest:
            if manifest not in manifests:
                manifests[manifest] = json.loads(manifest.read_text(encoding='utf-8'))
            data = manifests[manifest]
            logical = root.relative_to(manifest.parent).as_posix().lower()
            metadata = (manifest.parent, data['files'], data.get('locales', {}).get(logical, {}))
        sources.append((root, metadata))
    return sources


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
    require_editable(strings_path)
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


def audit_mod_localization(mod_dir: Path, fill: bool = False, locale: str = "enUS", *,
                           mods_dir=None, campaigns_dir=None, official_cache=None) -> list[str]:
    if fill:
        require_editable(mod_dir)
    mod_dir = component_path(mod_dir)
    issues: list[str] = []
    game_data = mod_dir / "Base.SC2Data" / "GameData"
    strings_path = mod_dir / f"{locale}.SC2Data" / "LocalizedData" / "GameStrings.txt"
    object_path = mod_dir / f"{locale}.SC2Data" / "LocalizedData" / "ObjectStrings.txt"

    if not game_data.is_dir() or not strings_path.is_file():
        return issues

    keys, unavailable = set(), []
    try:
        sources = localization_sources(mod_dir, mods_dir, campaigns_dir, official_cache)
        for root, metadata in sources:
            path = component_file(root, f'{locale}.SC2Data/LocalizedData/GameStrings.txt')
            if metadata:
                cache_root, files, coverage = metadata
                if coverage.get(locale) is not True:
                    unavailable.append(root.name)
                if path.is_file() and path.relative_to(cache_root).as_posix().lower() not in files:
                    raise ValueError('Unverified dependency localization input: ' + str(path))
            keys.update(parse_string_keys(path))
        def documents():
            for root, _metadata in sources:
                for path in catalog_paths(root):
                    yield ET.parse(path).getroot(), root == mod_dir
        refs = catalog_string_references(documents())
    except (OSError, ValueError, ET.ParseError) as exc:
        return [f'[{mod_dir.name}] Localization audit unconfirmed: {exc}']

    missing = sorted(ref for ref in refs if ref not in keys)
    templates = [ref for ref in missing if '##' in ref]
    if templates:
        return [f'[{mod_dir.name}] Unresolved localization template: {ref}' for ref in templates]
    if missing and unavailable:
        return [f'[{mod_dir.name}] Localization audit unconfirmed: {locale} dependency resources unavailable: '
                + ', '.join(unavailable) + f'; unresolved anchors: {len(missing)}']
    if missing and fill:
        added = fill_from_objectstrings(strings_path, object_path, keys, missing)
        print(tr('[{p0}] Auto-filled {p1} missing key(s) into GameStrings.txt.', p0=mod_dir.name, p1=added))
        missing = sorted(ref for ref in refs if ref not in keys)

    for m in missing:
        issues.append(f"[{mod_dir.name}] Missing GameStrings.txt anchor: {m}")

    return issues


@component_session
def main() -> int:
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument("--fill", action="store_true", help="Auto-fill missing GameStrings from ObjectStrings")
    parser.add_argument("--mod-dir", help="Explicit path to .SC2Mod directory")
    parser.add_argument('--mods-dir', type=Path, help='Dependency Mods root')
    parser.add_argument('--campaigns-dir', type=Path, help='Dependency Campaigns root')
    parser.add_argument('--official-cache', type=Path, help='Read-only build-bound official cache')
    parser.add_argument("--locale", default="enUS", choices=("enUS", "zhCN", "zhTW", "koKR", "deDE", "esES", "esMX", "frFR", "itIT", "plPL", "ptBR", "ruRU"), help="Localization directory to audit (default: enUS)")
    args = parser.parse_args()

    mods = find_local_mods(args.mod_dir)
    if not mods:
        print(tr('ERROR: No .SC2Mod directory found to audit.'))
        print(tr('Pass --mod-dir or correct agent-config.json (SC2_MODS_PATH is a fallback).'))
        return 2

    all_issues: list[str] = []
    audited_mods = 0
    for mod in mods:
        if args.fill:
            try:
                require_editable(mod)
            except ValueError as exc:
                parser.error(str(exc))
        game_data = mod / "Base.SC2Data" / "GameData"
        strings_path = mod / f"{args.locale}.SC2Data" / "LocalizedData" / "GameStrings.txt"
        if not game_data.is_dir():
            all_issues.append(f"[{mod.name}] Missing Base.SC2Data/GameData directory.")
            continue
        if not strings_path.is_file():
            all_issues.append(f"[{mod.name}] Missing {args.locale} GameStrings.txt.")
            continue
        audited_mods += 1
        all_issues.extend(audit_mod_localization(mod, fill=args.fill, locale=args.locale,
                         mods_dir=args.mods_dir, campaigns_dir=args.campaigns_dir, official_cache=args.official_cache))

    verify_archives()
    print("=" * 60)
    print(tr('GAMESTRINGS ANCHOR AUDIT'))
    print("=" * 60)
    print(tr('Target: {p0}', p0=mods[0]))
    print(tr('Audited mod directories: {p0}', p0=audited_mods))
    if all_issues:
        for issue in all_issues:
            label = '  [UNCONFIRMED] {p0}' if 'unconfirmed:' in issue or 'Unresolved localization template:' in issue else '  [MISSING STRING] {p0}'
            print(tr(label, p0=issue))
        print(tr('\nAudit completed with {p0} issue(s).', p0=len(all_issues)))
        return 1
    else:
        print(tr('All GameData string anchors verified in GameStrings.txt.'))
        return 0


if __name__ == "__main__":
    sys.exit(run_cli(main))
