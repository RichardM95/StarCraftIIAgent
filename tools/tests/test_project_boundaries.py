import argparse
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOLS))
from sc2_paths import find_project_mods
from index_fixture import stamp
from sc2_catalog_inputs import index_inputs, inventory, save_manifest

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,TOOLS/file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

DEPLOY=load("boundary_deploy","deploy-mod.py")
QUERY=load("boundary_query","sc2-catalog-query.py")

class ProjectBoundaryTests(unittest.TestCase):
    def test_configured_missing_source_does_not_use_same_name_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"Main.SC2Mod").mkdir(); (root/"Mods").mkdir()
            config={"paths":{"mods_dir":"Mods"},"project":{"primary_mod":"Main.SC2Mod"}}
            self.assertEqual(find_project_mods(root,config=config,env={}),[])
            self.assertEqual(find_project_mods(root,"Main.SC2Mod",config=config,env={}),[root/"Main.SC2Mod"])
            config["project"]["primary_mod"] = 42
            self.assertEqual(find_project_mods(root,config=config,env={"SC2_PRIMARY_MOD":"Main.SC2Mod"}),[])

    def test_nested_auto_deployment_and_explicit_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); mods=root/"Mods"; mods.mkdir(); source=root/"source"/"Main.SC2Mod"; source.mkdir(parents=True)
            config={"paths":{"mods_dir":"Mods"},"project":{"source_mode":"workspace_copy","source_mod":"source/Main.SC2Mod","primary_mod":"Campaign/Main.SC2Mod"}}
            (root/"agent-config.json").write_text(json.dumps(config))
            with patch.object(DEPLOY,"REPO_ROOT",root),patch.object(sys,"argv",["deploy-mod.py","--dry-run"]),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(DEPLOY.main(),0)
                self.assertIn(str(mods/"Campaign"/"Main.SC2Mod"),output.getvalue())
            nested=mods/"Campaign"/"Main.SC2Mod"; nested.mkdir(parents=True)
            config["project"]["source_mode"]="in_place"
            (root/"agent-config.json").write_text(json.dumps(config))
            with patch.object(DEPLOY,"REPO_ROOT",root),patch.object(sys,"argv",["deploy-mod.py"]),patch.object(DEPLOY.shutil,"copytree") as copy,redirect_stdout(io.StringIO()):
                self.assertEqual(DEPLOY.main(),0);copy.assert_not_called()
            with patch.object(DEPLOY,"REPO_ROOT",root),patch.object(sys,"argv",["deploy-mod.py","--source",str(source),"--dry-run"]),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(DEPLOY.main(),0)
                self.assertIn("Target: "+str(mods/"Main.SC2Mod"),output.getvalue())

    def test_deployment_target_rejects_escape_before_cleaning_or_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"Source.SC2Mod";source.mkdir();target=root/"Mods";target.mkdir()
            for relative in ("../Outside.SC2Mod",str(root/"Absolute.SC2Mod"),"not-a-mod"):
                with patch.object(DEPLOY.shutil,"copytree") as copy,patch.object(DEPLOY.shutil,"rmtree") as remove:
                    with self.assertRaises(SystemExit):
                        DEPLOY.deploy_mod(source,target,clean=True,relative_destination=relative)
                    copy.assert_not_called();remove.assert_not_called()

    def test_deployment_rejects_both_overlap_directions_before_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/"Mods";target.mkdir()
            outer=target/"Outer.SC2Mod";outer.mkdir();inner=outer/"Inner.SC2Mod";inner.mkdir()
            for source,relative in ((inner,"Outer.SC2Mod"),(outer,"Outer.SC2Mod/Inner.SC2Mod")):
                with patch.object(DEPLOY.shutil,"copytree") as copy,patch.object(DEPLOY.shutil,"rmtree") as remove:
                    with self.assertRaises(SystemExit):
                        DEPLOY.deploy_mod(source,target,clean=True,dry_run=True,relative_destination=relative)
                    copy.assert_not_called();remove.assert_not_called()

    def test_no_project_checks_reference_manifest_and_invalid_project_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); refs=root/"DataEditorXML";refs.mkdir();reference=refs/"UnitData.txt";reference.write_text("<Catalog/>")
            db=root/"catalog.sqlite";sqlite3.connect(db).close();stamp(db,root)
            reference.write_text('<Catalog><CUnit id="Changed"/></Catalog>')
            args=argparse.Namespace(db=str(db),graph=str(root/"graph.json"),allow_stale=False)
            with patch.object(QUERY,"ROOT",root),patch.object(QUERY,"DEFAULT_DB",db):
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args)
                    unexpected.close()
                args.allow_stale=True
                with redirect_stderr(io.StringIO()) as warning:
                    store=QUERY.load_store(args);store.close()
                    self.assertIn("historical",warning.getvalue().lower())
                stamp(db,root)
                (root/"agent-config.json").write_text(json.dumps({"paths":{"mods_dir":"MissingMods"},"project":{"primary_mod":"Missing.SC2Mod"}}))
                args.allow_stale=False
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args)
                    unexpected.close()
                (root/"agent-config.json").write_text("{invalid")
                with self.assertRaises(SystemExit):
                    unexpected=QUERY.load_store(args)
                    unexpected.close()
                args.allow_stale=True
                with redirect_stderr(io.StringIO()) as warning:
                    store=QUERY.load_store(args);store.close()
                    self.assertIn("historical",warning.getvalue().lower())

if __name__=="__main__":unittest.main()
