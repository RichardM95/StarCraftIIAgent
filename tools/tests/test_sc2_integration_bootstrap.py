"""The launcher uses isolated packages without the Windows venv redirector."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from sc2_integration_runtime import WORKSPACE, runtime_command


@unittest.skipUnless((WORKSPACE / 'integrations/sc2-editor-mcp/.venv/pyvenv.cfg').is_file(),
                     'Install the integration environments first')
class Bootstrap(unittest.TestCase):
    def test_packages_remain_in_the_selected_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'probe.py'
            script.write_text("import json,sys,numpy,unittest\nclass Probe(unittest.TestCase):\n def test_environment(self):\n  print(json.dumps({'prefix':sys.prefix,'numpy_file':numpy.__file__,'numpy_version':numpy.__version__}))\n")
            for package in ('sc2-editor-mcp', 'deepseek-supervisor'):
                with self.subTest(package=package):
                    proc = subprocess.run(runtime_command(package, 'unittest',
                        ['discover', '-s', str(script.parent), '-p', 'probe.py']),
                        capture_output=True, text=True, encoding='utf-8', timeout=30)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    result = json.loads(proc.stdout)
                    expected = WORKSPACE / 'integrations' / package / '.venv'
                    self.assertEqual(Path(result['prefix']), expected)
                    self.assertTrue(Path(result['numpy_file']).is_relative_to(expected))
                    self.assertEqual(result['numpy_version'], '2.5.4')


if __name__ == '__main__':
    unittest.main()
