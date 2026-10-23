from __future__ import annotations

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"

import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from sc2_dependencies import build_dependency_graph, extract_dependency_refs, render_dependency_tree, dependency_state


class DependencyReferenceTests(unittest.TestCase):
    def test_extracts_pure_local_mod_reference(self) -> None:
        refs = extract_dependency_refs(r"file:Mods\SharedCore.SC2Mod")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["file_path"], "Mods/SharedCore.SC2Mod")
        self.assertTrue(refs[0]["is_local_mod"])
        self.assertFalse(refs[0]["is_network"])

    def test_extracts_bnet_file_fallback(self) -> None:
        refs = extract_dependency_refs(
            r"bnet:Void (Campaign)/0.0/999,file:Campaigns/Void.SC2Campaign"
        )
        self.assertEqual(refs[0]["file_path"], "Campaigns/Void.SC2Campaign")
        self.assertTrue(refs[0]["is_network"])
        self.assertFalse(refs[0]["is_local_mod"])

    def test_marks_bnet_mod_fallback_as_local_shaped_reference(self) -> None:
        refs = extract_dependency_refs(
            r"bnet:Shared/0.0/999,file:Mods\SharedCore.SC2Mod"
        )
        self.assertTrue(refs[0]["is_network"])
        self.assertTrue(refs[0]["is_local_mod"])


class DependencyGraphTests(unittest.TestCase):
    def test_declared_postorder_custom_info_shared_nodes_and_cycle_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            mods = Path(tmp)/'Mods'
            declarations = {'Main': ['Zed', 'Alpha', 'Zed'], 'Zed': ['Deep'], 'Alpha': ['Deep'], 'Deep': []}
            for name, deps in declarations.items():
                p = mods/(name+'.SC2Mod'); p.mkdir(parents=True)
                (p/'ComponentList.SC2Components').write_text('<Components><DataComponent Type="info">CustomInfo</DataComponent></Components>')
                (p/'CustomInfo').write_text('<DocInfo><Dependencies>'+''.join('<Value>file:Mods/'+d+'.SC2Mod</Value>' for d in deps)+'</Dependencies></DocInfo>')
                (p/'DocumentInfo').write_text('<DocInfo/>')  # Must not replace the registered source.
            primary = mods/'Main.SC2Mod'
            graph = build_dependency_graph(primary, mods, official_cache=False)
            self.assertEqual([Path(graph['nodes'][k]['path']).stem for k in graph['traversal_order']], ['Deep','Zed','Alpha','Main'])
            direct = [e for e in graph['edges'] if e['source']==graph['primary']]
            self.assertEqual([e['ordinal'] for e in direct], [0,1,2])
            self.assertTrue(all(e['relation']=='declared' and e['evidence'].endswith('CustomInfo') for e in direct))
            self.assertEqual(dependency_state(graph)['status'], 'complete')
            self.assertEqual(graph['loading_order']['status'], 'confirmed')
            (mods/'Deep.SC2Mod/CustomInfo').write_text('<DocInfo><Dependencies><Value>file:Mods/Main.SC2Mod</Value></Dependencies></DocInfo>')
            graph = build_dependency_graph(primary, mods, official_cache=False)
            self.assertIn('Dependency cycle: Main.SC2Mod -> Zed.SC2Mod -> Deep.SC2Mod -> Main.SC2Mod', graph['errors'])
            (primary/'CustomInfo').write_text('<Broken/>')
            graph = build_dependency_graph(primary, mods, official_cache=False)
            self.assertIn('invalid CustomInfo root', str(graph['errors']))
            self.assertEqual(len(graph['nodes']),1)

    def test_recurses_marks_cycles_and_reports_missing_local_mods(self) -> None:
        mods_dir = Path("E:/Games/StarCraft II/Mods")
        primary = mods_dir / "Main.SC2Mod"
        dependencies = {
            "Main.SC2Mod": [r"file:Mods\Shared.SC2Mod", r"file:Mods\Missing.SC2Mod"],
            "Shared.SC2Mod": [r"file:Mods\Deep.SC2Mod"],
            "Deep.SC2Mod": [r"file:Mods\Main.SC2Mod"],
        }

        def read_dependencies(mod_dir: Path):
            refs = []
            for raw in dependencies[mod_dir.name]:
                refs.extend(extract_dependency_refs(raw))
            return "DocumentInfo", refs, []

        def is_existing_mod(path: Path) -> bool:
            return path.name != "Missing.SC2Mod"

        with (
            patch("sc2_dependencies.read_mod_dependencies", side_effect=read_dependencies),
            patch.object(Path, "is_dir", autospec=True, side_effect=is_existing_mod),
        ):
            graph = build_dependency_graph(primary, mods_dir)

        self.assertEqual(len(graph["nodes"]), 3)
        self.assertEqual(len(graph["missing"]), 1)
        self.assertEqual(graph["missing"][0]["target_name"], "Missing.SC2Mod")
        self.assertTrue(any(edge.get("cycle") for edge in graph["edges"]))
        tree = "\n".join(render_dependency_tree(graph))
        self.assertIn("Deep.SC2Mod", tree)
        self.assertIn("Main.SC2Mod [cycle]", tree)
        self.assertIn("Missing.SC2Mod [MISSING]", tree)

    def test_reports_missing_info_component_metadata(self) -> None:
        mods_dir = Path("E:/Games/StarCraft II/Mods")
        mod_dir = mods_dir / "Broken.SC2Mod"
        with patch(
            "sc2_dependencies.read_mod_dependencies",
            return_value=(None, [], ["Broken.SC2Mod: ComponentList has no Type='info' component"]),
        ):
            graph = build_dependency_graph(mod_dir, mods_dir)

        self.assertEqual(len(graph["errors"]), 1)
        self.assertIn("no Type='info'", graph["errors"][0])


if __name__ == "__main__":
    unittest.main()
