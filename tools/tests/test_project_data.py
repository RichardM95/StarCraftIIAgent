import argparse
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import sc2_paths as P

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

INIT = load('layout_init', 'init-project.py')
BUILD = load('layout_build', 'build-sc2-catalog-graph.py')
QUERY = load('layout_query', 'sc2-catalog-query.py')
AUDIT = load('layout_audit', 'audit-issue-lifecycle.py')
LOGS = load('layout_logs', 'extract-playtest-bugreport.py')

def config(root, primary='Main.SC2Mod', **project):
    return {'schema_version': 1, 'paths': {'mods_dir': str(root / 'Mods')}, 'project': {'primary_mod': primary, **project}}

def component(path):
    path.mkdir(parents=True)
    (path / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
    (path / 'DocumentInfo').write_text('<DocInfo/>')
    gd = path / 'Base.SC2Data/GameData'
    gd.mkdir(parents=True)
    (gd / 'UnitData.xml').write_text('<Catalog><CUnit id="Hero"/></Catalog>')
    return path

class ProjectDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'StarCraftIIAgent'
        self.root.mkdir()
        self.cfg = config(self.base)

    def tearDown(self):
        BUILD.find_local_mods.cache_clear()
        self.temp.cleanup()

    def test_readonly_default_relative_override_copy_and_reference(self):
        data = P.project_data_dir(self.root, self.cfg)
        self.assertEqual(data, self.base / 'Mods/Main.agent')
        self.assertFalse(data.exists())
        self.cfg['project'].update(source_mode='workspace_copy', source_mod='../Source/Main.SC2Mod')
        self.assertEqual(P.project_data_dir(self.root, self.cfg), data)
        self.cfg['project']['data_dir'] = '../Records'
        self.assertEqual(P.project_data_dir(self.root, self.cfg), self.base / 'Records')
        self.assertEqual(P.catalog_output_dir(self.root, {}), self.base / 'StarCraftIIAgent-data/reference')
        self.assertIsNone(P.project_data_dir(self.root, {}))

    def test_invalid_data_location_and_existing_file_fail_without_writes(self):
        for value in (None, '', 7, str(self.root / 'wiki'), str(self.base / 'Mods/Main.SC2Mod/Records')):
            self.cfg['project']['data_dir'] = value
            with self.assertRaises(ValueError): P.project_data_dir(self.root, self.cfg)
        collision = self.base / 'collision'
        collision.write_text('User content')
        self.cfg['project']['data_dir'] = str(collision)
        with self.assertRaises(ValueError): P.project_data_dir(self.root, self.cfg)
        self.assertEqual(collision.read_text(), 'User content')

    def test_lazy_ignore_preserves_user_file_and_failure(self):
        data = P.project_data_dir(self.root, self.cfg)
        P.ensure_project_data(data)
        self.assertEqual((data / '.gitignore').read_text(), 'runtime/\n')
        (data / '.gitignore').write_text('User rules\n')
        P.ensure_project_data(data)
        self.assertEqual((data / '.gitignore').read_text(), 'User rules\n')
        with patch.object(Path, 'mkdir', side_effect=PermissionError('Denied')):
            with self.assertRaises(PermissionError): P.ensure_project_data(self.base / 'Denied.agent')
        self.assertFalse((self.root / 'wiki').exists())

    def test_reselect_switch_explicit_and_initialization_do_not_create_data(self):
        primary = self.base / 'Mods/Main.SC2Mod'
        layout = {'mods_dir': primary.parent, 'sc2_install_dir': self.base, 'campaign_maps_dir': self.base / 'Maps/Campaign'}
        with patch.object(INIT, 'REPO_ROOT', self.root), patch.object(INIT, 'load_project_config', return_value=config(self.base, data_dir='../Custom')):
            result = INIT.build_config(primary, layout)
            self.assertEqual(result['project']['data_dir'], '../Custom')
            switched = INIT.build_config(primary.with_name('Other.SC2Mod'), layout)
            self.assertEqual(P.project_data_dir(self.root, switched), primary.parent / 'Other.agent')
            explicit = INIT.build_config(primary, layout, '../Explicit')
            self.assertEqual(P.project_data_dir(self.root, explicit), self.base / 'Explicit')
        self.assertFalse((primary.parent / 'Other.agent').exists())

    def test_cross_drive_serialization_and_no_project_paths_cli(self):
        with patch.object(INIT.os.path, 'relpath', side_effect=ValueError('cross-drive')):
            self.assertTrue(Path(INIT.config_path_value(self.base / 'Records')).is_absolute())
        paths = load('layout_cli', 'project-paths.py')
        with patch.object(paths, 'ROOT', self.root), patch.object(sys, 'argv', ['paths']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(paths.main(), 0)
        result = json.loads(output.getvalue())
        self.assertIsNone(result['data_dir'])
        self.assertFalse(Path(result['catalog']).exists())

    def test_default_catalog_build_query_and_explicit_history(self):
        mod = component(self.base / 'Mods/Main.SC2Mod')
        (self.root / 'agent-config.json').write_text(json.dumps(self.cfg))
        source_before = {p: p.read_bytes() for p in mod.rglob('*') if p.is_file()}
        suite_before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(BUILD, 'ROOT', self.root), patch.object(sys, 'argv', ['build', '--sqlite-only']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(BUILD.main(), 0)
        out = self.base / 'Mods/Main.agent/runtime/catalog'
        self.assertTrue((out / 'catalog.sqlite').is_file())
        args = argparse.Namespace(db=None, graph=None, allow_stale=False, allow_incomplete_dependencies=False, verify_input_hashes=True)
        with patch.object(QUERY, 'ROOT', self.root):
            store = QUERY.load_store(args)
            self.assertEqual(store.path, out / 'catalog.sqlite')
            store.close()
            args.db, args.graph = str(out / 'catalog.sqlite'), str(out / 'graph.json')
            store = QUERY.load_store(args)
            store.close()
        self.assertEqual(source_before, {p: p.read_bytes() for p in mod.rglob('*') if p.is_file()})
        self.assertEqual(suite_before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_no_project_build_and_custom_graph_without_active_config(self):
        with patch.object(BUILD, 'ROOT', self.root), patch.object(sys, 'argv', ['build', '--sqlite-only']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(BUILD.main(), 0)
        out = self.base / 'StarCraftIIAgent-data/reference'
        self.assertTrue((out / 'catalog.sqlite').is_file())
        self.assertFalse((self.root / 'sc2-catalog-graph-out').exists())
        (self.root / 'agent-config.json').write_text('broken json')
        args = argparse.Namespace(db=None, graph=str(out / 'graph.json'), allow_stale=False, allow_incomplete_dependencies=False, verify_input_hashes=True)
        # The artifact's manifest still checks its input config; stale permission is explicit.
        with patch.object(QUERY, 'ROOT', self.root):
            with self.assertRaises(SystemExit): QUERY.load_store(args)
            args.allow_stale = True
            store = QUERY.load_store(args)
            self.assertEqual(store.path, out / 'catalog.sqlite')
            store.close()

    def test_actual_initialization_only_writes_configuration(self):
        primary = component(self.base / 'Mods/Main.SC2Mod')
        with patch.object(INIT, 'REPO_ROOT', self.root), patch.object(sys, 'argv', ['init', str(primary)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(INIT.main(), 0)
        self.assertTrue((self.root / 'agent-config.json').is_file())
        self.assertFalse((self.base / 'Mods/Main.agent').exists())
        cfg = json.loads((self.root / 'agent-config.json').read_text(encoding='utf-8'))
        self.assertEqual(P.project_data_dir(self.root, cfg), self.base / 'Mods/Main.agent')

    def test_invalid_explicit_data_is_not_replaced_during_reselect(self):
        primary = self.base / 'Mods/Main.SC2Mod'
        layout = {'mods_dir': primary.parent, 'sc2_install_dir': self.base, 'campaign_maps_dir': self.base / 'Maps/Campaign'}
        with patch.object(INIT, 'REPO_ROOT', self.root), patch.object(INIT, 'load_project_config', return_value=config(self.base, data_dir=None)):
            with self.assertRaises(ValueError): INIT.build_config(primary, layout)

    def test_ledger_skip_explicit_strict_and_logs_output(self):
        with patch.object(AUDIT, 'REPO_ROOT', self.root), patch.object(sys, 'argv', ['audit']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(AUDIT.main(), 0)
            self.assertIn('SKIP', output.getvalue())
        ledger = self.base / 'issues.md'
        ledger.write_text('当前无活动问题。', encoding='utf-8')
        with patch.object(sys, 'argv', ['audit', '--ledger', str(ledger)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(AUDIT.main(), 0)
            ledger.write_text('### ISSUE-001: Broken\n- **Status:** source fixed\n', encoding='utf-8')
            self.assertEqual(AUDIT.main(), 1)
        with patch.object(sys, 'argv', ['audit', '--ledger', str(self.base / 'missing')]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(AUDIT.main(), 1)
        component(self.base / 'Mods/Main.SC2Mod')
        (self.root / 'agent-config.json').write_text(json.dumps(self.cfg))
        with patch.object(AUDIT, 'REPO_ROOT', self.root), patch.object(sys, 'argv', ['audit']), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(AUDIT.main(), 0)
            self.assertIn('SKIP', output.getvalue())
        logs = self.base / 'GameLogs'; logs.mkdir()
        with patch.object(LOGS, 'REPO_ROOT', self.root), patch.object(sys, 'argv', ['logs', '--logs-dir', str(logs)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(LOGS.main(), 0)
        self.assertTrue((self.base / 'Mods/Main.agent/runtime/reports/bugreport.txt').is_file())

if __name__ == '__main__':
    unittest.main()
