"""Dependency and migration boundaries, independent of a local SC2 install."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from sc2_dependencies import build_dependency_graph, dependency_problems
from sc2_triggers import Document, Index, Target, build_index, check, describe, remap_local_ids, references, walk
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("trigger_query", TOOLS / "sc2-trigger-query.py")
QUERY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(QUERY)


def component(path, dependencies=(), body="", library="", unpacked=False):
    path.mkdir(parents=True, exist_ok=True)
    if not unpacked:
        (path / "ComponentList.SC2Components").write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent>'
            '<DataComponent Type="trig">Triggers</DataComponent></Components>')
    (path / "DocumentInfo").write_text('<DocInfo><Dependencies>' + ''.join('<Value>'+v+'</Value>' for v in dependencies) + '</Dependencies></DocInfo>')
    (path / "Triggers").write_text('<TriggerData>' + ('<Library Id="'+library+'">'+body+'</Library>' if library else body) + '</TriggerData>')
    return path


def definition(ident="00000001", extra=""):
    return f'<Element Type="FunctionDef" Id="{ident}"><Identifier>Example</Identifier><FlagAction/>{extra}</Element>'


def call(library, ident="00000001", extra=""):
    return '<Element Type="FunctionCall" Id="A0000001"><FunctionDef Type="FunctionDef" Library="'+library+'" Id="'+ident+'"/>'+extra+'</Element>'


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mods = self.root / "Mods"
        self.campaigns = self.root / "Campaigns"
        self.mods.mkdir()
        self.campaigns.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_unloaded_void_rejected_and_transitive_campaign_loaded(self):
        liberty = component(self.mods / "Liberty.SC2Mod", body=definition(), library="Lbty")
        void = component(self.mods / "Void.SC2Mod", body=definition(), library="Lotv")
        story = component(self.campaigns / "Story.SC2Campaign", ['file:Mods/Void.SC2Mod'])
        target = component(self.root / "Mission.SC2Map", ['file:Mods/Liberty.SC2Mod'], call("Lotv"))
        result = check(Target(target, self.mods, self.campaigns))
        self.assertIn("missing/unloaded Lotv:FunctionDef:00000001", str(result["errors"]))
        (target / "DocumentInfo").write_text('<DocInfo><Dependencies><Value>file:Campaigns/Story.SC2Campaign</Value></Dependencies></DocInfo>')
        active = Target(target, self.mods, self.campaigns)
        self.assertEqual(check(active)["status"], "static validation passed")
        self.assertEqual(active.libraries()["libraries"][0]["library"], "Lotv")
        self.assertNotIn(str(liberty), str(active.libraries()))

    def test_metadata_is_not_library_registration(self):
        p = self.mods / "Liberty.SC2Mod"
        libs = p / "Base.SC2Data/TriggerLibs"
        libs.mkdir(parents=True)
        (libs / "LibraryList.xml").write_text('<TriggerData><library id="99" external="TriggerLibs/Test"/></TriggerData>')
        (libs / "Test.SC2Lib").write_text('<TriggerData><Standard Id="Lbty"/>'+definition()+'</TriggerData>')
        target = component(self.root / "Mission.SC2Map", ['file:Mods/Liberty.SC2Mod'], call("Lbty"))
        active = Target(target, self.mods, self.campaigns)
        self.assertTrue(active.problems)
        self.assertEqual(active.libraries()["libraries"][0]["library"], "Lbty")
        self.assertNotEqual(check(active)["status"], "static validation passed")
        (p / "DocumentInfo").write_text('<DocInfo/>')
        self.assertEqual(check(Target(target, self.mods, self.campaigns))["status"], "static validation passed")
        (libs / "Test.SC2Lib").unlink()
        self.assertIn("missing or ambiguous registered library", str(Target(target, self.mods, self.campaigns).problems))

    def test_map_local_not_available_to_mod_and_conflicts_rejected(self):
        mod = component(self.mods / "Main.SC2Mod", body=call("", "00000001"))
        component(self.root / "Map.SC2Map", ['file:Mods/Main.SC2Mod'], definition())
        self.assertTrue(check(Target(mod, self.mods, self.campaigns))["errors"])
        a = component(self.mods / "A.SC2Mod", body=definition(), library="Same")
        b = component(self.mods / "B.SC2Mod", body=definition(), library="Same")
        target = component(self.root / "Other.SC2Map", ['file:Mods/A.SC2Mod','file:Mods/B.SC2Mod'], call("Same"))
        self.assertIn("Ambiguous definition", str(Target(target, self.mods, self.campaigns).problems))

    def test_cross_library_parameter_owner_and_defaults(self):
        params = component(self.mods / "Params.SC2Mod", body='<Element Type="ParamDef" Id="00000002"><Identifier>x</Identifier><ParameterType><Type Value="int"/></ParameterType><Default Type="Param" Library="Params" Id="00000003"/></Element><Element Type="Param" Id="00000003"><Value>5</Value><ValueType Type="int"/></Element>', library="Params")
        fd = component(self.mods / "Fns.SC2Mod", ['file:Mods/Params.SC2Mod'], definition(extra='<Parameter Type="ParamDef" Library="Params" Id="00000002"/>'), "Fns")
        body = call("Fns", extra='<Parameter Type="Param" Id="A0000002"/>') + '<Element Type="Param" Id="A0000002"><ParameterDef Type="ParamDef" Library="Params" Id="00000002"/><Value>1</Value><ValueType Type="int"/></Element>'
        target = component(self.root / "Map.SC2Map", ['file:Mods/Fns.SC2Mod'], body)
        active = Target(target, self.mods, self.campaigns)
        self.assertEqual(check(active)["status"], "static validation passed")
        d = next(d for d in active.documents if d.component == fd)
        details = describe(d, ("Fns","FunctionDef","00000001"), active.resolve)
        self.assertIn('<Value>5</Value>', details["parameters"][0]["default"]["xml"])
        (target / "Triggers").write_text((target / "Triggers").read_text().replace('Library="Params"', 'Library="Fns"'))
        self.assertIn("missing/unloaded Fns:ParamDef", str(check(Target(target, self.mods, self.campaigns))["errors"]))

    def test_missing_parameters_and_subfunctions_fail(self):
        body = definition(extra='<Parameter Type="ParamDef" Library="Fns" Id="00000002"/>') + '<Element Type="ParamDef" Id="00000002"><ParameterType><Type Value="int"/></ParameterType></Element>'
        component(self.mods / "Fns.SC2Mod", body=body, library="Fns")
        target = component(self.root / "Map.SC2Map", ['file:Mods/Fns.SC2Mod'], call("Fns"))
        self.assertIn("parameter ownership/coverage", str(check(Target(target,self.mods,self.campaigns))["errors"]))

    def test_cycles_and_unresolved_network(self):
        a = component(self.mods / "A.SC2Mod", ['file:Mods/B.SC2Mod'])
        b = component(self.mods / "B.SC2Mod", ['file:Mods/A.SC2Mod','bnet:Missing/0.0/1'])
        graph = build_dependency_graph(a,self.mods,campaigns_dir=self.campaigns,strict_external=True)
        self.assertTrue(any(e.get("cycle") for e in graph["edges"]))
        self.assertIn("unresolved dependency", str(dependency_problems(graph)))

    def test_parameter_sibling_order_and_multiple_flag(self):
        params = '<Element Type="ParamDef" Id="00000002"><ParameterType><Type Value="int"/></ParameterType><ParamFlagMultiple/></Element><Element Type="ParamDef" Id="00000003"><ParameterType><Type Value="int"/></ParameterType></Element>'
        fd = definition(extra='<Parameter Type="ParamDef" Library="Fns" Id="00000002"/><Parameter Type="ParamDef" Library="Fns" Id="00000003"/>') + params
        library = component(self.mods / "Fns.SC2Mod", body=fd, library="Fns")
        body = call('Fns', extra='<Parameter Type="Param" Id="A0000002"/><Parameter Type="Param" Id="A0000003"/><Parameter Type="Param" Id="A0000004"/>')
        for ident, parameter in [('A0000002','00000003'),('A0000003','00000002'),('A0000004','00000002')]:
            body += f'<Element Type="Param" Id="{ident}"><ParameterDef Type="ParamDef" Library="Fns" Id="{parameter}"/><Value>1</Value><ValueType Type="int"/></Element>'
        target = component(self.root / 'Map.SC2Map',['file:Mods/Fns.SC2Mod'],body)
        self.assertEqual(check(Target(target,self.mods,self.campaigns))['status'],'static validation passed')
        p = library/'Triggers'
        p.write_text(p.read_text().replace('<ParamFlagMultiple/>',''))
        self.assertIn('coverage',str(check(Target(target,self.mods,self.campaigns))['errors']))

    def test_wrong_literal_type_and_foreign_subfunction(self):
        fd = definition(extra='<Parameter Type="ParamDef" Library="Fns" Id="00000002"/><SubFunctionType Type="SubFuncType" Library="Fns" Id="00000003"/>')
        fd += '<Element Type="ParamDef" Id="00000002"><ParameterType><Type Value="int"/></ParameterType></Element>'
        fd += '<Element Type="SubFuncType" Id="00000003"/><Element Type="SubFuncType" Id="00000004"/>'
        component(self.mods/'Fns.SC2Mod',body=fd,library='Fns')
        body = call('Fns',extra='<Parameter Type="Param" Id="A0000002"/><FunctionCall Type="FunctionCall" Id="A0000003"/>')
        body += '<Element Type="Param" Id="A0000002"><ParameterDef Type="ParamDef" Library="Fns" Id="00000002"/><Value>x</Value><ValueType Type="text"/></Element>'
        body += '<Element Type="FunctionCall" Id="A0000003"><FunctionDef Type="FunctionDef" Library="Fns" Id="00000001"/><SubFunctionType Type="SubFuncType" Library="Fns" Id="00000004"/></Element>'
        target=component(self.root/'Map.SC2Map',['file:Mods/Fns.SC2Mod'],body)
        errors=str(check(Target(target,self.mods,self.campaigns))['errors'])
        self.assertIn('expected int, got text',errors)
        self.assertIn('invalid SubFunctionType',errors)

    def test_template_local_closure_and_migration_names(self):
        directory=TOOLS.parent/'wiki/reference/trigger-templates'
        d=Document(directory/'GuiPatterns.SC2Map/Triggers')
        manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['patterns']),{'initialization','objectives','victory-defeat','regions','timers','waves','difficulty'})
        self.assertFalse(d.duplicates)
        for key,e in d.elements.items():
            for r in references(e,key):
                if not r[0]:self.assertIn(r,d.elements)
            if key[1] in {'Trigger','Variable'}:self.assertTrue(d.name(key))
        game={}
        for line in (d.component/'enUS.SC2Data/LocalizedData/GameStrings.txt').read_text(encoding='utf-8').splitlines():
            k,v=line.split('=',1);game[k]=v
        old_ids={k[2] for k in d.elements}
        raw,strings=remap_local_ids(d.path.read_bytes(),d.names|game,old_ids)
        newroot=ET.fromstring(raw)
        self.assertFalse(old_ids & {e.get('Id') for e in newroot.findall('Element')})
        self.assertTrue(all(e.get('Library')=='Ntve' for e in newroot.iter() if e.get('Library')))
        for e in newroot.iter('Value'):
            if e.text and e.text.startswith('Param/Value/'):
                self.assertIn(e.text,strings)
        for e in newroot.findall('Element'):
            if e.get('Type') in {'Trigger','Variable'}:
                self.assertIn(f"{e.get('Type')}/Name/{e.get('Id')}",strings)

    def test_component_info_mapping_is_not_bypassed(self):
        target=component(self.root/'Map.SC2Map')
        (target/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">OtherInfo</DataComponent></Components>')
        self.assertIn('info component does not exist',str(Target(target,self.mods,self.campaigns).problems))

    def test_target_snapshot_changes_do_not_certify_old_tree(self):
        p=component(self.mods/'Main.SC2Mod',body=definition(),library='Main')
        target=Target(p,self.mods,self.campaigns)
        (p/'Triggers').write_text((p/'Triggers').read_text().replace('Example','Changed'))
        self.assertIn('Target inputs changed',str(check(target)['errors']))

    def test_foreign_target_does_not_borrow_configured_installation(self):
        import argparse
        old=component(self.mods/'Old.SC2Mod')
        new=component(self.root/'New/Mods/New.SC2Mod')
        config={'paths':{'mods_dir':str(self.mods),'sc2_install_dir':str(self.mods.parent)},'project':{'primary_mod':'Old.SC2Mod'}}
        args=argparse.Namespace(target=new,mods_dir=None,campaigns_dir=None)
        target=QUERY.target_for(args,config)
        self.assertEqual(Path(target.graph['mods_dir']),new.parent)
        foreign=component(self.root/'Other/Map.SC2Map')
        # The old installation root in this fixture contains Other, so remove that
        # optional path to model a genuinely unrelated explicitly supplied map.
        config['paths'].pop('sc2_install_dir')
        args.target=foreign
        with self.assertRaisesRegex(ValueError,'--mods-dir'):
            QUERY.target_for(args,config)

    def test_default_templates_are_not_implicitly_executed(self):
        body=definition(extra='<Parameter Type="ParamDef" Library="Fns" Id="00000002"/>')
        body+='<Element Type="ParamDef" Id="00000002"><ParameterType><Type Value="int"/></ParameterType><Default Type="Param" Library="Fns" Id="00000003"/></Element>'
        body+='<Element Type="Param" Id="00000003"><FunctionCall Type="FunctionCall" Library="Fns" Id="00000004"/></Element>'
        body+='<Element Type="FunctionCall" Id="00000004"><FunctionDef Type="FunctionDef" Library="Fns" Id="00000001"/></Element>'
        component(self.mods/'Fns.SC2Mod',body=body,library='Fns')
        local=call('Fns',extra='<Parameter Type="Param" Id="A0000002"/>')+'<Element Type="Param" Id="A0000002"><ParameterDef Type="ParamDef" Library="Fns" Id="00000002"/><Value>1</Value><ValueType Type="int"/></Element>'
        p=component(self.root/'Map.SC2Map',['file:Mods/Fns.SC2Mod'],local)
        self.assertEqual(check(Target(p,self.mods,self.campaigns))['status'],'static validation passed')

    def test_ntve_is_bound_to_registered_core_source(self):
        core=component(self.mods/'Core.SC2Mod')
        libs=core/'Base.SC2Data/TriggerLibs'
        libs.mkdir(parents=True)
        (libs/'LibraryList.xml').write_text('<TriggerData><library id="27" external="TriggerLibs/NativeLib"/></TriggerData>')
        (libs/'NativeLib.TriggerLib').write_text('<TriggerData><Standard Id="Ntve"/>'+definition()+'</TriggerData>')
        p=component(self.root/'Map.SC2Map',['file:Mods/Core.SC2Mod'],call('Ntve'))
        self.assertEqual(check(Target(p,self.mods,self.campaigns))['status'],'static validation passed')
        fake=component(self.mods/'Fake.SC2Mod',body=definition(),library='Ntve')
        self.assertIn('registered Core NativeLib',str(Target(fake,self.mods,self.campaigns).problems))

    def test_index_freshness_and_reference_mode_without_project(self):
        p = component(self.mods / "Liberty.SC2Mod", body=definition(), library="Lbty")
        db = self.root / "triggers.sqlite"
        build_index(db,[self.mods])
        with patch.object(QUERY,"ROOT",self.root), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(QUERY.main(['--db',str(db),'--reference','find','Example']),0)
            self.assertIn('reference_only', output.getvalue())
        with patch.object(QUERY,"ROOT",self.root),redirect_stderr(io.StringIO()):
            self.assertEqual(QUERY.main(['--db',str(db),'find','Example']),1)
        (p / 'DocumentInfo').write_text('<DocInfo><Dependencies/></DocInfo>')
        with self.assertRaisesRegex(ValueError,'stale'):
            Index(db)
        build_index(db,[self.mods])
        (p / 'TriggerStrings.txt').write_text('Trigger/Name/1=X')
        with self.assertRaisesRegex(ValueError,'membership'):
            Index(db)

    def test_failed_build_retains_previous_index_and_excludes_storm(self):
        component(self.mods / "Good.SC2Mod", body=definition(), library="Good")
        storm = self.mods / "Other.StormMod"
        storm.mkdir()
        (storm / 'Triggers').write_text('not XML')
        db = self.root / 'index.sqlite'
        self.assertEqual(build_index(db,[self.mods])['documents'],1)
        before = db.read_bytes()
        component(self.mods / "Broken.SC2Mod", body=definition()+definition(),library="Bad")
        with self.assertRaisesRegex(ValueError,'duplicate'):
            build_index(db,[self.mods])
        self.assertEqual(before,db.read_bytes())

    def test_reference_root_must_be_loaded_and_same_source(self):
        component(self.mods/'Liberty.SC2Mod',body=definition(),library='Lbty')
        void=component(self.mods/'Void.SC2Mod',body=definition(),library='Lotv')
        p=component(self.root/'Map.SC2Map',['file:Mods/Liberty.SC2Mod'],call('Lotv'))
        d=Document(void/'Triggers'); key=('Lotv','FunctionDef','00000001')
        self.assertEqual(QUERY.compatibility(Target(p,self.mods,self.campaigns),d,key)['status'],'incompatible')
        self.assertIn('missing/unloaded',str(check(Target(p,self.mods,self.campaigns))['errors']))
        component(self.campaigns/'Story.SC2Campaign',['file:Mods/Void.SC2Mod'])
        (p/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Campaigns/Story.SC2Campaign</Value></Dependencies></DocInfo>')
        active=Target(p,self.mods,self.campaigns)
        self.assertEqual(QUERY.compatibility(active,d,key)['status'],'libraries_compatible')
        self.assertEqual(check(active)['status'],'static validation passed')
        other=component(self.root/'Reference.SC2Mod',body=definition(extra='<Comment>different</Comment>'),library='Lotv')
        state=QUERY.compatibility(active,Document(other/'Triggers'),key)
        self.assertEqual(state['status'],'incompatible')
        self.assertIn('source differs',str(state['problems']))
        (void/'Triggers').write_text('<TriggerData/>')
        self.assertEqual(QUERY.compatibility(active,d,key)['status'],'unconfirmed')

    def test_case_only_reviewed_map_nodes_can_be_transplanted(self):
        local=definition(extra='<FunctionCall Type="FunctionCall" Library="Lotv" Id="A0000001"/>')+call('Lotv')
        # A map-owned embedded library is migratable only when reviewed explicitly.
        source=component(self.root/'Source.SC2Map',body=local,library='Local')
        component(self.mods/'Void.SC2Mod',body=definition(),library='Lotv')
        target=component(self.root/'Target.SC2Map')
        d=Document(source/'Triggers'); key=('Local','FunctionDef','00000001')
        # Fix the local call reference to its map-owned namespace.
        (source/'Triggers').write_text((source/'Triggers').read_text().replace('Type="FunctionCall" Library="Lotv"','Type="FunctionCall" Library="Local"'))
        d=Document(source/'Triggers')
        record={'sha256':d.sha256,'local_graph':[{'library':k[0],'type':k[1],'id':k[2]} for k in d.elements]}
        active=Target(target,self.mods,self.campaigns)
        self.assertEqual(QUERY.compatibility(active,d,key,case=record)['status'],'incompatible')
        (target/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Void.SC2Mod</Value></Dependencies></DocInfo>')
        active=Target(target,self.mods,self.campaigns)
        self.assertEqual(QUERY.compatibility(active,d,key,case=record)['status'],'libraries_compatible')
        record['local_graph']=record['local_graph'][:1]
        self.assertEqual(QUERY.compatibility(active,d,key,case=record)['status'],'incompatible')
        # Even an explicit allowlist cannot grant mod/library-file transplantation.
        mod=component(self.root/'Source.SC2Mod',body=definition(),library='Local')
        md=Document(mod/'Triggers'); record={'sha256':md.sha256,'local_graph':[{'library':'Local','type':'FunctionDef','id':'00000001'}]}
        self.assertEqual(QUERY.compatibility(active,md,key,case=record)['status'],'incompatible')
        fake=component(self.root/'CopiedNative.SC2Map',body=definition(),library='Ntve')
        fd=Document(fake/'Triggers'); native_key=('Ntve','FunctionDef','00000001')
        record={'sha256':fd.sha256,'local_graph':[{'library':k[0],'type':k[1],'id':k[2]} for k in fd.elements]}
        self.assertEqual(QUERY.compatibility(active,fd,native_key,case=record)['status'],'incompatible')

    def test_multilingual_find_and_index_version(self):
        p=component(self.mods/'Fns.SC2Mod',body=definition(),library='Fns')
        for locale,value in [('enUS','English Action'),('zhCN','中文动作')]:
            strings=p/f'{locale}.SC2Data/LocalizedData/TriggerStrings.txt'
            strings.parent.mkdir(parents=True)
            strings.write_text(f'FunctionDef/Name/lib_Fns_00000001={value}',encoding='utf-8')
        db=self.root/'triggers.sqlite'; build_index(db,[self.mods])
        for term in ['Example','english action','中文动作']:
            for mode in [['--reference'],['--target',str(p),'--mods-dir',str(self.mods)]]:
                with patch.object(QUERY,'ROOT',self.root),redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(QUERY.main(['--db',str(db),*mode,'find',term]),0)
                rows=json.loads(output.getvalue()); self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['name'],'Example')
                self.assertEqual(rows[0]['names']['zhCN'],'中文动作')
        import sqlite3
        with closing(sqlite3.connect(db)) as connection, connection:
            connection.execute("UPDATE meta SET value='1' WHERE key='version'")
        with self.assertRaisesRegex(ValueError,'rebuild'):
            Index(db)

    def test_bounded_walk_checks_hidden_tail_and_cycles(self):
        body=definition(extra='<Parameter Type="ParamDef" Library="Other" Id="00000002"/><FunctionCall Type="FunctionCall" Library="Fns" Id="A0000001"/>')+call('Fns')
        p=component(self.mods/'Fns.SC2Mod',body=body,library='Fns'); d=Document(p/'Triggers')
        active=Target(p,self.mods,self.campaigns); key=('Fns','FunctionDef','00000001')
        full=walk([(d,key)],active.resolve,validate=False)
        for limit in [0,1]:
            bounded=walk([(d,key)],active.resolve,validate=False,node_limit=limit)
            self.assertEqual(bounded['errors'],full['errors'])
            self.assertEqual(bounded['total_nodes'],full['total_nodes'])
            self.assertEqual(bounded['total_resources'],full['total_resources'])
            self.assertEqual(bounded['required_libraries'],full['required_libraries'])
            self.assertLessEqual(len(bounded['nodes']),limit)
        self.assertIn('Other:ParamDef',str(full['errors']))

    def test_no_trigger_registration_is_not_silently_skipped(self):
        p=component(self.mods/'DataOnly.SC2Mod')
        (p/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
        self.assertEqual(check(Target(p,self.mods,self.campaigns))['status'],'not_applicable')
        (p/'ComponentList.SC2Components').unlink(); (p/'Triggers').unlink()
        self.assertIn('absence cannot be confirmed',str(check(Target(p,self.mods,self.campaigns))['errors']))
        (p/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent><DataComponent Type="trig">Missing</DataComponent></Components>')
        self.assertIn('missing registered',str(check(Target(p,self.mods,self.campaigns))['errors']))
        (p/'DocumentInfo').unlink()
        self.assertEqual(check(Target(p,self.mods,self.campaigns))['status'],'failed')

    def test_suite_passes_roots_and_never_applies_catalog_exclusions_to_triggers(self):
        spec=importlib.util.spec_from_file_location('suite',TOOLS/'test-suite.py')
        suite=importlib.util.module_from_spec(spec); spec.loader.exec_module(suite)
        p=component(self.mods/'Main.SC2Mod',body=definition(),library='Main')
        argv=['test-suite.py','--scope','mod','--mod-dir',str(p),'--mods-dir',str(self.mods),
              '--campaigns-dir',str(self.campaigns),'--primary-only','--exclude-mod','Void.SC2Mod']
        with patch.object(sys,'argv',argv),patch.object(suite,'load_project_config',return_value={}),patch.object(suite,'find_project_mods',return_value=[p]),patch.object(suite,'run_step',return_value=True) as run,redirect_stdout(io.StringIO()):
            self.assertEqual(suite.main(),0)
        commands=[args.args[1] for args in run.call_args_list if args.args[0]=='GUI Trigger Dependency Validator']
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][-1],'check')
        self.assertIn(str(self.campaigns),commands[0])
        self.assertIn(str(self.mods),commands[0])
        self.assertNotIn('--primary-only',commands[0]); self.assertNotIn('--exclude-mod',commands[0])

    def test_reference_cli_agrees_with_check_and_allows_research(self):
        component(self.mods/'Liberty.SC2Mod',body=definition(),library='Lbty')
        void=component(self.mods/'Void.SC2Mod',body=definition(),library='Lotv')
        target=component(self.root/'Map.SC2Map',['file:Mods/Liberty.SC2Mod'],call('Lotv'))
        db=self.root/'reference.sqlite'; build_index(db,[self.mods])
        prefix=['--target',str(target),'--mods-dir',str(self.mods),'--db',str(db)]
        for command in [['find','Example'],['show','Lotv:FunctionDef:00000001']]:
            with patch.object(QUERY,'ROOT',self.root),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(QUERY.main([*prefix,'--reference',*command]),0)
            value=json.loads(output.getvalue())
            if isinstance(value,list):value=next(r for r in value if r['library']=='Lotv')
            self.assertEqual(value['compatibility']['status'],'incompatible')
        with patch.object(QUERY,'ROOT',self.root),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(QUERY.main([*prefix,'check']),1)
        self.assertIn('missing/unloaded Lotv',output.getvalue())
        (void/'DocumentInfo').unlink()
        (target/'DocumentInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Void.SC2Mod</Value></Dependencies></DocInfo>')
        active=Target(target,self.mods,self.campaigns)
        self.assertEqual(QUERY.compatibility(active,Document(void/'Triggers'),('Lotv','FunctionDef','00000001'))['status'],'unconfirmed')

    def test_target_find_limit_stops_compatibility_work(self):
        p=component(self.mods/'Fns.SC2Mod',body=''.join(definition(f'{i:08X}') for i in range(1,5)),library='Fns')
        with patch.object(QUERY,'ROOT',self.root),patch.object(QUERY,'compatibility',wraps=QUERY.compatibility) as compatible,redirect_stdout(io.StringIO()) as output:
            self.assertEqual(QUERY.main(['--target',str(p),'--mods-dir',str(self.mods),'find','Example','--limit','1']),0)
        self.assertEqual(len(json.loads(output.getvalue())),1)
        self.assertEqual(compatible.call_count,1)

    def test_curated_case_selection_and_display_limit_preserve_errors(self):
        body=definition('00000001',extra='<Parameter Type="ParamDef" Library="Fns" Id="00000003"/>')+definition('00000002')
        body+='<Element Type="ParamDef" Id="00000003"><ParameterType><TypeElement Type="Preset" Library="Missing" Id="00000004"/></ParameterType></Element>'
        p=component(self.mods/'Fns.SC2Mod',body=body,library='Fns'); d=Document(p/'Triggers')
        db=self.root/'reference.sqlite'; build_index(db,[self.mods])
        records=[]
        for ident in ['00000001','00000002']:
            records.append({'mechanism':'dialogs','case_id':'button-'+ident,'source':'Fns.SC2Mod/Triggers',
                            'type':'FunctionDef','id':ident,'sha256':d.sha256,'local_graph':[
                                {'library':k[0],'type':k[1],'id':k[2]} for k in d.elements]})
        cases=self.root/'cases.json'; cases.write_text(json.dumps({'cases':records}))
        for selection in ['button-00000001','00000001']:
            with patch.object(QUERY,'ROOT',self.root),patch.object(QUERY,'CASES',cases),redirect_stdout(io.StringIO()) as output:
                self.assertEqual(QUERY.main(['--db',str(db),'--reference','examples','dialogs','--case',selection,'--max-nodes','1']),0)
            result=json.loads(output.getvalue()); self.assertEqual(len(result),1)
            self.assertEqual(result[0]['id'],'00000001')
            self.assertEqual(len(result[0]['local_graph']),1)
            self.assertTrue(result[0]['local_graph_truncated'])
            self.assertTrue(result[0]['closure']['truncated'])
            self.assertIn('Missing',str(result[0]['closure']['errors']))
        with patch.object(QUERY,'ROOT',self.root),patch.object(QUERY,'CASES',cases),redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(QUERY.main(['--db',str(db),'--reference','examples','dialogs','--case','unknown']),1)
        self.assertIn('Unknown curated case',errors.getvalue())


if __name__ == '__main__':
    unittest.main()
