#!/usr/bin/env python3
"""Regression: collect_references must treat nested <Reference value="Family,ID,field"/> like the Reference attribute."""
from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

TARGET = TOOLS_DIR / "build-sc2-catalog-graph.py"
MODULE_NAME = "catalog_graph_child_reference_test_target"


def load_target():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, TARGET)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves the defining module through sys.modules during exec_module.
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


graph = load_target()


def fixture(body: str) -> ET.Element:
    return ET.fromstring(f"<CUpgrade id=\"Example\">{body}</CUpgrade>")


def collect(elem: ET.Element):
    # Six positional args as build_graph constructs it; no parent attribute.
    defn = graph.Definition("local_mod", "fixture", "fixture.xml", "CUpgrade", "Example", None)
    edges: set = set()
    graph.collect_references(defn, elem, "Example", edges)
    return edges


def modifies(edges):
    return {e for e in edges if e.type == "modifies_field"}


class ChildReferenceTests(unittest.TestCase):
    def test_attribute_form_edge(self):
        edges = modifies(collect(fixture('<EffectArray index="0" Reference="Abil,MorphAbility,Cost.Resource[Vespene]"/>')))
        self.assertEqual(edges, {
            graph.Edge("object:Upgrade:Example", "object:Abil:MorphAbility", "modifies_field",
                       "Abil,MorphAbility,Cost.Resource[Vespene]", "fixture.xml", "local_mod"),
        })

    def test_nested_child_reference_form_parity(self):
        attr_edges = collect(fixture('<EffectArray index="0" Reference="Abil,MorphAbility,Cost.Resource[Vespene]"/>'))
        child_edges = collect(fixture('<EffectArray index="0"><Reference value="Abil,MorphAbility,Cost.Resource[Vespene]"/></EffectArray>'))
        self.assertEqual(modifies(child_edges), modifies(attr_edges))
        self.assertEqual(len(modifies(child_edges)), 1)
        self.assertEqual(len(modifies(attr_edges)), 1)

    def test_both_forms_dedup(self):
        edges = collect(fixture('<EffectArray index="0" Reference="Abil,MorphAbility,Cost.Resource[Vespene]">'
                                '<Reference value="Abil,MorphAbility,Cost.Resource[Vespene]"/></EffectArray>'
                                '<EffectArray index="1"><Reference value="Abil,MorphAbility,Cost.Resource[Vespene]"/></EffectArray>'))
        self.assertEqual(len(modifies(edges)), 1)

    def test_unknown_family_rejected(self):
        edges = collect(fixture('<EffectArray index="0"><Reference value="Nope,MorphAbility,Cost.Resource[Vespene]"/></EffectArray>'))
        self.assertEqual(modifies(edges), set())

    def test_macro_invalid_id_rejected(self):
        for bad in ("##id##", "0", "-1", "bad/id", "bad id"):
            value = f"Abil,{bad},Cost.Resource[Vespene]"
            with self.subTest(value=value):
                edges = collect(fixture(f'<EffectArray index="0"><Reference value="{value}"/></EffectArray>'))
                self.assertEqual(modifies(edges), set())

    def test_unrelated_value_node_not_modifies_field(self):
        edges = collect(fixture('<Name value="Abil,MorphAbility,CostRes"/>'))
        self.assertEqual(modifies(edges), set())


if __name__ == "__main__":
    unittest.main()
