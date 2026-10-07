from __future__ import annotations

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from convert_migrated_scripts_to_gui import ELEMENT_RE
from optimize_migrated_target_group import action_references, function_id, reachable_action_containers


COUNT_DEFS = {"A166DBF3", "24D9A2D7", "B52CD455", "AD14DE85"}
REMAPS = {
    "v1-to-native": {
        "A166DBF3": "24D9A2D7",
        "24D9A2D7": "A166DBF3",
        "B52CD455": "B52CD455",
        "AD14DE85": "AD14DE85",
    },
    "legacy-rotation": {
        "A166DBF3": "24D9A2D7",
        "24D9A2D7": "B52CD455",
        "B52CD455": "AD14DE85",
        "AD14DE85": "A166DBF3",
    },
}


def repair(text: str, trigger_ids: list[str], profile: str) -> tuple[str, int]:
    marker = f"AI AddUnits4 difficulty parameter order repaired ({profile})."
    if marker in text:
        raise RuntimeError("Difficulty parameter order was already repaired")
    newline = "\r\n" if "\r\n" in text else "\n"
    root = ET.fromstring(text)
    all_elements = root.findall("Element")
    elements = {element.get("Id", ""): element for element in all_elements}
    if len(elements) != len(all_elements):
        raise RuntimeError("Duplicate Element IDs prevent safe repair")
    calls = []
    for trigger_id in trigger_ids:
        trigger = elements.get(trigger_id)
        if trigger is None or trigger.get("Type") != "Trigger":
            raise RuntimeError(f"Trigger {trigger_id} was not found")
        calls.extend(
            elements[reference.get("Id", "")]
            for container in reachable_action_containers(trigger, elements)
            for reference in action_references(container)
            if function_id(elements[reference.get("Id", "")]) == "253D7FAD"
        )
    if not calls:
        raise RuntimeError("No AIAttackWaveAddUnits4 calls found in target trigger")
    target_params: dict[str, str] = {}
    for call in calls:
        found: dict[str, str] = {}
        for reference in call.findall("Parameter"):
            param_id = reference.get("Id", "")
            param = elements[param_id]
            definition = param.find("ParameterDef")
            if definition is not None and definition.get("Id") in COUNT_DEFS:
                found[definition.get("Id", "")] = param_id
        if set(found) != COUNT_DEFS:
            raise RuntimeError(
                f"Call {call.get('Id')} has unexpected count definitions: {sorted(found)}"
            )
        target_params.update({param_id: old_def for old_def, param_id in found.items()})

    spans = {match.group("id"): (match.start(), match.end()) for match in ELEMENT_RE.finditer(text)}
    edits: list[tuple[int, int, str]] = []
    for param_id, old_def in target_params.items():
        start, end = spans[param_id]
        block = text[start:end]
        pattern = re.compile(
            rf'(<ParameterDef Type="ParamDef" Library="Ntve" Id="){old_def}("/>)'
        )
        replacement, count = pattern.subn(
            rf'\g<1>{REMAPS[profile][old_def]}\g<2>', block, count=1
        )
        if count != 1:
            raise RuntimeError(f"Could not remap parameter {param_id}")
        edits.append((start, end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    text = text.replace(
        "</TriggerData>",
        f"    <!-- {marker} -->{newline}</TriggerData>",
        1,
    )
    ET.fromstring(text)
    return text, len(calls)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("triggers", type=Path)
    parser.add_argument("--trigger-id", action="append", required=True)
    parser.add_argument("--profile", choices=sorted(REMAPS), default="v1-to-native")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    with args.triggers.open("r", encoding="utf-8", newline="") as stream:
        original = stream.read()
    result, calls = repair(original, args.trigger_id, args.profile)
    print(
        f"{args.triggers}: repaired_add_units4_calls={calls} "
        f"apply={'yes' if args.apply else 'no'}"
    )
    if not args.apply:
        return 0
    if args.backup is None:
        raise RuntimeError("--backup is required with --apply")
    args.backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.triggers, args.backup)
    with args.triggers.open("w", encoding="utf-8", newline="") as stream:
        stream.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
