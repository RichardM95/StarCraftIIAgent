from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

SPEC = importlib.util.spec_from_file_location("validate_mod_tool", TOOLS_DIR / "validate-mod.py")
assert SPEC is not None and SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


def parse_with_comments(text: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(text, parser=parser)


class CatalogRuleTests(unittest.TestCase):
    def test_uint64_schema_uses_unsigned_long(self) -> None:
        namespace = {"xs": "http://www.w3.org/2001/XMLSchema"}
        schema = ET.parse(VALIDATE.CATALOG_XSD).getroot()
        uint64 = schema.find("xs:simpleType[@name='simple_uint64']", namespace)
        self.assertIsNotNone(uint64)
        restriction = uint64.find("xs:restriction", namespace)
        self.assertIsNotNone(restriction)
        self.assertEqual(restriction.get("base"), "xs:unsignedLong")

    def test_rejects_non_ascii_xml_comments(self) -> None:
        root = parse_with_comments('<Catalog><!-- 中文 --><CUnit id="UnitA"/></Catalog>')
        issues = VALIDATE.validate_catalog_root(root, "UnitData.xml")
        self.assertTrue(any("Non-ASCII XML comment" in issue for issue in issues))

    def test_rejects_comment_only_catalog(self) -> None:
        root = parse_with_comments("<Catalog><!-- placeholder --></Catalog>")
        issues = VALIDATE.validate_catalog_root(root, "UnitData.xml")
        self.assertTrue(any("Comment-only catalog" in issue for issue in issues))

    def test_accepts_ascii_comment_with_real_entry(self) -> None:
        root = parse_with_comments('<Catalog><!-- unit --><CUnit id="UnitA"/></Catalog>')
        self.assertEqual(VALIDATE.validate_catalog_root(root, "UnitData.xml"), [])


if __name__ == "__main__":
    unittest.main()
