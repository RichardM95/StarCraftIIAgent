"""Offline evidence/cache/consumer integration, never needs the installed game."""
import ctypes as C
import hashlib
import importlib.util
import io
import json
import queue
import struct
import sys
import tempfile
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import sc2_casc as native
import sc2_official as official
from sc2_dependencies import build_dependency_graph, dependency_state
from sc2_catalog_inputs import index_inputs, inventory, save_manifest, changed_input
from sc2_triggers import Target, check


def tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CLI = tool('cache_cli_test', 'sc2-official-cache.py')
BUILDER = tool('cache_builder_test', 'build-sc2-catalog-graph.py')
QUERY = tool('cache_catalog_query_test', 'sc2-catalog-query.py')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


class Reader:
    def __init__(self, files): self.files = files
    def names(self): return list(self.files)
    def read(self, name): return self.files.get(name)
    def __enter__(self): return self
    def __exit__(self, *args): pass


def component_files(logical, deps=()):
    return {logical + '/documentinfo': ('<DocInfo><Dependencies>' + ''.join(
        '<Value>' + d + '</Value>' for d in deps) + '</Dependencies></DocInfo>').encode(),
        logical + '/componentlist.sc2components': b'<Components><DataComponent Type="info">DocumentInfo</DataComponent><DataComponent Type="trig">Triggers</DataComponent></Components>',
        logical + '/triggers': b'<TriggerData/>'}


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.suite, self.install = self.root / 'suite', self.root / 'game'
        self.suite.mkdir()
        self.mods = self.install / 'Mods'
        self.target = self.mods / 'Main.SC2Mod'
        self.cache = self.root / 'cache'
        write(self.install / '.build.info', 'Active!DEC:1|Build Key!HEX:16|Version!STRING:0|Branch!STRING:0\n1|' + 'a'*32 + '|5.0.17.98370|cn\n')
        for name, raw in component_files('main', ['bnet:Void/0.0/999,file:Campaigns/Void.SC2Campaign']).items():
            write(self.target / name.split('/', 1)[1], raw)
        self.files = component_files('campaigns/void.sc2campaign', ['file:Mods/Core.SC2Mod'])
        self.files.update(component_files('mods/core.sc2mod'))
        self.files.update({
            'mods/core.sc2mod/base.sc2data/triggerlibs/librarylist.xml': b'<TriggerData><library external="TriggerLibs/NativeLib"/></TriggerData>',
            'mods/core.sc2mod/base.sc2data/triggerlibs/nativelib.triggerlib': b'<TriggerData><Standard Id="Ntve"/><Element Type="FunctionDef" Id="00000001"><Identifier>Example</Identifier><FlagAction/></Element></TriggerData>',
            'mods/core.sc2mod/base.sc2data/gamedata.xml': b'<Includes><Catalog path="GameData/A.xml"/></Includes>',
            'mods/core.sc2mod/base.sc2data/gamedata/a.xml': b'<Includes><Catalog path="GameData/Nested/B.xml"/></Includes>',
            'mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml': b'<Catalog><CUnit id="Shared"/></Catalog>',
            'mods/core.sc2mod/zhcn.sc2data/localizeddata/gamestrings.txt': 'Unit/Name/Shared=单位'.encode(),
        })
        self.dll = write(self.root / 'unused.dll', b'fixture')
        self.patch = patch.object(official, 'ROOT', self.suite)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(BUILDER.find_local_mods.cache_clear)

    def sync(self):
        contents, files = official.snapshot(Reader(self.files), self.target, self.mods)
        self.assertEqual(contents['problems'], [])
        official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files)
        return contents

    def graph(self):
        return build_dependency_graph(self.target, self.mods, official_cache=self.cache)

    def test_recursive_void_core_and_real_ntve_registration(self):
        self.sync()
        graph = self.graph()
        self.assertEqual(dependency_state(graph)['status'], 'complete')
        self.assertEqual(len(graph['nodes']), 3)
        target = Target(self.target, self.mods, None, official_cache=self.cache)
        self.assertEqual(target.libraries()['status'], 'confirmed')
        ntve = next(e for e in target.libraries()['libraries'] if e['library'] == 'Ntve')
        self.assertEqual(ntve['origin'], 'casc')
        self.assertIn('official-cache.json', ntve['casc']['manifest'])

    def test_cache_membership_does_not_load_unreferenced_libraries(self):
        self.sync()
        write(self.target / 'DocumentInfo', '<DocInfo/>')
        target = Target(self.target, self.mods, None, official_cache=self.cache)
        self.assertEqual(target.libraries()['libraries'], [])

    def test_local_override_wins_and_broken_local_is_not_masked(self):
        self.sync()
        local = self.mods / 'Core.SC2Mod'
        for key, raw in component_files('x').items(): write(local / key.split('/', 1)[1], raw)
        graph = self.graph()
        self.assertEqual(graph['nodes'][str(local.resolve()).casefold()]['origin'], 'local')
        write(local / 'ComponentList.SC2Components', '<bad')
        self.assertIn('invalid ComponentList', str(self.graph()['errors']))

    def test_missing_custom_and_unmapped_network_stay_partial(self):
        self.sync()
        write(self.target / 'DocumentInfo', '<DocInfo><Dependencies><Value>file:Mods/Custom.SC2Mod</Value><Value>bnet:Unknown/1/2</Value></Dependencies></DocInfo>')
        graph = build_dependency_graph(self.target, self.mods, official_cache=self.cache, strict_external=True)
        self.assertEqual(len(graph['missing']), 1)
        self.assertIn('unresolved dependency', str(graph['errors']))

    def test_corruption_missing_files_and_build_switch_reject_cache(self):
        self.sync()
        source = self.cache / 'mods/core.sc2mod/triggers'
        source.write_bytes(b'<broken')
        self.assertIn('Official cache rejected', str(self.graph()['errors']))
        source.unlink()
        self.assertIn('Official cache rejected', str(self.graph()['errors']))
        build = self.install / '.build.info'
        build.write_text(build.read_text().replace('a'*32, 'b'*32))
        self.assertIn('another installation/build', str(self.graph()['errors']))

    def test_cross_installation_does_not_borrow_cache(self):
        self.sync()
        other = self.root / 'other'
        write(other / '.build.info', (self.install / '.build.info').read_bytes())
        with self.assertRaisesRegex(ValueError, 'another installation'):
            official.cache_for_mods(other / 'Mods', self.cache)
        self.assertIsNone(official.cache_for_mods(other / 'Mods'))

    def test_malformed_manifest_and_engine_only_completeness_are_rejected(self):
        self.sync()
        manifest = self.cache / official.MANIFEST
        data = json.loads(manifest.read_text(encoding='utf-8'))
        manifest.write_text('[]', encoding='utf-8')
        self.assertIn('Official cache rejected', str(self.graph()['errors']))
        data['engine'] = {'sha256': 'not-bootstrap-evidence'}
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.assertIn('Core/bootstrap completeness', str(self.graph()['errors']))

    def test_hash_valid_but_malformed_xml_and_forged_dependencies_rejected(self):
        self.sync()
        path = self.cache / official.MANIFEST
        data = json.loads(path.read_text(encoding='utf-8'))
        data['components']['mods/core.sc2mod']['dependencies'] = ['file:Mods/Injected.SC2Mod']
        path.write_text(json.dumps(data))
        self.assertIn('differs', str(self.graph()['errors']))
        data['components']['mods/core.sc2mod']['dependencies'] = []
        raw = b'<bad'
        write(self.cache / 'mods/core.sc2mod/triggers', raw)
        entry = data['files']['mods/core.sc2mod/triggers']
        entry.update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
        # Root Triggers is also XML, despite lacking a suffix.
        path.write_text(json.dumps(data))
        self.assertEqual(Target(self.target, self.mods, None, official_cache=self.cache).libraries()['status'], 'unconfirmed')

    def test_unknown_metadata_does_not_inject_core_or_publish(self):
        self.files.pop('campaigns/void.sc2campaign/documentinfo')
        self.files.pop('campaigns/void.sc2campaign/componentlist.sc2components')
        contents, files = official.snapshot(Reader(self.files), self.target, self.mods)
        self.assertEqual(contents['status'], 'partial')
        self.assertNotIn('mods/core.sc2mod', contents['components'])
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files)
        self.assertFalse(self.cache.exists())

    def test_engine_evidence_recurses_but_bootstrap_remains_unconfirmed(self):
        self.files.pop('campaigns/void.sc2campaign/documentinfo')
        self.files.pop('campaigns/void.sc2campaign/componentlist.sc2components')
        engine = {'dependencies': {'campaigns/void.sc2campaign': ['mods/core.sc2mod']},
                  'rows': {'campaigns/void.sc2campaign': 1234}}
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            contents, _ = official.snapshot(Reader(self.files), self.target, self.mods)
        self.assertIn('mods/core.sc2mod', contents['components'])
        evidence = contents['components']['campaigns/void.sc2campaign']['dependency_evidence']
        self.assertEqual(evidence, {'kind': 'engine_table', 'row_offset': 1234})
        self.assertIn('Core/bootstrap', str(contents['problems']))

    def test_unreadable_optional_language_is_reported_without_fabrication(self):
        optional = 'mods/core.sc2mod/enus.sc2data/localizeddata/gamestrings.txt'
        self.files[optional] = None
        contents, files = official.snapshot(Reader(self.files), self.target, self.mods)
        self.assertFalse(contents['problems'])
        self.assertIn(optional, contents['unavailable_files'])
        self.assertNotIn(optional, files)

    def test_recursive_includes_and_missing_registration_fail(self):
        del self.files['mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml']
        contents, _ = official.snapshot(Reader(self.files), self.target, self.mods)
        self.assertIn('Missing GameData include', str(contents['problems']))
        self.files['mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml'] = b'<Catalog/>'
        del self.files['mods/core.sc2mod/base.sc2data/triggerlibs/nativelib.triggerlib']
        with self.assertRaisesRegex(ValueError, 'registered library'):
            official.verify_closure(self.files, 'mods/core.sc2mod')

    def test_preview_and_blocked_apply_do_not_write(self):
        result = {'status': 'read_verified', 'encoding': 'ansi', 'identity': official.identity(self.install)}
        options = ['sync', '--sc2-install-dir', str(self.install), '--casc-dll', str(self.dll), '--target', str(self.target), '--mods-dir', str(self.mods), '--official-cache', str(self.cache)]
        with patch.object(CLI, 'probe', return_value=result), patch.object(CLI, 'CascProcess', return_value=Reader(self.files)), redirect_stdout(io.StringIO()):
            self.assertEqual(CLI.main(options), 0)
            self.assertFalse(self.cache.exists())
            self.files.pop('campaigns/void.sc2campaign/documentinfo')
            self.assertEqual(CLI.main([*options, '--apply']), 1)
            self.assertFalse(self.cache.exists())

    def test_path_confinement_and_publication_rollback(self):
        self.sync()
        before = (self.cache / official.MANIFEST).read_bytes()
        contents, files = official.snapshot(Reader(self.files), self.target, self.mods)
        for invalid in ('../escape', '/absolute', 'C:/escape', 'mods/x:stream'):
            with self.assertRaises(ValueError): official.safe_path(self.cache, invalid)
        for destination in (self.root, self.suite / 'cache', self.install / 'cache'):
            with self.assertRaises(ValueError): official.publish_snapshot(destination, official.identity(self.install), self.dll, contents, files)
        rename = Path.rename
        def fail_switch(path, destination):
            if path.name.startswith('.cache.stage-'): raise OSError('switch failed')
            return rename(path, destination)
        with patch.object(Path, 'rename', fail_switch):
            with self.assertRaises(OSError): official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files)
        self.assertEqual((self.cache / official.MANIFEST).read_bytes(), before)

    def test_catalog_closure_locale_provenance_and_cache_freshness(self):
        self.sync()
        graph = self.graph()
        mods = [Path(n['path']) for n in graph['nodes'].values()]
        write(self.target / 'Base.SC2Data/GameData/Units.xml', '<Catalog><CUnit id="Shared"/></Catalog>')
        with patch.object(BUILDER, 'ROOT', self.suite), patch.object(BUILDER, 'find_local_mods', return_value=tuple(mods)), patch.object(BUILDER, 'DEPENDENCY_NODES', graph['nodes']), patch.object(BUILDER, 'LOCALE', 'zhCN'):
            nodes, _, _ = BUILDER.build_graph()
        definitions = nodes['object:Unit:Shared']['definitions']
        self.assertEqual({d['source_class'] for d in definitions}, {'local_mod', 'active_component_dependency'})
        self.assertTrue(next(d for d in definitions if d['casc'])['casc']['path'].endswith('nested/b.xml'))
        loc = nodes['loc:Unit/Name/Shared']
        self.assertEqual(loc['locale'], 'zhCN')
        self.assertEqual(loc['source_class'], 'active_component_dependency')
        data = json.loads((self.cache / official.MANIFEST).read_text(encoding='utf-8'))
        self.assertFalse(data['locales']['mods/core.sc2mod']['enUS'])
        index = self.root / 'catalog.sqlite'
        save_manifest(index, inventory(index_inputs(self.suite, mods)))
        write(self.cache / official.MANIFEST, json.dumps(data, indent=1))
        self.assertEqual(changed_input(index, index_inputs(self.suite, mods)), self.cache / official.MANIFEST)

    def test_catalog_cli_build_query_and_trigger_freshness_share_selection(self):
        self.sync()
        out = self.root / 'index'
        argv = ['builder', '--mod-dir', str(self.target), '--mods-dir', str(self.mods),
                '--official-cache', str(self.cache), '--locale', 'zhCN', '--out', str(out), '--sqlite-only']
        with patch.object(BUILDER, 'ROOT', self.suite), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
            self.assertEqual(BUILDER.main(), 0)
        args = type('Args', (), {'db': str(out / 'catalog.sqlite'), 'graph': None, 'allow_stale': False,
                                'verify_input_hashes': True, 'official_cache': self.cache})()
        store = QUERY.load_store(args)
        self.assertIsNotNone(store.get_node('object:Unit:Shared'))
        store.close()
        args.official_cache = self.root / 'another-cache'
        with self.assertRaises(SystemExit): QUERY.load_store(args)
        args.official_cache = self.cache
        index_manifest = out / 'catalog.sqlite.inputs.json'
        data = json.loads(index_manifest.read_text(encoding='utf-8'))
        data['version'] = 3
        index_manifest.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(SystemExit): QUERY.load_store(args)
        args.allow_stale = True
        store = QUERY.load_store(args)
        store.close()
        data['build_id'] = 'different-artifact'
        index_manifest.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(SystemExit): QUERY.load_store(args)
        target = Target(self.target, self.mods, None, official_cache=self.cache)
        manifest = self.cache / official.MANIFEST
        manifest.write_bytes(manifest.read_bytes() + b'\n')
        self.assertEqual(target.libraries()['status'], 'unconfirmed')


class NativeBoundaryTests(unittest.TestCase):
    def test_filter_excludes_assets_and_nested_maps(self):
        for path in ('mods/x.sc2mod/base.sc2assets/a.xml', 'campaigns/x.sc2campaign/base.sc2maps/m.sc2map/documentinfo', 'mods/x.sc2mod/base.sc2data/a.m3'):
            self.assertFalse(native.wanted(path))
        self.assertTrue(native.wanted('Mods/Core.SC2Mod/Base.SC2Data/TriggerLibs/NativeLib.TriggerLib'))

    def test_pe_bitness_and_missing_dll(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.dll'
            blob = bytearray(128); blob[:2] = b'MZ'; struct.pack_into('<I', blob, 60, 80); blob[80:84] = b'PE\0\0'; struct.pack_into('<H', blob, 84, 0x14c)
            path.write_bytes(blob)
            self.assertEqual(native.pe_bits(path), 32)
            if struct.calcsize('P') == 8:
                with self.assertRaisesRegex(ValueError, 'bitness'): native.CascProcess(path, Path(tmp))
            with self.assertRaises(OSError): native.CascProcess(path.with_name('missing.dll'), Path(tmp))

    def test_timeout_crash_and_pipe_errors_are_diagnostics(self):
        process = native.CascProcess.__new__(native.CascProcess)
        process.messages, process.stderr, process.timeout = queue.Queue(), [], .001
        process.close = Mock()
        with self.assertRaisesRegex(ValueError, 'timed out'): process._receive()
        process.close.assert_called_once()
        process.messages.put({'error': 'native crash'})
        with self.assertRaisesRegex(ValueError, 'native crash'): process._receive()
        process.process = Mock()
        process.process.stdin.write.side_effect = BrokenPipeError()
        with self.assertRaisesRegex(ValueError, 'pipe closed'): process.request('read')

    def test_short_empty_reads_and_file_handles(self):
        reader = native.NativeCasc.__new__(native.NativeCasc)
        reader.handle, reader.dll = C.c_void_p(1), Mock()
        reader.dll.CascOpenFile.return_value = True
        def size(handle, output): output._obj.value = 4; return True
        reader.dll.CascGetFileSize64.side_effect = size
        reader.dll.CascReadFile.return_value = True  # zero bytes despite success
        with self.assertRaisesRegex(ValueError, 'Short'): reader.read('mods/x.sc2mod/triggers')
        reader.dll.CascCloseFile.assert_called_once()
        def empty(handle, output): output._obj.value = 0; return True
        reader.dll.CascGetFileSize64.side_effect = empty
        self.assertEqual(reader.read('mods/x.sc2mod/triggers'), b'')
        self.assertEqual(reader.dll.CascCloseFile.call_count, 2)
        reader.close()
        reader.dll.CascCloseStorage.assert_called_once()

    def test_timeout_reaps_child_and_startup_load_failure_is_json(self):
        process = native.CascProcess.__new__(native.CascProcess)
        process.process = Mock()
        process.process.poll.return_value = None
        process.process.wait.side_effect = [subprocess.TimeoutExpired('worker', 2), 0]
        process.close()
        process.process.kill.assert_called_once()
        self.assertEqual(process.process.wait.call_count, 2)
        with patch.object(native, 'NativeCasc', side_effect=OSError('DLL load failed')), redirect_stdout(io.StringIO()) as output:
            native.worker('dll', 'game', 'ansi')
        self.assertIn('DLL load failed', json.loads(output.getvalue())['error'])

    def test_probe_abi_fallback_and_no_empty_xml_success(self):
        files = {'mods/core.sc2mod/base.sc2data/triggerlibs/librarylist.xml': b'<TriggerData/>',
                 'mods/core.sc2mod/base.sc2data/TriggerLibs/NativeLib.TriggerLib': b'<TriggerData/>'}
        with patch.object(official, 'identity', return_value={}), patch.object(official, 'file_digest', return_value='sha'), patch.object(official, 'pe_bits', return_value=64), patch.object(official, 'CascProcess', side_effect=[ValueError('wrong ABI'), Reader(files)]):
            result = official.probe(Path('.'), Path('x.dll'))
            self.assertEqual(result['encoding'], 'unicode')
            self.assertEqual(len(result['attempts']), 2)
        with patch.object(official, 'identity', return_value={}), patch.object(official, 'file_digest', return_value='sha'), patch.object(official, 'pe_bits', return_value=64), patch.object(official, 'CascProcess', return_value=Reader({k:b'' for k in files})):
            self.assertEqual(official.probe(Path('.'), Path('x.dll'))['status'], 'failed')


class EngineEvidenceTests(unittest.TestCase):
    def fixture(self):
        paths = ['mods/liberty.sc2mod', 'mods/libertymulti.sc2mod', 'campaigns/liberty.sc2campaign',
                 'campaigns/libertystory.sc2campaign', 'mods/swarm.sc2mod', 'mods/swarmmulti.sc2mod',
                 'campaigns/swarm.sc2campaign', 'campaigns/swarmstory.sc2campaign', 'mods/void.sc2mod',
                 'mods/voidmulti.sc2mod', 'campaigns/void.sc2campaign', 'campaigns/voidstory.sc2campaign',
                 'mods/balancemulti.sc2mod']
        parents = [[], [0], [0], [2], [0], [4], [2, 4], [6], [4], [8], [6, 8], [10], [8]]
        blob = bytearray(16384); blob[:2] = b'MZ'
        struct.pack_into('<I', blob, 60, 128); blob[128:132] = b'PE\0\0'
        struct.pack_into('<H', blob, 134, 1); struct.pack_into('<H', blob, 148, 240)
        struct.pack_into('<H', blob, 152, 0x20b); struct.pack_into('<Q', blob, 176, 0x140000000)
        struct.pack_into('<IIII', blob, 400, 15872, 0x1000, 15872, 512)
        pointers, at = [], 1024
        for path in paths:
            text = path.replace('mods/', 'Mods/').replace('campaigns/', 'Campaigns/').replace('.sc2mod', '.SC2Mod').replace('.sc2campaign', '.SC2Campaign').encode() + b'\0'
            blob[at:at+len(text)] = text
            pointers.append(0x140000000 + 0x1000 + at - 512); at += len(text)
        for i, indices in enumerate(parents):
            values = [pointers[i], *[pointers[p] for p in indices]]
            struct.pack_into('<5Q', blob, 4096 + i*40, *(values + [0]*(5-len(values))))
        for i, index in enumerate((1, 5, 9, 12)):
            struct.pack_into('<2Q', blob, 12000 + i*16, pointers[index], int(i > 0))
        return bytes(blob)

    def test_verified_engine_table_and_unknown_build_fail_closed(self):
        from sc2_engine_dependencies import parse_table, engine_registry
        result = parse_table(self.fixture(), 4096, 12000, 13)
        self.assertEqual(result['dependencies']['campaigns/void.sc2campaign'], ['campaigns/swarm.sc2campaign', 'mods/void.sc2mod'])
        self.assertEqual(result['dependencies']['mods/voidmulti.sc2mod'], ['mods/swarmmulti.sc2mod', 'mods/void.sc2mod'])
        self.assertNotIn('mods/core.sc2mod', result['dependencies'])
        for blob in (b'', self.fixture()[:300], self.fixture()[:2000]):
            with self.assertRaises((ValueError, struct.error)): parse_table(blob, 4096, 12000, 13)
        with tempfile.TemporaryDirectory() as tmp:
            install = Path(tmp)
            write(install / 'Versions/Base98370/SC2_x64.exe', self.fixture())
            with self.assertRaisesRegex(ValueError, 'not been verified'): engine_registry(install, '5.0.17.98370')


if __name__ == '__main__': unittest.main()
