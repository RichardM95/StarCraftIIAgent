from __future__ import annotations

import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
