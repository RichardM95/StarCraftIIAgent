---
name: galaxy-players-and-alliances
description: Player data patterns, playergroups, alliance setup, race helpers, player resources, camera control, game attributes, difficulty, player state flags, player color, and game-over calls in Galaxy script. Use when initializing alliances at map start, iterating active players, reading or modifying minerals/gas, checking player race, or ending the game for a player or group. Do not use for unit ownership queries (use galaxy-units-and-groups).
---

## Loading Boundary

- **This sub-skill owns:** player data, playergroups, alliances, race helpers, player resources, camera control, game attributes, difficulty, player state flags, and game-over calls
- **Parent root skill (`sc2-galaxy-scripting`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `galaxy-units-and-groups` (unit ownership), `galaxy-game-systems` (bank/revive), `galaxy-sound-camera-environment` (camera movement)

# Galaxy Scripting – Players & Alliances

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
| NativeLib alliance helpers | `TriggerLibs/NativeLib.galaxy` — `libNtve_gf_SetAlliance`, `libNtve_gf_SetPlayerGroupAlliance`, `libNtve_gf_SetAllianceBetweenTwoPlayerGroups`, `libNtve_gf_PlayerIsEnemy` |
| Variables guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/037_Variables/ |
| Records guide | https://s2editor-guides.readthedocs.io/New_Tutorials/03_Trigger_Editor/040_Records/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |

---

## Player Data Pattern (SSF)

Player state is stored in a struct array indexed by player slot (1-based):

```galaxy
// In GlobalVariables.galaxy
const int gv_MaxAmountPlayers = 6;

struct PlayerStruct {
    bool   activeFlag;
    bool   spectatingFlag;
    bank   bankfile;
    unit   heroUnit;
    int    points;
    int[gv_MaxAmountParts] wins;
    int    heroUnlocked;    // bitflag
};
PlayerStruct[gv_MaxAmountPlayers + 1] gv_PlayerStats;

// CRITICAL TYPE DISTINCTION — single-slot player IDs vs player groups:
//   gv_rTSPlayer1, gv_rTSPlayer2  →  int   (single player SLOT ID, e.g. 7 or 14)
//   gv_soldierPlayers1/2          →  playergroup  (group of multiple players on a team)
//
// Single-slot IDs are assigned via PlayerGroupPlayer() which returns int:
//   gv_rTSPlayer1 = PlayerGroupPlayer(GameAttributePlayersForTeam(1), 1);
// These are used everywhere as int: IsZerg(gv_rTSPlayer1), PlayerStartLocation(gv_rTSPlayer2), etc.
// NEVER declare a single-slot id as playergroup — that causes 100+ "Parameter type mismatch" errors.

int gv_rTSPlayer1;        // int — single player slot for team 1
int gv_rTSPlayer2;        // int — single player slot for team 2
playergroup gv_soldierPlayers1;   // playergroup — all players on team 1
playergroup gv_soldierPlayers2;   // playergroup — all players on team 2

// Common shared playergroups
playergroup gv_ActivePG;      // currently active players
playergroup gv_StartingPG;    // players at game start
playergroup gv_SpectatingPG;  // spectators
int gv_PlayerAmount;
int gv_PlayerAmountStart;

// Special player slots
const int gv_BasePlayer  = 7;    // allied non-hero structures
const int gv_EnemyPlayer = 14;   // enemy units
```

Access per-player data:
```galaxy
gv_PlayerStats[playerID].activeFlag = true;
unit hero = gv_PlayerStats[playerID].heroUnit;
PlayerGroupAdd(gv_ActivePG, playerID);
```

---

## Player Groups

### Creating / populating

```galaxy
playergroup lv_pg = PlayerGroupEmpty();     // empty group
PlayerGroupAdd(lv_pg, 3);                   // add player 3
PlayerGroupAdd(lv_pg, 4);

playergroup lv_all    = PlayerGroupAll();    // all players (observers too)
playergroup lv_active = PlayerGroupActive();// only active (connected, playing) players
playergroup lv_single = PlayerGroupSingle(lv_player);// single-player group

// From lobby — all players assigned to a team
playergroup lv_team1 = GameAttributePlayersForTeam(1);
```

### Querying

```galaxy
bool lv_has   = PlayerGroupHasPlayer(lv_pg, 2);
int  lv_count = PlayerGroupCount(lv_pg);
```

### Iterating active players (SSF pattern)

```galaxy
int tmpInt = -1;
while (true) {
    tmpInt = PlayerGroupNextPlayer(gv_ActivePG, tmpInt);
    if (tmpInt < 0) { break; }
    // act on tmpInt
}
```

---

## Player Info

```galaxy
string lv_name   = PlayerName(lv_player);
string lv_race   = PlayerRace(lv_player);            // "Terr", "Zerg", "Prot", "random"
int    lv_color  = PlayerGetColorIndex(lv_player, false);
color  lv_c      = libNtve_gf_ConvertPlayerColorToColor(lv_player);

// Slot state
int lv_status = PlayerStatus(lv_player);  // c_playerStatusActive, c_playerStatusLeft, etc.
bool lv_active = (lv_status == c_playerStatusActive);

// Slot type
PlayerType(lv_player);  // c_playerTypeUser, c_playerTypeComputer, c_playerTypeHuman
```

---

## Race Helpers

```galaxy
bool IsTerran(int player) {
    return StringContains(PlayerRace(player), "Terr", c_stringAnywhere, c_stringNoCase);
}
bool IsZerg(int player) {
    return StringContains(PlayerRace(player), "Zerg", c_stringAnywhere, c_stringNoCase);
}
bool IsProtoss(int player) {
    return StringContains(PlayerRace(player), "Prot", c_stringAnywhere, c_stringNoCase);
}
```

---

## Setting Race

```galaxy
PlayerSetRace(lv_player, "Terr");   // "Terr", "Zerg", "Prot"
```

---

## Alliance Settings

### Using the library helper (recommended)

```galaxy
// Ally with full shared vision
libNtve_gf_SetAlliance(1, 2, libNtve_ge_AllianceSetting_AllyWithSharedVision);

// Ally + shared vision + can push allies (used for same-team players)
libNtve_gf_SetAlliance(1, 2, libNtve_ge_AllianceSetting_AllyWithSharedVisionAndPushable);

// Ally + shared vision + full control over allies' units
libNtve_gf_SetAlliance(1, 2, libNtve_ge_AllianceSetting_AllyWithSharedVisionAndControl);

// Enemy
libNtve_gf_SetAlliance(1, 3, libNtve_ge_AllianceSetting_Enemy);

// Neutral with shared vision
libNtve_gf_SetAlliance(1, 2, libNtve_ge_AllianceSetting_NeutralWithSharedVision);

// Neutral (no vision)
libNtve_gf_SetAlliance(1, 2, libNtve_ge_AllianceSetting_Neutral);

// Precise alliance level presets (all confirmed in NativeLib_h.galaxy)
// libNtve_ge_AllianceSetting_Ally                                  = 0
// libNtve_ge_AllianceSetting_AllyWithSharedVision                  = 1
// libNtve_ge_AllianceSetting_AllyWithSharedVisionAndPushable        = 2
// libNtve_ge_AllianceSetting_AllyWithSharedVisionAndControl         = 3
// libNtve_ge_AllianceSetting_AllyWithSharedVisionControlAndSpending = 4
// libNtve_ge_AllianceSetting_Enemy                                  = 5
// libNtve_ge_AllianceSetting_EnemyWithSharedVision                  = 6
// libNtve_ge_AllianceSetting_Neutral                                = 7
// libNtve_ge_AllianceSetting_NeutralWithSharedVision                = 8
// libNtve_ge_AllianceSetting_NeutralWithSharedVisionAndPushable     = 9

// Player relation constants (for checking relationships, not setting them)
// libNtve_ge_PlayerRelation_Ally         = 0
// libNtve_ge_PlayerRelation_AllyMutual   = 1
// libNtve_ge_PlayerRelation_Neutral      = 2
// libNtve_ge_PlayerRelation_NeutralMutual = 3
// libNtve_ge_PlayerRelation_Enemy        = 4
// libNtve_ge_PlayerRelation_EnemyMutual  = 5
```

### Low-level alliance control

```galaxy
// Set a specific alliance channel
PlayerSetAlliance(lv_player, c_allianceIdTrade,        lv_other, true);
PlayerSetAlliance(lv_player, c_allianceIdControl,       lv_other, true);
PlayerSetAlliance(lv_player, c_allianceIdSeekHelp,      lv_other, false);
PlayerSetAlliance(lv_player, c_allianceIdPassive,       lv_other, false);
PlayerSetAlliance(lv_player, c_allianceIdSharedVision,  lv_other, true);
PlayerSetAlliance(lv_player, c_allianceIdPushable,      lv_other, true);  // units can physically push each other

// Query an alliance channel
bool lv_allied = PlayerGetAlliance(lv_player, c_allianceIdChat, lv_other);

// Common alliance ID constants
c_allianceIdTrade
c_allianceIdControl
c_allianceIdSeekHelp
c_allianceIdPassive
c_allianceIdPushToTalk
c_allianceIdSharedVision
c_allianceIdChat
c_allianceIdPushable
```

### Enemy/ally relationship check

```galaxy
// libNtve helper
bool lv_isEnemy = libNtve_gf_PlayerIsEnemy(
    lv_me, lv_target,
    libNtve_ge_PlayerRelation_Enemy  // or _Ally or _Neutral
);
```

---

## Player Resources

```galaxy
// Read
int lv_minerals = PlayerGetPropertyInt(lv_player, c_playerPropMinerals);
int lv_gas      = PlayerGetPropertyInt(lv_player, c_playerPropVespene);
int lv_supply   = PlayerGetPropertyInt(lv_player, c_playerPropSuppliesUsed);

// Write (absolute set)
PlayerModifyPropertyInt(lv_player, c_playerPropMinerals, c_playerPropOperSetTo, 500);

// Write (add/subtract)
PlayerModifyPropertyInt(lv_player, c_playerPropMinerals, c_playerPropOperAdd, 100);
PlayerModifyPropertyInt(lv_player, c_playerPropVespene,  c_playerPropOperSubtract, 25);

// Set handicap (AI difficulty scalar — reduces AI unit HP/damage)
PlayerModifyPropertyInt(lv_player, c_playerPropHandicap, c_playerPropOperSetTo, 50);

// Common property constants
c_playerPropMinerals
c_playerPropVespene
c_playerPropSuppliesUsed
c_playerPropSuppliesMade
c_playerPropSuppliesLimit
c_playerPropKills
c_playerPropDeaths
c_playerPropHandicap     // AI handicap level (0-100)
```

---

## Camera Control

```galaxy
// Pan camera to point
CameraPan(lv_player, lv_point, 0.0, -1, 10.0, false);
// (player, point, distance, yaw, pitch, sync)

// Snap camera instantly
CameraSetTarget(lv_player, lv_point, 0.0, -1, 10.0, false);
```

---

## Game Attributes (Lobby Options)

Used to read lobby-configured game settings:

```galaxy
// Returns the string value of the attribute for this player/game
string lv_val = GameAttributeGameValue("attrId");

// Example: select difficulty by attribute
bool isHardMode = (GameAttributeGameValue("Difficulty") == "Hard");
```

---

## Difficulty

```galaxy
// Get the current mission difficulty as an integer
// 1 = Casual, 2 = Normal, 3 = Hard, 4 = Brutal
int lv_diff = PlayerDifficulty(1);

// Branch on it
if (PlayerDifficulty(1) >= 3) {
    // hard or brutal
}
```

---

## Player State Flags

```galaxy
// Hide this player from the leader panel (used for non-playing computer slots)
PlayerSetState(lv_player, c_playerStateDisplayInLeaderPanel, false);

// Disable score accumulation for this player
PlayerSetState(lv_player, c_playerStateShowScore, false);
PlayerSetState(lv_player, c_playerStateXPGain, false);

// Disable unit fidgeting animations (helps performance / cutscenes)
PlayerSetState(lv_player, c_playerStateFidgetingEnabled, false);

// Query a state
bool lv_inPanel = PlayerGetState(lv_player, c_playerStateDisplayInLeaderPanel);
```

---

## Game Over

```galaxy
// For a specific player
GameOver(lv_player, c_gameOverVictory, true, true);  // (player, result, showScore, restart)
GameOver(lv_player, c_gameOverDefeat,  true, true);

// For a playergroup
libNtve_gf_EndGameForPlayerGroup(lv_group, c_gameOverVictory, true, true);

// Constants
c_gameOverVictory
c_gameOverDefeat
c_gameOverLeave
c_gameOverTie
```

---

## Player Color

```galaxy
// Get color index
int lv_idx = PlayerGetColorIndex(lv_player, false);

// Convert to color value
color lv_color = libNtve_gf_ConvertPlayerColorToColor(lv_player);

// Use in text
text lv_colored = TextWithColor(StringToText(PlayerName(lv_player)), lv_color);
```

---

## Alliance Init Pattern (SSF)

SSF initializes all alliances from scratch at map start, starting neutral then setting specifics:

```galaxy
void MapInit_ActivePlayers() {
    int tmpInt;

    gv_ActivePG  = PlayerGroupEmpty();
    gv_StartingPG = PlayerGroupEmpty();

    // Start everyone neutral
    libNtve_gf_SetPlayerGroupAlliance(PlayerGroupAll(), libNtve_ge_AllianceSetting_Neutral);

    // Specific overrides
    libNtve_gf_SetAlliance(gv_BasePlayer, gv_EnemyPlayer, libNtve_ge_AllianceSetting_Enemy);
    libNtve_gf_SetAlliance(gv_EnemyPlayer, gv_CollectiblePlayerEnemyAllied, libNtve_ge_AllianceSetting_AllyWithSharedVision);

    // Add active players to groups and set their alliances
    for (tmpInt = 1; tmpInt <= gv_MaxAmountPlayers; tmpInt += 1) {
        if (PlayerStatus(tmpInt) == c_playerStatusActive) {
            gv_PlayerStats[tmpInt].activeFlag = true;
            PlayerGroupAdd(gv_ActivePG, tmpInt);
            PlayerGroupAdd(gv_StartingPG, tmpInt);
            libNtve_gf_SetAlliance(tmpInt, gv_EnemyPlayer, libNtve_ge_AllianceSetting_Enemy);
            libNtve_gf_SetAlliance(tmpInt, gv_BasePlayer, libNtve_ge_AllianceSetting_AllyWithSharedVisionAndControl);
            PlayerOptionOverride(tmpInt, "simplecommandcard", "0");
        }
    }
    gv_PlayerAmount = PlayerGroupCount(gv_ActivePG);
    gv_PlayerAmountStart = gv_PlayerAmount;

    // All players allied with each other
    libNtve_gf_SetPlayerGroupAlliance(gv_StartingPG, libNtve_ge_AllianceSetting_AllyWithSharedVisionAndPushable);

    // Set enemy player color
    PlayerSetColorIndex(gv_EnemyPlayer, 13, true);
}
```
