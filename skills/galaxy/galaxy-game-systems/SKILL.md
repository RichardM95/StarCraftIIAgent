---
name: galaxy-game-systems
description: Bank save/load, spawner and wave systems, jungle/camp respawn, resource rewards, hero revive/death, tech tree upgrades, and game attribute lobby options in Galaxy script. Use when implementing persistent data storage, enemy wave spawners, neutral camp respawn timers, kill resource rewards, or player revive logic. Do not use for AI wave behavior (use galaxy-ai-and-techtree) or UI (use galaxy-ui-and-dialogs).
---

## Loading Boundary

- **This sub-skill owns:** bank save/load, spawner and wave systems, jungle/camp respawn, resource rewards, hero revive/death, tech tree upgrades, and game attribute lobby options
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-ai-and-techtree` (AI wave behavior), `galaxy-ui-and-dialogs` (UI), `galaxy-debug-data-catalog` (Data Table cross-trigger state), `galaxy-players-and-alliances` (player resources)

# Galaxy Scripting – Game Systems

## Prerequisite

Load [`sc2-galaxy-scripting`](../../sc2-galaxy-scripting/SKILL.md) first for project-wide Galaxy syntax constraints (variable hoisting, no `++`/`--`, `while` not `for`, include paths without extensions), source-of-truth rules, modular script boundaries, and naming conventions (e.g. `libMy_` function prefix, `libMy_g_` global prefix). This sub-skill owns deep API reference only; project conventions live in the router skill.

## Key References

| Resource | URL |
|---|---|
| Native function reference | https://mapster.talv.space/galaxy/reference |
| Galaxy syntax definition | https://github.com/Talv/vscode-sc2-galaxy/blob/master/syntaxes/galaxy.json |
| Banks guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/051_Banks/ |
| Custom Values guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/050_Custom_Values/ |
| **SC2-IngameDevTools (PRIMARY — #1 codebase)** | https://github.com/abrahamYG/SC2-IngameDevTools/tree/main/DevToolsIngame.SC2Mod/Script |
| SSF codebase (secondary style) | https://github.com/Cristall/SC2-SwarmSpecialForces/tree/main/SwarmSpecialForces.SC2Map/scripts |
| Alcyone Frontlines codebase | https://github.com/KimPlaybit/Alcyone_Frontlines/tree/master/ProximaFrontlines.SC2Mod/scripts |
| NativeLib | `TriggerLibs/NativeLib.galaxy` (sc2galaxy VS Code extension) |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Bank System (Save / Load Player Data)

Banks persist data between sessions per player. One bank = one named file tied to one player slot.

```galaxy
// Open (create if missing) — use your map/mod name as the bank name
BankLoad("MyMapName", lv_player);
bank lv_bank = BankLastCreated();

// Wait for async load to complete (needed if called at game start)
BankWait(lv_bank);

// Check section/key existence
bool lv_has = BankKeyExists(lv_bank, "Stats", "TotalKills");

// Read values
int   lv_kills   = BankValueGetAsInt(lv_bank, "Stats", "TotalKills");
bool  lv_flag    = BankValueGetAsFlag(lv_bank, "Flags", "CompletedTutorial");
fixed lv_score   = BankValueGetAsFixed(lv_bank, "Stats", "BestScore");
text  lv_name    = BankValueGetAsText(lv_bank, "Profile", "Name");

// Write values
BankValueSetFromInt(lv_bank, "Stats", "TotalKills", lv_kills + 1);
BankValueSetFromFlag(lv_bank, "Flags", "CompletedTutorial", true);
BankValueSetFromFixed(lv_bank, "Stats", "BestScore", 9999.0);

// Save to disk
BankSave(lv_bank);

// Remove section
BankSectionRemove(lv_bank, "OldData");

// Remove a key
BankKeyRemove(lv_bank, "Stats", "OldKey");

// Enable signature/encryption (prevents tampering by the player)
// Call this immediately after BankLoad, before BankWait
BankSetOptionSignature(lv_bank, true);
```

> **Bank file location on disk (Windows):**
> `Documents\StarCraft II\StarCraftPlayer.ID@#\Banks\[MapAuthorID]\[BankName].SC2Bank`
>
> Signature-enabled banks are checksummed by the engine. Manually editing a signed bank file will invalidate it on next load, causing the engine to treat it as empty/corrupt.
>
> **Full reference:** [Banks guide](https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/051_Banks/)

### Bank structure (hierarchy)

```
Bank file
 └─ Section  (e.g. "Stats", "Flags", "Profile")
     └─ Key  (e.g. "TotalKills", "BestScore")
         └─ Value  (typed: Int, Fixed, Bool, String, Text, Point, Unit)
```

---

## UserData System (Catalog-Driven Rewards)

UserData tables are defined in the Galaxy Data editor and read at runtime. Use them to keep design values (rewards, config) out of hardcoded script:

```galaxy
// Read from a UserData table by type identifier and field name
fixed baseExp     = UserDataGetFixed("KillRewards", unitType, "Exp", 1);
fixed baseBiomass = UserDataGetFixed("KillRewards", unitType, "Biomass", 1);
int enemyType     = UserDataGetInt("KillRewards", unitType, "EnemyType", 1);
int teamSizeMax   = UserDataGetInt("AcvReqSpeedruns", "P0D1", "TeamSizeMaxForSmall", 1);
```

The 4th parameter is the instance index (1-based). UserData tables are defined in the Galaxy Data editor.

---

## Spawner / Wave System

Spawn units on a periodic timer and route them through a series of waypoints using queued move orders.

### Global variables

```galaxy
// Declare in your GlobalVariables file
point[10] gv_laneSpawnPoint;       // spawn location per lane
point[10][11] gv_laneWaypoints;    // ordered waypoints per lane (up to 11)
int[10] gv_laneWaypointCount;      // number of registered waypoints per lane
int gv_laneCount = 0;
trigger gt_SpawnUnits;
```

### Register lanes at map init

```galaxy
void WaveSystem_RegisterLane(int lp_lane, point lp_spawn) {
    gv_laneSpawnPoint[lp_lane]    = lp_spawn;
    gv_laneWaypointCount[lp_lane] = 0;
    if (lp_lane > gv_laneCount) { gv_laneCount = lp_lane; }
}

void WaveSystem_AddWaypoint(int lp_lane, point lp_pt) {
    int lv_idx = gv_laneWaypointCount[lp_lane] + 1;
    gv_laneWaypoints[lp_lane][lv_idx] = lp_pt;
    gv_laneWaypointCount[lp_lane] = lv_idx;
}
```

### Example setup

```galaxy
void MapInit_Waves() {
    WaveSystem_RegisterLane(1, PointCreate(10.0, 50.0));
    WaveSystem_AddWaypoint(1, PointCreate(35.0, 50.0));
    WaveSystem_AddWaypoint(1, PointCreate(70.0, 50.0));
    WaveSystem_AddWaypoint(1, PointCreate(100.0, 50.0));

    gt_SpawnUnits = TriggerCreate("WaveSpawn_Handler");
    TriggerAddEventTimePeriodic(gt_SpawnUnits, 30.0, c_timeGame);
}
```

### Wave spawn handler

```galaxy
bool WaveSpawn_Handler(bool testConds, bool runActions) {
    int  lv_lane;
    int  lv_u;
    int  lv_wp;
    unit lv_unit;

    for (lv_lane = 1; lv_lane <= gv_laneCount; lv_lane += 1) {
        for (lv_u = 1; lv_u <= 5; lv_u += 1) {
            UnitCreate(1, "Zergling", c_unitCreateIgnorePlacement,
                2, gv_laneSpawnPoint[lv_lane], 270.0);
            lv_unit = UnitLastCreated();

            // Queue move orders through each waypoint in sequence
            for (lv_wp = 1; lv_wp <= gv_laneWaypointCount[lv_lane]; lv_wp += 1) {
                UnitIssueOrder(lv_unit,
                    OrderTargetingPoint(
                        AbilityCommand("move", 0),
                        gv_laneWaypoints[lv_lane][lv_wp]
                    ),
                    c_orderQueueAddToEnd  // MUST use AddToEnd — Replace cancels previous waypoints
                );
            }
        }
    }
    return true;
}
```

### Enabling/disabling spawns

```galaxy
TriggerEnable(gt_SpawnUnits, true);   // start spawning
TriggerEnable(gt_SpawnUnits, false);  // pause spawning
```

---

## Jungle / Camp Respawn System

When all units in a neutral camp die, wait a fixed time then recreate them at the spawn point.

### Global variables

```galaxy
// Declare in your GlobalVariables file
point[20]     gv_campSpawn;
 string[20]    gv_campUnitType;
int[20]       gv_campUnitCount;
fixed[20]     gv_campRespawnTime;
unitgroup[20] gv_campGroup;
int           gv_campCount = 0;
```

### Register a camp at map init

```galaxy
void Camp_Register(point lp_spawn, string lp_type, int lp_count, fixed lp_respawn) {
    int lv_u;
    gv_campCount += 1;
    int lv_idx = gv_campCount;

    gv_campSpawn[lv_idx]       = lp_spawn;
    gv_campUnitType[lv_idx]    = lp_type;
    gv_campUnitCount[lv_idx]   = lp_count;
    gv_campRespawnTime[lv_idx] = lp_respawn;
    gv_campGroup[lv_idx]       = UnitGroupEmpty();

    // Spawn initial units
    for (lv_u = 1; lv_u <= lp_count; lv_u += 1) {
        UnitCreate(1, lp_type, c_unitCreateIgnorePlacement,
            c_playerNeutralHostile, lp_spawn, 270.0);
        UnitGroupAdd(gv_campGroup[lv_idx], UnitLastCreated());
    }

    trigger lv_t = TriggerCreate("Camp_OnDeath");
    TriggerAddEventUnitDied(lv_t, null);
}
```

### Shared death / respawn handler

```galaxy
bool Camp_OnDeath(bool testConds, bool runActions) {
    unit lv_dead = EventUnit();
    int  lv_camp;
    int  lv_u;

    for (lv_camp = 1; lv_camp <= gv_campCount; lv_camp += 1) {
        if (!UnitGroupHasUnit(gv_campGroup[lv_camp], lv_dead)) { continue; }

        UnitGroupRemove(gv_campGroup[lv_camp], lv_dead);

        // Only respawn once the whole camp is cleared
        if (UnitGroupCount(gv_campGroup[lv_camp], c_unitCountAlive) > 0) { return true; }

        Wait(gv_campRespawnTime[lv_camp], c_timeGame);

        gv_campGroup[lv_camp] = UnitGroupEmpty();
        for (lv_u = 1; lv_u <= gv_campUnitCount[lv_camp]; lv_u += 1) {
            UnitCreate(1, gv_campUnitType[lv_camp], c_unitCreateIgnorePlacement,
                c_playerNeutralHostile, gv_campSpawn[lv_camp], 270.0);
            UnitGroupAdd(gv_campGroup[lv_camp], UnitLastCreated());
        }
        return true;
    }
    return true;
}
```

---

## Resource Rewards on Kill

Listen for unit death, identify the type, and reward the killing player with `PlayerModifyPropertyInt`.

```galaxy
void KillReward_Init() {
    trigger lv_t = TriggerCreate("KillReward_Handler");
    TriggerAddEventUnitDied(lv_t, null);
}

bool KillReward_Handler(bool testConds, bool runActions) {
    unit   lv_dead   = EventUnit();
    int    lv_killer = EventUnitKillingPlayer();
    string lv_type   = UnitGetType(lv_dead);

    if (lv_killer < 1) { return true; }  // killed by environment / trigger

    if (lv_type == "Zergling") {
        PlayerModifyPropertyInt(lv_killer, c_playerPropMinerals, c_playerPropOperAdd, 10);
    } else if (lv_type == "Roach") {
        PlayerModifyPropertyInt(lv_killer, c_playerPropMinerals, c_playerPropOperAdd, 25);
        PlayerModifyPropertyInt(lv_killer, c_playerPropVespene,  c_playerPropOperAdd, 5);
    }
    return true;
}
```

> `EventUnitKillingPlayer()` returns the player that dealt the killing blow. Returns -1 if killed by a non-player source.

---

## Tech Tree Upgrades

```galaxy
// Add an upgrade level to a player's tech tree
TechTreeUpgradeAddLevel(lv_player, "UpgradeName", 1);   // +1 level
TechTreeUpgradeAddLevel(lv_player, "UpgradeName", -1);  // -1 level (downgrade)

// Set level to a specific value
TechTreeUpgradeSetLevel(lv_player, "UpgradeName", 3);

// Get current level
int lv_lvl = TechTreeUpgradeGetLevel(lv_player, "UpgradeName");

// Query event for upgrade changes
TriggerAddEventUpgradeLevelChanged(myTrigger, c_playerAny);
// Inside handler:
string lv_upgrade = EventUpgradeName();
int    lv_delta   = EventUpgradeLevelDelta();

// Production restrictions
TechTreeRestrictionsEnable(lv_player, "Marine", false);   // allow
TechTreeRestrictionsEnable(lv_player, "Marine", true);    // restrict
```

---

## Melee Init (RTS Player Setup)

Initializes the default melee economy and unit placement for an AI/RTS player:

```galaxy
// Place starting units at startPoint for the given player and race
MeleeInitUnitsForPlayer(lv_player, PlayerRace(lv_player), lv_startPoint);

// Give standard starting resources
MeleeInitResourcesForPlayer(lv_player, PlayerRace(lv_player));

// Set upgrade levels for the RTS player (see Tech Tree Upgrades section)
TechTreeUpgradeAddLevel(lv_player, "UpgradeName", 1);
```

---

## Death & Revive System

### Hero unit revive (`UnitRevive`)

`UnitRevive` only works on `CUnitHero` type units. It preserves XP and level and revives the unit in place.

```galaxy
void HeroRevive_Init() {
    trigger lv_t = TriggerCreate("HeroRevive_Handler");
    TriggerAddEventUnitDied(lv_t, null);
}

bool HeroRevive_Handler(bool testConds, bool runActions) {
    unit lv_dead = EventUnit();  // capture BEFORE any Wait

    if (!UnitIsHero(lv_dead)) { return true; }

    Wait(10.0, c_timeGame);

    UnitRevive(lv_dead);  // revives in place; XP and level preserved
    return true;
}
```

### Regular unit respawn (`UnitCreate`)

For non-hero units, capture all needed state before `Wait`, then recreate:

```galaxy
bool UnitRespawn_Handler(bool testConds, bool runActions) {
    unit   lv_dead   = EventUnit();            // capture BEFORE Wait
    string lv_type   = UnitGetType(lv_dead);
    int    lv_player = UnitGetOwner(lv_dead);
    point  lv_pos    = UnitGetPosition(lv_dead);
    fixed  lv_face   = UnitGetFacing(lv_dead);

    Wait(10.0, c_timeGame);

    UnitCreate(1, lv_type, c_unitCreateIgnorePlacement,
        lv_player, lv_pos, lv_face);
    return true;
}
```

> **Always capture `EventUnit()` and all derived state as the very first actions, before any `Wait`.** After a `Wait` the trigger event context may have been reused by a later death event.

---

## Game Attributes (Mode Detection)

```galaxy
// Read lobby options (set at game creation)
string lv_attr = GameAttributeGameValue("attrId");
// Example:
bool isHardMode = (GameAttributeGameValue("Difficulty") == "Hard");
```

---

## Game Time

```galaxy
fixed lv_elapsed  = GameGetMissionTime();   // seconds since map start
fixed lv_timeGame = TimerGetElapsed(lv_timer);

// Async delay in a trigger function
Wait(5.0, c_timeGame);     // 5 game seconds
Wait(1.0, c_timeReal);     // 1 real second
```
