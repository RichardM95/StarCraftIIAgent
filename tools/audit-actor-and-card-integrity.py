#!/usr/bin/env python3
"""Audit command card layouts for high-confidence slot collisions."""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sc2_paths import find_project_mods

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mutually exclusive pairs or state toggles allowed to share the same slot
KNOWN_TOGGLE_FACES = {
    ("EnableBuildingAttack", "DisableBuildingAttack"),
    ("GhostHoldFire", "GhostWeaponsFree"),
    ("BiomassPassive", "BiomassPassiveEmpty"),
    ("BiomassPassiveEnergy", "BiomassPassiveEmpty"),
    ("MorphBackToGateway", "MorphBackToGateway"),
    ("Cancel", "Cancel"),
    ("Attack", "AcquireMove"),
    ("Attack", "AttackBuilding"),
}


def is_intentional_overlap(
    buttons: list[ET.Element],
    command_requirements: dict[tuple[str, str], str],
    show_nodes: dict[str, str],
) -> bool:
    """Recognize only slot sharing with an explicit SC2 state distinction."""
    # A producer may share the cancel slot between its construction,
    # training queue, and in-progress morph. These commands are exposed in
    # different states, even when all three are declared on the same card.
    if len(buttons) >= 2 and all(
        button.get("Type") == "AbilCmd"
        and (
            (button.get("Face") == "CancelBuilding" and button.get("AbilCmd") == "BuildInProgress,Cancel")
            or (button.get("Face") == "Cancel" and (
                button.get("AbilCmd", "").endswith(",CancelLast")
                or button.get("AbilCmd", "").endswith(",Cancel")
            ))
        )
        for button in buttons
    ) and any(button.get("Face") == "CancelBuilding" for button in buttons):
        return True
    if len(buttons) != 2:
        return False
    first, second = buttons
    faces = {first.get("Face", ""), second.get("Face", "")}
    commands = [button.get("AbilCmd", "") for button in buttons]

    if faces == {"Cancel", "CancelBuilding"}:
        return any(cmd.startswith("BuildInProgress,Cancel") for cmd in commands) and any(
            cmd.endswith(",CancelLast")
            or cmd in {"StructureCancelI,Execute", "MorphBackToGatewayI,Cancel"}
            for cmd in commands
        )
    if first.get("Face") == second.get("Face") and {first.get("Type"), second.get("Type")} == {
        "AbilCmd", "Passive"
    }:
        return True
    if all("," in cmd for cmd in commands):
        first_ability, first_command = commands[0].split(",", 1)
        second_ability, second_command = commands[1].split(",", 1)
        if first_ability == second_ability and {first_command, second_command} == {"On", "Off"}:
            return True
        if first.get("Face") == second.get("Face") and first_ability == second_ability:
            if {first_command, second_command} == {"Rally1", "Rally2"}:
                return True
        first_req = command_requirements.get((first_ability, first_command), "")
        second_req = command_requirements.get((second_ability, second_command), "")
        first_show = show_nodes.get(first_req, "")
        second_show = show_nodes.get(second_req, "")
        if first_show and second_show and (
            first_show == "Not" + second_show or second_show == "Not" + first_show
        ):
            return True
    return False


def find_local_mods(explicit: str | None = None) -> list[Path]:
    return find_project_mods(REPO_ROOT, explicit)


def check_command_card_layouts(game_data_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    unit_xml = game_data_dir / "UnitData.xml"
    if not unit_xml.is_file():
        # Fall back to checking GameData.xml if UnitData.xml is absent
        unit_xml = game_data_dir / "GameData.xml"
        if not unit_xml.is_file():
            return errors, warnings

    try:
        tree = ET.parse(unit_xml)
        root = tree.getroot()
    except Exception as e:
        errors.append(f"Failed to parse {unit_xml.name}: {e}")
        return errors, warnings

    command_requirements: dict[tuple[str, str], str] = {}
    abil_xml = game_data_dir / "AbilData.xml"
    if abil_xml.is_file():
        try:
            for ability in ET.parse(abil_xml).getroot():
                ability_id = ability.get("id", "")
                for info in ability.findall("InfoArray"):
                    button = info.find("Button")
                    if button is not None and button.get("Requirements"):
                        command_requirements[(ability_id, info.get("index", ""))] = button.get(
                            "Requirements", ""
                        )
        except ET.ParseError as exc:
            errors.append(f"Failed to parse {abil_xml.name}: {exc}")
            return errors, warnings

    show_nodes: dict[str, str] = {}
    req_xml = game_data_dir / "RequirementData.xml"
    if req_xml.is_file():
        try:
            for requirement in ET.parse(req_xml).getroot().findall("CRequirement"):
                show = requirement.find("NodeArray[@index='Show']")
                if show is not None:
                    show_nodes[requirement.get("id", "")] = show.get("Link", "")
        except ET.ParseError as exc:
            errors.append(f"Failed to parse {req_xml.name}: {exc}")
            return errors, warnings

    for unit in root.findall("CUnit"):
        unit_id = unit.attrib.get("id", "")
        if not unit_id:
            continue

        weapons = unit.findall("WeaponArray")
        for layout in unit.findall("CardLayouts"):
            layout_idx = layout.attrib.get("index", "0")
            card_id = layout.attrib.get("CardId", "")
            if layout_idx != "0" and not card_id:
                continue
            layout_label = card_id or layout_idx

            for btn in layout.findall("LayoutButtons"):
                if btn.attrib.get("removed") == "1":
                    continue
                btn_idx = btn.attrib.get("index", "")
                face = btn.attrib.get("Face", "")
                btn_type = btn.attrib.get("Type", "")

                # If index is 4 (standard Attack command slot), ensure it's not a passive
                if btn_idx == "4" and btn_type == "Passive" and weapons:
                    errors.append(
                        f"Unit '{unit_id}' has standard Attack slot index='4' replaced by passive button '{face}'."
                    )

            # Check for non-toggle button slot collisions
            slots: dict[tuple[str, str], list[ET.Element]] = {}
            for btn in layout.findall("LayoutButtons"):
                if btn.attrib.get("removed") == "1":
                    continue
                row = btn.attrib.get("Row", "")
                col = btn.attrib.get("Column", "")
                face = btn.attrib.get("Face", "")
                if row and col and face:
                    slots.setdefault((row, col), []).append(btn)

            for (r, c), buttons in slots.items():
                if len(buttons) > 1:
                    faces = [button.get("Face", "") for button in buttons]
                    if is_intentional_overlap(buttons, command_requirements, show_nodes):
                        continue
                    is_toggle = len(faces) == 2 and (
                        (faces[0], faces[1]) in KNOWN_TOGGLE_FACES
                        or (faces[1], faces[0]) in KNOWN_TOGGLE_FACES
                    )
                    if not is_toggle:
                        warnings.append(
                            f"Unit '{unit_id}' CardLayout[{layout_label}] has colliding buttons at (Row={r}, Col={c}): {faces}"
                        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit command card layouts for high-confidence slot collisions."
    )
    parser.add_argument("--mod-dir", help="Explicit path to .SC2Mod component directory")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unresolved slot-collision candidates as failures.",
    )
    parser.add_argument(
        "--show-warnings",
        action="store_true",
        help="Print every slot-collision candidate instead of only the count.",
    )
    args = parser.parse_args()

    mods = find_local_mods(args.mod_dir)
    if not mods:
        print("ERROR: No .SC2Mod directory found to audit.")
        print("Pass --mod-dir or correct agent-config.json (SC2_MODS_PATH is a fallback).")
        return 2

    all_errors: list[str] = []
    all_warnings: list[str] = []
    audited_mods = 0
    for mod in mods:
        game_data = mod / "Base.SC2Data" / "GameData"
        if not game_data.is_dir():
            all_errors.append(f"[{mod.name}] Missing Base.SC2Data/GameData directory.")
            continue
        audited_mods += 1
        errors, warnings = check_command_card_layouts(game_data)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    print("=" * 60)
    print("COMMAND CARD INTEGRITY AUDIT")
    print("=" * 60)
    print(f"Target: {mods[0]}")
    print(f"Audited mod directories: {audited_mods}")
    for issue in all_errors:
        print(f"  [INTEGRITY ERROR] {issue}")
    if args.show_warnings or args.strict:
        for warning in all_warnings:
            print(f"  [COLLISION CANDIDATE] {warning}")
    elif all_warnings:
        print(
            f"Collision candidates requiring dependency/requirement review: {len(all_warnings)} "
            "(use --show-warnings or --strict for details)"
        )

    if all_errors:
        print(f"\nAudit failed with {len(all_errors)} high-confidence error(s).")
        return 1
    if args.strict and all_warnings:
        print(f"\nStrict audit failed with {len(all_warnings)} collision candidate(s).")
        return 1

    print("No high-confidence command-card errors found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
