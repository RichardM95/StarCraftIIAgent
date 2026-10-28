"""Keystone candidates: portable fixtures plus an explicitly read-only map check."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

from PIL import Image
import pytest

from sc2_mcp.errors import SC2Error


_MODULE = Path(__file__).resolve().parents[1] / "src/sc2_mcp/keystone.py"
_SPEC = importlib.util.spec_from_file_location("sc2_mcp._keystone_under_test", _MODULE)
k = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = k
_SPEC.loader.exec_module(k)


_REFERENCE_FUNCTIONS = {
  "lib1_gf_GetUnitTextForCollectionCard": "string lib1_gf_GetUnitTextForCollectionCard (int lp_card_id) {\n    // Variable Declarations\n    string[lib1_gv_mAX_UNIT_TYPE_PER_CARD + 1] lv_unit_type;\n    int[lib1_gv_mAX_UNIT_TYPE_PER_CARD + 1] lv_unit_type_count;\n    int lv_unit_type_index;\n    int lv_unit_type_index_inner_loop;\n    int lv_next_index_to_insert;\n    bool lv_match_found;\n    string lv_text;\n\n    // Automatic Variable Declarations\n    const int auto7BAEEFF2_ae = lib1_gv_mAX_UNIT_TYPE_PER_CARD;\n    const int auto7BAEEFF2_ai = 1;\n    int auto8A8609F5_ae;\n    const int auto8A8609F5_ai = 1;\n    const int autoAAFB52CA_ae = lib1_gv_mAX_UNIT_TYPE_PER_CARD;\n    const int autoAAFB52CA_ai = 1;\n\n    // Variable Initialization\n    lv_text = \"\";\n\n    // Implementation\n    lv_unit_type_index = 0;\n    for ( ; ( (auto7BAEEFF2_ai >= 0 && lv_unit_type_index <= auto7BAEEFF2_ae) || (auto7BAEEFF2_ai < 0 && lv_unit_type_index >= auto7BAEEFF2_ae) ) ; lv_unit_type_index += auto7BAEEFF2_ai ) {\n        if ((lib1_gv_card[lp_card_id].lv_unit_count[lv_unit_type_index] > 0)) {\n            if ((lv_unit_type_index == 0)) {\n                lv_unit_type[lv_next_index_to_insert] = lib1_gv_card[lp_card_id].lv_unit_type[lv_unit_type_index];\n                lv_unit_type_count[lv_next_index_to_insert] = lib1_gv_card[lp_card_id].lv_unit_count[lv_unit_type_index];\n                lv_next_index_to_insert = (lv_next_index_to_insert + 1);\n            }\n            else {\n                lv_match_found = false;\n                auto8A8609F5_ae = lv_unit_type_index;\n                lv_unit_type_index_inner_loop = 0;\n                for ( ; ( (auto8A8609F5_ai >= 0 && lv_unit_type_index_inner_loop <= auto8A8609F5_ae) || (auto8A8609F5_ai < 0 && lv_unit_type_index_inner_loop >= auto8A8609F5_ae) ) ; lv_unit_type_index_inner_loop += auto8A8609F5_ai ) {\n                    if ((lib1_gf_GetCardSpecificUnitDisplayName(lp_card_id, lib1_gv_card[lp_card_id].lv_unit_type[lv_unit_type_index]) == lib1_gf_GetCardSpecificUnitDisplayName(lp_card_id, lv_unit_type[lv_unit_type_index_inner_loop]))) {\n                        lv_unit_type_count[lv_unit_type_index_inner_loop] = (lv_unit_type_count[lv_unit_type_index_inner_loop] + lib1_gv_card[lp_card_id].lv_unit_count[lv_unit_type_index]);\n                        lv_match_found = true;\n                        break;\n                    }\n\n                }\n                if ((lv_match_found == false)) {\n                    lv_unit_type[lv_next_index_to_insert] = lib1_gv_card[lp_card_id].lv_unit_type[lv_unit_type_index];\n                    lv_unit_type_count[lv_next_index_to_insert] = lib1_gv_card[lp_card_id].lv_unit_count[lv_unit_type_index];\n                    lv_next_index_to_insert = (lv_next_index_to_insert + 1);\n                }\n\n            }\n        }\n        else {\n            break;\n        }\n    }\n    lv_unit_type_index = 0;\n    for ( ; ( (autoAAFB52CA_ai >= 0 && lv_unit_type_index <= autoAAFB52CA_ae) || (autoAAFB52CA_ai < 0 && lv_unit_type_index >= autoAAFB52CA_ae) ) ; lv_unit_type_index += autoAAFB52CA_ai ) {\n        if ((lv_unit_type_count[lv_unit_type_index] > 0)) {\n            if ((lv_unit_type_index == 0)) {\n                lv_text = \"派出 \";\n            }\n            else if (true) {\n                lv_text = (lv_text + \"、\");\n            }\n            lv_text = (lv_text + IntToString(lv_unit_type_count[lv_unit_type_index]));\n            lv_text = (lv_text + \" \");\n            if ((lv_unit_type_count[lv_unit_type_index] == 1)) {\n                lv_text = (lv_text + lib1_gf_GetCardSpecificUnitDisplayName(lp_card_id, lv_unit_type[lv_unit_type_index]));\n            }\n            else {\n                lv_text = (lv_text + lib1_gf_GetCardSpecificUnitDisplayName(lp_card_id, lv_unit_type[lv_unit_type_index]));\n            }\n            if (((lv_unit_type_index == lib1_gv_mAX_UNIT_TYPE_PER_CARD) || (lv_unit_type_count[(lv_unit_type_index + 1)] == 0))) {\n                lv_text = (lv_text + \"。\");\n                break;\n            }\n\n        }\n\n    }\n    return lv_text;\n}",
  "lib1_gf_GetCardSpecificUnitDisplayName": "string lib1_gf_GetCardSpecificUnitDisplayName (int lp_card_id, string lp_unit_type) {\n    // Implementation\n    if (((lp_card_id == 877) && (lp_unit_type == \"ColossusPurifier2\"))) {\n        return \"巨像-战争使者\";\n    }\n    if (((lp_card_id == 919) && ((lp_unit_type == \"Cyclone\") || (lp_unit_type == \"CycloneMakeshift\")))) {\n        return TextToString(StringExternal(\"Card/Name/Makeshift_Cyclones\"));\n    }\n    return lib1_gf_GetUnitDisplayNameasString(lp_unit_type);\n}",
  "lib1_gf_GetUnitDisplayNameasString": "string lib1_gf_GetUnitDisplayNameasString (string lp_unit_type) {\n    // Variable Declarations\n    string lv_name;\n\n    // Automatic Variable Declarations\n    // Variable Initialization\n    lv_name = \"\";\n\n    // Implementation\n    if (((lp_unit_type == null) || (lp_unit_type == \"\"))) {\n        return \"None\";\n    }\n    lv_name = TextToString(UnitTypeGetName(lp_unit_type));\n    if (((lv_name == null) || (lv_name == \"\"))) {\n        return lib1_gf_GetUnitNameasString(false, lp_unit_type);\n    }\n    return lv_name;\n}",
  "lib1_gf_PortraitsPerPage": "int lib1_gf_PortraitsPerPage () {\n    // Automatic Variable Declarations\n    // Implementation\n    return ((lib1_gv_pORTRAIT_PICKER_MAX_COLUMN + 1) * (lib1_gv_pORTRAIT_PICKER_MAX_ROW + 1));\n}",
  "lib1_gf_PlayerPortraitRowCount": "int lib1_gf_PlayerPortraitRowCount (int lp_player) {\n    // Variable Declarations\n    int lv_portrait_id;\n    int lv_visible_portrait_count;\n\n    // Automatic Variable Declarations\n    const int auto3E019BF3_ae = lib1_gv_pORTRAIT_LIMIT;\n    const int auto3E019BF3_ai = 1;\n\n    // Variable Initialization\n\n    // Implementation\n    lv_portrait_id = 0;\n    for ( ; ( (auto3E019BF3_ai >= 0 && lv_portrait_id <= auto3E019BF3_ae) || (auto3E019BF3_ai < 0 && lv_portrait_id >= auto3E019BF3_ae) ) ; lv_portrait_id += auto3E019BF3_ai ) {\n        if ((lib1_gf_PortraitVisible(lp_player, lv_portrait_id) == true)) {\n            lv_visible_portrait_count = (lv_visible_portrait_count + 1);\n        }\n\n    }\n    return CeilingI((IntToFixed(lv_visible_portrait_count) / IntToFixed((lib1_gv_pORTRAIT_PICKER_MAX_COLUMN + 1))));\n}",
  "lib1_gf_MaxPortraitPage": "int lib1_gf_MaxPortraitPage (int lp_player) {\n    // Variable Declarations\n    int lv_page_count;\n\n    // Automatic Variable Declarations\n    // Implementation\n    lv_page_count = CeilingI((IntToFixed(lib1_gf_PlayerPortraitRowCount(lp_player)) / IntToFixed((lib1_gv_pORTRAIT_PICKER_MAX_ROW + 1))));\n    return MaxI((lv_page_count - 1), 0);\n}",
  "lib1_gf_OpenPortraitPicker": "void lib1_gf_OpenPortraitPicker (int lp_player, int lp_page) {\n    // Variable Declarations\n    int lv_row;\n    int lv_column;\n    int lv_portrait_id;\n    int lv_shift_count;\n    int lv_shift_increment;\n    int lv_shift_amount;\n    int lv_count_processed;\n\n    // Automatic Variable Declarations\n    const int auto23496324_ae = lib1_gv_pORTRAIT_PICKER_MAX_ROW;\n    const int auto23496324_ai = 1;\n    const int auto0804F67D_ae = lib1_gv_pORTRAIT_PICKER_MAX_COLUMN;\n    const int auto0804F67D_ai = 1;\n    const int autoB6F8A6AF_ae = lib1_gv_pORTRAIT_LIMIT;\n    const int autoB6F8A6AF_ai = 1;\n\n    // Variable Initialization\n    lv_shift_increment = 172;\n    lv_count_processed = 0;\n\n    // Implementation\n    lib1_gf_ExitCurrentMenu(lp_player);\n    lib1_gf_ClosePortraitPicker(lp_player);\n    lib1_gv_player_collection[lp_player].lv_portrait_page = lp_page;\n    DialogSetVisible(lib1_gv_portrait_picker_dialog, PlayerGroupSingle(lp_player), true);\n    lib1_gf_DisableNavButton(lp_player, lib1_gv_main_menu_profile_pic_button);\n    if ((lp_page == 0)) {\n        DialogControlSetVisible(lib1_gv_portrait_picker_left_arrow, PlayerGroupSingle(lp_player), false);\n        DialogControlSetEnabled(lib1_gv_portrait_picker_left_arrow_button, PlayerGroupSingle(lp_player), false);\n    }\n    else {\n        DialogControlSetVisible(lib1_gv_portrait_picker_left_arrow, PlayerGroupSingle(lp_player), true);\n        DialogControlSetEnabled(lib1_gv_portrait_picker_left_arrow_button, PlayerGroupSingle(lp_player), true);\n    }\n    if ((lp_page >= lib1_gf_MaxPortraitPage(lp_player))) {\n        DialogControlSetVisible(lib1_gv_portrait_picker_right_arrow, PlayerGroupSingle(lp_player), false);\n        DialogControlSetEnabled(lib1_gv_portrait_picker_right_arrow_button, PlayerGroupSingle(lp_player), false);\n    }\n    else {\n        DialogControlSetVisible(lib1_gv_portrait_picker_right_arrow, PlayerGroupSingle(lp_player), true);\n        DialogControlSetEnabled(lib1_gv_portrait_picker_right_arrow_button, PlayerGroupSingle(lp_player), true);\n    }\n    lv_row = 0;\n    for ( ; ( (auto23496324_ai >= 0 && lv_row <= auto23496324_ae) || (auto23496324_ai < 0 && lv_row >= auto23496324_ae) ) ; lv_row += auto23496324_ai ) {\n        lv_column = 0;\n        for ( ; ( (auto0804F67D_ai >= 0 && lv_column <= auto0804F67D_ae) || (auto0804F67D_ai < 0 && lv_column >= auto0804F67D_ae) ) ; lv_column += auto0804F67D_ai ) {\n            DialogControlSetVisible(lib1_gv_portrait_picker_button[lv_row][lv_column], PlayerGroupSingle(lp_player), false);\n            DialogControlSetVisible(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), false);\n            libNtve_gf_SetDialogItemTooltip(lib1_gv_portrait_picker_image[lv_row][lv_column], StringToText(\"\"), PlayerGroupSingle(lp_player));\n        }\n    }\n    lv_row = 0;\n    lv_column = 0;\n    lv_portrait_id = 0;\n    for ( ; ( (autoB6F8A6AF_ai >= 0 && lv_portrait_id <= autoB6F8A6AF_ae) || (autoB6F8A6AF_ai < 0 && lv_portrait_id >= autoB6F8A6AF_ae) ) ; lv_portrait_id += autoB6F8A6AF_ai ) {\n        if ((lv_count_processed >= (lib1_gf_PortraitsPerPage() * (lp_page + 1)))) {\n            break;\n        }\n\n        if ((lib1_gf_PortraitVisible(lp_player, lv_portrait_id) == true)) {\n            if ((lv_count_processed >= (lib1_gf_PortraitsPerPage() * lp_page))) {\n                lv_count_processed = (lv_count_processed + 1);\n                DialogControlSetVisible(lib1_gv_portrait_picker_button[lv_row][lv_column], PlayerGroupSingle(lp_player), true);\n                DialogControlSetVisible(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), true);\n                libNtve_gf_SetDialogItemImage(lib1_gv_portrait_picker_image[lv_row][lv_column], lib1_gf_PortraitResolvedImage(lib1_gv_cosmetic_portrait[lv_portrait_id].lv_save_id, lib1_gv_cosmetic_portrait[lv_portrait_id].lv_image), PlayerGroupSingle(lp_player));\n                libNtve_gf_SetDialogItemCurrentValue(lib1_gv_portrait_picker_button[lv_row][lv_column], lib1_gv_cosmetic_portrait[lv_portrait_id].lv_save_id, PlayerGroupSingle(lp_player));\n                if ((lib1_gf_PortraitAvailable(lp_player, lv_portrait_id) == true)) {\n                    DialogControlFadeTransparency(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), 0.0, 0.0);\n                    if ((lib1_gv_player_cosmetics[lp_player].lv_portrait_save_id == lib1_gv_cosmetic_portrait[lv_portrait_id].lv_save_id)) {\n                        DialogControlSetEnabled(lib1_gv_portrait_picker_button[lv_row][lv_column], PlayerGroupSingle(lp_player), true);\n                        DialogControlSetEnabled(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), true);\n                    }\n                    else {\n                        DialogControlSetEnabled(lib1_gv_portrait_picker_button[lv_row][lv_column], PlayerGroupSingle(lp_player), true);\n                        DialogControlSetEnabled(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), false);\n                    }\n                }\n                else {\n                    DialogControlSetEnabled(lib1_gv_portrait_picker_button[lv_row][lv_column], PlayerGroupSingle(lp_player), false);\n                    DialogControlSetEnabled(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), false);\n                    DialogControlFadeTransparency(lib1_gv_portrait_picker_image[lv_row][lv_column], PlayerGroupSingle(lp_player), 0.0, 60.0);\n                    if ((lib1_gv_cosmetic_portrait[lv_portrait_id].lv_standard_wins_required >= 2)) {\n                        libNtve_gf_SetDialogItemTooltip(lib1_gv_portrait_picker_image[lv_row][lv_column], (StringExternal(\"Param/Value/lib_1_F3EC044F\") + IntToText(lib1_gv_cosmetic_portrait[lv_portrait_id].lv_standard_wins_required) + StringExternal(\"Param/Value/lib_1_5D410C94\")), PlayerGroupSingle(lp_player));\n                    }\n                    else if ((lib1_gv_cosmetic_portrait[lv_portrait_id].lv_support_months_required == 1)) {\n                        libNtve_gf_SetDialogItemTooltip(lib1_gv_portrait_picker_image[lv_row][lv_column], (StringExternal(\"Param/Value/lib_1_B424C3A1\") + IntToText(lib1_gv_cosmetic_portrait[lv_portrait_id].lv_support_months_required) + StringExternal(\"Param/Value/lib_1_B6C9BFB0\")), PlayerGroupSingle(lp_player));\n                    }\n                    else if ((lib1_gv_cosmetic_portrait[lv_portrait_id].lv_support_months_required > 1)) {\n                        libNtve_gf_SetDialogItemTooltip(lib1_gv_portrait_picker_image[lv_row][lv_column], (StringExternal(\"Param/Value/lib_1_4F67F923\") + IntToText(lib1_gv_cosmetic_portrait[lv_portrait_id].lv_support_months_required) + StringExternal(\"Param/Value/lib_1_5267B154\")), PlayerGroupSingle(lp_player));\n                    }\n                    else if (true) {\n        libNtve_gf_SetDialogItemTooltip(lib1_gv_portrait_picker_image[lv_row][lv_column], (StringExternal(\"Param/Value/lib_1_666FEEC7\") + lib1_gf_GetNemesisDisplayName(lib1_gv_cosmetic_portrait[lv_portrait_id].lv_nemesis_unlock_id) + StringExternal(\"Param/Value/lib_1_45F7C38C\")), PlayerGroupSingle(lp_player));\n                    }\n                }\n                if ((lv_column == lib1_gv_pORTRAIT_PICKER_MAX_COLUMN)) {\n                    lv_row = (lv_row + 1);\n                    lv_column = 0;\n                }\n                else {\n                    lv_column = (lv_column + 1);\n                }\n            }\n            else {\n                lv_count_processed = (lv_count_processed + 1);\n            }\n        }\n\n    }\n}"
}

def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value.encode("utf-8") if isinstance(value, str) else value)
    return path


def digest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def png():
    image = Image.new("RGBA", (220, 152), (255, 0, 0, 255))
    image.paste((0, 180, 220, 110), (34, 0, 186, 152))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _news():
    counts = []
    mappings = []
    for category, (token, title, _) in k._CATEGORY.items():
        prefix = "if" if category == "global" else "else if"
        counts.append(f"    {prefix} ((lp_news_category == lib1_gv_nEWS_CATEGORY_{token})) {{\n        lv_page_count = 2;\n    }}")
        mappings.append(f'''    {prefix} ((lp_news_category == lib1_gv_nEWS_CATEGORY_{token})) {{
        if ((lv_page == 1)) {{
            lv_news_text = StringExternal("Param/Value/KSCG2News{title}20261014");
        }}
        else if ((lv_page == 2)) {{
            lv_news_text = StringExternal("Param/Value/Old{title}");
        }}
    }}''')
    return ('''void lib1_gf_SetMainMenuNewsPage (int lp_player, int lp_news_category, int lp_page) {
    int lv_page_count;
    int lv_page;
    text lv_news_text;
    if ((lp_player < 0) || (lp_player > lib1_gv_mAX_PLAYERS)) {
        return;
    }
''' + "\n".join(counts) + '''
    else {
        lv_page_count = 12;
    }
    lv_page = MinI(MaxI(lp_page, 1), lv_page_count);
''' + "\n".join(mappings) + '''
    lib1_gf_SetMainMenuNewsText(lp_player, lv_news_text);
    if ((lv_page <= 1)) {
        DialogControlSetEnabled(previous, PlayerGroupSingle(lp_player), false);
    }
    if ((lv_page >= lv_page_count)) {
        DialogControlSetVisible(next_image, PlayerGroupSingle(lp_player), false);
    }
}
''')


def _portraits(count, limit):
    save_ids = list(range(count))
    if count > 9:
        save_ids[7], save_ids[9] = save_ids[9], save_ids[7]
    entries = "\n".join(f'''    lv_display_id = (lv_display_id + 1);
    lib1_gf_DefineCosmeticPortrait(lv_display_id, {save_id}, "Assets\\\\Textures\\\\old_{save_id}.dds", -1, false, 0, 0);'''
                        for save_id in save_ids)
    return f'''const int lib1_gv_pORTRAIT_LIMIT = {limit};
const int lib1_gv_pORTRAIT_PICKER_MAX_ROW = 5;
const int lib1_gv_pORTRAIT_PICKER_MAX_COLUMN = 5;
const int lib1_gv_mAX_NEMESIS_ID = 9;
bool lib1_gt_InitializeCosmeticPortraits_Func (bool testConds, bool runActions) {{
    int lv_display_id;
    lv_display_id = -1;
    if (!runActions) {{
        return true;
    }}
{entries}
    return true;
}}
int lib1_gf_PortraitsPerPage () {{
    return ((lib1_gv_pORTRAIT_PICKER_MAX_COLUMN + 1) * (lib1_gv_pORTRAIT_PICKER_MAX_ROW + 1));
}}
int lib1_gf_PlayerPortraitRowCount (int lp_player) {{
    int lv_visible_portrait_count;
    int lv_portrait_id;
    lv_portrait_id = lib1_gv_pORTRAIT_LIMIT;
    if ((lib1_gf_PortraitVisible(lp_player, lv_portrait_id) == true)) {{
        lv_visible_portrait_count = (lv_visible_portrait_count + 1);
    }}
    return CeilingI((IntToFixed(lv_visible_portrait_count) / IntToFixed((lib1_gv_pORTRAIT_PICKER_MAX_COLUMN + 1))));
}}
int lib1_gf_MaxPortraitPage (int lp_player) {{
    int lv_page_count;
    lv_page_count = CeilingI((IntToFixed(lib1_gf_PlayerPortraitRowCount(lp_player)) / IntToFixed((lib1_gv_pORTRAIT_PICKER_MAX_ROW + 1))));
    return MaxI((lv_page_count - 1), 0);
}}
void lib1_gf_OpenPortraitPicker (int lp_player) {{
    lib1_gf_PortraitsPerPage();
    lib1_gf_MaxPortraitPage(lp_player);
    lib1_gf_PortraitVisible(lp_player, 0);
}}
'''


def fixture(root, portrait_count=2, portrait_limit=None):
    preview = ""
    for function in ("HoverStructureDamagingCard", "StopHoveringStructureDamagingCard"):
        preview += f'''void lib1_gf_{function} (string lp_removal_card_name, bool lp_card_is_selected) {{
    int lv_unspent_resources;
    int lp_max_targetable_structure_cost;
    if (((lp_removal_card_name == "Precision Airstrike") || ((lp_removal_card_name == "Triple Strike") && (lp_card_is_selected == true)))) {{
        lv_unspent_resources = (lib1_gf_MineralsRemaining(EventPlayer()) + lib1_gf_GasRemaining(EventPlayer()));
        lp_max_targetable_structure_cost = lv_unspent_resources;
    }}
    else if ((lp_removal_card_name == "Triple Strike") && (lp_card_is_selected == false)) {{
        lv_unspent_resources = (lib1_gf_MineralsRemaining(EventPlayer()) + lib1_gf_GasRemaining(EventPlayer()));
        lp_max_targetable_structure_cost = MaxI((lv_unspent_resources - 8), 0);
    }}
}}
'''
    script = '''const int lib1_gv_mAX_CARD_ID = 946;
const int lib1_gv_mAX_UNIT_TYPE_PER_CARD = 9;
bool lib1_gt_Cards_Func (bool testConds, bool runActions) {
    int lv_id;
    if (!runActions) {
        return true;
    }
    lv_id = -1;
    lv_id = (lv_id + 1);
    // ignored example lib1_gf_DefineCard(123, "comma, } fake");
    lib1_gf_DefineCard(lv_id, lib1_gv_cORE, lib1_gv_tERRAN, "Alpha", StringExternal("Card/Name/Alpha"), lib1_gv_aGGRESSIVE, "", lib1_gv_cOMMON, 4, 2, null, StringExternal("Card/Describe/Alpha"), "Assets\\\\Textures\\\\alpha.dds", SoundLink("A, B", 2));
    lib1_gf_DefineCardUnit(lv_id, "Marine", 12);
    lib1_gf_DefineCardUnit(lv_id, "Goliath", 4);
    lib1_gf_AddEffecttoCardDefinition(lv_id, lib1_gv_eF_DRAW, lib1_gt_Alpha);
    lv_id = (lv_id + 1);
    lib1_gf_DefineCard(lv_id, lib1_gv_cORE, lib1_gv_tERRAN, "Triple Strike", StringExternal("Card/Name/Triple_Strike"), lib1_gv_aCTION, "", lib1_gv_rARE, 5, 3, null, StringExternal("Card/Describe/Triple_Strike"), "image.dds", SoundLink("X", 0));
    lv_id = (lv_id + 1);
    lib1_gf_DefineCard(lv_id, lib1_gv_cORE, lib1_gv_tERRAN, "Beta", StringExternal("Card/Name/Beta"), lib1_gv_aGGRESSIVE, "", lib1_gv_cOMMON, 0, 0, null, StringExternal("Card/Describe/Beta"), "image.dds", SoundLink("X", 0));
    return true;
}
bool lib1_gt_Alpha_Func (bool testConds, bool runActions) {
    lib1_gf_DrawOne();
    return true;
}
void lib1_gt_Alpha_Init () {
    lib1_gt_Alpha = TriggerCreate("lib1_gt_Alpha_Func");
}
void lib1_gf_DrawOne () {
    NativeDraw();
}
void InitMap () {
    lib1_gt_Alpha_Init();
}
text lib1_gf_GetCardText (string lp_unit_text, string lp_base_text) {
    string lv_unparsed_text;
    if ((StringLength(lp_unit_text) >= 1) && (StringLength(lp_base_text) >= 1)) {
        lv_unparsed_text = (lp_unit_text + " " + lp_base_text);
    }
    else if ((StringLength(lp_unit_text) >= 1)) {
        lv_unparsed_text = lp_unit_text;
    }
    else if (true) {
        lv_unparsed_text = lp_base_text;
    }
    return StringToText(lv_unparsed_text);
}
string lib1_gf_GetCardString (string lp_unit_text, string lp_base_text) {
    string lv_unparsed_text;
    if ((StringLength(lp_unit_text) >= 1) && (StringLength(lp_base_text) >= 1)) {
        lv_unparsed_text = (lp_unit_text + " " + lp_base_text);
    }
    else if ((StringLength(lp_unit_text) >= 1)) {
        lv_unparsed_text = lp_unit_text;
    }
    else if (true) {
        lv_unparsed_text = lp_base_text;
    }
    return lv_unparsed_text;
}
string lib1_gf_GetUnitTextForCollectionCard (int lp_card_id) {
    string lv_text;
    lv_text = "派出 ";
    lv_text = (lv_text + "、");
    lv_text = (lv_text + IntToString(lv_unit_type_count[lv_unit_type_index]));
    lv_text = (lv_text + " ");
    lib1_gf_GetCardSpecificUnitDisplayName(lp_card_id, "Marine");
    lv_text = (lv_text + "。");
    return lv_text;
}
string lib1_gf_GetCardSpecificUnitDisplayName (int lp_card_id, string lp_unit_type) {
    return lib1_gf_GetUnitDisplayNameasString(lp_unit_type);
}
'''
    script = script + preview + _news() + _portraits(portrait_count, portrait_count - 1 if portrait_limit is None else portrait_limit)
    parsed = k._Script(script.encode("utf-8"))
    edits = []
    append = []
    for name, reference in _REFERENCE_FUNCTIONS.items():
        if name in parsed.functions:
            function = parsed.functions[name]
            edits.append((function.start, function.end, reference))
        else:
            append.append(reference)
    script = parsed.candidate(edits).decode("utf-8") + "\n" + "\n".join(append)
    put(root, k.SCRIPT, script.replace("\n", "\r\n"))
    rows = ["Card/Name/Alpha=甲", "Card/Describe/Alpha=12名陆战队员和4台歌莉娅。战吼：抽1张牌。", "Card/Name/Triple_Strike=三重击", "Card/Describe/Triple_Strike=保留原意。", "Card/Name/Beta=乙", "Card/Describe/Beta=", "Unit/Name/Marine=陆战队员", "Unit/Name/Goliath=歌莉娅"]
    for _, (_, title, _) in k._CATEGORY.items():
        rows += [f"Param/Value/KSCG2News{title}20261014=10.14 更新公告<n/>旧正文", f"Param/Value/Old{title}=历史页"]
    # Mixed line endings and no final newline deliberately exercise exact edits.
    put(root, k.TEXT, "\r\n".join(rows[:5]) + "\n" + "\n".join(rows[5:]))
    put(root, "Base.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="Marine"><Name value="Unit/Name/Marine"/></CUnit><CUnit id="Goliath"><Name value="Unit/Name/Goliath"/></CUnit></Catalog>')
    return root


def replace_script(root, old, new):
    path = root / k.SCRIPT
    data = path.read_bytes()
    assert old.encode("utf-8") in data
    path.write_bytes(data.replace(old.encode("utf-8"), new.encode("utf-8")))


def apply_fixture(root, candidate):
    # Test helper is intentionally outside the domain module.
    for name, data in candidate.items():
        assert data is not None
        put(root, name, data)


def test_exact_id_units_effect_chain_and_nested_commas(tmp_path):
    root = fixture(tmp_path)
    before = digest(root)
    report = k.inspect_keystone_card(root, name="Alpha")
    assert (report["card_id"], report["mineral"], report["gas"]) == (0, 4, 2)
    assert [(u["unit_id"], u["count"]) for u in report["units"]] == [("Marine", 12), ("Goliath", 4)]
    chain = report["effect_chain"]
    assert chain["roots"][0]["handler_binding_verified"] is True
    assert chain["roots"][0]["init_callers"][0]["function"] == "InitMap"
    assert chain["functions"][0]["calls"] == ["lib1_gf_DrawOne"]
    report["units"][0]["count"] = 999
    assert k.inspect_keystone_card(root, card_id=0)["units"][0]["count"] == 12
    assert digest(root) == before
    json.dumps(report, ensure_ascii=False)


def test_names_can_repeat_but_name_query_requires_unique(tmp_path):
    root = fixture(tmp_path)
    replace_script(root, '"Beta", StringExternal', '"Alpha", StringExternal')
    assert k.inspect_keystone_card(root, card_id=2)["name"] == "Alpha"
    with pytest.raises(SC2Error, match="精确匹配"):
        k.inspect_keystone_card(root, name="Alpha")


@pytest.mark.parametrize("old,new", [("lv_id = (lv_id + 1);", "lv_id += 1;"), ("lv_id = -1;", "lv_id = SomeFunction();"), ("lv_id = -1;", "lv_id = 946;")])
def test_unknown_id_or_overflow_refused(tmp_path, old, new):
    root = fixture(tmp_path)
    replace_script(root, old, new)
    with pytest.raises(SC2Error):
        k.inspect_keystone_card(root, card_id=0)


def test_cost_patch_is_exact_and_previews_stay_consistent(tmp_path):
    root = fixture(tmp_path)
    before = digest(root)
    raw = (root / k.SCRIPT).read_bytes()
    candidate = k.plan_keystone_card_cost(root, 1, 6, 2)
    expected = raw.replace(b'lib1_gv_rARE, 5, 3, null', b'lib1_gv_rARE, 6, 2, null')
    assert candidate[k.SCRIPT] == expected  # same total, previews need no byte change
    candidate = k.plan_keystone_card_cost(root, 1, 6, 3)
    assert candidate[k.SCRIPT] == raw.replace(b'lib1_gv_rARE, 5, 3, null', b'lib1_gv_rARE, 6, 3, null').replace(b'lv_unspent_resources - 8', b'lv_unspent_resources - 9')
    assert digest(root) == before
    apply_fixture(root, candidate)
    assert k.inspect_keystone_card(root, card_id=1)["mineral"] == 6
    assert k.plan_keystone_card_cost(root, 1, 6, 3) == {}


@pytest.mark.parametrize("old,new", [("lv_unspent_resources - 8", "lv_unspent_resources - 9"), ("MaxI((lv_unspent_resources - 8), 0)", "UnknownCost()")])
def test_unknown_or_stale_preview_refused(tmp_path, old, new):
    root = fixture(tmp_path)
    replace_script(root, old, new)
    before = digest(root)
    with pytest.raises(SC2Error):
        k.plan_keystone_card_cost(root, 1, 6, 3)
    assert digest(root) == before


def test_selected_preview_semantic_drift_refused(tmp_path):
    root = fixture(tmp_path)
    replace_script(root, "lp_max_targetable_structure_cost = lv_unspent_resources;", "lp_max_targetable_structure_cost = 99;")
    with pytest.raises(SC2Error):
        k.plan_keystone_card_cost(root, 1, 6, 3)


@pytest.mark.parametrize("value", [True, -1, 2_147_483_648, 3.5, "3"])
def test_invalid_costs_refused(tmp_path, value):
    root = fixture(tmp_path)
    with pytest.raises(SC2Error):
        k.plan_keystone_card_cost(root, 0, value, 0)


def test_composed_description_flags_duplication_without_writes(tmp_path):
    root = fixture(tmp_path)
    before = digest(root)
    report = k.audit_keystone_descriptions(root, [0])["cards"][0]
    assert report["automatic_unit_text"] == "派出 12 陆战队员、4 歌莉娅。"
    assert report["composed_text"].endswith("12名陆战队员和4台歌莉娅。战吼：抽1张牌。")
    assert [row["status"] for row in report["duplicates"]] == ["possible_duplicate", "possible_duplicate"]
    assert report["final_render_status"] == "not_observed"
    assert digest(root) == before
    text = (root / k.TEXT).read_bytes().replace("12名陆战队员和4台歌莉娅。".encode(), "派出 12 陆战队员、4 歌莉娅。".encode())
    put(root, k.TEXT, text)
    assert k.audit_keystone_descriptions(root, [0])["cards"][0]["duplicates"][0]["status"] == "exact_duplicate"


def test_missing_unit_name_and_unknown_composition_remain_partial(tmp_path):
    root = fixture(tmp_path)
    put(root, k.TEXT, (root / k.TEXT).read_bytes().replace("Unit/Name/Marine=陆战队员".encode(), b"Unused=Unused"))
    report = k.audit_keystone_descriptions(root, [0])["cards"][0]
    assert report["composition_status"] == "partial"
    assert "[Marine]" in report["automatic_unit_text"]
    replace_script(root, 'lv_text = "派出 ";', 'lv_text = "产生 ";')
    report = k.audit_keystone_descriptions(root, [0])["cards"][0]
    assert report["composition_status"] == "unknown"
    assert report["composed_text"] is None
    assert report["duplicates"] == []


def test_description_reads_bom_dependency_without_mutating_source(tmp_path):
    from sc2_mcp.source_context import prepare_source_context
    root = fixture(tmp_path / "map.SC2Map")
    put(root, k.TEXT, (root / k.TEXT).read_bytes().replace("Unit/Name/Marine=陆战队员".encode(), b"Unused=Unused"))
    put(root, "DocumentInfo", '<DocInfo><Dependencies><Value>file:Names.SC2Mod</Value></Dependencies></DocInfo>')
    dependency = tmp_path / "dependencies/Names.SC2Mod"
    put(dependency, "DocumentInfo", "<DocInfo/>")
    put(dependency, "Base.SC2Data/GameData/UnitData.xml", '<Catalog><CUnit id="Marine"><Name value="Unit/Name/Marine"/></CUnit></Catalog>')
    raw = b"\xef\xbb\xbf" + "Unit/Name/Marine=依赖陆战队员\r\n".encode("utf-8")
    put(dependency, k.TEXT, raw)
    context = prepare_source_context(root, [tmp_path / "dependencies"], tmp_path / "cache", locale="zhCN")
    before = digest(root)
    report = k.audit_keystone_descriptions(root, [0], source_context=context)
    name = report["cards"][0]["units"][0]["display_name"]
    assert name["value"] == "依赖陆战队员"
    assert Path(name["source"]) == dependency / k.TEXT
    assert report["source_context_id"] == context["source_context_id"]
    assert "依赖陆战队员" in report["cards"][0]["automatic_unit_text"]
    assert (dependency / k.TEXT).read_bytes() == raw and digest(root) == before
    with pytest.raises(SC2Error, match="依赖文本只读"):
        k._Strings(dependency, dependency=True).set("Unit/Name/Marine", "wrong")
    put(root, k.TEXT, b"\xef\xbb\xbf" + (root / k.TEXT).read_bytes())
    with pytest.raises(SC2Error) as exc:
        k.audit_keystone_descriptions(root, [0])
    assert exc.value.code == "keystone_encoding"


def test_complex_builder_and_paging_extra_logic_rejected(tmp_path):
    root = fixture(tmp_path)
    replace_script(root, 'return lv_text;', 'lv_text = "extra"; return lv_text;')
    assert k.audit_keystone_descriptions(root, [0])["composition_shape_recognized"] is False
    replace_script(root, "return MaxI((lv_page_count - 1), 0);", "lv_page_count = 5; return MaxI((lv_page_count - 1), 0);")
    with pytest.raises(SC2Error):
        k.plan_keystone_portrait(root, png())


def test_description_stops_at_zero_unit_slot(tmp_path):
    root = fixture(tmp_path)
    replace_script(root, 'lv_id, "Marine", 12', 'lv_id, "Marine", 0')
    report = k.audit_keystone_descriptions(root, [0])["cards"][0]
    assert report["automatic_unit_text"] == ""
    assert report["units"] == []
    assert report["composed_text"] == report["base_text"]


def test_news_new_date_head_insert_preserves_history_and_other_categories(tmp_path):
    root = fixture(tmp_path)
    before = digest(root)
    old = {category: k.inspect_keystone_news(root, category) for category in k._CATEGORY}
    raw = (root / k.SCRIPT).read_bytes()
    candidate = k.plan_keystone_news(root, "global", "2026-10-16", "逐字保留\n第二行")
    assert digest(root) == before
    assert b"\r\r\n" not in candidate[k.SCRIPT]
    assert candidate[k.TEXT].startswith((root / k.TEXT).read_bytes())
    apply_fixture(root, candidate)
    new = k.inspect_keystone_news(root)
    assert new["page_count"] == 3
    assert [p["key"] for p in new["pages"]][1:] == [p["key"] for p in old["global"]["pages"]]
    assert new["pages"][0]["text"] == "10.16 更新公告<n/>全局改动<n/>逐字保留<n/>第二行"
    for category in ("protoss", "terran", "zerg"):
        current = k.inspect_keystone_news(root, category)
        assert current["pages"] == old[category]["pages"]
        assert current["page_count"] == old[category]["page_count"]
    assert b"lv_page_count = 12;" in raw and b"lv_page_count = 12;" in candidate[k.SCRIPT]


def test_news_same_date_only_updates_exact_line_and_old_page(tmp_path):
    root = fixture(tmp_path)
    text = (root / k.TEXT).read_bytes()
    candidate = k.plan_keystone_news(root, "terran", "2026-10-14", "同日补充")
    assert set(candidate) == {k.TEXT}
    old = b"Param/Value/KSCG2NewsTerran20261014=" + "10.14 更新公告<n/>旧正文".encode()
    assert candidate[k.TEXT] == text.replace(old, old + "<n/>同日补充".encode())
    apply_fixture(root, k.plan_keystone_news(root, "terran", "2026-10-16", "新页"))
    later = k.plan_keystone_news(root, "terran", "2026-10-14", "同日补充")
    assert set(later) == {k.TEXT} and "新页".encode() in later[k.TEXT]
    apply_fixture(root, later)
    assert k.inspect_keystone_news(root, "terran")["page_count"] == 3


@pytest.mark.parametrize("category,date,body", [("tutorial", "2026-10-16", "x"), ("global", "2026-10-15x", "x"), ("global", "2026-10-13", "x"), ("global", "2026-10-16", ""), ("global", "2026-10-16", "a\x00b")])
def test_news_invalid_inputs_do_not_write(tmp_path, category, date, body):
    root = fixture(tmp_path)
    before = digest(root)
    with pytest.raises(SC2Error):
        k.plan_keystone_news(root, category, date, body)
    assert digest(root) == before


def test_news_duplicate_key_and_inconsistent_pages_refused(tmp_path):
    root = fixture(tmp_path)
    replace_script(root, "lv_page_count = 2;", "lv_page_count = 3;")
    with pytest.raises(SC2Error):
        k.plan_keystone_news(root, "global", "2026-10-16", "x")
    root = fixture(tmp_path)
    put(root, k.TEXT, (root / k.TEXT).read_bytes() + b"\nParam/Value/KSCG2NewsGlobal20261014=duplicate")
    with pytest.raises(SC2Error):
        k.plan_keystone_news(root, "global", "2026-10-14", "x")


def test_portrait_append_capacity_page_boundary_and_real_dds(tmp_path):
    root = fixture(tmp_path, portrait_count=36)
    before = digest(root)
    old = k.inspect_keystone_portraits(root)
    assert old["entries"][7]["save_id"] == 9
    assert old["all_registered_page_count"] == 1
    assert old["player_visible_page_count"] is None
    candidate = k.plan_keystone_portrait(root, png(), save_id=36, support_months_required=2)
    assert set(candidate) == {k.SCRIPT, "Assets/Textures/custom_portrait_36.dds"}
    dds = candidate["Assets/Textures/custom_portrait_36.dds"]
    assert dds[:4] == b"DDS " and dds[84:88] == b"DXT5" and len(dds) == 23232
    with Image.open(io.BytesIO(dds)) as image:
        image.load()
        assert image.size == (152, 152) and image.mode == "RGBA"
        red, green, blue, alpha = image.getpixel((0, 0))
        assert red < 20 and green > 160 and blue > 200 and 100 <= alpha <= 120
    assert digest(root) == before
    apply_fixture(root, candidate)
    report = k.inspect_keystone_portraits(root)
    assert report["limit"] == 36 and report["registered_count"] == 37
    assert report["all_registered_page_count"] == 2
    assert report["entries"][:-1] == old["entries"]
    assert report["entries"][-1]["save_id"] == 36
    assert report["entries"][-1]["support_months_required"] == 2


def test_portrait_spare_capacity_not_shrunk_and_unknown_paging_refused(tmp_path):
    root = fixture(tmp_path, portrait_limit=100)
    candidate = k.plan_keystone_portrait(root, png())
    assert b"lib1_gv_pORTRAIT_LIMIT = 100;" in candidate[k.SCRIPT]
    replace_script(root, "return MaxI((lv_page_count - 1), 0);", "return 0;")
    with pytest.raises(SC2Error):
        k.plan_keystone_portrait(root, png())


@pytest.mark.parametrize("kwargs", [{"save_id": 1}, {"save_id": 99}, {"save_id": True}, {"nemesis_unlock_id": 10}, {"nemesis_unlock_id": -2}, {"support_months_required": -1}, {"standard_wins_required": True}, {"backer_exclusive": "false"}])
def test_portrait_unlock_id_and_stable_id_guards(tmp_path, kwargs):
    root = fixture(tmp_path)
    with pytest.raises(SC2Error):
        k.plan_keystone_portrait(root, png(), **kwargs)


def test_portrait_invalid_image_collision_duplicate_ids(tmp_path):
    root = fixture(tmp_path)
    with pytest.raises(SC2Error):
        k.plan_keystone_portrait(root, b"not an image")
    put(root, "Assets/Textures/custom_portrait_2.dds", b"existing")
    with pytest.raises(SC2Error):
        k.plan_keystone_portrait(root, png())
    (root / "Assets/Textures/custom_portrait_2.dds").unlink()
    replace_script(root, 'lv_display_id, 1, "Assets', 'lv_display_id, 0, "Assets')
    with pytest.raises(SC2Error):
        k.inspect_keystone_portraits(root)


@pytest.mark.parametrize("prefix", [b"\xef\xbb\xbf", b"\x00"])
def test_encoding_guards(tmp_path, prefix):
    root = fixture(tmp_path)
    put(root, k.SCRIPT, prefix + (root / k.SCRIPT).read_bytes())
    with pytest.raises(SC2Error):
        k.inspect_keystone_card(root, card_id=0)


def test_lexical_error_refused(tmp_path):
    root = fixture(tmp_path)
    put(root, k.SCRIPT, (root / k.SCRIPT).read_bytes() + b"\n/* unclosed")
    with pytest.raises(SC2Error):
        k.plan_keystone_card_cost(root, 0, 1, 1)


def test_each_workflow_reads_big_script_once_and_content_parse_cache_refreshes(tmp_path, monkeypatch):
    root = fixture(tmp_path)
    k._cached_script.cache_clear()
    original = Path.read_bytes
    reads = []
    def recording(path):
        if path.name == k.SCRIPT:
            reads.append(path)
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", recording)
    assert k.inspect_keystone_card(root, card_id=0)["mineral"] == 4
    k.inspect_keystone_news(root)
    k.inspect_keystone_portraits(root)
    assert len(reads) == 3
    assert k._cached_script.cache_info().misses == 1
    assert k._cached_script.cache_info().hits == 2
    put(root, k.SCRIPT, original(root / k.SCRIPT).replace(b'lib1_gv_cOMMON, 4, 2', b'lib1_gv_cOMMON, 7, 2'))
    assert k.inspect_keystone_card(root, card_id=0)["mineral"] == 7
    assert len(reads) == 4
    assert k._cached_script.cache_info().misses == 2


@pytest.mark.skipif(not Path(r"<KEYSTONE_MAP_ROOT>\build\kscg2.SC2Map").is_dir(), reason="approved read-only real map unavailable")
def test_real_map_readonly_queries_and_in_memory_candidates():
    root = Path(r"<KEYSTONE_MAP_ROOT>\build\kscg2.SC2Map")
    paths = (k.SCRIPT, k.TEXT)
    before = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
    inventory = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    tarsonis = k.inspect_keystone_card(root, name="Tarsonis Battalion")
    triple = k.inspect_keystone_card(root, name="Triple Strike")
    assert tarsonis["card_id"] == 213 and [(u["unit_id"], u["count"]) for u in tarsonis["units"]] == [("Marine", 12), ("Goliath", 4)]
    assert triple["card_id"] == 676
    costs = k.plan_keystone_card_cost(root, triple["card_id"], triple["mineral"] + 1, triple["gas"])
    assert costs[k.SCRIPT].count(b"lv_unspent_resources - 9") == 2
    from datetime import date, timedelta
    current_news = k.inspect_keystone_news(root, "global")
    dated_keys = [page["key"][-8:] for page in current_news["pages"] if page["key"][-8:].isdigit()]
    latest = max(date(int(key[:4]), int(key[4:6]), int(key[6:])) for key in dated_keys)
    news = k.plan_keystone_news(root, "global", (latest + timedelta(days=1)).isoformat(), "只读测试候选，不提交。")
    assert k._news_structure(k._Script(news[k.SCRIPT]), "global")["count"] == current_news["page_count"] + 1
    descriptions = k.audit_keystone_descriptions(root, [tarsonis["card_id"]])
    assert descriptions["cards"][0]["base_text"] == "战吼：抽1张牌。将2张《叛乱》洗入你的牌库。"
    portraits = k.inspect_keystone_portraits(root)
    assert portraits["registered_count"] > 0 and portraits["per_page"] == 36
    imported = k.plan_keystone_portrait(root, png())
    assert f"Assets/Textures/custom_portrait_{portraits['next_save_id']}.dds" in imported
    after = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
    assert before == after
    assert inventory == sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
