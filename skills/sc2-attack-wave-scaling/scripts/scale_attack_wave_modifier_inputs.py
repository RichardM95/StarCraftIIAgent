from __future__ import annotations

import argparse
import os
import re
import shutil
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
SCRIPT_DIFF_RE = re.compile(
    r'lib67AA1763_gf_AttackWaveModifier\(libLotv_gf_DifficultyValueInt2\('
    r'(?P<a>\d+)\s*,\s*(?P<b>\d+)\s*,\s*(?P<c>\d+)\s*,\s*(?P<d>\d+)\)\)'
)
SCRIPT_LITERAL_RE = re.compile(r'lib67AA1763_gf_AttackWaveModifier\((?P<value>\d+)\)')
SCRIPT_ANY_RE = re.compile(r'lib67AA1763_gf_AttackWaveModifier\(')


def scaled(value: int) -> int:
    return (value * 3 + 3) // 4


def function_key(block: str) -> tuple[str, str] | None:
    match = FUNCTION_DEF_RE.search(block)
    if match is None:
        return None
    return match.group("library"), match.group("id")


def scale_map(triggers: Path, apply: bool, backup: Path | None) -> int:
    with triggers.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    ET.fromstring(text)
    newline = "\r\n" if "\r\n" in text else "\n"
    if MARKER in text:
        print(f"{triggers.parent.name}: already scaled (marker present)")
        return 0

    matches = list(ELEMENT_RE.finditer(text))
    elements = {match.group("id"): match for match in matches}
    if len(elements) != len(matches):
        raise RuntimeError("Duplicate Element IDs prevent safe scaling")

    literal_param_ids: set[str] = set()
    visited_calls: set[str] = set()

    def visit_param(param_id: str) -> None:
        element = elements.get(param_id)
        if element is None or element.group("type") != "Param":
            raise RuntimeError(f"Missing referenced Param element {param_id}")
        block = element.group(0)
        if INT_VALUE_RE.search(block):
            literal_param_ids.add(param_id)
        for call_id in CALL_REF_RE.findall(block):
            visit_call(call_id)

    def visit_call(call_id: str) -> None:
        if call_id in visited_calls:
            return
        visited_calls.add(call_id)
        element = elements.get(call_id)
        if element is None or element.group("type") != "FunctionCall":
            raise RuntimeError(f"Missing referenced FunctionCall element {call_id}")
        for param_id in PARAM_REF_RE.findall(element.group(0)):
            visit_param(param_id)

    modifier_calls = 0
    for element in elements.values():
        if element.group("type") != "FunctionCall":
            continue
        if function_key(element.group(0)) != ("67AA1763", "4F54E5A0"):
            continue
        modifier_calls += 1
        refs = PARAM_REF_RE.findall(element.group(0))
        if len(refs) != 1:
            raise RuntimeError(f"Modifier call {element.group('id')} does not have exactly one input")
        visit_param(refs[0])

    replacements: list[tuple[int, int, str]] = []
    xml_changed = 0
    xml_unchanged = 0
    for param_id in literal_param_ids:
        match = elements[param_id]
        block = match.group(0)

        def replace_value(value_match: re.Match[str]) -> str:
            nonlocal xml_changed, xml_unchanged
            old = int(value_match.group("value"))
            new = scaled(old)
            if new == old:
                xml_unchanged += 1
            else:
                xml_changed += 1
            return f"<Value>{new}</Value>{value_match.group('middle')}<ValueType Type=\"int\"/>"

        updated, count = INT_VALUE_RE.subn(replace_value, block)
        if count != 1:
            raise RuntimeError(f"Expected one integer literal in Param {param_id}, found {count}")
        replacements.append((match.start(), match.end(), updated))

    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]

    script_total = len(SCRIPT_ANY_RE.findall(text))
    script_changed = 0
    script_unchanged = 0

    def replace_script_number(raw: str) -> str:
        nonlocal script_changed, script_unchanged
        old = int(raw)
        new = scaled(old)
        if new == old:
            script_unchanged += 1
        else:
            script_changed += 1
        return str(new)

    def replace_diff(match: re.Match[str]) -> str:
        values = [replace_script_number(match.group(name)) for name in ("a", "b", "c", "d")]
        return (
            "lib67AA1763_gf_AttackWaveModifier("
            "libLotv_gf_DifficultyValueInt2(" + ", ".join(values) + "))"
        )

    text, script_diff_calls = SCRIPT_DIFF_RE.subn(replace_diff, text)

    def replace_literal(match: re.Match[str]) -> str:
        return f"lib67AA1763_gf_AttackWaveModifier({replace_script_number(match.group('value'))})"

    text, script_literal_calls = SCRIPT_LITERAL_RE.subn(replace_literal, text)
    recognized_script_calls = script_diff_calls + script_literal_calls
    if recognized_script_calls != script_total:
        raise RuntimeError(
            f"Unrecognized script modifier expressions: {script_total - recognized_script_calls}"
        )

    marker = f"    <!-- {MARKER} -->{newline}"
    text = text.replace("</TriggerData>", marker + "</TriggerData>", 1)
    ET.fromstring(text)
    print(
        f"{triggers.parent.name}: modifier_calls={modifier_calls}, "
        f"xml_values={xml_changed + xml_unchanged} ({xml_changed} changed), "
        f"script_calls={script_total}, script_values={script_changed + script_unchanged} "
        f"({script_changed} changed)"
    )
    if not apply:
        return 0
    if backup is not None:
        if backup.exists():
            raise FileExistsError(f"Backup already exists: {backup}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(triggers, backup)
    temporary = triggers.with_name(triggers.name + ".codex.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        shutil.copystat(triggers, temporary)
        os.replace(temporary, triggers)
    finally:
        if temporary.exists():
            temporary.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scale AttackWaveModifier unit quantities to ceil(value * 0.75)."
    )
    parser.add_argument("triggers", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    return scale_map(args.triggers, args.apply, args.backup)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
