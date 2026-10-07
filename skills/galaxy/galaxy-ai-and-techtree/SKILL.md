---
name: galaxy-ai-and-techtree
description: AI behavior, melee AI initialization, tech tree upgrades, wave difficulty scaling, AI waves, unit restrictions, and tactical AI helpers in Galaxy script. Use when setting up computer-controlled players, scaling enemy difficulty per wave, managing tech tree restrictions, or scripting AI attack waves. Do not use for player-controlled unit behavior (use galaxy-units-and-groups).
---

## Loading Boundary

- **This sub-skill owns:** AI behavior, melee AI initialization, tech tree upgrades, wave difficulty scaling, AI waves, unit restrictions, and tactical AI helpers
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-units-and-groups` (player-controlled unit behavior), `galaxy-game-systems` (spawner/wave systems), `galaxy-players-and-alliances` (player race/tech)

# Galaxy Scripting – AI & Tech Tree

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
| SC2 editor guides | https://s2editor-guides.readthedocs.io |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Melee AI Initialization

For RTS players that use the standard SC2 melee AI:

```galaxy
// Place starting units (workers + command center/hatchery/nexus)
MeleeInitUnitsForPlayer(lv_player, "Terr", lv_startPoint);
MeleeInitUnitsForPlayer(lv_player, "Zerg", lv_startPoint);
MeleeInitUnitsForPlayer(lv_player, "Prot", lv_startPoint);

// Give starting resources (minerals/gas)
MeleeInitResourcesForPlayer(lv_player, PlayerRace(lv_player));

// Start the AI
AIStart(lv_player, "AI\\Terran.SC2AIData", false, false, false, false);

// Variant that applies to all computer players
MeleeInitAI();
```

---

## AI Build/Train/Research (Script-Level)

```galaxy
// Queue a building
AIBuild(lv_player, "CommandCenter", lv_town, 1, true);
AITrain(lv_player, "Marine", lv_town, 1, true);
AIResearch(lv_player, "MarineRange", lv_town);

// Stock control (maintain a count of a unit type)
AISetStock(lv_player, "Marine", 8);
AISetStockEx(lv_player, "Tank", 4, c_townAny, true, true);

// Clear queues
AIClearBuildQueue(lv_player);
AIClearTrainQueue(lv_player);
```

---

## AI Waves

Waves are AI attack or patrol groups.

```galaxy
// Get a wave
wave lv_wave = AIWaveGet(lv_player, c_waveTypeAttack, 0);

// Get units in a wave
unitgroup lv_waveUnits = AIWaveGetUnits(lv_wave);

// Wave target helpers
wavetarget lv_tgt = AIWaveTargetGatherMelee(lv_player, lv_gatherPoint);
wavetarget lv_tgt2 = AIWaveTargetMeleeDefend(lv_player, lv_defPoint);

// Turn waves on/off
libNtve_gf_CAIWavesEnable(lv_player, true);
libNtve_gf_CAIWaveEnable(lv_player, lv_wave, false);
```

---

## AI Attack Wave – Scripted

Use when you want to manually direct an attack wave rather than using the default AI targeting:

```galaxy
// Direct the attack wave at a specific player (standard)
AIAttackWave(lv_player, lv_targetPlayer, c_aiAttackWaveGround, lv_gatherPoint);

// Direct the attack wave at a specific map point (not a player)
AIAttackWaveSetTargetPoint(lv_player, lv_targetPoint);

// Use an entire pre-built unit group as the attack wave (bypasses wave builder)
AIAttackWaveUseGroup(lv_player, lv_unitGroup);
```

---

## Drop Pods (Campaign)

`libCamp_gf_CreateDropPod` handles all the drop action: spawns pod, ejects units, plays effects.

```galaxy
// Build the group of units that will drop
unitgroup lv_dropGroup = UnitGroupEmpty();
libNtve_gf_CreateUnitsAtPoint2(4, "Zergling", lv_enemyPlayer, lv_dropPoint);
UnitGroupAdd(lv_dropGroup, UnitLastCreated());

// Zerg drop pod
libCamp_gf_CreateDropPod(libCamp_ge_DropPodRace_Zerg, lv_dropPoint, lv_dropGroup, false);

// Terran drop pod
libCamp_gf_CreateDropPod(libCamp_ge_DropPodRace_Terran, lv_dropPoint, lv_dropGroup, true);
```

---

## Campaign Tech & Story State

```galaxy
// Enable or disable a campaign tech unit for a player
libCamp_gf_EnableCampaignTechUnit(true, libCamp_ge_StoryTechGroup_Marine, lv_player);

// Read or write a story state variable (mission-to-mission carry-over)
// Story state values are integers stored in the campaign save
int lv_val = libCamp_gf_StoryState(libCamp_ge_StoryStateID_SomeFlag);
libCamp_gf_SetStoryState(libCamp_ge_StoryStateID_SomeFlag, 1);

// Common merc purchase state check
bool lv_hired = (libCamp_gf_StoryState(libCamp_ge_StoryStateID_SomeMercGroup) == libCamp_ge_StoryMercStatus_Purchased);
```

---

## Tech Tree – Upgrades

```galaxy
// Add a level to an upgrade for a player
TechTreeUpgradeAddLevel(lv_player, "MarineRange", 1);
TechTreeUpgradeAddLevel(lv_player, "MarineRange", -1);  // remove a level

// Set to specific level
TechTreeUpgradeSetLevel(lv_player, "MarineRange", 2);

// Read current level
int lv_lvl = TechTreeUpgradeGetLevel(lv_player, "MarineRange");

// Event when an upgrade changes
TriggerAddEventUpgradeLevelChanged(myTrigger, c_playerAny);
// Inside handler:
string lv_upgrade = EventUpgradeName();
int    lv_delta   = EventUpgradeLevelDelta();  // +1 or -1
int    lv_player  = EventPlayer();
```

---

## Tech Tree – Unit Counts

```galaxy
// How many of a unit type does player have?
int lv_count = TechTreeUnitCount(lv_player, "Marine", c_techCountBoth);

// Count constants
c_techCountAny   // counting training + alive
c_techCountBoth  // both alive and in training
c_techCountMade  // how many have ever been trained
c_techCountLost  // how many have been killed
```

---

## Tech Tree – Restrictions

```galaxy
// Stop a player from training/building something
TechTreeRestrictionsEnable(lv_player, "Banshee", true);  // restrict
TechTreeRestrictionsEnable(lv_player, "Banshee", false); // allow

// Check if restricted
bool lv_restr = TechTreeRestrictionsEnabled(lv_player, "Banshee");

// Requirements (prerequisite check)
TechTreeRequirementsEnable(lv_player, false); // disable all requirements checks
```

---

## Tech Tree – Production

```galaxy
// Set production cap (max simultaneous training of a type)
TechTreeProductionCapSet(lv_player, "Marine", 5);

// Reset
TechTreeProductionCapSet(lv_player, "Marine", c_techTreeProductionCapUnlimited);
```

---

## Wave Upgrade Pattern

Apply upgrades per wave to scale enemy difficulty. Track waves with a counter and apply upgrade levels on each wave transition:

```galaxy
void AddUpgradeForWave(int lp_player, string lp_upgrade) {
    TechTreeUpgradeAddLevel(lp_player, lp_upgrade, 1);
}

void RemoveUpgradeForWave(int lp_player, string lp_upgrade) {
    TechTreeUpgradeAddLevel(lp_player, lp_upgrade, -1);
}

// Called at start of each new wave:
void ApplyWaveUpgrades(int lp_waveNumber, int lp_enemyPlayer) {
    if (lp_waveNumber == 3) {
        AddUpgradeForWave(lp_enemyPlayer, "InflictedDamageIncrease");
    }
    if (lp_waveNumber == 5) {
        AddUpgradeForWave(lp_enemyPlayer, "ArmorIncrease");
    }
}
```

---

## AI Towns (Advanced)

```galaxy
// Get number of mineral/gas spots in a town
int lv_minerals = AIGetMineralNumSpots(lv_player, lv_town);
int lv_gas      = AIGetRawGasNumSpots(lv_player, lv_town);

// Get a town's gathering/defense locations
point lv_gather  = AIGetGatherLocation(lv_player, lv_town);
point lv_defense = AIGetGatherDefLocation(lv_player, lv_town);

// Set default economy behavior
AIDefaultEconomy(lv_player);
AIDefaultExpansion(lv_player);
```

---

## AI Evaluation

```galaxy
// Compare relative strengths
int lv_ratio = AIEvalRatio(lv_player1, lv_player2);
int lv_wRatio = AIWaveEvalRatio(lv_wave, lv_targetPlayer);

// Get best attack target
point lv_target = AIGetBestTarget(lv_player, lv_town, c_aiAttackWaveGround);
```

---

## Tactical AI Helpers (NativeLib)

These `libNtve_gf_*` functions are confirmed in NativeLib.galaxy:

```galaxy
// Set tactical range for a unit type for a player
libNtve_gf_SetTacticalAIRange(lv_player, "Marine", 8);
// (player, unitType, distance)

// Set tactical think target for a unit type
libNtve_gf_SetTacticalAIThink(lv_player, "Marine", "Zerg_Zergling", false);
// (player, unitType, targetUnitType, isNative)

// Force an AI unit to cast an ability (via scripted order)
libNtve_gf_AICast(lv_unit, OrderTargetingPoint(AbilityCommand("PsiStorm", 0), lv_point));
// (unit, order)

// Declare the next town center location for AI expansion
libNtve_gf_DeclareNextTown(lv_player, lv_expansionPoint);
// (player, centerPoint)
```

---

## Difficulty-Based Value Helpers (NativeLib)

```galaxy
// Returns a value based on current game difficulty
int   lv_hp   = libNtve_gf_DifficultyValueInt  (100, 150, 200, 250);  // easy/normal/advanced/expert
fixed lv_spd  = libNtve_gf_DifficultyValueFixed(1.0, 1.25, 1.5, 2.0);
string lv_type = libNtve_gf_DifficultyValueUnitType("Zergling", "Hydralisk", "Ultralisk", "Ultralisk");
```
