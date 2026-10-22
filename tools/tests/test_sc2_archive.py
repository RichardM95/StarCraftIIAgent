"""Real bundled-DLL round trips and shared read-only component contracts."""
import base64
import importlib.util
import io
import json
import os
import queue
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from sc2_archive import convert, restore, scan, payload_entries
from sc2_components import component_path, close_components, source_for, require_editable, parse_xml, MemberStream
from sc2_mpq import member_name, digest, DLL, DLL_SHA256, MpqProcess
from sc2_mpq import NativeStorm
from sc2_catalog_inputs import index_inputs, inventory, changed_input, save_manifest
from sc2_dependencies import build_dependency_graph, dependency_state
from sc2_casc import CascProcess
from sc2_publication import publish_component, staged_directory


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def component(path, dependencies='', info='DocumentInfo'):
    path.mkdir(parents=True)
    (path/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">' + info
        + '</DataComponent><DataComponent Type="trig">Triggers</DataComponent></Components>')
    target = path/info
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('<DocInfo><Dependencies>' + dependencies + '</Dependencies></DocInfo>')
    (path/'Triggers').write_text('<TriggerData/>')
    catalog = path/'Base.SC2Data/GameData/UnitData.xml'
    catalog.parent.mkdir(parents=True)
    catalog.write_text('<Catalog><CUnit id="PackedUnit"/></Catalog>')
    (path/'empty.bin').write_bytes(b'')
    (path/'Assets').mkdir()
    (path/'Assets/binary.bin').write_bytes(bytes(range(256))*20)
    return path


class BoundaryTests(unittest.TestCase):
    def enumerator(self, names, locales=1, count=None):
        native = object.__new__(NativeStorm)
        native.archive, native.members = 1, None
        iterator = iter(names)
        def set_entry(pointer):
            pointer._obj.name = next(iterator).encode()
            pointer._obj.size = 1
        native.SFileFindFirstFile = unittest.mock.Mock(side_effect=lambda a,b,p,d: (set_entry(p), 1)[1])
        def next_entry(handle, pointer):
            try:
                set_entry(pointer)
                return True
            except StopIteration:
                import ctypes
                ctypes.set_last_error(18)
                return False
        native.SFileFindNextFile = next_entry
        native.SFileFindClose = unittest.mock.Mock()
        def enum(a, name, values, size, flags):
            size._obj.value = locales
            return 0
        native.SFileEnumLocales = enum
        def info(a, cls, value, size, needed):
            value._obj.value = len(names) if count is None else count
            return True
        native.SFileGetFileInfo = info
        return native

    @unittest.skipUnless(os.name == 'nt', 'Windows error state')
    def test_enumeration_rejects_unknown_locale_collision_and_missing_names(self):
        for names, locales, count in ((['File00000001.xxx'],1,None), (['../escape'],1,None),
                (['a','A'],1,None), (['a','a/b/c'],1,None), (['a'],2,None), (['a'],1,2)):
            native = self.enumerator(names, locales, count)
            with self.subTest(names=names, locales=locales, count=count), self.assertRaises(ValueError):
                native.names()
            native.SFileFindClose.assert_called_once()

    def test_member_names_and_windows_aliases(self):
        for name in ('../x', '/x', r'C:\x', r'\\host\x', 'a/../x', 'x//y', 'NUL.txt', 'a:x', 'x.', 'a/CON', r'a\x\..\z'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                member_name(name)
        self.assertEqual(member_name(r'Base.SC2Data\GameData\Units.xml'), 'Base.SC2Data/GameData/Units.xml')

    def test_parent_protocol_timeout_crash_and_short_read(self):
        parent = object.__new__(CascProcess)
        parent.label, parent.timeout, parent.messages, parent.stderr = 'MPQ', 0.001, queue.Queue(), []
        with patch.object(CascProcess, 'close') as close:
            with self.assertRaisesRegex(ValueError, 'timed out'):
                parent._receive()
            close.assert_called_once()
        parent.messages.put({'error': 'native crash'})
        with patch.object(CascProcess, 'close') as close:
            with self.assertRaisesRegex(ValueError, 'native crash'):
                parent._receive()
            close.assert_called_once()
        source = unittest.mock.Mock()
        source.consumed = 0
        source.process.request.return_value = {'data': base64.b64encode(b'x').decode()}
        with MemberStream(source, 2) as stream:
            with self.assertRaisesRegex(ValueError, 'Short MPQ'):
                stream.readinto(bytearray(2))
        source.process.request.assert_any_call('close_file')

    def test_native_child_failure_is_diagnostic_and_reaped(self):
        with patch('sc2_mpq.dll_info'), patch('sc2_casc.pe_bits', return_value=struct.calcsize('P')*8), \
                patch('sc2_mpq.sys.executable', sys.executable):
            # Exercise the real pipe/exit path without loading native code.
            with self.assertRaisesRegex(ValueError, 'child exited'):
                CascProcess(DLL, Path('.'), _command=[sys.executable, '-c', 'raise SystemExit(17)'], _label='MPQ')

    def test_actual_child_timeout_and_dll_load_preconditions(self):
        children = []
        real_popen = subprocess.Popen
        def start(*args, **kwargs):
            child = real_popen(*args, **kwargs)
            children.append(child)
            return child
        with patch('sc2_casc.pe_bits', return_value=struct.calcsize('P')*8), patch('sc2_casc.subprocess.Popen', side_effect=start):
            with self.assertRaisesRegex(ValueError, 'timed out'):
                CascProcess(DLL, Path('.'), timeout=.02, _command=[sys.executable, '-c', 'import time;time.sleep(10)'], _label='MPQ')
        self.assertTrue(children)
        self.assertIsNotNone(children[0].poll())
        with patch('sc2_mpq.DLL', DLL.with_name('missing.dll')), self.assertRaises(OSError):
            MpqProcess()
        with patch('sc2_mpq.dll_info'), patch('sc2_casc.pe_bits', return_value=32 if struct.calcsize('P')==8 else 64), \
                self.assertRaisesRegex(ValueError, 'bitness'):
            MpqProcess()


@unittest.skipUnless(os.name == 'nt' and struct.calcsize('P') == 8, 'bundled Windows x64 DLL')
class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(close_components)
        self.root = Path(temporary.name)
        self.source = component(self.root/'源 文件.SC2Mod')
        self.archive = self.root/'Packed.SC2Mod'

    def pack(self):
        convert('pack', self.source, output=self.archive, apply=True)
        return component_path(self.archive)

    def test_dll_fingerprint_preview_and_native_round_trip(self):
        self.assertEqual(digest(DLL), DLL_SHA256)
        (self.source/'.git').mkdir()
        (self.source/'.git/private').write_bytes(b'keep in original')
        before = scan(self.source)
        report = convert('pack', self.source, output=self.archive)
        self.assertFalse(report['applied'])
        self.assertFalse(self.archive.exists())
        self.assertIn('.git/private', report['excluded'])
        packed = self.pack()
        self.assertEqual(parse_xml(packed/'DocumentInfo').getroot().tag, 'DocInfo')
        self.assertEqual((packed/'empty.bin').read_bytes(), b'')
        self.assertEqual((packed/'Assets/binary.bin').read_bytes(), (self.source/'Assets/binary.bin').read_bytes())
        source = source_for(packed)
        self.assertIs(source, source_for(packed/'DocumentInfo'))
        self.assertFalse((packed/'.git/private').exists())
        for action in (lambda: (packed/'x').write_bytes(b'x'), lambda: packed.rename(self.root/'oops')):
            with self.assertRaises(ValueError): action()
        close_components()
        output = self.root/'Unpacked.SC2Mod'
        convert('unpack', self.archive, output=output, apply=True)
        self.assertEqual(payload_entries(scan(output))[0], payload_entries(before)[0])
        self.assertEqual(scan(self.source), before)

    def test_in_place_and_backup_restore_keep_both_versions(self):
        initial = scan(self.source)
        report = convert('pack', self.source, in_place=True, apply=True)
        backup = Path(report['backup'])
        self.assertTrue(backup.is_dir())
        self.assertEqual(scan(backup), initial)
        self.assertTrue(self.source.is_file())
        self.assertFalse(restore(backup)['applied'])
        restored = restore(backup, apply=True)
        self.assertTrue(Path(restored['backup']).is_file())
        self.assertEqual(scan(self.source), initial)
        self.assertEqual(scan(backup), initial)

    def test_restore_rejects_unknown_or_modified_backups(self):
        report = convert('pack', self.source, in_place=True, apply=True)
        backup = Path(report['backup'])
        (backup/'DocumentInfo').write_text('<DocInfo broken>')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            restore(backup, apply=True)
        owner = backup.with_name(backup.name + '.owner.json')
        data = json.loads(owner.read_text()); data['tool'] = 'someone else'; owner.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'ownership'):
            restore(backup, apply=True)
        self.assertTrue(self.source.is_file())

    def test_targets_limits_and_timeout_preserve_original(self):
        before = scan(self.source)
        with self.assertRaises(ValueError):
            convert('pack', self.source, output=self.source/'Nested.SC2Mod', apply=True)
        publish = self.root/'publish'; publish.mkdir()
        with self.assertRaisesRegex(ValueError, 'publish'):
            convert('pack', self.source, output=publish/'Out.SC2Mod', apply=True)
        with patch('sc2_archive.MAX_FILE', 1), self.assertRaisesRegex(ValueError, 'limit'):
            convert('pack', self.source, output=self.archive, apply=True)
        with patch('sc2_archive.check_deadline', side_effect=TimeoutError('timeout')), self.assertRaises(TimeoutError):
            convert('pack', self.source, output=self.archive, apply=True)
        self.assertEqual(scan(self.source), before)
        self.assertFalse(self.archive.exists())

    def test_failed_publication_and_post_move_change_roll_back(self):
        before = scan(self.source)
        real_rename = Path.rename
        def fail_install(path, target):
            if '.stage-' in str(path):
                raise OSError('injected publication failure')
            return real_rename(path, target)
        with patch.object(Path, 'rename', fail_install), self.assertRaisesRegex(OSError, 'publication failure'):
            convert('pack', self.source, in_place=True, apply=True)
        self.assertEqual(scan(self.source), before)
        self.assertFalse(list(self.root.glob('*.lock')))
        with staged_directory(self.source) as stage:
            payload = stage/self.source.name
            payload.write_bytes(b'prepared')
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                publish_component(payload, self.source, expected={'kind': 'invalid'}, fingerprint=scan)
        self.assertEqual(scan(self.source), before)

    def test_mixed_dependency_recursion_and_corrupt_local_wins(self):
        mods = self.root/'Mods'
        primary = component(mods/'Main.SC2Mod', '<Value>file:Mods/Packed.SC2Mod</Value>')
        dependency = component(self.root/'Dep.SC2Mod', info='Metadata/Info.xml')
        packed = mods/'Packed.SC2Mod'
        convert('pack', dependency, output=packed, apply=True)
        graph = build_dependency_graph(primary, mods, official_cache=False)
        self.assertEqual(dependency_state(graph)['status'], 'complete')
        self.assertEqual(graph['nodes'][str(packed).casefold()]['info_component'], 'Metadata/Info.xml')
        self.assertEqual(graph['traversal_order'], [str(packed).casefold(), str(primary).casefold()])
        close_components()
        packed.write_bytes(b'broken local MPQ')
        graph = build_dependency_graph(primary, mods, official_cache=False)
        self.assertEqual(dependency_state(graph)['status'], 'partial')
        self.assertFalse(graph['missing'])
        self.assertTrue(graph['errors'])

    def test_archive_inventory_provenance_and_mid_query_change(self):
        packed = self.pack()
        files = index_inputs(self.root, [self.archive])
        inputs = inventory(files)
        unit = packed/'Base.SC2Data/GameData/UnitData.xml'
        source = inputs[unit.as_posix()]['source']
        self.assertEqual(source['archive'], str(self.archive))
        self.assertEqual(source['member'], 'Base.SC2Data/GameData/UnitData.xml')
        self.assertEqual(source['archive_sha256'], digest(self.archive))
        index = self.root/'catalog.sqlite'
        save_manifest(index, inputs)
        self.assertIsNone(changed_input(index, files, verify_hashes=True))
        with self.assertRaises(ValueError): require_editable(packed)
        # Windows denies writes while StormLib owns the read handle. Retain the
        # original session identity but release its OS handle to model a replacement.
        source_for(packed).process.close()
        with self.archive.open('ab') as stream: stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            inventory(files)

    def test_gui_catalog_and_static_consumers_use_archive(self):
        self.pack()
        from sc2_triggers import Target
        target = Target(self.archive, self.root, None, official_cache=False)
        self.assertFalse(target.problems)
        self.assertTrue(target.documents)
        validator = load('archive_validator', 'validate-mod.py')
        issues, status = validator.validate_xml_catalogs(self.archive)
        self.assertIn('verified 1', status)
        self.assertFalse(issues)
        builder = load('archive_builder', 'build-sc2-catalog-graph.py')
        out = self.root/'index'
        with patch.object(builder, 'ROOT', self.root), patch.object(sys, 'argv', ['builder', '--mod-dir', str(self.archive),
                '--mods-dir', str(self.root), '--out', str(out), '--sqlite-only']), redirect_stdout(io.StringIO()):
            self.assertEqual(builder.main(), 0)
        manifest = json.loads((out/'catalog.sqlite.inputs.json').read_text())
        self.assertEqual(manifest['version'], 8)
        self.assertEqual(manifest['selection']['primary'], str(self.archive))
        query = load('archive_query', 'sc2-catalog-query.py')
        args = query.build_parser().parse_args(['--db', str(out/'catalog.sqlite'), 'stats'])
        with redirect_stderr(io.StringIO()):
            store = query.load_store(args)
            try:
                node = store.get_node('object:Unit:PackedUnit')
                self.assertEqual(node['definitions'][0]['archive']['archive'], str(self.archive))
                self.assertIsNone(node['definitions'][0]['casc'])
            finally:
                store.close()

    def test_map_campaign_and_nested_includes_share_member_reader(self):
        from sc2_official import catalog_closure
        for extension in ('.SC2Map', '.SC2Campaign'):
            source = component(self.root/('Source' + extension))
            output = self.root/('Component' + extension)
            convert('pack', source, output=output, apply=True)
            self.assertEqual(parse_xml(component_path(output)/'DocumentInfo').getroot().tag, 'DocInfo')
        (self.source/'Base.SC2Data/GameData.xml').write_text('<Includes><Catalog path="GameData/Nested/More.xml"/></Includes>')
        nested = self.source/'Base.SC2Data/GameData/Nested/More.xml'
        nested.parent.mkdir()
        nested.write_text('<Includes><Catalog path="../UnitData.xml"/></Includes>')
        packed = self.pack()
        names = {m['name'].casefold(): m['name'] for m in source_for(packed).members.values()}
        closure = catalog_closure(set(names), lambda name: parse_xml(packed/names[name]).getroot())
        self.assertEqual(closure, ['base.sc2data/gamedata/unitdata.xml'])

    def test_changed_archive_hash_refreshes_even_with_restored_metadata(self):
        packed = self.pack()
        with self.archive.open('ab') as stream:
            stream.write(b'padding')
        files = index_inputs(self.root, [self.archive])
        index = self.root/'index.sqlite'
        save_manifest(index, inventory(files))
        metadata = self.archive.stat()
        close_components()
        # Change harmless padding, preserving XML, member sizes and mtime.
        raw = self.archive.read_bytes()
        self.archive.write_bytes(raw[:-1] + b'!')
        os.utime(self.archive, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        self.assertIsNotNone(changed_input(index, index_inputs(self.root, [self.archive])))

    def test_packed_workspace_copy_and_external_install_keep_their_identity(self):
        from sc2_paths import find_project_mods, is_project_source
        from sc2_dependencies import resolve_dependency_root
        self.pack()
        mods = self.root/'first/Mods'; mods.mkdir(parents=True)
        config = {'paths': {'mods_dir': str(mods)}, 'project': {'primary_mod': 'Installed.SC2Mod',
                  'source_mode': 'workspace_copy', 'source_mod': str(self.archive)}}
        sources = find_project_mods(self.root, config=config)
        self.assertEqual(Path(sources[0]), self.archive)
        self.assertTrue(is_project_source(self.root, self.archive, config))
        self.assertEqual(resolve_dependency_root(self.root, self.archive, config), mods)
        other = component(self.root/'second/Mods/Other.SC2Mod')
        convert('pack', other, in_place=True, apply=True)
        self.assertFalse(is_project_source(self.root, other, config))
        self.assertEqual(resolve_dependency_root(self.root, other, config), other.parent)

    def test_parent_directory_case_aliases_are_not_duplicate_members(self):
        from sc2_official import component_file
        (self.source/'Base.SC2Data/Extra.txt').write_bytes(b'extra')
        entries = payload_entries(scan(self.source))[0]
        entries = {(name.lower() if name.endswith('Extra.txt') else name): entry for name, entry in entries.items()}
        with MpqProcess() as writer:
            writer.request('pack', source=str(self.source), output=str(self.archive), members=entries)
        packed = component_path(self.archive)
        self.assertEqual(len([p for p in packed.iterdir() if p.name.casefold() == 'base.sc2data']), 1)
        self.assertEqual(component_file(packed, 'base.sc2data/extra.txt').read_bytes(), b'extra')
        self.assertEqual(parse_xml(component_file(packed, 'Base.SC2Data/GameData/UnitData.xml')).getroot().tag, 'Catalog')


if __name__ == '__main__':
    unittest.main()
