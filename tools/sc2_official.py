"""Build-bound official CASC snapshots. Consumers never load a DLL or download."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from sc2_casc import CascProcess, pe_bits, wanted

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'official-cache.json'


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


def catalog_paths(component: Path) -> list[Path]:
    """CASC uses its real GameData entry/include closure; local scope stays unchanged."""
    if cache_manifest(component) is None:
        return sorted((component / 'Base.SC2Data/GameData').glob('*.xml'))
    base = component_file(component, 'Base.SC2Data')
    entry = component_file(base, 'GameData.xml')
    pending = [entry] if entry.is_file() else []
    seen, catalogs = set(), []
    while pending:
        path = pending.pop(0)
        if path in seen:
            continue
        seen.add(path)
        root = ET.parse(path).getroot()
        if root.tag == 'Catalog':
            catalogs.append(path)
        elif root.tag == 'Includes':
            for entry in root:
                if entry.tag != 'Catalog' or not entry.get('path'):
                    raise ValueError('Unsupported GameData include: ' + str(path))
                pending.append(component_file(base, entry.get('path')))
        else:
            raise ValueError('Unsupported GameData root: ' + str(path))
    return catalogs


def verify_closure(files: dict[str, bytes], logical: str) -> None:
    """Verify references using the original registration XML, never synthesize files."""
    base = logical + '/base.sc2data/'
    component_list = logical + '/componentlist.sc2components'
    if component_list in files:
        for entry in ET.fromstring(files[component_list]).findall('DataComponent'):
            if entry.get('Type') in {'info', 'trig'}:
                relative = (entry.text or '').strip().replace('\\', '/').lower()
                safe_path(Path('/snapshot').resolve(), relative)
                if logical + '/' + relative not in files:
                    raise ValueError('Missing registered component: ' + logical + '/' + relative)
    pending, seen = [base + 'gamedata.xml'], set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        if name not in files:
            # A component with no GameData entry can be a pure trigger dependency.
            if name == base + 'gamedata.xml':
                break
            raise ValueError('Missing GameData include: ' + name)
        root = ET.fromstring(files[name])
        if root.tag == 'Includes':
            for entry in root:
                if entry.tag != 'Catalog' or not entry.get('path'):
                    raise ValueError('Unsupported GameData include: ' + name)
                relative = entry.get('path').replace('\\', '/').lower()
                safe_path(Path('/snapshot').resolve(), relative)
                pending.append(base + relative)
        elif root.tag != 'Catalog':
            raise ValueError('Unsupported GameData root: ' + name)
    listing = base + 'triggerlibs/librarylist.xml'
    if listing in files:
        for entry in ET.fromstring(files[listing]):
            external = entry.get('external')
            if not external:
                raise ValueError('Unsupported inline library registration: ' + listing)
            stem = base + external.replace('\\', '/').lower()
            safe_path(Path('/snapshot').resolve(), stem)
            if sum(stem + ext in files for ext in ('.triggerlib', '.sc2lib')) != 1:
                raise ValueError('Missing/ambiguous registered library: ' + stem)


class OfficialCache:
    def __init__(self, root: Path, install: Path):
        self.root = root.resolve()
        self.manifest_path = self.root / MANIFEST
        self.data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.identity = identity(install)
        if not isinstance(self.data, dict) or self.data.get('version') != 1 or self.data.get('identity') != self.identity:
            raise ValueError('Official cache belongs to another installation/build or needs rebuilding')
        if self.data.get('problems') or self.data.get('status') != 'complete':
            raise ValueError('Official cache is incomplete; cannot certify active dependencies')
        files = self.data.get('files')
        components = self.data.get('components')
        if not isinstance(files, dict) or not isinstance(components, dict) or not components:
            raise ValueError('Invalid official cache inventory')
        engine = self.data.get('engine')
        if engine:
            raise ValueError('Engine table alone does not establish Core/bootstrap completeness')
        for relative, entry in files.items():
            path = safe_path(self.root, relative)
            if not isinstance(entry, dict):
                raise ValueError('Invalid official file inventory entry: ' + relative)
            if (relative != relative.lower() or not wanted(relative) or file_digest(path) != entry['sha256']
                    or path.stat().st_size != entry.get('size')
                    or entry.get('casc_path', '').replace('\\', '/').lower() != relative):
                raise ValueError('Missing, damaged or disallowed official cache input: ' + relative)
            if path.suffix in {'.xml', '.triggerlib', '.sc2lib', '.sc2components'} or path.name == 'triggers':
                ET.parse(path)
        for relative, entry in components.items():
            safe_path(self.root, relative)
            if not isinstance(entry, dict):
                raise ValueError('Invalid component metadata: ' + relative)
            evidence = entry.get('dependency_evidence')
            if not isinstance(evidence, str) or evidence not in files or not evidence.startswith(relative + '/'):
                raise ValueError('Component dependency evidence missing: ' + relative)
            # Never trust a dependency list supplied without its original XML.
            dependencies = dependency_values((self.root / evidence).read_bytes())
            if dependencies != entry.get('dependencies'):
                raise ValueError('Component metadata differs from cache manifest: ' + relative)
            verify_closure({k: safe_path(self.root, k).read_bytes() for k in files if k.startswith(relative + '/')}, relative)

    def component(self, logical: str) -> Path | None:
        key = logical.replace('\\', '/').lower()
        return safe_path(self.root, key) if key in self.data['components'] else None

    def metadata(self, component: Path) -> dict:
        key = component.resolve().relative_to(self.root).as_posix()
        return self.data['components'][key]


def cache_for_mods(mods: Path, explicit: Path | None = None) -> OfficialCache | None:
    # A Mods root identifies its own installation; never borrow configured paths here.
    install = mods.resolve().parent
    if not (install / '.build.info').is_file():
        if explicit is not None:
            raise ValueError('Cannot bind official cache without the dependency installation .build.info')
        return None
    root = Path(explicit).resolve() if explicit is not None else default_cache(install)
    if not (root / MANIFEST).is_file() and explicit is None:
        return None
    return OfficialCache(root, install)


def dependency_values(raw: bytes) -> list[str]:
    text = raw.decode('utf-8-sig')
    if not re.sub(r'^\s*<\?xml[^?]*\?>', '', text, count=1).strip():
        return []
    root = ET.fromstring(text)
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


def snapshot(reader, target: Path, mods: Path) -> tuple[dict, dict[str, bytes]]:
    """Only explicitly declared components; unknown bootstrap relationships stay incomplete."""
    from sc2_dependencies import build_dependency_graph, extract_dependency_refs
    pending, problems, scanned = [], [], set()
    engine, engine_error, used_engine = None, None, False
    try:
        from sc2_engine_dependencies import engine_registry
        engine = engine_registry(mods.parent, identity(mods.parent)['version'])
    except (OSError, ValueError) as exc:
        engine_error = str(exc)
    def scan_local(component):
        if component in scanned:
            return
        scanned.add(component)
        graph = build_dependency_graph(component, mods, official_cache=False)
        problems.extend(graph['errors'])
        for edge in graph['edges']:
            if edge.get('file_path') and not edge.get('exists'):
                pending.append(edge['file_path'].replace('\\', '/').lower())
            elif edge.get('kind') == 'external' and not edge.get('file_path'):
                problems.append('Unmapped network dependency: ' + edge['raw'])
    scan_local(target)
    names = {}
    for name in reader.names():
        key = name.replace('\\', '/').lower()
        if key in names and names[key] != name:
            raise ValueError('Ambiguous CASC filename casing: ' + key)
        if wanted(key):
            names[key] = name
    components, files, unavailable = {}, {}, {}
    while pending:
        logical = pending.pop(0)
        safe_path(Path('/snapshot').resolve(), logical)
        if logical in components:
            continue
        candidates = [k for k in names if k.startswith(logical + '/')]
        if not candidates:
            problems.append('Official component not present in CASC: ' + logical)
            continue
        components[logical] = {}
        for key in candidates:
            try:
                raw = reader.read(names[key])
            except (OSError, ValueError) as exc:
                raw = None
                unavailable[key] = str(exc)
            if raw is None:
                unavailable.setdefault(key, 'CASC file not locally readable')
                if '/enus.sc2data/' not in key and '/zhcn.sc2data/' not in key:
                    problems.append('CASC file not locally readable: ' + key)
                continue
            files[key] = raw
        listing = logical + '/componentlist.sc2components'
        evidence = logical + '/documentinfo'
        if listing in files:
            root = ET.fromstring(files[listing])
            info = next((e.text for e in root.findall('DataComponent') if e.get('Type') == 'info' and e.text), None)
            if not info:
                problems.append('Component list has no info registration: ' + logical)
                continue
            evidence = logical + '/' + info.replace('\\', '/').strip().lower()
        if evidence in files:
            deps = dependency_values(files[evidence])
        elif listing not in files and engine and logical in engine['dependencies']:
            deps = ['file:' + p for p in engine['dependencies'][logical]]
            evidence = {'kind': 'engine_table', 'row_offset': engine['rows'][logical]}
            used_engine = True
        else:
            problems.append('No supported, original dependency metadata for ' + logical)
            continue
        components[logical] = {'dependency_evidence': evidence, 'dependencies': deps,
                              'library_registration': (logical + '/base.sc2data/triggerlibs/librarylist.xml'
                                                       if logical + '/base.sc2data/triggerlibs/librarylist.xml' in files else None)}
        for raw in deps:
            for ref in extract_dependency_refs(raw):
                path = ref.get('file_path')
                if not path:
                    problems.append('Unmapped official dependency: ' + raw)
                elif path.lower().startswith(('mods/', 'campaigns/')):
                    local = mods.parent.joinpath(*PurePosixPath(path).parts)
                    if not local.is_dir():
                        pending.append(path.lower())
                    else:
                        scan_local(local)
                else:
                    problems.append('Unsupported dependency path: ' + raw)
        # Preserve source XML and fail on any XML parse problem; do not lint official style.
        for key in candidates:
            if key in files and key.endswith(('.xml', '.triggerlib', '.sc2lib', '.sc2components')):
                ET.fromstring(files[key])
        try:
            verify_closure(files, logical)
        except ValueError as exc:
            problems.append(str(exc))
    if used_engine:
        problems.append('Engine table does not prove implicit Core/bootstrap loading; complete active graph remains unconfirmed')
    return {'components': components, 'problems': sorted(set(problems)),
            'unavailable_files': unavailable,
            'source_paths': {k: names[k] for k in files},
            'engine': engine if used_engine else None, 'engine_diagnostic': engine_error,
            'status': 'partial' if problems else 'complete'}, files


def publish_snapshot(destination: Path, info: dict, dll: Path, contents: dict, files: dict[str, bytes]):
    from sc2_publication import staged_directory, publish_directory, confined
    confined(destination, destination.parent)
    destination = destination.resolve()
    install = Path(info['install'])
    if any(destination.is_relative_to(p) or p.is_relative_to(destination) for p in (ROOT, install)):
        raise ValueError('Official cache must be outside the suite and game installation')
    if contents['problems'] or not contents['components']:
        raise ValueError('Refusing to publish an incomplete/empty official dependency snapshot')
    if identity(install) != info:
        raise ValueError('Installation changed during extraction')
    if destination.exists():
        previous = json.loads((destination / MANIFEST).read_text(encoding='utf-8'))
        if not isinstance(previous, dict) or previous.get('version') != 1 or previous.get('identity') != info:
            raise ValueError('Refusing to replace an unowned cache or another installation/build')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with staged_directory(destination) as stage:
        manifest = {'version': 1, 'identity': info, 'dll': {'path': str(dll.resolve()), 'sha256': file_digest(dll)},
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
        OfficialCache(stage, install)
        publish_directory(stage, destination, 'official-casc')
