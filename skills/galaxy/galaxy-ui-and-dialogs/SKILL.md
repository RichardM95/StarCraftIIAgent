---
name: galaxy-ui-and-dialogs
description: Dialog and dialog control creation, XML frame hookup, hero/upgrade selection panels, scoreboard panels, dialog events, HUD messages, localized text, minimap pings, and the SSF hooked-frame UI pattern in Galaxy script. Use when building or updating any in-game UI such as dialogs, buttons, labels, images, portraits, click handlers, or player-visible messages. Do not use for actor-based visuals (use galaxy-actor-and-visuals).
---

## Loading Boundary

- **This sub-skill owns:** dialog/dialog control creation, XML frame hookup, hero/upgrade panels, scoreboard panels, dialog events, HUD messages, localized text, minimap pings, and the SSF hooked-frame UI pattern
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-actor-and-visuals` (actor visuals), `galaxy-triggers-and-functions` (dialog events via triggers), `galaxy-players-and-alliances` (player-specific UI), `sc2data-actors-visuals` (SC2Layout XML)

# Galaxy Scripting – UI & Dialogs

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| Alcyone Frontlines codebase | https://github.com/KimPlaybit/Alcyone_Frontlines/tree/master/ProximaFrontlines.SC2Mod/scripts |
| NativeLib dialog helpers | `TriggerLibs/NativeLib.galaxy` — all `libNtve_gf_CreateDialogItem*`, `libNtve_gf_SetDialogItem*` functions |
| Dialogs guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/043_Dialogs/ |
| Dialog Panels guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/044_Dialog_Panels/ |
| UI Events guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/049_UI_Events/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Dialogs

Dialogs are overlay panels created either programmatically or hooked up to existing UI frames defined in layout XML.

### Hooking up an existing XML frame (SSF pattern — preferred)

SSF binds to frames already defined in the SC2 UI XML layout:

```galaxy
// Hook a panel frame by path from the root UI hierarchy
dialogcontrol gv_UI_MasterFrame = DialogControlHookupStandard(
    c_triggerControlTypePanel,
    "UIContainer/FullscreenUpperContainer/SSF_CustomUI"
);

// Hook a specific child control (button, label, etc.) within a parent frame
dialogcontrol saveBtn = DialogControlHookup(
    gv_UI_MasterFrame,
    c_triggerControlTypeButton,
    "Menu/SaveButton"
);

// Register click event on the hooked control
TriggerAddEventDialogControl(
    TriggerCreate("Bank_ManualSave"),
    c_playerAny,
    saveBtn,
    c_triggerControlEventTypeClick
);
```

The init pattern in `UI-Main.galaxy`:
```galaxy
void SSFCustomUI_Init() {
    gv_UI_MasterFrame = DialogControlHookupStandard(c_triggerControlTypePanel, "UIContainer/FullscreenUpperContainer/SSF_CustomUI");
    StatsInterface_Init();   // each UI subsystem hooks its own controls
    HeroPanel_Init();
    PlayerBoard_Init();
    // ...
}
```

### Creating a dialog programmatically (alternate)

```galaxy
dialog lv_dlg = DialogCreate(
    1200,              // width  (pixels)
    600,               // height (pixels)
    c_anchorCenter,    // anchor position on screen
    0,                 // x offset from anchor
    0,                 // y offset from anchor
    false              // modal (blocks input to game underneath)
);
// Or capture:
gv_heroDialog = DialogLastCreated();
```

### Showing / hiding

```galaxy
DialogSetVisible(lv_dlg, PlayerGroupAll(), true);   // show to all
DialogSetVisible(lv_dlg, PlayerGroupSingle(3), false); // hide for player 3
```

### Anchor constants

```galaxy
c_anchorTopLeft
c_anchorTop
c_anchorTopRight
c_anchorLeft
c_anchorCenter
c_anchorRight
c_anchorBottomLeft
c_anchorBottom
c_anchorBottomRight
```

---

## Dialog Controls

### ⭐ SC2-IngameDevTools `DialogControlHookup` pattern (PRIMARY — use for existing XML frames)

The SC2-IngameDevTools codebase hooks into **pre-existing XML UI frames** rather than creating dialog controls in code. This is the preferred pattern when UI frames are defined in `Base.SC2Data/UI/Layout/`:

```galaxy
// Hookup an existing XML panel by its frame path (no creation needed)
// The path is relative to the UI layout root
static const string CONTAINERDLG_PATH =
    "UIContainer/ConsoleUIContainer/CatalogManager/BehaviorManager";
static const string EDITBOX_PATH    = "Item";
static const string ADDBTN_PATH     = "AddButton";
static const string REMOVEBTN_PATH  = "RemoveButton";

struct BehaviorContainerStruct {
    int panel;       // the hooked panel (int = dialog control handle)
    int messageBox;
    int addButton;
    int removeButton;
};
BehaviorContainerStruct BehaviorContainer;

void BehaviorHandler_Init() {
    trigger t;
    // Hook the root panel by absolute path
    BehaviorContainer.panel =
        DialogControlHookupStandard(c_triggerControlTypePanel, CONTAINERDLG_PATH);

    // Hook child controls relative to the panel
    BehaviorContainer.messageBox =
        DialogControlHookup(BehaviorContainer.panel, c_triggerControlTypeEditBox, EDITBOX_PATH);
    BehaviorContainer.addButton =
        DialogControlHookup(BehaviorContainer.panel, c_triggerControlTypeButton, ADDBTN_PATH);
    BehaviorContainer.removeButton =
        DialogControlHookup(BehaviorContainer.panel, c_triggerControlTypeButton, REMOVEBTN_PATH);

    // Register click handler — trigger registered by STRING function name
    t = TriggerCreate("BehaviorContainerSendHandler");
    TriggerAddEventDialogControl(t, c_playerAny, BehaviorContainer.addButton,
        c_triggerControlEventTypeClick);
    TriggerAddEventDialogControl(t, c_playerAny, BehaviorContainer.removeButton,
        c_triggerControlEventTypeClick);
}
```

Key functions used:
| Function | Purpose |
|---|---|
| `DialogControlHookupStandard(type, path)` | Hook a root-level frame by absolute XML path |
| `DialogControlHookup(parent, type, childPath)` | Hook a child control relative to a parent panel |
| `DialogControlGetPropertyAsString(ctrl, prop, player)` | Read text/string property |
| `DialogControlSetPropertyAsString(ctrl, prop, pg, val)` | Set text/string property |
| `DialogControlGetPropertyAsInt(ctrl, prop, player)` | Read int property (e.g. selection index) |
| `DialogControlGetSelectedItem(list, player)` | Get selected listbox item index |
| `DialogControlAddItem(list, pg, text)` | Add item to a listbox/pulldown |
| `DialogControlRemoveAllItems(list, pg)` | Clear all listbox items |
| `DialogControlGetItemCount(list, player)` | Count items in a listbox |

### Button

```galaxy
libNtve_gf_CreateDialogItemButton(
    lv_dlg,          // parent dialog
    200, 50,         // width, height
    c_anchorTopLeft, // anchor within dialog
    10, 10,          // x, y offset from anchor
    StringToText(""),         // tooltip
    StringToText("Click Me"), // label
    ""               // style (empty = default)
);
dialogcontrol lv_btn = DialogControlLastCreated();
```

### Label

```galaxy
libNtve_gf_CreateDialogItemLabel(
    lv_dlg,
    300, 40,
    c_anchorTopLeft,
    10, 60,
    StringToText("Score: 0"),  // initial text
    ColorWithAlpha(255, 255, 255, 255), // white
    false,           // word wrap
    0                // wrap width (0 = no limit)
);
dialogcontrol lv_label = DialogControlLastCreated();
```

### Image

```galaxy
libNtve_gf_CreateDialogItemImage(
    lv_dlg,
    100, 100,
    c_anchorTopLeft,
    10, 110,
    StringToText(""),   // tooltip
    "Assets\\Textures\\UI_Protoss_Something.dds",
    c_triggeredImageTypeNormal,
    false,   // tiled
    ColorWithAlpha(255, 255, 255, 255)
);
dialogcontrol lv_img = DialogControlLastCreated();
```

### Portrait / unit image

```galaxy
libNtve_gf_CreateDialogItemPortrait(
    lv_dlg, 150, 150, c_anchorTopLeft, 10, 10,
    StringToText(""), -1,
    null, // unit (null for no unit)
    true  // use unit model
);
```

---

## Updating Controls

```galaxy
// Change text
libNtve_gf_SetDialogItemText(lv_label, StringToText("Score: 42"), PlayerGroupAll());

// Change image
libNtve_gf_SetDialogItemImage(lv_img, "Assets\\Textures\\NewImage.dds", PlayerGroupAll());

// Enable / disable
DialogControlSetEnabled(lv_btn, PlayerGroupAll(), true);
DialogControlSetEnabled(lv_btn, PlayerGroupSingle(lv_player), false);

// Guard against an uninitialized control (c_invalidDialogControlId == 0)
if (lv_label != c_invalidDialogControlId) {
    libNtve_gf_SetDialogItemText(lv_label, StringToText("..."), PlayerGroupAll());
}
```

---

## Dialog Events

### Register click handler on ALL controls in a dialog

```galaxy
TriggerAddEventDialogControl(
    myTrigger,
    c_playerAny,
    c_invalidDialogControlId,        // 0 = any control in dialog
    c_triggerControlEventTypeClick
);
```

### Register click handler on a specific button

```galaxy
TriggerAddEventDialogControl(
    myTrigger,
    c_playerAny,
    lv_btn,
    c_triggerControlEventTypeClick
);
```

### Reading the event inside the handler

```galaxy
bool MyClickHandler(bool testCond, bool runActions) {
    dialogcontrol clicked = EventDialogControl();
    int player = EventPlayer();

    if (clicked == gv_LockInButton) {
        HeroSelection_SelectHero(player, gv_SelectedHero[player]);
    }
    return true;
}
```

---

## Hero Selection Dialog Pattern (SSF)

SSF uses hooked XML frames for hero selection. Each panel is a separate file under `scripts/UI/`. The `HeroSelection.galaxy` file drives the logic while `UI-HeroPanel.galaxy` owns the dialog controls:

```galaxy
// UI-HeroPanel.galaxy
static dialogcontrol HeroPanel_MainFrame;
static dialogcontrol[gv_MaxAmountHeroes + 1] HeroPanel_HeroButtons;

void HeroPanel_Init() {
    HeroPanel_MainFrame = DialogControlHookup(gv_UI_MasterFrame, c_triggerControlTypePanel, "HeroPanel");
    int i = 1;
    for (; i <= gv_MaxAmountHeroes; i += 1) {
        HeroPanel_HeroButtons[i] = DialogControlHookup(HeroPanel_MainFrame, c_triggerControlTypeButton, "Hero" + IntToString(i));
    }
    TriggerAddEventDialogControl(TriggerCreate("HeroPanel_Click"), c_playerAny, c_invalidDialogControlId, c_triggerControlEventTypeClick);
}

void HeroPanel_UpdatePlayer(int playerID) {
    // Show/hide based on unlock state
    int i = 1;
    for (; i <= gv_MaxAmountHeroes; i += 1) {
        bool unlocked = ((gv_PlayerStats[playerID].heroUnlocked & (1 << i)) != 0);
        DialogControlSetEnabled(HeroPanel_HeroButtons[i], PlayerGroupSingle(playerID), unlocked);
    }
}
```

### Level-up upgrade panel

```galaxy
bool HeroLevelUp_Handler(bool testCond, bool runActions) {
    unit hero = EventUnit();
    int level = UnitXPGetCurrentLevel(hero);
    int player = UnitGetOwner(hero);
    // Show appropriate upgrade panel for this level
    if (level == 2) {
        DialogControlSetVisible(gv_UpgradeFrame_Level2, PlayerGroupSingle(player), true);
    }
    return true;
}
```

---

## Messages & Feedback

### Display message in HUD area

```galaxy
UIDisplayMessage(PlayerGroupAll(), c_messageAreaChat,     StringToText("GG!"));
UIDisplayMessage(PlayerGroupAll(), c_messageAreaSubtitle, StringToText("Round 1 – Fight!"));
UIDisplayMessage(
    PlayerGroupSingle(lv_player),
    c_messageAreaChat,
    StringToText("Not enough minerals!")
);

// Area constants
c_messageAreaChat         // bottom-left chat area
c_messageAreaSubtitle     // center subtitle
c_messageAreaDefault
c_messageAreaObjective
c_messageAreaWarning
```

### Error message with sound

```galaxy
libNtve_gf_UIErrorMessage(
    PlayerGroupSingle(lv_player),
    StringToText("Cannot afford this upgrade!"),
    SoundLink("UI_GenericError", -1)
);
```

---

## Localized Text

```galaxy
// Read from GameStrings.txt / Trig/ namespace
text lv_msg = StringExternal("Trig/Bosskilled");

// With variable replacements (SSF pattern)
text lv_result = Utility_TextExpressionReplacement3(
    "Trig/Bosskilled",
    IntToText(gv_Part_AmountObjectivesDefeated),
    IntToText(gv_Part_AmountObjectivesMax),
    IntToText(gv_Difficulty_Points)
);

// Colorize player name
color playerColor = libNtve_gf_ConvertPlayerColorToColor(PlayerGetColorIndex(playerID, false));
text colored = TextWithColor(StringToText(PlayerName(playerID)), playerColor);

// Combine text
text lv_msg2 = StringToText("+") + FixedToText(amount, 2);
```

---

## UI Alerts & Minimap

```galaxy
// Toggle built-in alert types
UISetAlertTypeVisible(PlayerGroupAll(), "AlertWorkerAttacked", false);

// Minimap ping
PingCreate(PlayerGroupAll(), lv_point, 10.0, ColorWithAlpha(255, 0, 0, 255), "");
```

---

## Scoreboard / Stats Panel (SSF pattern)

SSF uses hooked XML frames for the player board, updated by calling `PlayerBoard_UpdatePlayer(playerID)`:

```galaxy
// UI-PlayerBoard.galaxy
static dialogcontrol PlayerBoard_MainFrame;
static dialogcontrol[gv_MaxAmountPlayers + 1] PlayerBoard_KillsLabel;
static dialogcontrol[gv_MaxAmountPlayers + 1] PlayerBoard_ScoreLabel;

void PlayerBoard_Init() {
    PlayerBoard_MainFrame = DialogControlHookup(gv_UI_MasterFrame, c_triggerControlTypePanel, "PlayerBoard");
    int i = 1;
    for (; i <= gv_MaxAmountPlayers; i += 1) {
        PlayerBoard_KillsLabel[i] = DialogControlHookup(PlayerBoard_MainFrame, c_triggerControlTypeLabel, "Player" + IntToString(i) + "/Kills");
    }
}

void PlayerBoard_UpdatePlayer(int playerID) {
    libNtve_gf_SetDialogItemText(
        PlayerBoard_KillsLabel[playerID],
        IntToText(gv_PlayerStats[playerID].kills),
        PlayerGroupAll()
    );
}
```

### UI mode control

```galaxy
// Switch player(s) to fullscreen UI (hides default game HUD)
UISetMode(PlayerGroupAll(), c_uiModeFullscreen, c_transitionDurationImmediate);

// Hide specific HUD frames
UISetFrameVisible(PlayerGroupAll(), c_syncFrameTypeSupply,        false);  // hide supply display
UISetFrameVisible(PlayerGroupAll(), c_syncFrameTypeResourcePanel, false);  // hide minerals/gas panel

// Hide alert types
UISetAlertTypeVisible(PlayerGroupAll(), "AlertWorkerAttacked", false);
```

---

## Help Panel (Campaign)

```galaxy
// Hide the tech tree button inside the help panel
HelpPanelEnableTechTreeButton(PlayerGroupAll(), false);

// Navigate to a specific help panel page
HelpPanelDisplayPage(PlayerGroupAll(), c_helpPanelPageTutorials);

// Register a unit type on the help panel's unit tab
libCamp_gf_AddUnitTypeToUnitHelpPanel("Marine", false, lv_player);

// Create a campaign tutorial entry (shows in the help panel)
libCamp_gf_CreateCampaignTutorial(
    StringToText("Tutorial Title"),
    StringToText("Explanation body text here."),
    "Assets\\Textures\\btn-unit-terr-marine.dds",   // icon path
    ""   // video path (or empty)
);
```

---

## UI Alerts & Objective Pings

```galaxy
// Beacon / alert for a map point (flashes minimap + compass)
UIAlertPoint("TriggerName", PlayerGroupSingle(lv_player), StringExternal("Param/Alert/..."), null, lv_point);

// Beacon / alert centered on a specific unit
UIAlertUnit("TriggerName", lv_player, StringExternal("Param/Alert/..."), null, lv_unit);

// Minimap ping with facing angle (used for objectives)
libNtve_gf_CreatePingFacingAngle(
    PlayerGroupAll(),
    "PingObjective",                   // ping type from data
    lv_point,
    ColorWithAlpha(0, 100, 0, 0),      // RGBA color (0-255 or 0-1 depending on version)
    0.0,                               // duration (0 = permanent until destroyed)
    270.0                              // facing angle
);
ping lv_ping = PingLastCreated();
PingSetScale(lv_ping, 0.75);
PingSetTooltip(lv_ping, StringToText("Objective location"));
```

---

## Dialog Layout & Resolution

> **Source:** [Dialogs guide — Dialog Formatting](https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/043_Dialogs/)

### Internal resolution system

Dialogs are sized in an **internal pixel space** — they look the same regardless of the player's monitor resolution. The SC2 client maps this internal space to the player's screen:

| Screen ratio | Internal resolution (width × height) |
|---|---|
| 4:3 | 1600 × 1200 |
| 16:9 | 2133 × 1200 |
| 16:10 | 1920 × 1200 |

Height is always **1200 internal pixels**. Width scales by ratio.

**Practical rule:** Keep dialogs no wider than **1600 px** (the narrowest 4:3 width) to ensure they never clip or overflow on any screen ratio. Design at 1600 px wide and you're safe for all players.

```galaxy
// Safe full-screen-width dialog (works on all ratios)
dialog gv_mainDialog = DialogCreate(
    1600,           // safe max width
    1200,           // full height
    c_anchorCenter,
    0, 0,
    false
);

// For UI elements, anchor to edges rather than absolute coords
// so they stay on-screen across all ratios:
// c_anchorTopLeft, c_anchorTopRight, c_anchorBottomLeft, c_anchorBottomRight, c_anchorCenter
```

### DialogControlCreateFromTemplate

Wrapper pattern that avoids the GUI editor crash when creating items from a template string:

```galaxy
// Use this helper instead of the GUI "Create Dialog Item From Template" action
int CreateDialogItemFromTemplate(int dialog, int type, string template) {
    return DialogControlCreateFromTemplate(dialog, type, template);
}
```
