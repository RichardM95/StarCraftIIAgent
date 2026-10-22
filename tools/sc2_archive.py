"""Explicit, verified Components/MPQ conversions. Never used by ordinary queries."""
from __future__ import annotations

import json
import hashlib
import shutil
import stat
import time
from pathlib import Path

from sc2_components import ArchiveSource, SUFFIXES, close_components, component_path, parse_xml, source_for
from sc2_mpq import MpqProcess, digest, dll_info, member_name, INTERNAL, EXCLUDED, MAX_MEMBERS, MAX_FILE, MAX_TOTAL
from sc2_publication import staged_directory, publish_component


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('Archive conversion timed out; original preserved')


def no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Links/junctions are unsupported: ' + str(part))


def allowed_target(path):
    no_links(path)
    path = Path(path).absolute()
    if any(p.name.casefold() == 'publish' for p in (path, *path.parents)):
        raise ValueError('publish/ cannot be a conversion target')
    if not path.parent.is_dir() or path == path.parent:
        raise ValueError('Output parent must already exist: ' + str(path))
    return path


def scan(root, deadline=None):
    """Fingerprint every source entry, including exclusions retained in backup."""
    root = Path(root)
    check_deadline(deadline)
    no_links(root)
    def fingerprint(path):
        hashed = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                check_deadline(deadline)
                hashed.update(chunk)
        return hashed.hexdigest()
    if root.is_file():
        if root.stat().st_size > MAX_TOTAL:
            raise ValueError('Archive resource limit exceeded')
        return {'kind': 'file', 'size': root.stat().st_size, 'sha256': fingerprint(root)}
    if not root.is_dir():
        raise ValueError('Source not found: ' + str(root))
    files, total = {}, 0
    pending = sorted(root.iterdir(), reverse=True)
    while pending:
        path = pending.pop()
        check_deadline(deadline)
        no_links(path)
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if path.is_dir():
            files[relative] = {'kind': 'directory'}
            pending.extend(sorted(path.iterdir(), reverse=True))
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
            if info.st_size > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('Component resource limit exceeded: ' + relative)
            files[relative] = {'kind': 'file', 'size': info.st_size, 'sha256': fingerprint(path)}
        else:
            raise ValueError('Non-regular component entry: ' + relative)
        if len(files) > MAX_MEMBERS:
            raise ValueError('Component entry resource limit exceeded')
    return {'kind': 'directory', 'entries': files}


def payload_entries(snapshot):
    result, excluded, seen, total = {}, [], set(), 0
    for name, entry in snapshot['entries'].items():
        first = name.split('/')[0].casefold()
        if first in EXCLUDED or name.casefold() in INTERNAL:
            excluded.append(name)
            continue
        member_name(name)
        if name.casefold() in seen:
            raise ValueError('Case-conflicting component entries: ' + name)
        seen.add(name.casefold())
        if entry['kind'] != 'file':
            continue
        if len(name.replace('/', '\\').encode('utf-8')) >= 260:
            raise ValueError('MPQ member name exceeds verified ABI capacity: ' + name)
        total += entry['size']
        if len(result) >= MAX_MEMBERS or entry['size'] > MAX_FILE or total > MAX_TOTAL:
            raise ValueError('Component resource limit exceeded: ' + name)
        result[name] = {'size': entry['size'], 'sha256': entry['sha256']}
    return result, excluded


def validate_component(source):
    path = component_path(source)
    listing = path / 'ComponentList.SC2Components'
    if not listing.is_file() or parse_xml(listing).getroot().tag != 'Components':
        raise ValueError('Missing/invalid ComponentList.SC2Components: ' + str(source))
    from sc2_dependencies import read_mod_dependencies
    _info, _refs, errors = read_mod_dependencies(path)
    if errors:
        raise ValueError('; '.join(errors))


def probe(path):
    path = Path(path).resolve()
    result = {'source': str(path), 'dll': dll_info(), 'editable': path.is_dir()}
    if path.suffix.casefold() not in SUFFIXES:
        raise ValueError('Expected .SC2Mod, .SC2Map or .SC2Campaign')
    validate_component(path)
    if path.is_file():
        with_source = source_for(path)
        result.update(container='mpq', sha256=with_source.sha256,
                      members=len(with_source.members), bytes=sum(m['size'] for m in with_source.members.values()))
        with_source.check(hashes=True)
    else:
        snapshot = scan(path)
        entries, excluded = payload_entries(snapshot)
        result.update(container='components', members=len(entries), excluded=excluded)
    return result


def convert(operation, source, *, output=None, in_place=False, apply=False, timeout=1800):
    if operation not in {'pack', 'unpack'} or timeout <= 0:
        raise ValueError('Invalid conversion operation/timeout')
    if bool(output) == bool(in_place):
        raise ValueError('Choose exactly one of --output or --in-place')
    deadline = time.monotonic() + timeout
    source = Path(source).absolute()
    no_links(source)
    if source.suffix.casefold() not in SUFFIXES:
        raise ValueError('Expected .SC2Mod, .SC2Map or .SC2Campaign')
    if (operation == 'pack' and not source.is_dir()) or (operation == 'unpack' and not source.is_file()):
        raise ValueError('pack requires Components; unpack requires an MPQ file')
    target = allowed_target(source if in_place else output)
    if not in_place and (target.exists() or target.is_relative_to(source) or source.is_relative_to(target)):
        raise ValueError('Output must be absent and separate from source')
    if target.suffix.casefold() != source.suffix.casefold():
        raise ValueError('Output must retain the component extension')
    validate_component(source)
    before = scan(source, deadline)
    if operation == 'pack':
        entries, excluded = payload_entries(before)
    else:
        reader = source_for(source)
        if any(m['locale'] != 0 for m in reader.members.values()):
            raise ValueError('Components cannot preserve MPQ locale metadata; conversion refused')
        entries = {m['name']: {'size': m['size']} for m in reader.members.values()
                   if m['name'].casefold() not in INTERNAL and m['name'].split('/')[0].casefold() not in EXCLUDED}
        excluded = [m['name'] for m in reader.members.values() if m['name'] not in entries]
    report = {'operation': operation, 'source': str(source), 'output': str(target), 'applied': False,
              'in_place': in_place, 'members': len(entries), 'excluded': excluded, 'backup': None}
    if not apply:
        return report
    # Drop read-only source handles before a Windows rename; no query cache is materialized.
    close_components()
    with staged_directory(target) as stage:
        payload = stage / target.name
        if operation == 'pack':
            with MpqProcess(timeout=timeout) as writer:
                writer.request('pack', source=str(source), output=str(payload), members=entries)
            reader = ArchiveSource(payload, timeout=min(timeout, 60))
            try:
                actual = {m['name']: m for m in reader.members.values() if m['name'].casefold() not in INTERNAL}
                if set(actual) != set(entries):
                    raise ValueError('Packed member set differs from source')
                for name, entry in entries.items():
                    check_deadline(deadline)
                    with reader.open(name) as stream:
                        hashed = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if actual[name]['size'] != entry['size'] or hashed != entry['sha256']:
                        raise ValueError('Packed member verification failed: ' + name)
                reader.check(hashes=True)
            finally:
                reader.close()
        else:
            payload.mkdir()
            reader = ArchiveSource(source, timeout=min(timeout, 60))
            try:
                for name, entry in entries.items():
                    check_deadline(deadline)
                    destination = payload / member_name(name)
                    if len(str(destination)) > 4096 or not destination.resolve().is_relative_to(payload.resolve()):
                        raise ValueError('Archive path escapes output')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    hashed = hashlib.sha256()
                    with reader.open(name) as stream, destination.open('xb') as out:
                        while chunk := stream.read(1024 * 1024):
                            check_deadline(deadline)
                            hashed.update(chunk)
                            out.write(chunk)
                    if destination.stat().st_size != entry['size'] or digest(destination) != hashed.hexdigest():
                        raise ValueError('Extracted member verification failed: ' + name)
                reader.check(hashes=True)
            finally:
                reader.close()
            validate_component(payload)
            close_components()
            if set(payload_entries(scan(payload, deadline))[0]) != set(entries):
                raise ValueError('Extracted member set differs from archive')
        check_deadline(deadline)
        if scan(source, deadline) != before:
            raise ValueError('Source changed during conversion; original preserved')
        backup = publish_component(payload, target, expected=before if in_place else None, fingerprint=scan)
    report.update(applied=True, backup=str(backup) if backup else None)
    return report


def restore(backup, *, apply=False, timeout=1800):
    backup = Path(backup).absolute()
    no_links(backup)
    owner = backup.with_name(backup.name + '.owner.json')
    no_links(owner)
    data = json.loads(owner.read_text(encoding='utf-8'))
    target = allowed_target(data['target'])
    if (data.get('tool') != 'SC2ModAgent' or data.get('kind') != 'component-conversion' or data.get('version') != 1
            or data.get('backup') != str(backup) or backup.parent != target.parent
            or not backup.name.startswith('.' + target.name + '.sc2-backup-') or timeout <= 0):
        raise ValueError('Unknown or invalid backup ownership; refusing restoration')
    deadline = time.monotonic() + timeout
    if scan(backup, deadline) != data['fingerprint']:
        raise ValueError('Backup integrity mismatch')
    report = {'operation': 'restore', 'source': str(backup), 'output': str(target), 'applied': False, 'backup': None}
    if not apply:
        return report
    current = scan(target, deadline) if target.exists() else None
    close_components()
    with staged_directory(target) as stage:
        payload = stage / target.name
        if backup.is_dir():
            shutil.copytree(backup, payload)
        else:
            shutil.copy2(backup, payload)
        if scan(payload, deadline) != data['fingerprint'] or scan(backup, deadline) != data['fingerprint']:
            raise ValueError('Backup changed during restoration')
        retained = publish_component(payload, target, expected=current, fingerprint=scan)
    report.update(applied=True, backup=str(retained) if retained else None)
    return report
