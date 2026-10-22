import argparse
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
TOOLS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(TOOLS))
import sc2_dependencies as deps
from index_fixture import stamp
from sc2_catalog_inputs import index_inputs,inventory,save_manifest,manifest_path,changed_input

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,TOOLS/file);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
BUILDER=load("dependency_contract_builder","build-sc2-catalog-graph.py")
QUERY=load("dependency_contract_query","sc2-catalog-query.py")
SUITE=load("dependency_contract_suite","test-suite.py")
INSPECT=load("dependency_contract_inspect","inspect-mod-dependencies.py")

def component(path,reference="",info="DocumentInfo"):
    path.mkdir(parents=True)
    (path/"ComponentList.SC2Components").write_text('<Components><DataComponent Type="info">'+info+'</DataComponent></Components>')
    (path/info).write_text('<DocInfo><Dependencies>'+('<Value>'+reference+'</Value>' if reference else '')+'</Dependencies></DocInfo>')
    return path

class DependencyContractTests(unittest.TestCase):
    def tearDown(self):BUILDER.find_local_mods.cache_clear()
    def test_malformed_catalog_never_publishes_or_replaces_previous_index(self):
        for source in ('primary', 'dependency', 'reference'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                main = component(root/'Mods/Main.SC2Mod', 'file:Mods/Shared.SC2Mod')
                shared = component(root/'Mods/Shared.SC2Mod')
                catalog = main/'Base.SC2Data/GameData/Units.xml'
                catalog.parent.mkdir(parents=True)
                catalog.write_text('<Catalog><CUnit id="Saved"/></Catalog>')
                out = root/'index'
                args = ['builder', '--mod-dir', str(main), '--out', str(out), '--max-object-pages', '1']
                with patch.object(BUILDER, 'ROOT', root), patch.multiple(BUILDER, BUILD_MOD_DIR=None,
                        BUILD_MODS_DIR=None, BUILD_CAMPAIGNS_DIR=None, OFFICIAL_CACHE=None,
                        ALLOW_INCOMPLETE_DEPENDENCIES=False), redirect_stdout(io.StringIO()):
                    with patch.object(sys, 'argv', args):
                        self.assertEqual(BUILDER.main(), 0)
                    before = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
                    broken = {'primary': catalog, 'dependency': shared/'Base.SC2Data/GameData/Units.xml',
                              'reference': root/'DataEditorXML/Broken.txt'}[source]
                    broken.parent.mkdir(parents=True, exist_ok=True)
                    broken.write_text('<Catalog><CUnit id="Lost">')
                    # A partial dependency permit never permits damaged input files.
                    with patch.object(sys, 'argv', [*args, '--allow-incomplete-dependencies']):
                        self.assertEqual(BUILDER.main(), 1)
                    self.assertEqual(before, {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()})
                    with patch.object(sys, 'argv', ['builder', '--mod-dir', str(main), '--out', str(root/'new-index'), '--sqlite-only']):
                        self.assertEqual(BUILDER.main(), 1)
                    self.assertFalse((root/'new-index').exists())
                    self.assertFalse(list(root.glob('.*.stage-*')))

    def test_campaign_root_is_shared_by_build_query_and_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = component(root/'old/Mods/Main.SC2Mod')
            main = component(root/'new/Mods/Main.SC2Mod', 'file:Campaigns/Story.SC2Campaign')
            story = component(root/'archive/Story.SC2Campaign')
            units = story/'Base.SC2Data/GameData/Units.xml'
            units.parent.mkdir(parents=True)
            units.write_text('<Catalog><CUnit id="Archived"/></Catalog>')
            config = {'paths': {'mods_dir': str(old.parent)}, 'project': {'primary_mod': old.name}}
            (root/'agent-config.json').write_text(json.dumps(config))
            out = root/'index'
            argv = ['builder', '--mod-dir', str(main), '--campaigns-dir', 'archive', '--out', str(out)]
            with patch.object(BUILDER, 'ROOT', root), patch.multiple(BUILDER, BUILD_MOD_DIR=None,
                    BUILD_MODS_DIR=None, BUILD_CAMPAIGNS_DIR=None, OFFICIAL_CACHE=None,
                    ALLOW_INCOMPLETE_DEPENDENCIES=False), \
                    patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
                self.assertEqual(BUILDER.main(), 0)
            manifest = json.loads(manifest_path(out/'catalog.sqlite').read_text())
            self.assertEqual(manifest['selection']['campaigns_dir'], str(root/'archive'))
            self.assertEqual(manifest['dependencies']['campaigns_dir'], str(root/'archive'))
            self.assertEqual(manifest['dependencies']['status'], 'complete')
            with patch.object(QUERY, 'ROOT', root), redirect_stderr(io.StringIO()):
                args = QUERY.build_parser().parse_args(['--db', str(out/'catalog.sqlite'), 'stats'])
                store = QUERY.load_store(args)
                self.assertIsNotNone(store.get_node('object:Unit:Archived'))
                store.close()
                graph_store = QUERY.JsonCatalogStore(out/'graph.json')
                self.assertIsNone(QUERY.stale_default_index_input(graph_store))
                self.assertIsNotNone(graph_store.get_node('object:Unit:Archived'))
                args.campaigns_dir = Path('archive')
                store = QUERY.load_store(args); store.close()
                args.campaigns_dir = root/'wrong'
                with self.assertRaises(SystemExit): QUERY.load_store(args)
                args.campaigns_dir = None
                units.write_text('<Catalog><CUnit id="Changed"/></Catalog>')
                with self.assertRaises(SystemExit): QUERY.load_store(args)
                self.assertEqual(QUERY.stale_default_index_input(graph_store), units)

    def test_localization_conflicts_survive_both_indexes_and_are_visible_in_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = component(root/'Mods/Main.SC2Mod', 'file:Mods/Shared.SC2Mod')
            shared = component(root/'Mods/Shared.SC2Mod', 'file:Mods/Other.SC2Mod')
            other = component(root/'Mods/Other.SC2Mod')
            for mod, text in ((shared, 'FIRST'), (other, 'SECOND')):
                strings = mod/'enUS.SC2Data/LocalizedData/GameStrings.txt'
                strings.parent.mkdir(parents=True)
                strings.write_text('Unit/Name/Shared=' + text)
            out = root/'index'
            with patch.object(BUILDER, 'ROOT', root), patch.multiple(BUILDER, BUILD_MOD_DIR=None,
                    BUILD_MODS_DIR=None, BUILD_CAMPAIGNS_DIR=None, OFFICIAL_CACHE=None,
                    ALLOW_INCOMPLETE_DEPENDENCIES=False), patch.object(sys, 'argv',
                    ['builder', '--mod-dir', str(main), '--out', str(out)]), redirect_stdout(io.StringIO()):
                self.assertEqual(BUILDER.main(), 0)
            store = QUERY.SqliteCatalogStore(out/'catalog.sqlite')
            try:
                node = store.get_node('loc:Unit/Name/Shared')
                self.assertEqual(node, QUERY.JsonCatalogStore(out/'graph.json').get_node('loc:Unit/Name/Shared'))
                self.assertEqual(node['value_status'], 'ambiguous')
                self.assertNotIn('value_preview', node)
                self.assertEqual({v['value'] for v in node['values']}, {'FIRST', 'SECOND'})
                for command in ('show', 'providers'):
                    args = QUERY.build_parser().parse_args([command, 'loc:Unit/Name/Shared'])
                    with patch.object(QUERY, 'load_store', return_value=store), redirect_stdout(io.StringIO()) as output:
                        getattr(QUERY, 'command_' + command)(args)
                    self.assertIn('ambiguous', output.getvalue())
                    self.assertIn('FIRST', output.getvalue())
                    self.assertIn('SECOND', output.getvalue())
            finally:
                store.close()

    def test_version_four_index_requires_rebuild_or_explicit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = root/'catalog.sqlite'
            sqlite3.connect(database).close()
            stamp(database, root)
            path = manifest_path(database)
            legacy = json.loads(path.read_text())
            legacy['version'] = 4
            path.write_text(json.dumps(legacy))
            args = QUERY.build_parser().parse_args(['--db', str(database), 'stats'])
            with self.assertRaises(SystemExit): QUERY.load_store(args)
            args.allow_stale = True
            with redirect_stderr(io.StringIO()) as output:
                store = QUERY.load_store(args); store.close()
            self.assertIn('Historical version 4', output.getvalue())

    def test_foreign_catalog_build_records_its_actual_recursive_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=component(root/'old/Mods/Main.SC2Mod')
            target=component(root/'new/Mods/Main.SC2Mod','file:Mods/Shared.SC2Mod')
            shared=component(root/'new/Mods/Shared.SC2Mod')
            config={'paths':{'mods_dir':str(old.parent)},'project':{'primary_mod':old.name,'resolve_dependencies_recursive':False}}
            (root/'agent-config.json').write_text(json.dumps(config))
            out=root/'index'
            with patch.object(BUILDER,'ROOT',root),patch.multiple(BUILDER,BUILD_MOD_DIR=None,BUILD_MODS_DIR=None,OFFICIAL_CACHE=None,ALLOW_INCOMPLETE_DEPENDENCIES=False),patch.object(sys,'argv',['builder','--mod-dir',str(target),'--sqlite-only','--out',str(out)]),redirect_stdout(io.StringIO()):
                self.assertEqual(BUILDER.main(),0)
            manifest=json.loads(manifest_path(out/'catalog.sqlite').read_text())
            self.assertIs(manifest['selection']['recursive'],True)
            self.assertEqual(Path(manifest['selection']['mods_dir']),shared.parent)
            self.assertEqual(manifest['dependencies']['status'],'complete')
            args=argparse.Namespace(db=str(out/'catalog.sqlite'),graph=None,allow_stale=False)
            store=QUERY.load_store(args);store.close()

    def test_inspector_campaign_override_is_independent_of_current_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=component(root/'old/Mods/Main.SC2Mod')
            target=component(root/'new/Mods/Main.SC2Mod','file:Campaigns/Story.SC2Campaign')
            story=component(root/'archive/Story.SC2Campaign')
            config={'paths':{'mods_dir':str(old.parent)},'project':{'primary_mod':old.name}}
            with patch.object(INSPECT,'REPO_ROOT',root),patch.object(INSPECT,'load_project_config',return_value=config), \
                 patch.object(sys,'argv',['inspect','--mod-dir',str(target),'--campaigns-dir','archive','--json']),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(INSPECT.main(),0)
            graph=json.loads(output.getvalue())
            self.assertEqual(graph['dependency_status']['status'],'complete')
            self.assertIn(str(story.resolve()).casefold(),graph['nodes'])

    def test_foreign_nested_mod_uses_its_mods_ancestor_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=component(root/"Old"/"Mods"/"Main.SC2Mod")
            new=component(root/"New"/"Mods"/"Campaign"/"Main.SC2Mod","file:Mods/Shared.SC2Mod")
            shared=component(root/"New"/"Mods"/"Shared.SC2Mod")
            cfg={"paths":{"mods_dir":str(old.parent)},"project":{"primary_mod":"Main.SC2Mod"}}
            self.assertEqual(deps.resolve_dependency_root(root,new,cfg),shared.parent)
            self.assertEqual(deps.resolve_dependency_root(root,new,cfg,str(old.parent)),old.parent)
            targets,problems=SUITE.dependency_validation_targets(new,cfg,set())
            self.assertEqual(targets,[shared]);self.assertEqual(problems,[])
            outside=component(root/"Standalone.SC2Mod")
            with self.assertRaises(ValueError):deps.resolve_dependency_root(root,outside,cfg)
    def test_missing_dependencies_stop_default_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);main=component(root/"Mods"/"Main.SC2Mod","file:Mods/Missing.SC2Mod")
            cfg={"paths":{"mods_dir":"Mods"},"project":{"primary_mod":"Main.SC2Mod"}}
            with patch.object(BUILDER,"ROOT",root),patch.object(BUILDER,"load_project_config",return_value=cfg):
                with self.assertRaises(ValueError):BUILDER.find_local_mods()
    def test_custom_info_changes_invalidate_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mod=component(root/"Mods"/"Main.SC2Mod",info="CustomInfo.xml")
            db=root/"catalog.sqlite";db.touch();save_manifest(db,inventory(index_inputs(root,[mod])))
            self.assertIn(mod/"CustomInfo.xml",index_inputs(root,[mod]))
            (mod/"CustomInfo.xml").write_text('<DocInfo><Dependencies><Value>file:Campaigns/Void.SC2Campaign</Value></Dependencies></DocInfo>')
            self.assertEqual(changed_input(db,index_inputs(root,[mod]),verify_hashes=True),mod/"CustomInfo.xml")
    def test_partial_manifest_requires_its_own_flag_even_for_historical_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/"catalog.sqlite";sqlite3.connect(db).close()
            state={"status":"partial","problems":["missing dependency: Missing.SC2Mod"]}
            stamp(db,root,dependencies=state)
            args=argparse.Namespace(db=str(db),graph=str(root/"graph.json"),allow_stale=True)
            with patch.object(QUERY,"ROOT",root),patch.object(QUERY,"DEFAULT_DB",db):
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args);unexpected.close()
                args.allow_incomplete_dependencies=True
                for _ in range(2):
                    with redirect_stderr(io.StringIO()) as output:
                        store=QUERY.load_store(args);store.close()
                        self.assertIn("Missing.SC2Mod",output.getvalue())
                        self.assertIn("partial",output.getvalue().lower())
    def test_partial_builder_manifest_and_query_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);main=component(root/"Mods"/"Main.SC2Mod","file:Mods/Missing.SC2Mod")
            config={"paths":{"mods_dir":"Mods"},"project":{"primary_mod":"Main.SC2Mod"}}
            (root/"agent-config.json").write_text(json.dumps(config));out=root/"index"
            with patch.object(BUILDER,"ROOT",root),patch.object(BUILDER,"BUILD_MOD_DIR",None),patch.object(BUILDER,"BUILD_MODS_DIR",None),patch.object(BUILDER,"ALLOW_INCOMPLETE_DEPENDENCIES",False):
                with patch.object(sys,"argv",["builder","--sqlite-only","--out",str(out)]),redirect_stdout(io.StringIO()):
                    self.assertEqual(BUILDER.main(),1);self.assertFalse(out.exists())
                with patch.object(sys,"argv",["builder","--sqlite-only","--out",str(out),"--allow-incomplete-dependencies"]),redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(BUILDER.main(),0);self.assertIn("PARTIAL",output.getvalue())
                state=json.loads(manifest_path(out/"catalog.sqlite").read_text())["dependencies"]
                self.assertEqual(state["status"],"partial");self.assertIn("Missing.SC2Mod",state["problems"][0])
            args=argparse.Namespace(db=str(out/"catalog.sqlite"),graph=str(out/"graph.json"),allow_stale=False,allow_incomplete_dependencies=False)
            with patch.object(QUERY,"ROOT",root),patch.object(QUERY,"DEFAULT_DB",out/"catalog.sqlite"):
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args);unexpected.close()
                args.allow_stale=True
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args);unexpected.close()
                args.allow_stale=False;args.allow_incomplete_dependencies=True
                with redirect_stderr(io.StringIO()) as output:
                    store=QUERY.load_store(args);store.close()
                    self.assertIn("PARTIAL",output.getvalue());self.assertIn("Missing.SC2Mod",output.getvalue())

    def test_recursion_disabled_requires_explicit_partial_investigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);main=component(root/"Mods"/"Main.SC2Mod")
            config={"paths":{"mods_dir":"Mods"},"project":{"primary_mod":"Main.SC2Mod","resolve_dependencies_recursive":False}}
            (root/"agent-config.json").write_text(json.dumps(config))
            with patch.object(BUILDER,"ROOT",root),patch.object(BUILDER,"ALLOW_INCOMPLETE_DEPENDENCIES",False):
                with self.assertRaises(ValueError):BUILDER.find_local_mods()
                BUILDER.find_local_mods.cache_clear()
                with patch.object(BUILDER,"ALLOW_INCOMPLETE_DEPENDENCIES",True):
                    self.assertEqual(BUILDER.find_local_mods(),(main,))
                    self.assertEqual(BUILDER.DEPENDENCY_STATE["status"],"partial")
                    self.assertIn("disabled",BUILDER.DEPENDENCY_STATE["problems"][0].lower())
            db=root/"catalog.sqlite";sqlite3.connect(db).close();stamp(db,root,[main],recursive=False)
            args=argparse.Namespace(db=str(db),graph=str(root/"graph.json"),allow_stale=True)
            with patch.object(QUERY,"ROOT",root),patch.object(QUERY,"DEFAULT_DB",db):
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args);unexpected.close()
                args.allow_stale=False;args.allow_incomplete_dependencies=True
                with redirect_stderr(io.StringIO()) as output:
                    store=QUERY.load_store(args);store.close()
                    self.assertIn("disabled",output.getvalue().lower())
                    self.assertIn("PARTIAL",output.getvalue())

    def test_old_manifest_requires_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/"catalog.sqlite";db.touch()
            manifest_path(db).write_text(json.dumps({"version":1,"files":{}}))
            self.assertEqual(changed_input(db,[]),manifest_path(db))

if __name__=="__main__":unittest.main()
