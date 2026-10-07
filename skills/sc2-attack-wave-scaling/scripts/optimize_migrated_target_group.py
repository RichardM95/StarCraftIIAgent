from __future__ import annotations

import argparse
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from convert_migrated_scripts_to_gui import Build, ELEMENT_RE, remove_unused_local_variables


class NoOptimizationCandidate(RuntimeError):
    pass


def function_id(element: ET.Element) -> str | None:
    node = element.find("FunctionDef")
    return node.get("Id") if node is not None else None


def referenced_elements(element_id: str, elements: dict[str, ET.Element]) -> set[str]:
    found: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in found:
            return
        found.add(current_id)
        current = elements[current_id]
        for child in current:
            if child.tag in {"Parameter", "FunctionCall"} and child.get("Id") in elements:
                visit(child.get("Id", ""))

    visit(element_id)
    return found


def nested_function(param: ET.Element, elements: dict[str, ET.Element]) -> ET.Element | None:
    reference = param.find("FunctionCall")
    return elements.get(reference.get("Id", "")) if reference is not None else None


def empty_group_assignment(call: ET.Element, elements: dict[str, ET.Element]) -> bool:
    if function_id(call) != "00000136":
        return False
    params = [elements.get(ref.get("Id", "")) for ref in call.findall("Parameter")]
    if len(params) != 2 or any(param is None for param in params):
        return False
    value_call = nested_function(params[1], elements)  # type: ignore[arg-type]
    return value_call is not None and function_id(value_call) == "00000056"


def add_player_details(call: ET.Element, elements: dict[str, ET.Element]) -> tuple[str, str] | None:
    if function_id(call) != "15C2C248":
        return None
    params = [elements.get(ref.get("Id", "")) for ref in call.findall("Parameter")]
    if len(params) != 2 or any(param is None for param in params):
        return None
    group_param, player_param = params
    group_var = group_param.find("Variable")  # type: ignore[union-attr]
    player_value = player_param.find("Value")  # type: ignore[union-attr]
    if group_var is None or player_value is None:
        return None
    return group_var.get("Id", ""), player_value.text or ""


def single_assignment_details(
    call: ET.Element,
    elements: dict[str, ET.Element],
) -> tuple[str, str] | None:
    if function_id(call) != "00000136":
        return None
    params = [elements.get(ref.get("Id", "")) for ref in call.findall("Parameter")]
    if len(params) != 2 or any(param is None for param in params):
        return None
    group_var = params[0].find("Variable")  # type: ignore[union-attr]
    single = nested_function(params[1], elements)  # type: ignore[arg-type]
    if group_var is None or single is None or function_id(single) != "00000057":
        return None
    player_ref = single.find("Parameter")
    if player_ref is None or player_ref.get("Id", "") not in elements:
        return None
    value = elements[player_ref.get("Id", "")].findtext("Value")
    if value is None:
        return None
    return group_var.get("Id", ""), value


def action_references(container: ET.Element) -> list[ET.Element]:
    tag = "Action" if container.get("Type") == "Trigger" else "FunctionCall"
    return [child for child in container if child.tag == tag and child.get("Id")]


def reachable_action_containers(
    trigger: ET.Element,
    elements: dict[str, ET.Element],
) -> list[ET.Element]:
    result: list[ET.Element] = []
    pending = [trigger]
    seen: set[str] = set()
    while pending:
        container = pending.pop()
        container_id = container.get("Id", "")
        if container_id in seen:
            continue
        seen.add(container_id)
        result.append(container)
        for reference in action_references(container):
            child = elements.get(reference.get("Id", ""))
            if child is not None and child.get("Type") == "FunctionCall":
                pending.append(child)
    return result


def optimize(
    text: str,
    trigger_id: str,
    expected_player: str | None,
) -> tuple[str, int, int, str]:
    newline = "\r\n" if "\r\n" in text else "\n"
    root = ET.fromstring(text)
    all_elements = root.findall("Element")
    elements = {element.get("Id", ""): element for element in all_elements}
    if len(elements) != len(all_elements):
        raise RuntimeError("Duplicate Element IDs prevent safe optimization")
    trigger = elements.get(trigger_id)
    if trigger is None or trigger.get("Type") != "Trigger":
        raise RuntimeError(f"Trigger {trigger_id} was not found")

    pairs: list[tuple[str, str, str]] = []
    existing_singles: list[tuple[str, str, str]] = []
    containers = reachable_action_containers(trigger, elements)
    for container in containers:
        references = action_references(container)
        action_ids = [ref.get("Id", "") for ref in references]
        for action_id in action_ids:
            details = single_assignment_details(elements[action_id], elements)
            if details is not None:
                group_id, player = details
                existing_singles.append((action_id, group_id, player))
        index = 0
        while index + 1 < len(action_ids):
            clear_id, add_id = action_ids[index], action_ids[index + 1]
            clear_call, add_call = elements[clear_id], elements[add_id]
            details = add_player_details(add_call, elements)
            if empty_group_assignment(clear_call, elements) and details is not None:
                group_id, player = details
                if expected_player is None:
                    expected_player = player
                if player != expected_player:
                    raise RuntimeError(f"Unexpected target player {player}; expected {expected_player}")
                pairs.append((clear_id, add_id, group_id))
                index += 2
                continue
            index += 1
    if not pairs:
        raise NoOptimizationCandidate("No clear-and-add target player-group pairs were found")
    for _, _, player in existing_singles:
        if expected_player is None:
            expected_player = player
        if player != expected_player:
            raise RuntimeError(f"Existing target player {player} differs from {expected_player}")
    assert expected_player is not None
    group_ids = {group_id for _, _, group_id in pairs} | {
        group_id for _, group_id, _ in existing_singles
    }
    if len(group_ids) != 1:
        raise RuntimeError(f"Target pairs use multiple variables: {sorted(group_ids)}")

    used = set(elements)
    build = Build(used, newline)
    replacement_id = build.set_player_group_single(group_ids.pop(), expected_player, None)

    remove_ids: set[str] = set()
    for clear_id, add_id, _ in pairs:
        remove_ids.update(referenced_elements(clear_id, elements))
        remove_ids.update(referenced_elements(add_id, elements))
    for action_id, _, _ in existing_singles:
        remove_ids.update(referenced_elements(action_id, elements))
    for element_id in remove_ids:
        occurrences = len(re.findall(rf'\bId="{element_id}"', text))
        if occurrences != 2:
            raise RuntimeError(f"Element {element_id} is not singly owned (occurrences={occurrences})")

    reference_lines = {
        element_id: re.compile(
            rf'(?m)^\s*<(?:Action|FunctionCall) Type="FunctionCall" Id="{element_id}"\s*/>\r?\n?'
        )
        for element_id in {
            *(element_id for pair in pairs for element_id in pair[:2]),
            *(action_id for action_id, _, _ in existing_singles),
        }
    }
    for element_id, pattern in reference_lines.items():
        text, count = pattern.subn("", text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not remove action reference {element_id}")

    stop_ids = [
        ref.get("Id", "")
        for ref in trigger.findall("Action")
        if function_id(elements[ref.get("Id", "")]) == "898E65C3"
    ]
    if len(stop_ids) != 1:
        raise RuntimeError(f"Expected one top-level personality stop action, found {len(stop_ids)}")
    stop_pattern = re.compile(
        rf'(?m)^(?P<indent>\s*)<Action Type="FunctionCall" Id="{stop_ids[0]}"\s*/>\r?$'
    )
    stop_match = stop_pattern.search(text)
    if stop_match is None:
        raise RuntimeError("Could not locate personality stop action")
    assignment_line = (
        f'{newline}{stop_match.group("indent")}<Action Type="FunctionCall" Id="{replacement_id}"/>'
    )
    text = text[: stop_match.end()] + assignment_line + text[stop_match.end() :]

    spans = {
        match.group("id"): (match.start(), match.end())
        for match in ELEMENT_RE.finditer(text)
        if match.group("id") in remove_ids
    }
    if set(spans) != remove_ids:
        raise RuntimeError(f"Could not locate element blocks: {sorted(remove_ids - set(spans))}")
    for start, end in sorted(spans.values(), reverse=True):
        text = text[:start] + text[end:]
    insertion = "".join(build.blocks)
    marker = f"</TriggerData>"
    if marker not in text:
        raise RuntimeError("Missing TriggerData closing tag")
    text = text.replace(marker, insertion + marker, 1)
    text, unused_variables = remove_unused_local_variables(text, {trigger_id})

    final_root = ET.fromstring(text)
    final_elements = {element.get("Id", ""): element for element in final_root.findall("Element")}
    final_trigger = final_elements[trigger_id]
    final_containers = reachable_action_containers(final_trigger, final_elements)
    final_calls = [
        final_elements[reference.get("Id", "")]
        for container in final_containers
        for reference in action_references(container)
    ]
    if sum(function_id(call) == "15C2C248" for call in final_calls) != 0:
        raise RuntimeError("PlayerGroupAdd remains in the optimized trigger")
    single_assignments = sum(
        single_assignment_details(call, final_elements) is not None for call in final_calls
    )
    if single_assignments != 1:
        raise RuntimeError(f"Expected one PlayerGroupSingle assignment, found {single_assignments}")
    top_level_singles = sum(
        single_assignment_details(final_elements[ref.get("Id", "")], final_elements) is not None
        for ref in final_trigger.findall("Action")
    )
    if top_level_singles != 1:
        raise RuntimeError("PlayerGroupSingle assignment was not hoisted to trigger scope")
    return text, len(pairs), unused_variables, expected_player


def trigger_names(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    return [
        (match.group("id"), match.group("name"))
        for match in re.finditer(
            r"^Trigger/Name/(?P<id>[0-9A-F]{8})=(?P<name>.+ Attack Waves)$",
            text,
            re.MULTILINE,
        )
    ]


def migrated_trigger_ids(text: str) -> set[str]:
    root = ET.fromstring(text)
    elements = {element.get("Id", ""): element for element in root.findall("Element")}
    result: set[str] = set()
    for trigger in root.findall("Element"):
        if trigger.get("Type") != "Trigger":
            continue
        for reference in trigger.findall("Action"):
            call = elements.get(reference.get("Id", ""))
            if call is not None and function_id(call) == "898E65C3":
                result.add(trigger.get("Id", ""))
                break
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("triggers", type=Path)
    parser.add_argument("--trigger-id")
    parser.add_argument("--player")
    parser.add_argument("--trigger-strings", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    with args.triggers.open("r", encoding="utf-8", newline="") as stream:
        original = stream.read()
    if bool(args.trigger_id) == bool(args.trigger_strings):
        raise RuntimeError("Specify exactly one of --trigger-id or --trigger-strings")
    candidates = (
        [(args.trigger_id, args.trigger_id)]
        if args.trigger_id
        else trigger_names(args.trigger_strings)
    )
    if args.trigger_strings:
        migrated_ids = migrated_trigger_ids(original)
        candidates = [item for item in candidates if item[0] in migrated_ids]
    result = original
    optimized: list[tuple[str, str, int, int, str]] = []
    for trigger_id, name in candidates:
        try:
            result, pair_count, unused_variables, player = optimize(
                result,
                trigger_id,
                args.player if args.trigger_id else None,
            )
        except NoOptimizationCandidate:
            continue
        optimized.append((trigger_id, name, pair_count, unused_variables, player))
    if not optimized:
        print(f"{args.triggers}: no redundant migrated target groups")
        return 0
    for trigger_id, name, pair_count, unused_variables, player in optimized:
        print(
            f"{args.triggers}: trigger={name} id={trigger_id} redundant_pairs={pair_count} "
            f"replacement=PlayerGroupSingle({player}) unused_variables={unused_variables}"
        )
    print(f"apply={'yes' if args.apply else 'no'} optimized_triggers={len(optimized)}")
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
