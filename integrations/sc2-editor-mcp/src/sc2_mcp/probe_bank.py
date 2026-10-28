"""受控 SC2Bank 探针结果回读。

本模块只做只读解析: 给定 ``bytes`` 形式的 SC2Bank XML, 返回可 JSON 序列化的
结果字典。它绝不写回或修改任何文件, 也不推断未采集的数据。

协议要点:

* ``<Bank>`` / ``<Section name=...>`` / ``<Key name=...>`` / ``<Value .../>``。
* ``Value`` 只允许 ``int`` / ``fixed`` / ``bool`` / ``string`` 之一。
* 拒绝 DTD/entity、超过 8 MiB 的输入、重复 section/key、非法值和非有限 fixed。
* 保留空字符串、原始索引键 (如 ``AbilArray[9].Link``), 不补未采集的零值。
* ``Run.Status == FINISHED`` 只表示 execution complete, 不等于断言全部通过。
* 独立 ``expected_run_id`` 必须与 ``Run.RunId`` 精确匹配, 否则抛
  ``SC2Error(stale_probe_bank)``。
* 未传 ``expected_run_id`` 时 binding 标记为 ``historical_unbound``, 绝不冒充
  新 run 已验证。
"""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat

try:  # 以包导入时
    from .errors import SC2Error
except ImportError:  # pragma: no cover - 以顶层模块导入时
    from errors import SC2Error


__all__ = ["parse_probe_bank"]


MAX_BANK_BYTES = 8 * 1024 * 1024

BINDING_RUN_BOUND = "run_bound"
BINDING_HISTORICAL_UNBOUND = "historical_unbound"

EXECUTION_COMPLETE = "complete"
EXECUTION_PARTIAL = "partial"
EXECUTION_UNKNOWN = "unknown"

VERDICT_COMPLETE = "complete"
VERDICT_PARTIAL = "partial"
VERDICT_FAILED = "failed"
VERDICT_UNKNOWN = "unknown"

ASSERTION_PASSED = "passed"
ASSERTION_FAILED = "failed"
ASSERTION_NOT_OBSERVED = "not_observed"

_OPERATORS = ("eq", "ne", "lt", "lte", "gt", "gte")
_VALUE_TYPES = ("int", "fixed", "bool", "flag", "string")

_INT_RE = re.compile(r"^[+-]?\d+$")
_FIXED_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_WEAPON_RE = re.compile(r"^Weapon(\d+)$")


def _fail(code: str, message: str, **details):
    raise SC2Error(code, message, **details)


def _local(tag):
    if not isinstance(tag, str):
        return tag
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _reject_dtd_and_entities(raw: bytes) -> None:
    """用 expat 预扫描, 在构建树之前拒绝 DTD/ENTITY 声明。"""

    parser = expat.ParserCreate()

    def _start_doctype(*_args):
        _fail(
            "probe_bank_dtd_forbidden",
            "SC2Bank probe input must not contain a DTD",
        )

    def _entity_decl(*_args):
        _fail(
            "probe_bank_entity_forbidden",
            "SC2Bank probe input must not declare XML entities",
        )

    def _external_entity_ref(*_args):
        _fail(
            "probe_bank_entity_forbidden",
            "SC2Bank probe input must not reference external entities",
        )

    parser.StartDoctypeDeclHandler = _start_doctype
    parser.EntityDeclHandler = _entity_decl
    parser.ExternalEntityRefHandler = _external_entity_ref
    try:
        parser.Parse(raw, True)
    except SC2Error:
        raise
    except expat.ExpatError as exc:
        _fail(
            "probe_bank_malformed",
            "SC2Bank probe input is not well-formed XML: %s" % (exc,),
        )


def _parse_xml(raw: bytes):
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        _fail(
            "probe_bank_malformed",
            "SC2Bank probe input is not well-formed XML: %s" % (exc,),
        )


def _parse_value(elem, section: str, key: str):
    unknown = sorted(a for a in elem.attrib if a not in _VALUE_TYPES)
    if unknown:
        _fail(
            "probe_bank_invalid_value",
            "Value in section %r key %r has unsupported attribute(s): %s"
            % (section, key, ", ".join(unknown)),
            section=section,
            key=key,
        )

    present = [name for name in _VALUE_TYPES if elem.get(name) is not None]
    if len(present) != 1:
        _fail(
            "probe_bank_invalid_value",
            "Value in section %r key %r must carry exactly one of "
            "int/fixed/bool/string" % (section, key),
            section=section,
            key=key,
        )

    kind = present[0]
    text = elem.get(kind)
    assert text is not None

    if kind == "int":
        stripped = text.strip()
        if not _INT_RE.match(stripped):
            _fail(
                "probe_bank_invalid_value",
                "Invalid int value %r in section %r key %r"
                % (text, section, key),
                section=section,
                key=key,
            )
        return int(stripped, 10)

    if kind == "fixed":
        stripped = text.strip()
        if not _FIXED_RE.match(stripped):
            _fail(
                "probe_bank_invalid_value",
                "Invalid fixed value %r in section %r key %r"
                % (text, section, key),
                section=section,
                key=key,
            )
        value = float(stripped)
        if not math.isfinite(value):
            _fail(
                "probe_bank_invalid_value",
                "Non-finite fixed value %r in section %r key %r"
                % (text, section, key),
                section=section,
                key=key,
            )
        return value

    if kind in ("bool", "flag"):
        stripped = text.strip().lower()
        if stripped in ("1", "true"):
            return True
        if stripped in ("0", "false"):
            return False
        _fail(
            "probe_bank_invalid_value",
            "Invalid bool value %r in section %r key %r" % (text, section, key),
            section=section,
            key=key,
        )

    # string: 原样保留, 包括空字符串。
    return text


def _parse_sections(root) -> dict:
    if _local(root.tag) != "Bank":
        _fail(
            "probe_bank_malformed",
            "Expected a <Bank> root element, found <%s>" % (_local(root.tag),),
        )

    sections: dict = {}
    for section_elem in list(root):
        if _local(section_elem.tag) != "Section":
            _fail(
                "probe_bank_malformed",
                "Unexpected <%s> element inside <Bank>" % (_local(section_elem.tag),),
            )
        section_name = section_elem.get("name")
        if section_name is None:
            _fail(
                "probe_bank_malformed",
                "<Section> element is missing its name attribute",
            )
        if section_name in sections:
            _fail(
                "probe_bank_duplicate_section",
                "Duplicate section %r" % (section_name,),
                section=section_name,
            )

        keys: dict = {}
        for key_elem in list(section_elem):
            if _local(key_elem.tag) != "Key":
                _fail(
                    "probe_bank_malformed",
                    "Unexpected <%s> element inside section %r"
                    % (_local(key_elem.tag), section_name),
                )
            key_name = key_elem.get("name")
            if key_name is None:
                _fail(
                    "probe_bank_malformed",
                    "<Key> element in section %r is missing its name attribute"
                    % (section_name,),
                )
            if key_name in keys:
                _fail(
                    "probe_bank_duplicate_key",
                    "Duplicate key %r in section %r" % (key_name, section_name),
                    section=section_name,
                    key=key_name,
                )

            value_elems = []
            other_elems = []
            for child in list(key_elem):
                if _local(child.tag) == "Value":
                    value_elems.append(child)
                else:
                    other_elems.append(child)
            if other_elems:
                _fail(
                    "probe_bank_malformed",
                    "Unexpected element inside key %r of section %r"
                    % (key_name, section_name),
                )
            if len(value_elems) != 1:
                _fail(
                    "probe_bank_malformed",
                    "Key %r in section %r must contain exactly one <Value>"
                    % (key_name, section_name),
                )

            keys[key_name] = _parse_value(value_elems[0], section_name, key_name)

        sections[section_name] = keys

    return sections


def _lookup(sections: dict, section: str, key: str):
    container = sections.get(section)
    if not container:
        return None
    return container.get(key)


def _is_finished(value) -> bool:
    return isinstance(value, str) and value.strip().upper() == "FINISHED"


def _observe_phases(sections: dict, expected_phases):
    if expected_phases is None:
        return {"expected": [], "observed": {}, "all_finished": None}

    expected = list(expected_phases)
    observed: dict = {}
    all_finished = True

    for name in expected:
        if name in observed:
            continue
        container = sections.get(name)
        if container is None:
            observed[name] = {
                "finished": False,
                "marker": None,
                "status": None,
                "section_present": False,
            }
            all_finished = False
            continue

        finished = False
        marker = None
        status = None
        if "StageStatus" in container:
            marker = "StageStatus"
            status = container["StageStatus"]
            finished = _is_finished(status)
        if not finished and "Status" in container:
            marker = "Status"
            status = container["Status"]
            finished = _is_finished(status)

        observed[name] = {
            "finished": finished,
            "marker": marker,
            "status": status,
            "section_present": True,
        }
        if not finished:
            all_finished = False

    return {"expected": expected, "observed": observed, "all_finished": all_finished}


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _values_equal(left, right) -> bool:
    # bool 与 int 在 Python 中相等, 但探针类型不同, 不应互相冒充。
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


def _compare(operator: str, observed, expected):
    if operator == "eq":
        return (ASSERTION_PASSED if _values_equal(observed, expected) else ASSERTION_FAILED), None
    if operator == "ne":
        return (ASSERTION_FAILED if _values_equal(observed, expected) else ASSERTION_PASSED), None

    if not _is_number(observed) or not _is_number(expected):
        return ASSERTION_FAILED, "incomparable_operands"

    if operator == "lt":
        ok = observed < expected
    elif operator == "lte":
        ok = observed <= expected
    elif operator == "gt":
        ok = observed > expected
    elif operator == "gte":
        ok = observed >= expected
    else:  # pragma: no cover - 已由上层校验
        _fail("invalid_assertion", "Unsupported operator %r" % (operator,))
    return (ASSERTION_PASSED if ok else ASSERTION_FAILED), None


def _run_assertions(sections: dict, assertions):
    results = []
    if assertions is None:
        return results
    if not isinstance(assertions,list) or len(assertions)>1000:
        _fail('invalid_assertion','Assertions must be a list of at most 1000 records')
    identifiers=set()

    for spec in assertions:
        if not isinstance(spec, dict):
            _fail("invalid_assertion", "Each assertion must be a mapping")
        for field in ("id", "section", "key", "operator"):
            if field not in spec:
                _fail(
                    "invalid_assertion",
                    "Assertion is missing required field %r" % (field,),
                    field=field,
                )
        source=spec.get('expected_source')
        if ('expected' in spec)==('expected_source' in spec):
            _fail('invalid_assertion','Specify exactly one expected value or expected_source')
        if source is not None and (not isinstance(source,dict) or set(source)!={'section','key'} or
                any(not isinstance(value,str) for value in source.values())):
            _fail('invalid_assertion','expected_source must identify a section and key')
        expected=_lookup(sections,source['section'],source['key']) if source is not None else spec['expected']
        operator = spec["operator"]
        if any(not isinstance(spec[name],str) or not spec[name] for name in ('id','section','key','operator')):
            _fail('invalid_assertion','Assertion identifiers, section, key and operator must be nonempty strings')
        if spec['id'] in identifiers:_fail('invalid_assertion','Assertion IDs must be unique')
        identifiers.add(spec['id'])
        if operator not in _OPERATORS:
            _fail(
                "invalid_assertion",
                "Unsupported assertion operator %r" % (operator,),
                operator=operator,
            )

        section_name = spec["section"]
        key_name = spec["key"]
        record = {
            "id": spec["id"],
            "section": section_name,
            "key": key_name,
            "operator": operator,
            "expected": expected,
        }
        if source is not None:record['expected_source']=source

        if _lookup(sections, section_name, key_name) is None or (source is not None and expected is None):
            record.update(
                {
                    "observed": None,
                    "missing": True,
                    "result": ASSERTION_NOT_OBSERVED,
                    "reason": "not_observed",
                }
            )
            results.append(record)
            continue

        observed = sections[section_name][key_name]
        outcome, reason = _compare(operator, observed, expected)
        record.update({"observed": observed, "missing": False, "result": outcome})
        if reason is not None:
            record["reason"] = reason
        results.append(record)

    return results


def _is_enabled(value) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    return None


def _observe_weapons(sections: dict) -> dict:
    observations: dict = {}

    for section_name, keys in sections.items():
        indexed = []
        for key_name in keys:
            match = _WEAPON_RE.match(key_name)
            if match is not None:
                indexed.append((int(match.group(1)), key_name))
        if not indexed:
            continue
        indexed.sort(key=lambda item: item[0])

        weapons = []
        enabled_count = 0
        disabled_count = 0
        unknown_count = 0
        for index, weapon_key in indexed:
            enabled_key = "Enabled%d" % index
            enabled_value = keys.get(enabled_key)
            enabled = _is_enabled(enabled_value)
            if enabled is True:
                enabled_count += 1
            elif enabled is False:
                disabled_count += 1
            else:
                unknown_count += 1
            weapons.append(
                {
                    "index": index,
                    "weapon": keys[weapon_key],
                    "enabled": enabled,
                    "enabled_key": enabled_key,
                    "enabled_value": enabled_value,
                }
            )

        cached_key = None
        cached_value = None
        for candidate in ("UnitWeaponCount", "Weapons"):
            if candidate in keys:
                cached_key = candidate
                cached_value = keys[candidate]
                break

        cached_numeric = _is_number(cached_value)
        observations[section_name] = {
            "weapons": weapons,
            "weapon_count": len(weapons),
            "enabled_count": enabled_count,
            "disabled_count": disabled_count,
            "unknown_enabled_count": unknown_count,
            "cached_total_key": cached_key,
            "cached_total": cached_value,
            "cache_mismatch": bool(
                cached_numeric and cached_value != len(weapons)
            ),
        }

    return observations


def _execution_run_state(run_status):
    if run_status is None:
        return EXECUTION_UNKNOWN
    if _is_finished(run_status):
        return EXECUTION_COMPLETE
    return EXECUTION_PARTIAL


def _aggregate_verdict(execution_state: str, phases: dict, assertion_results) -> str:
    if any(item["result"] == ASSERTION_FAILED for item in assertion_results):
        return VERDICT_FAILED
    if execution_state == EXECUTION_PARTIAL:
        return VERDICT_PARTIAL
    if phases.get("all_finished") is False:
        return VERDICT_PARTIAL
    if any(item["result"] == ASSERTION_NOT_OBSERVED for item in assertion_results):
        return VERDICT_PARTIAL
    if execution_state == EXECUTION_UNKNOWN:
        return VERDICT_UNKNOWN
    return VERDICT_COMPLETE


def parse_probe_bank(
    raw: bytes,
    expected_run_id: str | None = None,
    expected_phases: list[str] | None = None,
    assertions: list[dict] | None = None,
) -> dict:
    """解析一次受控 SC2Bank 探针的字节结果。

    参数:
        raw: SC2Bank XML 字节。仅读取, 不修改。
        expected_run_id: 期望的 ``Run.RunId``; 传入时必须精确匹配, 否则抛
            ``SC2Error(stale_probe_bank)``。不传时按历史 Bank 处理。
        expected_phases: 期望完成的阶段 section 名列表。每个阶段由该 section 的
            ``StageStatus`` 或 ``Status`` 等于 ``FINISHED`` 标识。
        assertions: 断言字典列表, 每项含 ``id`` / ``section`` / ``key`` /
            ``operator`` / ``expected``。

    返回可 JSON 序列化的结果字典, 包含 ``sections`` / ``execution`` /
    ``verdict`` / ``phases`` / ``assertions`` / ``weapon_observations`` /
    ``binding``。
    """

    if not isinstance(raw, (bytes, bytearray)):
        _fail("probe_bank_invalid_input", "raw probe bank must be bytes")
    raw = bytes(raw)

    if len(raw) > MAX_BANK_BYTES:
        _fail(
            "probe_bank_too_large",
            "SC2Bank probe input is %d bytes, exceeding the %d byte limit"
            % (len(raw), MAX_BANK_BYTES),
            size=len(raw),
            limit=MAX_BANK_BYTES,
        )

    _reject_dtd_and_entities(raw)
    root = _parse_xml(raw)
    sections = _parse_sections(root)

    run_status = _lookup(sections, "Run", "Status")
    run_id = _lookup(sections, "Run", "RunId")

    if expected_run_id is None:
        binding = BINDING_HISTORICAL_UNBOUND
        bound_run_id = run_id
    else:
        if not isinstance(run_id, str) or run_id != expected_run_id:
            _fail(
                "stale_probe_bank",
                "Probe bank Run.RunId %r does not match expected run id %r"
                % (run_id, expected_run_id),
                expected_run_id=expected_run_id,
                actual_run_id=run_id,
            )
        binding = BINDING_RUN_BOUND
        bound_run_id = run_id

    phases = _observe_phases(sections, expected_phases)
    assertion_results = _run_assertions(sections, assertions)

    run_state = _execution_run_state(run_status)
    if run_state == EXECUTION_COMPLETE and phases.get("all_finished") is False:
        execution_state = EXECUTION_PARTIAL
    else:
        execution_state = run_state

    execution = {
        "run_status": run_status,
        "run_state": run_state,
        "state": execution_state,
        "run_id": bound_run_id,
    }

    verdict = _aggregate_verdict(execution_state, phases, assertion_results)

    result = {
        "sections": sections,
        "execution": execution,
        "verdict": verdict,
        "phases": phases,
        "assertions": assertion_results,
        "weapon_observations": _observe_weapons(sections),
        "binding": binding,
    }

    try:
        return json.loads(json.dumps(result))
    except (TypeError, ValueError) as exc:
        _fail(
            "probe_bank_not_serializable",
            "Probe result is not JSON serializable: %s" % (exc,),
        )
