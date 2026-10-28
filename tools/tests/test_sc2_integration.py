"""Registration must preserve user settings and be reversible without overwrites."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('integration_setup', TOOLS / 'sc2-integration.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


@unittest.skipUnless(importlib.util.find_spec('tomlkit'), 'Run in the integration environment for TOML registration tests')
class Registration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / 'codex'
        self.home.mkdir()
        self.settings = self.root / 'settings.json'
        self.settings.write_text(json.dumps({'workspace': str(setup.WORKSPACE)}), encoding='utf-8')
        self.env = patch.dict(os.environ, {'CODEX_HOME': str(self.home),
            'SC2_AGENT_INTEGRATION_CONFIG': str(self.settings)})
        self.env.start()
        self.config = self.home / 'config.toml'
        self.original = 'model = "user-model"\n[mcp_servers.other]\ncommand = "user-tool"\n'
        self.config.write_text(self.original, encoding='utf-8')

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_register_repeat_unregister_preserves_unrelated_configuration(self):
        import tomlkit
        self.assertTrue(setup.register()['changed'])
        registered = self.config.read_bytes()
        self.assertFalse(setup.register()['changed'])
        self.assertEqual(self.config.read_bytes(), registered)
        current = tomlkit.parse(registered.decode()).unwrap()
        self.assertEqual(current['model'], 'user-model')
        self.assertEqual(current['mcp_servers']['other'], {'command': 'user-tool'})
        self.assertEqual(len(list(self.home.glob('config.toml.sc2-agent-*.bak'))), 1)
        setup.register(True)
        self.assertEqual(tomlkit.parse(self.config.read_text()).unwrap(), tomlkit.parse(self.original).unwrap())
        self.assertFalse((self.home / 'skills/sc2-agent-tools/SKILL.md').exists())

    def test_conflicting_server_is_never_overwritten(self):
        self.config.write_text(self.original + '[mcp_servers.sc2-editor]\ncommand = "someone-else"\n')
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already in use'):
            setup.register()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse((self.home / 'skills/sc2-agent-tools/SKILL.md').exists())

    def test_preexisting_identical_server_is_not_claimed_by_registration(self):
        import tomlkit
        parsed = tomlkit.parse(self.original)
        value = setup.expected_servers()['sc2-editor']
        parsed['mcp_servers']['sc2-editor'] = value
        self.config.write_text(tomlkit.dumps(parsed))
        setup.register()
        setup.register(True)
        after = tomlkit.parse(self.config.read_text()).unwrap()
        self.assertEqual(after['mcp_servers']['sc2-editor'], value)

    def test_unregister_refuses_changed_owned_entry(self):
        import tomlkit
        setup.register()
        parsed = tomlkit.parse(self.config.read_text())
        parsed['mcp_servers']['sc2-editor']['tool_timeout_sec'] = 999
        self.config.write_text(tomlkit.dumps(parsed))
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed'):
            setup.register(True)
        self.assertEqual(self.config.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
