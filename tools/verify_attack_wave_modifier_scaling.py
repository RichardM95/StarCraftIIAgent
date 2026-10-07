from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


MARKER = "AttackWaveModifier unit quantities scaled by 75 percent with ceiling."
ELEMENT_RE = re.compile(
    r'^    <Element Type="(?P<type>[^"]+)" Id="(?P<id>[0-9A-F]{8})">\r?\n'
    r'.*?^    </Element>\r?\n?',
    re.MULTILINE | re.DOTALL,
)
FUNCTION_DEF_RE = re.compile(
    r'<FunctionDef Type="FunctionDef" Library="(?P<library>[^"]+)" Id="(?P<id>[0-9A-F]{8})"/>'
)
PARAM_REF_RE = re.compile(r'<Parameter Type="Param" Id="([0-9A-F]{8})"/>')
CALL_REF_RE = re.compile(r'<FunctionCall Type="FunctionCall" Id="([0-9A-F]{8})"/>')
INT_VALUE_RE = re.compile(r'<Value>(?P<value>\d+)</Value>(?P<middle>\s*)<ValueType Type="int"/>')
SCRIPT_RE = re.compile(
    r'lib67AA1763_gf_AttackWaveModifier\('
    r'(?:libLotv_gf_DifficultyValueInt2\('
    r'(?P<a>\d+)\s*,\s*(?P<b>\d+)\s*,\s*(?P<c>\d+)\s*,\s*(?P<d>\d+)\)'
    r'|(?P<value>\d+))\)'
)


def scaled(value: int) -> int:
    return (value * 3 + 3) // 4


def extract(path: Path) -> tuple[dict[str, int], list[int], str]:
    text = path.read_text(encoding="utf-8")
    ET.fromstring(text)
    matches = list(ELEMENT_RE.finditer(text))
    elements = {match.group("id"): match for match in matches}
    if len(elements) != len(matches):
        raise RuntimeError(f"Duplicate Element IDs in {path}")

    values: dict[str, int] = {}
    visited_calls: set[str] = set()

    def visit_param(param_id: str) -> None:
        element = elements.get(param_id)
        if element is None or element.group("type") != "Param":
            raise RuntimeError(f"Missing Param {param_id} in {path}")
        block = element.group(0)
        literal = INT_VALUE_RE.search(block)
        if literal is not None:
            values[param_id] = int(literal.group("value"))
        for call_id in CALL_REF_RE.findall(block):
            visit_call(call_id)

    def visit_call(call_id: str) -> None:
        if call_id in visited_calls:
            return
        visited_calls.add(call_id)
        element = elements.get(call_id)
        if element is None or element.group("type") != "FunctionCall":
            raise RuntimeError(f"Missing FunctionCall {call_id} in {path}")
        for param_id in PARAM_REF_RE.findall(element.group(0)):
            visit_param(param_id)

    for element in elements.values():
        if element.group("type") != "FunctionCall":
            continue
        function = FUNCTION_DEF_RE.search(element.group(0))
        if function is None or (function.group("library"), function.group("id")) != (
            "67AA1763",
            "4F54E5A0",
        ):
            continue
        refs = PARAM_REF_RE.findall(element.group(0))
        if len(refs) != 1:
            raise RuntimeError(f"Malformed modifier call {element.group('id')} in {path}")
        visit_param(refs[0])

    script_values: list[int] = []
    for match in SCRIPT_RE.finditer(text):
        if match.group("value") is not None:
            script_values.append(int(match.group("value")))
        else:
            script_values.extend(int(match.group(name)) for name in ("a", "b", "c", "d"))
    return values, script_values, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before_xml, before_script, _ = extract(args.before)
    after_xml, after_script, after_text = extract(args.after)
    if MARKER not in after_text:
        raise RuntimeError(f"Scaling marker missing in {args.after}")
    if before_xml.keys() != after_xml.keys():
        raise RuntimeError(f"Modifier XML leaf set changed in {args.after}")
    for param_id, old in before_xml.items():
        new = after_xml[param_id]
        if new != scaled(old):
            raise RuntimeError(f"Bad XML scaling in {args.after}: {param_id} {old} -> {new}")
    if len(before_script) != len(after_script):
        raise RuntimeError(f"Script modifier value count changed in {args.after}")
    for index, (old, new) in enumerate(zip(before_script, after_script)):
        if new != scaled(old):
            raise RuntimeError(f"Bad script scaling in {args.after}: #{index} {old} -> {new}")
    changed = sum(before_xml[key] != after_xml[key] for key in before_xml)
    changed += sum(old != new for old, new in zip(before_script, after_script))
    print(f"{args.after.parent.name}: verified {len(before_xml) + len(before_script)} values ({changed} changed)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
