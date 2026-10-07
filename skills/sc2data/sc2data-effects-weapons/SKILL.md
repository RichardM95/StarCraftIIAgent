---
name: sc2data-effects-weapons
description: SC2 Data Editor — Effects, Weapons, Upgrades, and the damage chain in XML. Use when creating or modifying CEffect* (damage, search, apply behavior, launch missile, set), CWeapon, CUpgrade, or the full chain from weapon through to damage application. Also covers TargetFind, TargetSort, and Footprints. Always consult the catalogsData.xsd schema for exact fields and structure — do not assume unsupported fields exist. Do not use for actors/visuals (sc2data-actors-visuals) or unit/ability containers (sc2data-units-abilities).
---

## Loading Boundary

- **This sub-skill owns:** CEffect*, CWeapon, CUpgrade, the damage chain, TargetFind, TargetSort, and Footprints XML schema
- **Parent root skill (`sc2-catalog-xml`) owns:** project conventions, schema/syntax rules, source-of-truth, naming prefixes
- **Sibling sub-skills own:** `sc2data-actors-visuals` (actors presenting effects), `sc2data-units-abilities` (unit/ability containers), `sc2data-behaviors-validators` (behaviors applied by effects)

# SC2 Data Editor – Effects & Weapons

## Prerequisite

Load [`sc2-catalog-xml`](../../sc2-catalog-xml/SKILL.md) first for project-wide Catalog XML schema rules (child value elements not raw attributes, ASCII-only, no `AbilAutoCmd`, no `CBehaviorBuff.InitEffect`, no comment-only catalogs), parent inheritance pitfalls, effective-value evidence workflow, localization anchors, and Editor round-trip safety. This sub-skill owns deep schema reference only; project conventions live in the router skill.

Effects and weapons define **how game logic executes**: what damage is dealt, what behaviors are applied, what searches are performed, and what units are spawned. The full chain from a weapon or ability fires down through effect sets and terminates in atomic effects.

## Key References

| Resource | URL |
|---|---|
| Data Editor Introduction | https://s2editor-guides.readthedocs.io/New_Tutorials/04_Data_Editor/058_Data_Editor_Introduction/ |
| SC2Mapster wiki | https://sc2mapster.wiki.gg/ |
| Effects (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Effects |
| Targets for Effects (wiki) | https://sc2mapster.wiki.gg/wiki/Targets_for_Effects |
| Weapons (wiki) | https://sc2mapster.wiki.gg/wiki/Data/Weapons |
| SC2Mapster mkdocs reference | https://sc2mapster.github.io/mkdocs/galaxy/ |
| ShadowDragon Base.SC2Data (real GameData XML reference) | https://github.com/ShadowDragonSC2/Base.SC2Data/tree/main/GameData |
| **Source of Truth: CatalogsData XSD Schema** | https://github.com/ShadowDragonSC2/Base.SC2Data/raw/refs/heads/main/.vscode/schemas/catalogsData.xsd — Always consult this for exact fields, attributes, and structure of effects, weapons, and upgrades. Do not assume fields exist; verify against the schema. |
| **Recommended VS Code Extension** | Red Hat XML (redhat.vscode-xml) — Install this extension for XML validation, auto-completion, and error detection using the catalogsData.xsd schema. Configure it in .vscode/settings.json for automatic validation.

## XML Schema Error Check and Fix Workflow

When editing SC2 data XML, always run this loop until diagnostics are clean:

1. Validate with Red Hat XML diagnostics (Problems panel).
2. For each error, identify whether it is an invalid element, invalid attribute, invalid enum value, or invalid field path/array index.
3. Verify the exact allowed structure in `catalogsData.xsd` before changing anything.
4. Fix the XML by aligning to schema-supported fields only; remove guessed or unsupported fields.
5. Re-validate and repeat until no schema errors remain.

If a user asks to fix XML errors, perform this end-to-end workflow rather than only describing it.

---

> **File placement:** When creating effects for a new unit or ability, put them in the unit's own self-contained XML file (`GameData/Faction/UnitName/UnitName.xml`), not in a monolithic `EffectData.xml`. Register the file via `<Catalog path="..."/>` in `GameData.xml`. See the sc2data-units-abilities skill for the full file template.

## Effect Chain Architecture

```
CWeapon
  └─ Effect ──► CEffectSet
                  ├─► CEffectDamage             (subtract HP)
                  ├─► CEffectApplyBehavior      (add buff/debuff)
                  ├─► CEffectCreateUnit         (spawn unit)
                  ├─► CEffectSearch / EnumArea  (AoE spread)
                  │     └─► CEffectDamage
                  └─► CEffectLaunchMissile ──► CEffectDamage
```

An ability or weapon fires a **single root effect**. That root is almost always a `CEffectSet` which chains multiple phases.

---

## Weapons (`WeaponData.xml`)

File: `Base.SC2Data/GameData/WeaponData.xml`

```xml
<CWeapon id="MyWeapon">
    <EditorCategories value="Race:Terran"/>
    <DisplayEffect value="MyWeaponDamage"/>     <!-- effect shown in tooltip for damage display -->
    <Effect value="MyWeaponEffect"/>            <!-- root effect to fire on attack -->
    <Range value="5"/>                          <!-- attack range -->
    <Period value="0.8608"/>                    <!-- attack period (seconds between attacks) -->
    <DamagePoint value="0.0"/>                  <!-- % of Period before damage applies (0–1) -->
    <BackswingPoint value="0.5"/>              <!-- % of Period before unit can move/turn -->
    <Arc value="360"/>                          <!-- attack arc in degrees -->
    <Flags index="AttackTargetMover" value="1"/>
    <TargetFilters value="Visible;Self,Ally,Neutral,Dead,Invulnerable"/>
</CWeapon>
```

### Weapon key fields

| Field | Purpose |
|---|---|
| `Effect` | Root effect fired on attack |
| `DisplayEffect` | Effect used for tooltip damage display (can differ) |
| `Range` | Attack range |
| `Period` | Attack speed — seconds per attack |
| `DamagePoint` | Where in the Period animation the hit lands (0.0–1.0) |
| `BackswingPoint` | Where the unit can move again after attacking |
| `Arc` | Cone arc for directional weapons |
| `TargetFilters` | Which targets can be attacked |

---

## Effect Types

File: `Base.SC2Data/GameData/EffectData.xml`

### CEffectSet — chain multiple effects

```xml
<CEffectSet id="MyAbilityEffect">
    <EffectArray index="0" value="MyAbilityDamage"/>
    <EffectArray index="1" value="MyAbilityApplyBuff"/>
    <EffectArray index="2" value="MyAbilitySpawnUnit"/>
</CEffectSet>
```

### CEffectDamage — deal damage

```xml
<CEffectDamage id="MyWeaponDamage">
    <Amount value="25"/>
    <Kind value="Ranged"/>              <!-- Melee, Ranged, Spell, Splash -->
    <DamageModifierSource value="Weapon"/>
    <ValidatorArray index="0" value="IsTargetNotInvulnerable"/>
    <AttributeBonus index="Armored" value="10"/>  <!-- bonus vs Armored: 25+10=35 -->
    <AttributeBonus index="Light" value="5"/>
</CEffectDamage>
```

### CEffectApplyBehavior — apply a buff/debuff

```xml
<CEffectApplyBehavior id="MyStunApply">
    <Behavior value="MyStunBehavior"/>
    <ValidatorArray index="0" value="IsTargetAlive"/>
</CEffectApplyBehavior>
```

### CEffectRemoveBehavior — strip a buff

```xml
<CEffectRemoveBehavior id="MyBuffRemove">
    <Behavior value="MyBuff"/>
</CEffectRemoveBehavior>
```

### CEffectSearch — AoE by radius

```xml
<CEffectSearch id="MyAoeSearch">
    <AreaArray index="0" Radius="2.5" Effect="MyAoeDamage"
               TargetFilters="Visible,Alive;Self,Ally,Neutral,Dead"/>
    <SearchFlags index="SameCliff" value="1"/>   <!-- ignore units on different cliff levels -->
</CEffectSearch>
```

### CEffectEnumArea — custom-shape AoE

```xml
<CEffectEnumArea id="MyLineAoe">
    <AreaArray index="0" Effect="MyAoeDamage" Radius="2" Arc="30" Distance="8"/>
</CEffectEnumArea>
```

### CEffectLaunchMissile — spawn a projectile

```xml
<CEffectLaunchMissile id="MyMissileLaunch">
    <Mover value="MyMissile"/>
    <ImpactEffect value="MyMissileImpact"/>
    <LaunchMissileFlags index="DeleteOnImpact" value="1"/>
    <ImpactLocation><Effect value="TargetPoint"/></ImpactLocation>
</CEffectLaunchMissile>
```

### CEffectCreateUnit — spawn a unit

```xml
<CEffectCreateUnit id="SpawnMyUnit">
    <UnitType value="MySpawnUnit"/>
    <Owner value="Caster"/>              <!-- Caster, Neutral, etc. -->
    <Count value="1"/>
</CEffectCreateUnit>
```

### CEffectIssueOrder — command a unit

```xml
<CEffectIssueOrder id="ForceAttack">
    <Ability value="Attack"/>
    <AbilityCmd value="Attack"/>
</CEffectIssueOrder>
```

### CEffectModifyPlayer — modify a player resource

```xml
<CEffectModifyPlayer id="GrantMinerals">
    <Owner value="Caster"/>
    <Resource index="Minerals" value="50"/>   <!-- add 50 minerals to caster's player -->
</CEffectModifyPlayer>
```

---

## Effect Subtype Reference

Full list of all `CEffect*` subtypes for awareness:

| Subtype | Purpose |
|---|---|
| `CEffectSet` | Sequence multiple effects |
| `CEffectDamage` | Deal HP damage |
| `CEffectApplyBehavior` | Apply a buff/debuff behavior |
| `CEffectRemoveBehavior` | Strip a behavior |
| `CEffectSearch` | AoE by radius — runs sub-effect on all hits |
| `CEffectEnumArea` | Custom-shape AoE (arc, line) |
| `CEffectLaunchMissile` | Spawn a projectile that delivers an impact effect |
| `CEffectCreateUnit` | Spawn a unit |
| `CEffectIssueOrder` | Command a unit to perform an ability |
| `CEffectModifyPlayer` | Modify player resources (minerals, gas, supply) |
| `CEffectModifyUnit` | Modify unit vitals or stats directly |
| `CEffectCreatePersistent` | Create a timed persistent area (for abilities like Psi Storm) |
| `CEffectDestroyPersistent` | End a persistent effect early |
| `CEffectSwitch` | Conditional branch — pick effect by index |
| `CEffectRandom` | Random branch — pick from effect array randomly |
| `CEffectTeleport` | Move a unit to a new location instantly |
| `CEffectMorph` | Transform a unit into a different unit type |
| `CEffectTransferBehavior` | Move a behavior from one unit to another |
| `CEffectCancelOrder` | Cancel a unit's current order |
| `CEffectUserData` | Execute a user-data-driven branch (custom data lookups) |
| `CEffectLastTarget` | Re-use the final target from a previous effect |
| `CEffectUseCalldown` | Trigger a calldown ability |
| `CEffectLoadContainer` | Load a unit into transport |
| `CEffectRedirectMissile` | Change a missile's target mid-flight |
| `CEffectApplyForce` | Push a unit (physics force — used by e.g. Shockwave) |

---

## Effect Common Fields

These fields appear on most or all `CEffect*` types:

| Field | Purpose |
|---|---|
| `ValidatorArray` | AND gate — if any validator returns false, effect is skipped and linked actor event is suppressed |
| `Chance` | 0.0–1.0 probability the effect executes (default 1.0 = always) |
| `DebugTrace` | When `1`: shows visual debug markers in Test Mode at launch/impact locations |
| `CasterHistory` | Saves the effect in the caster's Effect History Limit (used by some validators) |
| `CanBeBlocked` | If `1`, queries the target unit's Block Chance — sends actor sub-event `Blocked` if blocked |

### Markers — prevent re-hitting in AoE

Markers tag a unit as already hit by this effect instance, preventing double-hits in area effects:

```xml
<CEffectSearch id="MySplash">
    <MarkerArray index="0" MatchFlags="Link" MismatchFlags=""/>
    <!-- Units already tagged with "Link" are skipped; new hits get tagged -->
</CEffectSearch>
```

Use `CValidatorUnitCompareMarkerCount` to gate effects based on marker state.

### Response & AI Notify Flags

| Field | Values | Meaning |
|---|---|---|
| `ResponseFlags` | `Acquire` | Target starts attacking the caster |
| `ResponseFlags` | `Flee` | Target runs away from caster |
| `AINotifyFlags` | `HelpFriend`, `HurtEnemy`, `HurtFriend`, `MajorDanger`, `MinorDanger` | Trigger AI threat/help response |

### First-effect targeting rule

The **first effect in an ability's effect chain** determines the ability's targeting type. If you need a targeted ability (click on unit or point), the root effect must be a type that accepts and uses a target. `CEffectIssueOrder` as the **first** effect will make the ability untargetable — place a `CEffectSet` first or ensure the ordering accounts for this.

---

## Damage Kind & Attribute Bonuses

| Kind | Notes |
|---|---|
| `Melee` | Affected by armor, melee upgrades |
| `Ranged` | Affected by armor, ranged upgrades |
| `Spell` | Ignores armor by default |
| `Splash` | Can hit multiple units |

Attribute bonuses add extra damage vs units with matching attributes:

```xml
<AttributeBonus index="Light" value="10"/>
<AttributeBonus index="Armored" value="5"/>
<AttributeBonus index="Biological" value="15"/>
<AttributeBonus index="Massive" value="20"/>
```

---

## Upgrades (`UpgradeData.xml`)

File: `Base.SC2Data/GameData/UpgradeData.xml`

Upgrades fire an effect chain when researched and can stack in levels:

```xml
<CUpgrade id="MyUpgrade">
    <EditorCategories value="Race:Terran"/>
    <Name value="Upgrade/Name/MyUpgrade"/>
    <EffectArray index="0" value="MyUpgradeEffect"/>
    <MaxLevel value="3"/>   <!-- 0 = no limit, 1 = single-level, 3 = tri-level -->
</CUpgrade>
```

Upgrades commonly fire `CEffectUpgradePlayer` (modify unit stats) or `CEffectApplyBehavior` effects.

---

## Validators in Effects

Attach validators to `ValidatorArray` on any effect. If **any validator returns false**, the effect is **not applied**:

```xml
<CEffectDamage id="ConditionalDamage">
    <Amount value="50"/>
    <ValidatorArray index="0" value="TargetIsExposed"/>
    <ValidatorArray index="1" value="CasterNotBurrowed"/>
</CEffectDamage>
```

See `sc2data-behaviors-validators` for validator definition patterns.

---

## TargetFind (`TargetFindData.xml`)

TargetFind types determine where an effect or weapon "finds" its target point/unit:

| Common TargetFind | Meaning |
|---|---|
| `TargetPoint` | The originally targeted location |
| `SourcePoint` | The caster's location |
| `BuffTarget` | Unit the behavior is applied to |

---

## Footprints (`FootprintData.xml` / `TerrainData.xml`)

Footprints define the terrain blocked by a structure:

```xml
<CFootprint id="MyStructureFootprint">
    <Layers index="0">
        <Row index="0" value="PPPPPP"/>
        <Row index="1" value="PPPPPP"/>
    </Layers>
</CFootprint>
```

`P` = passable, `X` = blocked.

---

## Naming Conventions

| Item | Convention |
|---|---|
| Weapon id | `UnitNameWeapon` or descriptive name (e.g. `MarineWeapon`) |
| Root effect id | Same as weapon or ability id (e.g. `MarineWeaponEffect`) |
| Damage effect id | Root + `Damage` (e.g. `MarineWeaponDamage`) |
| Search effect id | Root + `Search` (e.g. `SiegeSplashSearch`) |
| Apply behavior effect | `ApplyBehaviorName` (e.g. `ApplyLockedDown`) |
| Upgrade id | `PascalCase` (e.g. `InfantryWeaponLevel1`) |

---

## Best Practices

- Always route through a `CEffectSet` — even for a single effect — to make future additions trivial.
- Set `DisplayEffect` on weapons to the direct `CEffectDamage` so tooltips show accurate numbers.
- Add `ValidatorArray` on `CEffectDamage` for conditional hits rather than filtering at the weapon level.
- Use `CEffectSearch` + `CEffectDamage` for splash/AoE rather than multiple separate weapons.
- Effects are forward-declared: ability → effect → sub-effect(s). Do not circular-reference.
- Keep each effect id uniquely named; Blizzard's data is dense and naming collisions cause silent overrides.
