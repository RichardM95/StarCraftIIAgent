"""Build-bound official CASC snapshots. Consumers never load CascLib or download."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import posixpath
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from sc2_casc import CascProcess, pe_bits, wanted
from sc2_components import component_path, component_exists

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'official-cache.json'
ASSESSMENT_VERSION = 3
# Comparison baseline from SC2EditorTool; candidates, never an engine load rule.
TOOLBOX_CATALOG_FAMILIES = (
    'HeroAbil', 'HeroStat', 'ArtifactSlot', 'Artifact', 'RequirementNode', 'AchievementTerm', 'ConversationState',
    'TargetFind', 'TargetSort', 'ScoreValue', 'ScoreResult', 'ItemClass', 'ArmyCategory', 'ArmyUnit', 'ArmyUpgrade',
    'DataCollection', 'AttachMethod', 'Abil', 'Unit', 'Weapon', 'Effect', 'Behavior', 'Actor', 'Model', 'Button',
    'Upgrade', 'Requirement', 'Validator', 'Mover', 'Turret', 'Footprint', 'Sound', 'Camera', 'Race', 'Talent',
    'Hero', 'Item', 'Campaign', 'Commander', 'User', 'Skin', 'Achievement', 'Accumulator', 'Ping', 'Tactical',
    'Kinetic', 'Loot', 'Reward', 'Conversation', 'Character', 'BankCondition', 'Config', 'Texture', 'GameUI')


def file_digest(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def identity(install: Path) -> dict:
    install = install.resolve()
    raw = (install / '.build.info').read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter='|'))
    active = [r for r in rows if next((v for k, v in r.items() if isinstance(k, str) and k.startswith('Active!')), '') == '1']
    if len(active) != 1:
        raise ValueError('Expected exactly one active SC2 build in .build.info')
    def value(name):
        return next((v for k, v in active[0].items() if isinstance(k, str) and k.startswith(name + '!')), '')
    build = value('Build Key')
    if not re.fullmatch('[0-9a-fA-F]{32}', build):
        raise ValueError('Invalid active Build Key')
    return {'install': str(install), 'install_id': hashlib.sha256(str(install).casefold().encode()).hexdigest()[:16],
            'build_key': build.lower(), 'version': value('Version'), 'branch': value('Branch'),
            'build_info_sha256': hashlib.sha256(raw).hexdigest()}


def default_cache(install: Path) -> Path:
    info = identity(install)
    return ROOT.with_name(ROOT.name + '-data') / 'reference/casc' / info['install_id'] / info['build_key']


def safe_path(root: Path, relative: str) -> Path:
    relative = relative.replace('\\', '/')
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or any(p in {'.', '..'} or ':' in p for p in parts.parts):
        raise ValueError('Unsafe cache path: ' + relative)
    result = root.joinpath(*parts.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Cache path escapes its root: ' + relative)
    return result


def component_file(component: Path, relative: str) -> Path:
    component = component_path(component)
    safe_path(component, relative)
    current = component
    for part in relative.replace('\\', '/').split('/'):
        matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()] if current.is_dir() else []
        if len(matches) > 1:
            raise ValueError('Ambiguous component path: ' + relative)
        current = matches[0] if matches else current / part
    return current


def cache_manifest(component: Path) -> Path | None:
    return next((p / MANIFEST for p in component.parents if (p / MANIFEST).is_file()), None)


def catalog_closure(names: set[str], xml_for, *, standard_paths=()) -> list[str]:
    """One registration/closure rule for both a snapshot and its Catalog consumer."""
    base, entry = 'base.sc2data/', 'base.sc2data/gamedata.xml'
    standards = [n for n in standard_paths if n in names]
    for name in standards:
        if xml_for(name).tag != 'Catalog':
            raise ValueError('Unsupported GameData root: ' + name)
    if entry not in names:
        if standards:
            return standards
        listing = 'componentlist.sc2components'
        has_xml = any(n.startswith(base + 'gamedata/') and n.endswith('.xml') for n in names)
        if has_xml:
            raise ValueError('GameData XML exists without its GameData.xml loading entry')
        if listing not in names:
            raise ValueError('GameData absence is unconfirmed: no original component registration')
        root = xml_for(listing)
        if (root.tag != 'Components' or any(e.tag != 'DataComponent' or e.get('Type') not in
                {'info', 'trig', 'text'} for e in root)):
            raise ValueError('GameData loading entry missing or component registration unsupported')
        return []
    pending, seen, active, catalogs = [(entry, False)], set(standards), set(), list(standards)
    while pending:
        name, exiting = pending.pop()
        if exiting:
            active.remove(name)
            continue
        if name in active:
            raise ValueError('Cyclic GameData include: ' + name)
        if name in seen:
            continue
        seen.add(name)
        active.add(name)
        pending.append((name, True))
        if name not in names:
            raise ValueError('Missing GameData include: ' + name)
        root = xml_for(name)
        if root.tag == 'Catalog':
            catalogs.append(name)
        elif root.tag == 'Includes':
            children = []
            for child in root:
                if child.tag != 'Catalog' or not child.get('path', '').strip():
                    raise ValueError('Unsupported GameData include: ' + name)
                relative = child.get('path').replace('\\', '/').lower().strip()
                if PurePosixPath(relative).is_absolute():
                    raise ValueError('Unsafe cache path: ' + relative)
                relative = posixpath.normpath(posixpath.join(posixpath.dirname(name), relative))
                safe_path(Path('/snapshot').resolve(), relative)
                children.append((relative, False))
            pending.extend(reversed(children))
        else:
            raise ValueError('Unsupported GameData root: ' + name)
    return catalogs


def validation_tree(raw: bytes, name: str) -> ET.Element:
    root = ET.fromstring(raw)
    # Closure validation needs Catalog/definition root types, not their large bodies.
    if root.tag == 'Catalog' or name.endswith(('/triggers', '.triggerlib', '.sc2lib')):
        return ET.Element(root.tag, {'_entry_count': str(len(root))})
    return root


def catalog_paths(component: Path, *, research=False, manifest_data=None, registration=None) -> list[Path]:
    """Official sources need load evidence; retain the local mod scan scope."""
    manifest = cache_manifest(component)
    if manifest is None:
        return sorted((component_path(component) / 'Base.SC2Data/GameData').glob('*.xml'))
    data = manifest_data if manifest_data is not None else json.loads(manifest.read_text(encoding='utf-8'))
    logical = component.resolve().relative_to(manifest.parent.resolve()).as_posix()
    if research:
        # Availability is sufficient for reference navigation, never active loading.
        return [safe_path(manifest.parent, name) for name in data['files']
                if name.startswith(logical + '/base.sc2data/') and name.endswith('.xml')
                and '/triggerlibs/' not in name]
    # Active collection must use the same hashed inventory as research/validation.
    # A file dropped beside the cache is not a verified official provider.
    candidates = {name[len(logical) + 1:]: safe_path(manifest.parent, name)
                  for name in data['files'] if name.startswith(logical + '/') and (
                      name.startswith(logical + '/base.sc2data/gamedata/') and name.endswith('.xml')
                      or name in {logical + '/base.sc2data/gamedata.xml', logical + '/componentlist.sc2components'})}
    if registration is None:
        from sc2_engine_dependencies import catalog_registration
        registration = catalog_registration(Path(data['identity']['install']), data['identity'], data['engine']) if data.get('engine') else None
    standard_paths = registration['catalogs'] if registration and registration.get('source_scope') == 'confirmed' else ()
    closure = catalog_closure(set(candidates), lambda n: ET.parse(candidates[n]).getroot(), standard_paths=standard_paths)
    extra = {n for n in candidates if '/gamedata/' in n and ET.parse(candidates[n]).getroot().tag == 'Catalog'} - set(closure)
    if registration and registration.get('source_scope') == 'confirmed':
        extra = {n for n in extra if len(ET.parse(candidates[n]).getroot())}
    if extra:
        raise ValueError('GameData loading unconfirmed for unregistered catalogs: ' + ', '.join(sorted(extra)))
    return [candidates[n] for n in closure]


def verify_closure(files: dict[str, bytes], logical: str, parsed: dict | None = None, *, catalogs=True) -> None:
    """Verify original registrations; parsed XML is reused within this operation."""
    parsed = {} if parsed is None else parsed
    prefix = logical + '/'
    names = {key[len(prefix):] for key in files if key.startswith(prefix)}
    def xml_for(name):
        key = prefix + name
        if key not in parsed:
            parsed[key] = ET.fromstring(files[key])
        return parsed[key]
    if catalogs:
        catalog_closure(names, xml_for)
    component_list = 'componentlist.sc2components'
    if component_list in names:
        for entry in xml_for(component_list).findall('DataComponent'):
            if entry.get('Type') in {'info', 'trig'}:
                relative = (entry.text or '').strip().replace('\\', '/').lower()
                safe_path(Path('/snapshot').resolve(), relative)
                if relative not in names:
                    raise ValueError('Missing registered component: ' + logical + '/' + relative)
    listing = 'base.sc2data/triggerlibs/librarylist.xml'
    if listing in names:
        for entry in xml_for(listing):
            external = entry.get('external')
            if not external:
                raise ValueError('Unsupported inline library registration: ' + listing)
            stem = 'base.sc2data/' + external.replace('\\', '/').lower()
            safe_path(Path('/snapshot').resolve(), stem)
            if sum(stem + ext in names for ext in ('.triggerlib', '.sc2lib')) != 1:
                raise ValueError('Missing/ambiguous registered library: ' + stem)


def assess_component(files: dict[str, bytes], logical: str, parsed: dict, metadata: dict, *, bootstrap=None, registration=None, dependency_rule=None) -> dict:
    """Separate validated bytes, registration, candidate catalogs and load evidence."""
    prefix = logical + '/'
    names = {k[len(prefix):] for k in files if k.startswith(prefix)}
    def xml_for(name):
        key = prefix + name
        if key not in parsed:
            parsed[key] = validation_tree(files[key], key)
        return parsed[key]
    available = sorted(n for n in names if n.startswith('base.sc2data/') and n.endswith('.xml')
                       and '/triggerlibs/' not in n and xml_for(n).tag == 'Catalog')
    hard, unknown, registered = [], [], []
    try:
        verify_closure(files, logical, parsed, catalogs=False)
    except ValueError as exc:
        hard.append(str(exc))
    catalog_hard_start = len(hard)
    try:
        standard_paths = registration['catalogs'] if registration and registration.get('source_scope') == 'confirmed' else ()
        registered = catalog_closure(names, xml_for, standard_paths=standard_paths)
    except ValueError as exc:
        if str(exc).startswith(('Missing GameData include:', 'Unsafe cache path:', 'Cache path escapes',
                                'Cyclic GameData include:', 'Unsupported GameData include:', 'Unsupported GameData root:')):
            hard.append(str(exc))
        else:
            unknown.append('GameData loading unconfirmed: ' + str(exc))
    unregistered = sorted(set(available) - set(registered))
    empty_unregistered = [n for n in unregistered if not int(xml_for(n).get('_entry_count', len(xml_for(n))))]
    affecting = sorted(set(unregistered) - set(empty_unregistered)) if registration and registration.get('source_scope') == 'confirmed' else unregistered
    unclassified = sorted(n for n in names if n.startswith('base.sc2data/gamedata/') and n.endswith('.xml')
                          and xml_for(n).tag not in {'Catalog', 'Includes'})
    if unclassified:
        unknown.append(f'Unclassified GameData XML ({len(unclassified)} files); see unclassified_files')
    if affecting:
        unknown.append(f'GameData standard/unregistered catalog loading unconfirmed ({len(affecting)} catalogs; see reference_catalogs)')
    loading = 'unconfirmed' if hard[catalog_hard_start:] or unknown else 'confirmed' if available else 'not_applicable'
    evidence = metadata.get('dependency_evidence')
    relation = 'locale_chain' if isinstance(evidence, dict) and evidence.get('kind') in {'engine_table', 'engine_locale_table'} else (
        'bootstrap' if isinstance(evidence, dict) and evidence.get('kind') in {'engine_bootstrap', 'sc2_core_base'} else (
        'research_only' if isinstance(evidence, dict) and evidence.get('kind') == 'research_only' else 'declared'))
    if bootstrap and logical in bootstrap['roots'] and relation == 'research_only':
        relation = 'bootstrap'
    if relation == 'locale_chain' and dependency_rule and logical not in dependency_rule['excluded_components']:
        relation = 'engine_dependency_chain'
    if relation not in {'declared', 'bootstrap', 'engine_dependency_chain'}:
        unknown.append('Dependency loading unconfirmed: ' + relation + ' evidence is not a complete active dependency graph')
    baseline = {'base.sc2data/gamedata/' + f.lower() + 'data.xml' for f in TOOLBOX_CATALOG_FAMILIES}
    baseline.add('base.sc2data/gamedata/sc2data.xml')
    candidates = [n for n in available if n.endswith('data.xml')]
    return {'version': ASSESSMENT_VERSION, 'availability': 'verified',
            'dependency_resolution': 'confirmed' if relation in {'declared', 'bootstrap', 'engine_dependency_chain'} else 'unconfirmed',
            'dependency_relation': relation, 'catalog_loading': loading,
            'bootstrap_loading': 'confirmed' if bootstrap else 'unconfirmed',
            'registered_catalogs': registered, 'standard_candidates': candidates,
            'candidate_baseline': 'SC2EditorTool:FAMILIES:54',
            'additional_standard_candidates': sorted(set(candidates) - baseline),
            'engine_registered_catalogs': [n for n in available if registration and n in registration['catalogs']],
            'empty_unregistered_catalogs': empty_unregistered,
            'nonempty_catalogs': [n for n in available if int(xml_for(n).get('_entry_count', len(xml_for(n)))) > 0],
            'reference_catalogs': available, 'hard_problems': hard, 'unconfirmed': unknown,
            'unclassified_files': unclassified,
            'closure': 'incomplete' if hard or unknown else 'complete', 'problems': hard + unknown,
            'loading_rule': ({'kind': 'standard_catalog_sources', 'engine_sha256': registration['engine_sha256'],
                              'source_scope': 'confirmed', 'file_merge_order': 'unconfirmed'}
                             if registration and registration.get('source_scope') == 'confirmed' else None)}


class OfficialCache:
    def __init__(self, root: Path, install: Path, *, allow_partial=False):
        self.root = root.resolve()
        self.manifest_path = self.root / MANIFEST
        self.data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.identity = identity(install)
        if not isinstance(self.data, dict) or self.data.get('version') not in (1, 2, 3) or self.data.get('identity') != self.identity:
            raise ValueError('Official cache belongs to another installation/build or needs rebuilding')
        self.partial = self.data.get('status') == 'partial'
        if (self.partial and (not allow_partial or self.data.get('version') not in (2, 3))
                or self.data.get('status') not in ('complete', 'partial')
                or not self.partial and self.data.get('problems')):
            raise ValueError('Official cache is incomplete; cannot certify active dependencies')
        if self.partial and (not self.data.get('problems') or self.data.get('extraction_phase') != 'payload'):
            raise ValueError('Partial cache must retain problems and extracted payload')
        if self.data.get('version') in (2, 3) and self.data.get('loading_status') != ('unconfirmed' if self.partial else 'confirmed'):
            raise ValueError('Official cache loading status is inconsistent')
        files = self.data.get('files')
        components = self.data.get('components')
        if not isinstance(files, dict) or not isinstance(components, dict) or not components:
            raise ValueError('Invalid official cache inventory')
        states = self.data.get('file_states', {})
        if not isinstance(states, dict):
            raise ValueError('Invalid official cache file states')
        for name, state in states.items():
            safe_path(self.root, name)
            if not isinstance(state, str) or state not in {'readable', 'unavailable', 'not_attempted'}:
                raise ValueError('Invalid official cache file state: ' + name)
            if state == 'readable' and name not in files:
                raise ValueError('Cache inventory omits readable GameData/metadata file: ' + name)
        engine = self.data.get('engine')
        bootstrap = None
        self.registration = None
        self.dependency_rule = None
        if engine:
            from sc2_engine_dependencies import engine_registry, bootstrap_registry, catalog_registration, dependency_chain_rule
            try:
                verified = engine_registry(install, self.identity['version'])
                if verified != engine:
                    raise ValueError('Engine dependency source changed')
                bootstrap = bootstrap_registry(install, self.identity, verified)
                self.registration = catalog_registration(install, self.identity, verified)
                self.dependency_rule = dependency_chain_rule(verified)
            except (OSError, ValueError) as exc:
                raise ValueError('Core/bootstrap completeness cannot be verified: ' + str(exc)) from exc
            if ((self.data.get('bootstrap') is not None and self.data['bootstrap'] != bootstrap)
                    or not self.partial and not bootstrap):
                raise ValueError('Engine table alone does not establish Core/bootstrap completeness')
        elif self.data.get('bootstrap'):
            raise ValueError('Bootstrap evidence has no verified engine')
        raw_files, parsed = {}, {}
        for relative, entry in files.items():
            path = safe_path(self.root, relative)
            if not isinstance(entry, dict):
                raise ValueError('Invalid official file inventory entry: ' + relative)
            raw = path.read_bytes()
            raw_files[relative] = raw
            if (relative != relative.lower() or not wanted(relative) or hashlib.sha256(raw).hexdigest() != entry['sha256']
                    or path.stat().st_size != entry.get('size')
                    or entry.get('casc_path', '').replace('\\', '/').lower() != relative):
                raise ValueError('Missing, damaged or disallowed official cache input: ' + relative)
            if path.suffix in {'.xml', '.triggerlib', '.sc2lib', '.sc2components'} or path.name == 'triggers':
                parsed[relative] = validation_tree(raw, relative)
        self.assessments = {}
        self.dependency_ordinals = {}
        self.bootstrap = bootstrap
        for relative, entry in components.items():
            safe_path(self.root, relative)
            if not isinstance(entry, dict):
                raise ValueError('Invalid component metadata: ' + relative)
            if not self.partial and entry.get('scope') == 'research_only':
                raise ValueError('Research-only source cannot certify active loading')
            evidence = entry.get('dependency_evidence')
            if isinstance(evidence, str) and evidence in files and evidence.startswith(relative + '/'):
                listing = relative + '/componentlist.sc2components'
                if listing in parsed:
                    registered = next((e.text.strip().replace('\\', '/').lower()
                                       for e in parsed[listing].findall('DataComponent')
                                       if e.get('Type') == 'info' and e.text and e.text.strip()), None)
                    if parsed[listing].tag != 'Components' or evidence != relative + '/' + (registered or ''):
                        raise ValueError('Dependency evidence differs from original info registration: ' + relative)
                if evidence not in parsed:
                    text = raw_files[evidence].decode('utf-8-sig')
                    parsed[evidence] = (ET.fromstring(text) if re.sub(r'^\s*<\?xml[^?]*\?>', '', text, count=1).strip()
                                        else ET.Element('DocInfo'))
                dependencies = dependency_values(raw_files[evidence], parsed[evidence])
                self.dependency_ordinals[relative] = [i for i, value in enumerate(parsed[evidence].findall('./Dependencies/Value'))
                                                     if value.text and value.text.strip()]
            elif isinstance(evidence, dict) and evidence.get('kind') in {'engine_table', 'engine_locale_table'} and engine:
                if evidence != {'kind': evidence['kind'], 'row_offset': engine['rows'].get(relative)} or relative not in engine['dependencies']:
                    raise ValueError('Unverified engine dependency row: ' + relative)
                dependencies = ['file:' + p for p in engine['dependencies'][relative]]
            elif bootstrap and evidence in ({'kind': 'engine_bootstrap', 'root': relative},
                                             {'kind': bootstrap['kind'], 'root': relative}) and relative in bootstrap['roots']:
                dependencies = ['file:' + p for p in bootstrap['dependencies'][relative]]
            elif self.partial and evidence == {'kind': 'research_only'} and entry.get('scope') == 'research_only':
                dependencies = []
            else:
                raise ValueError('Component dependency evidence missing: ' + relative)
            locale_entry = isinstance(evidence, dict) and evidence.get('kind') in {'engine_table', 'engine_locale_table'}
            if (locale_entry and self.data['version'] == 3 and
                    (dependencies != entry.get('locale_dependencies') or entry.get('dependencies') != [])):
                raise ValueError('Locale dependency metadata differs from cache manifest: ' + relative)
            if not (locale_entry and self.data['version'] == 3) and dependencies != entry.get('dependencies'):
                raise ValueError('Component metadata differs from cache manifest: ' + relative)
            self.assessments[relative] = assess_component(raw_files, relative, parsed, entry,
                                                         bootstrap=bootstrap, registration=self.registration,
                                                         dependency_rule=self.dependency_rule)
            stored = entry.get('assessment')
            if self.data.get('version') == 3 and (not isinstance(stored, dict) or stored.get('version') not in (1, 2, ASSESSMENT_VERSION)):
                raise ValueError('Unsupported component assessment version: ' + relative)
            if self.data.get('version') == 3 and stored['version'] == ASSESSMENT_VERSION and stored != self.assessments[relative]:
                raise ValueError('Component closure assessment differs from payload: ' + relative + ': '
                                 + '; '.join(self.assessments[relative]['problems']))
        if (self.data.get('version') == 3 and any(e.get('assessment', {}).get('version') == ASSESSMENT_VERSION
                                                for e in components.values())
                and (self.data.get('loading_rules') or {}).get('catalog_registration') != self.registration):
            raise ValueError('Catalog registration evidence differs from this build')
        if not self.partial:
            for relative, entry in components.items():
                for raw in entry['dependencies']:
                    from sc2_dependencies import extract_dependency_refs
                    for ref in extract_dependency_refs(raw):
                        key = (ref.get('file_path') or '').replace('\\', '/').lower()
                        if key and key not in components and key not in self.data.get('local_components', []):
                            raise ValueError('Incomplete cached dependency closure: ' + key)
            if bootstrap and any(r not in components for r in bootstrap['roots']):
                raise ValueError('Missing bootstrap root payload')
        self.hard_problems = [f'{k}: {p}' for k, v in self.assessments.items() for p in v['hard_problems']]
        for name in self.data.get('unavailable_files', {}):
            safe_path(self.root, name)
            if '/enus.sc2data/' not in name and '/zhcn.sc2data/' not in name:
                self.hard_problems.append('Official file unavailable: ' + name)
        self.unconfirmed = [f'{k}: {p}' for k, v in self.assessments.items() for p in v['unconfirmed']]
        self.global_unconfirmed = []
        if engine and not bootstrap:
            self.unconfirmed.append('Core/bootstrap loading unconfirmed for the current build')
        old_policy = self.data['version'] < 3 or any(e.get('assessment', {}).get('version', 0) < ASSESSMENT_VERSION for e in components.values())
        reevaluated = old_policy and self.bootstrap and self.bootstrap.get('kind') == 'sc2_core_base' and self.registration and self.registration.get('source_scope') == 'confirmed'
        if self.partial and not self.hard_problems and not self.unconfirmed and not reevaluated:
            self.global_unconfirmed.append('Legacy partial cache diagnostics need confirmation: ' + '; '.join(self.data['problems']))
            self.unconfirmed.extend(self.global_unconfirmed)
        self.partial = (self.partial and not reevaluated) or bool(self.hard_problems or self.unconfirmed)
        if self.partial and not allow_partial:
            raise ValueError('Official loading incomplete: ' + '; '.join(self.hard_problems + self.unconfirmed))

    def component(self, logical: str) -> Path | None:
        key = logical.replace('\\', '/').lower()
        entry = self.data['components'].get(key)
        return safe_path(self.root, key) if entry else None

    def research_components(self):
        return [safe_path(self.root, key) for key, value in self.data['components'].items()
                if value.get('scope') == 'research_only']

    def metadata(self, component: Path) -> dict:
        key = component.resolve().relative_to(self.root).as_posix()
        value = {**self.data['components'][key], 'assessment': self.assessments[key]}
        if (self.bootstrap and key in self.bootstrap['roots']
                and value.get('dependency_evidence') == {'kind': 'research_only'}):
            value.update(scope='declared_dependency', dependencies=[],
                         dependency_evidence={'kind': self.bootstrap['kind'], 'source': self.bootstrap['source']})
        if key in self.dependency_ordinals:
            value['dependency_ordinals'] = self.dependency_ordinals[key]
        if (self.data['version'] < 3 and isinstance(value.get('dependency_evidence'), dict)
                and value['dependency_evidence'].get('kind') in {'engine_table', 'engine_locale_table'}):
            value['locale_dependencies'], value['dependencies'] = value['dependencies'], []
        if self.assessments[key]['dependency_relation'] == 'engine_dependency_chain':
            value.update(source_dependency_evidence=value['dependency_evidence'],
                         dependency_evidence={'kind': 'sc2_builtin_dependency_chain', 'rule': self.dependency_rule},
                         dependencies=value.get('locale_dependencies', []), locale_dependencies=[])
        inventory = self.data.get('file_states', {})
        if not isinstance(inventory, dict):
            inventory = {}
        entries = [n for n in inventory if n.startswith(key + '/')]
        component_files = [n for n in self.data['files'] if n.startswith(key + '/')]
        trigger_inputs = [n for n in [*entries, *component_files] if n.endswith(('/triggers', '/librarylist.xml', '.sc2lib', '.triggerlib'))]
        if ('library_registration' in value and value['library_registration'] is None and entries
                and all(inventory[n] in {'readable', 'unavailable', 'not_attempted'} for n in entries)
                and all(n in inventory for n in component_files)
                and not trigger_inputs and self.assessments[key]['dependency_resolution'] == 'confirmed'):
            value['trigger_registration'] = {'status': 'absent', 'basis': 'casc_enumeration',
                                             'manifest': str(self.manifest_path)}
        return value


def cache_for_mods(mods: Path, explicit: Path | None = None, *, allow_partial=False, research=False) -> OfficialCache | None:
    # A Mods root identifies its own installation; never borrow configured paths here.
    install = mods.resolve().parent
    if allow_partial and explicit is None and not research:
        raise ValueError('Partial official cache requires an explicit --official-cache path')
    if not (install / '.build.info').is_file():
        if explicit is not None:
            raise ValueError('Cannot bind official cache without the dependency installation .build.info')
        return None
    root = Path(explicit).resolve() if explicit is not None else default_cache(install)
    if not (root / MANIFEST).is_file() and explicit is None:
        partial = root.with_name(root.name + '-partial')
        if not research or not (partial / MANIFEST).is_file():
            return None
        root = partial
    return OfficialCache(root, install, allow_partial=allow_partial or research)


def dependency_values(raw: bytes, root: ET.Element | None = None) -> list[str]:
    text = raw.decode('utf-8-sig')
    if not re.sub(r'^\s*<\?xml[^?]*\?>', '', text, count=1).strip():
        return []
    root = ET.fromstring(text) if root is None else root
    if root.tag not in {'DocInfo', 'DocumentInfo', 'DocHeader', 'DocumentHeader'}:
        raise ValueError('Unsupported official dependency metadata root: ' + root.tag)
    return [e.text.strip() for e in root.findall('./Dependencies/Value') if e.text and e.text.strip()]


def probe(install: Path, dll: Path, timeout=60) -> dict:
    result = {'identity': identity(install), 'dll': str(dll.resolve()), 'dll_sha256': file_digest(dll),
              'dll_bits': pe_bits(dll), 'attempts': [], 'status': 'failed',
              'layout': {'sc2data': (install / 'SC2Data').is_dir(), 'versions': (install / 'Versions').is_dir()},
              'interfaces': ['CascOpenStorage', 'CascOpenFile', 'CascGetFileSize64', 'CascReadFile',
                             'CascFindFirstFile', 'CascFindNextFile', 'CascFindClose',
                             'CascCloseFile', 'CascCloseStorage']}
    metadata = ['mods/core.sc2mod/base.sc2data/triggerlibs/librarylist.xml',
                'campaigns/void.sc2campaign/DocumentInfo', 'mods/core.sc2mod/DocumentInfo',
                'mods/core.sc2mod/StandardInfo']
    definitions = ['mods/core.sc2mod/base.sc2data/TriggerLibs/NativeLib.TriggerLib',
                   'mods/core.sc2mod/base.sc2data/GameData/UnitData.xml']
    for encoding in ('ansi', 'unicode'):
        attempt = {'encoding': encoding, 'samples': []}
        result['attempts'].append(attempt)
        try:
            with CascProcess(dll, install, encoding, timeout) as reader:
                for kind, paths in (('metadata', metadata), ('definition', definitions)):
                    for path in paths:
                        raw = reader.read(path)
                        if raw:
                            parsed = ET.fromstring(raw)
                            attempt['samples'].append({'kind': kind, 'path': path, 'bytes': len(raw),
                                                       'xml_root': parsed.tag,
                                                       'sha256': hashlib.sha256(raw).hexdigest()})
                            break
                    else:
                        raise ValueError('No readable XML sample for ' + kind)
            result.update(status='read_verified', encoding=encoding)
            break
        except (ValueError, OSError, ET.ParseError) as exc:
            attempt['error'] = str(exc)
    return result


def snapshot(reader, target: Path, mods: Path, *, allow_partial=False) -> tuple[dict, dict[str, bytes]]:
    """Resolve original dependency metadata before reading the component payload."""
    from sc2_dependencies import build_dependency_graph, extract_dependency_refs
    pending, problems, scanned = [], [], set()
    engine, engine_error, engine_checked, used_engine = None, None, False, False
    bootstrap, bootstrap_checked = None, False
    local_components = set()
    def scan_local(component):
        if component in scanned:
            return
        scanned.add(component)
        if component.is_relative_to(mods.parent):
            local_components.add(component.relative_to(mods.parent).as_posix().lower())
        graph = build_dependency_graph(component, mods, official_cache=False)
        problems.extend(graph['errors'])
        for edge in graph['edges']:
            if edge.get('file_path') and not edge.get('exists'):
                pending.append(edge['file_path'].replace('\\', '/').lower())
            elif edge.get('kind') == 'external' and not edge.get('file_path'):
                problems.append('Unmapped network dependency: ' + edge['raw'])
    scan_local(target)
    names, grouped = {}, {}
    for name in reader.names():
        key = name.replace('\\', '/').lower()
        if key in names and names[key] != name:
            raise ValueError('Ambiguous CASC filename casing: ' + key)
        if wanted(key):
            safe_path(Path('/snapshot').resolve(), key)
            names[key] = name
            parts = key.split('/')
            end = next(i for i, p in enumerate(parts) if p.endswith(('.sc2mod', '.sc2campaign')))
            logical = '/'.join(parts[:end + 1])
            grouped.setdefault(logical, []).append(key)
    components, files, unavailable, parsed = {}, {}, {}, {}
    attempted, visited, info_files = set(), set(), set()
    def read_file(key):
        if key not in names or key in attempted:
            return files.get(key)
        attempted.add(key)
        try:
            raw = reader.read(names[key])
        except (OSError, ValueError) as exc:
            raw = None
            unavailable[key] = str(exc)
        if raw is None:
            unavailable.setdefault(key, 'CASC file not locally readable')
            if '/enus.sc2data/' not in key and '/zhcn.sc2data/' not in key:
                problems.append('CASC file not locally readable: ' + key)
        else:
            files[key] = raw
        return raw
    def xml_for(key):
        if key not in parsed:
            parsed[key] = validation_tree(files[key], key)
        return parsed[key]
    def result(phase):
        return {'components': components, 'problems': sorted(set(problems)),
                'unavailable_files': unavailable, 'source_paths': {k: names[k] for k in files},
                'engine': engine if used_engine else None, 'engine_diagnostic': engine_error,
                'bootstrap': bootstrap, 'local_components': sorted(local_components),
                'file_states': {k: 'unavailable' if k in unavailable else 'readable' if k in files else 'not_attempted'
                                for logical in components for k in grouped.get(logical, [])},
                'loading_status': 'unconfirmed' if problems else 'confirmed',
                'extraction_phase': phase, 'status': 'partial' if problems else 'complete'}, files
    while pending or used_engine and not bootstrap_checked:
        if not pending:
            bootstrap_checked = True
            from sc2_engine_dependencies import bootstrap_registry
            try:
                bootstrap = bootstrap_registry(mods.parent, identity(mods.parent), engine)
            except (OSError, ValueError) as exc:
                problems.append('Core/bootstrap evidence rejected: ' + str(exc))
            if bootstrap:
                pending.extend(bootstrap['roots'])
            else:
                problems.append('Engine table does not prove implicit Core/bootstrap loading; complete active graph remains unconfirmed')
                if allow_partial and 'mods/core.sc2mod' in grouped and 'mods/core.sc2mod' not in visited:
                    # Explicit research source, never an inferred active dependency.
                    components['mods/core.sc2mod'] = {'scope': 'research_only',
                        'dependency_evidence': {'kind': 'research_only'}, 'dependencies': [],
                        'library_registration': 'mods/core.sc2mod/base.sc2data/triggerlibs/librarylist.xml'}
            continue
        logical = pending.pop(0)
        safe_path(Path('/snapshot').resolve(), logical)
        if logical in visited:
            continue
        visited.add(logical)
        if logical not in grouped:
            problems.append('Official component not present in CASC: ' + logical)
            continue
        components[logical] = {'scope': 'research_only', 'dependency_evidence': {'kind': 'research_only'}, 'dependencies': []}
        listing, evidence = logical + '/componentlist.sc2components', logical + '/documentinfo'
        try:
            if listing in names:
                if read_file(listing) is None:
                    continue
                root = xml_for(listing)
                if root.tag != 'Components':
                    raise ValueError('Unsupported component registration: ' + logical)
                info = next((e.text for e in root.findall('DataComponent') if e.get('Type') == 'info' and e.text), None)
                if not info:
                    raise ValueError('Component list has no info registration: ' + logical)
                evidence = logical + '/' + info.replace('\\', '/').strip().lower()
                safe_path(Path('/snapshot').resolve(), evidence)
            if evidence in names:
                raw = read_file(evidence)
                if raw is None:
                    continue
                deps = dependency_values(raw)
                info_files.add(evidence)
            elif listing not in names:
                if bootstrap and logical in bootstrap['roots']:
                    deps = ['file:' + p for p in bootstrap['dependencies'][logical]]
                    evidence = {'kind': bootstrap['kind'], 'root': logical}
                    registration = logical + '/base.sc2data/triggerlibs/librarylist.xml'
                    components[logical] = {'dependency_evidence': evidence, 'dependencies': deps,
                        'library_registration': registration if registration in names else None,
                        'scope': 'declared_dependency'}
                    pending.extend(bootstrap['dependencies'][logical])
                    continue
                if not engine_checked:
                    engine_checked = True
                    try:
                        from sc2_engine_dependencies import engine_registry
                        engine = engine_registry(mods.parent, identity(mods.parent)['version'])
                    except (OSError, ValueError) as exc:
                        engine_error = str(exc)
                if not engine or logical not in engine['dependencies']:
                    raise ValueError('No supported, original dependency metadata for ' + logical)
                deps = ['file:' + p for p in engine['dependencies'][logical]]
                evidence = {'kind': 'engine_locale_table', 'row_offset': engine['rows'][logical]}
                used_engine = True
            else:
                raise ValueError('No supported, original dependency metadata for ' + logical)
        except (ValueError, ET.ParseError) as exc:
            problems.append(str(exc))
            continue
        registration = logical + '/base.sc2data/triggerlibs/librarylist.xml'
        components[logical] = {'dependency_evidence': evidence, 'dependencies': deps,
                              'library_registration': registration if registration in names else None,
                              'scope': 'declared_dependency'}
        if isinstance(evidence, dict) and evidence.get('kind') == 'engine_locale_table':
            components[logical]['locale_dependencies'], components[logical]['dependencies'] = deps, []
        for raw in deps:
            for ref in extract_dependency_refs(raw):
                path = ref.get('file_path')
                if not path:
                    problems.append('Unmapped official dependency: ' + raw)
                elif path.lower().startswith(('mods/', 'campaigns/')):
                    safe_path(mods.parent, path)
                    local = mods.parent.joinpath(*PurePosixPath(path).parts)
                    if not component_exists(local):
                        pending.append(path.lower())
                    else:
                        scan_local(local)
                else:
                    problems.append('Unsupported dependency path: ' + raw)
    if problems and not allow_partial:
        return result('metadata')
    if allow_partial and problems and 'mods/core.sc2mod' in grouped and 'mods/core.sc2mod' not in components:
        components['mods/core.sc2mod'] = {'scope': 'research_only',
            'dependency_evidence': {'kind': 'research_only'}, 'dependencies': [],
            'library_registration': 'mods/core.sc2mod/base.sc2data/triggerlibs/librarylist.xml'}
    from sc2_engine_dependencies import catalog_registration, dependency_chain_rule
    registration = catalog_registration(mods.parent, identity(mods.parent), engine) if used_engine else None
    dependency_rule = dependency_chain_rule(engine) if used_engine else None
    for logical in components:
        for key in grouped[logical]:
            raw = read_file(key)
            if raw is not None and key not in info_files and (key.endswith(('.xml', '.triggerlib', '.sc2lib', '.sc2components')) or key.endswith('/triggers')):
                try:
                    xml_for(key)
                except ET.ParseError as exc:
                    problems.append(key + ': ' + str(exc))
        assessment = assess_component(files, logical, parsed, components[logical], bootstrap=bootstrap,
                                      registration=registration, dependency_rule=dependency_rule)
        components[logical]['assessment'] = assessment
        problems.extend(logical + ': ' + p for p in assessment['problems'])
    return result('payload')


def publish_snapshot(destination: Path, info: dict, dll: Path, contents: dict, files: dict[str, bytes], *, allow_partial=False):
    from sc2_publication import staged_directory, publish_directory, confined
    confined(destination, destination.parent)
    destination = destination.resolve()
    install = Path(info['install'])
    if any(destination.is_relative_to(p) or p.is_relative_to(destination) for p in (ROOT, install)):
        raise ValueError('Official cache must be outside the suite and game installation')
    partial = contents.get('status') == 'partial'
    if (contents['problems'] and not (partial and allow_partial and contents.get('extraction_phase') == 'payload')
            or not contents['components']):
        raise ValueError('Refusing to publish an incomplete/empty official dependency snapshot')
    if identity(install) != info:
        raise ValueError('Installation changed during extraction')
    if destination.exists():
        previous = json.loads((destination / MANIFEST).read_text(encoding='utf-8'))
        if not isinstance(previous, dict) or previous.get('version') not in (1, 2, 3) or previous.get('identity') != info:
            raise ValueError('Refusing to replace an unowned cache or another installation/build')
        if previous.get('status') != contents.get('status'):
            raise ValueError('Refusing to replace another cache completeness level')
    destination.parent.mkdir(parents=True, exist_ok=True)
    from sc2_engine_dependencies import catalog_registration
    registration = catalog_registration(install, info, contents['engine']) if contents.get('engine') else None
    with staged_directory(destination) as stage:
        manifest = {'version': 3, 'identity': info, 'dll': {'path': str(dll.resolve()), 'sha256': file_digest(dll)},
                    'loading_rules': {'assessment_version': ASSESSMENT_VERSION, 'standard_catalog_rule': None,
                                      'catalog_registration': registration},
                    **contents, 'files': {}, 'locales': {}}
        for relative, data in sorted(files.items()):
            path = safe_path(stage, relative)
            if not wanted(relative):
                raise ValueError('Disallowed cache content: ' + relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            manifest['files'][relative] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
                                         'casc_path': contents.get('source_paths', {}).get(relative, relative)}
        for logical in contents['components']:
            manifest['locales'][logical] = {lang: any(k.startswith(logical + '/' + lang.lower() + '.sc2data/')
                                                     for k in files) for lang in ('zhCN', 'enUS')}
        (stage / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        OfficialCache(stage, install, allow_partial=allow_partial)
        publish_directory(stage, destination, 'official-casc')
