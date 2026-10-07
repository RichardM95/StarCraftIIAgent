---
name: galaxy-debug-data-catalog
description: Debug output, Data Table key-value storage, Catalog runtime field access, UserData, and asset preloading in Galaxy script. Use when reading or writing catalog fields at runtime, storing cross-trigger state in the Data Table, printing debug output, or preloading models and sounds. Do not use for bank save/load (use galaxy-game-systems).
---

## Loading Boundary

- **This sub-skill owns:** debug output, Data Table key-value storage, Catalog runtime field access, UserData, and asset preloading
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-game-systems` (bank save/load), `galaxy-triggers-and-functions` (cross-trigger state via triggers), `sc2data-units-abilities` (XML catalog authoring)

# Galaxy Scripting – Debug, Data Table & Catalog

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| Trigger Debugger guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/053_Trigger_Debugger/ |
| Optimizing Code guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/056_Optimizing_Code/ |
| Data Tables guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/041_Data_Tables/ |
| Custom Values guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/050_Custom_Values/ |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| NativeLib catalog helpers | `TriggerLibs/NativeLib.galaxy` — `libNtve_gf_CatalogFieldValueGetAsReal`, `libNtve_gf_CatalogReferenceGetAsReal`, `libNtve_gf_CatalogFieldValueSetAsReal`, `libNtve_gf_CatalogReferenceModifyBasedOnDefaultValue` |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Debug Output

```galaxy
// Print to the in-game debug window (F7 to open in test mode)
TriggerDebugOutput(c_triggerDebugOutputCode, StringToText("my value: " + IntToString(lv_n)), true);

// Enable/disable debug output globally
TriggerDebugOutputEnable(c_triggerDebugOutputCode, true);

// Open or close the debug window for a player
TriggerDebugWindowOpen(lv_player, true);

// Convenience debug functions (Template / unclassified)
DebugString(lv_player, "lv_unit type: " + UnitGetType(lv_unit));
DebugInt(lv_player, "lv_i", lv_i);
DebugFixed(lv_player, "lv_dist", lv_dist);
DebugUnit(lv_player, lv_unit);
DebugPoint(lv_player, lv_point);

// Debug message type constants
c_triggerDebugOutputCode      // code path output
c_triggerDebugOutputError     // error highlighting
c_triggerDebugOutputMessage   // general message
```

---

## Data Table (Global Key-Value Store)

The Data Table stores arbitrary values by `string` name, accessible from any trigger. It survives the scope of individual functions.

### ⭐ SC2-IngameDevTools DataTable patterns (PRIMARY — use these)

The SC2-IngameDevTools codebase uses the DataTable extensively as a backing store for its `ItemList` abstraction, chat command parameters, per-player state, and catalog lookups. Key patterns:

```galaxy
// Namespaced keys prevent collisions — use "Module.Feature.Key" format
DataTableSetInt(true, "DataTableListPage."+IntToString(player), page);
int page = DataTableGetInt(true, "DataTableListPage."+IntToString(player));

// Store catalog type integer by catalog name string
DataTableSetInt(true, "Catalog.Unit",    c_gameCatalogUnit);
DataTableSetInt(true, "Catalog.Ability", c_gameCatalogAbil);
// Retrieve: int catalog = DataTableGetInt(true, "Catalog."+catalogName);

// Per-player listbox selection state (DataTable as a UI state cache)
string key = listId+".Selected["+IntToString(player)+"]:"+IntToString(listItem);
DataTableSetString(true, key, ItemListGetVal(itemList, index));
if (DataTableValueExists(true, key)) {
    string val = DataTableGetString(true, key);
}
DataTableValueRemove(true, key);

// Trigger event param passing via DataTable (scoped to trigger execution context)
string paramKey = TriggerEventParamName("DevTools_ChatCommand.Exec."+cmd, "_player");
DataTableSetInt(false, paramKey, player);
int p = DataTableGetInt(false, TriggerEventParamName(EventGenericName(), "_player"));

// ItemList backing store (the full ItemList implementation in ItemList/index.galaxy)
// ItemList is a string key; all data goes into the DataTable with structured keys:
// "ItemList::[listId][index]"      → the value stored at that slot
// "ItemList::[listId].Count"       → current item count
// "ItemList[listId].Active.Player1" → current selection per player
```

### Global (map-wide) data table

```galaxy
// Save values — always pass true for the global (map-wide) scope
DataTableSetInt(true, "myKey", 42);
DataTableSetFixed(true, "position_x", 16.5);
DataTableSetBool(true, "isPhase2", true);
DataTableSetUnit(true, "heroUnit", lv_hero);
DataTableSetString(true, "lastEvent", "SpawnWave");
DataTableSetPoint(true, "spawnPt", lv_point);

// Load values
int    lv_n   = DataTableGetInt(true, "myKey");
fixed  lv_x   = DataTableGetFixed(true, "position_x");
bool   lv_b   = DataTableGetBool(true, "isPhase2");
unit   lv_u   = DataTableGetUnit(true, "heroUnit");
string lv_s   = DataTableGetString(true, "lastEvent");
point  lv_p   = DataTableGetPoint(true, "spawnPt");

// Check existence
bool lv_has = DataTableValueExists(c_dataTableScopeGlobal, "myKey");

// Remove
DataTableValueRemove(c_dataTableScopeGlobal, "myKey");

// Scope constants
c_dataTableScopeGlobal   // map-wide
c_dataTableScopeLocal    // trigger-local
```

### Instance Data Tables

Instance tables let you create multiple independent tables (like a dictionary per unit):

```galaxy
DataTableInstanceCreate();
int lv_dt = DataTableInstanceLastCreated();

DataTableInstanceSetInt(lv_dt, "kills", 0);
DataTableInstanceSetUnit(lv_dt, "owner", lv_unit);

int  lv_k = DataTableInstanceGetInt(lv_dt, "kills");
unit lv_o = DataTableInstanceGetUnit(lv_dt, "owner");

DataTableInstanceClear(lv_dt);
```

---

## Catalog (Runtime Data Field Access)

The Catalog lets you read and modify game data fields at runtime — damage, range, cost, etc. — from within triggers.

### Reading catalog values

```galaxy
// Get the string value of a data field
string lv_val = CatalogFieldValueGet(
    c_gameCatalogUnit,           // which catalog
    "Marine",                    // entry name
    "LifeMax",                   // field name
    lv_player                    // player context
);

// Get as integer or fixed
int   lv_int  = CatalogFieldValueGetAsInt(c_gameCatalogUnit, "Marine", "LifeMax", lv_player);
fixed lv_real = libNtve_gf_CatalogFieldValueGetAsReal(c_gameCatalogWeapon, "C-14Rifle", "Range", lv_player);

// Catalog constants
c_gameCatalogUnit
c_gameCatalogWeapon
c_gameCatalogAbil
c_gameCatalogEffect
c_gameCatalogBehavior
c_gameCatalogUpgrade
c_gameCatalogModel
c_gameCatalogSound
c_gameCatalogActor
```

### Writing catalog values

```galaxy
// Set a field for a player (overrides for that player)
bool lv_ok = CatalogFieldValueSet(
    c_gameCatalogWeapon, "C-14Rifle", "Range",
    lv_player, "8"               // value as string
);

// Modify relative to current value
CatalogFieldValueModify(
    c_gameCatalogUnit, "Marine", "LifeMax",
    lv_player, c_upgradeOperAdd, "25"    // add 25 HP
);

// Set as real
libNtve_gf_CatalogFieldValueSetAsReal(
    c_gameCatalogWeapon, "C-14Rifle", "Range",
    lv_player, 9.0
);
```

### Array fields

```galaxy
// Field array element — for fields like Weapons[0].Range
int lv_count = CatalogFieldValueCount(c_gameCatalogUnit, "Marine", "Weapons", lv_player);
string lv_wpn = CatalogFieldValueGet(c_gameCatalogUnit, "Marine", "Weapons[0]", lv_player);
```

### Catalog references

```galaxy
// Read a link reference (e.g., which weapon a unit uses)
string lv_ref = CatalogReferenceGet(c_gameCatalogUnit, "Marine", "Weapons[0]", lv_player);

// get as int
int lv_ri = CatalogReferenceGetAsInt(c_gameCatalogUnit, "Marine", "Weapons[0]", lv_player);
```

---

## User Data

User data allows embedding custom typed values directly in game data entries (configured in the editor's data module).

```galaxy
// Load a user data value by category and field
string lv_val = UserDataGetString("MyCategory", lv_entryName, "MyField", 0, lv_player);
int    lv_i   = UserDataGetInt("MyCategory", lv_entryName, "MyField", 0, lv_player);
fixed  lv_f   = UserDataGetFixed("MyCategory", lv_entryName, "MyField", 0, lv_player);
text   lv_t   = UserDataGetText("MyCategory", lv_entryName, "MyField", 0, lv_player);
color  lv_c   = UserDataGetColor("MyCategory", lv_entryName, "MyField", 0, lv_player);
```

---

## Preloading Assets

Preload before they're needed to avoid hitches:

```galaxy
PreloadAsset("Assets\\Textures\\MyHero.dds");
PreloadModel("Assets\\Units\\Hero\\Hero.m3");
PreloadImage("Assets\\UI\\HeroPortrait.dds");
PreloadLayout("Assets\\UI\\MyDialog.SC2Layout");

// Preload model animations — native function (NOT a libNtve helper):
ModelAnimationLoad("Assets\\Units\\Hero\\Hero.m3",  "Assets\\Units\\Hero\\Hero_Attack.m3a");
ModelAnimationLoadOverriding("Assets\\Units\\Hero\\Hero.m3", "Assets\\Override\\Hero_Walk.m3a");
ModelAnimationUnload("Assets\\Units\\Hero\\Hero.m3", "Assets\\Units\\Hero\\Hero_Attack.m3a");
// (modelPath, animPath) — animPath is the .m3a animation file
```

---

## Trigger Debugger

The Trigger Debugger is the primary runtime analysis tool for Galaxy scripts.

> **Full documentation:** [Trigger Debugger guide](https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/053_Trigger_Debugger/)

### Launching

| Method | How |
|---|---|
| In-game cheat | Type `trigdebug` in chat during a map test |
| Editor setting | File → Preferences → Test Document → Show Trigger Debugging Window |
| Galaxy code | `TriggerDebugWindowOpen(lv_player, true);` |
| Galaxy breakpoint | Add the keyword `Breakpoint;` in Galaxy code — debugger opens and jumps to that line when executed |

> The game must be in **Windowed** mode for the debug window to appear.

### Recommended initial config

Right-click the bottom subview → uncheck all "Show" options **except** `Show Errors` and `Show User Output`. This dramatically reduces performance overhead from the debugger.

### Key tabs

| Tab | Best used for |
|---|---|
| **Variables** | Browse all global variables and their current values at runtime. Sort by `Total Memory Size` to find memory hogs. Complex types (arrays, structs) show "Double Click to Expand". |
| **Triggers** | List of all triggers, with fire count, fail count, run count, average/total run time. Sort by `Total Time` to find background lag; sort by `Average Run Time` to find latency spikes. |
| **Threads** | All active `Wait`-based threads. Shows which `Wait` type (Real vs Game) each thread is currently blocked on. Right-click → View Script to jump to the function. |
| **Queue** | Triggers currently using `TriggerQueueEnter()`/`TriggerQueueExit()`. |
| **Trigger Profiling** | Detailed profiling of threaded triggers. Shows **Self-Only Time** (pure Galaxy ops, excluding sub-function call time) vs **Self+Children Time** (total including sub-calls). Enable `Show Natives` and `Show SubCalls` for full call-stack detail. |
| **Function Profiling** | Per-function call stats, run count, average/worst/total run time. |
| **Activity** | Visual graph of fired events (green), checked conditions (yellow), executed triggers (red) vs time. Useful for spotting latency spikes. |
| **Script Code** | Full source view with breakpoint support, locals inspection, callstack, and Watch list. |

### Setting breakpoints in Script Code tab

1. Right-click in the Script Code tab → **Add/Remove Breakpoint** on the desired line.
2. When execution hits the breakpoint, the game pauses and the debugger gains focus.
3. Use the dropdown menus in the subviews to switch between **Globals**, **Locals**, **Watch**, **Callstack**, or **Breakpoints** views.
4. The **Locals** view is the most useful — it shows every local variable and event parameter in the currently paused function.

### Profiling workflow (from Optimizing Code guide)

1. Run the map with the debugger open.
2. In **Triggers Tab**, sort by `Total Time` — this reveals which trigger causes the most cumulative lag.
3. In **Trigger Profiling Tab**, enable `Show Natives` and `Show SubCalls` — this exposes exactly which native functions inside the trigger are the hottest.
4. Optimize the inner-loop first: even a small improvement in a hot inner loop compounds multiplicatively.

> **Note:** Unit Custom Values are **not** tracked in the Variables Tab. If you use custom values for debugging, build your own debug UI.

---

## Data Table: Performance & Scope Guidelines

(Expanded from the [Data Tables guide](https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/041_Data_Tables/))

### Search time comparison

| Structure | Search Time | Notes |
|---|---|---|
| Array | Linear O(n) | Making it 10× bigger increases search time 10×. |
| Data Table | Constant O(1) | Search time does not grow with table size. |

Use arrays for small, typed, well-defined collections. Use Data Tables when the collection is large, dynamic, or mixed-type.

### Scope rules

| Scope | Created by | Lifetime | Access |
|---|---|---|---|
| Global (`c_dataTableScopeGlobal`) | Always exists | Entire game session | Accessible from any trigger |
| Local (`c_dataTableScopeLocal`) | First `DataTableSet*` call inside a trigger | Cleared when the trigger exits | Only the current trigger |

**Memory leak risk:** The Global data table is permanent. Entries added but never removed will accumulate. Always call `DataTableValueRemove(c_dataTableScopeGlobal, "key")` or `DataTableClear(c_dataTableScopeGlobal)` when data is no longer needed. Local tables are cleaned up automatically when their trigger finishes.
