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
