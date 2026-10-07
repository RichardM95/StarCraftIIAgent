from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from sc2_catalog_inputs import changed_input, index_inputs, inventory, save_manifest

SPEC = importlib.util.spec_from_file_location("catalog_query_freshness_tool", TOOLS / "sc2-catalog-query.py")
assert SPEC and SPEC.loader
QUERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUERY)


class CatalogFreshnessTests(unittest.TestCase):
    def test_manifest_detects_added_and_removed_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mod = root / "Main.SC2Mod"
            game_data = mod / "Base.SC2Data" / "GameData"
            game_data.mkdir(parents=True)
            first = game_data / "UnitData.xml"
            first.write_text("<Catalog/>", encoding="utf-8")
            index = root / "catalog.sqlite"
            index.touch()
            files = index_inputs(root, [mod])
            save_manifest(index, inventory(files))
            self.assertIsNone(changed_input(index, files))
            added = game_data / "EffectData.xml"
            added.write_text("<Catalog/>", encoding="utf-8")
            self.assertEqual(added, changed_input(index, index_inputs(root, [mod])))
            added.unlink()
            first.unlink()
            self.assertEqual(first, changed_input(index, index_inputs(root, [mod])))

    def test_manifest_hash_detects_same_size_restored_timestamp_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "UnitData.xml"
            source.write_text("<Catalog/>", encoding="utf-8")
            index = root / "catalog.sqlite"
            index.touch()
            save_manifest(index, inventory([source]))
            before = source.stat()
            source.write_text("<Catxlog/>", encoding="utf-8")
            os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
            self.assertIsNone(changed_input(index, [source]))
            self.assertEqual(source, changed_input(index, [source], verify_hashes=True))

    def test_changed_catalog_blocks_default_query_but_allows_historical_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "catalog.sqlite"
            sqlite3.connect(database).close()
            mod = root / "Main.SC2Mod"
            game_data = mod / "Base.SC2Data" / "GameData"
            game_data.mkdir(parents=True)
            catalog = game_data / "UnitData.xml"
            catalog.write_text('<Catalog><CUnit id="Marine"/></Catalog>', encoding="utf-8")
            os.utime(database, (1000, 1000))
            os.utime(catalog, (2000, 2000))
            args = argparse.Namespace(db=str(database), graph=str(root / "graph.json"), allow_stale=False)
            with (
                patch.object(QUERY, "ROOT", root),
                patch.object(QUERY, "DEFAULT_DB", database),
                patch.object(QUERY, "find_project_mods", return_value=[mod]),
                patch.object(QUERY, "load_project_config", return_value={"project": {"resolve_dependencies_recursive": False}}),
            ):
                initial_store = QUERY.SqliteCatalogStore(database)
                self.assertEqual(catalog, QUERY.stale_default_index_input(initial_store))
                initial_store.close()
                with self.assertRaises(SystemExit):
                    QUERY.load_store(args)
                args.allow_stale = True
                store = QUERY.load_store(args)
                store.close()
                graph = root / "json" / "graph.json"
                graph.parent.mkdir()
                graph.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
                os.utime(graph, (1000, 1000))
                args.db = str(root / "missing.sqlite")
                args.graph = str(graph)
                with patch.object(QUERY, "DEFAULT_GRAPH", graph):
                    args.allow_stale = False
                    with self.assertRaises(SystemExit):
                        QUERY.load_store(args)


if __name__ == "__main__":
    unittest.main()
