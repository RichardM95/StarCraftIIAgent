import argparse, importlib.util, io, json, sqlite3, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
TOOLS=Path(__file__).resolve().parents[1];sys.path.insert(0,str(TOOLS))
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,TOOLS/file);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
B=load("publication_builder","build-sc2-catalog-graph.py");Q=load("publication_query","sc2-catalog-query.py");D=load("publication_deploy","deploy-mod.py")
def component(p,unit):
    p.mkdir(parents=True);(p/"ComponentList.SC2Components").write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>');(p/"DocumentInfo").write_text('<DocInfo/>');gd=p/"Base.SC2Data/GameData";gd.mkdir(parents=True);(gd/"UnitData.xml").write_text('<Catalog><CUnit id="'+unit+'"/></Catalog>');return p
class PublicationTests(unittest.TestCase):
    def tearDown(self): B.find_local_mods.cache_clear()
    def build(self,root,out,*flags):
        with patch.object(B,"ROOT",root),patch.object(sys,"argv",["builder","--sqlite-only","--out",str(out),*flags]),redirect_stdout(io.StringIO()): return B.main()
    def query(self,root,out,**options):
        args=argparse.Namespace(db=str(out/"catalog.sqlite"),graph=str(out/"graph.json"),allow_stale=False,verify_input_hashes=True,**options)
        with patch.object(Q,"ROOT",root),patch.object(Q,"DEFAULT_DB",root/"default/catalog.sqlite"): return Q.load_store(args)
    def test_failed_copy_preserves_previous_deployment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=component(root/"source/Main.SC2Mod","New");mods=root/"Mods";target=component(mods/"Main.SC2Mod","Old");before=(target/"Base.SC2Data/GameData/UnitData.xml").read_bytes()
            with patch.object(D.shutil,"copytree",side_effect=OSError("copy failed")),redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):D.deploy_mod(source,mods,clean=True)
            self.assertEqual((target/"Base.SC2Data/GameData/UnitData.xml").read_bytes(),before)
    def test_failed_manifest_preserves_previous_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mod=component(root/"Mods/Main.SC2Mod","Old");(root/"agent-config.json").write_text(json.dumps({"paths":{"mods_dir":"Mods"},"project":{"primary_mod":"Main.SC2Mod"}}));out=root/"index"
            self.build(root,out);before=(out/"catalog.sqlite").read_bytes();manifest=(out/"catalog.sqlite.inputs.json").read_bytes()
            (mod/"Base.SC2Data/GameData/UnitData.xml").write_text('<Catalog><CUnit id="New"/></Catalog>')
            with patch.object(B,"save_manifest",side_effect=OSError("manifest failed")):
                with self.assertRaises(OSError):self.build(root,out)
            self.assertEqual((out/"catalog.sqlite").read_bytes(),before);self.assertEqual((out/"catalog.sqlite.inputs.json").read_bytes(),manifest)
    def test_switch_failure_restores_target_and_source_change_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=component(root/"source/Main.SC2Mod","New");mods=root/"Mods";target=component(mods/"Main.SC2Mod","Old");before=(target/"Base.SC2Data/GameData/UnitData.xml").read_bytes()
            original_rename=Path.rename
            def fail_switch(path,destination):
                if path.name.startswith(".Main.SC2Mod.stage-"): raise OSError("switch failed")
                return original_rename(path,destination)
            with patch.object(Path,"rename",fail_switch),redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):D.deploy_mod(source,mods,clean=True)
            self.assertEqual((target/"Base.SC2Data/GameData/UnitData.xml").read_bytes(),before)
            original_copy=D.shutil.copytree
            def changed_source(src,dst,*args,**kwargs):
                result=original_copy(src,dst,*args,**kwargs)
                if Path(src)==source:(source/"Base.SC2Data/GameData/UnitData.xml").write_text('<Catalog><CUnit id="Changed"/></Catalog>')
                return result
            with patch.object(D.shutil,"copytree",changed_source),redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):D.deploy_mod(source,mods,clean=True)
            self.assertEqual((target/"Base.SC2Data/GameData/UnitData.xml").read_bytes(),before)
    def test_recovery_failure_preserves_directories_and_reports_paths(self):
        from sc2_publication import PublicationRecoveryError
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=component(root/"source/Main.SC2Mod","New");mods=root/"Mods";target=component(mods/"Main.SC2Mod","Old")
            original_rename=Path.rename
            def fail_publication_and_recovery(path,destination):
                if path.name.startswith(".Main.SC2Mod.stage-") or path.name==".Main.SC2Mod.sc2-previous":raise OSError("injected rename failure")
                return original_rename(path,destination)
            with patch.object(Path,"rename",fail_publication_and_recovery),redirect_stdout(io.StringIO()):
                with self.assertRaises(PublicationRecoveryError) as error:D.deploy_mod(source,mods,clean=True)
            self.assertIn(str(target),str(error.exception));self.assertIn("recovery was incomplete",str(error.exception))
            self.assertTrue((mods/".Main.SC2Mod.sc2-previous").exists());self.assertEqual(len(list(mods.glob(".Main.SC2Mod.stage-*"))),1)
    def test_merge_clean_backup_rotation_and_manual_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=component(root/"source/Main.SC2Mod","New");mods=root/"Mods";target=component(mods/"Main.SC2Mod","Old");(target/"manual.txt").write_text("keep")
            with redirect_stdout(io.StringIO()):D.deploy_mod(source,mods)
            backup=mods/".Main.SC2Mod.sc2-previous";self.assertTrue((target/"manual.txt").exists());self.assertTrue((backup/"manual.txt").exists())
            with redirect_stdout(io.StringIO()):D.deploy_mod(source,mods,clean=True)
            self.assertFalse((target/"manual.txt").exists());self.assertTrue((backup/"manual.txt").exists());self.assertFalse(list(mods.glob(".Main.SC2Mod.sc2-retired-*")))
            (mods/".Main.SC2Mod.sc2-previous.owner.json").unlink()
            before=(target/"Base.SC2Data/GameData/UnitData.xml").read_bytes()
            with redirect_stdout(io.StringIO()),self.assertRaises(ValueError):D.deploy_mod(source,mods,clean=True)
            self.assertEqual((target/"Base.SC2Data/GameData/UnitData.xml").read_bytes(),before);self.assertTrue((backup/"manual.txt").exists())
    def test_backup_link_is_rejected_before_resolving_to_manual_directory(self):
        from sc2_publication import publish_directory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/"target";target.mkdir();stage=root/"stage";stage.mkdir();manual=root/"manual";manual.mkdir();(manual/"human.txt").write_text("keep")
            backup=root/".target.sc2-previous"
            try:backup.symlink_to(manual,target_is_directory=True)
            except OSError as error:self.skipTest("Directory symlink unavailable: "+str(error))
            (root/".target.sc2-previous.owner.json").write_text(json.dumps({"tool":"SC2ModAgent","kind":"fixture","target":str(target.resolve())}))
            with self.assertRaises(ValueError):publish_directory(stage,target,"fixture")
            self.assertTrue((manual/"human.txt").exists());self.assertTrue(target.exists())
    def test_ownership_read_failure_releases_publication_lock(self):
        from sc2_publication import publish_directory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/"target";target.mkdir();stage=root/"stage";stage.mkdir();backup=root/".target.sc2-previous";backup.mkdir();owner=root/".target.sc2-previous.owner.json"
            owner.write_text(json.dumps({"tool":"SC2ModAgent","kind":"fixture","target":str(target.resolve())}))
            original=Path.read_bytes
            def fail_owner(path,*args,**kwargs):
                if path==owner:raise OSError("owner read failed")
                return original(path,*args,**kwargs)
            with patch.object(Path,"read_bytes",fail_owner),self.assertRaises(OSError):publish_directory(stage,target,"fixture")
            self.assertFalse((root/".target.sc2-publish.lock").exists());self.assertTrue(owner.exists());self.assertTrue(target.exists())

    def test_json_explicit_default_identity_and_sqlite_only_preserve_other_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mod=component(root/"Mods/Main.SC2Mod","Old");out=root/"index"
            with patch.object(B,"ROOT",root),patch.object(sys,"argv",["builder","--out",str(out),"--mod-dir",str(mod)]),redirect_stdout(io.StringIO()):self.assertEqual(B.main(),0)
            graph_before=(out/"graph.json").read_bytes();graph_manifest=(out/"graph.json.inputs.json").read_bytes();(out/"manual.txt").write_text("human");(out/"summaries/human.txt").write_text("human summary")
            self.build(root,out,"--mod-dir",str(mod))
            self.assertEqual((out/"graph.json").read_bytes(),graph_before);self.assertEqual((out/"graph.json.inputs.json").read_bytes(),graph_manifest);self.assertEqual((out/"manual.txt").read_text(),"human")
            with patch.object(Q,"ROOT",root),patch.object(Q,"DEFAULT_DB",out/"catalog.sqlite"):
                args=argparse.Namespace(db=str(out/"catalog.sqlite"),graph=str(out/"graph.json"),allow_stale=False)
                store=Q.load_store(args);store.close()  # explicit build is usable without project config
            (out/"catalog.sqlite").rename(out/"catalog.hidden")
            args=argparse.Namespace(db=None,graph=str(out/"graph.json"),allow_stale=False,verify_input_hashes=True)
            with patch.object(Q,"ROOT",root):
                store=Q.load_store(args);self.assertIsInstance(store,Q.JsonCatalogStore);store.nodes;store=None
                (mod/"Base.SC2Data/GameData/UnitData.xml").write_text('<Catalog><CUnit id="Changed"/></Catalog>')
                with self.assertRaises(SystemExit):Q.load_store(args)
                data=json.loads((out/"graph.json").read_text());data["build_id"]="wrong";(out/"graph.json").write_text(json.dumps(data));args.allow_stale=True
                with self.assertRaises(SystemExit):Q.load_store(args)
    def test_legacy_partial_history_still_requires_partial_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/"legacy";out.mkdir();db=out/"catalog.sqlite";sqlite3.connect(db).close()
            (out/"catalog.sqlite.inputs.json").write_text(json.dumps({"version":2,"files":{},"dependencies":{"status":"partial","problems":["old missing dependency"]}}))
            args=argparse.Namespace(db=str(db),graph=str(out/"graph.json"),allow_stale=True)
            with self.assertRaises(SystemExit):Q.load_store(args)
            args.allow_incomplete_dependencies=True
            with redirect_stderr(io.StringIO()) as warning:
                store=Q.load_store(args);store.close();self.assertIn("Historical legacy",warning.getvalue());self.assertIn("PARTIAL",warning.getvalue())
    def test_custom_index_change_and_build_identity_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);mod=component(root/"Mods/Main.SC2Mod","Old");out=root/"custom"
            self.build(root,out,"--mod-dir",str(mod))
            store=self.query(root,out);store.close()
            (mod/"Base.SC2Data/GameData/UnitData.xml").write_text('<Catalog><CUnit id="New"/></Catalog>')
            with self.assertRaises(SystemExit):
                store=self.query(root,out);store.close()
            self.build(root,out,"--mod-dir",str(mod));manifest=out/"catalog.sqlite.inputs.json";data=json.loads(manifest.read_text());data["build_id"]="another-generation";manifest.write_text(json.dumps(data))
            args=argparse.Namespace(db=str(out/"catalog.sqlite"),graph=str(out/"graph.json"),allow_stale=True)
            with self.assertRaises(SystemExit),patch.object(Q,"ROOT",root):
                store=Q.load_store(args);store.close()
if __name__=="__main__":unittest.main()
