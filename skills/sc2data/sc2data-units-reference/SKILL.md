---
name: sc2data-units-reference
description: StarCraft II unit catalog reference — editor IDs, races, attributes, and roles for all multiplayer units and structures across Wings of Liberty, Heart of the Swarm, and Legacy of the Void. Also covers campaign-only units and all 18 co-op commanders with their race, hero unit IDs, and signature units. Use when you need to know the correct catalog/Galaxy type ID for a unit (e.g. "SiegeTank", "HighTemplar", "BroodLord"), or when checking a unit's race, classification, expansion of origin, or which commander a unit belongs to. Referenced by sc2data-units-abilities, galaxy-units-and-groups, sc2data-actors-visuals, and sc2data-effects-weapons.
---

## Loading Boundary

- **This sub-skill owns:** SC2 unit catalog reference — editor IDs, races, attributes, roles for multiplayer units, campaign-only units, and 18 co-op commanders
- **Parent root skill (`sc2-catalog-xml`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `sc2data-units-abilities` (CUnit XML authoring), `galaxy-units-and-groups` (Galaxy UnitCreate/GetType), `sc2data-actors-visuals` (actor unit references)

# SC2 Units Reference

## Prerequisite

Load [`sc2-catalog-xml`](../../sc2-catalog-xml/SKILL.md) first for project-wide Catalog XML schema rules (child value elements not raw attributes, ASCII-only, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs), parent inheritance pitfalls, effective-value evidence workflow, localization anchors, and Editor round-trip safety. This sub-skill owns deep schema reference only; project conventions live in the router skill.

This file lists all StarCraft II multiplayer units and structures with their **editor catalog IDs** — the exact strings used in both Galaxy scripting (e.g. `UnitCreate(1, "Marine", ...)`) and XML data (e.g. `<CUnit id="Marine"/>`).

> **Source of truth:** [ShadowDragon Base.SC2Data — UnitData.xml](https://github.com/ShadowDragonSC2/Base.SC2Data/blob/main/GameData/UnitData.xml). When in doubt, verify the exact ID there.

> **Expansion key:** WoL = Wings of Liberty, HotS = Heart of the Swarm, LotV = Legacy of the Void

> **Build slot mapping:** When modifying worker build times via `CAbilBuild` (`TerranBuild`, `ProtossBuild`, `ZergBuild`), the InfoArray slots are numeric (`Build1`, `Build2`, ...) — NOT the structure catalog IDs. See `sc2data-units-abilities` skill for the full verified slot-to-building mapping and standard build times for all three races.

---

## Terran

### Units

| Display Name | Editor ID | Exp | Type | Attributes | Role |
|---|---|---|---|---|---|
| Marine | `Marine` | WoL | Infantry | Light · Biological | Basic ranged infantry |
| Marauder | `Marauder` | WoL | Infantry | Armored · Biological | Heavy anti-armored infantry, slows targets |
| Reaper | `Reaper` | WoL | Infantry | Light · Biological | Fast cliff-jumping raider |
| Ghost | `Ghost` | WoL | Infantry | Light · Biological · Psionic | Cloak, Snipe, Nuke, EMP specialist |
| Hellion | `Hellion` | WoL | Vehicle | Light · Mechanical | Fast ground AoE fire line |
| Siege Tank | `SiegeTank` | WoL | Vehicle | Armored · Mechanical | Tank/Siege mode, long-range AoE siege |
| Siege Tank (Sieged) | `SiegeTankSieged` | WoL | Vehicle | Armored · Mechanical | Siege mode state of Siege Tank |
| Thor | `Thor` | WoL | Mech | Armored · Mechanical · Massive | Heavy assault walker, anti-air splash |
| Medivac | `Medivac` | WoL | Gunship | Armored · Mechanical | Transport + heals biological units |
| Viking (Air) | `Viking` | WoL | Fighter | Light · Mechanical | Air fighter, transforms to ground assault |
| Viking (Ground) | `VikingAssault` | WoL | Assault | Light · Mechanical | Ground state of transforming Viking |
| Banshee | `Banshee` | WoL | Gunship | Light · Mechanical | Cloak-capable anti-ground gunship |
| Raven | `Raven` | WoL | Ship | Light · Mechanical · Psionic | Detector; deploys Auto-Turret |
| Battlecruiser | `Battlecruiser` | WoL | Capital Ship | Armored · Mechanical · Massive · Psionic | Heavy air, Yamato Cannon |
| SCV | `SCV` | WoL | Worker | Armored · Biological · Mechanical | Builder/harvester; can repair |
| Auto-Turret | `AutoTurret` | WoL | Structure | Armored · Mechanical · Structure | Temporary defensive turret deployed by Raven |
| MULE | `MULE` | WoL | Drone | Armored · Mechanical | Orbital Command–summoned harvester |
| Hellbat | `Hellbat` | HotS | Infantry | Biological · Mechanical | Hellion transform; melee-range AoE, healed by Medivac |
| Widow Mine | `WidowMine` | HotS | Mech | Mechanical · Armored | Burrows, fires homing missile on nearby enemies |
| Widow Mine (Burrowed) | `WidowMineBurrowed` | HotS | Mech | Mechanical · Armored | Burrowed/active state of Widow Mine |
| Cyclone | `Cyclone` | LotV | Vehicle | Armored · Mechanical | Fast vehicle with lock-on missile pods |
| Liberator | `Liberator` | LotV | Gunship | Armored · Mechanical | Transforms into stationary anti-ground platform |
| Liberator (AG mode) | `LiberatorAG` | LotV | Gunship | Armored · Mechanical | Defender mode state, precise anti-ground |

### Structures

| Display Name | Editor ID | Exp | Notes |
|---|---|---|---|
| Command Center | `CommandCenter` | WoL | Main base, upgrades to OC or PF |
| Orbital Command | `OrbitalCommand` | WoL | Upgrade of CC: MULE, Scanner, extra supply |
| Planetary Fortress | `PlanetaryFortress` | WoL | Upgrade of CC: immobile, armed, repairs |
| Supply Depot | `SupplyDepot` | WoL | Supply building; can lower to allow unit pass |
| Supply Depot (Lowered) | `SupplyDepotLowered` | WoL | Lowered state of Supply Depot |
| Refinery | `Refinery` | WoL | Gas harvesting building |
| Barracks | `Barracks` | WoL | Produces infantry |
| Factory | `Factory` | WoL | Produces vehicles |
| Starport | `Starport` | WoL | Produces air units |
| Engineering Bay | `EngineeringBay` | WoL | Upgrades infantry weapons/armor |
| Armory | `Armory` | WoL | Upgrades vehicle/ship weapons/armor |
| Fusion Core | `FusionCore` | WoL | Required for Battlecruiser |
| Ghost Academy | `GhostAcademy` | WoL | Enables Ghosts; researches nuke |
| Bunker | `Bunker` | WoL | Garrisonable static defense |
| Missile Turret | `MissileTurret` | WoL | Anti-air detector structure |
| Sensor Tower | `SensorTower` | WoL | Reveals enemy movement through fog |
| Reactor | `Reactor` | WoL | Add-on: doubles production slots |
| Tech Lab | `TechLab` | WoL | Add-on: enables advanced units + upgrades |

---

## Protoss

### Units

| Display Name | Editor ID | Exp | Type | Attributes | Role |
|---|---|---|---|---|---|
| Probe | `Probe` | WoL | Worker | Light · Biological · Psionic | Builder/harvester |
| Zealot | `Zealot` | WoL | Warrior | Light · Biological | Melee unit with Charge |
| Stalker | `Stalker` | WoL | Warrior | Armored · Biological · Psionic | Ranged, Blink teleport |
| Sentry | `Sentry` | WoL | Warrior | Light · Mechanical · Psionic | Support: Force Field, Guardian Shield |
| Immortal | `Immortal` | WoL | Mech | Armored · Mechanical · Psionic | Heavy anti-armored, Hardened Shield |
| Colossus | `Colossus` | WoL | Mech | Armored · Mechanical · Massive · Psionic | Cliff-walking AoE laser walker |
| High Templar | `HighTemplar` | WoL | Warrior | Light · Biological · Psionic | Psychic Storm, Feedback; merges to Archon |
| Dark Templar | `DarkTemplar` | WoL | Warrior | Light · Biological · Psionic | Permanently cloaked melee assassin |
| Archon | `Archon` | WoL | Warrior | Armored · Massive · Psionic | Energy-splash melee, strong shields |
| Observer | `Observer` | WoL | Ship | Light · Mechanical · Psionic | Cloaked detector/scout |
| Phoenix | `Phoenix` | WoL | Fighter | Light · Mechanical · Psionic | Fast air fighter, Graviton Beam |
| Warp Prism | `WarpPrism` | WoL | Ship | Light · Mechanical · Psionic | Transport + mobile Pylon power field |
| Warp Prism (Phasing) | `WarpPrismPhasing` | WoL | Ship | Light · Mechanical · Psionic | Stationary power-field mode |
| Void Ray | `VoidRay` | WoL | Ship | Armored · Mechanical · Psionic | Beam that ramps up damage on same target |
| Carrier | `Carrier` | WoL | Capital Ship | Armored · Mechanical · Massive · Psionic | Launches Interceptors; no direct attack |
| Interceptor | `Interceptor` | WoL | Fighter | Light · Mechanical · Psionic | Auto-spawned by Carrier |
| Mothership | `Mothership` | WoL | Capital Ship | Armored · Mechanical · Massive · Psionic | Ultimate; Mass Recall, Vortex, Cloaks army |
| Mothership Core | `MothershipCore` | HotS | Ship | Armored · Mechanical · Psionic | Base defender; Overcharge, Recall; upgrades to Mothership (removed in LotV) |
| Oracle | `Oracle` | HotS | Ship | Light · Mechanical · Psionic | Harassment/vision; Revelation, Stasis Ward |
| Tempest | `Tempest` | HotS | Capital Ship | Armored · Mechanical · Massive · Psionic | Long-range capital ship, Disintegration |
| Adept | `Adept` | LotV | Warrior | Light · Biological · Psionic | Ground ranged, Psionic Transfer shade |
| Disruptor | `Disruptor` | LotV | Mech | Armored · Mechanical · Psionic | Purification Nova: massive AoE ground burst |
| Disruptor (Nova) | `DisruptorPhased` | LotV | Drone | Armored · Mechanical · Psionic | Rolling Nova ball state |

### Structures

| Display Name | Editor ID | Exp | Notes |
|---|---|---|---|
| Nexus | `Nexus` | WoL | Main base, produces Probes |
| Pylon | `Pylon` | WoL | Supply + power field for structures |
| Assimilator | `Assimilator` | WoL | Gas harvesting building |
| Gateway | `Gateway` | WoL | Produces ground warriors; converts to Warp Gate |
| Warp Gate | `WarpGate` | WoL | Warps-in units anywhere in pylon range |
| Forge | `Forge` | WoL | Upgrades ground weapons/armor/shields |
| Cybernetics Core | `CyberneticsCore` | WoL | Unlocks Stalker, Sentry; air upgrades |
| Twilight Council | `TwilightCouncil` | WoL | Enables Charge, Blink, Resonating Glaives |
| Templar Archives | `TemplarArchive` | WoL | Required for High Templar |
| Dark Shrine | `DarkShrine` | WoL | Required for Dark Templar |
| Photon Cannon | `PhotonCannon` | WoL | Detector, attacks air and ground |
| Robotics Facility | `RoboticsFacility` | WoL | Produces Immortal, Colossus, Observer, WP |
| Robotics Bay | `RoboticsBay` | WoL | Enables Colossus; upgrades Observer/WP |
| Stargate | `Stargate` | WoL | Produces air units |
| Fleet Beacon | `FleetBeacon` | WoL | Enables Carrier/Mothership; air upgrades |
| Shield Battery | `ShieldBattery` | LotV | Recharges shields of nearby units/structures |
| Stasis Ward | `StasisWard` | LotV | Oracle-placed cloaked trap |

---

## Zerg

### Units

| Display Name | Editor ID | Exp | Type | Attributes | Role |
|---|---|---|---|---|---|
| Drone | `Drone` | WoL | Worker | Light · Biological | Builder/harvester; morphs into structures |
| Zergling | `Zergling` | WoL | Infantry | Light · Biological | Fast cheap melee swarm unit |
| Baneling | `Baneling` | WoL | Infantry | Light · Biological | Zergling morph; explodes for AoE acid damage |
| Roach | `Roach` | WoL | Infantry | Armored · Biological | Tough short-range unit with fast burrow regen |
| Hydralisk | `Hydralisk` | WoL | Infantry | Light · Biological | Ranged anti-air/ground attacker |
| Infestor | `Infestor` | WoL | Infantry | Light · Biological · Psionic | Fungal Growth, Infested Terran, Neural Parasite |
| Corruptor | `Corruptor` | WoL | Ship | Light · Biological · Psionic | Anti-air; mutates into Brood Lord |
| Mutalisk | `Mutalisk` | WoL | Ship | Light · Biological | Fast harassment flier with bouncing attack |
| Brood Lord | `BroodLord` | WoL | Ship | Armored · Biological · Massive · Psionic | Aerial siege; rains Broodlings |
| Broodling | `Broodling` | WoL | Infantry | Light · Biological | Short-lived melee unit spawned by Brood Lords |
| Ultralisk | `Ultralisk` | WoL | Infantry | Armored · Biological · Massive · Psionic | Massive melee with Kaiser Blades AoE |
| Queen | `Queen` | WoL | Infantry | Armored · Biological · Psionic | Transfuse, Creep Tumor, Spawn Larva; base defender |
| Overlord | `Overlord` | WoL | Ship | Armored · Biological · Massive · Psionic | Supply provider; upgrades to transport/Overseer |
| Overseer | `Overseer` | WoL | Ship | Armored · Biological · Massive · Psionic | Overlord morph: detector/scouting support |
| Infested Terran | `InfestedTerran` | WoL | Infantry | Light · Biological | Infestor-spawned limited-life attacker |
| Changeling | `Changeling` | WoL | Infantry | Light · Biological | Overseer-spawned spy; mimics enemy units |
| Nydus Worm | `NydusCanal` | WoL | Structure | Armored · Biological · Massive · Structure | Exit point of Nydus Network tunnel |
| Swarm Host | `SwarmHost` | HotS | Infantry | Armored · Biological | Siege unit; burrows and periodically spawns Locusts |
| Swarm Host (Burrowed) | `SwarmHostBurrowed` | HotS | Infantry | Armored · Biological | Active burrowed state spawning Locusts |
| Locust | `Locust` | HotS | Infantry | Light · Biological | Timed-life melee unit spawned by Swarm Host |
| Viper | `Viper` | HotS | Ship | Light · Biological · Psionic | Abduct, Blinding Cloud, Parasitic Bomb aerial support |
| Lurker | `Lurker` | LotV | Infantry | Armored · Biological · Psionic | Hydralisk morph; burrows to attack in a line |
| Lurker (Burrowed) | `LurkerBurrowed` | LotV | Infantry | Armored · Biological · Psionic | Burrowed/active state of Lurker |
| Ravager | `Ravager` | LotV | Infantry | Armored · Biological | Roach morph; artillery with Corrosive Bile |

### Structures

| Display Name | Editor ID | Exp | Notes |
|---|---|---|---|
| Hatchery | `Hatchery` | WoL | Main base (tier 1); spawns Larva |
| Lair | `Lair` | WoL | Hatchery morph (tier 2) |
| Hive | `Hive` | WoL | Lair morph (tier 3) |
| Extractor | `Extractor` | WoL | Gas harvesting building |
| Spawning Pool | `SpawningPool` | WoL | Enables Zerglings; produces Queens |
| Evolution Chamber | `EvolutionChamber` | WoL | Upgrades ground melee/missile/carapace |
| Baneling Nest | `BanelingNest` | WoL | Enables Baneling morph |
| Roach Warren | `RoachWarren` | WoL | Enables Roach; burrow upgrades |
| Hydralisk Den | `HydraliskDen` | WoL | Enables Hydralisk |
| Infestation Pit | `InfestationPit` | WoL | Required for Infestor, Hive |
| Spire | `Spire` | WoL | Enables Mutalisk, Corruptor, Overlord morph |
| Greater Spire | `GreaterSpire` | WoL | Spire morph; enables Brood Lord |
| Ultralisk Cavern | `UltraliskCavern` | WoL | Enables Ultralisk |
| Nydus Network | `NydusNetwork` | WoL | Creates Nydus Canal tunnels anywhere on creep |
| Spine Crawler | `SpineCrawler` | WoL | Ground-only defensive structure; can uproot and move — uprooted form: `SpineCrawlerUprooted` |
| Spore Crawler | `SporeCrawler` | WoL | Anti-air detector structure; can uproot and move — uprooted form: `SporeCrawlerUprooted` |
| Creep Tumor | `CreepTumor` | WoL | Spreads creep; placed by Queen (burrowed) |
| Creep Tumor (Burrowed) | `CreepTumorBurrowed` | WoL | Active spread state |
| Lurker Den | `LurkerDen` | LotV | Enables Lurker morph from Hydralisk |

> **Cost override pitfall — uprooted/burrowed variants:** Spine Crawler and Spore Crawler have separate uprooted CUnit entries (`SpineCrawlerUprooted`, `SporeCrawlerUprooted`). Most burrowed Zerg units also have a distinct CUnit catalog entry. If the variant's inherited cost is higher than the override on the primary unit, SC2 will charge the difference when transitioning. Always override both. If the variant catalog ID is not known, confirm it with the user before writing the override. See `sc2data-units-abilities` skill for the full pitfall table.

---

## Campaign & Co-op Units

These units exist in the editor's data (available as parents or `UnitCreate` targets) but are not present in standard multiplayer. Many originate from the singleplayer campaigns or co-op commanders. Editor IDs are best-effort — always verify against [ShadowDragon Base.SC2Data](https://github.com/ShadowDragonSC2/Base.SC2Data/blob/main/GameData/UnitData.xml) for the exact catalog ID.

> **Campaign key:** WoL = Wings of Liberty, HotS = Heart of the Swarm, LotV = Legacy of the Void, NCO = Nova Covert Ops (co-op), Co-op = Co-op Missions commander unit

### Terran Campaign Units

| Display Name | Editor ID | Campaign | Role |
|---|---|---|---|
| Firebat | `Firebat` | WoL | Short-range AoE flamethrower infantry; classic SC1 unit |
| Medic | `Medic` | WoL | Heals nearby biological units |
| Goliath | `Goliath` | WoL | Ground walker with cannons + anti-air missiles; classic SC1 unit |
| Vulture | `Vulture` | WoL | Fast hover bike; deploys Spider Mines |
| Spider Mine | `SpiderMine` | WoL | Burrowing proximity mine deployed by Vulture |
| Science Vessel | `ScienceVessel` | WoL | Detector; Irradiate, EMP Shockwave, Defensive Matrix |
| Wraith | `Wraith` | WoL | Cloaking fighter, air-to-air and air-to-ground |
| Spectre | `Spectre` | WoL | Ghost alternative; Psionic Lash, Permanent Cloak |
| Diamondback | `Diamondback` | WoL | Hovertank that can attack while moving |
| Predator | `Predator` | WoL | Fast anti-biological mech; Entropic Field AoE |
| Hercules | `Hercules` | WoL | Massive transport dropship |
| Marauder Commando | `MarauderCommando` | WoL | Enhanced Marauder campaign upgrade variant |
| HERC | `Herc` | NCO | Grappling hook infantry; close-range combat specialist |
| Hellbat Ranger | `HellbatRanger` | NCO | Ranged hellbat variant with extended attack range |
| Raven Type-II | `RavenTypeII` | NCO | Enhanced Raven with additional abilities |
| Assault Galleon | `AssaultGalleon` | Co-op | Massive capital ship (Horner co-op commander) |
| Dusk Wings | `DuskWings` | Co-op | Elite banshee mercenary unit |
| Strike Fighter | `StrikeFighter` | WoL/Co-op | Air strike support craft |

### Zerg Campaign Units

| Display Name | Editor ID | Campaign | Role |
|---|---|---|---|
| Brutalisk | `Brutalisk` | HotS | Massive melee beast; boss-level enemy |
| Aberration | `Aberration` | WoL/HotS | Large melee Zerg variant, tough and slow |
| Guardian | `Guardian` | HotS | Classic SC1 Brood War unit; long-range aerial ground attacker |
| Devourer | `Devourer` | HotS | Classic SC1 Brood War unit; anti-air with acid spores |
| Impaler | `Impaler` | HotS | Burrowed Hydralisk evolution; spike melee siege attacker |
| Swarm Queen | `SwarmQueen` | HotS | Kerrigan-era Queen; more aggressive combat role than standard Queen |
| Hunter Killer | `HunterKiller` | HotS | Named elite Hydralisk |
| Torrasque | `Torrasque` | HotS | Named elite Ultralisk; respawns on death |
| Leviathan | `Leviathan` | HotS | Giant Zerg capital ship (mission objective unit) |
| Primal Zergling | `PrimalZergling` | HotS | Zerus primal zerg variant |
| Primal Roach | `PrimalRoach` | HotS | Zerus primal zerg variant |
| Primal Hydralisk | `PrimalHydralisk` | HotS | Zerus primal zerg variant |
| Primal Mutalisk | `PrimalMutalisk` | HotS | Zerus primal zerg variant |
| Tyrannozor | `Tyrannozor` | HotS | Enormous primal zerg boss creature |
| Raptor | `Raptor` | HotS | Zergling evolution: jumps to higher ground |
| Swarmling | `Swarmling` | HotS | Zergling evolution: spawns three at once |
| Infested Terran (campaign) | `InfestedTerranCampaign` | WoL/HotS | Campaign-version Infested Terran with extended lifespan |

### Protoss Campaign Units

| Display Name | Editor ID | Campaign | Role |
|---|---|---|---|
| Dragoon | `Dragoon` | LotV | Classic SC1 unit; ranged ground walker |
| Dark Archon | `DarkArchon` | LotV | Classic SC1 unit; Maelstrom, Feedback, Mind Control |
| Scout | `Scout` | LotV | Classic SC1 fighter; attacks air and ground |
| Corsair | `Corsair` | LotV | Classic SC1 unit; Disruption Web AoE |
| Arbiter | `Arbiter` | LotV | Classic SC1 unit; cloaks nearby units, Stasis Field, Recall |
| Reaver | `Reaver` | LotV | Classic SC1 unit; launches Scarabs for massive single-hit ground AoE |
| Annihilator | `Annihilator` | LotV/Co-op | Tal'darim Immortal variant; stronger attack vs light |
| Wrathwalker | `Wrathwalker` | LotV/Co-op | Massive walker; sustained beam attack |
| Ascendant | `Ascendant` | LotV/Co-op | Tal'darim High Templar; Psionic Orb, Repeatedly-use HOTS Psionic Transfer |
| Vanguard | `Vanguard` | LotV | Protoss Zealot evolution; AoE beam weapon |
| Centurion | `Centurion` | LotV | Protoss Dark Templar evolution; charges into combat |
| Destroyer | `Destroyer` | LotV | Tal'darim Void Ray variant with Void Slash wave |
| Energizer | `Energizer` | Co-op | Fenix co-op; phased support unit, powers structures remotely |
| Slayer | `Slayer` | Co-op | Alarak co-op; stealthed Dark Templar variant |
| Supplicant | `Supplicant` | Co-op | Alarak co-op; sacrifices shields for damage |
| Havoc | `Havoc` | Co-op | Alarak co-op; buffs nearby units with Target Lock |
| Sentinel | `Sentinel` | LotV/Co-op | Artanis co-op; Zealot variant with Shield Overcharge |
| Corsair (Mirage) | `Mirage` | Co-op | Fenix co-op; enhanced Corsair variant |
| Interdictor | `Interdictor` | Co-op | Karax co-op carrier; spawns defensive fighters |
| Conservator | `Conservator` | Co-op | Karax co-op; armed static defense variant |
| Avenger | `Avenger` | Co-op | Alarak co-op; gains power from nearby deaths |
| Blood Hunter | `BloodHunter` | Co-op | Alarak co-op; heavily armored melee |
| Shadow Guard | `ShadowGuard` | Co-op | Nova co-op; Protoss-tech Ghost variant |
| Void Templar | `VoidTemplar` | LotV | Tal'darim zealot evolution with life-drain |

---

## Co-op Commanders

All 18 Co-op Missions commanders, grouped by race. Hero unit IDs are best-effort — verify in the relevant co-op mod's GameData XML if needed. Most co-op data lives under `Mods/CoopCampaign.SC2Mod`.

> **Tip:** Co-op unit IDs tagged "Co-op" in the Campaign tables above belong to the commanders listed here, matched by the Commander column.

### Terran Commanders

| Commander | Hero Unit ID | Style / Signature | Notable Unique Units |
|---|---|---|---|
| **Jim Raynor** | `RaynorJim` | Durable all-rounder; Hyperion battlecruiser calldown; Bunker-heavy macro | Vultures, Goliaths, Science Vessels, Medics, upgraded MMM |
| **Rory Swann** | `SwannRory` | Mechanical focus; free mech repair; Hercules calldown | Goliaths, Wraiths, Diamondbacks, Science Vessels; Thor upgrades |
| **Nova Terra** | `NovaTerra` | Covert strike force; all units permanently cloaked; Nuke/Airstrike calldowns | Spectres, Siege Breakers, Ravens, Raven Type-II |
| **Mira Han & Matt Horner** | `HanMira` / `HornerMatt` | Dual-hero; Han fields mercenary ground troops; Horner builds a capital ship fleet | Assault Galleons, Dusk Wings, War Pigs, Spartan Company and other mercenary squads |
| **Tychus Findlay** | `TychusFindlay` | Squad of unique outlaw heroes (up to 5); each hero has distinct abilities | Sirius (Goliath), Nux (Thor), Vega (Medivac), Crooked Sam (Viking), Cannonball (Siege Tank) |
| **Arcturus Mengsk** | `MengskArcturus` | Imperial Guard; calls in Royal Guard elite units; Dominion Trooper fodder army | Royal Guard units, Dominion troopers/assault troopers as disposable front line |

### Zerg Commanders

| Commander | Hero Unit ID | Style / Signature | Notable Unique Units |
|---|---|---|---|
| **Sarah Kerrigan** | `KerriganSarahZerg` | Hero-centric; powerful melee hero; can morph to primal form; Leviathan calldown | Standard Zerg army enhanced by hero ability chain |
| **Zagara** | `ZagaraZerg` | Swarm mass production; Hunter Killers, banelings, and Scourge; Feral Frenzy | Hunter Killers, Aberrations, Scourge, Baneling Hunter drops |
| **Abathur** | `AbathurZerg` | Evolution/mutation focus; Toxic Nest; Symbiote buff on allied units | Brutalisks, Symbiote-buffed allies, Swarm Host Locusts |
| **Dehaka** | `DehakaZerg` | Primal Zerg; Essence collection grants permanent upgrades; large solo hero + primal pack | Primal Zerglings, Primal Roaches, Primal Hydralisks, Primal Guardians, Tyrannozors |
| **Alexei Stukov** | `StukovAlexei` | Infested Terran theme; infests enemy structures; infested building construction | Infested Marines, Infested Siege Tanks, Infested SCVs, Infested Bunkers, Infested Liberators |
| **Egon Stetmann** | `StetmannEgon` | Mecha Zerg (robotic skins); Gary (mecha Ultralisk hero); Stetellite power grid for bonuses | Mecha Zergling, Mecha Hydralisk, Mecha Roach, Mecha Lurker, Mecha Corruptor, Mecha Overlord |

### Protoss Commanders

| Commander | Hero Unit ID | Style / Signature | Notable Unique Units |
|---|---|---|---|
| **Artanis** | `ArtanisProtoss` | Guardian Shell passive (survives one-hit kills); Spear of Adun solar lance; classic Protoss | Dragoons, Scouts, Corsairs, Reavers via Spear of Adun orbital strikes |
| **Vorazun** | `VorazunProtoss` | Dark Templar / shadow ops; Time Stop ultimate; all units permanently cloaked | Dark Templar, Dark Archon, Corsairs, Shadow Guard |
| **Karax** | `KaraxProtoss` | Mechanical army + Spear of Adun support; Repair Beam; Photon Overcharge | Arbiters, Carriers, Spear of Adun calldowns; Conservators, Interdictor |
| **Alarak** | `AlarakProtoss` | Tal'darim elite; Death Fleet calldown; hero grows stronger from allied deaths | Ascendants, Slayers, Supplicants, Havoc, Avengers, Blood Hunters |
| **Fenix** | `FenixProtoss` | Champion suit with 6 swappable loadouts (each a different unit type); classic Protoss army | Dragoons, Scouts, Carriers, Reavers, Immortals, Adepts — depending on active suit; Mirage |
| **Zeratul** | `ZeratulProtoss` | Artifact / void shard powers; passive army-wide buffs from collected fragments | Standard Protoss army empowered by artifact powers; Void Templar units |
| **Zagara** (Zerg) | *(see Zerg above)* | — | — |

---

## Common Neutral/Critter Units

| Display Name | Editor ID | Notes |
|---|---|---|
| Mineral Field (small) | `MineralField450` | 450-mineral patch |
| Mineral Field (large) | `MineralField750` | 750-mineral patch |
| Vespene Geyser | `VespeneGeyser` | Raw geyser before refinery placed |
| Xel'Naga Tower | `XelNagaTower` | Vision tower, activates when unit stands on it |
| Destructible Rock | `DestructibleRock6x6` | Common blocking rock (many size variants) |

---

## Working with Unit IDs

### In Galaxy script

```galaxy
// Unit type ID is always the exact catalog ID string
unit lv_marine = UnitCreate(1, "Marine", c_unitCreateIgnorePlacement, 1, lv_point, 270.0);
bool lv_isZealot = (UnitGetType(lv_unit) == "Zealot");

// Siege tank has two IDs — check both for unsieged + sieged  
bool lv_isTank = (UnitGetType(lv_unit) == "SiegeTank") || (UnitGetType(lv_unit) == "SiegeTankSieged");
```

### In XML data

```xml
<!-- The id attribute must match the catalog entry exactly -->
<CUnit id="MyCustomUnit" parent="Marine">
    ...
</CUnit>

<!-- Referencing a Blizzard-defined unit as parent -->
<CUnit id="StrongerZergling" parent="Zergling">
    <LifeMax value="75"/>
</CUnit>
```

### Transform/morph ID pairs

Some units have two IDs for their two modes — always handle both:

| Unit | Normal ID | Alternate ID |
|---|---|---|
| Siege Tank | `SiegeTank` | `SiegeTankSieged` |
| Viking | `Viking` | `VikingAssault` |
| Hellion | `Hellion` | `Hellbat` |
| Warp Prism | `WarpPrism` | `WarpPrismPhasing` |
| Gateway | `Gateway` | `WarpGate` |
| Widow Mine | `WidowMine` | `WidowMineBurrowed` |
| Lurker | `Lurker` | `LurkerBurrowed` |
| Swarm Host | `SwarmHost` | `SwarmHostBurrowed` |
| Disruptor | `Disruptor` | `DisruptorPhased` |
| Supply Depot | `SupplyDepot` | `SupplyDepotLowered` |

---

## Unit Attributes Quick Reference

These are the `Attributes` values used in XML and the `c_unitAttribute*` constants in Galaxy.

| Attribute | Typical units | Galaxy constant |
|---|---|---|
| Light | Marines, Zerglings, most basic units | `c_unitAttributeLight` |
| Armored | Roaches, Marauders, Stalkers | `c_unitAttributeArmored` |
| Biological | All organic units (Terran infantry, all Zerg, most Protoss warriors) | `c_unitAttributeBiological` |
| Mechanical | All Terran vehicles/ships, Protoss mechs | `c_unitAttributeMechanical` |
| Massive | Ultralisks, Thors, Carriers, Tempests, Brood Lords | `c_unitAttributeMassive` |
| Psionic | Ghosts, High/Dark Templar, Overseers, Infestors, many Protoss | `c_unitAttributePsionic` |
| Structure | All buildings | `c_unitAttributeStructure` |
| Hover | Hellion (moves over some terrain) | `c_unitAttributeHover` |
