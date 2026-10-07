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
