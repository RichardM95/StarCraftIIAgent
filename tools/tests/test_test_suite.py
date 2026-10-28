from __future__ import annotations

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"

import importlib.util
import io
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location("test_suite_tool", TOOLS_DIR / "test-suite.py")
assert SPEC is not None and SPEC.loader is not None
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)


class DependencyValidationTests(unittest.TestCase):
    def fixture(self, root, relative, dependency=''):
        p = root / relative
        p.mkdir(parents=True)
        (p / 'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">DocumentInfo</DataComponent></Components>')
        (p / 'DocumentInfo').write_text('<DocInfo><Dependencies>' +
            ('<Value>file:' + dependency + '</Value>' if dependency else '') + '</Dependencies></DocInfo>')
        return p

    def commands(self, root, target, config, *flags):
        commands = []
        with patch.object(SUITE, 'REPO_ROOT', root), patch.object(SUITE, 'load_project_config', return_value=config), \
             patch.object(sys, 'argv', ['suite', '--scope', 'mod', '--mod-dir', str(target), *flags]), \
             patch.object(SUITE, 'run_step', side_effect=lambda name, cmd, verbose: commands.append(cmd) or True), redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.main(), 0)
        return commands

    def test_foreign_target_checks_its_own_roots_and_does_not_inherit_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = self.fixture(root, 'old/Mods/Main.SC2Mod')
            target = self.fixture(root, 'new/Mods/Main.SC2Mod', 'Mods/Shared.SC2Mod')
            shared = self.fixture(root, 'new/Mods/Shared.SC2Mod')
            config = {'paths': {'mods_dir': str(old.parent)}, 'project': {'primary_mod': old.name, 'resolve_dependencies_recursive': False},
                      'validation': {'include_dependencies': True, 'exclude_mods': ['Shared.SC2Mod']}}
            campaigns, cache = root / 'archive', root / 'cache'
            commands = self.commands(root, target, config, '--mods-dir', str(target.parent), '--campaigns-dir', str(campaigns), '--official-cache', str(cache), '--locale', 'zhCN')
            self.assertFalse(any('tools/validate-agent-config.py' in c for c in commands))
            inspector = next(c for c in commands if 'tools/inspect-mod-dependencies.py' in c)
            gui = next(c for c in commands if 'tools/sc2-trigger-query.py' in c)
            anchors = next(c for c in commands if 'tools/audit-gamestrings-anchors.py' in c)
            self.assertEqual(anchors[anchors.index('--locale') + 1], 'zhCN')
            for cmd in (inspector, gui, anchors):
                for option, value in (('--mods-dir', target.parent), ('--campaigns-dir', campaigns), ('--official-cache', cache)):
                    self.assertEqual(cmd[cmd.index(option) + 1], str(value))
            self.assertFalse(any(str(shared) in c for c in commands))
            # Explicit scanning wins and the old project's exclusion does not leak.
            commands = self.commands(root, target, config, '--include-dependencies')
            self.assertTrue(any('tools/validate-mod.py' in c and str(shared) in c for c in commands))

    def test_workspace_copy_is_current_project_and_campaign_override_reaches_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.fixture(root, 'source/Main.SC2Mod', 'Campaigns/Story.SC2Campaign')
            mods = root / 'game/Mods'; mods.mkdir(parents=True)
            story = self.fixture(root, 'archive/Story.SC2Campaign')
            config = {'paths': {'mods_dir': str(mods)}, 'project': {'primary_mod': source.name,
                'source_mode': 'workspace_copy', 'source_mod': str(source)}, 'validation': {'include_dependencies': True}}
            commands = self.commands(root, source, config, '--campaigns-dir', 'archive')
            validator = next(c for c in commands if 'tools/validate-agent-config.py' in c)
            self.assertEqual(validator[-2:], ['--campaigns-dir', str(story.parent)])
            self.assertTrue(any('tools/validate-mod.py' in c and str(story) in c for c in commands))

    def test_explicit_target_reaches_ledger_audit(self):
        target = Path('Other/Other.SC2Mod').resolve()
        commands = []
        with patch.object(sys, 'argv', ['suite', '--scope', 'mod', '--mod-dir', str(target)]), \
             patch.object(SUITE, 'load_project_config', return_value={}), \
             patch.object(SUITE, 'find_project_mods', return_value=[target]), \
             patch.object(SUITE, 'run_step', side_effect=lambda name, cmd, verbose: commands.append(cmd) or True), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(SUITE.main(), 0)
        ledger = next(c for c in commands if 'tools/audit-issue-lifecycle.py' in c)
        self.assertEqual(ledger[-2:], ['--target', str(target)])

    def test_reads_dependency_defaults_and_exclusions(self) -> None:
        include, exclusions = SUITE.validation_settings(
            {
                "validation": {
                    "include_dependencies": True,
                    "exclude_mods": ["Heros.SC2Mod"],
                }
            }
        )
        self.assertTrue(include)
        self.assertEqual(exclusions, {"heros.sc2mod"})

    def test_invalid_exclusion_type_does_not_crash_preflight(self) -> None:
        include, exclusions = SUITE.validation_settings(
            {
                "validation": {
                    "include_dependencies": True,
                    "exclude_mods": 42,
                }
            }
        )
        self.assertTrue(include)
        self.assertEqual(exclusions, set())

    @patch.object(SUITE, "build_dependency_graph")
    @patch.object(SUITE, "find_project_mods")
    def test_workspace_copy_keeps_installed_dependencies(self, find_mods, graph):
        source = Path("C:/workspace/source/Main.SC2Mod").resolve()
        installed = Path("D:/StarCraft II/Mods").resolve()
        find_mods.return_value = [source]
        graph.return_value = {"nodes": {}, "missing": [], "errors": []}
        SUITE.dependency_validation_targets(source, {
            "paths": {"mods_dir": str(installed)},
            "project": {"source_mode": "workspace_copy", "source_mod": str(source)}}, set())
        graph.assert_called_once_with(source, installed)
        graph.reset_mock()
        other = Path("E:/OtherMods/Other.SC2Mod").resolve()
        targets, problems = SUITE.dependency_validation_targets(other, {
            "paths": {"mods_dir": str(installed)}}, set())
        self.assertEqual(targets, [])
        self.assertIn("--mods-dir", problems[0])
        graph.assert_not_called()
        with patch.object(Path, "is_dir", return_value=True):
            SUITE.dependency_validation_targets(other, {}, set(), str(other.parent))
        graph.assert_called_once_with(other, other.parent.resolve())

    @patch.object(SUITE, "build_dependency_graph")
    @patch.object(SUITE, "resolve_configured_path")
    def test_excludes_named_dependency(self, resolve_path, build_graph) -> None:
        primary = Path("E:/Games/StarCraft II/Mods/Main.SC2Mod")
        keep = Path("E:/Games/StarCraft II/Mods/Keep.SC2Mod")
        skip = Path("E:/Games/StarCraft II/Mods/Heros.SC2Mod")
        resolve_path.return_value = primary.parent
        build_graph.return_value = {
            "nodes": {
                str(primary.resolve(strict=False)).casefold(): {"path": str(primary)},
                str(keep.resolve(strict=False)).casefold(): {"path": str(keep)},
                str(skip.resolve(strict=False)).casefold(): {"path": str(skip)},
            },
            "missing": [],
            "errors": [],
        }

        targets, problems = SUITE.dependency_validation_targets(
            primary,
            {"paths": {"mods_dir": str(primary.parent)}},
            {"heros.sc2mod"},
        )

        self.assertEqual(targets, [keep])
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
