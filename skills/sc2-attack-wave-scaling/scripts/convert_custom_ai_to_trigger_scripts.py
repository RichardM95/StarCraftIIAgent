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


def fresh(used: set[str]) -> str:
    while True:
        value = secrets.token_hex(4).upper()
        if value not in used:
            used.add(value)
            return value


def named_trigger_id(strings: Path, name: str) -> str:
    if not strings.is_file():
        raise FileNotFoundError(f"TriggerStrings.txt is required to locate {name!r}")
    pattern = re.compile(r"^Trigger/Name/([0-9A-F]{8})=(.*)$")
    matches = []
    for line in strings.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(2).strip() == name:
            matches.append(match.group(1))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one trigger named {name!r}, found {matches}")
    return matches[0]


def personality_names(object_strings: Path) -> dict[str, str]:
    if not object_strings.is_file():
        raise FileNotFoundError("ObjectStrings.txt is required for AI personality names")
    result: dict[str, str] = {}
    pattern = re.compile(r"^AI/Name/([0-9A-F]{8})=(.+)$")
    for line in object_strings.read_text(encoding="utf-8").splitlines():
        line = line.lstrip("\ufeff")
        match = pattern.match(line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def append_actions(text: str, trigger_id: str, action_ids: list[str], newline: str) -> str:
    pattern = re.compile(
        rf'(?ms)(^    <Element Type="Trigger" Id="{trigger_id}">\r?\n)(.*?)(^    </Element>)'
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"Could not locate startup trigger {trigger_id}")
    refs = "".join(
        f'        <Action Type="FunctionCall" Id="{action_id}"/>{newline}'
        for action_id in action_ids
    )
    replacement = match.group(1) + match.group(2) + refs + match.group(3)
    return text[: match.start()] + replacement + text[match.end() :]


def values(node: ET.Element | None, tag: str) -> list[int]:
    result = [0, 0, 0, 0]
    if node is not None:
        for child in node.findall(tag):
            level = int(child.get("DiffLevel", "1"))
            if 1 <= level <= 4:
                result[level - 1] = int(child.get("Value", "0"))
    return result


def diff_int(v: list[int]) -> str:
    return "libLotv_gf_DifficultyValueInt2(" + ", ".join(map(str, v)) + ")"


def diff_fixed(v: list[int]) -> str:
    return "libLotv_gf_DifficultyValueFixed2(" + ", ".join(f"{x}.0" for x in v) + ")"


def scale_count_75(value: int) -> int:
    if value < 0:
        raise RuntimeError(f"Attack-wave unit count cannot be negative: {value}")
    return (value * 3 + 3) // 4


def active_expr(point: ET.Element) -> str | None:
    active = point.findall("Active")
    if not active:
        return None
    flags = ["false"] * 4
    for item in active:
        level = int(item.get("DiffLevel", "1"))
        if 1 <= level <= 4:
            flags[level - 1] = "true"
    if all(v == "true" for v in flags):
        return None
    return "libLotv_gf_DifficultyValueVoidBoolean(" + ", ".join(flags) + ")"


class Build:
    def __init__(self, used: set[str], newline: str):
        self.used = used
        self.nl = newline
        self.blocks: list[str] = []
        self.names: list[tuple[str, str, str]] = []

    def script(self, code: str, subtype: str | None = None) -> str:
        element_id = fresh(self.used)
        sub = "" if subtype is None else f'        <SubFunctionType Type="SubFuncType" Library="Ntve" Id="{subtype}"/>{self.nl}'
        escaped = html.escape(code, quote=False)
        self.blocks.append(
            f'    <Element Type="FunctionCall" Id="{element_id}">{self.nl}'
            f'        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000123"/>{self.nl}'
            f'{sub}        <ScriptCode>{self.nl}{escaped}{self.nl}        </ScriptCode>{self.nl}'
            f'    </Element>{self.nl}'
        )
        return element_id

    def execute(self, trigger_id: str, subtype: str | None = None) -> str:
        call_id, check_id, wait_id, target_id = (fresh(self.used) for _ in range(4))
        sub = "" if subtype is None else f'        <SubFunctionType Type="SubFuncType" Library="Ntve" Id="{subtype}"/>{self.nl}'
        self.blocks.extend([
            f'    <Element Type="FunctionCall" Id="{call_id}">{self.nl}        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000116"/>{self.nl}{sub}        <Parameter Type="Param" Id="{check_id}"/>{self.nl}        <Parameter Type="Param" Id="{wait_id}"/>{self.nl}        <Parameter Type="Param" Id="{target_id}"/>{self.nl}    </Element>{self.nl}',
            f'    <Element Type="Param" Id="{check_id}">{self.nl}        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000183"/>{self.nl}        <Preset Type="PresetValue" Library="Ntve" Id="00000065"/>{self.nl}    </Element>{self.nl}',
            f'    <Element Type="Param" Id="{wait_id}">{self.nl}        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000184"/>{self.nl}        <Preset Type="PresetValue" Library="Ntve" Id="00000068"/>{self.nl}    </Element>{self.nl}',
            f'    <Element Type="Param" Id="{target_id}">{self.nl}        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000182"/>{self.nl}        <ValueType Type="trigger"/>{self.nl}        <ValueElement Type="Trigger" Id="{trigger_id}"/>{self.nl}    </Element>{self.nl}',
        ])
        return call_id

    def repeat(self, children: list[str]) -> str:
        call_id = fresh(self.used)
        refs = "".join(f'        <FunctionCall Type="FunctionCall" Id="{x}"/>{self.nl}' for x in children)
        self.blocks.append(f'    <Element Type="FunctionCall" Id="{call_id}">{self.nl}        <FunctionDef Type="FunctionDef" Library="Ntve" Id="CEDAB9C3"/>{self.nl}{refs}    </Element>{self.nl}')
        return call_id

    def trigger(self, name: str, actions: list[str], event: bool, variables: bool = True) -> str:
        trigger_id = fresh(self.used)
        event_id = fresh(self.used) if event else None
        var_ids = [fresh(self.used), fresh(self.used)] if variables else []
        var_refs = "".join(f'        <Variable Type="Variable" Id="{x}"/>{self.nl}' for x in var_ids)
        event_ref = "" if event_id is None else f'        <Event Type="FunctionCall" Id="{event_id}"/>{self.nl}'
        action_refs = "".join(f'        <Action Type="FunctionCall" Id="{x}"/>{self.nl}' for x in actions)
        self.blocks.append(f'    <Element Type="Trigger" Id="{trigger_id}">{self.nl}{var_refs}{event_ref}{action_refs}    </Element>{self.nl}')
        if event_id:
            self.blocks.append(f'    <Element Type="FunctionCall" Id="{event_id}">{self.nl}        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000120"/>{self.nl}    </Element>{self.nl}')
        if variables:
            group_id, point_id = var_ids
            init_param, init_call = fresh(self.used), fresh(self.used)
            self.blocks.extend([
                f'    <Element Type="Variable" Id="{group_id}">{self.nl}        <VariableType>{self.nl}            <Type Value="playergroup"/>{self.nl}        </VariableType>{self.nl}        <Value Type="Param" Id="{init_param}"/>{self.nl}    </Element>{self.nl}',
                f'    <Element Type="Param" Id="{init_param}">{self.nl}        <FunctionCall Type="FunctionCall" Id="{init_call}"/>{self.nl}    </Element>{self.nl}',
                f'    <Element Type="FunctionCall" Id="{init_call}">{self.nl}        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000056"/>{self.nl}    </Element>{self.nl}',
                f'    <Element Type="Variable" Id="{point_id}">{self.nl}        <VariableType>{self.nl}            <Type Value="point"/>{self.nl}        </VariableType>{self.nl}    </Element>{self.nl}',
            ])
            self.names.extend([("Variable", group_id, "target"), ("Variable", point_id, "createPoint")])
        self.names.append(("Trigger", trigger_id, name))
        return trigger_id


def script_lines(
    wave: ET.Element,
    definition: ET.Element,
    phase: str,
    scale_migrated_counts: bool = False,
) -> list[str]:
    source = int(definition.find("SourcePlayer").get("Value"))
    targets = definition.find("TargetPlayer").get("Value", "").split()
    arrival_node = next((x for x in wave.findall("Time") if x.get("Type") == "Arrival"), None)
    gather_node = next((x for x in wave.findall("Time") if x.get("Type") == "GatherTime"), None)
    arrival, gather = values(arrival_node, "Duration"), values(gather_node, "Duration")
    pre = [max(a - g, 0) if 0 < g < a else 0 for a, g in zip(arrival, gather)]
    send = [g if 0 < g < a else a for a, g in zip(arrival, gather)]
    lines: list[str] = []
    if phase == "pre":
        if any(pre):
            lines.append(f"            Wait({diff_fixed(pre)}, c_timeAI);")
        return lines
    if phase == "main":
        lines.append("            PlayerGroupClear(lv_target);")
        for player in targets:
            lines.append(f"            PlayerGroupAdd(lv_target, {player});")
        lines.append(f"            AIAttackWaveSetTargetPlayer({source}, lv_target);")
        default = definition.find("GatherDefault")
        if default is not None and default.get("Id"):
            lines.append(f"            AIAttackWaveSetGatherPoint({source}, PointFromId({default.get('Id')}));")
        for point in wave.findall("Point"):
            kind, pid, cond = point.get("Type"), point.get("Id"), active_expr(point)
            if kind not in {"Gather", "TargetPoint", "Waypoint", "Transport"}:
                continue
            call = {"Gather": "AIAttackWaveSetGatherPoint", "TargetPoint": "AIAttackWaveSetTargetPoint", "Waypoint": "AIAttackWaveAddWaypoint", "Transport": "AIAttackWaveAddWaypoint"}[kind]
            tail = ", true" if kind == "Transport" else (", false" if kind == "Waypoint" else "")
            statement = f"{call}({source}, PointFromId({pid}){tail});"
            lines.append(f"            if ({cond}) {{ {statement} }}" if cond else f"            {statement}")
        create = wave.find("CreateUnits") is not None
        units = wave.findall("Unit")
        if create and units:
            create_points = [p for p in wave.findall("Point") if p.get("Type") == "Create"]
            fallback = create_points[0].get("Id") if create_points else (default.get("Id") if default is not None else None)
            lines.append(f"            lv_createPoint = {'PointFromId('+fallback+')' if fallback else 'null'};")
            for point in create_points:
                cond = active_expr(point)
                statement = f"lv_createPoint = PointFromId({point.get('Id')});"
                lines.append(f"            if ({cond}) {{ {statement} }}" if cond else f"            {statement}")
            for unit in units:
                counts = values(unit, "Count")
                if scale_migrated_counts:
                    counts = [scale_count_75(value) for value in counts]
                count = diff_int(counts)
                count = f"lib67AA1763_gf_AttackWaveModifier({count})"
                utype = unit.get("Type")
                lines.append(f'            UnitCreate({count}, "{utype}", 0, {source}, lv_createPoint, PointGetFacing(lv_createPoint));')
                lines.append(f"            AIAttackWaveUseGroup({source}, UnitLastCreatedGroup());")
        else:
            for unit in units:
                counts_by_difficulty = values(unit, "Count")
                if scale_migrated_counts:
                    counts_by_difficulty = [
                        scale_count_75(value) for value in counts_by_difficulty
                    ]
                counts = [
                    f"lib67AA1763_gf_AttackWaveModifier({value})"
                    for value in counts_by_difficulty
                ]
                lines.append(f'            AIAttackWaveAddUnits4({", ".join(counts)}, "{unit.get("Type")}");')
        return lines
    if phase == "send":
        lines.append(f"            AIAttackWaveSend({source}, {diff_int(send)}, false);")
        if any(send):
            lines.append(f"            Wait({diff_fixed(send)}, c_timeAI);")
    return lines


def hooks(wave: ET.Element, at_end: bool) -> list[str]:
    result = []
    for node in wave.findall("Time"):
        trigger = node.get("Trigger")
        if trigger and (node.get("TriggerRunAtEnd") == "1") == at_end:
            result.append(trigger)
    return result


def wave_actions(
    build: Build,
    wave: ET.Element,
    definition: ET.Element,
    subtype: str | None,
    scale_migrated_counts: bool = False,
) -> list[str]:
    result: list[str] = []
    for phase in ("pre",):
        code = "\n".join(
            script_lines(wave, definition, phase, scale_migrated_counts)
        )
        if code:
            result.append(build.script(code, subtype))
    result.extend(build.execute(x, subtype) for x in hooks(wave, False))
    main = "\n".join(
        script_lines(wave, definition, "main", scale_migrated_counts)
    )
    if main:
        result.append(build.script(main, subtype))
    config = wave.find("ConfigTrigger")
    if config is not None and config.get("Value"):
        result.append(build.execute(config.get("Value"), subtype))
    send = "\n".join(
        script_lines(wave, definition, "send", scale_migrated_counts)
    )
    if send:
        result.append(build.script(send, subtype))
    result.extend(build.execute(x, subtype) for x in hooks(wave, True))
    return result


def convert(
    map_dir: Path,
    apply: bool,
    backup_dir: Path | None,
    start_trigger_name: str = "Start AI",
    scale_migrated_counts: bool = False,
) -> int:
    triggers, custom_ai = map_dir / "Triggers", map_dir / "CustomAI"
    strings = map_dir / "enUS.SC2Data" / "LocalizedData" / "TriggerStrings.txt"
    object_strings = map_dir / "enUS.SC2Data" / "LocalizedData" / "ObjectStrings.txt"
    with triggers.open("r", encoding="utf-8", newline="") as stream:
        text = stream.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    root = ET.fromstring(text)
    ai_root = ET.parse(custom_ai).getroot()
    definitions = [d for d in ai_root.findall("Definition") if d.get("Id") and d.findall("Step[@Type='Wave']")]
    if not definitions:
        print(f"{map_dir.name}: no personality waves")
        return 0
    if "Codex migrated AI personality" in text:
        print(f"{map_dir.name}: already migrated")
        return 0
    names = personality_names(object_strings)
    missing_names = [definition.get("Id", "") for definition in definitions if definition.get("Id", "") not in names]
    if missing_names:
        raise RuntimeError(f"Missing AI personality display names: {missing_names}")
    used = {e.get("Id") for e in root.findall("Element") if e.get("Id")}
    build = Build(used, newline)
    category_id = fresh(used)
    trigger_ids: list[str] = []
    main_trigger_ids: list[str] = []
    for definition in definitions:
        display_name = names[definition.get("Id", "")]
        waves = [x for x in definition.findall("Step") if x.get("Type") == "Wave"]
        async_ids: dict[int, str] = {}
        for index, wave in enumerate(waves):
            if wave.find("NoWait") is not None:
                acts = wave_actions(
                    build, wave, definition, None, scale_migrated_counts
                )
                async_ids[index] = build.trigger(
                    f"{display_name} Attack Wave {wave.get('Id')} Async", acts, False
                )
                trigger_ids.append(async_ids[index])
        actions = [build.script(f'            // Codex migrated AI personality\n            cai_waves_stop("ai{definition.get("Id")}");')]
        def add_wave(index: int, subtype: str | None) -> list[str]:
            if index in async_ids:
                return [build.execute(async_ids[index], subtype)]
            return wave_actions(
                build,
                waves[index],
                definition,
                subtype,
                scale_migrated_counts,
            )
        repeat_node = definition.find("RepeatWaves")
        repeat_count = int(repeat_node.get("Value", "0")) if repeat_node is not None else 0
        first_repeat = len(waves) - repeat_count if repeat_count > 0 else len(waves)
        for index in range(first_repeat):
            actions.extend(add_wave(index, None))
        if repeat_count > 0:
            loop_children: list[str] = []
            for index in range(first_repeat, len(waves)):
                loop_children.extend(add_wave(index, "4945FAA8"))
            actions.append(build.repeat(loop_children))
        trigger_id = build.trigger(f"{display_name} Attack Waves", actions, False)
        trigger_ids.append(trigger_id)
        main_trigger_ids.append(trigger_id)
    start_trigger_id = named_trigger_id(strings, start_trigger_name)
    startup_calls = [build.execute(trigger_id) for trigger_id in main_trigger_ids]
    text = append_actions(text, start_trigger_id, startup_calls, newline)
    item = f'        <Item Type="Category" Id="{category_id}"/>{newline}'
    text = text.replace(f"    </Root>{newline}", item + f"    </Root>{newline}", 1)
    cat_items = "".join(f'        <Item Type="Trigger" Id="{x}"/>{newline}' for x in trigger_ids)
    category = f'    <Element Type="Category" Id="{category_id}">{newline}{cat_items}    </Element>{newline}'
    generated = category + "".join(build.blocks)
    text = text.replace(f"</TriggerData>{newline}" if text.endswith(f"</TriggerData>{newline}") else "</TriggerData>", generated + "</TriggerData>" + (newline if text.endswith(newline) else ""), 1)
    ET.fromstring(text)
    print(f"{map_dir.name}: definitions={len(definitions)} triggers={len(trigger_ids)} new_elements={len(build.blocks)+1}")
    if not apply:
        return 0
    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for source in (triggers, custom_ai, strings):
            if not source.exists():
                continue
            target = backup_dir / f"{map_dir.name}.{source.name}.bak"
            if not target.exists():
                shutil.copy2(source, target)
    temporary = triggers.with_name("Triggers.codex.tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    shutil.copystat(triggers, temporary)
    os.replace(temporary, triggers)
    if strings.exists():
        with strings.open("r", encoding="utf-8", newline="") as stream:
            existing = stream.read()
    else:
        existing = ""
    additions = [("Category", category_id, "Migrated AI Personalities"), *build.names]
    with strings.open("a", encoding="utf-8", newline="") as stream:
        if existing and not existing.endswith(("\n", "\r")):
            stream.write(newline)
        for kind, element_id, name in additions:
            stream.write(f"{kind}/Name/{element_id}={name}{newline}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "INTERNAL compatibility stage. Use convert_custom_ai_to_gui.py for normal work; "
            "this tool writes temporary Custom Script actions."
        )
    )
    parser.add_argument("map_dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--start-trigger-name", default="Start AI")
    parser.add_argument("--scale-migrated-counts", action="store_true")
    parser.add_argument("--internal-allow-script-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.apply and not args.internal_allow_script_stage:
        raise ValueError(
            "Direct ScriptCode staging is disabled. Use convert_custom_ai_to_gui.py instead."
        )
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
