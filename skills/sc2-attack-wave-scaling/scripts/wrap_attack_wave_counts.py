from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ADD_COUNT_PARAMS = ["A166DBF3", "24D9A2D7", "B52CD455", "AD14DE85"]

ELEMENT_RE = re.compile(
    r'^    <Element Type="(?P<type>[^"]+)" Id="(?P<id>[0-9A-F]{8})">\r?\n'
    r'.*?^    </Element>\r?\n?',
    re.MULTILINE | re.DOTALL,
)
FUNCTION_DEF_RE = re.compile(
    r'<FunctionDef Type="FunctionDef" Library="(?P<library>[^"]+)" Id="(?P<id>[0-9A-F]{8})"/>'
)
PARAM_REF_RE = re.compile(r'<Parameter Type="Param" Id="([0-9A-F]{8})"/>')
PARAM_DEF_RE = re.compile(
    r'<ParameterDef Type="ParamDef"(?: Library="[^"]+")? Id="(?P<id>[0-9A-F]{8})"/>'
)
NESTED_CALL_RE = re.compile(r'<FunctionCall Type="FunctionCall" Id="([0-9A-F]{8})"/>')


@dataclass(frozen=True)
class Profile:
    add_function: tuple[str, str]
    add_count_params: frozenset[str]
    flexible_function: tuple[str, str]
    flexible_count_param: str
    modifier_function: tuple[str, str]
    modifier_param: str


def build_element_index(text: str) -> dict[str, re.Match[str]]:
    matches = list(ELEMENT_RE.finditer(text))
    counts = Counter(match.group("id") for match in matches)
    duplicates = sorted(element_id for element_id, count in counts.items() if count > 1)
    if duplicates:
        raise RuntimeError("Duplicate Element IDs: " + ", ".join(duplicates))
    return {match.group("id"): match for match in matches}


def function_key(block: str) -> tuple[str, str] | None:
    match = FUNCTION_DEF_RE.search(block)
    if match is None:
        return None
    return match.group("library"), match.group("id")


def parameter_definition(block: str) -> str | None:
    match = PARAM_DEF_RE.search(block)
    return None if match is None else match.group("id")


def collect_targets(
    elements: dict[str, re.Match[str]], profile: Profile
) -> tuple[set[str], int, int]:
    targets: set[str] = set()
    add_calls = 0
    flexible_calls = 0

    for element in elements.values():
        if element.group("type") != "FunctionCall":
            continue
        block = element.group(0)
        key = function_key(block)
        if key == profile.add_function:
            add_calls += 1
        elif key == profile.flexible_function:
            flexible_calls += 1
        else:
            continue

        for parameter_id in PARAM_REF_RE.findall(block):
            parameter = elements.get(parameter_id)
            if parameter is None:
                raise RuntimeError(f"Missing referenced Param element {parameter_id}")
            definition = parameter_definition(parameter.group(0))
            if key == profile.add_function and definition in profile.add_count_params:
                targets.add(parameter_id)
            elif key == profile.flexible_function and definition == profile.flexible_count_param:
                targets.add(parameter_id)

    return targets, add_calls, flexible_calls


def is_wrapped(block: str, elements: dict[str, re.Match[str]], profile: Profile) -> bool:
    nested = NESTED_CALL_RE.search(block)
    if nested is None:
        return False
    nested_element = elements.get(nested.group(1))
    return nested_element is not None and function_key(nested_element.group(0)) == profile.modifier_function


def fresh_id(used_ids: set[str]) -> str:
    while True:
        candidate = secrets.token_hex(4).upper()
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate


def wrap_parameter(
    block: str,
    call_id: str,
    value_parameter_id: str,
    newline: str,
    profile: Profile,
) -> str:
    opening_end = block.index(newline) + len(newline)
    closing = f"    </Element>{newline}"
    if not block.endswith(closing):
        closing = "    </Element>"
    body = block[opening_end : len(block) - len(closing)]

    definition = re.search(r'^        <ParameterDef[^\r\n]+/>\r?\n', body, re.MULTILINE)
    if definition is None:
        raise RuntimeError("Target Param element has no ParameterDef")
    definition_line = definition.group(0)
    payload = body[: definition.start()] + body[definition.end() :]

    outer = (
        block[:opening_end]
        + definition_line
        + f'        <FunctionCall Type="FunctionCall" Id="{call_id}"/>{newline}'
        + f"    </Element>{newline}"
    )
    modifier_call = (
        f'    <Element Type="FunctionCall" Id="{call_id}">{newline}'
        f'        <FunctionDef Type="FunctionDef" Library="{profile.modifier_function[0]}" '
        f'Id="{profile.modifier_function[1]}"/>{newline}'
        f'        <Parameter Type="Param" Id="{value_parameter_id}"/>{newline}'
        f"    </Element>{newline}"
    )
    value_parameter = (
        f'    <Element Type="Param" Id="{value_parameter_id}">{newline}'
        f'        <ParameterDef Type="ParamDef" Library="{profile.modifier_function[0]}" '
        f'Id="{profile.modifier_param}"/>{newline}'
        + payload
        + f"    </Element>{newline}"
    )
    return outer + modifier_call + value_parameter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrap supported SC2 Triggers attack-wave quantity parameters with an integer modifier."
    )
    parser.add_argument("triggers", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Atomically update the Triggers file.")
    mode.add_argument("--check", action="store_true", help="Fail if any target quantity is unwrapped.")
    parser.add_argument("--backup", type=Path, help="Optional backup path outside the map component.")
    parser.add_argument("--add-library", default="Ntve")
    parser.add_argument("--add-function", default="253D7FAD")
    parser.add_argument("--add-count-param", action="append", dest="add_count_params")
    parser.add_argument("--flexible-library", default="67AA1763")
    parser.add_argument("--flexible-function", default="6EB258E9")
    parser.add_argument("--flexible-count-param", default="E7457FB6")
    parser.add_argument("--modifier-library", default="67AA1763")
    parser.add_argument("--modifier-function", default="4F54E5A0")
    parser.add_argument("--modifier-param", default="4D4D221F")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = Profile(
        add_function=(args.add_library, args.add_function.upper()),
        add_count_params=frozenset(args.add_count_params or DEFAULT_ADD_COUNT_PARAMS),
        flexible_function=(args.flexible_library, args.flexible_function.upper()),
        flexible_count_param=args.flexible_count_param.upper(),
        modifier_function=(args.modifier_library, args.modifier_function.upper()),
        modifier_param=args.modifier_param.upper(),
    )

    with args.triggers.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    ET.fromstring(text)
    newline = "\r\n" if "\r\n" in text else "\n"

    elements = build_element_index(text)
    targets, add_calls, flexible_calls = collect_targets(elements, profile)
    pending = [parameter_id for parameter_id in targets if not is_wrapped(elements[parameter_id].group(0), elements, profile)]
    wrapped = len(targets) - len(pending)

    print(f"AIAttackWaveAddUnits4 calls: {add_calls}")
    print(f"Flexible attack-wave calls: {flexible_calls}")
    print(f"Target quantity parameters: {len(targets)}")
    print(f"Already wrapped: {wrapped}")
    print(f"Pending: {len(pending)}")

    if args.check:
        return 0 if not pending else 1
    if not args.apply:
        return 0
    if not pending:
        print("No changes required.")
        return 0

    used_ids = set(elements)
    replacements: list[tuple[int, int, str]] = []
    for parameter_id in pending:
        match = elements[parameter_id]
        call_id = fresh_id(used_ids)
        value_parameter_id = fresh_id(used_ids)
        replacements.append(
            (
                match.start(),
                match.end(),
                wrap_parameter(match.group(0), call_id, value_parameter_id, newline, profile),
            )
        )

    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]

    ET.fromstring(text)
    updated_elements = build_element_index(text)
    updated_targets, _, _ = collect_targets(updated_elements, profile)
    remaining = [
        parameter_id
        for parameter_id in updated_targets
        if not is_wrapped(updated_elements[parameter_id].group(0), updated_elements, profile)
    ]
    if remaining:
        raise RuntimeError(f"Post-transform verification found {len(remaining)} unwrapped quantities")

    if args.backup:
        if args.backup.exists():
            raise FileExistsError(f"Backup already exists: {args.backup}")
        shutil.copy2(args.triggers, args.backup)

    temporary = args.triggers.with_name(args.triggers.name + ".codex.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        shutil.copystat(args.triggers, temporary)
        os.replace(temporary, args.triggers)
    finally:
        if temporary.exists():
            temporary.unlink()

    print(f"Applied wrappers: {len(replacements)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
