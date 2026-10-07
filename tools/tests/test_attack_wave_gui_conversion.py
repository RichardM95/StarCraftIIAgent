import importlib.util
import sys
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "sc2-attack-wave-scaling"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "convert_custom_ai_to_gui", SCRIPT_DIR / "convert_custom_ai_to_gui.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
import convert_custom_ai_to_trigger_scripts as STAGE_MODULE

GUI_SPEC = importlib.util.spec_from_file_location(
    "convert_migrated_scripts_to_gui",
    SCRIPT_DIR / "convert_migrated_scripts_to_gui.py",
)
GUI_MODULE = importlib.util.module_from_spec(GUI_SPEC)
assert GUI_SPEC.loader is not None
GUI_SPEC.loader.exec_module(GUI_MODULE)

OPT_SPEC = importlib.util.spec_from_file_location(
    "optimize_migrated_target_group",
    SCRIPT_DIR / "optimize_migrated_target_group.py",
)
OPT_MODULE = importlib.util.module_from_spec(OPT_SPEC)
assert OPT_SPEC.loader is not None
OPT_SPEC.loader.exec_module(OPT_MODULE)


class PureGuiValidationTests(unittest.TestCase):
    def setUp(self):
        self.original = "<TriggerData/>"

    def result(self, parameter_library: str) -> str:
        return f"""<TriggerData>
    <Element Type="Trigger" Id="11111111">
        <Action Type="FunctionCall" Id="22222222"/>
    </Element>
    <Element Type="FunctionCall" Id="22222222">
        <FunctionDef Type="FunctionDef" Library="Lotv" Id="A6DBDC2B"/>
        <Parameter Type="Param" Id="33333333"/>
    </Element>
    <Element Type="Param" Id="33333333">
        <ParameterDef Type="ParamDef" Library="{parameter_library}" Id="68571483"/>
        <Value>1</Value>
        <ValueType Type="int"/>
    </Element>
</TriggerData>"""

    def test_accepts_single_parent_pure_gui_tree(self):
        self.assertEqual(
            MODULE.validate_gui_result(self.original, self.result("Lotv")),
            (3, 1, 0),
        )

    def test_rejects_cross_library_parameter_definition(self):
        with self.assertRaisesRegex(RuntimeError, "cross-library"):
            MODULE.validate_gui_result(self.original, self.result("Ntve"))

    def test_rejects_new_script_code(self):
        with self.assertRaisesRegex(RuntimeError, "Custom Script"):
            MODULE.validate_gui_result(
                self.original,
                "<TriggerData><Element Type='FunctionCall' Id='AAAAAAAA'>"
                "<ScriptCode>bad();</ScriptCode></Element></TriggerData>",
            )

    def test_accepts_eventless_migrated_trigger_run_from_start_ai(self):
        triggers = """<TriggerData>
    <Element Type="Trigger" Id="AAAAAAAA">
        <Action Type="FunctionCall" Id="CCCCCCCC"/>
    </Element>
    <Element Type="Trigger" Id="BBBBBBBB"/>
    <Element Type="FunctionCall" Id="CCCCCCCC">
        <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000116"/>
        <Parameter Type="Param" Id="DDDDDDDD"/>
    </Element>
    <Element Type="Param" Id="DDDDDDDD">
        <ParameterDef Type="ParamDef" Library="Ntve" Id="00000182"/>
        <ValueType Type="trigger"/>
        <ValueElement Type="Trigger" Id="BBBBBBBB"/>
    </Element>
</TriggerData>"""
        strings = (
            "Trigger/Name/AAAAAAAA=Start AI\n"
            "Trigger/Name/BBBBBBBB=Protoss P02 Attack Waves\n"
        )
        ai_tree = ET.ElementTree(
            ET.fromstring(
                "<AIData><Definition Id='041954F3'><Step Type='Wave' Id='1'/></Definition></AIData>"
            )
        )
        with mock.patch.object(MODULE.ET, "parse", return_value=ai_tree):
            self.assertEqual(
                MODULE.validate_start_wiring(
                    triggers,
                    strings,
                    "\ufeffAI/Name/041954F3=Protoss P02\n",
                    Path("unused"),
                ),
                ("AAAAAAAA", ["BBBBBBBB"]),
            )

    def test_converts_wrapped_ai_attack_wave_add_units4_to_gui(self):
        build = GUI_MODULE.Build(set(), "\n")
        actions = GUI_MODULE.convert_script(
            build,
            'AIAttackWaveAddUnits4('
            'lib67AA1763_gf_AttackWaveModifier(8), '
            'lib67AA1763_gf_AttackWaveModifier(5), '
            'lib67AA1763_gf_AttackWaveModifier(1), '
            'lib67AA1763_gf_AttackWaveModifier(12), "ZerglingW");',
            "AAAAAAAA",
            None,
        )
        generated = "".join(build.blocks)
        self.assertEqual(len(actions), 1)
        self.assertIn('Library="Ntve" Id="253D7FAD"', generated)
        self.assertIn('Id="0FEB500B"', generated)
        self.assertEqual(generated.count('Library="67AA1763" Id="4F54E5A0"'), 4)
        self.assertNotIn("ScriptCode", generated)
        root = ET.fromstring(f"<TriggerData>{generated}</TriggerData>")
        elements = {element.get("Id", ""): element for element in root.findall("Element")}
        values_by_definition = {}
        for element in root.findall("Element"):
            definition = element.find("ParameterDef")
            nested = element.find("FunctionCall")
            if definition is None or nested is None:
                continue
            if definition.get("Id") not in {"A166DBF3", "B52CD455", "AD14DE85", "24D9A2D7"}:
                continue
            modifier = elements[nested.get("Id", "")]
            amount_ref = modifier.find("Parameter")
            amount = elements[amount_ref.get("Id", "")]
            values_by_definition[definition.get("Id", "")] = amount.findtext("Value")
        self.assertEqual(
            values_by_definition,
            {
                "24D9A2D7": "8",
                "B52CD455": "5",
                "AD14DE85": "1",
                "A166DBF3": "12",
            },
        )

    def test_converts_transport_waypoint_to_gui_true_preset(self):
        build = GUI_MODULE.Build(set(), "\n")
        actions = GUI_MODULE.convert_script(
            build,
            "AIAttackWaveAddWaypoint(3, PointFromId(81), true);",
            "AAAAAAAA",
            None,
        )
        generated = "".join(build.blocks)
        self.assertEqual(len(actions), 1)
        self.assertIn('Library="Ntve" Id="17E6D92B"', generated)
        self.assertIn('Id="97A85CF7"', generated)
        self.assertIn('Library="Ntve" Id="75B749DB"', generated)
        self.assertNotIn("ScriptCode", generated)

    def test_add_player_uses_player_then_group_parameter_definitions(self):
        build = GUI_MODULE.Build(set(), "\n")
        build.add_player("AAAAAAAA", "1", None)
        generated = "".join(build.blocks)
        self.assertRegex(
            generated,
            r'Id="1D6C8796"/>\n\s*<Value>1</Value>\n\s*<ValueType Type="int"/>',
        )
        self.assertRegex(
            generated,
            r'Id="F4B91B76"/>\n\s*<Variable Type="Variable" Id="AAAAAAAA"/>',
        )

    def test_reuses_unchanged_target_player_group_across_script_blocks(self):
        build = GUI_MODULE.Build(set(), "\n")
        state = {}
        code = (
            "PlayerGroupClear(lv_target);\n"
            "PlayerGroupAdd(lv_target, 1);\n"
            "AIAttackWaveSetTargetPlayer(2, lv_target);"
        )
        first = GUI_MODULE.convert_script(build, code, "AAAAAAAA", None, state)
        second = GUI_MODULE.convert_script(build, code, "AAAAAAAA", None, state)
        generated = "".join(build.blocks)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 1)
        self.assertEqual(generated.count('Library="Ntve" Id="00000136"'), 1)
        self.assertEqual(generated.count('Library="Ntve" Id="00000057"'), 1)
        self.assertEqual(generated.count('Library="Ntve" Id="15C2C248"'), 0)
        self.assertIn('Id="00000094"', generated)
        self.assertIn('<Value>1</Value>', generated)
        self.assertEqual(generated.count('Library="Ntve" Id="3955F80B"'), 2)

    def test_removes_only_unreferenced_migrated_local_variables(self):
        triggers = """<TriggerData>
    <Element Type="Trigger" Id="AAAAAAAA">
        <Variable Type="Variable" Id="BBBBBBBB"/>
        <Variable Type="Variable" Id="CCCCCCCC"/>
    </Element>
    <Element Type="Variable" Id="BBBBBBBB">
        <VariableType><Type Value="point"/></VariableType>
    </Element>
    <Element Type="Variable" Id="CCCCCCCC">
        <VariableType><Type Value="playergroup"/></VariableType>
    </Element>
    <Element Type="Param" Id="DDDDDDDD">
        <Variable Type="Variable" Id="CCCCCCCC"/>
    </Element>
</TriggerData>"""
        result, removed = GUI_MODULE.remove_unused_local_variables(
            triggers, {"AAAAAAAA"}
        )
        self.assertEqual(removed, 1)
        self.assertNotIn("BBBBBBBB", result)
        self.assertIn("CCCCCCCC", result)

    def test_batch_optimizer_selects_only_triggers_that_stop_a_personality(self):
        triggers = """<TriggerData>
    <Element Type="Trigger" Id="AAAAAAAA">
        <Action Type="FunctionCall" Id="CCCCCCCC"/>
    </Element>
    <Element Type="Trigger" Id="BBBBBBBB">
        <Action Type="FunctionCall" Id="DDDDDDDD"/>
    </Element>
    <Element Type="FunctionCall" Id="CCCCCCCC">
        <FunctionDef Type="FunctionDef" Library="Ntve" Id="898E65C3"/>
    </Element>
    <Element Type="FunctionCall" Id="DDDDDDDD">
        <FunctionDef Type="FunctionDef" Library="Ntve" Id="3A0403D0"/>
    </Element>
</TriggerData>"""
        self.assertEqual(OPT_MODULE.migrated_trigger_ids(triggers), {"AAAAAAAA"})

    def test_optimizer_removes_nested_target_pairs_and_hoists_one_assignment(self):
        group_id = "AAAAAAAA"
        trigger_id = "BBBBBBBB"
        build = GUI_MODULE.Build({group_id, trigger_id}, "\n")
        stop_id = build.stop_personality("ai041954F3", None)
        existing_id = build.set_player_group_single(group_id, "1", None)
        clear_id = build.clear_group(group_id, None)
        wrong_add_id = build.call(
            "Ntve",
            "15C2C248",
            [
                build.variable("1D6C8796", group_id),
                build.literal("F4B91B76", "1", "int"),
            ],
        )
        loop_id = build.call("Ntve", "00000142", children=[clear_id, wrong_add_id])
        triggers = (
            "<TriggerData>\n"
            f'    <Element Type="Trigger" Id="{trigger_id}">\n'
            f'        <Variable Type="Variable" Id="{group_id}"/>\n'
            f'        <Action Type="FunctionCall" Id="{stop_id}"/>\n'
            f'        <Action Type="FunctionCall" Id="{existing_id}"/>\n'
            f'        <Action Type="FunctionCall" Id="{loop_id}"/>\n'
            "    </Element>\n"
            f'    <Element Type="Variable" Id="{group_id}">\n'
            '        <VariableType><Type Value="playergroup"/></VariableType>\n'
            "    </Element>\n"
            + "".join(build.blocks)
            + "</TriggerData>"
        )
        result, pair_count, unused, player = OPT_MODULE.optimize(
            triggers, trigger_id, None
        )
        root = ET.fromstring(result)
        elements = {element.get("Id", ""): element for element in root.findall("Element")}
        trigger = elements[trigger_id]
        containers = OPT_MODULE.reachable_action_containers(trigger, elements)
        calls = [
            elements[reference.get("Id", "")]
            for container in containers
            for reference in OPT_MODULE.action_references(container)
        ]
        self.assertEqual(pair_count, 1)
        self.assertEqual(unused, 0)
        self.assertEqual(player, "1")
        self.assertFalse(any(OPT_MODULE.function_id(call) == "15C2C248" for call in calls))
        self.assertEqual(
            sum(
                OPT_MODULE.single_assignment_details(call, elements) is not None
                for call in calls
            ),
            1,
        )
        self.assertIsNotNone(
            OPT_MODULE.single_assignment_details(
                elements[trigger.findall("Action")[1].get("Id", "")], elements
            )
        )

    def test_mirrors_personality_stop_into_cleanup_trigger_only(self):
        triggers = """<TriggerData>
    <Element Type="Trigger" Id="AAAAAAAA">
        <Action Type="FunctionCall" Id="CCCCCCCC"/>
    </Element>
    <Element Type="Trigger" Id="BBBBBBBB">
        <Action Type="FunctionCall" Id="DDDDDDDD"/>
    </Element>
    <Element Type="FunctionCall" Id="CCCCCCCC">
        <FunctionDef Type="FunctionDef" Library="Ntve" Id="898E65C3"/>
        <Parameter Type="Param" Id="EEEEEEEE"/>
    </Element>
    <Element Type="Param" Id="EEEEEEEE">
        <ParameterDef Type="ParamDef" Library="Ntve" Id="9904C380"/>
        <Value>ai041954F3</Value>
        <ValueType Type="aidef"/>
    </Element>
    <Element Type="FunctionCall" Id="DDDDDDDD">
        <FunctionDef Type="FunctionDef" Library="Ntve" Id="898E65C3"/>
        <Parameter Type="Param" Id="FFFFFFFF"/>
    </Element>
    <Element Type="Param" Id="FFFFFFFF">
        <ParameterDef Type="ParamDef" Library="Ntve" Id="9904C380"/>
        <Value>ai041954F3</Value>
        <ValueType Type="aidef"/>
    </Element>
</TriggerData>
"""
        strings = "Trigger/Name/AAAAAAAA=Protoss P02 Attack Waves\n"
        ai_tree = ET.ElementTree(
            ET.fromstring(
                "<AIData><Definition Id='041954F3'><Step Type='Wave' Id='1'/></Definition></AIData>"
            )
        )
        with mock.patch.object(MODULE.ET, "parse", return_value=ai_tree):
            result, added = MODULE.wire_personality_stop_sites(
                triggers,
                strings,
                "AI/Name/041954F3=Protoss P02\n",
                Path("unused"),
            )
            second_result, second_added = MODULE.wire_personality_stop_sites(
                result,
                strings,
                "AI/Name/041954F3=Protoss P02\n",
                Path("unused"),
            )
        self.assertEqual(added, 1)
        self.assertEqual(second_added, 0)
        self.assertEqual(second_result, result)
        self.assertEqual(result.count('Library="Ntve" Id="698FE891"'), 1)
        self.assertEqual(result.count('ValueElement Type="Trigger" Id="AAAAAAAA"'), 1)

    def test_scales_only_migrated_ai_unit_counts_when_requested(self):
        definition = ET.fromstring(
            "<Definition><SourcePlayer Value='2'/><TargetPlayer Value='1'/></Definition>"
        )
        wave = ET.fromstring(
            "<Step Type='Wave'><Unit Type='ZerglingW'>"
            "<Count DiffLevel='1' Value='8'/><Count DiffLevel='2' Value='5'/>"
            "<Count DiffLevel='3' Value='1'/><Count DiffLevel='4' Value='0'/>"
            "</Unit></Step>"
        )
        lines = STAGE_MODULE.script_lines(wave, definition, "main", True)
        expected = (
            "AIAttackWaveAddUnits4("
            "lib67AA1763_gf_AttackWaveModifier(6), "
            "lib67AA1763_gf_AttackWaveModifier(4), "
            "lib67AA1763_gf_AttackWaveModifier(1), "
            "lib67AA1763_gf_AttackWaveModifier(0), \"ZerglingW\");"
        )
        self.assertTrue(any(expected in line for line in lines))

    def test_renames_legacy_migrated_personality_triggers(self):
        ai_tree = ET.ElementTree(
            ET.fromstring(
                "<AIData><Definition Id='041954F3'><Step Type='Wave' Id='1'/></Definition></AIData>"
            )
        )
        strings = (
            "Trigger/Name/AAAAAAAA=AI 041954F3 Migrated Waves\r\n"
            "Trigger/Name/BBBBBBBB=AI 041954F3 Wave 9 Async\r\n"
        )
        with mock.patch.object(MODULE.ET, "parse", return_value=ai_tree):
            result, changed = MODULE.rename_legacy_migrated_triggers(
                strings,
                "AI/Name/041954F3=05 Protoss P02\n",
                Path("unused"),
            )
        self.assertEqual(changed, 2)
        self.assertIn("Trigger/Name/AAAAAAAA=05 Protoss P02 Attack Waves", result)
        self.assertIn("Trigger/Name/BBBBBBBB=05 Protoss P02 Attack Wave 9 Async", result)


if __name__ == "__main__":
    unittest.main()
