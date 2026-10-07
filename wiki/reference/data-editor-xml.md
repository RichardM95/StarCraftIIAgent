# DataEditorXML — Field Name Reference

This folder contains XML dumps extracted from the SC2 Data Editor. Use these files to look up correct field names, capitalization, attribute names, and existing IDs before writing any XML for your custom campaign mod.

> **Rule:** Grep these files before writing any XML. Do not guess field names — they are case-sensitive and undocumented outside the editor.

If you need catalogs from inactive dependencies (such as Nova Covert Ops, Co-op Commanders, or custom extensions), you can export matching `.txt` XML dumps from the SC2 Data Editor into `DataEditorXML/` or a custom reference folder. See [`unit-extraction-from-inactive-xml.md`](unit-extraction-from-inactive-xml.md).

For raw component-form reference data, use [`DataEditorXML/SC2GameDataComponents/`](../../DataEditorXML/SC2GameDataComponents/README.md). That snapshot preserves component paths and contains the available `Base.SC2Data/GameData/`, `enUS.SC2Data/`, and `zhCN.SC2Data/` content from 26 official and partner `.SC2Mod` / `.SC2Campaign` folders. Treat it as reference evidence, not proof that a component is an active dependency.

---

## What These Files Are

Each `.txt` file is a raw XML dump from a specific SC2 data source (mod or campaign layer). Files contain `<Catalog>` blocks with data entries (`CUpgrade`, `CBehaviorBuff`, `CEffectDamage`, etc.) showing exactly how Blizzard named fields, how they structured arrays, and what values they used.

You may add your own working-example `.txt` dumps (e.g. a proven upgrade pattern) beside the Blizzard catalogs — document them in the table below.

For graph-style lookup across reference exports, inactive sources, the current project, and resolved dependencies, run:

```powershell
python tools/build-sc2-catalog-graph.py --sqlite-only
```

The command above refreshes `catalog.sqlite` only. Omit `--sqlite-only` when the complete `graph.json`, `graph.graphml`, duplicate/unresolved-reference audits, one-object Markdown summaries, and graphify ingest pages are needed.

Use the local query tool for token-efficient agent lookup:

```powershell
python tools/sc2-catalog-query.py stats
python tools/sc2-catalog-query.py find Marine --source-class local_mod --limit 20
python tools/sc2-catalog-query.py show Unit:Marine --limit 30 --depth 2
python tools/sc2-catalog-query.py providers Button:Marine
python tools/sc2-catalog-query.py unresolved --contains My --limit 40
python tools/sc2-catalog-query.py path Abil:MyGatewayTrain Unit:MyCommando --max-depth 3
python tools/sc2-catalog-query.py unit-chain Unit:Marine --source-class local_mod
python tools/sc2-catalog-query.py ability-chain Abil:MyGatewayTrain --source-class local_mod
python tools/sc2-catalog-query.py actor-chain Unit:Marine --source-class local_mod
python tools/sc2-catalog-query.py production-chain Unit:MyCommando --source-class local_mod
```

Prefer this deterministic query tool over loading raw XML dumps or graphify reports into the model context. It reads `catalog.sqlite` when available and falls back to `graph.json`, returning only the scoped node, edge, provider, or unresolved-reference information requested.

The top-level `.txt` dumps and component snapshot overlap: 36 of the 156 top-level dumps are byte-identical to snapshot XML files (8,155,558 bytes, measured 2026-09-24). This is an exact-file count, not a measure of shared catalog objects. Keep the graph as the first lookup for IDs and relationships; query raw component examples only when a matching implementation, component provenance, or English/Chinese string is needed:

```powershell
python tools/sc2-reference-query.py components --source CM
python tools/sc2-reference-query.py find 'id="Marine"' --area gamedata --family Unit --component liberty --limit 20
python tools/sc2-reference-query.py find 'Unit/Name/Marine' --area zhcn --component liberty --limit 10
python tools/sc2-reference-query.py object Unit:Marine --component liberty --max-chars 6000
```

Use the returned component path and line number to inspect a small fragment of the raw file; `object` returns the exact XML object with its component path. The snapshot is outside the catalog graph and does not establish active dependency or effective values. Top-level TXT definitions in the graph are marked `reference_export`; only resolved component dependencies are marked `active_component_dependency`.

Use the curated chain commands before raw grep when implementing or debugging a unit:

- `unit-chain`: unit abilities, weapons, behaviors, command buttons, production abilities, and listening actors.
- `ability-chain`: producer units, produced/referenced units, buttons, requirements, effects, and validators.
- `actor-chain`: actor event targets, models, sounds, and created/messaged actors for an actor or unit.
- `production-chain`: produced unit or train/build ability with production buttons and requirements grouped together.

Do not run graphify over raw catalog XML dumps during normal implementation work. Broad graphify/Gemini ingestion of the generated catalog pages has already proven too noisy and quota-heavy for this corpus. Treat the deterministic graph and `sc2-catalog-query.py` as the primary catalog navigation layer; reserve graphify for the smaller repo/wiki graph or for tightly scoped experiments.

## Included Dump Coverage

The active dependency dump set now includes broader Button, Sound, Requirement Node, Texture, Game UI Data, Data Collection, Core campaign metadata, Void Campaign Story, and Co-op commander metadata files beyond the original unit/effect/actor/ability-focused set. Use `tools/build-sc2-catalog-graph.py` for complete coverage instead of relying only on the hand-written table below.

The separate `SC2GameDataComponents/` snapshot adds raw GameData and English/Chinese localization trees for official and partner component packages. Its component hierarchy also covers packages and files absent from the curated `.txt` dump index below.

High-value additions:

- Active `* Buttons.txt` files for Core, Liberty, Swarm, and Void layers.
- Active `* Sounds.txt` files for Core, Liberty, Swarm, Void, and Void Campaign Story layers.
- Additional `* Requirement Nodes.txt` files for Core, Liberty Mod/Campaign, and Swarm Mod.
- Active `* Textures.txt` files for Liberty, Swarm Campaign, Void Campaign, and Void Campaign Story.
- Active `* Game UI Data.txt`, `* Data Collection.txt`, Core campaign maps/objectives, and Void Campaign Story army/map/bank/objective/location files.
- `Coop Commanders.txt` for identifying commander-only systems to exclude, not as an active dependency source.

## External Data Docs

Use local dumps for exact XML. Use external data docs for field meaning:

- [Talv Data File List](https://mapster.talv.space/data/files.html) routes by header/catalog family (`Unit.h`, `Abil.h`, `Behavior.h`, `Effect.h`, `Actor.h`, `Requirement.h`, `Weapon.h`, etc.).
- [Talv Data Class List](https://mapster.talv.space/data/annotated.html) routes by catalog class such as `CUnit`, `CAbilTrain`, `CAbilEffect`, `CBehaviorBuff`, `CEffectDamage`, `CRequirement*`, and `CActorUnit`.
- [sc2-gamedata-documentation](https://github.com/chansey97/sc2-gamedata-documentation/tree/master) is the upstream/offline CHM source for these data-structure docs.

Important boundary: the external docs explain what fields mean, but they do not replace grep of `DataEditorXML/` for capitalization, array index spelling, inherited overrides, or Blizzard examples.

---

## File Index by Source

### Core (base game defaults — all races/mods)
| File | Contents |
|---|---|
| `Core Units.txt` | Default `CUnit*` field schemas |
| `Core Abilities.txt` | Default `CAbil*` field schemas and flags |
| `Core Actors.txt` | Default actor field schemas |
| `Core Behaviors.txt` | Default `CBehavior*` field schemas |
| `Core Models.txt` | Default model field schemas and base model IDs |
| `Core Validators.txt` | Default validator field schemas |

### Liberty Mod (WoL base mod)
| File | Contents |
|---|---|
| `Liberty Mod Units.txt` | WoL mod units |
| `Liberty Mod Abilities.txt` | WoL mod abilities |
| `Liberty Mod Actors.txt` | WoL mod actors |
| `Liberty Mod Behaviors.txt` | WoL mod behaviors |
| `Liberty Mod Effects.txt` | WoL mod effects |
| `Liberty Mod Footprints.txt` | WoL mod footprints — primary reference for build placement, creep checks, contour shapes, and pathing layers |
| `Liberty Mod Models.txt` | WoL mod models |
| `Liberty Mod Movers.txt` | WoL mod movers |
| `Liberty Mod Requirements.txt` | WoL mod requirements |
| `Liberty Mod Turrets.txt` | WoL mod turrets |
| `Liberty Mod Upgrades.txt` | WoL mod upgrades |
| `Liberty Mod Validators.txt` | WoL mod validators |
| `Liberty Mod Weapons.txt` | WoL mod weapons |
| `Liberty Tactical AI.txt` | WoL tactical AI data |

### Liberty Campaign (Wings of Liberty campaign layer)
| File | Contents |
|---|---|
| `Liberty Campaign Abilities.txt` | WoL campaign abilities |
| `Liberty Campaign Actors.txt` | WoL campaign actors |
| `Liberty Campaign Attach Methods.txt` | WoL campaign attach methods |
| `Liberty Campaign Behaviors.txt` | WoL campaign behaviors |
| `Liberty Campaign Effects.txt` | WoL campaign effects |
| `Liberty Campaign Footprints.txt` | WoL campaign footprints and campaign-only placement/pathing examples |
| `Liberty Campaign Models.txt` | WoL campaign models |
| `Liberty Campaign Movers.txt` | WoL campaign movers |
| `Liberty Campaign Requirements.txt` | WoL campaign requirements |
| `Liberty Campaign Tactical AI.txt` | WoL campaign tactical AI |
| `Liberty Campaign Turrets.txt` | WoL campaign turrets |
| `Liberty Campaign Units.txt` | WoL campaign units |
| `Liberty Campaign Upgrades.txt` | WoL campaign upgrades — **key reference for upgrade patterns** |
| `Liberty Campaign Validators.txt` | WoL campaign validators |
| `Liberty Campaign Weapons.txt` | WoL campaign weapons |

### Swarm Mod (HotS base mod)
| File | Contents |
|---|---|
| `Swarm Mod Abilities.txt` | HotS mod abilities |
| `Swarm Mod Actors.txt` | HotS mod actors |
| `Swarm Mod Behaviors.txt` | HotS mod behaviors — check here for existing Zerg behavior IDs |
| `Swarm Mod Effects.txt` | HotS mod effects |
| `Swarm Mod Movers.txt` | HotS mod movers |
| `Swarm Mod Requirements.txt` | HotS mod requirements |
| `Swarm Mod Turrets.txt` | HotS mod turrets |
| `Swarm Mod Units.txt` | HotS mod units |
| `Swarm Mod Upgrades.txt` | HotS mod upgrades |
| `Swarm Mod Validators.txt` | HotS mod validators |
| `Swarm Mod Weapons.txt` | HotS mod weapons |

### Swarm Campaign (Heart of the Swarm campaign layer)
| File | Contents |
|---|---|
| `Swarm Campaign Abilities.txt` | HotS campaign abilities — morph abilities, train abilities, etc. |
| `Swarm Campaign Actors.txt` | HotS campaign actors |
| `Swarm Campaign Attach Methods.txt` | HotS campaign attach methods |
| `Swarm Campaign Behaviors.txt` | HotS campaign behaviors — strain behaviors, timed effects |
| `Swarm Campaign Effects.txt` | HotS campaign effects — damage amounts, search areas, apply behaviors |
| `Swarm Campaign Footprints.txt` | HotS campaign footprints, including creep-source and campaign structure footprints |
| `Swarm Campaign Locations.txt` | Campaign location data |
| `Swarm Campaign Maps.txt` | Campaign map metadata |
| `Swarm Campaign Models.txt` | HotS campaign models |
| `Swarm Campaign Movers.txt` | HotS campaign movers |
| `Swarm Campaign Objectives.txt` | Mission objective definitions |
| `Swarm Campaign Requirements.txt` | HotS campaign requirements — **check here for existing CRequirement IDs to reuse** |
| `Swarm Campaign Requirement Nodes.txt` | HotS campaign requirement nodes (e.g. leviathan upgrade mechanic) |
| `Swarm Campaign Story Army Units.txt` | Story-mode army unit entries |
| `Swarm Campaign Story Bank Conditions.txt` | Story-mode bank conditions |
| `Swarm Campaign Story Locations.txt` | Story-mode location data |
| `Swarm Campaign Story Map Data.txt` | Story-mode map data |
| `Swarm Campaign Story Objectives.txt` | Story-mode objectives |
| `Swarm Campaign Tactical AI.txt` | HotS campaign tactical AI |
| `Swarm Campaign Turrets.txt` | HotS campaign turrets |
| `Swarm Campaign Units.txt` | HotS campaign units — strain IDs, unit field definitions |
| `Swarm Campaign Upgrades.txt` | HotS campaign upgrades — **most important file; existing HotS talent upgrade XML** |
| `Swarm Campaign Validators.txt` | HotS campaign validators |
| `Swarm Campaign Weapons.txt` | HotS campaign weapons — weapon IDs, damage fields, attack speed |

### Swarm Story (HotS story/cutscene layer)
| File | Contents |
|---|---|
| `Swarm Story Units.txt` | Story unit definitions |

### Void Mod (LotV base mod)
| File | Contents |
|---|---|
| `Void Mod Abilities.txt` | LotV mod abilities |
| `Void Mod Actors.txt` | LotV mod actors |
| `Void Mod Behaviors.txt` | LotV mod behaviors — contains `SourceIsNotStationary` and other reusable validators |
| `Void Mod Effects.txt` | LotV mod effects |
| `Void Mod Footprints.txt` | LotV mod footprints and later dependency overrides |
| `Void Mod Movers.txt` | LotV mod movers |
| `Void Mod Requirements.txt` | LotV mod requirements |
| `Void Mod Turrets.txt` | LotV mod turrets |
| `Void Mod Units.txt` | LotV mod units |
| `Void Mod Upgrades.txt` | LotV mod upgrades |
| `Void Mod Validators.txt` | LotV mod validators — check here for pre-existing validators before redefining |
| `Void Mod Weapons.txt` | LotV mod weapons |

### Void Campaign (Legacy of the Void campaign layer)
| File | Contents |
|---|---|
| `Void Campaign Abilities.txt` | LotV campaign abilities |
| `Void Campaign Actors.txt` | LotV campaign actors |
| `Void Campaign Army Categories.txt` | LotV army panel category definitions |
| `Void Campaign Army Units.txt` | LotV army panel unit entries and campaign unlock metadata |
| `Void Campaign Attach Methods.txt` | LotV campaign attach methods |
| `Void Campaign Bank Conditions.txt` | LotV campaign bank condition definitions |
| `Void Campaign Behaviors.txt` | LotV campaign behaviors |
| `Void Campaign Effects.txt` | LotV campaign effects |
| `Void Campaign Footprints.txt` | LotV campaign footprints and mission-specific placement/pathing examples |
| `Void Campaign Locations.txt` | LotV campaign location data |
| `Void Campaign Maps.txt` | LotV campaign map metadata |
| `Void Campaign Models.txt` | LotV campaign models |
| `Void Campaign Movers.txt` | LotV campaign movers |
| `Void Campaign Objectives.txt` | LotV campaign objective definitions |
| `Void Campaign Requirements.txt` | LotV campaign requirements |
| `Void Campaign Turrets.txt` | LotV campaign turrets |
| `Void Campaign Units.txt` | LotV campaign units |
| `Void Campaign Weapons.txt` | LotV campaign weapons |

---

## How to Use

1. **Finding an existing ID** — grep the relevant source file. Example: to find how `HotSAdrenalGlands` is defined, grep `Swarm Campaign Upgrades.txt`.
2. **Checking field names** — grep the type file. Example: to find the correct attribute name for weapon range on `CWeaponLegacy`, grep `Swarm Campaign Weapons.txt` or `Swarm Mod Weapons.txt`.
3. **Checking array index names** — look at existing entries. Example: `InfoArray[Train2]` index names come from `Swarm Campaign Abilities.txt`.
4. **Finding pre-existing validators/requirements** — check `Void Mod Validators.txt` and `Swarm Campaign Requirements.txt` before creating new ones.
5. **Confirming `EffectArray` reference strings** — grep `Swarm Campaign Upgrades.txt` for `Reference=` to see the exact path format (`Weapon,WeaponID,FieldName`, `Abil,AbilID,InfoArray[Slot].Field`, etc.).
6. **Checking footprint/placement behavior** — grep the new `* Footprints.txt` files before creating or overriding `Footprint` / `PlacementFootprint` values. `Liberty Mod Footprints.txt` contains key baseline examples such as `Footprint2x2IgnoreCreepContour`, `Footprint3x3IgnoreCreepContour`, `Footprint5x5DropOff`, and capped geyser footprints.
7. **Checking LotV campaign shell data** — use `Void Campaign Army Units.txt`, `Void Campaign Army Categories.txt`, `Void Campaign Bank Conditions.txt`, `Void Campaign Maps.txt`, `Void Campaign Locations.txt`, and `Void Campaign Objectives.txt` for War Council, mission, and persistence-adjacent metadata.
8. **Checking model references** — grep `Core Models.txt`, `Liberty Campaign Models.txt`, `Liberty Mod Models.txt`, `Swarm Campaign Models.txt`, or `Void Campaign Models.txt` before copying actor/model IDs.
9. **Checking inactive model/sound support** — when a chosen unit comes from `XMLFromDependenciesWeDontUse/`, follow actors into that source's `Models.txt` and `Sounds.txt` exports. Copy only model/sound IDs referenced by the final actor chain; skip commander voice, cutscene, prestige, mutator, top-bar, and unrelated UI sounds/models.

---

## Units catalog — practical semantics

Use this section together with grep of `Core Units.txt`, `Swarm Mod Units.txt`, or `Swarm Campaign Units.txt` for **exact XML names**. The dumps show fields; these bullets capture behavior that is easy to miss.

- **32 abilities per unit** — `AbilArray` is capped at 32. Abilities on a morph **destination** also count toward the **source** unit’s cap.
- **Attack / Move / Warpable** — Without **Attack**, weapons do not fire. Without **Move**, the unit cannot move. **Warpable** is required for warp-in from a power field. Abilities can sit in `AbilArray` without a command-card button and still be used via **Issue Order** or spawn/create effects.
- **Spawn behaviors** — Default unit behaviors apply on birth and **cannot** be relocated with **Transfer Behavior** (use apply/remove or duplicate definitions if you need mobility between units).
- **Build time on the unit** — The unit’s build-time fields are consumed by **CAbilBuild / Train / Morph** for timing; always confirm the **ability** as well — it is not the only place timing may be overridden.
- **Acceleration vs deceleration** — `1000` acceleration is effectively instant; `0` means immobile. If **Deceleration** is `0`, the engine copies **Acceleration** once; layered dependencies can leave Deceleration stale vs a later Acceleration change (odd turning on multi-patch units).
- **Death time** — `DeathTime = -1` keeps the unit reference alive for actors/long tail effects; many such units hurt performance. Long positive death times can desync warp-train / “dead while building” actor cleanup unless the actor handles unit death explicitly.
- **Tech Alias + requirements** — Community reports (circa **patch 5.0+**) that **Tech Alias** lookups from **Requirement / Validator** can fail for **custom** unit variants (aliases not grouping forms as expected). Treat Tech Alias as fragile for custom unit variants; prefer explicit unit lists or in-game verification.
- **Weapons** — A usable **Attack** ability is required for **Weapons** to fire. With **Linked Cooldown**, the **lowest weapon index** (closest to 0) is favored.
