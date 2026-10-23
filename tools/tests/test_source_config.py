
import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("source_config", TOOLS / "validate-agent-config.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

class SourceConfigTests(unittest.TestCase):
    def test_official_uncertainty_blocks_configuration_and_initialization(self):
        init_spec = importlib.util.spec_from_file_location('strict_source_init', TOOLS / 'init-project.py')
        initializer = importlib.util.module_from_spec(init_spec)
        init_spec.loader.exec_module(initializer)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / 'game/Mods/Main.SC2Mod'
            primary.mkdir(parents=True)
            (primary / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
            (primary / 'DocumentInfo').write_text('<DocInfo/>')
            (root / 'game/Maps/Campaign').mkdir(parents=True)
            config = {'schema_version': 1, 'paths': {'workspace_dir': '.', 'sc2_install_dir': 'game',
                'mods_dir': 'game/Mods', 'campaign_maps_dir': 'game/Maps/Campaign'},
                'project': {'primary_mod': 'Main.SC2Mod', 'data_dir': str(root.with_name(root.name + '-records'))}}
            path = root / 'agent-config.json'
            path.write_text(json.dumps(config))
            before = path.read_bytes()
            graph = {'primary': 'main', 'nodes': {'main': {'name': primary.name, 'path': str(primary)}},
                     'edges': [], 'errors': [], 'missing': [],
                     'official_problems': ['Core/bootstrap loading unconfirmed']}
            for tool, args in ((validator, ['validate']), (initializer, ['init', str(primary), '--dry-run'])):
                with self.subTest(tool=tool.__name__), patch.object(tool, 'REPO_ROOT', root), \
                        patch.object(tool, 'build_dependency_graph', return_value=graph), \
                        patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(tool.main(), 1)
                    self.assertIn('Core/bootstrap loading unconfirmed', output.getvalue())
                self.assertEqual(path.read_bytes(), before)

    def test_one_off_dependency_roots_do_not_rewrite_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, ref in (('game/Mods/Main.SC2Mod', 'Mods/Shared.SC2Mod'),
                                  ('alternate/Mods/Shared.SC2Mod', 'Campaigns/Story.SC2Campaign'),
                                  ('archive/Story.SC2Campaign', None)):
                mod = root / relative; mod.mkdir(parents=True)
                (mod / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
                (mod / 'DocumentInfo').write_text('<DocInfo><Dependencies>' +
                    ('<Value>file:' + ref + '</Value>' if ref else '') + '</Dependencies></DocInfo>')
            (root / 'maps').mkdir()
            config = {'schema_version': 1, 'paths': {'workspace_dir': '.', 'sc2_install_dir': 'game',
                'mods_dir': 'game/Mods', 'campaign_maps_dir': 'maps'}, 'project': {'primary_mod': 'Main.SC2Mod',
                'data_dir': str(root.with_name(root.name + '-records'))}}
            path = root / 'agent-config.json'; path.write_text(json.dumps(config))
            before = path.read_bytes()
            with patch.object(validator, 'REPO_ROOT', root), redirect_stdout(io.StringIO()):
                self.assertEqual(validator.main(), 1)
                self.assertEqual(validator.main(['--mods-dir', 'alternate/Mods', '--campaigns-dir', 'archive']), 0)
            self.assertEqual(path.read_bytes(), before)

    def test_copy_without_deployment_validates_and_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("install", "mods", "maps", "source/Main.SC2Mod", "mods/Shared.SC2Mod"):
                (root / name).mkdir(parents=True)
            for relative, dependency in (("source/Main.SC2Mod", "Shared.SC2Mod"),
                                          ("mods/Shared.SC2Mod", None)):
                mod = root / relative
                (mod / "ComponentList.SC2Components").write_text(
                    '<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
                refs = f'<Value>file:Mods/{dependency}</Value>' if dependency else ''
                (mod / "DocumentInfo").write_text(
                    f'<DocInfo><Dependencies>{refs}</Dependencies></DocInfo>')
            config = {"schema_version": 1, "paths": {
                "workspace_dir": ".", "sc2_install_dir": "install",
                "mods_dir": "mods", "campaign_maps_dir": "maps"}, "project": {
                "primary_mod": "Main.SC2Mod", "data_dir": str(root.with_name(root.name + "-records")), "source_mode": "workspace_copy",
                "source_mod": "source/Main.SC2Mod", "resolve_dependencies_recursive": True}}
            with patch.object(validator, "REPO_ROOT", root), redirect_stdout(io.StringIO()):
                (root / "agent-config.json").write_text(json.dumps(config))
                self.assertEqual(validator.main(), 0)
                del config["project"]["source_mod"]
                (root / "agent-config.json").write_text(json.dumps(config))
                self.assertEqual(validator.main(), 1)

if __name__ == "__main__":
    unittest.main()
