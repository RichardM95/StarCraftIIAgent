"""Default-project refresh uses real builds in isolated fixtures, never the game."""

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"
import importlib.util
import io
import json
import struct
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from sc2_catalog_inputs import manifest_path


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


Q = load('auto_refresh_query', 'sc2-catalog-query.py')
B = load('auto_refresh_builder', 'build-sc2-catalog-graph.py')
REAL_RUN = subprocess.run


def component(path, name='Old', dependencies=''):
    path.mkdir(parents=True)
    (path/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    (path/'DocumentInfo').write_text('<DocInfo><Dependencies>' + dependencies + '</Dependencies></DocInfo>')
    catalog = path/'Base.SC2Data/GameData/Units.xml'
    catalog.parent.mkdir(parents=True)
    catalog.write_text('<Catalog><CUnit id="' + name + '"/></Catalog>')
    return catalog


class AutoRefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.suite = self.root/'suite'
        self.suite.mkdir()
        self.mod = self.root/'game/Mods/Main.SC2Mod'
        self.units = component(self.mod)
        self.out = self.mod.with_name('Main.agent')/'runtime/catalog'
        self.config = {'paths': {'mods_dir': str(self.mod.parent)},
                       'project': {'primary_mod': self.mod.name, 'resolve_dependencies_recursive': True}}
        self.save_config()
        self.commands = []
        for active in (patch.object(Q, 'ROOT', self.suite),
                       patch.object(Q.subprocess, 'run', side_effect=self.build_child)):
            active.start()
            self.addCleanup(active.stop)
        self.addCleanup(B.find_local_mods.cache_clear)

    def save_config(self):
        (self.suite/'agent-config.json').write_text(json.dumps(self.config))

    def args(self, *flags):
        return Q.build_parser().parse_args([*flags, 'stats'])

    def build_child(self, command, **options):
        self.commands.append(command)
        self.assertEqual(options['timeout'], 300)
        self.assertNotEqual(Path(command[command.index('--out') + 1]), self.out)
        output = io.StringIO()
        with patch.object(B, 'ROOT', Q.ROOT), patch.multiple(B, BUILD_MOD_DIR=None, BUILD_MODS_DIR=None,
                BUILD_CAMPAIGNS_DIR=None, OFFICIAL_CACHE=None, ALLOW_INCOMPLETE_DEPENDENCIES=False,
                ALLOW_PARTIAL_OFFICIAL_CACHE=False, LOCALE='enUS'), \
                patch.object(sys, 'argv', command[1:]), redirect_stdout(output):
            result = B.main()
        return subprocess.CompletedProcess(command, result, output.getvalue(), '')

    def query(self, *flags):
        with redirect_stderr(io.StringIO()):
            store = Q.load_store(self.args(*flags))
            try:
                return store.get_node('object:Unit:Old')
            finally:
                store.close()

    def manifest(self):
        return json.loads(manifest_path(self.out/'catalog.sqlite').read_text())

    def change_manifest(self, change):
        data = self.manifest()
        change(data)
        manifest_path(self.out/'catalog.sqlite').write_text(json.dumps(data))

    def saved_index(self):
        return {p.name: p.read_bytes() for p in self.out.iterdir() if p.is_file()}

    def test_first_query_builds_once_and_valid_index_never_builds(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            store = Q.load_store(self.args())
            try:
                with patch.object(Q, 'load_store', return_value=store): Q.command_stats(self.args())
            finally:
                store.close()
        self.assertIn('Nodes:', output.getvalue())
        self.assertNotIn('Rebuilding', output.getvalue())
        self.assertIn('Catalog query index refreshed', errors.getvalue())
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.manifest()['selection']['locale'], 'enUS')
        self.assertIsNotNone(self.query())
        self.assertEqual(len(self.commands), 1)

    def test_input_add_edit_remove_and_v4_upgrade_refresh_once_each(self):
        self.query()
        added = self.units.with_name('Added.xml')
        for action in (
            lambda: added.write_text('<Catalog><CUnit id="Added"/></Catalog>'),
            lambda: added.write_text('<Catalog><CUnit id="EditedLonger"/></Catalog>'),
            added.unlink,
            lambda: self.change_manifest(lambda m: m.update(version=4)),
            lambda: self.change_manifest(lambda m: m.update(version=6)),
            lambda: self.change_manifest(lambda m: m.update(version=7)),
        ):
            action()
            before = len(self.commands)
            self.query()
            self.assertEqual(len(self.commands), before + 1)
        self.assertEqual(self.manifest()['version'], 8)

    def test_locale_is_reused_and_explicit_locale_rebuilds(self):
        self.query('--locale', 'zhCN')
        self.units.write_text('<Catalog><CUnit id="Old"/><CUnit id="New"/></Catalog>')
        self.query()
        self.assertEqual(self.manifest()['selection']['locale'], 'zhCN')
        self.query('--locale', 'enUS')
        self.assertEqual(self.manifest()['selection']['locale'], 'enUS')
        self.assertEqual(len(self.commands), 3)

    @unittest.skipUnless(os.name == 'nt' and struct.calcsize('P') == 8, 'bundled Windows x64 DLL')
    def test_packed_default_project_refresh_and_readonly_queries(self):
        from sc2_archive import convert
        from sc2_components import close_components
        self.addCleanup(close_components)
        self.query()
        convert('pack', self.mod, in_place=True, apply=True)
        old_index = self.saved_index()
        with self.assertRaises(SystemExit):
            self.query('--no-auto-rebuild')
        self.assertEqual(self.saved_index(), old_index)
        self.assertEqual(len(self.commands), 1)
        self.assertIsNotNone(self.query())
        self.assertEqual(len(self.commands), 2)
        self.assertIsNotNone(self.query())
        self.assertEqual(len(self.commands), 2)
        # A query releases its native handle, so an explicit later conversion works.
        convert('unpack', self.mod, in_place=True, apply=True)
        self.units.write_text('<Catalog><CUnit id="Old"/><CUnit id="New"/></Catalog>')
        convert('pack', self.mod, in_place=True, apply=True)
        self.query()
        self.assertEqual(len(self.commands), 3)

    def test_ui_language_does_not_rebuild_or_change_selection(self):
        self.query('--ui-language', 'en')
        original = self.saved_index()
        before_manifest = self.manifest()
        for language in ('zh-CN', 'en', 'auto'):
            self.query('--ui-language', language)
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.saved_index(), original)
        self.assertEqual(self.manifest(), before_manifest)
        self.assertNotIn('ui_language', json.dumps(before_manifest))
        preference = self.root/'personal-preferences.json'
        preference.write_text('{"ui_language":"zh-CN"}')
        with patch.dict(os.environ, {'SC2AGENT_PREFERENCES_FILE': str(preference)}):
            os.environ.pop('SC2AGENT_UI_LANGUAGE', None)
            self.query()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.saved_index(), original)


    def test_real_cli_subprocess_builds_and_preserves_query_stdout(self):
        tools = self.suite/'tools'
        tools.mkdir()
        for name in ('sc2-catalog-query.py', 'build-sc2-catalog-graph.py', 'sc2_paths.py',
                     'sc2_dependencies.py', 'sc2_catalog_inputs.py', 'sc2_official.py',
                     'sc2_i18n.py', 'sc2_ui_messages.json', 'sc2_casc.py', 'sc2_publication.py', 'sc2_components.py', 'sc2_mpq.py'):
            shutil.copyfile(TOOLS/name, tools/name)
        command = [sys.executable, str(tools/'sc2-catalog-query.py'), '--locale', 'zhCN', 'stats']
        result = REAL_RUN(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Nodes:', result.stdout)
        self.assertNotIn('Rebuilding', result.stdout)
        self.assertIn('Catalog query index refreshed', result.stderr)
        result = REAL_RUN(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Rebuilding', result.stderr)
        self.assertEqual(self.manifest()['selection']['locale'], 'zhCN')

    def test_readonly_historical_explicit_and_reference_scopes_never_build(self):
        self.query()
        before = self.saved_index()
        self.units.write_text('<Catalog><CUnit id="Changed"/></Catalog>')
        for flags in (('--no-auto-rebuild',), ('--db', str(self.out/'catalog.sqlite')),
                      ('--graph', str(self.out/'graph.json'))):
            with self.subTest(flags=flags), self.assertRaises(SystemExit): self.query(*flags)
        self.assertIsNotNone(self.query('--allow-stale'))
        self.config = {}
        self.save_config()
        with patch.object(Q, 'catalog_output_dir', return_value=self.out), self.assertRaises(SystemExit):
            self.query()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.saved_index(), before)

    def test_workspace_copy_and_recorded_campaign_override(self):
        copy_mod = self.root/'copy/Main.SC2Mod'
        component(copy_mod)
        self.config['project'].update(source_mode='workspace_copy', source_mod=str(copy_mod))
        self.save_config()
        self.query()
        self.assertEqual(self.manifest()['selection']['primary'], str(copy_mod))
        campaign = self.root/'archive/Story.SC2Campaign'
        component(campaign, 'Story')
        (copy_mod/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Campaigns/Story.SC2Campaign</Value></Dependencies></DocInfo>')
        self.query('--campaigns-dir', str(campaign.parent))
        self.units = copy_mod/'Base.SC2Data/GameData/Units.xml'
        self.units.write_text('<Catalog><CUnit id="Old"/><CUnit id="Copy"/></Catalog>')
        self.query()
        self.assertEqual(self.manifest()['selection']['campaigns_dir'], str(campaign.parent))
        self.assertEqual(self.commands[-1][self.commands[-1].index('--campaigns-dir') + 1], str(campaign.parent))

    def test_broken_source_or_missing_dependency_preserves_old_index(self):
        self.query()
        (self.out/'graph.json').write_text('old graph')
        (self.out/'manual.txt').write_text('keep')
        before = self.saved_index()
        self.units.write_text('<Catalog><CUnit id="Broken">')
        with self.assertRaises(SystemExit) as error: self.query()
        self.assertIn('rebuild failed', str(error.exception))
        self.assertEqual(self.saved_index(), before)
        self.units.write_text('<Catalog/>')
        (self.mod/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Missing.SC2Mod</Value></Dependencies></DocInfo>')
        with self.assertRaises(SystemExit): self.query()
        self.assertEqual(self.saved_index(), before)
        self.assertEqual(len(self.commands), 2)  # Dependency rejection does not start another build.

    def test_corrupt_manifest_identity_or_project_switch_never_overwrites(self):
        self.query()
        original = manifest_path(self.out/'catalog.sqlite').read_bytes()
        for change in (
            lambda m: m.update(build_id='wrong'),
            lambda m: m['selection'].update(primary=str(self.root/'Other.SC2Mod')),
            lambda m: m['selection'].update(workspace_root=str(self.root/'other-suite')),
            lambda m: m['selection'].pop('campaigns_dir'),
        ):
            self.change_manifest(change)
            before = self.saved_index()
            with self.assertRaises(SystemExit) as error: self.query()
            self.assertIn('Manual rebuild:', str(error.exception))
            self.assertEqual(self.saved_index(), before)
            manifest_path(self.out/'catalog.sqlite').write_bytes(original)
        manifest_path(self.out/'catalog.sqlite').write_text('{broken')
        with self.assertRaises(SystemExit): self.query()
        manifest_path(self.out/'catalog.sqlite').write_bytes(original)
        other = self.root/'game/Mods/Other.SC2Mod'
        component(other)
        self.config['project'].update(primary_mod=other.name, data_dir=str(self.out.parent.parent))
        self.save_config()
        with self.assertRaises(SystemExit): self.query()
        self.assertEqual(len(self.commands), 1)

    def test_partial_permissions_are_not_implicitly_enabled(self):
        self.query()
        self.change_manifest(lambda m: m.update(dependencies={**m['dependencies'], 'status': 'partial', 'problems': ['missing evidence']}))
        self.units.write_text('<Catalog/>')
        for flags in ((), ('--allow-stale',)):
            with self.assertRaises(SystemExit): self.query(*flags)
        self.query('--allow-incomplete-dependencies')
        self.assertIn('--allow-incomplete-dependencies', self.commands[-1])
        self.assertNotIn('--allow-partial-official-cache', self.commands[-1])
        self.change_manifest(lambda m: m['selection'].update(allow_partial_official_cache=True, official_cache=str(self.root/'partial-cache')))
        with self.assertRaises(SystemExit): self.query('--allow-incomplete-dependencies')
        self.assertEqual(len(self.commands), 2)

    def test_timeout_and_failed_publication_preserve_old_files(self):
        import sc2_publication
        self.query()
        before = self.saved_index()
        self.units.write_text('<Catalog><CUnit id="Timeout"/></Catalog>')
        with patch.object(Q.subprocess, 'run', side_effect=subprocess.TimeoutExpired('builder', 300)):
            with self.assertRaises(SystemExit) as error: self.query()
        self.assertIn('timed out', str(error.exception))
        self.assertEqual(self.saved_index(), before)
        original = sc2_publication.publish_directory
        def fail_parent(stage, target, kind):
            if target == self.out: raise OSError('parent switch failed')
            return original(stage, target, kind)
        with patch.object(sc2_publication, 'publish_directory', side_effect=fail_parent):
            with self.assertRaises(SystemExit): self.query()
        self.assertEqual(self.saved_index(), before)
        self.assertFalse(self.out.with_name('.catalog.sc2-refresh.lock').exists())

    def test_successful_child_without_valid_output_is_not_retried(self):
        with patch.object(Q.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as runner:
            with self.assertRaises(SystemExit): self.query()
        self.assertEqual(runner.call_count, 1)
        self.assertFalse(self.out.exists())

    def test_missing_index_strict_readonly_never_creates_runtime(self):
        for flags in (('--no-auto-rebuild',), ('--allow-stale',)):
            with self.subTest(flags=flags), self.assertRaises(SystemExit): self.query(*flags)
        self.assertFalse(self.out.parent.exists())
        self.assertEqual(self.commands, [])

    def test_recursion_changes_require_explicit_partial_permission(self):
        self.query()
        before = self.saved_index()
        self.config['project']['resolve_dependencies_recursive'] = False
        self.save_config()
        with self.assertRaises(SystemExit): self.query()
        self.assertEqual(self.saved_index(), before)
        self.query('--allow-incomplete-dependencies')
        self.assertIs(self.manifest()['selection']['recursive'], False)
        self.assertEqual(self.manifest()['dependencies']['status'], 'partial')

    def test_official_cache_is_reused_only_for_matching_installation(self):
        import test_official_cache as fixtures
        fixture = fixtures.CacheTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.sync()
        self.suite, self.mod = fixture.suite, fixture.target
        self.out = self.mod.with_name('Main.agent')/'runtime/catalog'
        self.config = {'paths': {'mods_dir': str(fixture.mods)}, 'project': {'primary_mod': self.mod.name}}
        self.save_config()
        with patch.object(Q, 'ROOT', self.suite):
            self.query('--official-cache', str(fixture.cache))
            local = self.mod/'Base.SC2Data/GameData/Units.xml'
            local.parent.mkdir(parents=True)
            local.write_text('<Catalog><CUnit id="Old"/></Catalog>')
            self.query()
            self.assertIn('--official-cache', self.commands[-1])
            self.assertEqual(self.commands[-1][self.commands[-1].index('--official-cache') + 1], str(fixture.cache))
            before = self.saved_index()
            # Keep the copy source while selecting another dependency installation.
            mods = fixture.root/'new-game/Mods'
            mods.mkdir(parents=True)
            self.config['paths']['mods_dir'] = str(mods)
            self.config['project'].update(source_mode='workspace_copy', source_mod=str(self.mod))
            self.save_config()
            with self.assertRaises(SystemExit): self.query()
            self.assertNotIn('--official-cache', self.commands[-1])
            self.assertEqual(self.commands[-1][self.commands[-1].index('--mods-dir') + 1], str(mods))
            self.assertEqual(self.saved_index(), before)

    def test_lock_timeout_never_removes_existing_lock(self):
        self.out.parent.mkdir(parents=True)
        lock = self.out.with_name('.catalog.sc2-refresh.lock')
        lock.mkdir()
        (lock/'manual').write_text('keep')
        with patch.object(Q, 'REFRESH_WAIT', 0), self.assertRaises(SystemExit) as error: self.query()
        self.assertIn('refresh lock', str(error.exception))
        self.assertTrue((lock/'manual').exists())
        self.assertEqual(self.commands, [])

    def test_concurrent_queries_recheck_under_lock_and_build_once(self):
        self.query()
        self.commands.clear()
        self.units.write_text('<Catalog><CUnit id="Old"/><CUnit id="New"/></Catalog>')
        started, second_waiting = threading.Event(), threading.Event()
        original_lock = Q.refresh_lock
        count_lock = threading.Lock()
        attempts = 0
        @contextmanager
        def observed_lock(out):
            nonlocal attempts
            with count_lock:
                attempts += 1
                if attempts == 2: second_waiting.set()
            with original_lock(out): yield
        def child(command, **options):
            started.set()
            self.assertTrue(second_waiting.wait(5))
            return self.build_child(command, **options)
        def query_thread():
            store = Q.load_store(self.args())
            try: return store.get_node('object:Unit:New') is not None
            finally: store.close()
        with patch.object(Q, 'refresh_lock', observed_lock), patch.object(Q.subprocess, 'run', side_effect=child), redirect_stderr(io.StringIO()), ThreadPoolExecutor(2) as pool:
            first = pool.submit(query_thread)
            self.assertTrue(started.wait(5))
            second = pool.submit(query_thread)
            self.assertTrue(first.result(timeout=10))
            self.assertTrue(second.result(timeout=10))
        self.assertEqual(len(self.commands), 1)


if __name__ == '__main__':
    unittest.main()
