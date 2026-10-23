"""Offline evidence/cache/consumer integration, never needs the installed game."""

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"
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
from sc2_dependencies import build_dependency_graph, dependency_state, official_research_allowed
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
            'mods/core.sc2mod/base.sc2data/gamedata/a.xml': b'<Includes><Catalog path="Nested/B.xml"/></Includes>',
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
        self.assertEqual(evidence, {'kind': 'engine_locale_table', 'row_offset': 1234})
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

    def test_missing_catalog_entry_never_certifies_existing_or_declared_data(self):
        original = dict(self.files)
        entry = 'mods/core.sc2mod/base.sc2data/gamedata.xml'
        for mode in ('xml_present', 'gada_registered', 'unknown_registration', 'unknown_component_type'):
            with self.subTest(mode=mode):
                self.files = dict(original)
                del self.files[entry]
                if mode != 'xml_present':
                    self.files = {k:v for k,v in self.files.items() if '/gamedata/' not in k}
                listing = 'mods/core.sc2mod/componentlist.sc2components'
                if mode == 'gada_registered':
                    self.files[listing] = self.files[listing].replace(b'</Components>', b'<DataComponent Type="gada">GameData</DataComponent></Components>')
                if mode == 'unknown_registration':
                    del self.files[listing]
                if mode == 'unknown_component_type':
                    self.files[listing] = self.files[listing].replace(b'</Components>', b'<DataComponent Type="future">Unknown</DataComponent></Components>')
                contents, _ = official.snapshot(Reader(self.files), self.target, self.mods)
                self.assertEqual(contents['status'], 'partial')
                self.assertIn('GameData', str(contents['problems']))

    def test_old_complete_cache_with_missing_entry_is_rejected_by_both_consumers(self):
        self.sync()
        manifest = self.cache / official.MANIFEST
        data = json.loads(manifest.read_text(encoding='utf-8'))
        entry = 'mods/core.sc2mod/base.sc2data/gamedata.xml'
        del data['files'][entry]
        (self.cache / entry).unlink()
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.assertIn('GameData', str(self.graph()['errors']))
        with self.assertRaisesRegex(ValueError, 'GameData'):
            official.catalog_paths(self.cache / 'mods/core.sc2mod')

    def test_input_inventory_reads_each_cache_manifest_once(self):
        self.sync()
        mods = [Path(n['path']) for n in self.graph()['nodes'].values()]
        original, reads = Path.read_text, []
        def read(path, *args, **kwargs):
            if path.name == official.MANIFEST:
                reads.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read):
            index_inputs(self.suite, mods)
        self.assertEqual(reads, [self.cache / official.MANIFEST])

    def test_cache_validation_reads_files_and_parses_xml_once_per_operation(self):
        self.sync()
        read_bytes, fromstring = Path.read_bytes, official.ET.fromstring
        reads, parses = [], []
        def read(path):
            reads.append(path)
            return read_bytes(path)
        def parse(raw, *args, **kwargs):
            parses.append(raw)
            return fromstring(raw, *args, **kwargs)
        with patch.object(Path, 'read_bytes', read), patch.object(official.ET, 'fromstring', parse):
            official.OfficialCache(self.cache, self.install)
        self.assertEqual(len(reads), len(set(reads)))
        for key, raw in self.files.items():
            if key.endswith(('librarylist.xml', '/a.xml', '/b.xml', '.triggerlib')):
                self.assertEqual(parses.count(raw), 1)

    def test_bootstrap_blocker_stops_before_payload_reads(self):
        self.files.pop('campaigns/void.sc2campaign/documentinfo')
        self.files.pop('campaigns/void.sc2campaign/componentlist.sc2components')
        engine = {'dependencies': {'campaigns/void.sc2campaign': ['mods/core.sc2mod']},
                  'rows': {'campaigns/void.sc2campaign': 1234}}
        reader = Reader(self.files)
        reads = []
        original = reader.read
        def read(name):
            reads.append(name)
            self.assertNotIn('/base.sc2data/', name)
            self.assertNotIn('/localizeddata/', name)
            return original(name)
        reader.read = read
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            contents, files = official.snapshot(reader, self.target, self.mods)
        self.assertEqual(contents['status'], 'partial')
        self.assertIn('Core/bootstrap', str(contents['problems']))
        self.assertEqual(len(reads), len(files))

    def test_preview_and_blocked_apply_do_not_write(self):
        result = {'status': 'read_verified', 'encoding': 'ansi', 'identity': official.identity(self.install)}
        options = ['sync', '--sc2-install-dir', str(self.install), '--casc-dll', str(self.dll), '--target', str(self.target), '--mods-dir', str(self.mods), '--official-cache', str(self.cache)]
        with patch.object(CLI, 'probe', return_value=result), patch.object(CLI, 'CascProcess', return_value=Reader(self.files)), redirect_stdout(io.StringIO()):
            self.assertEqual(CLI.main(options), 0)
            self.assertFalse(self.cache.exists())
            self.files.pop('campaigns/void.sc2campaign/documentinfo')
            self.assertEqual(CLI.main([*options, '--apply']), 1)
            self.assertFalse(self.cache.exists())

    def partial_snapshot(self):
        self.files.pop('campaigns/void.sc2campaign/documentinfo', None)
        self.files.pop('campaigns/void.sc2campaign/componentlist.sc2components', None)
        engine = {'dependencies': {'campaigns/void.sc2campaign': []},
                  'rows': {'campaigns/void.sc2campaign': 1234}}
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            return official.snapshot(Reader(self.files), self.target, self.mods, allow_partial=True), engine

    def test_partial_publication_requires_opt_in_and_preserves_complete_cache(self):
        self.sync()
        before = (self.cache / official.MANIFEST).read_bytes()
        (contents, files), engine = self.partial_snapshot()
        self.assertEqual(contents['status'], 'partial')
        self.assertEqual(contents['extraction_phase'], 'payload')
        self.assertEqual(contents['components']['mods/core.sc2mod']['scope'], 'research_only')
        partial = self.cache.with_name(self.cache.name + '-partial')
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            with self.assertRaises(ValueError):
                official.publish_snapshot(partial, official.identity(self.install), self.dll, contents, files)
            official.publish_snapshot(partial, official.identity(self.install), self.dll, contents, files, allow_partial=True)
            with self.assertRaises(ValueError): official.OfficialCache(partial, self.install)
            loaded = official.OfficialCache(partial, self.install, allow_partial=True)
            self.assertIsNotNone(loaded.component('mods/core.sc2mod'))
            self.assertEqual(loaded.assessments['mods/core.sc2mod']['dependency_resolution'], 'unconfirmed')
            with self.assertRaises(ValueError):
                official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files, allow_partial=True)
        self.assertEqual((self.cache / official.MANIFEST).read_bytes(), before)

    def test_partial_cache_queries_stay_unconfirmed_and_core_is_research_only(self):
        (contents, files), engine = self.partial_snapshot()
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files, allow_partial=True)
            target = Target(self.target, self.mods, None, official_cache=self.cache, allow_partial_official_cache=True)
            self.assertEqual(target.libraries()['status'], 'unconfirmed')
            native = next(l for l in target.libraries()['libraries'] if l['library'] == 'Ntve')
            self.assertEqual(native['source_class'], 'official_reference')
            self.assertEqual(native['dependency_path'], [])
            self.assertIn('unconfirmed', str(target.problems))
            self.assertEqual(dependency_state(self.graph())['status'], 'partial')

    def test_partial_cache_does_not_waive_corruption_or_missing_opt_in_path(self):
        (contents, files), engine = self.partial_snapshot()
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files, allow_partial=True)
            write(self.cache / 'mods/core.sc2mod/base.sc2data/triggerlibs/nativelib.triggerlib', '<broken')
            with self.assertRaises(ValueError): official.OfficialCache(self.cache, self.install, allow_partial=True)
        with self.assertRaises(ValueError): official.cache_for_mods(self.mods, allow_partial=True)

    def test_verified_synthetic_bootstrap_is_required_on_both_sides(self):
        import sc2_engine_dependencies as evidence
        # Synthetic reviewed-profile fixture, never evidence for the installed game.
        blob = EngineEvidenceTests().fixture()
        engine_path = write(self.install / 'Versions/Base98370/SC2_x64.exe', blob)
        sha = hashlib.sha256(blob).hexdigest()
        engine = {'dependencies': {'campaigns/void.sc2campaign': []},
                  'rows': {'campaigns/void.sc2campaign': 1234}, 'sha256': sha,
                  'path': str(engine_path.resolve()), 'version': official.identity(self.install)['version']}
        profile = {'version': engine['version'], 'build_key': 'a'*32,
                   'context': 'component_dependencies', 'order': 'before_component_dependencies',
                   'roots': ['mods/core.sc2mod'], 'dependencies': {'mods/core.sc2mod': []},
                   'review': 'Synthetic bootstrap test fixture only',
                   'locations': [{'offset': 7000, 'length': 16, 'sha256': hashlib.sha256(blob[7000:7016]).hexdigest()}]}
        for logical in ('campaigns/void.sc2campaign', 'mods/core.sc2mod'):
            self.files.pop(logical + '/documentinfo')
            self.files.pop(logical + '/componentlist.sc2components')
        self.files['campaigns/void.sc2campaign/base.sc2data/gamedata.xml'] = b'<Includes/>'
        with patch.object(evidence, 'engine_registry', return_value=engine), patch.dict(evidence.BOOTSTRAP_PROFILES, {sha: profile}):
            contents, files = official.snapshot(Reader(self.files), self.target, self.mods)
            self.assertEqual(contents['status'], 'partial')  # Bootstrap does not prove locale edges are active dependencies.
            official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files, allow_partial=True)
            self.assertEqual(dependency_state(self.graph())['status'], 'partial')
            self.assertEqual(dependency_state(self.graph())['bootstrap_loading'], 'confirmed')
            target = Target(self.target, self.mods, None, official_cache=self.cache)
            self.assertEqual(target.libraries()['status'], 'unconfirmed')
            paths = [Path(n['path']) for n in target.graph['nodes'].values()]
            self.assertIn(engine_path.resolve().as_posix(), inventory(index_inputs(self.suite, paths)))
            data = json.loads((self.cache / official.MANIFEST).read_text())
            data['bootstrap']['roots'] = []
            (self.cache / official.MANIFEST).write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'Core/bootstrap'): official.OfficialCache(self.cache, self.install, allow_partial=True)
            profile['build_key'] = 'b'*32
            with self.assertRaises(ValueError): evidence.bootstrap_registry(self.install, official.identity(self.install), engine)
            profile['build_key'] = 'a'*32
            engine_path.write_bytes(blob + b'changed')
            self.assertEqual(target.libraries()['status'], 'unconfirmed')
            with self.assertRaises(ValueError): evidence.bootstrap_registry(self.install, official.identity(self.install), engine)
        self.assertIsNone(evidence.bootstrap_registry(self.install, official.identity(self.install), engine))

    def test_legacy_xml_cache_remains_readable(self):
        self.sync()
        path = self.cache / official.MANIFEST
        data = json.loads(path.read_text())
        data['version'] = 1
        for key in ('bootstrap', 'file_states', 'loading_status', 'local_components'):
            data.pop(key)
        for component in data['components'].values():
            component.pop('scope'); component.pop('assessment')
        path.write_text(json.dumps(data))
        self.assertFalse(official.OfficialCache(self.cache, self.install).partial)

    def test_partial_cli_and_catalog_trigger_opt_in_end_to_end(self):
        (contents, files), engine = self.partial_snapshot()
        result = {'status': 'read_verified', 'encoding': 'ansi', 'identity': official.identity(self.install)}
        options = ['sync', '--sc2-install-dir', str(self.install), '--casc-dll', str(self.dll),
                   '--target', str(self.target), '--mods-dir', str(self.mods), '--allow-partial', '--apply']
        output = io.StringIO()
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine), patch.object(CLI, 'probe', return_value=result), patch.object(CLI, 'CascProcess', return_value=Reader(self.files)), patch.object(CLI, 'default_cache', return_value=self.cache), redirect_stdout(output):
            self.assertEqual(CLI.main(options), 1)  # Applied partial != complete.
        partial = self.cache.with_name(self.cache.name + '-partial')
        self.assertTrue(json.loads(output.getvalue())['applied'])
        self.assertTrue(partial.is_dir()); self.assertFalse(self.cache.exists())
        out = self.root / 'partial-index'
        arguments = ['build', '--mod-dir', str(self.target), '--mods-dir', str(self.mods),
                     '--official-cache', str(partial), '--allow-partial-official-cache',
                     '--allow-incomplete-dependencies', '--out', str(out), '--sqlite-only']
        trigger = tool('partial_trigger_cli_test', 'sc2-trigger-query.py')
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine), patch.object(BUILDER, 'ROOT', self.suite), patch.object(sys, 'argv', arguments), redirect_stdout(io.StringIO()):
            self.assertEqual(BUILDER.main(), 0)
            manifest = json.loads((out / 'catalog.sqlite.inputs.json').read_text())
            self.assertTrue(manifest['selection']['allow_partial_official_cache'])
            self.assertEqual(manifest['dependencies']['status'], 'partial')
            flags = ['--db', str(out / 'catalog.sqlite'), '--official-cache', str(partial),
                     '--allow-incomplete-dependencies', '--allow-partial-official-cache']
            args = QUERY.build_parser().parse_args([*flags, 'stats'])
            store = QUERY.load_store(args)
            definition = store.get_node('object:Unit:Shared')['definitions'][0]
            self.assertEqual(definition['source_class'], 'reference_export')
            self.assertEqual(definition['casc']['loading_status'], 'unconfirmed')
            store.close()
            args.allow_partial_official_cache = False; args.allow_stale = True
            with self.assertRaises(SystemExit): QUERY.load_store(args)
            args.allow_partial_official_cache = True
            (partial / official.MANIFEST).write_bytes((partial / official.MANIFEST).read_bytes() + b'\n')
            args.allow_stale = False
            with self.assertRaises(SystemExit): QUERY.load_store(args)
            query = ['--target', str(self.target), '--mods-dir', str(self.mods), '--official-cache', str(partial),
                     '--allow-partial-official-cache', 'find', 'Example']
            packet = io.StringIO()
            with redirect_stdout(packet): self.assertEqual(trigger.main(query), 0)
            found = json.loads(packet.getvalue())
            self.assertEqual(found[0]['source_class'], 'official_reference')
            self.assertEqual(found[0]['compatibility']['status'], 'unconfirmed')

    def test_partial_missing_required_payload_and_optional_language_are_distinct(self):
        self.files['mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml'] = None
        (contents, files), _ = self.partial_snapshot()
        key = 'mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml'
        self.assertEqual(contents['file_states'][key], 'unavailable')
        self.assertNotIn(key, files)
        self.assertEqual(contents['components']['mods/core.sc2mod']['assessment']['closure'], 'incomplete')
        self.assertIn('Missing GameData include', str(contents['problems']))

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

    def publish_default_research(self):
        (contents, files), engine = self.partial_snapshot()
        destination = official.default_cache(self.install)
        destination = destination.with_name(destination.name + '-partial')
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            official.publish_snapshot(destination, official.identity(self.install), self.dll, contents, files, allow_partial=True)
        return destination, engine

    def test_default_research_resolves_void_and_indexes_standard_and_unregistered_tables(self):
        prefix = 'campaigns/void.sc2campaign/base.sc2data/'
        self.files[prefix + 'gamedata/unitdata.xml'] = b'<Catalog><CUnit id="OfficialVoidUnit"/></Catalog>'
        self.files[prefix + 'gamedata/extra.xml'] = b'<Catalog><CAbil id="AdditionalAbil"/></Catalog>'
        self.files[prefix + 'gamedata/unknown.xml'] = b'<Unknown><CUnit id="NotACatalog"/></Unknown>'
        self.files[prefix + 'gamedata.xml'] = b'<Includes><Catalog path="GameData/Extra.xml"/></Includes>'
        cache, engine = self.publish_default_research()
        out = self.root/'research-index'
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            graph = build_dependency_graph(self.target, self.mods)
            state = dependency_state(graph)
            self.assertTrue(official_research_allowed(state))
            self.assertFalse(any(e['kind'] == 'external' for e in graph['edges']))
            self.assertEqual(state['bootstrap_loading'], 'unconfirmed')
            void = graph['nodes'][str(cache/'campaigns/void.sc2campaign').casefold()]
            self.assertEqual(void['availability'], 'verified')
            self.assertEqual(void['assessment']['dependency_relation'], 'locale_chain')
            self.assertEqual(void['assessment']['catalog_loading'], 'unconfirmed')
            self.assertEqual(void['casc']['dependencies'], [])
            self.assertEqual(void['scope'], 'research_only')
            argv = ['builder', '--mod-dir', str(self.target), '--official-research', '--out', str(out), '--sqlite-only']
            with patch.object(BUILDER, 'ROOT', self.suite), patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                self.assertEqual(BUILDER.main(), 0)
            args = QUERY.build_parser().parse_args(['--db', str(out/'catalog.sqlite'), 'stats'])
            store = QUERY.load_store(args)
            try:
                self.assertIsNone(store.get_node('object:Unit:NotACatalog'))
                for key in ('object:Unit:OfficialVoidUnit', 'object:Abil:AdditionalAbil', 'object:Unit:Shared'):
                    definition = store.get_node(key)['definitions'][0]
                    self.assertEqual(definition['source_class'], 'reference_export')
                    self.assertEqual(definition['casc']['loading_status'], 'unconfirmed')
            finally: store.close()
            historical = out/'catalog.sqlite.inputs.json'
            data = json.loads(historical.read_text()); data['version'] = 6
            write(historical,json.dumps(data)); before = historical.read_bytes()
            args.allow_stale = True
            with patch.object(QUERY.subprocess,'run',side_effect=AssertionError('Historical index must stay read-only')):
                store=QUERY.load_store(args)
                self.assertIsNotNone(store.get_node('object:Unit:OfficialVoidUnit')); store.close()
            self.assertEqual(historical.read_bytes(),before)
            trigger = tool('default_research_trigger', 'sc2-trigger-query.py')
            flags = ['--target', str(self.target), '--mods-dir', str(self.mods)]
            for command in (['find', 'Example'], ['show', 'Ntve:FunctionDef:00000001'], ['libraries']):
                with redirect_stdout(io.StringIO()) as packet:
                    self.assertEqual(trigger.main([*flags, *command]), 0)
                data = json.loads(packet.getvalue())
                if command[0] == 'find':
                    self.assertEqual(data[0]['source_class'], 'official_reference')
                    self.assertEqual(data[0]['compatibility']['status'], 'unconfirmed')
            with redirect_stdout(io.StringIO()): self.assertEqual(trigger.main([*flags, 'check']), 1)

    def test_research_never_waives_missing_custom_dependency_or_additional_include(self):
        prefix = 'campaigns/void.sc2campaign/base.sc2data/'
        self.files[prefix + 'gamedata.xml'] = b'<Includes><Catalog path="GameData/Missing.xml"/></Includes>'
        _, engine = self.publish_default_research()
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            state = dependency_state(build_dependency_graph(self.target, self.mods))
            self.assertFalse(official_research_allowed(state))
            self.assertIn('Missing GameData include', str(state['hard_problems']))
            write(self.target/'DocumentInfo', '<DocInfo><Dependencies><Value>file:Mods/Missing.SC2Mod</Value></Dependencies></DocInfo>')
            state = dependency_state(build_dependency_graph(self.target, self.mods))
            self.assertIn('Missing.SC2Mod', str(state['hard_problems']))

    def test_invalid_complete_cache_does_not_fall_back_to_valid_partial_cache(self):
        _, engine = self.publish_default_research()
        complete = official.default_cache(self.install)
        write(complete/official.MANIFEST, '{broken')
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            graph = build_dependency_graph(self.target, self.mods)
        self.assertIsNone(graph['official_cache'])
        self.assertIn('Official cache rejected', str(graph['errors']))

    def test_legacy_cache_reassesses_missing_entries_without_mutating_manifest(self):
        self.sync()
        path = self.cache/official.MANIFEST
        data = json.loads(path.read_text())
        data['version'] = 2
        entry = 'mods/core.sc2mod/base.sc2data/gamedata.xml'
        del data['files'][entry]
        data.get('file_states', {}).pop(entry, None)
        (self.cache/entry).unlink()
        write(path, json.dumps(data))
        before = path.read_bytes()
        cache = official.OfficialCache(self.cache, self.install, allow_partial=True)
        self.assertTrue(cache.partial)
        self.assertEqual(cache.assessments['mods/core.sc2mod']['catalog_loading'], 'unconfirmed')
        self.assertEqual(path.read_bytes(), before)
        graph = self.graph()
        self.assertEqual(dependency_state(graph)['status'], 'partial')
        self.assertIn('GameData', str(graph['official_problems']))

    def test_relative_includes_are_recursive_and_cannot_escape_component(self):
        files = {'base.sc2data/gamedata.xml': b'<Includes><Catalog path="GameData/Nested/More.xml"/></Includes>',
                 'base.sc2data/gamedata/nested/more.xml': b'<Includes><Catalog path="Units.xml"/></Includes>',
                 'base.sc2data/gamedata/nested/units.xml': b'<Catalog/>'}
        parse = lambda name: official.ET.fromstring(files[name])
        self.assertEqual(official.catalog_closure(set(files), parse), ['base.sc2data/gamedata/nested/units.xml'])
        files['base.sc2data/gamedata/nested/more.xml'] = b'<Includes><Catalog path="../../../../escape.xml"/></Includes>'
        with self.assertRaisesRegex(ValueError, 'Unsafe'): official.catalog_closure(set(files), parse)

    def test_required_unavailable_payload_is_a_hard_problem_in_default_research(self):
        self.files['mods/core.sc2mod/base.sc2data/gamedata/unitdata.xml'] = None
        _, engine = self.publish_default_research()
        with patch('sc2_engine_dependencies.engine_registry', return_value=engine):
            state = dependency_state(build_dependency_graph(self.target, self.mods))
        self.assertFalse(official_research_allowed(state))
        self.assertIn('Official file unavailable', str(state['hard_problems']))

    def test_unrelated_loading_unknown_is_isolated_but_inventory_damage_still_fails(self):
        logical = 'mods/unused.sc2mod'
        self.files.update(component_files(logical))
        self.files[logical+'/base.sc2data/gamedata/unitdata.xml'] = b'<Catalog><CUnit id="Unused"/></Catalog>'
        info = self.target/'DocumentInfo'
        original = info.read_bytes()
        info.write_bytes(original.replace(b'</Dependencies>', b'<Value>file:Mods/Unused.SC2Mod</Value></Dependencies>'))
        contents, files = official.snapshot(Reader(self.files), self.target, self.mods, allow_partial=True)
        official.publish_snapshot(self.cache, official.identity(self.install), self.dll, contents, files, allow_partial=True)
        related = self.graph()
        self.assertEqual(dependency_state(related)['status'], 'partial')
        self.assertIn('unused.sc2mod', str(related['official_problems']))
        info.write_bytes(original)
        graph = self.graph()
        self.assertEqual(dependency_state(graph)['status'], 'complete')
        self.assertEqual(graph['official_cache']['status'], 'partial')
        edge = next(e for e in graph['edges'] if e['source']==graph['primary'])
        self.assertEqual((edge['relation'],edge['ordinal']), ('declared',0))
        self.assertTrue(edge['evidence'].endswith('DocumentInfo'))
        write(self.cache/logical/'base.sc2data/gamedata/unitdata.xml', '<broken')
        self.assertIn('Official cache rejected', str(self.graph()['errors']))

    def test_v3_old_assessment_recomputed_read_only_and_unknown_version_rejected(self):
        self.sync()
        path = self.cache/official.MANIFEST
        data = json.loads(path.read_text())
        for entry in data['components'].values():
            entry['assessment']['version'] = 1
            entry['assessment']['catalog_loading'] = 'obsolete'
        write(path,json.dumps(data)); before = path.read_bytes()
        cache = official.OfficialCache(self.cache,self.install)
        self.assertTrue(all(a['version']==3 for a in cache.assessments.values()))
        self.assertEqual(path.read_bytes(),before)
        next(iter(data['components'].values()))['assessment']['version'] = 999
        write(path,json.dumps(data))
        with self.assertRaisesRegex(ValueError,'assessment version'):
            official.OfficialCache(self.cache,self.install)

    def test_local_target_does_not_acquire_unused_core_research_context(self):
        cache, engine = self.publish_default_research()
        write(self.target/'DocumentInfo','<DocInfo/>')
        with patch('sc2_engine_dependencies.engine_registry',return_value=engine):
            graph = build_dependency_graph(self.target,self.mods)
        self.assertEqual(graph['research_nodes'],{})
        self.assertEqual(graph['bootstrap_loading'],'not_applicable')
        self.assertEqual(dependency_state(graph)['status'],'complete')

    def test_unclassified_legacy_cache_warning_only_applies_when_cache_is_used(self):
        contents,files=official.snapshot(Reader(self.files),self.target,self.mods)
        contents.update(status='partial',problems=['Legacy aggregate evaluation unavailable'],loading_status='unconfirmed')
        official.publish_snapshot(self.cache,official.identity(self.install),self.dll,contents,files,allow_partial=True)
        self.assertEqual(dependency_state(self.graph())['status'],'partial')
        write(self.target/'DocumentInfo','<DocInfo/>')
        self.assertEqual(dependency_state(self.graph())['status'],'complete')

    def test_cached_declaration_ordinal_keeps_empty_value_positions(self):
        key='campaigns/void.sc2campaign/documentinfo'
        self.files[key]=b'<DocInfo><Dependencies><Value/><Value>file:Mods/Core.SC2Mod</Value></Dependencies></DocInfo>'
        self.sync()
        graph=self.graph()
        edge=next(e for e in graph['edges'] if e['source'].endswith('void.sc2campaign'))
        self.assertEqual(edge['ordinal'],1)

    def test_include_order_deduplication_cycle_and_component_relative_path(self):
        files = {'base.sc2data/gamedata.xml': b'<Includes><Catalog path="GameData/Z.xml"/><Catalog path="GameData/A.xml"/><Catalog path="GameData/Z.xml"/></Includes>',
                 'base.sc2data/gamedata/z.xml': b'<Catalog/>', 'base.sc2data/gamedata/a.xml': b'<Catalog/>'}
        parse = lambda n: official.ET.fromstring(files[n])
        self.assertEqual(official.catalog_closure(set(files),parse), ['base.sc2data/gamedata/z.xml','base.sc2data/gamedata/a.xml'])
        files['base.sc2data/gamedata/z.xml'] = b'<Includes><Catalog path="../GameData.xml"/></Includes>'
        with self.assertRaisesRegex(ValueError,'Cyclic'):
            official.catalog_closure(set(files),parse)

    def test_candidates_outside_toolbox_baseline_remain_research(self):
        logical='mods/core.sc2mod'
        names=('Cursor','DSP','Light','SoundMixSnapshot','Soundtrack','VoiceOver')
        self.files.update({logical+'/base.sc2data/gamedata/'+n.lower()+'data.xml':
                           ('<Catalog><C'+n+' id="Extra"/></Catalog>').encode() for n in names})
        evidence={'catalogs':['base.sc2data/gamedata/'+n.lower()+'data.xml' for n in names]}
        assessment=official.assess_component(self.files,logical,{}, {'dependency_evidence':'documentinfo'},registration=evidence)
        self.assertEqual(len(assessment['additional_standard_candidates']),6)
        self.assertEqual(len(assessment['engine_registered_catalogs']),6)
        self.assertTrue(set(assessment['additional_standard_candidates']) <= set(assessment['nonempty_catalogs']))
        self.assertEqual(assessment['catalog_loading'],'unconfirmed')
        self.assertIsNone(assessment['loading_rule'])

    def test_dependency_evidence_does_not_change_independent_catalog_assessment(self):
        logical='mods/simple.sc2mod'
        files=component_files(logical)
        assessment=official.assess_component(files,logical,{}, {'dependency_evidence':{'kind':'engine_locale_table'}})
        self.assertEqual(assessment['catalog_loading'],'not_applicable')
        self.assertEqual(assessment['dependency_resolution'],'unconfirmed')
        bootstrap=official.assess_component(files,logical,{}, {'dependency_evidence':{'kind':'engine_bootstrap'}},bootstrap={'roots':[logical]})
        self.assertEqual(bootstrap['dependency_relation'],'bootstrap')
        self.assertEqual(bootstrap['dependency_resolution'],'confirmed')
        self.assertEqual(bootstrap['catalog_loading'],'not_applicable')

    def test_standard_source_rule_is_independent_of_additional_entry_and_keeps_unknown_content_visible(self):
        logical='mods/simple.sc2mod';prefix=logical+'/'
        files={prefix+'base.sc2data/gamedata/unitdata.xml':b'<Catalog><CUnit id="Known"/></Catalog>',
               prefix+'base.sc2data/gamedata/sc2data.xml':b'<Catalog/>'}
        reg={'catalogs':['base.sc2data/gamedata/unitdata.xml'],'source_scope':'confirmed','engine_sha256':'fixture'}
        rule={'excluded_components':['mods/voidmulti.sc2mod']}
        meta={'dependency_evidence':{'kind':'engine_locale_table'}}
        a=official.assess_component(files,logical,{},meta,registration=reg,dependency_rule=rule)
        self.assertEqual(a['catalog_loading'],'confirmed')
        self.assertEqual(a['dependency_relation'],'engine_dependency_chain')
        self.assertEqual(a['loading_rule']['file_merge_order'],'unconfirmed')
        files[prefix+'base.sc2data/gamedata/sc2data.xml']=b'<Catalog><CUnit id="Unregistered"/></Catalog>'
        a=official.assess_component(files,logical,{},meta,registration=reg,dependency_rule=rule)
        self.assertEqual(a['catalog_loading'],'unconfirmed')
        files[prefix+'base.sc2data/gamedata.xml']=b'<Includes><Catalog path="GameData/Missing.xml"/></Includes>'
        a=official.assess_component(files,logical,{},meta,registration=reg,dependency_rule=rule)
        self.assertIn('Missing GameData include',str(a['hard_problems']))
        a=official.assess_component({},'mods/voidmulti.sc2mod',{},meta,dependency_rule=rule)
        self.assertEqual(a['dependency_relation'],'locale_chain')

    def test_unlisted_cache_file_is_not_an_active_provider_and_omitted_readable_file_is_rejected(self):
        self.sync()
        component=self.cache/'mods/core.sc2mod'
        foreign=write(component/'base.sc2data/gamedata/foreign.xml','<Catalog><CUnit id="Unverified"/></Catalog>')
        self.assertNotIn(foreign,official.catalog_paths(component))
        path=self.cache/official.MANIFEST;data=json.loads(path.read_text())
        state_key=next(iter(data['file_states']));saved=data['file_states'][state_key]
        data['file_states'][state_key]={}
        write(path,json.dumps(data))
        with self.assertRaisesRegex(ValueError,'Invalid official cache file state'):
            official.OfficialCache(self.cache,self.install)
        data['file_states'][state_key]=saved
        del data['files']['mods/core.sc2mod/base.sc2data/gamedata/nested/b.xml']
        write(path,json.dumps(data))
        with self.assertRaisesRegex(ValueError,'omits readable'):
            official.OfficialCache(self.cache,self.install)

    def test_revalidated_old_partial_cache_can_supply_strict_core_and_standard_sources(self):
        # Synthetic rules exercise policy migration, not evidence for a real engine.
        logical='campaigns/void.sc2campaign'
        self.files.pop(logical+'/documentinfo');self.files.pop(logical+'/componentlist.sc2components')
        self.files.pop(logical+'/triggers')
        self.files[logical+'/base.sc2data/gamedata/unitdata.xml']=b'<Catalog><CUnit id="OfficialVoidUnit"/></Catalog>'
        engine={'dependencies':{logical:[]},'rows':{logical:1234}}
        core={'kind':'sc2_core_base','source':'fixture:documented-core','roots':['mods/core.sc2mod'],
              'dependencies':{'mods/core.sc2mod':[]},'order':'before_component_dependencies'}
        registration={'source_scope':'confirmed','engine_sha256':'fixture',
                      'catalogs':['base.sc2data/gamedata/unitdata.xml']}
        rules={'excluded_components':[],'source':'fixture:path-validation'}
        with patch('sc2_engine_dependencies.engine_registry',return_value=engine), \
             patch('sc2_engine_dependencies.bootstrap_registry',return_value=core), \
             patch('sc2_engine_dependencies.catalog_registration',return_value=registration), \
             patch('sc2_engine_dependencies.dependency_chain_rule',return_value=rules):
            contents,files=official.snapshot(Reader(self.files),self.target,self.mods)
            self.assertEqual(contents['status'],'complete')
            official.publish_snapshot(self.cache,official.identity(self.install),self.dll,contents,files)
            path=self.cache/official.MANIFEST;data=json.loads(path.read_text())
            data.update(version=2,status='partial',loading_status='unconfirmed',bootstrap=None,
                        problems=['Core/bootstrap unknown in old policy'])
            for item in data['components'].values():
                if 'locale_dependencies' in item:item['dependencies']=item.pop('locale_dependencies')
            write(path,json.dumps(data));before=path.read_bytes()
            graph=self.graph();state=dependency_state(graph)
            self.assertEqual(state['status'],'complete')
            self.assertEqual(state['bootstrap_loading'],'confirmed')
            self.assertEqual(graph['loading_order']['status'],'confirmed')
            self.assertEqual(graph['nodes'][graph['traversal_order'][0]]['name'],'core.sc2mod')
            native=next(x for x in Target(self.target,self.mods,None,official_cache=self.cache).libraries()['libraries'] if x['library']=='Ntve')
            self.assertEqual(native['source_class'],'active_dependency')
            self.assertTrue(native['dependency_path'])
            self.assertEqual(path.read_bytes(),before)
            no_inventory=dict(data);no_inventory.pop('file_states')
            write(path,json.dumps(no_inventory))
            self.assertIn('missing trigger registration metadata',str(Target(self.target,self.mods,None,official_cache=self.cache).problems))
            path.write_bytes(before)
            (self.mods/'Core.SC2Mod').mkdir()
            self.assertIn('missing ComponentList',str(self.graph()['errors']))


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
    def test_supported_sc2_core_base_is_a_documented_rule_without_fabricated_code_locations(self):
        import sc2_engine_dependencies as evidence
        sha=next(iter(evidence.VERIFIED))
        info={'version':'5.0.17.98370','build_key':'a'*32}
        engine={'sha256':sha,'version':info['version']}
        rule=evidence.bootstrap_registry(Path('unused'),info,engine)
        self.assertIsNotNone(rule)
        self.assertEqual(rule['kind'],'sc2_core_base')
        self.assertEqual(rule['roots'],['mods/core.sc2mod'])
        self.assertEqual(rule['order'],'before_component_dependencies')
        self.assertNotIn('locations',rule)
        self.assertIn('core-always-first',rule['source'])
        engine['table_offset']=evidence.VERIFIED[sha]['table_offset']
        chain=evidence.dependency_chain_rule(engine)
        self.assertEqual(chain['context'],'builtin_component_path_validation')
        self.assertIn('mods/voidmulti.sc2mod',chain['excluded_components'])
        self.assertIsNone(evidence.dependency_chain_rule({'sha256':'unsupported'}))

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

    def test_catalog_registration_is_bounded_fingerprinted_and_never_loading_proof(self):
        from sc2_engine_dependencies import parse_catalog_registration, catalog_registration, CATALOG_REGISTRATIONS
        blob=bytearray(self.fixture())
        for i, name in enumerate(('GameData/CursorData.xml','GameData/Assets.txt')):
            raw=6000+i*64; data=name.encode()
            blob[raw:raw+len(data)+1]=data+b'\0'
            struct.pack_into('<QIIII',blob,8000+i*24,0x140000000+0x1000+raw-512,len(data),*(0xffffffff,)*3)
        profile={'table':{'offset':8000,'length':48,'sha256':hashlib.sha256(blob[8000:8048]).hexdigest()},
                 'xrefs':[{'offset':7000,'length':7,'sha256':hashlib.sha256(blob[7000:7007]).hexdigest()}]}
        self.assertEqual(parse_catalog_registration(blob,profile),['gamedata/cursordata.xml','gamedata/assets.txt'])
        with tempfile.TemporaryDirectory() as tmp:
            install=Path(tmp); path=write(install/'Versions/Base98370/SC2_x64.exe',bytes(blob))
            sha=hashlib.sha256(blob).hexdigest()
            self.assertIsNone(catalog_registration(install,{}, {'sha256':'unknown'}))
            with patch.dict(CATALOG_REGISTRATIONS,{sha:profile}):
                info={'version':'5.0.17.98370','build_key':'a'*32}
                evidence=catalog_registration(install,info,{'sha256':sha})
                self.assertEqual(evidence['context'],'catalog_registration')
                self.assertEqual(evidence['activity'],'unconfirmed')
                self.assertEqual(evidence['catalogs'],['base.sc2data/gamedata/cursordata.xml'])
                path.write_bytes(bytes(blob)+b'changed')
                with self.assertRaisesRegex(ValueError,'engine changed'):catalog_registration(install,info,{'sha256':sha})
        for offset in (8000,7000):
            changed=bytearray(blob);changed[offset]^=1
            with self.assertRaisesRegex(ValueError,'evidence changed'):parse_catalog_registration(changed,profile)


if __name__ == '__main__': unittest.main()
