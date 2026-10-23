from __future__ import annotations

import os
os.environ["SC2AGENT_UI_LANGUAGE"] = "en"

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location(
    "catalog_builder_tool",
    TOOLS_DIR / "build-sc2-catalog-graph.py",
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BUILDER
SPEC.loader.exec_module(BUILDER)


class CatalogBuilderDependencyTests(unittest.TestCase):
    def tearDown(self) -> None:
        BUILDER.find_local_mods.cache_clear()

    def test_recursive_dependency_mods_are_included_after_primary(self) -> None:
        mods_dir = Path("E:/Games/StarCraft II/Mods")
        primary = mods_dir / "Main.SC2Mod"
        dependency = mods_dir / "Shared.SC2Mod"
        primary_key = str(primary.resolve(strict=False)).casefold()
        dependency_key = str(dependency.resolve(strict=False)).casefold()
        graph = {
            "primary": primary_key,
            "nodes": {
                primary_key: {"path": str(primary)},
                dependency_key: {"path": str(dependency)},
            },
        }
        with (
            patch.object(BUILDER, "find_project_mods", return_value=[primary]),
            patch.object(
                BUILDER,
                "load_project_config",
                return_value={
                    "paths": {"mods_dir": str(mods_dir)},
                    "project": {"resolve_dependencies_recursive": True},
                },
            ),
            patch.object(BUILDER, "build_dependency_graph", return_value=graph),
        ):
            self.assertEqual(BUILDER.find_local_mods(), (primary, dependency))

    def test_dependency_sources_have_distinct_source_class(self) -> None:
        mods_dir = Path("E:/Games/StarCraft II/Mods")
        primary = mods_dir / "Main.SC2Mod"
        dependency = mods_dir / "Shared.SC2Mod"
        with patch.object(BUILDER, "find_local_mods", return_value=(primary, dependency)):
            self.assertEqual(
                BUILDER.source_info(primary / "Base.SC2Data/GameData/UnitData.xml")[0],
                "local_mod",
            )
            self.assertEqual(
                BUILDER.source_info(dependency / "Base.SC2Data/GameData/UnitData.xml")[0],
                "active_component_dependency",
            )
            self.assertEqual(
                BUILDER.source_info(BUILDER.ROOT / "DataEditorXML" / "Liberty Mod Units.txt")[0],
                "reference_export",
            )


class LocalizationPrecedenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = {}
        for name, source_class, value in (
            ("Reference", "reference_export", "REFERENCE"),
            ("First", "active_component_dependency", "FIRST"),
            ("Second", "active_component_dependency", "SECOND"),
            ("Main", "local_mod", "LOCAL"),
        ):
            path = self.root / (name + ".txt")
            path.write_text("Unit/Name/Shared=" + value, encoding="utf-8")
            self.sources[name] = path
        self.classes = dict(zip(self.sources.values(), (
            "reference_export", "active_component_dependency", "active_component_dependency", "local_mod")))
        for active in (
            patch.object(BUILDER, "source_info", side_effect=lambda p: (self.classes[p], p.stem)),
            patch.object(BUILDER, "source_provenance", return_value={"loading_status": "unconfirmed"}),
        ):
            active.start()
            self.addCleanup(active.stop)

    def read(self, names):
        nodes = {}
        for name in names:
            BUILDER.read_localization(self.sources[name], "GameStrings", nodes)
        return nodes["loc:Unit/Name/Shared"]

    def test_reference_never_hides_active_text_and_local_override_wins(self):
        for order in (("Reference", "First"), ("First", "Reference")):
            with self.subTest(order=order):
                node = self.read(order)
                self.assertEqual(node["value_preview"], "FIRST")
                self.assertEqual(node["source_class"], "active_component_dependency")
                self.assertEqual(len(node["values"]), 2)
        for order in (("Main", "First", "Reference"), ("Reference", "First", "Main")):
            node = self.read(order)
            self.assertEqual(node["value_preview"], "LOCAL")
            self.assertEqual(node["source_class"], "local_mod")
            self.assertEqual(node["value_status"], "resolved")
            self.assertTrue(all(value["casc"] for value in node["values"]))

    def test_conflicting_dependencies_are_ambiguous_in_either_order(self):
        for order in (("First", "Second", "Reference"), ("Second", "Reference", "First")):
            with self.subTest(order=order):
                node = self.read(order)
                self.assertEqual(node["value_status"], "ambiguous")
                self.assertNotIn("value_preview", node)
                self.assertNotIn("source_file", node)
                self.assertEqual(len(node["values"]), 3)
        node = self.read(("First", "Second", "Main"))
        self.assertEqual(node["value_status"], "resolved")
        self.assertEqual(node["value_preview"], "LOCAL")

    def test_identical_values_keep_each_provider_and_reference_stays_reference(self):
        self.sources["Second"].write_text("Unit/Name/Shared=FIRST", encoding="utf-8")
        node = self.read(("First", "Second"))
        self.assertEqual(node["value_status"], "resolved")
        self.assertEqual(len(node["values"]), 2)
        self.assertEqual(self.read(("Reference",))["value_status"], "reference_only")


if __name__ == "__main__":
    unittest.main()
