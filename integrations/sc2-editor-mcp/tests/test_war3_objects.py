"""Synthetic unit tests for sc2_mcp.war3_objects.parse_object_bytes.

The module is loaded by file path so the tests do not depend on package
import side effects. No real Warcraft binaries are touched.
"""

import hashlib
import struct
import unittest

from sc2_mcp.war3_objects import parse_object_bytes
from sc2_mcp.errors import SC2Error

_NULL = b"\x00\x00\x00\x00"


def _rc(text):
    raw = text.encode("ascii")
    assert len(raw) == 4, text
    return raw


def _object(old, new, mods):
    old_raw = old if isinstance(old, bytes) else _rc(old)
    new_raw = new if isinstance(new, bytes) else _rc(new)
    return old_raw + new_raw + struct.pack("<i", len(mods)) + b"".join(mods)


def _table(objects):
    return struct.pack("<i", len(objects)) + b"".join(objects)


def _mod(field, value_type, *, level_column=None, int_value=0, float_value=0.0,
         text=None, text_bytes=None):
    raw = bytearray()
    raw += _rc(field)
    raw += struct.pack("<i", value_type)
    if level_column is not None:
        raw += struct.pack("<ii", level_column[0], level_column[1])
    if value_type == 0:
        raw += struct.pack("<i", int_value)
    elif value_type in (1, 2):
        raw += struct.pack("<f", float_value)
    elif value_type == 3:
        if text_bytes is None:
            assert text is not None
            text_bytes = text.encode("utf-8")
        raw += text_bytes + b"\x00"
    else:
        raise AssertionError("bad test value type")
    return bytes(raw)+_NULL


def _file(version=2, original=(), custom=(), tail=b""):
    return (
        struct.pack("<i", version)
        + _table(list(original))
        + _table(list(custom))
        + tail
    )


def _codes(result):
    return [d["code"] for d in result["diagnostics"]]


class LayoutTests(unittest.TestCase):
    def test_abilities_full_layout_and_duplicate_fields(self):
        lc = (1, 0)
        mods = [
            _mod("F001", 0, level_column=lc, int_value=7),
            _mod("F001", 0, level_column=lc, int_value=9),  # duplicate field preserved
            _mod("F002", 1, level_column=lc, float_value=1.5),
            _mod("F003", 3, level_column=(2, 0), text="hello"),
        ]
        original = _object("Aaaa", "A001", mods)
        custom = _object("Bbbb", "B001", [_mod("G001", 0, level_column=(1, 0), int_value=3)])
        data = _file(2, [original], [custom])

        result = parse_object_bytes(data, kind="abilities", source="unit-test")

        self.assertEqual(result["version"], 2)
        self.assertEqual(result["kind"], "abilities")
        self.assertTrue(result["has_level_column"])
        self.assertEqual([t["name"] for t in result["tables"]], ["original", "custom"])
        self.assertEqual([t["count"] for t in result["tables"]], [1, 1])
        self.assertEqual(result["source"], "unit-test")
        self.assertEqual(result["size"], len(data))
        self.assertEqual(result["source_sha256"], hashlib.sha256(data).hexdigest())

        obj = result["tables"][0]["objects"][0]
        self.assertEqual(obj["old_id"], "Aaaa")
        self.assertEqual(obj["new_id"], "A001")
        self.assertTrue(obj["new_id_present"])
        ms = obj["modifications"]
        self.assertEqual([m["field_id"] for m in ms], ["F001", "F001", "F002", "F003"])
        self.assertEqual(ms[0]["field_id_raw_hex"], "46303031")
        self.assertEqual(ms[0]["level"], 1)
        self.assertEqual(ms[0]["column"], 0)
        self.assertEqual(ms[0]["value"], 7)
        self.assertEqual(ms[3]["level"], 2)
        self.assertAlmostEqual(ms[2]["value"], 1.5)
        self.assertEqual(ms[3]["value"], "hello")
        self.assertEqual(ms[3]["encoding"], "utf-8")
        self.assertEqual(result["tables"][1]["objects"][0]["new_id"], "B001")
        self.assertTrue(result["complete"])
        self.assertEqual(result["diagnostics"], [])

    def test_destructables_have_no_level_or_column(self):
        mods = [
            _mod("N001", 0, int_value=-3),
            _mod("N002", 2, float_value=2.5),
            _mod("N003", 3, text=""),
        ]
        data = _file(2, [_object("D001", "D002", mods)], [])
        result = parse_object_bytes(data, kind="destructables")
        ms = result["tables"][0]["objects"][0]["modifications"]
        self.assertFalse(result["has_level_column"])
        self.assertIsNone(ms[0]["level"])
        self.assertIsNone(ms[0]["column"])
        self.assertEqual(ms[0]["value"], -3)
        self.assertEqual(ms[1]["type_name"], "float")
        self.assertEqual(ms[2]["value"], "")
        self.assertEqual(ms[2]["encoding"], "utf-8")
        self.assertTrue(result["complete"])

    def test_empty_tables(self):
        result = parse_object_bytes(_file(2, [], []), kind="buffs")
        self.assertEqual([t["count"] for t in result["tables"]], [0, 0])
        self.assertEqual([t["objects"] for t in result["tables"]], [[], []])
        self.assertTrue(result["complete"])

    def test_null_new_id_keeps_raw_hex(self):
        data = _file(2, [_object("F001", _NULL, [_mod("G001", 0, int_value=1)])], [])
        result = parse_object_bytes(data, kind="destructables")
        obj = result["tables"][0]["objects"][0]
        self.assertIsNone(obj["new_id"])
        self.assertFalse(obj["new_id_present"])
        self.assertEqual(obj["new_id_raw_hex"], "00000000")
        self.assertTrue(result["complete"])

    def test_bytearray_input_accepted(self):
        data = bytearray(_file(2, [], []))
        result = parse_object_bytes(data, kind="buffs")
        self.assertEqual(result["version"], 2)


class StringTests(unittest.TestCase):
    def test_utf8_chinese_string(self):
        text = "技能中文"
        mods = [_mod("S001", 3, level_column=(1, 0), text=text)]
        data = _file(2, [_object("C001", "C002", mods)], [])
        result = parse_object_bytes(data, kind="abilities")
        m = result["tables"][0]["objects"][0]["modifications"][0]
        self.assertEqual(m["value"], text)
        self.assertEqual(m["encoding"], "utf-8")
        self.assertEqual(m["raw_hex"], text.encode("utf-8").hex())
        # version 4 + count 4 + header 12 + field 4 + type 4 + level/col 8
        self.assertEqual(m["byte_offset"], 36)
        self.assertTrue(result["complete"])

    def test_gb18030_string_not_mojibake(self):
        text = "中文测试"
        raw = text.encode("gb18030")
        with self.assertRaises(UnicodeDecodeError):
            raw.decode("utf-8")  # must exercise the GB18030 fallback
        mods = [_mod("S001", 3, text_bytes=raw)]
        data = _file(1, [_object("B001", "B002", mods)], [])
        result = parse_object_bytes(data, kind="destructables")
        m = result["tables"][0]["objects"][0]["modifications"][0]
        self.assertEqual(m["value"], text)
        self.assertEqual(m["encoding"], "gb18030")
        self.assertEqual(m["raw_hex"], raw.hex())
        # version 4 + count 4 + header 12 + field 4 + type 4
        self.assertEqual(m["byte_offset"], 28)
        self.assertTrue(result["complete"])

    def test_corrupted_string_keeps_raw_hex(self):
        bad = b"\xff\xff"
        data = _file(2, [_object("E001", "E002", [_mod("X001", 3, text_bytes=bad)])], [])
        result = parse_object_bytes(data, kind="destructables")
        m = result["tables"][0]["objects"][0]["modifications"][0]
        self.assertIsNone(m["value"])
        self.assertEqual(m["encoding"], "unknown")
        self.assertEqual(m["raw_hex"], "ffff")
        self.assertIn("undecodable_string", _codes(result))
        self.assertFalse(result["complete"])

    def test_rawcode_not_ascii_reported(self):
        mod = b"\xff\xff\xff\xff" + struct.pack("<i", 0) + struct.pack("<i", 1)+_NULL
        data = _file(2, [_object("K001", "K002", [mod])], [])
        result = parse_object_bytes(data, kind="destructables")
        m = result["tables"][0]["objects"][0]["modifications"][0]
        self.assertIsNone(m["field_id"])
        self.assertEqual(m["field_id_raw_hex"], "ffffffff")
        self.assertIn("rawcode_not_ascii", _codes(result))


class DiagnosticTests(unittest.TestCase):
    def test_non_finite_float_reported(self):
        mod = _mod("N001", 1, float_value=float("nan"))
        data = _file(2, [_object("J001", "J002", [mod])], [])
        result = parse_object_bytes(data, kind="destructables")
        m = result["tables"][0]["objects"][0]["modifications"][0]
        self.assertIsNone(m["value"])
        self.assertEqual(m["encoding"], "unknown")
        self.assertIn("non_finite_float", _codes(result))
        self.assertFalse(result["complete"])

    def test_trailing_bytes_reported(self):
        data = _file(2, [], [], tail=b"\xde\xad")
        result = parse_object_bytes(data, kind="destructables")
        self.assertIn("trailing_bytes", _codes(result))
        self.assertFalse(result["complete"])
        self.assertEqual(result["diagnostics"][0]["raw_hex"], "dead")

    def test_unexpected_end_marker_reported(self):
        mod = _mod('N001',0,int_value=1)[:-4]+b'BAD!'
        data = _file(2, [_object('X001','X002',[mod])], [])
        result = parse_object_bytes(data, kind="destructables")
        self.assertIn("unexpected_end_marker", _codes(result))
        self.assertFalse(result["complete"])


class ErrorTests(unittest.TestCase):
    def _assert_code(self, code, data, kind="destructables"):
        with self.assertRaises(SC2Error) as ctx:
            parse_object_bytes(data, kind=kind)
        self.assertEqual(ctx.exception.code, code)

    def test_bad_input_type(self):
        self._assert_code("bad_input", "not-bytes", kind="buffs")

    def test_unsupported_kind(self):
        self._assert_code("unsupported_kind", b"", kind="w3z")

    def test_unsupported_version(self):
        self._assert_code("unsupported_version", struct.pack("<i", 3))

    def test_negative_count(self):
        data = struct.pack("<i", 2) + struct.pack("<i", -1)
        self._assert_code("negative_count", data)

    def test_oversized_count(self):
        data = struct.pack("<i", 2) + struct.pack("<i", 10_000_000)
        self._assert_code("count_out_of_range", data)

    def test_missing_end_marker_out_of_bounds(self):
        mod = _mod('N001',0,int_value=1)[:-4]
        data = struct.pack('<i',2)+_table([_object('N001','N002',[mod])])
        self._assert_code("count_out_of_range", data)

    def test_truncated_object_out_of_bounds(self):
        data = (
            struct.pack("<i", 2)
            + struct.pack("<i", 1)
            + _rc("Aaaa")
            + _rc("A001")
            + struct.pack("<i", 0)
        )
        self._assert_code("out_of_bounds", data)

    def test_unterminated_string(self):
        mod = _rc("S001") + struct.pack("<i", 3) + b"abcdef"
        data = struct.pack("<i", 2) + struct.pack("<i", 1) + _object("H001", "H002", [mod])
        self._assert_code("unterminated_string", data)

    def test_unknown_value_type(self):
        mod = _rc("S001") + struct.pack("<i", 9) + struct.pack("<i", 0)
        data = _file(2, [_object("I001", "I002", [mod])], [])
        self._assert_code("unknown_value_type", data)


if __name__ == "__main__":
    unittest.main()
