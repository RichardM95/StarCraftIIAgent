---
name: galaxy-units-and-groups
description: Unit creation, properties, behaviors, abilities, XP/leveling, unit groups, orders, death/kill events, custom values, and cargo in Galaxy script. Use when creating units, modifying HP/shields/energy, adding behaviors, issuing orders, querying or iterating unit groups, handling level-up events, or listening for unit death. Do not use for the AI that controls units (use galaxy-ai-and-techtree).
---

## Loading Boundary

- **This sub-skill owns:** unit creation, properties, behaviors, abilities, XP/leveling, unit groups, orders, death/kill events, custom values, and cargo
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-ai-and-techtree` (AI that controls units), `galaxy-actor-and-visuals` (visual attachments), `galaxy-triggers-and-functions` (unit events via triggers)

# Galaxy Scripting – Units & Unit Groups

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
| NativeLib | `TriggerLibs/NativeLib.galaxy` (sc2galaxy VS Code extension) |
| Custom Values guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/050_Custom_Values/ |
| Unit Selection Events guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/048_Unit_Selection_Events/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| **SC2 Unit Type IDs** | See skill `sc2data-units-reference` for the full list of all multiplayer unit type ID strings (e.g. `"SiegeTank"`, `"HighTemplar"`, `"BroodLord"`), transform/morph ID pairs, race, attributes, and expansion — use when calling `UnitCreate`, `UnitGetType`, or checking unit attributes. |

---

## Creating Units

```galaxy
// Basic create
UnitCreate(1, "Marine", c_unitCreateIgnorePlacement, 1, lv_point, 270.0);
unit lv_marine = UnitLastCreated();

// Via library helpers (common variants)
libNtve_gf_CreateUnitsAtPoint2(1, "Marine", 1, lv_point);
libNtve_gf_UnitCreateFacingPoint(1, "Marine", 0, 1, lv_point, lv_facingPoint);

// UnitCreate flags
c_unitCreateIgnorePlacement    // ignore placement rules (most common)
c_unitCreateUsePreferences     // use placement preferences
```

---

## Testing Units

```galaxy
bool lv_alive   = UnitIsAlive(lv_unit);
bool lv_valid   = UnitIsValid(lv_unit);
bool lv_dead    = !UnitIsAlive(lv_unit);
bool lv_type    = (UnitGetType(lv_unit) == "Marine");
int  lv_owner   = UnitGetOwner(lv_unit);
```

---

## Destroying / Removing Units

```galaxy
UnitKill(lv_unit);          // kill instantly (no kill-credit/XP awarded to any attacker)
UnitRemove(lv_unit);        // remove instantly with no death animation or events
UnitPauseAll(bool);         // pause or unpause ALL units on the map simultaneously
```

---

## Unit Position & Facing

```galaxy
point lv_pos = UnitGetPosition(lv_unit);
UnitSetPosition(lv_unit, lv_newPos, false);          // false = no smooth move
UnitSetFacing(lv_unit, 90.0, 0.0);                   // angle in degrees, duration 0
fixed lv_facing = UnitGetFacing(lv_unit);
```

---

## Unit Properties

```galaxy
// Reading
fixed lv_life    = UnitGetPropertyFixed(lv_unit, c_unitPropLife, true);       // true = current
fixed lv_maxLife = UnitGetPropertyFixed(lv_unit, c_unitPropLife, false);      // false = max
fixed lv_energy  = UnitGetPropertyFixed(lv_unit, c_unitPropEnergy, true);
fixed lv_shield  = UnitGetPropertyFixed(lv_unit, c_unitPropShields, true);

// Writing
UnitSetPropertyFixed(lv_unit, c_unitPropLife,     75.0);
UnitSetPropertyFixed(lv_unit, c_unitPropShields, 100.0);

// Property constants
c_unitPropLife           // current HP
c_unitPropLifeMax        // max HP
c_unitPropLifePercent    // HP as percent 0-100
c_unitPropShields        // current shields
c_unitPropShieldsMax     // max shields
c_unitPropEnergy         // current energy
c_unitPropEnergyMax      // max energy
c_unitPropEnergyPercent  // energy as percent 0-100 (writable)
c_unitPropKills          // kill count
c_unitPropMoveSpeed      // movement speed
c_unitPropArmorLevel     // armor rating
c_unitPropCurrent        // attack damage (general current)

---

## Custom Unit Values (Data Slots)

Each unit has 4 custom fixed-point data slots (indices 0–3) for storing arbitrary values:

```galaxy
// Store a float in slot 0 (e.g. spawn time, special flag, current state)
UnitSetCustomValue(lv_unit, 0, 2.5);

// Retrieve the stored value
fixed lv_val = UnitGetCustomValue(lv_unit, 0);

// Slots 0-3 are independent; default value is 0.0
```

---

## Cargo

```galaxy
// Count units currently loaded in a transport
int lv_count = UnitCargoValue(lv_transport, c_unitCargoUnitCount);
```
```

---

## Scale, Appearance

```galaxy
UnitSetScale(lv_unit, 1.5, 1.5, 1.5);      // x, y, z scale multipliers
```

---

## Behaviors

Behaviors are the primary mechanism for applying upgrades, buffs, and debuffs:

```galaxy
// Add a behavior (with stack count)
UnitBehaviorAdd(lv_unit, "PowerOverwhelming", lv_unit, 1);
UnitBehaviorAdd(lv_unit, "ArmorPlatesAura",   lv_unit, 1);

// Remove a behavior
UnitBehaviorRemove(lv_unit, "PowerOverwhelming", 1);

// Set behavior count
UnitBehaviorSetCount(lv_unit, "ShieldBoost", lv_unit, 2);

// Query
int  lv_count   = UnitBehaviorCount(lv_unit, "PowerOverwhelming");
bool lv_hasBhvr = UnitHasBehavior(lv_unit, "PowerOverwhelming");
```

---

## Abilities

```galaxy
// Reset cooldown of an ability
UnitAbilityReset(lv_unit, "Ability_Name", true);

// Check if unit can use ability
bool lv_can = UnitAbilityEnabled(lv_unit, "Ability_Name");

// Set ability enabled
UnitAbilityEnable(lv_unit, "Ability_Name", true);

// Order a unit to use ability at a point
UnitOrder(lv_unit, OrderTargetingPoint(AbilityCommand("Ability_Name", 0), lv_point));
```

---

## XP / Level System

```galaxy
// Add XP
UnitXPAddXP(lv_unit, 200.0);

// Query XP
fixed lv_xp    = UnitXPGetCurrentXP(lv_unit);
int   lv_level = UnitXPGetCurrentLevel(lv_unit);
int   lv_level2 = UnitLevel(lv_unit);   // same result, shorter

// Event: listen for level-up
TriggerAddEventUnitGainLevel(myTrigger, null);   // null = any unit
// Inside handler:
unit lv_leveledUnit = EventUnit();
int  lv_newLevel    = UnitXPGetCurrentLevel(lv_leveledUnit);
```

---

## Unit Groups

### Creating a unit group

```galaxy
// Empty group
unitgroup lv_group = UnitGroupEmpty();

// Filtered group from the game world
unitgroup lv_enemies = UnitGroup(
    null,                       // null = any unit type (or "Marine" for specific)
    1,                          // player
    RegionEntire(),             // region to search in
    UnitFilter(0, 0, (1 << c_targetFilterDead), 0),   // exclude dead
    0                           // max units, 0 = unlimited
);
```

### UnitFilter

```galaxy
// UnitFilter(requiresMask, excludeMask, requiresType, excludeType)
UnitFilter(0, 0, 0, 0)                              // no filter
UnitFilter(0, 0, (1 << c_targetFilterDead), 0)      // exclude dead
UnitFilter((1 << c_targetFilterEnemy), 0, 0, 0)     // require enemy

// Common filter constants
c_targetFilterDead
c_targetFilterAlly
c_targetFilterEnemy
c_targetFilterSelf
c_targetFilterGround
c_targetFilterAir
c_targetFilterStructure
c_targetFilterWorker
c_targetFilterHero
```

### Modifying a group

```galaxy
UnitGroupAdd(lv_group, lv_unit);
UnitGroupRemove(lv_group, lv_unit);
UnitGroupAddUnitGroup(lv_group, lv_otherGroup);
UnitGroupClear(lv_group);
```

### Querying a group

```galaxy
int  lv_count  = UnitGroupCount(lv_group, c_unitCountAll);
bool lv_has    = UnitGroupHasUnit(lv_group, lv_unit);
unit lv_first  = UnitGroupUnit(lv_group, 1);        // 1-based index
unit lv_random = UnitGroupRandomUnit(lv_group, c_unitCountAll);
unit lv_close  = UnitGroupClosestToPoint(lv_group, lv_point);
bool lv_dead   = libNtve_gf_UnitGroupIsDead(lv_group);
point lv_center = UnitGroupCenterOfGroup(lv_group);

// Filter by player
unitgroup lv_filtered = UnitGroupFilterPlayer(lv_group, 2, 0);

// Filter by unit type from an existing group (version = 0)
unitgroup lv_marines = UnitGroupFilter("Marine", lv_player, lv_sourceGroup, UnitFilter(0,0,0,0), 0);

// Get all units created by the last batch UnitCreate call (e.g. after creating 5 at once)
unitgroup lv_batch = UnitLastCreatedGroup();

// Convert single unit to group
unitgroup lv_single = libNtve_gf_ConvertUnitToUnitGroup(lv_unit);

// Unit count constants
c_unitCountAll
c_unitCountAlive
c_unitCountDead
```

### Iterating a unit group (from-end pattern)

The editor generates iteration from the end to safely handle removal during loops:

```galaxy
int lv_u = UnitGroupCount(lv_group, c_unitCountAll);
unit lv_cur;
for (; lv_u > 0 ; lv_u -= 1) {
    lv_cur = UnitGroupUnitFromEnd(lv_group, lv_u);
    if (lv_cur == null) { continue; }
    // act on lv_cur ...
}
```

---

## Unit Orders

```galaxy
// Move to point
UnitOrder(lv_unit, OrderTargetingPoint(AbilityCommand("Move", 0), lv_point));

// Attack-move to point
UnitOrder(lv_unit, OrderTargetingPoint(AbilityCommand("Attack", 0), lv_point));

// Stop
UnitOrder(lv_unit, Order(AbilityCommand("Stop", 0)));

// Hold position
UnitOrder(lv_unit, Order(AbilityCommand("HoldPosition", 0)));

// Queue orders
UnitOrderAdd(lv_unit, OrderTargetingPoint(AbilityCommand("Move", 0), lv_pt2), false);

// Queued group orders
UnitGroupOrder(lv_group, OrderTargetingPoint(AbilityCommand("Move", 0), lv_point), false);
```

---

## Unit Utility Functions

```galaxy
// Find nearest unit
unit lv_near = UnitNearestUnit(lv_point, lv_group);

// Default facing from one position to another
fixed lv_angle = AngleBetweenPoints(lv_from, lv_to);

// Give unit to a different player
UnitSetOwner(lv_unit, lv_newPlayer, true);   // true = change color

// Unit state flags
UnitSetState(lv_unit, c_unitStateInvulnerable,  true);
UnitSetState(lv_unit, c_unitStateHidden,        true);
UnitSetState(lv_unit, c_unitStateSelectable,    false);  // prevent selection by players
UnitSetState(lv_unit, c_unitStateStatusBar,     false);  // hide HP bar
UnitSetState(lv_unit, c_unitStateTooltipable,   true);   // allow tooltip on hover

// Common state constants
c_unitStateInvulnerable
c_unitStateHidden
c_unitStatePaused
c_unitStateIsHallucination
c_unitStateSelectable
c_unitStateStatusBar
c_unitStateTooltipable

// libNtve helper wrappers (shortcuts for common state combos)
libNtve_gf_MakeUnitInvulnerable(lv_unit, true);    // sets invulnerable
libNtve_gf_MakeUnitUncommandable(lv_unit, true);   // prevents player from commanding the unit
libNtve_gf_ShowHideUnit(lv_unit, false);           // hide (sets hidden + removes from selection)

// Change unit skin / variation (e.g. aged model, damaged state)
libNtve_gf_UnitSetVariation(lv_unit, "Marine", 1, "Battle");
// (unit, typeName, variationIndex, variationTag)

// Selection control
UnitFlashSelection(lv_unit, 2.0);      // flash selection ring for duration (seconds)
UnitSelect(lv_unit, lv_player, true);  // add to player's current selection
UnitClearSelection(lv_player);         // deselect all units for player
libNtve_gf_StoreUnitSelection(lv_player, libNtve_ge_UnitSelectionStoreOption_ClearUnitSelection);
libNtve_gf_RestoreUnitSelection(lv_player);  // restore previously stored selection
```
