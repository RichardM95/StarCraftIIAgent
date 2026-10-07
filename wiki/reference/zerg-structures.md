# Zerg Structure Reference Guide (HotS — optional)

Example reference for HotS Zerg structures. Replace or supplement for other factions; see `setup.md`.

Reference for Zerg structure IDs, build/morph times, and how to correctly modify them via upgrades.

---

## How Build Time Actually Works

**`Unit.BuildTime` does NOT control construction speed.** SC2 ignores `Reference="Unit,X,BuildTime"` in upgrades — no effect, no error. There are two separate systems:

| Construction Type | Mechanism | Upgrade Reference Pattern |
|---|---|---|
| Drone morphs into structure | `CAbilBuild` `ZergBuild` ability, `InfoArray[BuildX].Time` | `Abil,ZergBuild,InfoArray[Build1].Time` |
| Drone morphs into special structure | Custom `CAbilBuild` ability, `InfoArray[Build1].Time` | `Abil,<YourPrefix>BuildCustomStructure,InfoArray[Build1].Time` (custom `CAbilBuild`) |
| Building upgrades into building | `CAbilMorph` ability, `InfoArray[0].SectionArray[Y].DurationArray[Delay]` | `Abil,UpgradeToLair,InfoArray[0].SectionArray[Abils].DurationArray[Delay]` |
| Building spawns a structure | `CAbilBuild` on the spawning building, `InfoArray[Build1].Time` | `Abil,BuildNydusCanal,InfoArray[Build1].Time` |

`Operation="Multiply" Value="0.5"` works for both (confirmed from SC2 campaign data).

---

## ZergBuild Ability — Drone Construction

All drone→structure construction goes through the single `ZergBuild` ability. Times shown are HotS campaign values (Swarm Campaign overrides the Liberty Mod base values).

| InfoArray Index | Unit ID | Build Time (s) | Source |
|---|---|---|---|
| `Build1` | `Hatchery` | 60 | Swarm Campaign override (Liberty: 100) |
| `Build3` | `Extractor` | 30 | Liberty Mod |
| `Build4` | `SpawningPool` | 30 | Swarm Campaign override (Liberty: 65) |
| `Build5` | `EvolutionChamber` | 40 | Swarm Campaign override |
| `Build6` | `HydraliskDen` | 40 | Liberty Mod |
| `Build7` | `Spire` | 40 | Swarm Campaign override (Liberty: 100) |
| `Build8` | `UltraliskCavern` | 50 | Swarm Campaign override (Liberty: 65) |
| `Build9` | `InfestationPit` | 40 | Swarm Campaign override (Liberty: 50) |
| `Build10` | `NydusNetwork` | 50 | Liberty Mod |
| `Build11` | `BanelingNest` | 30 | Swarm Campaign override (Liberty: 60) |
| `Build14` | `RoachWarren` | 40 | Swarm Campaign override (Liberty: 55) |
| `Build15` | `SpineCrawler` | 30 | Swarm Campaign override (Liberty: 50) |
| `Build16` | `SporeCrawler` | 30 | Liberty Mod |
| `Build17` | `LurkerDen` | 40 | Swarm Campaign addition (HotS only) |
| `Build19` | `AutomatedExtractor` | 30 | Swarm Campaign addition (HotS only) |
| `Build21` | `Digester` | 30 | Swarm Mod addition |

**LurkerDen vs ImpalerDen:** There is no `ImpalerDen` building. Both Lurker and Impaler paths use `LurkerDen` (Build17). The distinction is `HydraliskLurker` vs `HydraliskImpaler` as the trainable Hydralisk unit, not the den.

**Command-card cost display:** custom Drone build buttons must be linked as `Type="AbilCmd"` to the exact build command (e.g. `ZergBuild,Build22` for a custom unit, or `<YourPrefix>Build...,Build1` for a custom `CAbilBuild`). The cost shown on hover comes from the produced unit's `CostResource` plus visible resource tooltip flags; do not add manual cost text to the button tooltip. When patching Drone build submenus, keep both the inherited index and vanilla card ID (`CardLayouts index="1" CardId="ZBl1"`, `index="2" CardId="ZBl2"`) so the patch modifies the opened submenu instead of creating an unused duplicate.

---

## CAbilMorph — Building-to-Building Upgrades

These morphs do **not** involve a drone. Time is split across multiple SectionArrays; modify both `Abils` and `Stats` for gameplay effect (Actor controls animation only).

| Ability ID | From → To | Abils Delay (s) | Stats Delay (s) | Source |
|---|---|---|---|---|
| `UpgradeToLair` | Hatchery → Lair | 60 | 60 | Swarm Campaign override (Liberty: 80) |
| `UpgradeToHive` | Lair → Hive | 60 | 60 | Swarm Campaign override (Liberty: 100) |
| `UpgradeToGreaterSpire` | Spire → GreaterSpire | 100 | 100 | Liberty Mod (not overridden in Swarm) |
| `UpgradeToLurkerDenMP` | HydraliskDen → LurkerDenMP | 100 | 100 | Swarm Mod (multiplayer only) |

**Upgrade reference pattern for morphs:**
```xml
<EffectArray Operation="Multiply" Reference="Abil,UpgradeToLair,InfoArray[0].SectionArray[Abils].DurationArray[Delay]" Value="0.5"/>
<EffectArray Operation="Multiply" Reference="Abil,UpgradeToLair,InfoArray[0].SectionArray[Stats].DurationArray[Delay]" Value="0.5"/>
```

---

## Unit IDs for Structures

| Structure | CUnit ID | Notes |
|---|---|---|
| Hatchery | `Hatchery` | |
| Lair | `Lair` | Morphed from Hatchery |
| Hive | `Hive` | Morphed from Lair |
| Spawning Pool | `SpawningPool` | |
| Baneling Nest | `BanelingNest` | |
| Roach Warren | `RoachWarren` | |
| Hydralisk Den | `HydraliskDen` | |
| Lurker Den | `LurkerDen` | Campaign unit (Build17); covers both Lurker/Impaler paths |
| Infestation Pit | `InfestationPit` | |
| Spire | `Spire` | |
| Greater Spire | `GreaterSpire` | Morphed from Spire |
| Ultralisk Cavern | `UltraliskCavern` | |
| Evolution Chamber | `EvolutionChamber` | |
| Spine Crawler | `SpineCrawler` | |
| Spore Crawler | `SporeCrawler` | |
| Extractor | `Extractor` | |
| Automated Extractor | `AutomatedExtractor` | HotS campaign only |
| Nydus Network | `NydusNetwork` | Built by drone (ZergBuild Build10, 50 s); unlocked by strategic choice |
| Greater Nydus Worm | `GreaterNydusWorm` | Spawned by NydusNetwork via `BuildNydusCanal` and `BuildGreaterNydusWorm` (5 s, 10 s cooldown) |

---

## Common Pitfalls

- **`Unit.BuildTime` does nothing in upgrades** — confirmed by absence in all SC2 campaign data.
- **Command-card cost display requires real ability-command wiring** — the button must point at the producing `CAbilBuild`/`CAbilTrain` InfoArray slot, and the produced unit/button must not hide resources. Manual cost text in `Button/Tooltip` is a fallback only for non-standard commands and should be avoided.
- **`Operation="Multiply"` works** for both `Abil` time and DurationArray references (unlike `CostResource` where it doesn't work).
- **Building morph time** requires two EffectArray entries per morph: one for `SectionArray[Abils]` and one for `SectionArray[Stats]`. Omitting either leaves half the timer unaffected.
- **`UpgradeToLurkerDenMP`** is the multiplayer morph ability — not used in the HotS campaign. Campaign uses ZergBuild Build17 instead.
- **Nydus Worm** has two spawn abilities (`BuildNydusCanal` and `BuildGreaterNydusWorm`). Both must be referenced if you want build time reductions to apply. `BuildNydusCanal` is the usual campaign override target; `BuildGreaterNydusWorm` is 5 s with a 10 s cooldown.
