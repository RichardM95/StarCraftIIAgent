"""``parse_probe_bank`` 的独立测试。

仅以只读方式加载 ``tests/fixtures`` 下的样例, 并构造内存中的合成 Bank 覆盖
拒绝路径。测试使用标准库 ``unittest``, 不新增依赖。
"""

import json
import os
import sys
import unittest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from sc2_mcp.errors import SC2Error
from sc2_mcp.probe_bank import parse_probe_bank


_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "probe_banks")


def _load(name):
    with open(os.path.join(_FIXTURES, name), "rb") as handle:
        return handle.read()


def _attr(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _key_raw(name, kind, value):
    return '<Key name="%s"><Value %s="%s"/></Key>' % (_attr(name), kind, _attr(value))


def _int_key(name, value):
    return _key_raw(name, "int", value)


def _fixed_key(name, value):
    return _key_raw(name, "fixed", value)


def _bool_key(name, value):
    return _key_raw(name, "bool", value)


def _str_key(name, value):
    return _key_raw(name, "string", value)


def _section(name, *keys):
    return '<Section name="%s">%s</Section>' % (_attr(name), "".join(keys))


def _bank(*sections):
    return (
        '<?xml version="1.0" encoding="utf-8"?><Bank version="1">%s</Bank>'
        % "".join(sections)
    ).encode("utf-8")


class FixtureTests(unittest.TestCase):
    def test_warfield_c_is_complete(self):
        result = parse_probe_bank(_load("warfield_c.SC2Bank"))

        self.assertEqual(result["binding"], "historical_unbound")
        self.assertEqual(result["execution"]["run_status"], "FINISHED")
        self.assertEqual(result["execution"]["state"], "complete")
        self.assertEqual(result["verdict"], "complete")

        # 类型保持与原始索引键保留; 未采集的键不补零。
        base = result["sections"]["BaseUpgrade"]
        self.assertEqual(base["Period1"], 24.0)
        self.assertEqual(base["CatalogWeaponCount"], 1)
        self.assertEqual(base["Armor"], "2")
        self.assertNotIn("NoSuchKey", base)

    def test_warfield_d_is_partial(self):
        result = parse_probe_bank(_load("warfield_d.SC2Bank"))

        self.assertEqual(result["execution"]["run_status"], "STARTED")
        self.assertEqual(result["execution"]["state"], "partial")
        self.assertEqual(result["verdict"], "partial")

        # 即使存在通过的断言, 也不能把 partial 提升为 complete。
        with_assertion = parse_probe_bank(
            _load("warfield_d.SC2Bank"),
            assertions=[
                {
                    "id": "pass",
                    "section": "BaseUpgrade",
                    "key": "Period1",
                    "operator": "eq",
                    "expected": 24.0,
                }
            ],
        )
        self.assertEqual(with_assertion["assertions"][0]["result"], "passed")
        self.assertEqual(with_assertion["verdict"], "partial")
        self.assertEqual(with_assertion["execution"]["state"], "partial")

    def test_ht_after_enabled_count_is_one(self):
        result = parse_probe_bank(_load("ht_after.SC2Bank"))
        observations = result["weapon_observations"]

        self.assertEqual(observations["AfterAttack"]["weapon_count"], 1)
        self.assertEqual(observations["AfterAttack"]["enabled_count"], 1)
        self.assertEqual(observations["Released"]["enabled_count"], 1)
        self.assertEqual(observations["Born"]["enabled_count"], 1)
        self.assertEqual(observations["Waiting"]["enabled_count"], 0)

        # 没有实际 WeaponN 键的 section 不产生武器观察。
        self.assertNotIn("CardCaster", observations)
        self.assertNotIn("Catalog", observations)

        # 空字符串与原始索引键保留。
        catalog = result["sections"]["Catalog"]
        self.assertEqual(catalog["AbilArray[9].Link"], "")
        self.assertIn("AbilArray[10].Link", catalog)

    def test_all_fixtures_are_json_serializable(self):
        for name in ("warfield_c.SC2Bank", "warfield_d.SC2Bank", "ht_after.SC2Bank"):
            result = parse_probe_bank(_load(name))
            json.dumps(result)


class AssertionTests(unittest.TestCase):
    def test_failed_assertion_on_finished_run(self):
        result = parse_probe_bank(
            _load("warfield_c.SC2Bank"),
            assertions=[
                {
                    "id": "bad",
                    "section": "BaseUpgrade",
                    "key": "Period1",
                    "operator": "eq",
                    "expected": 999.0,
                }
            ],
        )
        self.assertEqual(result["assertions"][0]["result"], "failed")
        self.assertEqual(result["execution"]["state"], "complete")
        self.assertEqual(result["verdict"], "failed")

    def test_missing_key_is_not_observed(self):
        result = parse_probe_bank(
            _load("warfield_c.SC2Bank"),
            assertions=[
                {
                    "id": "missing",
                    "section": "BaseUpgrade",
                    "key": "NoSuchKey",
                    "operator": "eq",
                    "expected": 1,
                }
            ],
        )
        record = result["assertions"][0]
        self.assertEqual(record["result"], "not_observed")
        self.assertTrue(record["missing"])
        self.assertNotEqual(record["result"], "passed")
        self.assertEqual(result["verdict"], "partial")

    def test_invalid_operator_rejected(self):
        with self.assertRaises(SC2Error):
            parse_probe_bank(
                _bank(_section("S", _int_key("K", 1))),
                assertions=[
                    {
                        "id": "x",
                        "section": "S",
                        "key": "K",
                        "operator": "approx",
                        "expected": 1,
                    }
                ],
            )


class PhaseTests(unittest.TestCase):
    def test_phase_partial(self):
        raw = _bank(
            _section("Run", _str_key("Status", "FINISHED")),
            _section("PhaseX", _str_key("StageStatus", "STARTED")),
        )
        result = parse_probe_bank(raw, expected_phases=["PhaseX"])

        self.assertFalse(result["phases"]["observed"]["PhaseX"]["finished"])
        self.assertFalse(result["phases"]["all_finished"])
        self.assertEqual(result["verdict"], "partial")
        self.assertEqual(result["execution"]["state"], "partial")

    def test_phase_finished(self):
        raw = _bank(
            _section("Run", _str_key("Status", "FINISHED")),
            _section("PhaseX", _str_key("StageStatus", "FINISHED")),
        )
        result = parse_probe_bank(raw, expected_phases=["PhaseX"])

        self.assertTrue(result["phases"]["observed"]["PhaseX"]["finished"])
        self.assertEqual(result["verdict"], "complete")

    def test_status_marker_also_marks_phase_finished(self):
        raw = _bank(
            _section("Run", _str_key("Status", "FINISHED")),
            _section("PhaseY", _str_key("Status", "FINISHED")),
        )
        result = parse_probe_bank(raw, expected_phases=["PhaseY"])

        self.assertTrue(result["phases"]["observed"]["PhaseY"]["finished"])
        self.assertEqual(result["phases"]["observed"]["PhaseY"]["marker"], "Status")

    def test_run_status_does_not_implicitly_fill_missing_phase(self):
        raw = _bank(_section("Run", _str_key("Status", "FINISHED")))
        result = parse_probe_bank(raw, expected_phases=["MissingPhase"])

        self.assertFalse(result["phases"]["observed"]["MissingPhase"]["finished"])
        self.assertEqual(result["verdict"], "partial")


class BindingTests(unittest.TestCase):
    def test_old_run_id_rejected(self):
        raw = _bank(
            _section(
                "Run",
                _str_key("Status", "FINISHED"),
                _str_key("RunId", "run-old"),
            )
        )
        with self.assertRaises(SC2Error) as ctx:
            parse_probe_bank(raw, expected_run_id="run-new")
        self.assertEqual(ctx.exception.code, "stale_probe_bank")

    def test_missing_run_id_rejected_when_expected(self):
        raw = _bank(_section("Run", _str_key("Status", "FINISHED")))
        with self.assertRaises(SC2Error) as ctx:
            parse_probe_bank(raw, expected_run_id="run-1")
        self.assertEqual(ctx.exception.code, "stale_probe_bank")

    def test_matching_run_id_is_bound(self):
        raw = _bank(
            _section(
                "Run",
                _str_key("Status", "FINISHED"),
                _str_key("RunId", "run-1"),
            )
        )
        bound = parse_probe_bank(raw, expected_run_id="run-1")
        self.assertEqual(bound["binding"], "run_bound")
        self.assertEqual(bound["execution"]["run_id"], "run-1")

        # 不传 expected_run_id 时历史 Bank 可解析, 但绝不能冒充已验证。
        unbound = parse_probe_bank(raw)
        self.assertEqual(unbound["binding"], "historical_unbound")


class RejectionTests(unittest.TestCase):
    def test_nul_rejected(self):
        with self.assertRaises(SC2Error):
            parse_probe_bank(b"<Bank>\x00</Bank>")

    def test_doctype_rejected(self):
        raw = b'<?xml version="1.0"?><!DOCTYPE Bank [<!ENTITY xxe "boom">]><Bank/>'
        with self.assertRaises(SC2Error):
            parse_probe_bank(raw)

    def test_external_doctype_rejected(self):
        raw = b'<?xml version="1.0"?><!DOCTYPE Bank SYSTEM "x.dtd"><Bank/>'
        with self.assertRaises(SC2Error):
            parse_probe_bank(raw)

    def test_entity_reference_rejected(self):
        raw = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE Bank [<!ENTITY xxe "boom">]>'
            b'<Bank><Section name="&xxe;"/></Bank>'
        )
        with self.assertRaises(SC2Error):
            parse_probe_bank(raw)

    def test_duplicate_section_rejected(self):
        raw = _bank(
            _section("S", _str_key("K", "a")),
            _section("S", _str_key("K", "b")),
        )
        with self.assertRaises(SC2Error) as ctx:
            parse_probe_bank(raw)
        self.assertEqual(ctx.exception.code, "probe_bank_duplicate_section")

    def test_duplicate_key_rejected(self):
        raw = _bank(_section("S", _str_key("K", "a"), _str_key("K", "b")))
        with self.assertRaises(SC2Error) as ctx:
            parse_probe_bank(raw)
        self.assertEqual(ctx.exception.code, "probe_bank_duplicate_key")

    def test_non_finite_fixed_rejected(self):
        for value in ("nan", "NaN", "inf", "-inf", "Infinity"):
            with self.assertRaises(SC2Error):
                parse_probe_bank(_bank(_section("S", _fixed_key("F", value))))

    def test_invalid_int_rejected(self):
        with self.assertRaises(SC2Error):
            parse_probe_bank(_bank(_section("S", _int_key("I", "abc"))))

    def test_oversized_input_rejected(self):
        raw = b"<Bank>" + b" " * (8 * 1024 * 1024 + 1) + b"</Bank>"
        with self.assertRaises(SC2Error) as ctx:
            parse_probe_bank(raw)
        self.assertEqual(ctx.exception.code, "probe_bank_too_large")


class WeaponObservationTests(unittest.TestCase):
    def test_cached_unit_weapon_count_is_not_double_counted(self):
        raw = _bank(
            _section(
                "S",
                _int_key("UnitWeaponCount", 2),
                _int_key("Enabled1", 1),
                _str_key("Weapon1", "WeaponA"),
            )
        )
        result = parse_probe_bank(raw)
        observation = result["weapon_observations"]["S"]

        # 实际 WeaponN 键只有一个, 缓存总数 2 不得当作双份攻击。
        self.assertEqual(observation["weapon_count"], 1)
        self.assertEqual(observation["enabled_count"], 1)
        self.assertEqual(observation["cached_total"], 2)
        self.assertTrue(observation["cache_mismatch"])

    def test_two_real_weapons_counted_individually(self):
        raw = _bank(
            _section(
                "S",
                _int_key("UnitWeaponCount", 2),
                _int_key("Enabled1", 1),
                _str_key("Weapon1", "WeaponA"),
                _int_key("Enabled2", 0),
                _str_key("Weapon2", "WeaponB"),
            )
        )
        result = parse_probe_bank(raw)
        observation = result["weapon_observations"]["S"]

        self.assertEqual(observation["weapon_count"], 2)
        self.assertEqual(observation["enabled_count"], 1)
        self.assertFalse(observation["cache_mismatch"])

    def test_weapons_key_is_not_a_weapon_entry(self):
        raw = _bank(_section("S", _int_key("Weapons", 3)))
        result = parse_probe_bank(raw)
        self.assertEqual(result["weapon_observations"], {})


class ValueParsingTests(unittest.TestCase):
    def test_bool_values_parsed(self):
        raw = _bank(
            _section("S", _bool_key("T", "true"), _bool_key("F", "0")),
        )
        result = parse_probe_bank(raw)
        self.assertIs(result["sections"]["S"]["T"], True)
        self.assertIs(result["sections"]["S"]["F"], False)

    def test_uncollected_keys_are_not_filled(self):
        raw = _bank(_section("S", _int_key("Present", 1)))
        result = parse_probe_bank(raw)
        self.assertEqual(result["sections"]["S"], {"Present": 1})


if __name__ == "__main__":
    unittest.main()
