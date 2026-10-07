---
name: galaxy-language-fundamentals
description: Core Galaxy language syntax, all primitive and engine handle types (including funcref/structref/arrayref), naming conventions, include/file structure, structs, arrays, control flow, and map initialization patterns. Use for any question about Galaxy syntax, type system, variable declarations, or the MapScript bootstrap chain. Also documents which files are auto-generated (MapScript.galaxy, LibHASH.galaxy) and must never be edited.
---

## Loading Boundary

- **This sub-skill owns:** Galaxy language syntax, primitive/handle types, naming conventions, include/file structure, structs, arrays, control flow, and the MapScript bootstrap chain
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-code-organization` (file layout/include order), `galaxy-math-strings-conversion` (math/string APIs), `galaxy-triggers-and-functions` (trigger/event declaration)

# Galaxy Scripting – Language Fundamentals

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

Galaxy is the scripting language used in StarCraft II map/mod development. It is a statically-typed, C-like language compiled by the SC2 editor.

## Key References

| Resource | URL |
|---|---|
| **SC2-IngameDevTools (PRIMARY codebase — use as #1 example)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| Native function reference | https://mapster.talv.space/galaxy/reference |
| GalaxyScript guide (when/how to use script vs GUI) | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/058_GalaxyScript/ |
| SC2Mapster Galaxy reference | https://sc2mapster.github.io/mkdocs/galaxy/ |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| GalaxyScript beginner guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/058_GalaxyScript/ |
| Multithreading guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/057_Multithreading_with_Action_Definitions/ |
| SSF codebase (secondary style reference) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| Alcyone Frontlines codebase (secondary reference) | https://github.com/KimPlaybit/Alcyone_Frontlines/tree/master/ProximaFrontlines.SC2Mod/scripts |
| NativeLib helper functions | `TriggerLibs/NativeLib.galaxy` (installed with SC2 editor and the sc2galaxy VS Code extension) |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Language Overview (wiki) | https://sc2mapster.wiki.gg/wiki/Language_Overview |
| Types reference (wiki) | https://sc2mapster.wiki.gg/wiki/Types |

---

---

## File Structure & Includes

Code is split across multiple `.galaxy` files using `include`. The entry point is `MapScript.galaxy`, which hands off to a `scripts/main.galaxy` coordinator:

> **⚠️ Auto-Generated Files — NEVER write code in these:**
> - `MapScript.galaxy` — rebuilt by the editor on every save.
> - `LibHASH.galaxy` (e.g. `Lib5A1C9904.galaxy`) — the editor-generated library wrapper for an `.SC2Mod`; it wraps calls into `scripts/` via `include`.
> - `LibHASH_h.galaxy` — the auto-generated library header.
>
> **All custom logic belongs in `scripts/` files.** The editor will overwrite the auto-generated files.

```galaxy
// MapScript.galaxy (editor-managed — do not add logic here)
include "TriggerLibs/NativeLib"
include "TriggerLibs/LibertyLib"
void InitLibs() { libNtve_InitLib(); libLbty_InitLib(); }
include "scripts/main"
void InitCustomScript() { main(); }
void InitMap() { InitLibs(); InitCustomScript(); }
```

```galaxy
// scripts/main.galaxy — coordinator, lists all includes and defines main()
include "scripts/Enums"
include "scripts/GlobalVariables"
include "scripts/Header"
include "scripts/Utilities"
// ... all other files ...
include "scripts/MapInit"

void main() {
    TriggerAddEventMapInit(TriggerCreate("MapInit_Main"));
}
```

- Paths in `include` are **relative to the map root**, no `.galaxy` extension.
- Order matters: a file can only use types/functions declared in earlier includes.
- `Header.galaxy` holds forward declarations so files can call functions defined later in the include chain.
- See `galaxy-code-organization` skill for the full file-splitting pattern.

### Campaign map pattern (WoL / HotS / LotV story missions)
Campaign maps include three engine libraries — NativeLib + LibertyLib + CampaignLib:
```galaxy
include "TriggerLibs/NativeLib"
include "TriggerLibs/LibertyLib"
include "TriggerLibs/CampaignLib"

void InitLibs() {
    libNtve_InitLib();
    libLbty_InitLib();
    libCamp_InitLib();
}
```
This gives access to `libNtve_*` (native helpers), `libLbty_*` (Liberty/WoL helpers), and `libCamp_*` (campaign-specific API: transmissions, objectives, story state, drop pods, etc.).

### Library mod pattern (alternate)
When working inside an `.SC2Mod` library, files use a split header/impl pattern with a hash prefix:
```galaxy
include "TriggerLibs/NativeLib"
include "LibXXXXXXXX_h"  // header: structs, globals, forward decls (replace XXXXXXXX with your mod's hash)
```

### Test map / simple map pattern (alternate)
Some small maps use a no-path include with just the library name:
```galaxy
include "LibHASH"   // no path, no extension — editor resolves from linked dependencies
```

---

## Naming Conventions

### ⭐ Handler-module pattern (SC2-IngameDevTools — #1 PRIMARY reference)

This is the **canonical naming convention** for this project. Every module is a self-contained `.galaxy` file with a clear public `ModuleName_Init()` entry point and all internal helpers marked `static`.

| Kind | Convention | Example |
|---|---|---|
| **Public module function** | `ModuleName_FunctionName` | `UnitHandler_Init`, `ItemList_FilterListRebuild`, `DevTools_ChatCommandCreate` |
| **Trigger handler function** | `ModuleNameEvent(bool a, bool b)` | `BehaviorContainerSendHandler`, `UnitListBoxFilterQuery` |
| **Library function** | `libPrefix_lowercasename` | `libGalExe_unit`, `libGalExe_strip`, `libGalExe_debug` |
| **Struct type** | `FeatureContainerStruct` (PascalCase + Struct suffix) | `ItemListContainerStruct`, `ListBoxFilterStruct`, `EffectContainerStruct` |
| **Struct typedef (structref)** | `StructNameRef` | `typedef structref<ItemListContainerStruct> ItemListContainerStructRef` |
| **Funcref typedef** | `CallbackNameRef` or `CallbackName` | `typedef funcref<ItemListSetActiveCallbackDef> ItemListSetActiveCallback` |
| **Global module state** | PascalCase instance name | `BehaviorContainer`, `LightingContainer`, `EffectContainer` |
| **File-local/private** | `static` keyword | `static string ItemList;`, `static ListBoxFilterStruct ListBoxFilter;` |
| **Path string constant** | `UPPER_SNAKE_CASE` with `static const string` | `CONTAINERDLG_PATH`, `ADDBTN_PATH`, `EDITBOX_PATH` |
| **Config/limit constant** | `UPPER_SNAKE_CASE` with `const int` | `ITEM_LIST_MAX`, `DEBUG_TYPE_INFO` |
| **DataTable key prefix** | `c_FeatureName` or bare string | `c_ChatCommandkey = "DevTools.ChatCommand."` |
| **Local variable** | short camelCase (no prefix) | `player`, `pg`, `val`, `i`, `entry`, `trigRan` |
| **Struct field** | camelCase (no prefix) | `panel`, `messageBox`, `addButton`, `ownerPlayerPulldown` |

#### Key structural rules from SC2-IngameDevTools:

- Every module file has exactly one public `void ModuleName_Init()` function — the only entry point.
- All internal helpers, state variables, and filter functions are `static`.
- Trigger functions registered by string: `TriggerCreate("BehaviorContainerSendHandler")` — the string **must match the function name exactly**.
- Trigger function signature: **always** `bool FunctionName(bool a, bool b)`.
- Header files (`_h.galaxy`) contain only **forward declarations** — no implementations.
- Debug/logging helpers use ultra-short global names: `print(string s)`, `console(string s)`, `err(string s)`.
- Module-private console wrappers: `static void ModuleName_console(string s)` wrapping `TriggerDebugOutput`.

#### Real examples from SC2-IngameDevTools:

```galaxy
// BehaviorHandler.galaxy — complete module pattern
include "Script/debug_h"
include "Script/ItemList"

static const string CONTAINERDLG_PATH = "UIContainer/ConsoleUIContainer/CatalogManager/BehaviorManager";

ItemListContainerStruct BehaviorContainer;   // global module state (PascalCase)
static string ItemList;                       // file-private
static ListBoxFilterStruct ListBoxFilter;     // file-private

// Trigger handler — bool(bool,bool) signature, registered by string name
bool BehaviorListBoxFilterQuery(bool a, bool b) {
    int player = EventPlayer();               // locals are plain camelCase
    playergroup pg = PlayerGroupSingle(player);
    string val = DialogControlGetPropertyAsString(
        ListBoxFilter.editbox, c_triggerControlPropertyEditText, player);
    ItemList_FilterListRebuild(ItemList, ListBoxFilter, val, pg);
    return true;
}

bool BehaviorContainerSendHandler(bool a, bool b) {
    bool trigRan = true;
    string val = DialogControlGetPropertyAsString(
        BehaviorContainer.messageBox, c_triggerControlPropertyEditText, EventPlayer());
    // ...
    return trigRan;
}

void BehaviorHandler_Init() {                 // the ONE public entry point
    playergroup pg = PlayerGroupAll();
    ItemList = "BehaviorList";
    ItemListContainer_InitStandard(BehaviorContainer, CONTAINERDLG_PATH,
        "BehaviorContainerSendHandler");
    ItemListInitFromCatalog(ItemList, c_gameCatalogBehavior, ItemListCatalogFilter);
    ItemList_FilterListInitStandard(ListBoxFilter, "BehaviorListBox",
        BehaviorListBoxSetActive, ItemListItemTextValue, CONTAINERDLG_PATH+"/NavList");
    ItemList_FilterListRebuild(ItemList, ListBoxFilter, "", pg);
}
```

```galaxy
// Struct declaration — FeatureNameStruct pattern
struct EffectContainerStruct {
    int panel;
    int messageBox;
    int addButton;
    int removeButton;
    int sourceButton;
    int targetButton;
    int sourceUnitFrame;
    int targetUnitFrame;
    unit source;
    unit target;
};
// Typedef for passing by reference:
typedef structref<EffectContainerStruct> EffectContainerStructRef;
```

```galaxy
// Funcref typedef pattern for callbacks
void ItemListSetActiveCallbackDef(ItemListStructRef itemList, int index, playergroup pg);
typedef funcref<ItemListSetActiveCallbackDef> ItemListSetActiveCallback;

int ItemListForEachCallBack(string element, int currentIndex, ItemListStructRef itemList);
typedef funcref<ItemListForEachCallBack> ItemListForEachCallBackRef;
```

```galaxy
// Library utility functions: libPrefix_lowercaseName
void libGalExe_debug(int player, string msg) { ... }
string libGalExe_strip(string message) { ... }
actor libGalExe_actor(int player, string param) { ... }
```

```galaxy
// debug.galaxy — ultra-short global debug helpers
void print(string s)   { TriggerDebugOutput(1, StringToText(s), true); }
void console(string s) { TriggerDebugOutput(1, StringToText(s), false); }
void err(string s)     { TriggerDebugOutput(1, StringToText(s), true); }

// Module-private console wrapper:
static void CatalogValueHandler_console(string s) {
    TriggerDebugOutput(DEBUG_TYPE_INFO, StringToText(s), false);
}
```

---

### Standalone map / SC2Map (secondary — SSF pattern)

| Kind | Convention | Example |
|---|---|---|
| Global variable | `gv_SystemName_Variable` | `gv_PlayerStats`, `gv_ActivePG` |
| Global const (game-wide config) | `gv_MaxX` | `gv_MaxAmountPlayers`, `gv_GameTimeMax` |
| Named constant / enum | `c_Category_Name` | `c_Part_Terran`, `c_BossFightState_Alive` |
| Function | `SystemName_Action` | `Player_AddExp`, `MapInit_ActivePlayers` |
| Static trigger param | `SystemName_Param_Name` | `Utility_DelayedTextTagDestroyer_ParamTextTag` |
| Local variable | no prefix (short name) | `tmpInt`, `hero`, `playerID` |
| Struct field | no prefix | `activeFlag`, `heroUnit`, `bankfile` |

### Library mod / SC2Mod (alternate — editor-generated)

| Kind | Prefix | Example |
|---|---|---|
| Global variable | `libHASH_gv_` | `libXXXXXXXX_gv_soldiers` |
| Global function | `libHASH_gf_` | `libXXXXXXXX_gf_IsZerg` |
| Trigger variable | `libHASH_gt_` | `libXXXXXXXX_gt_SpawnJungle` |
| Struct type | `libHASH_gs_` | `libXXXXXXXX_gs_Spawn` |
| Local parameter | `lp_` | `lp_startPosition1` |
| Local variable | `lv_` | `lv_raceName` |

---

## Primitive Types

```galaxy
int     lv_count = 0;          // integer
bool    lv_flag = true;        // boolean
string  lv_name = "";          // text string (ASCII)
text    lv_display;            // localized text (UI)
fixed   lv_amount = 3.5;       // fixed-point number (like float)
byte    lv_b;                  // 8-bit integer
char    lv_c;                  // single character
```

### All Engine Handle Types (complete list from the Galaxy language spec)

```galaxy
unit             lv_hero;       // reference to a unit on the map
unitgroup        lv_soldiers;   // a collection of units
unitfilter       lv_filter;     // unit filter bitfield
unitref          lv_ref;        // unit reference (for data)
playergroup      lv_team;       // a collection of player slots
trigger          lv_spawnTrig;  // a trigger object
bank             lv_bank;       // a saved bank file
point            lv_pos;        // a 2D map coordinate
region           lv_region;     // a map region
color            lv_col;        // RGBA color
actor            lv_actor;      // model/effect visual actor
actorscope       lv_scope;      // actor scope (groups related actors)
abilcmd          lv_cmd;        // ability command (ability + target)
order            lv_order;      // unit order
sound            lv_snd;        // a playing sound instance
soundlink        lv_link;       // link to a sound asset
timer            lv_timer;      // a countdown or repeating timer
camerainfo       lv_cam;        // camera info / snapshot
revealer         lv_rev;        // vision revealer
marker           lv_marker;     // path marker
doodad           lv_doodad;     // doodad reference
bitmask          lv_bits;       // bitmask
generichandle    lv_handle;     // generic engine handle
effecthistory    lv_hist;       // effect history handle
aifilter         lv_aiFilter;   // AI filter
transmissionsource lv_trans;    // transmission source
wave             lv_wave;       // AI wave
waveinfo         lv_waveInfo;   // AI wave info
wavetarget       lv_waveTarget; // AI wave target
datetime         lv_dt;         // timestamp
```

### Reference types (funcref / structref / arrayref)

These allow passing functions and structs by reference — used in SSF for boss ability callbacks and generic systems:

```galaxy
// funcref: store a pointer to a function matching a blueprint signature
bool blueprint_BossAbility(unitgroup ug, unit boss);
typedef funcref<blueprint_BossAbility> Blueprint_BossAbility;

Blueprint_BossAbility lv_fn = someConcreteFunction;
lv_fn(lv_group, lv_boss);   // call via funcref

// structref: pass a struct by reference (avoids copying)
void BossFight_Init(structref<BossFightData> data) {
    data.amountBosses = 3;
}

// arrayref: pass an array by reference
void FillArray(arrayref<int> arr, int size) {
    int i = 0;
    for (; i < size; i += 1) { arr[i] = 0; }
}
```

---

## Constants

```galaxy
// In a header file (replace libXXXXXXXX_ with your mod's auto-generated prefix):
const int libXXXXXXXX_gv_heroDialogWidth = 1200;
const int libXXXXXXXX_gv_buttonSizePickY = 50;

// Built-in engine constants use the c_ prefix:
c_timeGame          // time constant for Wait()
c_playerAny         // wildcard player slot
c_invalidDialogControlId
c_invalidDialogId
c_anchorTopLeft
c_stringAnywhere
c_stringNoCase
c_unitCountAll
c_gameOverVictory
c_gameOverDefeat
c_playerPropMinerals
c_playerPropVespene
c_playerPropOperSetTo
c_unitPropEnergy
c_unitPropCurrent
c_allianceIdSeekHelp
c_allianceIdChat
c_targetFilterMissile
c_targetFilterDead
c_targetFilterHidden
```

---

## Structs

Structs are declared in header files. Fields are accessed with `.`.

```galaxy
// Declaration (replace libXXXXXXXX_ with your mod's auto-generated prefix):
struct libXXXXXXXX_gs_Spawner {
    point  lv_point;
    string lv_unitType;
    int    lv_player;
};

struct libXXXXXXXX_gs_Spawn {
    point                          lv_point;
    libXXXXXXXX_gs_UnitsToSpawn[5] lv_unitSpawn;  // fixed-size array field
    int                            lv_respawnTime;
    int                            lv_spawnTime;
    trigger                        lv_deathCallbackTrigger;
};

// Usage:
libXXXXXXXX_gv_spawners[lv_index].lv_unitType = "Marine";
libXXXXXXXX_gv_createdSpawners[lv_index].lv_lastIndexPoint += 1;
```

Passing structs by reference uses `structref<T>`:

```galaxy
void libXXXXXXXX_gf_AddJungleSpawn (structref<libXXXXXXXX_gs_Spawn> lp_toSpawn) {
    libXXXXXXXX_gv_jungleToSpawn[libXXXXXXXX_gv_lastIndexOfSpawn].lv_point = lp_toSpawn.lv_point;
}
```

---

## Arrays

Fixed-size arrays are declared with `[size]`. 0-based indexing is typical.

```galaxy
// Declaration (in GlobalVariables.galaxy):
PlayerStruct[gv_MaxAmountPlayers + 1] gv_PlayerStats;   // indexed 1..gv_MaxAmountPlayers
int[gv_MaxAmountParts] gv_PartWins;                     // sized by const

// Multi-dimensional array (part x difficulty x playerCount):
int[gv_MaxAmountParts][gv_MaxAmountDifficulties][gv_MaxAmountPlayers] speedrunsTime;

// Initialization loop:
int tmpInt = 0;
for (; tmpInt < gv_MaxAmountPlayers; tmpInt += 1) {
    gv_ActivePG = PlayerGroupEmpty();
}
```

---

## Control Flow

```galaxy
// if / else if / else
if (gf_IsSurvival() == true) {
    // ...
}
else if (lv_raceCheck == true) {
    // ...
}
else {
    // ...
}

// for loop (Galaxy compiler pattern – uses auto variables):
const int auto4853DB8A_ai = 1;
int auto4853DB8A_ae = gv_spawnerLastIndex;
lv_index = 0;
for ( ; ( (auto4853DB8A_ai >= 0 && lv_index <= auto4853DB8A_ae)
         || (auto4853DB8A_ai < 0 && lv_index >= auto4853DB8A_ae) )
      ; lv_index += auto4853DB8A_ai ) {
    // body
}

// while (PlayerGroup iteration pattern):
lv_loopedPlayer = -1;
while (true) {
    lv_loopedPlayer = PlayerGroupNextPlayer(autoGroup, lv_loopedPlayer);
    if (lv_loopedPlayer < 0) { break; }
    // body
}

---

## Common Gotchas & Language Rules

These are the most common mistakes when writing Galaxy — sourced from the official SC2 editor guides and the SC2Mapster community:

| Rule | Detail |
|---|---|
| Variables declared at top | All local variables **must** be declared at the very top of a function — before any statements, conditions, or function calls. The compiler enforces this strictly. |
| No `++` / `--` operators | `var++` and `var--` are not valid syntax. Use `var += 1` and `var -= 1`. |
| No block comments | `/* */` block comments do not exist in Galaxy. Use only `//` line comments. |
| `static` = file-private | A `static` function is invisible outside its own `.galaxy` file. Use to avoid polluting the global namespace. |
| Line length limit | Lines must not exceed 2048 characters (compiler hard limit). |
| Cross-file calls without include | Once two files are both included into `MapScript.galaxy`, either file can call functions defined in the other — you do **not** need a local `include` at the top of the calling file. All included files share one global compilation unit. |
| `for` loop with null body | Galaxy `for` loops can have an empty body; the iteration step still runs. This is sometimes used for skip patterns. |
| `fixed` is 20-bit | `fixed` is a **fixed-point** type (not IEEE float). Precision is ~0.0001 and max value is ~524287. Use `fixed` everywhere SC2 uses "Real". |
| No dynamic memory | Galaxy has no `new`/`delete` or heap allocation. All storage is static globals, locals on the stack, or engine-managed handles (`unit`, `region`, `timer`, …). |
| Function name in `TriggerCreate` | `TriggerCreate` takes the **string name** of the function — not a funcref. The function signature must be `bool (bool, bool)`. Example: `TriggerCreate("MyHandler_Func")`. |

// switch-style (auto val):
int auto4221B408_val = lv_race;
if (auto4221B408_val == 1) { PlayerSetRace(lp_player, "Terr"); }
else if (auto4221B408_val == 2) { PlayerSetRace(lp_player, "Zerg"); }
else if (auto4221B408_val == 3) { PlayerSetRace(lp_player, "Prot"); }
```

---

## String Operations

```galaxy
StringContains(haystack, needle, c_stringAnywhere, c_stringNoCase)  // → bool
StringEqual(a, b, c_stringNoCase)                                   // → bool
IntToString(lv_count)                                               // → string
FixedToText(lv_fixed, c_fixedPrecisionAny)                          // → text
TextToString(lv_text)                                               // → string
StringExternal("Param/Value/lib_5A1C9904_KeyName")                  // → text (localized)
```

Concatenation uses `+`:

```galaxy
string lv_key = lp_key + IntToString(lv_index);
text lv_msg = lv__KilledTextBuilder + StringExternal("Param/Value/lib_5A1C9904_956C1A6F") + lv__KillerTextBuilder;
```

---

## Color

```galaxy
color lv_allyColor  = Color(28*100/255, 167*100/255, 234*100/255);
color lv_enemyColor = Color(100.00, 0.00, 0.00);
color lv_transparent = ColorWithAlpha(0, 0, 0, 0);
color lv_playerColor = libNtve_gf_ConvertPlayerColorToColor(PlayerGetColorIndex(lp_player, false));
```

---

## Map Initialization Pattern (SSF)

The bootstrap chain: `MapScript.galaxy` → `main()` → map-init trigger → init functions:

```galaxy
// scripts/main.galaxy
void main() {
    TriggerAddEventMapInit(TriggerCreate("MapInit_Main"));
}

// scripts/MapInit.galaxy
bool MapInit_Main(bool testCond, bool runActions) {
    MapInit_ActivePlayers();   // alliances, playergroups
    SSFCustomUI_Init();        // UI
    PartTerran_TriggerCreate(); // register part triggers
    // ... other init calls
    return true;
}
```

### Library mod init pattern (alternate)

Libraries use an idempotent `InitLib` function:
```galaxy
bool libXXXXXXXX_InitLib_completed = false;
void libXXXXXXXX_InitLib() {
    if (libXXXXXXXX_InitLib_completed) { return; }
    libXXXXXXXX_InitLib_completed = true;
    libXXXXXXXX_InitVariables();
    libXXXXXXXX_InitTriggers();
}
```
