from __future__ import annotations

import argparse
import collections
import contextlib
import io
import os
import re
import secrets
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from convert_custom_ai_to_trigger_scripts import convert as stage_conversion
from convert_migrated_scripts_to_gui import convert as gui_conversion


GUI_MARKER = "Migrated AI personality waves converted to GUI actions."
STOP_PERSONALITY_FUNCTION = ("Ntve", "898E65C3")
STOP_TRIGGER_FUNCTION = ("Ntve", "698FE891")
LOTV_PARAMETER_DEFS = {
    "68571483",
    "0A001767",
    "4BA3AD0F",
    "760D9F48",
    "CCED8B10",
    "CBAE34FC",
    "5BD0FB07",
    "E19C724E",
    "46034F7A",
    "6A9C62E7",
    "3E9B2F40",
    "D22511AA",
}


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def element_map(root: ET.Element) -> dict[str, ET.Element]:
    elements = [element for element in root.findall("Element") if element.get("Id")]
    result = {element.get("Id", ""): element for element in elements}
    if len(result) != len(elements):
        raise RuntimeError("Duplicate Element IDs prevent safe conversion")
    return result


def validate_known_parameter_libraries(root: ET.Element) -> None:
    bad: list[str] = []
    for parameter_def in root.findall(".//ParameterDef"):
        parameter_id = parameter_def.get("Id")
        library = parameter_def.get("Library")
        if parameter_id in LOTV_PARAMETER_DEFS and library != "Lotv":
            bad.append(f"{library}:{parameter_id} (expected Lotv)")
        if parameter_id == "4D4D221F" and library != "67AA1763":
            bad.append(f"{library}:{parameter_id} (expected 67AA1763)")
    if bad:
        raise RuntimeError("Invalid cross-library ParameterDef references: " + ", ".join(bad))


def trigger_names(strings_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in strings_text.splitlines():
        if not line.startswith("Trigger/Name/") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[value.strip()] = key.rsplit("/", 1)[-1]
    return result


def personality_names(object_strings_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in object_strings_text.splitlines():
        line = line.lstrip("\ufeff")
        if not line.startswith("AI/Name/") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.rsplit("/", 1)[-1]] = value.strip()
    return result


def rename_legacy_migrated_triggers(
    strings_text: str,
    object_strings_text: str,
    custom_ai: Path,
) -> tuple[str, int]:
    ai_names = personality_names(object_strings_text)
    changed = 0
    definitions = [
        definition
        for definition in ET.parse(custom_ai).getroot().findall("Definition")
        if definition.get("Id") and definition.findall("Step[@Type='Wave']")
    ]
    for definition in definitions:
        definition_id = definition.get("Id", "")
        display_name = ai_names.get(definition_id)
        if not display_name:
            raise RuntimeError(f"Missing AI personality display name for {definition_id}")
        replacements = (
            (
                re.compile(
                    rf"^(Trigger/Name/[0-9A-F]{{8}}=)AI {definition_id} Migrated Waves(?=\r?$)",
                    re.MULTILINE,
                ),
                rf"\g<1>{display_name} Attack Waves",
            ),
            (
                re.compile(
                    rf"^(Trigger/Name/[0-9A-F]{{8}}=)AI {definition_id} Wave (.+?) Async(?=\r?$)",
                    re.MULTILINE,
                ),
                rf"\g<1>{display_name} Attack Wave \g<2> Async",
            ),
        )
        for pattern, replacement in replacements:
            strings_text, count = pattern.subn(replacement, strings_text)
            changed += count
    return strings_text, changed


def validate_start_wiring(
    triggers_text: str,
    strings_text: str,
    object_strings_text: str,
    custom_ai: Path,
    start_trigger_name: str = "Start AI",
) -> tuple[str, list[str]]:
    root = ET.fromstring(triggers_text)
    elements = element_map(root)
    names = trigger_names(strings_text)
    ai_names = personality_names(object_strings_text)
    start_id = names.get(start_trigger_name)
    if start_id is None or start_id not in elements:
        raise RuntimeError(f"Could not locate startup trigger {start_trigger_name!r}")
    definition_ids = [
        definition.get("Id", "")
        for definition in ET.parse(custom_ai).getroot().findall("Definition")
        if definition.get("Id") and definition.findall("Step[@Type='Wave']")
    ]
    migrated_ids = []
    for definition_id in definition_ids:
        display_name = ai_names.get(definition_id)
        if not display_name:
            raise RuntimeError(f"Missing AI personality display name for {definition_id}")
        name = f"{display_name} Attack Waves"
        trigger_id = names.get(name)
        if trigger_id is None or trigger_id not in elements:
            raise RuntimeError(f"Could not locate migrated trigger {name!r}")
        if elements[trigger_id].find("Event") is not None:
            raise RuntimeError(f"Migrated trigger {name!r} must not have its own event")
        migrated_ids.append(trigger_id)

    targets: list[str] = []
    start = elements[start_id]
    for action in start.findall("Action"):
        call = elements.get(action.get("Id", ""))
        if call is None:
            continue
        function = call.find("FunctionDef")
        if function is None or function.get("Library") != "Ntve" or function.get("Id") != "00000116":
            continue
        for parameter_ref in call.findall("Parameter"):
            parameter = elements.get(parameter_ref.get("Id", ""))
            if parameter is None:
                continue
            parameter_def = parameter.find("ParameterDef")
            target = parameter.find("ValueElement")
            if (
                parameter_def is not None
                and parameter_def.get("Library") == "Ntve"
                and parameter_def.get("Id") == "00000182"
                and target is not None
                and target.get("Type") == "Trigger"
            ):
                targets.append(target.get("Id", ""))
    bad = {trigger_id: targets.count(trigger_id) for trigger_id in migrated_ids if targets.count(trigger_id) != 1}
    if bad:
        raise RuntimeError(f"Startup trigger does not run each migrated trigger exactly once: {bad}")
    return start_id, migrated_ids


def normalize_migrated_start_wiring(
    triggers_text: str,
    strings_text: str,
    object_strings_text: str,
    custom_ai: Path,
    start_trigger_name: str,
) -> tuple[str, int, int]:
    root = ET.fromstring(triggers_text)
    elements = element_map(root)
    names = trigger_names(strings_text)
    ai_names = personality_names(object_strings_text)
    start_id = names.get(start_trigger_name)
    if start_id is None or start_id not in elements:
        raise RuntimeError(f"Could not locate startup trigger {start_trigger_name!r}")
    used = set(elements)
    newline = "\r\n" if "\r\n" in triggers_text else "\n"
    removed_events = 0
    added_runs = 0

    definitions = [
        definition
        for definition in ET.parse(custom_ai).getroot().findall("Definition")
        if definition.get("Id") and definition.findall("Step[@Type='Wave']")
    ]
    for definition in definitions:
        definition_id = definition.get("Id", "")
        display_name = ai_names.get(definition_id)
        if not display_name:
            raise RuntimeError(f"Missing AI personality display name for {definition_id}")
        migrated_id = names.get(f"{display_name} Attack Waves")
        if migrated_id is None or migrated_id not in elements:
            raise RuntimeError(f"Missing migrated trigger for AI personality {display_name}")
        migrated = elements[migrated_id]

        for event_ref in list(migrated.findall("Event")):
            event_id = event_ref.get("Id", "")
            event = elements.get(event_id)
            function = event.find("FunctionDef") if event is not None else None
            if (
                event is None
                or event.get("Type") != "FunctionCall"
                or function is None
                or (function.get("Library"), function.get("Id")) != ("Ntve", "00000120")
            ):
                raise RuntimeError(
                    f"Migrated trigger {display_name!r} has an unsupported event {event_id}"
                )
            trigger_pattern = re.compile(
                rf'(?ms)(^    <Element Type="Trigger" Id="{migrated_id}">\r?\n.*?)(^    </Element>)'
            )
            match = trigger_pattern.search(triggers_text)
            if match is None:
                raise RuntimeError(f"Could not locate migrated trigger {migrated_id}")
            body = re.sub(
                rf'^        <Event Type="FunctionCall" Id="{event_id}"/>\r?\n',
                "",
                match.group(1),
                count=1,
                flags=re.MULTILINE,
            )
            triggers_text = (
                triggers_text[: match.start()]
                + body
                + match.group(2)
                + triggers_text[match.end() :]
            )
            event_pattern = re.compile(
                rf'(?ms)^    <Element Type="FunctionCall" Id="{event_id}">\r?\n.*?^    </Element>\r?\n?'
            )
            triggers_text, count = event_pattern.subn("", triggers_text, count=1)
            if count != 1:
                raise RuntimeError(f"Could not remove legacy map-init event {event_id}")
            removed_events += 1

        current_root = ET.fromstring(triggers_text)
        current_elements = element_map(current_root)
        start = current_elements[start_id]
        run_count = 0
        for action in start.findall("Action"):
            call = current_elements.get(action.get("Id", ""))
            if call is None:
                continue
            function = call.find("FunctionDef")
            if (
                function is not None
                and (function.get("Library"), function.get("Id")) == ("Ntve", "00000116")
                and referenced_trigger(call, current_elements) == migrated_id
            ):
                run_count += 1
        if run_count > 1:
            raise RuntimeError(
                f"Startup trigger runs migrated trigger {display_name!r} more than once"
            )
        if run_count == 1:
            continue

        new_ids: list[str] = []
        for _ in range(4):
            element_id = secrets.token_hex(4).upper()
            while element_id in used:
                element_id = secrets.token_hex(4).upper()
            used.add(element_id)
            new_ids.append(element_id)
        call_id, check_id, wait_id, target_id = new_ids
        start_pattern = re.compile(
            rf'(?ms)(^    <Element Type="Trigger" Id="{start_id}">\r?\n)(.*?)(^    </Element>)'
        )
        match = start_pattern.search(triggers_text)
        if match is None:
            raise RuntimeError(f"Could not locate startup trigger {start_id}")
        action_ref = f'        <Action Type="FunctionCall" Id="{call_id}"/>{newline}'
        triggers_text = (
            triggers_text[: match.start()]
            + match.group(1)
            + match.group(2)
            + action_ref
            + match.group(3)
            + triggers_text[match.end() :]
        )
        blocks = (
            f'    <Element Type="FunctionCall" Id="{call_id}">{newline}'
            f'        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000116"/>{newline}'
            f'        <Parameter Type="Param" Id="{check_id}"/>{newline}'
            f'        <Parameter Type="Param" Id="{wait_id}"/>{newline}'
            f'        <Parameter Type="Param" Id="{target_id}"/>{newline}'
            f'    </Element>{newline}'
            f'    <Element Type="Param" Id="{check_id}">{newline}'
            f'        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000183"/>{newline}'
            f'        <Preset Type="PresetValue" Library="Ntve" Id="00000065"/>{newline}'
            f'    </Element>{newline}'
            f'    <Element Type="Param" Id="{wait_id}">{newline}'
            f'        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000184"/>{newline}'
            f'        <Preset Type="PresetValue" Library="Ntve" Id="00000068"/>{newline}'
            f'    </Element>{newline}'
            f'    <Element Type="Param" Id="{target_id}">{newline}'
            f'        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000182"/>{newline}'
            f'        <ValueType Type="trigger"/>{newline}'
            f'        <ValueElement Type="Trigger" Id="{migrated_id}"/>{newline}'
            f'    </Element>{newline}'
        )
        closing = (
            f"</TriggerData>{newline}"
            if triggers_text.endswith(f"</TriggerData>{newline}")
            else "</TriggerData>"
        )
        triggers_text = triggers_text.replace(closing, blocks + closing, 1)
        added_runs += 1

    ET.fromstring(triggers_text)
    return triggers_text, removed_events, added_runs


def referenced_trigger(call: ET.Element, elements: dict[str, ET.Element]) -> str | None:
    for parameter_ref in call.findall("Parameter"):
        parameter = elements.get(parameter_ref.get("Id", ""))
        if parameter is None:
            continue
        target = parameter.find("ValueElement")
        if target is not None and target.get("Type") == "Trigger":
            return target.get("Id")
    return None


def wire_personality_stop_sites(
    triggers_text: str,
    strings_text: str,
    object_strings_text: str,
    custom_ai: Path,
) -> tuple[str, int]:
    root = ET.fromstring(triggers_text)
    elements = element_map(root)
    names = trigger_names(strings_text)
    ai_names = personality_names(object_strings_text)
    used = set(elements)
    newline = "\r\n" if "\r\n" in triggers_text else "\n"
    additions: list[tuple[str, str, str]] = []

    definitions = [
        definition
        for definition in ET.parse(custom_ai).getroot().findall("Definition")
        if definition.get("Id") and definition.findall("Step[@Type='Wave']")
    ]
    for definition in definitions:
        definition_id = definition.get("Id", "")
        display_name = ai_names.get(definition_id)
        if not display_name:
            raise RuntimeError(f"Missing AI personality display name for {definition_id}")
        migrated_id = names.get(f"{display_name} Attack Waves")
        if migrated_id is None or migrated_id not in elements:
            raise RuntimeError(f"Missing migrated trigger for AI personality {display_name}")

        stop_calls: set[str] = set()
        for element_id, element in elements.items():
            if element.get("Type") != "FunctionCall":
                continue
            function = element.find("FunctionDef")
            if function is None or (function.get("Library"), function.get("Id")) != STOP_PERSONALITY_FUNCTION:
                continue
            values = []
            for parameter_ref in element.findall("Parameter"):
                parameter = elements.get(parameter_ref.get("Id", ""))
                if parameter is not None and parameter.find("Value") is not None:
                    values.append(parameter.findtext("Value", ""))
            if f"ai{definition_id}" in values:
                stop_calls.add(element_id)

        for owner_id, owner in elements.items():
            if owner.get("Type") != "Trigger" or owner_id == migrated_id:
                continue
            actions = owner.findall("Action")
            owner_stop_calls = [
                action.get("Id", "") for action in actions if action.get("Id", "") in stop_calls
            ]
            if not owner_stop_calls:
                continue
            already_stops_migrated = False
            for action in actions:
                call = elements.get(action.get("Id", ""))
                if call is None:
                    continue
                function = call.find("FunctionDef")
                if (
                    function is not None
                    and (function.get("Library"), function.get("Id")) == STOP_TRIGGER_FUNCTION
                    and referenced_trigger(call, elements) == migrated_id
                ):
                    already_stops_migrated = True
                    break
            if already_stops_migrated:
                continue
            if len(owner_stop_calls) != 1:
                raise RuntimeError(
                    f"Trigger {owner_id} has multiple stops for AI personality {definition_id}"
                )
            call_id = secrets.token_hex(4).upper()
            while call_id in used:
                call_id = secrets.token_hex(4).upper()
            used.add(call_id)
            parameter_id = secrets.token_hex(4).upper()
            while parameter_id in used:
                parameter_id = secrets.token_hex(4).upper()
            used.add(parameter_id)
            additions.append((owner_id, owner_stop_calls[0], call_id))
            call_block = (
                f'    <Element Type="FunctionCall" Id="{call_id}">{newline}'
                f'        <FunctionDef Type="FunctionDef" Library="Ntve" Id="698FE891"/>{newline}'
                f'        <Parameter Type="Param" Id="{parameter_id}"/>{newline}'
                f'    </Element>{newline}'
                f'    <Element Type="Param" Id="{parameter_id}">{newline}'
                f'        <ParameterDef Type="ParamDef" Library="Ntve" Id="13A87DA8"/>{newline}'
                f'        <ValueType Type="trigger"/>{newline}'
                f'        <ValueElement Type="Trigger" Id="{migrated_id}"/>{newline}'
                f'    </Element>{newline}'
            )
            closing = f"</TriggerData>{newline}" if triggers_text.endswith(f"</TriggerData>{newline}") else "</TriggerData>"
            triggers_text = triggers_text.replace(closing, call_block + closing, 1)

    for owner_id, stop_call_id, call_id in additions:
        pattern = re.compile(
            rf'(?ms)(^    <Element Type="Trigger" Id="{owner_id}">\r?\n.*?'
            rf'^        <Action Type="FunctionCall" Id="{stop_call_id}"/>\r?\n)'
        )
        match = pattern.search(triggers_text)
        if match is None:
            raise RuntimeError(f"Could not append migrated stop action in trigger {owner_id}")
        insertion = f'        <Action Type="FunctionCall" Id="{call_id}"/>{newline}'
        triggers_text = triggers_text[: match.end()] + insertion + triggers_text[match.end() :]

    ET.fromstring(triggers_text)
    return triggers_text, len(additions)


def validate_gui_result(original_text: str, final_text: str) -> tuple[int, int, int]:
    original_root = ET.fromstring(original_text)
    final_root = ET.fromstring(final_text)
    original_elements = element_map(original_root)
    final_elements = element_map(final_root)
    validate_known_parameter_libraries(final_root)
    new_ids = set(final_elements) - set(original_elements)

    if "Codex migrated AI personality" in final_text:
        raise RuntimeError("A migrated Custom Script marker remains in the GUI result")
    original_scripts = len(original_root.findall(".//ScriptCode"))
    final_scripts = len(final_root.findall(".//ScriptCode"))
    if final_scripts > original_scripts:
        raise RuntimeError("Conversion introduced Custom Script blocks")

    reference_counts: collections.Counter[str] = collections.Counter()
    for node in final_root.iter():
        if node.tag == "Element" or not node.get("Id"):
            continue
        target = final_elements.get(node.get("Id", ""))
        if target is None or target.get("Id") not in new_ids:
            continue
        if node.get("Type") == target.get("Type"):
            reference_counts[target.get("Id", "")] += 1

    bad_references = {
        element_id: reference_counts[element_id]
        for element_id in new_ids
        if final_elements[element_id].get("Type") in {"FunctionCall", "Param"}
        and reference_counts[element_id] != 1
    }
    if bad_references:
        raise RuntimeError(
            "Generated GUI calls or parameters do not have exactly one parent reference: "
            f"{bad_references}"
        )

    for element_id in new_ids:
        call = final_elements[element_id]
        if call.get("Type") != "FunctionCall":
            continue
        function = call.find("FunctionDef")
        if function is None:
            raise RuntimeError(f"Generated FunctionCall {element_id} has no FunctionDef")
        function_library = function.get("Library")
        for parameter_ref in call.findall("Parameter"):
            parameter = final_elements.get(parameter_ref.get("Id", ""))
            if parameter is None:
                raise RuntimeError(
                    f"Generated FunctionCall {element_id} references a missing parameter"
                )
            parameter_def = parameter.find("ParameterDef")
            if parameter_def is None:
                continue
            if parameter_def.get("Library") != function_library:
                raise RuntimeError(
                    "Cross-library ParameterDef mismatch: "
                    f"call {function_library}:{function.get('Id')} uses "
                    f"{parameter_def.get('Library')}:{parameter_def.get('Id')}"
                )

    generated_calls = sum(
        final_elements[element_id].get("Type") == "FunctionCall" for element_id in new_ids
    )
    return len(new_ids), generated_calls, final_scripts


def copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def backup_sources(map_dir: Path, backup_dir: Path) -> None:
    sources = (
        map_dir / "Triggers",
        map_dir / "CustomAI",
        map_dir / "enUS.SC2Data" / "LocalizedData" / "TriggerStrings.txt",
    )
    targets = [backup_dir / f"{map_dir.name}.{source.name}.bak" for source in sources]
    existing = [target for target in targets if target.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite backup: {existing[0]}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for source, target in zip(sources, targets):
        copy_if_exists(source, target)


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".codex.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(text: str, target: Path) -> None:
    temporary = target.with_name(target.name + ".codex.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def convert(
    map_dir: Path,
    apply: bool,
    backup_dir: Path | None,
    start_trigger_name: str = "Start AI",
    scale_migrated_counts: bool = False,
) -> int:
    triggers = map_dir / "Triggers"
    custom_ai = map_dir / "CustomAI"
    strings = map_dir / "enUS.SC2Data" / "LocalizedData" / "TriggerStrings.txt"
    object_strings = map_dir / "enUS.SC2Data" / "LocalizedData" / "ObjectStrings.txt"
    if not triggers.is_file() or not custom_ai.is_file():
        raise FileNotFoundError("The component map must contain Triggers and CustomAI")
    if apply and backup_dir is None:
        raise ValueError("--backup-dir is required with --apply")

    original_text = read_text(triggers)
    strings_text = read_text(strings) if strings.exists() else ""
    object_strings_text = read_text(object_strings) if object_strings.exists() else ""
    if GUI_MARKER in original_text:
        renamed_strings_text, renamed_count = rename_legacy_migrated_triggers(
            strings_text,
            object_strings_text,
            custom_ai,
        )
        normalized_text, removed_events, added_runs = normalize_migrated_start_wiring(
            original_text,
            renamed_strings_text,
            object_strings_text,
            custom_ai,
            start_trigger_name,
        )
        existing_root = ET.fromstring(normalized_text)
        element_map(existing_root)
        validate_known_parameter_libraries(existing_root)
        validate_start_wiring(
            normalized_text,
            renamed_strings_text,
            object_strings_text,
            custom_ai,
            start_trigger_name,
        )
        if "Codex migrated AI personality" in original_text:
            raise RuntimeError("Pure-GUI marker coexists with staged Custom Script")
        rewired_text, added_stops = wire_personality_stop_sites(
            normalized_text,
            renamed_strings_text,
            object_strings_text,
            custom_ai,
        )
        if added_stops or renamed_count or removed_events or added_runs:
            validate_gui_result(original_text, rewired_text)
            print(
                f"{map_dir.name}: pending_migrated_stop_actions={added_stops} "
                f"pending_trigger_renames={renamed_count} "
                f"pending_removed_init_events={removed_events} "
                f"pending_start_runs={added_runs} "
                f"total_scriptcode={len(existing_root.findall('.//ScriptCode'))}"
            )
            if apply:
                assert backup_dir is not None
                backup_sources(map_dir, backup_dir)
                if added_stops or removed_events or added_runs:
                    atomic_write_text(rewired_text, triggers)
                if renamed_count:
                    atomic_write_text(renamed_strings_text, strings)
            return 0
        print(
            f"{map_dir.name}: already_pure_gui=yes "
            f"total_scriptcode={len(existing_root.findall('.//ScriptCode'))}"
        )
        return 0
    staging_root = Path.cwd() / "tmp"
    staging_root.mkdir(parents=True, exist_ok=True)
    temporary_dir = staging_root / f"sc2-ai-gui-{secrets.token_hex(6)}"
    temporary_dir.mkdir()
    try:
        staged_map = temporary_dir / map_dir.name
        staged_strings = staged_map / "enUS.SC2Data" / "LocalizedData" / "TriggerStrings.txt"
        staged_object_strings = staged_map / "enUS.SC2Data" / "LocalizedData" / "ObjectStrings.txt"
        copy_if_exists(triggers, staged_map / "Triggers")
        copy_if_exists(custom_ai, staged_map / "CustomAI")
        copy_if_exists(strings, staged_strings)
        copy_if_exists(object_strings, staged_object_strings)

        internal_output = io.StringIO()
        with contextlib.redirect_stdout(internal_output):
            stage_conversion(
                staged_map,
                True,
                None,
                start_trigger_name,
                scale_migrated_counts,
            )
            gui_conversion(staged_map / "Triggers", True, None)

        final_text = read_text(staged_map / "Triggers")
        staged_strings_text = read_text(staged_strings) if staged_strings.exists() else ""
        staged_strings_text, renamed_count = rename_legacy_migrated_triggers(
            staged_strings_text,
            read_text(staged_object_strings) if staged_object_strings.exists() else "",
            staged_map / "CustomAI",
        )
        if renamed_count:
            atomic_write_text(staged_strings_text, staged_strings)
        final_text, removed_events, added_runs = normalize_migrated_start_wiring(
            final_text,
            staged_strings_text,
            read_text(staged_object_strings) if staged_object_strings.exists() else "",
            staged_map / "CustomAI",
            start_trigger_name,
        )
        if removed_events or added_runs:
            atomic_write_text(final_text, staged_map / "Triggers")
        final_text, added_stops = wire_personality_stop_sites(
            final_text,
            staged_strings_text,
            read_text(staged_object_strings) if staged_object_strings.exists() else "",
            staged_map / "CustomAI",
        )
        if added_stops:
            atomic_write_text(final_text, staged_map / "Triggers")
        new_elements, new_calls, remaining_scripts = validate_gui_result(
            original_text, final_text
        )
        staged_object_strings_text = (
            read_text(staged_object_strings) if staged_object_strings.exists() else ""
        )
        validate_start_wiring(
            final_text,
            staged_strings_text,
            staged_object_strings_text,
            staged_map / "CustomAI",
            start_trigger_name,
        )
        print(
            f"{map_dir.name}: pure_gui=yes new_elements={new_elements} "
            f"new_function_calls={new_calls} migrated_scriptcode=0 "
            f"total_scriptcode={remaining_scripts} "
            f"migrated_counts_scaled_75={'yes' if scale_migrated_counts else 'no'}"
        )
        if not apply:
            return 0

        assert backup_dir is not None
        backup_sources(map_dir, backup_dir)
        atomic_copy(staged_map / "Triggers", triggers)
        if staged_strings.exists():
            atomic_copy(staged_strings, strings)
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert CustomAI personality waves directly to ordinary GUI trigger trees. "
            "The target map is never written with staged ScriptCode."
        )
    )
    parser.add_argument("map_dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--start-trigger-name", default="Start AI")
    parser.add_argument(
        "--scale-migrated-counts",
        action="store_true",
        help="Scale only newly migrated AI unit counts to ceil(value * 0.75).",
    )
    args = parser.parse_args()
    return convert(
        args.map_dir,
        args.apply,
        args.backup_dir,
        args.start_trigger_name,
        args.scale_migrated_counts,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
