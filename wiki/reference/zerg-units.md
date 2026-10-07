# Zerg Unit Reference Guide (HotS — optional)

Shipped as an **example** for Heart of the Swarm Zerg campaigns. For Terran/Protoss or non-HotS bases, create `wiki/reference/units.md` with your faction's IDs. Update or replace this page when your design diverges from vanilla HotS.

> ⚠️ **Critical naming trap:** The buildable "Swarm Queen" unit the player trains has `CUnit id="Queen"`. The `CUnit id="SwarmQueen"` is a *completely different* unit — it is Niadra's hero form in zexpedition03 and is not buildable by the player. Do not confuse them.

---

## Basic Buildable Units

These are the standard HotS campaign buildable units (strains replace base units after evolution choices in vanilla HotS).

| Design Name | CUnit ID | Burrowed CUnit ID | Notes |
|---|---|---|---|
| Drone | `Drone` | `DroneBurrowed` | Worker |
| Zergling | `Zergling` | `ZerglingBurrowed` | Replaced by strain after evo mission |
| Swarm Queen | `Queen` | `QueenBurrowed` | ⚠️ NOT `SwarmQueen` — that is Niadra |
| Roach | `Roach` | `RoachBurrowed` | Replaced by strain after evo mission |
| Hydralisk | `Hydralisk` | `HydraliskBurrowed` | After evo mission, replaced by `HydraliskLurker` or `HydraliskImpaler` |
| Baneling | `Baneling` | `BanelingBurrowed` | Replaced by strain after evo mission |
| Aberration | `InfestedAbomination` | `InfestedAbominationBurrowed` | Design doc calls it "Aberration" |
| Mutalisk | `Mutalisk` | *(air — no burrow)* | After evo mission, replaced by `MutaliskBroodlord` or `MutaliskViper` |
| Swarm Host | `SwarmHost` | `SwarmHostBurrowed` | Replaced by strain after evo mission |
| Ultralisk | `Ultralisk` | `UltraliskBurrowed` | Replaced by strain after evo mission |

---

## Evolution Mission Strain Replacements

After completing an evolution mission, the chosen strain **permanently replaces** the base unit for all future missions. The unchosen strain cannot be built. Burrowed variants follow the same `<ID>Burrowed` pattern.

### Zergling → Raptor or Swarmling (zevolutionzergling)
| Strain | CUnit ID | Burrowed |
|---|---|---|
| Raptor Strain | `HotSRaptor` | `HotSRaptorBurrowed` |
| Swarmling Strain | `HotSSwarmling` | `HotSSwarmlingBurrowed` |

### Baneling → Hunter or Splitterling (zevolutionbaneling)
| Strain | CUnit ID | Burrowed |
|---|---|---|
| Hunter Strain | `HotSHunter` | `HotSHunterBurrowed` |
| Splinterling Strain | `HotSSplitterlingBig` | `HotSSplitterlingBigBurrowed` |

### Roach → Corpser or Vile (zevolutionroach)
| Strain | CUnit ID | Burrowed |
|---|---|---|
| Corpser Strain | `RoachCorpser` | `RoachCorpserBurrowed` |
| Vile Strain | `RoachVile` | `RoachVileBurrowed` |

### Hydralisk → Lurker or Impaler form (zevolutionhydralisk)

The Hydralisk's visual and abilities change. The new unit is still the "Hydralisk" from a gameplay perspective but can now morph into the chosen advanced unit.

| Choice | Hydralisk Form CUnit ID | Burrowed | Morphs Into | Morphed CUnit ID |
|---|---|---|---|---|
| Lurker path | `HydraliskLurker` | `HydraliskLurkerBurrowed` | Lurker | `Lurker` |
| Impaler path | `HydraliskImpaler` | `HydraliskImpalerBurrowed` | Impaler | `Impaler` |

> `HydraliskLurker` and `HydraliskImpaler` are the **Hydralisk units** (trainable from hatchery). `Lurker` and `Impaler` are the **morphed forms** (like a Roach→Ravager morph). Lurker burrowed: `LurkerBurrowed`. Impaler burrowed: `ImpalerBurrowed`. See burrow mechanics note below.

### Mutalisk → Broodlord or Viper form (zevolutionmutalisk)

Same pattern as Hydralisk. The Mutalisk form changes and can morph into the chosen unit.

| Choice | Mutalisk Form CUnit ID | Morphs Into | Morphed CUnit ID | Notes |
|---|---|---|---|---|
| Broodlord path | `MutaliskBroodlord` | Broodlord | `BroodLord` | Both air units — no burrow |
| Viper path | `MutaliskViper` | Viper | `Viper` | Both air units — no burrow |

### Swarm Host → Strain A or B (zevolutionswarmhost)
| Strain | CUnit ID | Burrowed |
|---|---|---|
| Strain A | `SwarmHostSplitA` | `SwarmHostSplitABurrowed` |
| Strain B | `SwarmHostSplitB` | `SwarmHostSplitBBurrowed` |

### Ultralisk → Noxious or Torrasque (zevolutionultralisk)
| Strain | CUnit ID | Burrowed |
|---|---|---|
| Noxious Strain | `HotSNoxious` | `HotSNoxiousBurrowed` |
| Torrasque Strain | `HotSTorrasque` | `HotSTorrasqueBurrowed` |

---

## Air Units (no burrow ability)

| Unit | CUnit ID | Notes |
|---|---|---|
| Mutalisk | `Mutalisk` | Replaced by strain after evo mission |
| Mutalisk (Broodlord path) | `MutaliskBroodlord` | Pre-morph form |
| Mutalisk (Viper path) | `MutaliskViper` | Pre-morph form |
| Broodlord | `BroodLord` | Morphed from `MutaliskBroodlord` |
| Viper | `Viper` | Morphed from `MutaliskViper` |
| Overlord | `Overlord` | Supply + transport |
| Overseer | `Overseer` | Morphed from Overlord; detector |
| Brood Queen | `QueenClassic` | KaldirChoice=1 only |

---

## Special / Hero Units (not buildable by player)

| Unit | CUnit ID | Where Used |
|---|---|---|
| Niadra (Stage 1) | `SwarmQueen` | zexpedition03 only — ⚠️ NOT the buildable Swarm Queen |
| Niadra (Stage 2) | `LargeSwarmQueen` | zexpedition03 only |
| Niadra (Final) | `HugeSwarmQueen` | zexpedition03 only |
| Niadra (Larva) | `LarvalQueen` | zexpedition03 start — ignore for challenges |
| Zagara | `ZaGara` | Zerus strategic hero / campaign hero; burrowed form is `ZaGaraBurrowed` |
| Kerrigan (Ghost Lab) | `KerriganGhostLab` | Specific HotS lab missions |
| Kerrigan (Char form) | `KerriganChar` | Char / challenge variants |
| Kerrigan (standard) | `K5Kerrigan` | Most HotS campaign missions |

---

## Burrow Mechanics

All Zerg ground units have a burrow ability. When burrowed, a unit:
- Switches to its burrowed `CUnit id` (e.g., `Roach` → `RoachBurrowed`)
- Becomes **cloaked** (invisible without a detector)
- Can be **passed over** by other units (no collision)
- **Cannot attack** in burrowed state — with two exceptions:

| Unit | Attack behavior |
|---|---|
| All other ground units | Can attack unburrowed; **cannot** attack burrowed |
| `Lurker` / `LurkerBurrowed` | **Cannot** attack unburrowed; can only attack as `LurkerBurrowed` |
| `Impaler` / `ImpalerBurrowed` | **Cannot** attack unburrowed; can only attack as `ImpalerBurrowed` |

> **Galaxy implication:** When searching for "all Roaches" to apply a buff, you must query both `Roach` and `RoachBurrowed` as they are treated as different unit types in unit group filters. The same applies to every ground unit and all its strains.

---

## Rules for Galaxy Unit Group Iteration

When writing code that iterates "all player Zerglings" (or any unit that may have been replaced by a strain), you must include all possible IDs:

```galaxy
// Example: apply buff to all Zergling-type units
// Must cover base unit + both strains + burrowed variants of each
string[6] zerglingTypes;
int i;
unitGroup ug;

zerglingTypes[0] = "Zergling";
zerglingTypes[1] = "ZerglingBurrowed";
zerglingTypes[2] = "HotSRaptor";
zerglingTypes[3] = "HotSRaptorBurrowed";
zerglingTypes[4] = "HotSSwarmling";
zerglingTypes[5] = "HotSSwarmlingBurrowed";
for (i = 0; i < 6; i += 1) {
    ug = UnitGroup(zerglingTypes[i], 1, UnitFilter(0,0,0,0), RegionEntireMap(), 200);
    // apply buff to each unit in ug...
}
```

> In practice, for challenge effects applied at mission start, it may be simpler to use a broad `UnitFilter` with `c_playerAny` and then check `UnitGetType(u) == "Zergling"` etc. in the loop body. Use whichever approach is cleaner for the specific challenge.

---

## Where Unit IDs Are Used

| Context | File to edit |
|---|---|
| `AffectedUnitArray` (button visibility on unit card) | `UpgradeData.xml` — add one entry per unit ID + burrowed variant + all strains |
| `EffectArray Reference="Unit,ID,..."` (stat changes) | `UpgradeData.xml` — must list every ID explicitly; parent upgrades do NOT auto-cover strains |
| Galaxy unit group iteration | `<configured mods_dir>/AeonOfIhanrii.SC2Mod/Base.SC2Data/Epi_Main.galaxy` — cover base + strains + all burrowed/state variants |
| Challenge / buff code targeting player army | Project guides under `wiki/guides/` when created |

**SwarmHost state reminder:** SwarmHost has 3 states × 3 unit variants = 9 IDs: `SwarmHost`, `SwarmHostRooted`, `SwarmHostBurrowed`, `SwarmHostSplitA`, `SwarmHostSplitARooted`, `SwarmHostSplitABurrowed`, `SwarmHostSplitB`, `SwarmHostSplitBRooted`, `SwarmHostSplitBBurrowed`.

---
