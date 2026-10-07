from __future__ import annotations

import argparse
import html
import os
import re
import secrets
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ELEMENT_RE = re.compile(
    r'^    <Element Type="(?P<type>[^"]+)" Id="(?P<id>[0-9A-F]{8})">\r?\n'
    r'.*?^    </Element>\r?\n?',
    re.MULTILINE | re.DOTALL,
)
DIFF_FIXED_RE = re.compile(
    r"libLotv_gf_DifficultyValueFixed2\(([-\d.]+), ([-\d.]+), ([-\d.]+), ([-\d.]+)\)"
)
DIFF_INT_RE = re.compile(
    r"libLotv_gf_DifficultyValueInt2\((-?\d+), (-?\d+), (-?\d+), (-?\d+)\)"
)
DIFF_BOOL_RE = re.compile(
    r"libLotv_gf_DifficultyValueVoidBoolean\((true|false), (true|false), (true|false), (true|false)\)"
)


def fresh(used: set[str]) -> str:
    while True:
        value = secrets.token_hex(4).upper()
        if value not in used:
            used.add(value)
            return value


class Build:
    def __init__(self, used: set[str], newline: str):
        self.used = used
        self.nl = newline
        self.blocks: list[str] = []
        self.call_ids: set[str] = set()
        self.param_ids: set[str] = set()

    def param(self, parameter_def: str, body: str, library: str | None = "Ntve") -> str:
        element_id = fresh(self.used)
        self.param_ids.add(element_id)
        library_attribute = "" if library is None else f' Library="{library}"'
        self.blocks.append(
            f'    <Element Type="Param" Id="{element_id}">{self.nl}'
            f'        <ParameterDef Type="ParamDef"{library_attribute} Id="{parameter_def}"/>{self.nl}'
            f'{body}'
            f'    </Element>{self.nl}'
        )
        return element_id

    def literal(
        self,
        parameter_def: str,
        value: str,
        value_type: str,
        parameter_library: str | None = "Ntve",
    ) -> str:
        return self.param(
            parameter_def,
            f'        <Value>{html.escape(value)}</Value>{self.nl}'
            f'        <ValueType Type="{value_type}"/>{self.nl}',
            library=parameter_library,
        )

    def unit_link(self, parameter_def: str, value: str) -> str:
        return self.param(
            parameter_def,
            f'        <Value>{html.escape(value)}</Value>{self.nl}'
            f'        <ValueType Type="gamelink"/>{self.nl}'
            f'        <ValueGameType Type="Unit"/>{self.nl}',
        )

    def variable(self, parameter_def: str, variable_id: str) -> str:
        return self.param(
            parameter_def,
            f'        <Variable Type="Variable" Id="{variable_id}"/>{self.nl}',
        )

    def point(self, parameter_def: str, point_id: str) -> str:
        return self.param(
            parameter_def,
            f'        <ValueType Type="point"/>{self.nl}'
            f'        <ValueId Id="{point_id}"/>{self.nl}',
        )

    def preset(self, parameter_def: str, preset_id: str) -> str:
        return self.param(
            parameter_def,
            f'        <Preset Type="PresetValue" Library="Ntve" Id="{preset_id}"/>{self.nl}',
        )

    def create_style(self) -> str:
        return self.param(
            "A927C67A",
            f'        <ValueType Type="preset"/>{self.nl}'
            f'        <ValueElement Type="Preset" Library="Ntve" Id="E85564CA"/>{self.nl}'
            f'        <ValuePreset Type="PresetValue" Library="Ntve" Id="7491C9A8"/>{self.nl}',
        )

    def nested(
        self,
        parameter_def: str,
        call_id: str,
        parameter_library: str | None = "Ntve",
    ) -> str:
        return self.param(
            parameter_def,
            f'        <FunctionCall Type="FunctionCall" Id="{call_id}"/>{self.nl}',
            library=parameter_library,
        )

    def call(
        self,
        library: str | None,
        function_id: str,
        params: list[str] | None = None,
        subtype: str | None = None,
        children: list[str] | None = None,
    ) -> str:
        element_id = fresh(self.used)
        self.call_ids.add(element_id)
        library_attribute = "" if library is None else f' Library="{library}"'
        sub = ""
        if subtype is not None:
            sub = (
                f'        <SubFunctionType Type="SubFuncType" Library="Ntve" Id="{subtype}"/>{self.nl}'
            )
        param_refs = "".join(
            f'        <Parameter Type="Param" Id="{param_id}"/>{self.nl}'
            for param_id in (params or [])
        )
        child_refs = "".join(
            f'        <FunctionCall Type="FunctionCall" Id="{call_id}"/>{self.nl}'
            for call_id in (children or [])
        )
        self.blocks.append(
            f'    <Element Type="FunctionCall" Id="{element_id}">{self.nl}'
            f'        <FunctionDef Type="FunctionDef"{library_attribute} Id="{function_id}"/>{self.nl}'
            f'{sub}{param_refs}{child_refs}'
            f'    </Element>{self.nl}'
        )
        return element_id

    def difficulty(self, kind: str, values: tuple[str, str, str, str], subtype: str | None = None) -> str:
        definitions = {
            "int": ("A6DBDC2B", ("68571483", "0A001767", "4BA3AD0F", "760D9F48")),
            "fixed": ("45B6068A", ("CCED8B10", "CBAE34FC", "5BD0FB07", "E19C724E")),
            "bool": ("37046EF0", ("46034F7A", "6A9C62E7", "3E9B2F40", "D22511AA")),
        }
        function_id, parameter_defs = definitions[kind]
        params = [
            self.literal(parameter_def, value, kind, parameter_library="Lotv")
            for parameter_def, value in zip(parameter_defs, values)
        ]
        return self.call("Lotv", function_id, params, subtype=subtype)

    def modifier(self, values: tuple[str, str, str, str]) -> str:
        difficulty = self.difficulty("int", values)
        amount = self.nested("4D4D221F", difficulty, parameter_library="67AA1763")
        return self.call("67AA1763", "4F54E5A0", [amount])

    def modifier_literal(self, value: str) -> str:
        amount = self.literal(
            "4D4D221F", value, "int", parameter_library="67AA1763"
        )
        return self.call("67AA1763", "4F54E5A0", [amount])

    def stop_personality(self, ai_id: str, subtype: str | None) -> str:
        return self.call("Ntve", "898E65C3", [self.literal("9904C380", ai_id, "aidef")], subtype)

    def wait(self, values: tuple[str, str, str, str], subtype: str | None) -> str:
        duration = self.difficulty("fixed", values)
        params = [self.nested("00000419", duration), self.preset("00000420", "EC544EA4")]
        return self.call("Ntve", "00000242", params, subtype)

    def clear_group(self, group_id: str, subtype: str | None) -> str:
        empty = self.call("Ntve", "00000056")
        params = [self.variable("00000219", group_id), self.nested("00000220", empty)]
        return self.call("Ntve", "00000136", params, subtype)

    def add_player(self, group_id: str, player: str, subtype: str | None) -> str:
        params = [self.literal("1D6C8796", player, "int"), self.variable("F4B91B76", group_id)]
        return self.call("Ntve", "15C2C248", params, subtype)

    def set_player_group_single(
        self,
        group_id: str,
        player: str,
        subtype: str | None,
    ) -> str:
        single = self.call(
            "Ntve",
            "00000057",
            [self.literal("00000094", player, "int")],
        )
        params = [
            self.variable("00000219", group_id),
            self.nested("00000220", single),
        ]
        return self.call("Ntve", "00000136", params, subtype)

    def target_player(self, player: str, group_id: str, subtype: str | None) -> str:
        params = [self.literal("D621D0A0", player, "int"), self.variable("6707020E", group_id)]
        return self.call("Ntve", "3955F80B", params, subtype)

    def point_action(self, function_id: str, player_def: str, point_def: str, player: str, point: str, subtype: str | None) -> str:
        params = [self.literal(player_def, player, "int"), self.point(point_def, point)]
        return self.call("Ntve", function_id, params, subtype)

    def waypoint(
        self,
        player: str,
        point: str,
        subtype: str | None,
        use_transport: bool = False,
    ) -> str:
        params = [
            self.preset("97A85CF7", "75B749DB" if use_transport else "F6A98FEE"),
            self.point("EC5281C7", point),
            self.literal("AB268797", player, "int"),
        ]
        return self.call("Ntve", "17E6D92B", params, subtype)

    def conditional_waypoint(self, flags: tuple[str, str, str, str], player: str, point: str, subtype: str | None) -> str:
        condition = self.difficulty("bool", flags, subtype="00000003")
        action = self.waypoint(player, point, subtype="00000004")
        return self.call("Ntve", "00000137", subtype=subtype, children=[condition, action])

    def create_units(self, counts: tuple[str, str, str, str], unit: str, player: str, point: str, subtype: str | None) -> str:
        amount = self.modifier(counts)
        params = [
            self.nested("6A3CFF43", amount),
            self.create_style(),
            self.literal("FF0C620E", player, "int"),
            self.unit_link("D43CB595", unit),
            self.point("23D48FEC", point),
        ]
        return self.call("Ntve", "F247156C", params, subtype)

    def add_units(
        self,
        counts: tuple[str, str, str, str],
        unit: str,
        subtype: str | None,
    ) -> str:
        # The editor serializes these parameter definitions in a different order
        # from the Galaxy signature. Map easy/normal/hard/expert explicitly.
        # The editor labels these as easy, normal, hard, expert in this order.
        # Bind by the native definitions, not by the serialized reference order.
        count_defs = ("24D9A2D7", "B52CD455", "AD14DE85", "A166DBF3")
        count_params = [
            self.nested(parameter_def, self.modifier_literal(value))
            for parameter_def, value in zip(count_defs, counts)
        ]
        params = [count_params[0], self.unit_link("0FEB500B", unit), *count_params[1:]]
        return self.call("Ntve", "253D7FAD", params, subtype)

    def use_last_created_group(self, player: str, subtype: str | None) -> str:
        last_group = self.call("Ntve", "00000141")
        params = [self.literal("982396A7", player, "int"), self.nested("E72BEF37", last_group)]
        return self.call("Ntve", "D16912F9", params, subtype)

    def send(self, player: str, values: tuple[str, str, str, str], subtype: str | None) -> str:
        duration = self.difficulty("int", values)
        params = [
            self.literal("1B20A0F2", player, "int"),
            self.nested("84463647", duration),
            self.preset("CA9FBBA2", "00000067"),
        ]
        return self.call("Ntve", "3A0403D0", params, subtype)


def owner_trigger(script_id: str, elements: dict[str, ET.Element]) -> ET.Element:
    parents: dict[str, str] = {}
    for element_id, element in elements.items():
        for child in element:
            if child.tag in {"Action", "FunctionCall"} and child.get("Type") == "FunctionCall" and child.get("Id"):
                parents[child.get("Id")] = element_id
    current = script_id
    seen: set[str] = set()
    while current in parents:
        if current in seen:
            raise RuntimeError(f"Reference cycle while locating owner of {script_id}")
        seen.add(current)
        current = parents[current]
        element = elements[current]
        if element.get("Type") == "Trigger":
            return element
    raise RuntimeError(f"Could not locate owning trigger for script {script_id}")


def player_group_variable(trigger: ET.Element, elements: dict[str, ET.Element]) -> str:
    for reference in trigger.findall("Variable"):
        variable = elements.get(reference.get("Id", ""))
        if variable is None:
            continue
        type_node = variable.find("./VariableType/Type")
        if type_node is not None and type_node.get("Value") == "playergroup":
            return variable.get("Id", "")
    raise RuntimeError(f"Trigger {trigger.get('Id')} has no playergroup local variable")


def split_statements(code: str) -> list[str]:
    result: list[str] = []
    for raw in code.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        result.append(line)
    return result


def convert_script(
    build: Build,
    code: str,
    group_id: str,
    subtype: str | None,
    target_state: dict[str, str] | None = None,
) -> list[str]:
    actions: list[str] = []
    create_point: str | None = None
    statements = split_statements(code)
    index = 0
    while index < len(statements):
        line = statements[index]
        index += 1
        if line == "PlayerGroupClear(lv_target);" and index < len(statements):
            add_match = re.fullmatch(
                r"PlayerGroupAdd\(lv_target, (?P<player>\d+)\);",
                statements[index],
            )
            if add_match and target_state is not None:
                player = add_match.group("player")
                if target_state.get(group_id) != player:
                    actions.append(build.set_player_group_single(group_id, player, subtype))
                    target_state[group_id] = player
                index += 1
                continue
        match = re.fullmatch(r'cai_waves_stop\("(?P<ai>ai[0-9A-F]{8})"\);', line)
        if match:
            actions.append(build.stop_personality(match.group("ai"), subtype))
            continue
        match = re.fullmatch(r"Wait\((?P<diff>.+), c_timeAI\);", line)
        if match:
            values = DIFF_FIXED_RE.fullmatch(match.group("diff"))
            if values is None:
                raise RuntimeError(f"Unsupported wait expression: {line}")
            actions.append(build.wait(values.groups(), subtype))
            continue
        if line == "PlayerGroupClear(lv_target);":
            actions.append(build.clear_group(group_id, subtype))
            continue
        match = re.fullmatch(r"PlayerGroupAdd\(lv_target, (?P<player>\d+)\);", line)
        if match:
            actions.append(build.add_player(group_id, match.group("player"), subtype))
            continue
        match = re.fullmatch(r"AIAttackWaveSetTargetPlayer\((?P<player>\d+), lv_target\);", line)
        if match:
            actions.append(build.target_player(match.group("player"), group_id, subtype))
            continue
        match = re.fullmatch(r"AIAttackWaveSetGatherPoint\((?P<player>\d+), PointFromId\((?P<point>\d+)\)\);", line)
        if match:
            actions.append(build.point_action("D92EAFA7", "4563368E", "311451BE", match.group("player"), match.group("point"), subtype))
            continue
        match = re.fullmatch(r"AIAttackWaveSetTargetPoint\((?P<player>\d+), PointFromId\((?P<point>\d+)\)\);", line)
        if match:
            actions.append(build.point_action("12E81501", "D5F3A1D1", "B55CF069", match.group("player"), match.group("point"), subtype))
            continue
        match = re.fullmatch(
            r"AIAttackWaveAddWaypoint\((?P<player>\d+), PointFromId\((?P<point>\d+)\), "
            r"(?P<transport>true|false)\);",
            line,
        )
        if match:
            actions.append(
                build.waypoint(
                    match.group("player"),
                    match.group("point"),
                    subtype,
                    use_transport=match.group("transport") == "true",
                )
            )
            continue
        match = re.fullmatch(
            r"if \((?P<cond>libLotv_gf_DifficultyValueVoidBoolean\(.+\))\) \{ "
            r"AIAttackWaveAddWaypoint\((?P<player>\d+), PointFromId\((?P<point>\d+)\), false\); \}",
            line,
        )
        if match:
            flags = DIFF_BOOL_RE.fullmatch(match.group("cond"))
            if flags is None:
                raise RuntimeError(f"Unsupported difficulty condition: {line}")
            actions.append(build.conditional_waypoint(flags.groups(), match.group("player"), match.group("point"), subtype))
            continue
        match = re.fullmatch(r"lv_createPoint = PointFromId\((?P<point>\d+)\);", line)
        if match:
            create_point = match.group("point")
            continue
        match = re.fullmatch(
            r'UnitCreate\(lib67AA1763_gf_AttackWaveModifier\((?P<diff>libLotv_gf_DifficultyValueInt2\(.+\))\), '
            r'"(?P<unit>[^"]+)", 0, (?P<player>\d+), lv_createPoint, PointGetFacing\(lv_createPoint\)\);',
            line,
        )
        if match:
            if create_point is None:
                raise RuntimeError(f"UnitCreate has no preceding create point: {line}")
            counts = DIFF_INT_RE.fullmatch(match.group("diff"))
            if counts is None:
                raise RuntimeError(f"Unsupported unit count expression: {line}")
            actions.append(build.create_units(counts.groups(), match.group("unit"), match.group("player"), create_point, subtype))
            continue
        match = re.fullmatch(
            r'AIAttackWaveAddUnits4\('
            r'lib67AA1763_gf_AttackWaveModifier\((?P<c1>-?\d+)\), '
            r'lib67AA1763_gf_AttackWaveModifier\((?P<c2>-?\d+)\), '
            r'lib67AA1763_gf_AttackWaveModifier\((?P<c3>-?\d+)\), '
            r'lib67AA1763_gf_AttackWaveModifier\((?P<c4>-?\d+)\), '
            r'"(?P<unit>[^"]+)"\);',
            line,
        )
        if match:
            counts = tuple(match.group(name) for name in ("c1", "c2", "c3", "c4"))
            actions.append(build.add_units(counts, match.group("unit"), subtype))
            continue
        match = re.fullmatch(r"AIAttackWaveUseGroup\((?P<player>\d+), UnitLastCreatedGroup\(\)\);", line)
        if match:
            actions.append(build.use_last_created_group(match.group("player"), subtype))
            continue
        match = re.fullmatch(
            r"AIAttackWaveSend\((?P<player>\d+), (?P<diff>libLotv_gf_DifficultyValueInt2\(.+\)), false\);",
            line,
        )
        if match:
            duration = DIFF_INT_RE.fullmatch(match.group("diff"))
            if duration is None:
                raise RuntimeError(f"Unsupported send duration: {line}")
            actions.append(build.send(match.group("player"), duration.groups(), subtype))
            continue
        raise RuntimeError(f"Unsupported migrated script statement: {line}")
    if not actions:
        raise RuntimeError("Migrated script block produced no GUI actions")
    return actions


def remove_unused_local_variables(text: str, trigger_ids: set[str]) -> tuple[str, int]:
    root = ET.fromstring(text)
    elements = {element.get("Id", ""): element for element in root.findall("Element")}
    block_spans = {
        match.group("id"): (match.start(), match.end())
        for match in ELEMENT_RE.finditer(text)
    }
    edits: list[tuple[int, int, str]] = []
    removed = 0
    for trigger_id in trigger_ids:
        trigger = elements[trigger_id]
        for reference in trigger.findall("Variable"):
            variable_id = reference.get("Id", "")
            if len(re.findall(rf'\bId="{variable_id}"', text)) != 2:
                continue
            pattern = re.compile(
                rf'(?m)^\s*<Variable Type="Variable" Id="{variable_id}"\s*/>\r?\n?'
            )
            match = pattern.search(text)
            if match is None or variable_id not in block_spans:
                raise RuntimeError(f"Could not remove unused local variable {variable_id}")
            edits.append((match.start(), match.end(), ""))
            start, end = block_spans[variable_id]
            edits.append((start, end, ""))
            removed += 1
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, removed


def convert(triggers: Path, apply: bool, backup: Path | None) -> int:
    with triggers.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    root = ET.fromstring(text)
    if "Codex migrated AI personality" not in text:
        print(f"{triggers.parent.name}: no staged migration scripts")
        return 0
    matches = list(ELEMENT_RE.finditer(text))
    elements = {element.get("Id", ""): element for element in root.findall("Element")}
    if len(elements) != len(root.findall("Element")):
        raise RuntimeError("Duplicate Element IDs prevent safe conversion")
    used = set(elements)
    build = Build(used, newline)
    replacements: list[tuple[int, int, str]] = []
    removed: list[tuple[int, int]] = []
    script_count = 0
    action_count = 0
    target_state: dict[str, str] = {}
    converted_trigger_ids: set[str] = set()
    for match in matches:
        element_id = match.group("id")
        element = elements[element_id]
        script = element.find("ScriptCode")
        if script is None:
            continue
        code = script.text or ""
        if not any(
            token in code
            for token in (
                "Codex migrated AI personality",
                "AIAttackWave",
                "PlayerGroupClear(lv_target)",
                "Wait(libLotv_gf_DifficultyValueFixed2",
                "UnitCreate(lib67AA1763_gf_AttackWaveModifier",
            )
        ):
            continue
        trigger = owner_trigger(element_id, elements)
        converted_trigger_ids.add(trigger.get("Id", ""))
        group_id = player_group_variable(trigger, elements)
        subtype_node = element.find("SubFunctionType")
        subtype = subtype_node.get("Id") if subtype_node is not None else None
        actions = convert_script(build, code, group_id, subtype, target_state)
        reference_patterns = [
            ("Action", re.compile(rf'(?m)^(?P<indent>\s*)<Action Type="FunctionCall" Id="{element_id}"/>\r?$')),
            ("FunctionCall", re.compile(rf'(?m)^(?P<indent>\s*)<FunctionCall Type="FunctionCall" Id="{element_id}"/>\r?$')),
        ]
        located: list[tuple[str, re.Match[str]]] = []
        for tag, pattern in reference_patterns:
            located.extend((tag, ref) for ref in pattern.finditer(text))
        if len(located) != 1:
            raise RuntimeError(f"Expected one parent reference for script {element_id}, found {len(located)}")
        tag, reference = located[0]
        indent = reference.group("indent")
        replacement = newline.join(
            f'{indent}<{tag} Type="FunctionCall" Id="{action_id}"/>' for action_id in actions
        )
        replacements.append((reference.start(), reference.end(), replacement))
        removed.append((match.start(), match.end()))
        script_count += 1
        action_count += len(actions)

    if script_count == 0:
        raise RuntimeError("Migration marker exists but no generated ScriptCode blocks were recognized")
    edits = [(start, end, "") for start, end in removed] + replacements
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    marker = f'    <!-- Migrated AI personality waves converted to GUI actions. -->{newline}'
    generated = marker + "".join(build.blocks)
    text = text.replace("</TriggerData>", generated + "</TriggerData>", 1)
    text, unused_variable_count = remove_unused_local_variables(text, converted_trigger_ids)
    final_root = ET.fromstring(text)
    final_elements = final_root.findall("Element")
    final_ids = [element.get("Id") for element in final_elements if element.get("Id")]
    if len(final_ids) != len(set(final_ids)):
        raise RuntimeError("Conversion produced duplicate Element IDs")
    if "Codex migrated AI personality" in text:
        raise RuntimeError("A migrated custom-script marker remains after conversion")
    final_script_count = sum(element.find("ScriptCode") is not None for element in final_elements)
    generated = build.call_ids | build.param_ids
    generated_types = {
        element.get("Id", ""): element.get("Type")
        for element in final_elements
        if element.get("Id") in generated
    }
    reference_counts: dict[str, int] = {element_id: 0 for element_id in generated}
    for node in final_root.iter():
        node_id = node.get("Id")
        if node.tag != "Element" and node_id in reference_counts:
            if node.get("Type") == generated_types[node_id]:
                reference_counts[node_id] += 1
    bad = {element_id: count for element_id, count in reference_counts.items() if count != 1}
    if bad:
        raise RuntimeError(f"Generated elements without exactly one parent reference: {bad}")
    print(
        f"{triggers.parent.name}: script_blocks={script_count}, gui_actions={action_count}, "
        f"new_elements={len(build.blocks)}, unused_variables_removed={unused_variable_count}, "
        f"remaining_scriptcode={final_script_count}"
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
    parser = argparse.ArgumentParser(description="Convert staged AI personality ScriptCode actions to pure GUI trigger calls.")
    parser.add_argument("triggers", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    return convert(args.triggers, args.apply, args.backup)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
